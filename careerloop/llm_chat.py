import os
import json
import logging
import requests
from typing import Tuple, Dict, Any

logger = logging.getLogger("careerloop.llm_chat")

class LLMChatAgent:
    def __init__(self, api_key: str = None, model: str = "deepseek-chat"):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.model = model

    RETRY_STATUSES = {429, 500, 502, 503, 504}
    MAX_RETRIES = 2
    SAFE_ERROR_MSG = (
        "I hit a model issue while processing that. "
        "Your data is safe. Try again or type /help for available commands."
    )

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """Call DeepSeek with retry on transient errors. Never return raw API text to user."""
        import time

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 4096,
                    },
                    timeout=30,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]

                # Retryable error?
                if response.status_code in self.RETRY_STATUSES and attempt < self.MAX_RETRIES:
                    wait = (attempt + 1) * 2
                    logger.warning(
                        "DeepSeek %d on attempt %d/%d, retrying in %ds",
                        response.status_code, attempt + 1, self.MAX_RETRIES + 1, wait,
                    )
                    time.sleep(wait)
                    continue

                # Non-retryable or exhausted retries — log internally, return safe message
                logger.error(
                    "DeepSeek API error %d after %d attempts: %s",
                    response.status_code, attempt + 1, response.text[:200],
                )
                return f'{{"reply": "{self.SAFE_ERROR_MSG}"}}'

            except requests.Timeout:
                if attempt < self.MAX_RETRIES:
                    logger.warning("DeepSeek timeout on attempt %d, retrying", attempt + 1)
                    time.sleep(2)
                    continue
                logger.error("DeepSeek timeout after %d attempts", self.MAX_RETRIES + 1)
                return f'{{"reply": "{self.SAFE_ERROR_MSG}"}}'

            except Exception as e:
                logger.exception("DeepSeek unexpected error on attempt %d", attempt + 1)
                if attempt < self.MAX_RETRIES:
                    time.sleep(2)
                    continue
                return f'{{"reply": "{self.SAFE_ERROR_MSG}"}}'

        return f'{{"reply": "{self.SAFE_ERROR_MSG}"}}'

    def _parse_json(self, text: str) -> dict:
        import re
        content = text.strip()
        
        # Try to find JSON block wrapped in markdown
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if match:
            content = match.group(1)
        else:
            # Fallback: extract anything that looks like a JSON object
            match = re.search(r'(\{.*\})', content, re.DOTALL)
            if match:
                content = match.group(1)
                
        try:
            return json.loads(content)
        except Exception as e:
            logger.debug(f"Failed to parse JSON. Error: {e}; raw content: {content[:500]}")
            return {}

class OnboardingAgent(LLMChatAgent):
    SYSTEM_PROMPT = """You are an intelligent onboarding agent for CareerLoop.
Your goal is to collect 6 key pieces of information from the user:
1. cv_content (full resume/CV text)
2. target_roles
3. target_cities
4. salary_expectations
5. notice_period
6. aggressiveness (e.g., High volume, Highly selective)

Analyze the user's message and update the extracted fields. If the user is asking a question, answer it. If some fields are missing, ask for them politely.
When all 6 fields are collected and non-empty, set "is_complete" to true. 
Return ONLY valid JSON in the following format:
{
  "extracted_fields": {
    "cv_content": "...",
    "target_roles": "...",
    "target_cities": "...",
    "salary_expectations": "...",
    "notice_period": "...",
    "aggressiveness": "..."
  },
  "reply": "Your message to the user here. Acknowledge what was provided, ask for what is missing.",
  "is_complete": false
}

CRITICAL JSON RULES:
- You MUST properly escape all newlines as \\n and double quotes as \\" inside cv_content.
- NEVER include literal unescaped newlines inside the JSON string values.
- Ensure you include all previously collected fields in "extracted_fields" if they are still valid, updating them if the user provided new info."""

    def process(self, user_message: str, current_data: Dict[str, Any]) -> Tuple[Dict[str, Any], str, bool]:
        prompt = f"""Current Data: {json.dumps(current_data)}
User Message: {user_message}"""
        raw_response = self._call_api(self.SYSTEM_PROMPT, prompt)
        result = self._parse_json(raw_response)
        
        extracted = result.get("extracted_fields", current_data)
        reply = result.get("reply", "I didn't quite get that. Could you provide your info again?")
        is_complete = result.get("is_complete", False)
        
        # Merge extracted with current data to ensure we don't lose fields if LLM hallucinated missing ones
        updated_data = current_data.copy()
        for k, v in extracted.items():
            if not isinstance(v, str):
                if v:
                    updated_data[k] = v
                continue
            normalized = v.strip()
            if normalized and normalized.lower() not in {"n/a", "na", "none", "null", "-"}:
                updated_data[k] = v
                
        return updated_data, reply, is_complete

class ChatIntentAgent(LLMChatAgent):
    SYSTEM_PROMPT = """You are the CareerLoop central router.
Analyze the user's message and their profile context.
Determine the user's intent from the following list:
- SHOW_PIPELINE: User wants to see their current jobs, daily briefing, pipeline, or shortlist. "daily briefing", "show my jobs", "pipeline status", "what jobs do I have" → SHOW_PIPELINE.
- SCAN_JOBS: User EXPLICITLY wants to run a NEW scan to find fresh jobs. Only use this for explicit scan/search requests like "scan for new jobs", "find me new jobs", "run a search".
- GENERAL_CHAT: User is just chatting or asking a general question.

Return ONLY valid JSON in the following format:
{
  "intent": "SHOW_PIPELINE",
  "reply": "If GENERAL_CHAT, put your intelligent conversational response here. If SHOW_PIPELINE, put a brief confirmation like 'Let me pull up your pipeline...'."
}"""

    def process(self, user_message: str, profile_data: Dict[str, Any]) -> Tuple[str, str]:
        # Only send a compact profile summary — never the full CV to the intent router.
        # Full CV content in the prompt causes DeepSeek to produce malformed JSON.
        compact = {}
        for key in ("target_roles", "target_cities", "salary_expectations",
                     "notice_period", "aggressiveness"):
            if profile_data.get(key):
                compact[key] = profile_data[key]
        cv = profile_data.get("cv_content", "")
        if cv and isinstance(cv, str):
            compact["has_cv"] = True
            compact["cv_preview"] = cv[:200]

        prompt = f"User Profile: {json.dumps(compact)}\nUser Message: {user_message}"
        raw_response = self._call_api(self.SYSTEM_PROMPT, prompt)
        result = self._parse_json(raw_response)

        if not result:
            logger.error("ChatIntentAgent JSON parse failed. Raw: %s", raw_response[:500])
            # Graceful fallback — defer to GENERAL_CHAT instead of guessing
            return "GENERAL_CHAT", (
                "I'm here to help with your job search! You can use these commands:\n"
                "• `/brief` — see today's job matches\n"
                "• `/scan` — search for new jobs\n"
                "• `/status` — view your profile\n"
                "• `/pipeline` — see all crawled jobs\n\n"
                "What would you like to do?"
            )

        intent = result.get("intent", "GENERAL_CHAT")
        reply = result.get("reply", "")
        if not reply:
            reply = "How can I help with your job search today?"
        return intent, reply


def validate_api_key() -> bool:
    """Check DEEPSEEK_API_KEY is set and non-empty. Log warning if missing."""
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        logging.getLogger("careerloop.llm_chat").critical(
            "DEEPSEEK_API_KEY is not set. All LLM calls will fail."
        )
        return False
    return True
