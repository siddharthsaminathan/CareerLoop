"""
CareerLoop India Fit Engine — LLM-based job scoring.

Uses DeepSeek API to evaluate fit across 14 dimensions.
Answers 4 questions per job:
A. Can this user plausibly do this job?
B. Does this user actually want this job?
C. Is this job strategically good for the user?
D. Is this worth applying to today?

No regex. No hardcoded company tables. Actual reasoning.
"""

import os
import json
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load env from career-ops root
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)

from careerloop.models import JobPosting, Recommendation


class LLMIndiaFitEngine:
    """
    LLM-powered India Fit scoring engine.
    """

    SYSTEM_PROMPT = """You are an India-specific career fit evaluator. Analyze the job posting against the user profile and return ONLY the JSON object below. No markdown. No explanation.

Return exactly this JSON structure:
{
  "overall_score": 0,
  "recommendation": "APPLY",
  "reason": "why this is a good fit in 1 sentence",
  "risks": ["risk 1", "risk 2"],
  "why_user_might_like_it": "what makes this attractive to this specific user",
  "why_user_might_hate_it": "what might make this user reject this job",
  "missing_info": ["info not available that would help scoring"],
  "confidence": 0.0,
  "dimensions": {
    "role_fit": 0,
    "skill_fit": 0,
    "location_fit": 0,
    "salary_fit": 5,
    "work_mode_fit": 5,
    "company_stability": 5,
    "brand_value": 5,
    "career_trajectory": 5,
    "response_likelihood": 5
  }
}

RULES:
- overall_score: 0-100 (weighted average of dimensions)
- recommendation: "APPLY" (>=70), "MAYBE" (50-69), or "SKIP" (<50)
- dimensions: each 0-10
- If user rejected_roles includes this role type → SKIP, score < 40
- If user rejected_company_types matches → SKIP, score < 40
- If location is not India and user is in India → lower location_fit
- If salary unknown → salary_fit = 5
- confidence: 0-1 (how confident are you in this score given available info)
- Be honest: low info = low confidence"""

    def __init__(self, api_key: str = None, model: str = "deepseek-v4-flash"):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.model = model

    def score_job(self, job: JobPosting, user_profile: dict) -> dict:
        """Score a single job against a user profile. Returns full JSON result."""
        user_prompt = self._build_user_prompt(job, user_profile)

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
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
                timeout=30,
            )

            if response.status_code != 200:
                return self._fallback_score(job, user_profile, f"API error: {response.status_code}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse JSON from response (handle markdown code blocks)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                if content.startswith("json"):
                    content = content[4:].strip()
            result = json.loads(content)

            # Validate required fields
            required = ["overall_score", "recommendation", "reason", "risks"]
            for field in required:
                if field not in result:
                    result[field] = "MISSING" if field != "overall_score" else 50

            result["_model"] = self.model
            result["_timestamp"] = datetime.now(timezone.utc).isoformat()
            return result

        except Exception as e:
            return self._fallback_score(job, user_profile, str(e))

    def _build_user_prompt(self, job: JobPosting, profile: dict) -> str:
        """Build the user prompt with job details and user profile."""

        # Build a clean user profile summary
        target_roles = profile.get("target_roles", [])
        confirmed_skills = profile.get("confirmed_skills", [])
        weak_skills = profile.get("weak_skills", [])
        rejected_roles = profile.get("rejected_roles", [])
        rejected_company_types = profile.get("rejected_company_types", [])
        preferred_company_types = profile.get("preferred_company_types", [])

        notice_days = profile.get("notice_period_days", 30)
        salary_floor = profile.get("salary_floor_lakhs", 0)
        expected_ctc = profile.get("expected_ctc_lakhs", 0)
        startup_tolerance = profile.get("startup_tolerance", 5)
        assignment_tolerance = profile.get("assignment_burden_tolerance", 5)
        location_city = profile.get("location_city", "")
        work_mode_pref = profile.get("location_flexibility", "")

        prompt = f"""JOB POSTING:
Title: {job.role_title}
Company: {job.company}
Location: {job.location}
Work Mode: {job.work_mode or 'unknown'}
Salary: {job.salary_range or 'not specified'}
Company Type: {job.company_type or 'unknown'}
Skills Required: {', '.join(job.skills_required) if job.skills_required else 'not specified'}
Description: {job.raw_description[:1000] or 'No description available'}
Source: {job.source}
Posted: {job.posted_at or 'unknown'}

USER PROFILE:
Target Roles: {', '.join(target_roles)}
Confirmed Skills: {', '.join(confirmed_skills) if confirmed_skills else 'not set'}
Weak Skills: {', '.join(weak_skills) if weak_skills else 'none'}
Rejected Roles: {', '.join(rejected_roles) if rejected_roles else 'none'}
Rejected Company Types: {', '.join(rejected_company_types) if rejected_company_types else 'none'}
Preferred Company Types: {', '.join(preferred_company_types) if preferred_company_types else 'none'}
Notice Period: {notice_days} days
Salary Floor: ₹{salary_floor}L
Expected CTC: ₹{expected_ctc}L
Startup Tolerance: {startup_tolerance}/10
Assignment Tolerance: {assignment_tolerance}/10
Location: {location_city}
Work Mode Preference: {work_mode_pref}

Score this job. Return ONLY valid JSON."""
        return prompt

    def _fallback_score(self, job: JobPosting, profile: dict, error: str) -> dict:
        """Fallback scoring when LLM is unavailable. Conservative, not aggressive."""
        return {
            "overall_score": 50,
            "recommendation": "MAYBE",
            "reason": f"LLM scoring unavailable ({error}). Manual review needed.",
            "risks": ["Automated scoring failed — review manually"],
            "why_user_might_like_it": "Unable to determine — LLM unavailable",
            "why_user_might_hate_it": "Unable to determine — LLM unavailable",
            "missing_info": ["Full JD text", "Salary details", "Work mode"],
            "confidence": 0.3,
            "_scoring_mode": "fallback",
            "_error": error,
        }

    def score_batch(self, jobs: list[JobPosting], profile: dict) -> list[dict]:
        """Score multiple jobs. Returns scored list sorted by overall_score desc."""
        results = []
        for job in jobs:
            result = self.score_job(job, profile)
            result["_job_fingerprint"] = job.fingerprint
            result["_company"] = job.company
            result["_role"] = job.role_title
            result["_location"] = job.location
            results.append(result)

        results.sort(key=lambda x: x.get("overall_score", 0), reverse=True)
        return results
