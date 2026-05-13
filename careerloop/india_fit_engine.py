"""
India Fit Engine — 14-dimension job scoring for Indian professionals.

Scores jobs on fit dimensions WITHOUT LLM calls.
Uses keyword matching, heuristics, and lookup tables from config.py.

Total: 100 points weighted across 14 dimensions.
"""

import re
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from careerloop.config import (
    FIT_WEIGHTS,
    COMPANY_STABILITY_SIGNALS,
    BRAND_VALUE_SIGNALS,
    INDIAN_TECH_CITIES,
    WORK_MODES,
)
from careerloop.profile_manager import ProfileManager


class IndiaFitEngine:
    """
    Scores a job against a user profile across 14 India-specific dimensions.

    Usage:
        engine = IndiaFitEngine(profile_manager)
        score, breakdown = engine.score_job(job_dict)
        # score: 0-100
        # breakdown: dict with per-dimension scores
    """

    def __init__(self, profile: ProfileManager):
        self.p = profile

    # ── Public API ────────────────────────────────────────────────────

    def score_job(self, job: dict) -> tuple[float, dict]:
        """
        Score a single job. Returns (total_score, breakdown).
        job dict must have: title, company, location, source
        Optional: salary_text, description, work_mode, posted_date
        """
        breakdown = {}
        total = 0.0

        dims = [
            ("role_fit", self._score_role_fit),
            ("skill_fit", self._score_skill_fit),
            ("salary_fit", self._score_salary_fit),
            ("location_fit", self._score_location_fit),
            ("work_mode_fit", self._score_work_mode_fit),
            ("notice_period_fit", self._score_notice_period_fit),
            ("company_stability", self._score_company_stability),
            ("startup_risk", self._score_startup_risk),
            ("brand_value", self._score_brand_value),
            ("commute_risk", self._score_commute_risk),
            ("assignment_burden", self._score_assignment_burden),
            ("interview_difficulty", self._score_interview_difficulty),
            ("response_likelihood", self._score_response_likelihood),
            ("career_trajectory", self._score_career_trajectory),
        ]

        for name, scorer in dims:
            raw = scorer(job)
            weight = FIT_WEIGHTS[name]
            weighted = (raw / 10.0) * weight
            breakdown[name] = {"raw": raw, "weight": weight, "weighted": round(weighted, 1)}
            total += weighted

        return round(total, 1), breakdown

    def score_jobs_batch(self, jobs: list) -> list:
        """Score multiple jobs, return sorted by score descending."""
        scored = []
        for job in jobs:
            score, breakdown = self.score_job(job)
            scored.append({"job": job, "score": score, "breakdown": breakdown})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    # ── Dimension Scorers (each returns 0-10) ─────────────────────────

    def _score_role_fit(self, job: dict) -> float:
        """Match job title against user's target roles and archetypes."""
        title = (job.get("title") or "").lower()
        score = 0.0

        # Primary target roles → strongest signal
        for role in self.p.target_roles:
            role_lower = role.lower()
            if role_lower in title or self._partial_match(role_lower, title):
                score = 9.0
                break

        # Archetype matching
        if score < 7:
            for arch in self.p.archetypes:
                arch_name = arch.get("name", "").lower()
                if arch_name and arch_name in title:
                    fit = arch.get("fit", "secondary")
                    score = max(score, 8.0 if fit == "primary" else 6.0 if fit == "secondary" else 4.0)

        # Keyword signals
        ai_signals = ["ai", "llm", "ml", "agent", "machine learning", "applied ai", "genai"]
        senior_signals = ["senior", "staff", "principal", "lead", "head", "founding"]
        product_signals = ["product engineer", "platform", "backend", "full stack"]

        if score == 0:
            # Fallback: count keyword overlap
            hits = sum(1 for kw in ai_signals + product_signals if kw in title)
            score = min(hits * 2.5, 7.0)

        # Seniority boost
        if any(s in title for s in senior_signals):
            score = min(score + 1, 10)

        # Rejected roles → instant penalty
        for rejected in self.p.rejected_roles:
            if rejected.lower() in title:
                score = max(score - 5, 0)

        return round(score, 1)

    def _score_skill_fit(self, job: dict) -> float:
        """Match job description skills against user's confirmed skills.
        Falls back to title + company signals when no description available."""
        desc = (job.get("description") or "").lower()
        title = (job.get("title") or "").lower()
        company = (job.get("company") or "").lower()
        confirmed = [s.lower() for s in self.p.confirmed_skills]
        weak = [s.lower() for s in self.p.weak_skills]

        if not confirmed:
            return 5.0

        # If we have description, match against it
        if desc and len(desc) > 50:
            confirmed_hits = sum(1 for s in confirmed if s in desc)
            weak_hits = sum(1 for s in weak if s in desc)
            hit_ratio = confirmed_hits / max(len(confirmed), 1)
            score = hit_ratio * 8 + 2
            score -= weak_hits * 0.5
            return round(max(0, min(10, score)), 1)

        # No description → infer skills from title + company
        # Known tech stacks by company type
        score = 5.0  # Start neutral

        # Title-based skill signals
        title_skill_map = {
            "ai": ["llm apis", "rag pipelines", "embeddings", "prompt engineering"],
            "ml": ["llm apis", "rag pipelines", "embeddings"],
            "llm": ["llm apis", "prompt engineering", "tool calling"],
            "agent": ["agentic workflows", "tool calling", "multi-model routing"],
            "backend": ["fastapi", "postgresql", "redis", "docker", "aws"],
            "platform": ["docker", "aws", "redis", "postgresql"],
            "full stack": ["fastapi", "sql", "docker"],
            "data": ["sql", "etl pipelines", "power bi", "postgresql"],
            "product engineer": ["fastapi", "postgresql", "redis", "agentic workflows"],
            "solutions": ["prompt engineering", "llm apis", "multi-model routing"],
            "forward deployed": ["llm apis", "tool calling", "fastapi"],
            "founding": ["agentic workflows", "multi-model routing", "tool calling"],
        }

        inferred_skills = set()
        for keyword, skills in title_skill_map.items():
            if keyword in title:
                inferred_skills.update(skills)

        # Company-specific signals
        company_skill_map = {
            "anthropic": ["llm apis", "prompt engineering", "agentic workflows"],
            "stripe": ["fastapi", "postgresql", "redis", "docker", "aws"],
            "gitlab": ["docker", "aws", "postgresql", "redis"],
            "vercel": ["fastapi", "docker", "aws"],
            "mongodb": ["postgresql", "redis", "aws", "docker"],
            "datadog": ["aws", "docker", "postgresql", "redis"],
            "cloudflare": ["aws", "docker", "fastapi"],
            "twilio": ["fastapi", "postgresql", "redis"],
        }
        if company in company_skill_map:
            inferred_skills.update(company_skill_map[company])

        if not inferred_skills:
            # Generic AI/engineering role → assume reasonable overlap
            if any(k in title for k in ["ai", "ml", "engineer", "backend", "platform"]):
                return 6.0
            return 5.0

        # Score based on inferred skill overlap with confirmed skills
        hits = sum(1 for s in inferred_skills if s in confirmed)
        ratio = hits / max(len(inferred_skills), 1)
        score = ratio * 7 + 3  # 3-10 range

        # Weak skills penalty
        weak_hits = sum(1 for s in weak if s in title)
        score -= weak_hits * 0.5

        # Seniority adjust: senior+ roles expect broader skill match
        if any(s in title for s in ["senior", "staff", "principal", "lead"]):
            score = min(score + 0.5, 10)

        return round(max(1, min(10, score)), 1)

    def _score_salary_fit(self, job: dict) -> float:
        """Check if job salary aligns with user expectations."""
        floor = self.p.salary_floor_lakhs
        if floor is None:
            return 5.0  # No preference set → neutral

        salary_text = (job.get("salary_text") or "").lower()

        # Try to extract numeric salary from text
        import re
        numbers = re.findall(r'[\d.]+', salary_text.replace(",", ""))
        if not numbers:
            return 5.0  # Can't determine → neutral

        # Heuristic: largest number in salary range is likely upper bound
        amounts = [float(n) for n in numbers]
        max_salary = max(amounts)

        # Normalize: if number looks like lakhs (common in India)
        if max_salary < 10:  # likely in lakhs already
            salary_lakhs = max_salary
        elif max_salary < 1000:  # could be thousands
            salary_lakhs = max_salary / 100
        else:  # likely raw number (e.g., 3500000 = 35L)
            salary_lakhs = max_salary / 100000

        if salary_lakhs >= floor:
            # Above floor: scale up to 10 based on how much above
            ratio = min(salary_lakhs / floor, 2.0)
            return round(5 + (ratio - 1) * 5, 1)
        else:
            # Below floor: penalize proportionally
            ratio = salary_lakhs / floor
            return round(ratio * 5, 1)

    def _score_location_fit(self, job: dict) -> float:
        """Match job location against user's city preferences."""
        job_loc = (job.get("location") or "").lower()
        user_city = self.p.location_city.lower()

        if not job_loc:
            return 5.0

        # Direct match with user's city
        if user_city in job_loc:
            return 10.0

        # Check aliases
        for city, info in INDIAN_TECH_CITIES.items():
            if city == user_city:
                if any(alias in job_loc for alias in [city] + info["aliases"]):
                    return 10.0

        # Remote
        if "remote" in job_loc:
            return 9.0

        # Same tier city
        user_tier = None
        for city, info in INDIAN_TECH_CITIES.items():
            if city == user_city or user_city in info["aliases"]:
                user_tier = info["tier"]
                break
            # Also check if user_city matches an alias
            if user_city in info["aliases"]:
                user_tier = info["tier"]
                break

        if user_tier:
            for city, info in INDIAN_TECH_CITIES.items():
                if city in job_loc or any(a in job_loc for a in info["aliases"]):
                    if info["tier"] == user_tier:
                        return 7.0  # Same tier, different city
                    else:
                        return 4.0  # Different tier

        # India but unknown city match
        if "india" in job_loc:
            return 6.0

        # International — would need relocation
        if self.p.extended.get("willing_to_relocate"):
            return 5.0
        else:
            return 2.0

    def _score_work_mode_fit(self, job: dict) -> float:
        """Match remote/hybrid/onsite against user preference."""
        mode = (job.get("work_mode") or job.get("location") or "").lower()

        # User preference from profile (default: remote-friendly)
        loc_flex = self.p.base.get("compensation", {}).get("location_flexibility", "").lower()
        prefers_remote = "remote" in loc_flex

        if "remote" in mode or "work from home" in mode or "wfh" in mode:
            return 10.0 if prefers_remote else 8.0
        elif "hybrid" in mode:
            return 8.0 if prefers_remote else 10.0
        elif "onsite" in mode or "on-site" in mode or "in-office" in mode:
            return 4.0 if prefers_remote else 7.0
        else:
            return 5.0  # Unknown

    def _score_notice_period_fit(self, job: dict) -> float:
        """Check if job's notice period requirement matches user's."""
        desc = (job.get("description") or "").lower()
        user_notice = self.p.notice_period_days

        # Look for notice period mentions in JD
        notice_patterns = [
            (r"notice period[:\s]*(\d+)\s*(?:days|d)", 1),
            (r"immediate(?:ly)?\s*(?:joining|joiner)", 0),
            (r"(\d+)\s*(?:days|d)\s*notice", 1),
            (r"can join(?: in)?\s*(\d+)\s*(?:days|d)", 1),
        ]

        for pattern, group in notice_patterns:
            match = re.search(pattern, desc)
            if match:
                if group == 0:
                    required_days = 0
                else:
                    required_days = int(match.group(group))

                if user_notice <= required_days:
                    return 10.0
                elif user_notice <= required_days * 1.5:
                    return 7.0
                elif user_notice <= required_days * 2:
                    return 4.0
                else:
                    return 2.0

        # No notice period mentioned → neutral
        return 7.0

    def _score_company_stability(self, job: dict) -> float:
        """Score company stability from signals lookup."""
        company = (job.get("company") or "").lower()
        raw = COMPANY_STABILITY_SIGNALS.get(company, COMPANY_STABILITY_SIGNALS["__default__"])
        return float(raw)

    def _score_startup_risk(self, job: dict) -> float:
        """Inverse of stability + user's startup tolerance. Lower = riskier."""
        stability = self._score_company_stability(job)
        # Invert: stable company = low startup risk (good = high score)
        # 10 (most stable) → startup risk score 10 (good)
        # 5 (default/unknown) → startup risk score scales with user tolerance
        company = (job.get("company") or "").lower()

        # Known startups: risk inversely proportional to stability
        if stability <= 5:
            # High-risk startup: score depends on user tolerance
            return float(self.p.startup_tolerance)
        elif stability <= 7:
            return 8.0
        else:
            return 10.0  # Established company = low startup risk

    def _score_brand_value(self, job: dict) -> float:
        """Career resume value of having this company on your CV."""
        company = (job.get("company") or "").lower()
        return float(BRAND_VALUE_SIGNALS.get(company, BRAND_VALUE_SIGNALS["__default__"]))

    def _score_commute_risk(self, job: dict) -> float:
        """Lower score = worse commute. Higher = better."""
        job_loc = (job.get("location") or "").lower()
        user_city = self.p.location_city.lower()

        if not job_loc or "remote" in job_loc:
            return 10.0  # No commute

        if user_city in job_loc:
            # Same city — depends on size and traffic
            for city, info in INDIAN_TECH_CITIES.items():
                if city in job_loc or any(a in job_loc for a in info["aliases"]):
                    if city in ["bangalore", "mumbai", "delhi"]:
                        return 6.0  # Terrible traffic
                    elif city in ["chennai", "hyderabad", "pune"]:
                        return 7.0  # Bad but manageable
                    else:
                        return 8.0  # Better
            return 7.0  # Same city, unknown

        # Different city — relocation needed
        if self.p.extended.get("willing_to_relocate"):
            relo_cities = self.p.extended.get("relocation_cities", [])
            if any(c.lower() in job_loc for c in relo_cities):
                return 8.0  # Willing to relocate here
            return 5.0  # Relocation needed, not preferred city
        return 2.0  # Can't/won't relocate

    def _score_assignment_burden(self, job: dict) -> float:
        """Penalize jobs that likely have heavy take-home assignments."""
        desc = (job.get("description") or "").lower()
        title = (job.get("title") or "").lower()

        # Signals of assignment-heavy hiring
        assignment_signals = [
            "take home", "assignment", "case study", "coding challenge",
            "project round", "hackathon", "presentation",
        ]
        signal_count = sum(1 for s in assignment_signals if s in desc)

        # Some roles are known for heavy assignments
        heavy_assignment_roles = ["frontend", "full stack", "mobile", "ios", "android"]
        is_heavy_role = any(r in title for r in heavy_assignment_roles)

        base = 10.0  # Start perfect (no burden)
        base -= signal_count * 1.5
        if is_heavy_role:
            base -= 2.0

        # User's tolerance adjusts the impact
        tolerance = self.p.assignment_burden_tolerance
        if tolerance >= 8:
            base = min(base + 2, 10)  # Doesn't mind assignments

        return round(max(0, min(10, base)), 1)

    def _score_interview_difficulty(self, job: dict) -> float:
        """Estimate interview difficulty. Higher = easier (better)."""
        title = (job.get("title") or "").lower()
        company = (job.get("company") or "").lower()

        # Known hard interviewers
        hard_companies = {"anthropic", "openai", "stripe", "atlassian", "uber", "google", "meta", "apple"}
        if company in hard_companies:
            base = 2.0
        else:
            base = 5.0

        # Senior roles are harder
        if any(s in title for s in ["staff", "principal", "lead", "head", "director"]):
            base -= 2.0
        elif any(s in title for s in ["senior"]):
            base -= 1.0

        # AI/research roles often have harder loops
        if any(k in title for k in ["ai", "ml", "research", "llm"]):
            base -= 1.0

        return round(max(1, min(10, base)), 1)

    def _score_response_likelihood(self, job: dict) -> float:
        """Estimate probability of getting a response."""
        company = (job.get("company") or "").lower()
        posted = job.get("posted_date") or job.get("source_date") or ""

        base = 5.0

        # Known fast-hiring companies
        fast_companies = {"stripe", "atlassian", "gitlab", "cloudflare", "mongodb", "datadog"}
        if company in fast_companies:
            base += 2.0

        # Direct ATS postings (Greenhouse/Lever) = more likely real
        source = job.get("source") or ""
        if "greenhouse" in source or "lever" in source or "ashby" in source:
            base += 1.0

        # Recent postings (within 2 weeks) = more likely active
        if posted:
            from datetime import datetime, timedelta
            try:
                if isinstance(posted, str):
                    posted_date = datetime.fromisoformat(posted[:10])
                    age_days = (datetime.now() - posted_date).days
                    if age_days <= 7:
                        base += 3.0
                    elif age_days <= 14:
                        base += 1.0
                    elif age_days > 30:
                        base -= 2.0
            except (ValueError, TypeError):
                pass

        return round(max(1, min(10, base)), 1)

    def _score_career_trajectory(self, job: dict) -> float:
        """How much does this role advance the user's career?"""
        title = (job.get("title") or "").lower()
        company = (job.get("company") or "").lower()

        base = 5.0

        # Seniority signals = trajectory positive
        seniority = ["senior", "staff", "principal", "lead", "head", "founding"]
        for i, s in enumerate(seniority):
            if s in title:
                base += (i + 1) * 0.8
                break

        # AI/ML roles = high growth
        if any(k in title for k in ["ai", "ml", "llm", "agent", "machine learning"]):
            base += 1.5

        # Strong brand = resume value
        brand = BRAND_VALUE_SIGNALS.get(company, BRAND_VALUE_SIGNALS["__default__"])
        if brand >= 8:
            base += 1.5
        elif brand >= 6:
            base += 0.5

        return round(max(1, min(10, base)), 1)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _partial_match(role: str, title: str) -> bool:
        """Check if most words of role appear in title."""
        role_words = set(role.lower().split())
        title_words = set(title.lower().split())
        if not role_words:
            return False
        overlap = role_words & title_words
        return len(overlap) / len(role_words) >= 0.6
