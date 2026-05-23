import os
import json
import requests
from typing import Tuple, Dict, Any

class LLMChatAgent:
    def __init__(self, api_key: str = None, model: str = "deepseek-chat"):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.model = model

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
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
                    "max_tokens": 1500,
                },
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f'{{"reply": "API error: {response.status_code}"}}'
        except Exception as e:
            return f'{{"reply": "Exception: {str(e)}"}}'

    def _parse_json(self, text: str) -> dict:
        content = text.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            if content.startswith("json"):
                content = content[4:].strip()
        try:
            return json.loads(content)
        except Exception:
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
Note: Ensure you include all previously collected fields in "extracted_fields" if they are still valid, updating them if the user provided new info."""

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
            if v and v.strip():
                updated_data[k] = v
                
        return updated_data, reply, is_complete

class ChatIntentAgent(LLMChatAgent):
    SYSTEM_PROMPT = """You are the CareerLoop central router.
Analyze the user's message and their profile context.
Determine the user's intent from the following list:
- SCAN_JOBS: User wants to scan/find new jobs.
- SHOW_PIPELINE: User wants to see their job pipeline.
- GENERAL_CHAT: User is just chatting or asking a general question.

Return ONLY valid JSON in the following format:
{
  "intent": "SCAN_JOBS",
  "reply": "If GENERAL_CHAT, put your intelligent conversational response here. If SCAN_JOBS, put a brief confirmation like 'Scanning jobs now...'."
}"""

    def process(self, user_message: str, profile_data: Dict[str, Any]) -> Tuple[str, str]:
        prompt = f"""User Profile: {json.dumps(profile_data)}
User Message: {user_message}"""
        raw_response = self._call_api(self.SYSTEM_PROMPT, prompt)
        result = self._parse_json(raw_response)
        
        intent = result.get("intent", "GENERAL_CHAT")
        reply = result.get("reply", "I'm not sure how to respond to that.")
        return intent, reply
