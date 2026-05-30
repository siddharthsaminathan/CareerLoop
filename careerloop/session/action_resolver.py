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

CRITICAL CONTEXT RULES:
- If the user's journey state is NEW_USER: they are still setting up their profile.
  Statements about target roles, cities, salary, notice period, or preferences
  are profile setup — NOT job search requests. Route to GENERAL_CHAT only.
  NEVER route NEW_USER messages to START_SCAN, SHOW_BRIEF, or SHOW_PIPELINE.

- START_SCAN should ONLY be triggered when the user EXPLICITLY asks to search,
  scan, or find new jobs AND their state is PROFILE_READY or higher.
  Keywords that trigger START_SCAN: "scan now", "find new jobs", "search for jobs",
  "run a scan", "start scanning", "look for new roles", "find me something fresh".

- "I want [role] roles in [city]" during NEW_USER or with incomplete profile
  is profile information, NOT a scan request.

- "Find [role] jobs in [city] now" with PROFILE_READY is START_SCAN.

Available actions and when to use them:
- SHOW_BRIEF: User wants to see TODAY's already-generated job matches. Does NOT trigger a new scan.
  If no brief exists for today, tell the user they can start a scan.
- START_SCAN: User EXPLICITLY wants to run a NEW job search NOW. This is expensive (156 API calls,
  60-120 seconds). Only use when the user clearly says "scan", "search", "find jobs", "look for".
  Do NOT trigger from profile statements, casual conversation, or hypothetical questions.
- SHOW_PIPELINE: User wants to see their pipeline status or all tracked jobs.
- SHOW_STATUS: User asks about their current state or profile status.
- SHOW_PROFILE: User EXPLICITLY asks to see their full profile, resume, or CV as a document.
  Examples: "show me my resume", "show my profile", "display my CV", "what does my profile look like".
  Do NOT use for specific field questions — those go to GENERAL_CHAT.
  Examples that are NOT SHOW_PROFILE: "what roles am I targeting?", "what's my salary?", "which cities?",
  "do you know my name?", "do you have my profile?" — these are GENERAL_CHAT (answer conversationally).
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
- GENERAL_CHAT: Casual conversation, specific profile field questions ("what roles am I targeting?",
  "what's my expected salary?", "which cities did I pick?", "do you know my name?", "do you have my profile?"),
  or anything that doesn't fit a more specific action. The system will answer using stored profile context.

Context rules:
- If active_artifact_type is "daily_brief" and user says a number OR describes a job ("the first one", "the Stripe role") → SELECT_BRIEF_ITEM
- If active_artifact_type is "job_card" → actions relate to that job (REVIEW_JOB, PREPARE_APPLICATION_PACK, SKIP_JOB, etc.)
- If no active context and user asks to see jobs they already have → SHOW_BRIEF
- If no active context and user explicitly asks to find/search/scan for NEW jobs AND state is PROFILE_READY or higher → START_SCAN
- If state is NEW_USER: profile statements (roles, cities, salary, notice, preferences) → GENERAL_CHAT (not SHOW_BRIEF or START_SCAN)
- Specific profile field questions (roles, salary, cities, notice period, name) → GENERAL_CHAT even when PROFILE_READY
- "show me my resume / profile / CV" (full document request) → SHOW_PROFILE
- Default to GENERAL_CHAT for casual conversation

Return ONLY valid JSON:
{
  "action_type": "SHOW_BRIEF",
  "parsed_args": {},
  "confidence": 0.95,
  "reasoning": "brief one-sentence explanation"
}"""

    # Slash commands that are always allowed regardless of onboarding state
    _ONBOARDING_SAFE_COMMANDS = {"/reset", "/help"}
    # Slash commands that require PROFILE_READY or higher
    _PROFILE_REQUIRED_COMMANDS = {"/scan", "/brief", "/pipeline", "/status", "/profile"}

    def resolve(self, user_message: str, user_id: str, state: UserJourneyState, artifact_context: Dict[str, Any], messages: List[BaseMessage] = None) -> Action:
        msg_lower = user_message.strip().lower()

        # Hard guard: NEW_USER must complete onboarding before accessing any
        # scan/brief/pipeline actions. This cannot be bypassed by slash commands.
        if state == UserJourneyState.NEW_USER:
            cmd = msg_lower.split()[0] if msg_lower.startswith("/") else ""
            if cmd and cmd not in self._ONBOARDING_SAFE_COMMANDS:
                return Action(
                    action_type=ActionType.GENERAL_CHAT,
                    user_id=user_id,
                    raw_text=user_message,
                    parsed_args={"onboarding_blocked": True},
                    confidence=1.0,
                )
            if not cmd:
                # Non-slash messages during onboarding → GENERAL_CHAT (routed to onboarding flow by supervisor)
                return Action(
                    action_type=ActionType.GENERAL_CHAT,
                    user_id=user_id,
                    raw_text=user_message,
                    confidence=1.0,
                )

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
