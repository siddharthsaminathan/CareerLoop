import logging
import json
from typing import Optional, List, Dict, Any

from langchain_core.messages import BaseMessage
from careerloop.llm_chat import LLMChatAgent
from careerloop.session.models import Action, ActionType
from careerloop.session.states import UserJourneyState

logger = logging.getLogger("careerloop.session.action_resolver")

class ActionResolver(LLMChatAgent):
    SYSTEM_PROMPT = """You are the CareerLoop Action Resolver. Given the user's message, their journey state, active UI context, and recent conversation history, determine which action to take.

Available actions and when to use them:
- SHOW_BRIEF: User wants to see today's job matches or daily briefing.
- START_SCAN: User explicitly wants to find NEW jobs now.
- SHOW_PIPELINE: User wants to see their pipeline status or all tracked jobs.
- SHOW_STATUS: User asks about their current state or profile status.
- SHOW_PROFILE: User asks about their stored profile details.
- SHOW_COMPANY_INTEL: User asks about the company of the currently selected job.
- SHOW_PEOPLE_TO_REACH: User asks who to contact at a company.
- SELECT_BRIEF_ITEM: User selects a specific job from the active brief (by number or description). Set parsed_args.index to the 1-based index.
- REVIEW_JOB: User wants detailed fit analysis for the active job.
- SKIP_JOB: User wants to skip/dismiss the current job.
- SAVE_JOB: User wants to save the current job for later.
- PREPARE_APPLICATION_PACK: User wants to prepare application materials for the active job.
- EDIT_APPLICATION_PACK: User wants to modify an application pack.
- MARK_APPLIED: User confirms they applied to the active job.
- HELP: User asks what commands are available.
- RESET_SESSION: User wants to start over.
- GENERAL_CHAT: Casual conversation or questions that don't fit other actions.

Context rules:
- If active_artifact_type is "daily_brief" and user says a number OR describes a job ("the first one", "the Stripe role") → SELECT_BRIEF_ITEM
- If active_artifact_type is "job_card" → actions relate to that job (REVIEW_JOB, PREPARE_APPLICATION_PACK, SKIP_JOB, etc.)
- If no active context and user asks about jobs → SHOW_BRIEF
- If no active context and user asks to find jobs → START_SCAN
- Default to GENERAL_CHAT for casual conversation

Return ONLY valid JSON:
{
  "action_type": "SHOW_BRIEF",
  "parsed_args": {},
  "confidence": 0.95,
  "reasoning": "brief one-sentence explanation"
}"""

    def resolve(self, user_message: str, user_id: str, state: UserJourneyState, artifact_context: Dict[str, Any], messages: List[BaseMessage] = None) -> Action:
        msg_lower = user_message.strip().lower()

        _SLASH_MAP = {
            "/brief": ActionType.SHOW_BRIEF,
            "/scan": ActionType.START_SCAN,
            "/pipeline": ActionType.SHOW_PIPELINE,
            "/status": ActionType.SHOW_STATUS,
            "/profile": ActionType.SHOW_PROFILE,
            "/reset": ActionType.RESET_SESSION,
            "/help": ActionType.HELP,
        }

        # Slash commands → direct Action mapping (no LLM needed)
        if msg_lower.startswith("/"):
            cmd = msg_lower.split()[0]
            action_type = _SLASH_MAP.get(cmd)
            if action_type:
                return Action(
                    action_type=action_type,
                    user_id=user_id,
                    raw_text=user_message,
                    confidence=1.0,
                )

        # Context-aware number selection — only when user is looking at a daily brief
        if msg_lower.isdigit():
            if artifact_context.get("active_artifact_type") == "daily_brief":
                return Action(
                    action_type=ActionType.SELECT_BRIEF_ITEM,
                    user_id=user_id,
                    raw_text=user_message,
                    parsed_args={"index": int(msg_lower)},
                    confidence=1.0,
                )
            # Otherwise: bare number with no brief context → let LLM handle naturally
                
        # Build context-rich prompt for LLM
        recent_history = ""
        if messages:
            history_entries = []
            for m in messages[-6:]:  # last 6 messages
                role = "User" if hasattr(m, 'content') and not hasattr(m, 'tool_calls') else "Assistant"
                content = m.content if hasattr(m, 'content') else str(m)
                history_entries.append(f"{role}: {content}")
            recent_history = "\n".join(history_entries)

        prompt = f"""Current State: {state.value}
Active Context: {json.dumps(artifact_context)}
Recent Conversation:
{recent_history or '(no prior messages)'}

User Message: {user_message}
"""
        raw_response = self._call_api(self.SYSTEM_PROMPT, prompt)
        result = self._parse_json(raw_response)

        action_type_str = result.get("action_type", "GENERAL_CHAT")
        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            action_type = ActionType.GENERAL_CHAT
            
        parsed_args = result.get("parsed_args", {})
            
        return Action(
            action_type=action_type,
            user_id=user_id,
            raw_text=user_message,
            parsed_args=parsed_args,
            confidence=result.get("confidence", 0.5)
        )
