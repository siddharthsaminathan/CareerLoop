import os
import json
import requests
import logging
import time
from typing import Any, Optional, Union

logger = logging.getLogger("careerloop.outreach_engine")

# ── Resilient ddgs Search Engine ───────────────────────────────────────────────
def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """Uses the official ddgs package to search DuckDuckGo text index."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            logger.error("Neither ddgs nor duckduckgo_search library is installed.")
            return []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region="in-en"))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                }
                for r in results
            ]
    except Exception as e:
        logger.error(f"DDG search query failed for '{query}': {e}")
        return []

# ── Core Outreach & Matching Engine ────────────────────────────────────────────
class OutreachEngine:
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.model = model

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        """Standard HTTP post request wrapper for DeepSeek/OpenAI endpoint."""
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is missing from environment.")
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
                    "temperature": temperature,
                },
                timeout=30,
            )
            if response.status_code != 200:
                raise RuntimeError(f"DeepSeek API error: {response.status_code} - {response.text}")
            
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"LLM Call failed: {e}")
            raise

    def classify_route(self, jd_text: str) -> dict:
        """
        Step 1: Check if the JD explicitly names a recruiter/poster.
        Returns Route details.
        """
        system_prompt = """You are an application route classifier. 
Analyze the job description text and check if there is an explicit named recruiter or job poster mentioned.
Return ONLY a raw JSON string. No markdown, no triple backticks.

Expected JSON Structure:
{
  "route": "Route A" or "Route C",
  "has_explicit_poster": true or false,
  "poster_name": "Name of poster if found, else empty",
  "poster_title": "Title of poster if found, else empty",
  "reason": "Brief reason for classification"
}"""
        user_prompt = f"Analyze this job description:\n\n{jd_text}"
        try:
            response_content = self._call_llm(system_prompt, user_prompt)
            # Handle markdown code fences safely
            if response_content.startswith("```"):
                lines = response_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_content = "\n".join(lines).strip()
            if response_content.startswith("json"):
                response_content = response_content[4:].strip()
            
            return json.loads(response_content)
        except Exception as e:
            logger.error(f"classify_route failed: {e}")
            return {
                "route": "Route C",
                "has_explicit_poster": False,
                "poster_name": "",
                "poster_title": "",
                "reason": f"Fallback due to parse error: {e}"
            }

    def discover_leads(self, company_name: str) -> list[dict]:
        """
        Step 2: Scrape Google/DDG proxy pages to find recruiter and hiring manager leads.
        """
        queries = [
            f'{company_name} Talent Acquisition Recruiter LinkedIn',
            f'{company_name} Head of Engineering LinkedIn',
            f'{company_name} VP Engineering LinkedIn'
        ]
        
        all_leads = []
        seen_urls = set()
        
        for q in queries:
            results = _ddg_search(q, max_results=5)
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    all_leads.append(r)
                    seen_urls.add(url)
            time.sleep(1.0)
                    
        return all_leads

    def parse_and_rank_leads(self, leads: list[dict], jd_text: str) -> dict:
        """
        Steps 3 & 4: LLM Structured Parser + Relevance Matcher.
        Cleans search results and scores them to find the #1 Recruiter and #1 Hiring Manager.
        """
        if not leads:
            return {"recruiter": None, "hiring_manager": None, "all_leads": []}

        system_prompt = """You are a profile relevance matcher.
Analyze the list of crawled search snippets against the target job description.
Extract the people, categorize them, and assign a Plausibility Score (1-5) on how likely they are to be the recruiter or hiring manager for this role.

1 = No match / irrelevant role
2 = Same company but wrong department / location
3 = Possible peer or related team member
4 = Direct talent recruiter or engineering leader in same department
5 = Explicitly the EM / Recruiter listed for the job

Return ONLY a raw JSON string. No markdown, no triple backticks.

Expected JSON Structure:
{
  "recruiter": {
    "name": "...",
    "title": "...",
    "linkedin_url": "...",
    "plausibility_score": 4,
    "reason": "..."
  } or null,
  "hiring_manager": {
    "name": "...",
    "title": "...",
    "linkedin_url": "...",
    "plausibility_score": 5,
    "reason": "..."
  } or null,
  "all_leads": [
    {
      "name": "...",
      "title": "...",
      "linkedin_url": "...",
      "score": 3,
      "category": "Recruiter" or "Hiring Manager" or "Other"
    }
  ]
}"""

        user_prompt = f"JOB DESCRIPTION:\n{jd_text}\n\nCRAWLED PROFILES:\n{json.dumps(leads, indent=2)}"
        try:
            response_content = self._call_llm(system_prompt, user_prompt)
            # Handle markdown code fences safely
            if response_content.startswith("```"):
                lines = response_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_content = "\n".join(lines).strip()
            if response_content.startswith("json"):
                response_content = response_content[4:].strip()

            return json.loads(response_content)
        except Exception as e:
            logger.error(f"parse_and_rank_leads failed: {e}")
            return {"recruiter": None, "hiring_manager": None, "all_leads": []}

    def generate_outreach_pack(self, target_profile: dict, user_profile: dict, jd_text: str, route: str) -> dict:
        """
        Step 5: Synthesize outreach DMs. Includes strict Anti-AI humanizer and Andrej Karpathy's style principles.
        """
        system_prompt = """You are an elite, high-converting human outreach specialist.
Your goal is to write a highly tailored, direct, and completely professional outreach message.

CRITICAL TONE & STYLE CONSTRAINTS (ANTI-AI HUMANIZER):
- STRICTLY FORBIDDEN (AI buzzwords): Do not use "spearheaded", "leveraged", "utilize", "synergy", "cutting-edge", "delve", "empower", "thrilled", "passionate", "groundbreaking", "excited".
- FORBIDDEN MULTIPLIERS & HYPERBOLE: Do not use relative multipliers like "10x", "50x", or "15x" speedup/cost reduction. These read like ungrounded AI puffery. Always use absolute, credible engineering bounds (e.g., "inference costs under $0.02", "latencies under 3s", "scaled to 450+ active users").
- NO VAGUE COPE: Do not say "your company is doing amazing work" or validate them unnecessarily. Keep it professional, calm, and grounded.
- ACTION & SOLUTION-DRIVEN PROOF-OF-WORK: You must frame the message around the company's active engineering/GTM scaling problems described in the JD. Pitch yourself as an active builder proposing a solution. Directly link your live product **Emote (emotenow.app)** in the DM as primary proof-of-work. Example structure: "I saw you are building [X]. I built Emote (emotenow.app) solving [Y] with [Z] metrics, and want to help you scale [W]."
- PEER-TO-PEER CADENCE: Talk like an extremely competent Senior Engineer/Product lead talking to another. No subservience, no transactional sales pitch.
- SHORT & PUNCHY: Keep the message under 3 sentences / 120 words. Every sentence must hold high information density.

Return ONLY a raw JSON string. No markdown, no triple backticks.

Expected JSON Structure:
{
  "outreach_dm": "The finalized human outreach text.",
  "exit_line": "Direct, professional call to action.",
  "email_guesses": ["first.last@company.com", "first@company.com"]
}"""

        user_prompt = f"""Target Lead Profile:
{json.dumps(target_profile, indent=2)}

User Profile:
{json.dumps(user_profile, indent=2)}

Job Description:
{jd_text}

Route Selected: {route}"""

        try:
            response_content = self._call_llm(system_prompt, user_prompt, temperature=0.1)
            # Handle markdown code fences safely
            if response_content.startswith("```"):
                lines = response_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_content = "\n".join(lines).strip()
            if response_content.startswith("json"):
                response_content = response_content[4:].strip()

            return json.loads(response_content)
        except Exception as e:
            logger.error(f"generate_outreach_pack failed: {e}")
            return {
                "outreach_dm": "Fallback message: Hey, I saw the open role at your company and wanted to connect to share my experience in AI engineering.",
                "exit_line": "Let me know if you have 5 minutes to chat.",
                "email_guesses": []
            }
