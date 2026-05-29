"""
India Fit Engine — dynamic, intent-based job scoring.

Refactored 2026-05-18. Removed hardcoded AI/ML keyword bias, company lookup
tables, and role-specific tech stack maps. All scoring is now driven by:

1. JD structured fields (role_summary, responsibilities, requirements, benefits)
   — extracted verbatim by sources/ats_adapter.py and sources/company_portal_scraper.py.
2. User profile (target_functions, confirmed_skills, salary band, ESOPs,
   benefits_must_have, sector preferences, location, work mode).
3. Company memory table — for stability and brand value when known.

No LLM calls per job. Pure heuristic pre-filter. The LLM rescore is
LLMIndiaFitEngine.

15 weighted dimensions, total 100 points. See config.FIT_WEIGHTS.
"""

import re
from typing import Optional, TYPE_CHECKING

from careerloop.config import (
    FIT_WEIGHTS,
    COMPANY_STABILITY_DEFAULT,
    BRAND_VALUE_DEFAULT,
    INDIAN_TECH_CITIES,
)

if TYPE_CHECKING:
    from careerloop.profile_manager import ProfileManager


# ── Token & text helpers ─────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    return set(_TOKEN_RE.findall(text.lower()))


def _overlap_ratio(needles: list[str], haystack_tokens: set[str]) -> float:
    """Fraction of multi-word needles whose tokens are mostly present in haystack."""
    if not needles:
        return 0.0
    hits = 0
    for needle in needles:
        needle_tokens = _tokens(needle)
        if not needle_tokens:
            continue
        present = sum(1 for t in needle_tokens if t in haystack_tokens)
        if present / len(needle_tokens) >= 0.6:
            hits += 1
    return hits / len(needles)


def _jd_text(job: dict) -> str:
    """Combine all available JD fields into one searchable text blob."""
    parts = [
        job.get("title", ""),
        job.get("role_summary", ""),
        job.get("responsibilities", ""),
        job.get("requirements", ""),
        job.get("benefits", ""),
        job.get("description", ""),
        job.get("raw_jd_text", ""),
    ]
    return " ".join(str(p) for p in parts if p)


# ── Company memory accessor ──────────────────────────────────────────────

def _company_memory_lookup(company_name: str, conn=None) -> dict:
    """Pull stability + brand_value + sector signals from company_memory table.
    Returns {} on miss — caller falls back to defaults."""
    if not company_name:
        return {}
    try:
        from careerloop.memory.connection import get_db_manager
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "company_memory_lookup failed for '%s': %s — using defaults", company_name, e
        )
        return {}
    try:
        db = get_db_manager()
        normalized = re.sub(r"[^a-z0-9]+", "", company_name.lower())
        
        if conn is not None:
            cur = conn.cursor()
            cur.execute(
                "SELECT startup_risk, company_maturity, company_intelligence "
                "FROM careerloop.company_memory WHERE company_normalized = %s",
                [normalized],
            )
            row = cur.fetchone()
            return dict(row) if row else {}
        else:
            with db.get_connection() as c:
                cur = c.cursor()
                cur.execute(
                    "SELECT startup_risk, company_maturity, company_intelligence "
                    "FROM careerloop.company_memory WHERE company_normalized = %s",
                    [normalized],
                )
                row = cur.fetchone()
                return dict(row) if row else {}
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "company_memory_lookup failed for '%s': %s — using defaults", company_name, e
        )
        return {}


def _company_registry_lookup(company_name: str, conn=None) -> dict:
    """Pull employee_estimate + sector + ats_provider from companies registry."""
    if not company_name:
        return {}
    try:
        from careerloop.memory.connection import get_db_manager
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "company_registry import failed for '%s': %s — using defaults", company_name, e
        )
        return {}
    try:
        db = get_db_manager()
        normalized = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")

        if conn is not None:
            cur = conn.cursor()
            cur.execute(
                "SELECT employee_estimate, sector, ats_provider, last_job_count "
                "FROM careerloop.companies WHERE id = %s OR LOWER(name) = LOWER(%s)",
                [normalized, company_name],
            )
            row = cur.fetchone()
            return dict(row) if row else {}
        else:
            with db.get_connection() as c:
                cur = c.cursor()
                cur.execute(
                    "SELECT employee_estimate, sector, ats_provider, last_job_count "
                    "FROM careerloop.companies WHERE id = %s OR LOWER(name) = LOWER(%s)",
                    [normalized, company_name],
                )
                row = cur.fetchone()
                return dict(row) if row else {}
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "company_registry_lookup failed for '%s': %s — using defaults", company_name, e
        )
        return {}


# ── Salary parsing ───────────────────────────────────────────────────────

_SALARY_PATTERNS = [
    # ₹35L - ₹60L  /  35-60 LPA  /  35L to 60L
    re.compile(r"(?:₹|rs\.?|inr)?\s*([\d.]+)\s*(?:l|lpa|lakhs?|lac)\s*(?:-|to|–)\s*(?:₹|rs\.?|inr)?\s*([\d.]+)\s*(?:l|lpa|lakhs?|lac)", re.IGNORECASE),
    re.compile(r"([\d.]+)\s*(?:l|lpa|lakhs?|lac)", re.IGNORECASE),
    re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]+)", re.IGNORECASE),
]


def _parse_salary_lakhs(text: str) -> tuple[Optional[float], Optional[float]]:
    """Extract (min_lakhs, max_lakhs) from arbitrary salary text. Either may be None."""
    if not text:
        return None, None
    t = text.lower().replace(",", "")

    def _to_float(s: str) -> Optional[float]:
        try:
            v = float(s)
            return v if v > 0 else None
        except (ValueError, TypeError):
            return None

    # Range pattern first
    m = _SALARY_PATTERNS[0].search(t)
    if m:
        lo, hi = _to_float(m.group(1)), _to_float(m.group(2))
        if lo is not None and hi is not None:
            return lo, hi
    # Single-number lakhs
    m = _SALARY_PATTERNS[1].search(t)
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return v, v
    # Raw INR
    m = _SALARY_PATTERNS[2].search(t)
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return v / 100000, v / 100000
    return None, None


# ── Engine ───────────────────────────────────────────────────────────────

class IndiaFitEngine:
    """Dynamic, intent-based job scoring. 15 dims, total 100. No AI bias."""

    def __init__(self, profile: "ProfileManager"):
        self.p = profile
        self._company_memory_cache = {}
        self._company_registry_cache = {}

    # ── Public API ────────────────────────────────────────────────────

    def score_job(self, job: dict, conn=None) -> tuple[float, dict]:
        """Score a single job. Returns (total_score, breakdown).
        job dict must have: title, company, location.
        Optional: role_summary, responsibilities, requirements, benefits,
                  salary_text, work_mode, posted_date."""
        rejection = self._reject_if_not_job(job)
        if rejection:
            return 0.0, {"rejected": rejection}

        # Precompute shared signals
        jd_text = _jd_text(job)
        jd_tokens = _tokens(jd_text)
        
        company = job.get("company", "")
        if company not in self._company_memory_cache:
            self._company_memory_cache[company] = _company_memory_lookup(company, conn=conn)
        memory = self._company_memory_cache[company]
        
        if company not in self._company_registry_cache:
            self._company_registry_cache[company] = _company_registry_lookup(company, conn=conn)
        registry = self._company_registry_cache[company]

        ctx = {
            "jd_text": jd_text,
            "jd_tokens": jd_tokens,
            "company_memory": memory,
            "company_registry": registry,
        }

        dims = [
            ("role_fit", self._score_role_fit),
            ("archetype_fit", self._score_archetype_fit),
            ("skill_fit", self._score_skill_fit),
            ("salary_fit", self._score_salary_fit),
            ("equity_fit", self._score_equity_fit),
            ("benefits_fit", self._score_benefits_fit),
            ("location_fit", self._score_location_fit),
            ("work_mode_fit", self._score_work_mode_fit),
            ("notice_period_fit", self._score_notice_period_fit),
            ("sector_fit", self._score_sector_fit),
            ("company_stability", self._score_company_stability),
            ("startup_risk", self._score_startup_risk),
            ("brand_value", self._score_brand_value),
            ("commute_risk", self._score_commute_risk),
            ("response_likelihood", self._score_response_likelihood),
            ("career_trajectory", self._score_career_trajectory),
        ]

        breakdown = {}
        total = 0.0
        role_fit_raw = 0.0
        for name, scorer in dims:
            raw = scorer(job, ctx)
            weight = FIT_WEIGHTS.get(name, 0)
            weighted = (raw / 10.0) * weight
            breakdown[name] = {"raw": raw, "weight": weight, "weighted": round(weighted, 1)}
            total += weighted
            if name == "role_fit":
                role_fit_raw = raw

        # Hard gate: role identity mismatch → cap score at 30
        if role_fit_raw < self.p.role_fit_gate:
            return min(round(total, 1), 30.0), breakdown

        return round(total, 1), breakdown

    def score_jobs_batch(self, jobs: list) -> list:
        scored = []
        for job in jobs:
            score, breakdown = self.score_job(job)
            scored.append({"job": job, "score": score, "breakdown": breakdown})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    # ── Pre-filter ────────────────────────────────────────────────────

    def _reject_if_not_job(self, job: dict) -> Optional[str]:
        """Reject category/search/blog URLs upfront."""
        url = (job.get("source_url") or job.get("url") or "").lower()
        title = (job.get("title") or "").lower()
        full = url + " " + title

        search_patterns = [
            (r'naukri\.com/[a-z\-]+-jobs-in-', "Naukri search results page"),
            (r'/jobs/[a-z\-]+-jobs-', "LinkedIn search results page"),
            (r'/jobs/[a-z\-]+-jobs$', "LinkedIn category page"),
            (r'/jobs/\d+-[a-z]', None),
            (r'cutshort\.io/jobs/', "Cutshort category page"),
            (r'foundit\.in/search/', "Foundit search page"),
            (r'foundit\.in/job/[a-z\-]+-\d{5,}', None),
            (r'instahyre\.com/[a-z\-]+-jobs-in-', "Instahyre category page"),
            (r'hirist\.tech/[ck]/', "Hirist category page"),
            (r'/blog/', "Blog post, not a job"),
            (r'/career-advice/', "Career advice article"),
            (r'/code360/library/', "Naukri learning article"),
            (r'how-to-become', "Career guide, not a job"),
            (r'highest-paying', "Salary article, not a job"),
            (r'best-career-options', "Career advice article"),
            (r'career-prospects', "Career advice article"),
            (r'interview-questions', "Interview prep article"),
        ]
        for pattern, reason in search_patterns:
            if re.search(pattern, full):
                if reason is None:
                    return None
                return reason

        for pattern, reason in [
            (r'^\d+\+?\s*[a-z\s]+jobs?\s*(in|vacanc)', "Job count listing page"),
            (r'^\d+\s*[a-z\s]+job\s*(vacanc|open)', "Job count listing page"),
        ]:
            if re.search(pattern, title):
                return reason
        return None

    # ── Dimension scorers (each returns 0-10) ─────────────────────────

    def _score_role_fit(self, job: dict, ctx: dict) -> float:
        """Token-overlap of user's target functions/roles vs job title + role_summary.
        Uses BOTH target_functions (horizontal) and target_roles (vertical) — whichever overlaps more."""
        title = (job.get("title") or "").lower()
        role_summary = (job.get("role_summary") or "").lower()
        haystack = _tokens(title + " " + role_summary)

        needles_fn = self.p.target_functions or []
        needles_roles = self.p.target_roles or []
        archetypes = [a.get("name", "") for a in self.p.archetypes if a.get("name")]

        scores = []
        if needles_fn:
            scores.append(_overlap_ratio(needles_fn, haystack) * 10.0)
        if needles_roles:
            scores.append(_overlap_ratio(needles_roles, haystack) * 10.0)
        if archetypes:
            scores.append(_overlap_ratio(archetypes, haystack) * 9.0)

        if not scores:
            return 5.0  # no intent set → neutral
        score = max(scores)

        # Seniority alignment: if user title contains a seniority signal that matches JD's, boost
        seniority_signals = ["junior", "senior", "staff", "principal", "lead", "head", "director", "founding"]
        user_seniority = [s for s in seniority_signals if any(s in r.lower() for r in needles_roles)]
        if user_seniority and any(s in title for s in user_seniority):
            score = min(score + 1.0, 10.0)

        # Rejected roles → penalty
        for rejected in self.p.rejected_roles:
            if rejected.lower() in title:
                score = max(score - 5.0, 0.0)

        return round(score, 1)

    def _score_archetype_fit(self, job: dict, ctx: dict) -> float:
        """Use pre-computed ontology archetype_match from _tag_jobs_with_ontology.
        Falls back to 5.0 if ontology tag not present."""
        ontology = job.get("_ontology")
        if not ontology:
            return 5.0
        match = ontology.get("archetype_match", 0.5)
        # Scale 0-1 → 0-10; preferred_company_match gives +1 bonus
        score = match * 10.0
        if ontology.get("preferred_company_match"):
            score = min(score + 1.0, 10.0)
        return round(score, 1)

    def _score_skill_fit(self, job: dict, ctx: dict) -> float:
        """Confirmed-skill token overlap against requirements + responsibilities text."""
        confirmed = self.p.confirmed_skills or []
        weak = self.p.weak_skills or []

        if not confirmed:
            return 5.0

        # Prefer structured fields when available
        haystack_text = (
            (job.get("requirements") or "") + " " +
            (job.get("responsibilities") or "") + " " +
            (job.get("role_summary") or "")
        )
        # Fall back to raw description if structured sections are empty
        if len(haystack_text.strip()) < 100:
            haystack_text = job.get("description") or job.get("raw_jd_text") or ""

        if not haystack_text.strip():
            return 5.0  # no JD content to match

        haystack = _tokens(haystack_text)
        confirmed_hit = _overlap_ratio(confirmed, haystack)
        weak_hit = _overlap_ratio(weak, haystack) if weak else 0.0

        # Base: confirmed skills should appear; weak skills appearing reduces fit
        score = confirmed_hit * 8.0 + 2.0
        score -= weak_hit * 1.5
        return round(max(0.0, min(10.0, score)), 1)

    def _score_salary_fit(self, job: dict, ctx: dict) -> float:
        """Compare extracted salary band to user's [floor, ceiling]. Both ends matter."""
        floor = self.p.salary_floor_lakhs
        ceiling = self.p.salary_ceiling_lakhs

        if floor is None and ceiling is None:
            return 5.0

        salary_text = (
            (job.get("salary_text") or "") + " " +
            (job.get("salary") or "") + " " +
            (job.get("benefits") or "")
        )
        job_min, job_max = _parse_salary_lakhs(salary_text)
        if job_min is None:
            return 5.0  # unknown → neutral

        if floor is None:
            floor = max(0.0, (ceiling or job_min) * 0.6)
        if ceiling is None:
            ceiling = floor * 2.0

        # Score based on how the job's max overlaps the user's [floor, ceiling]
        if job_max < floor:
            return round(max(0.0, (job_max / floor) * 4.0), 1)
        if job_min >= ceiling:
            # Above ceiling = still good (8-10 depending on how far above)
            return round(min(10.0, 8.0 + (job_min / ceiling - 1.0) * 2.0), 1)
        # Job band overlaps user band → great
        return 10.0

    def _score_equity_fit(self, job: dict, ctx: dict) -> float:
        """ESOPs match. If user doesn't care → neutral 10. If user requires equity, check JD."""
        if not self.p.equity_required:
            return 10.0
        text = ctx["jd_text"].lower()
        equity_signals = ["esop", "equity", "stock option", "rsu", "share grant", "ownership"]
        has_signal = any(s in text for s in equity_signals)
        if not has_signal:
            return 2.0  # user wants equity, JD doesn't mention → likely no
        # Check percentage mention if user has a minimum
        min_pct = self.p.esops_min_percent
        if min_pct is not None:
            # Match "X% equity" OR "equity ... X%" within a small window
            m = re.search(r"([\d.]+)\s*%\s*(?:esops?|equity|stock)", text) \
                or re.search(r"(?:esops?|equity|stock)[^.\n]{0,40}?([\d.]+)\s*%", text)
            if m:
                pct = float(m.group(1))
                if pct >= min_pct:
                    return 10.0
                return round(max(2.0, (pct / min_pct) * 10.0), 1)
        return 8.0  # equity mentioned but no specific %

    def _score_benefits_fit(self, job: dict, ctx: dict) -> float:
        """Check that user's must-have benefits appear in JD benefits/description."""
        must = self.p.benefits_must_have
        if not must:
            return 10.0
        text = ((job.get("benefits") or "") + " " + ctx["jd_text"]).lower()
        hits = sum(1 for b in must if b.lower() in text)
        return round(min(10.0, (hits / len(must)) * 10.0), 1)

    def _score_location_fit(self, job: dict, ctx: dict) -> float:
        """Same logic as before — city aliases + tier matching + relocation."""
        job_loc = (job.get("location") or "").lower()
        user_city = self.p.location_city.lower()

        if not job_loc:
            return 5.0
        if user_city and user_city in job_loc:
            return 10.0

        for city, info in INDIAN_TECH_CITIES.items():
            if city == user_city or user_city in info["aliases"]:
                if any(alias in job_loc for alias in [city] + info["aliases"]):
                    return 10.0

        if "remote" in job_loc:
            return 9.0

        user_tier = None
        for city, info in INDIAN_TECH_CITIES.items():
            if city == user_city or user_city in info["aliases"]:
                user_tier = info["tier"]
                break

        if user_tier:
            for city, info in INDIAN_TECH_CITIES.items():
                if city in job_loc or any(a in job_loc for a in info["aliases"]):
                    return 7.0 if info["tier"] == user_tier else 4.0

        if "india" in job_loc:
            return 6.0
        if self.p.extended.get("willing_to_relocate"):
            return 5.0
        return 2.0

    def _score_work_mode_fit(self, job: dict, ctx: dict) -> float:
        mode = (job.get("work_mode") or job.get("location") or "").lower()
        loc_flex = self.p.base.get("compensation", {}).get("location_flexibility", "").lower()
        prefers_remote = "remote" in loc_flex

        if "remote" in mode or "work from home" in mode or "wfh" in mode:
            return 10.0 if prefers_remote else 8.0
        if "hybrid" in mode:
            return 8.0 if prefers_remote else 10.0
        if "onsite" in mode or "on-site" in mode or "in-office" in mode:
            return 4.0 if prefers_remote else 7.0
        return 5.0

    def _score_notice_period_fit(self, job: dict, ctx: dict) -> float:
        text = ctx["jd_text"].lower()
        user_notice = self.p.notice_period_days

        notice_patterns = [
            (r"notice period[:\s]*(\d+)\s*(?:days|d)", 1),
            (r"immediate(?:ly)?\s*(?:joining|joiner)", 0),
            (r"(\d+)\s*(?:days|d)\s*notice", 1),
            (r"can join(?: in)?\s*(\d+)\s*(?:days|d)", 1),
        ]
        for pattern, group in notice_patterns:
            match = re.search(pattern, text)
            if match:
                required_days = 0 if group == 0 else int(match.group(group))
                if user_notice <= required_days:
                    return 10.0
                if user_notice <= required_days * 1.5:
                    return 7.0
                if user_notice <= required_days * 2:
                    return 4.0
                return 2.0
        return 7.0

    def _score_sector_fit(self, job: dict, ctx: dict) -> float:
        """User's sector allow/deny preference vs company's known sector."""
        prefs = self.p.sector_preferences
        rejections = self.p.sector_rejections
        if not prefs and not rejections:
            return 10.0  # no preference set

        company_sector = (ctx["company_registry"].get("sector") or "").strip()
        if not company_sector:
            return 6.0  # unknown sector — neither penalize hard nor reward

        sector_lower = company_sector.lower()
        if any(r.lower() in sector_lower for r in rejections):
            return 1.0
        if prefs and not any(p.lower() in sector_lower for p in prefs):
            return 4.0  # not in allowlist
        return 10.0

    def _score_company_stability(self, job: dict, ctx: dict) -> float:
        """Pull from company_memory.startup_risk (lower risk = higher stability)."""
        mem = ctx["company_memory"]
        if not mem:
            # Fall back to registry employee estimate
            emp = ctx["company_registry"].get("employee_estimate") or 0
            if emp >= 1000:
                return 8.0
            if emp >= 200:
                return 6.5
            if emp >= 50:
                return 5.5
            if emp > 0:
                return 4.5
            return COMPANY_STABILITY_DEFAULT
        # startup_risk in company_memory: 0-10 where higher = riskier
        risk = mem.get("startup_risk", 5.0) or 5.0
        return round(max(0.0, min(10.0, 10.0 - risk)), 1)

    def _score_startup_risk(self, job: dict, ctx: dict) -> float:
        """Inverse of stability, weighted by user's startup tolerance."""
        stability = self._score_company_stability(job, ctx)
        if stability >= 7.0:
            return 10.0  # established, low risk
        # Less stable → user's tolerance determines the score
        tolerance = self.p.startup_tolerance
        return round(min(10.0, stability + tolerance * 0.4), 1)

    def _score_brand_value(self, job: dict, ctx: dict) -> float:
        """Pull from company_memory.company_maturity or default."""
        mem = ctx["company_memory"]
        maturity = (mem.get("company_maturity") or "").lower() if mem else ""
        if "public" in maturity or "ipo" in maturity:
            return 9.0
        if "unicorn" in maturity or "late stage" in maturity:
            return 7.5
        if "growth" in maturity or "series c" in maturity or "series d" in maturity:
            return 6.5
        if "series a" in maturity or "series b" in maturity:
            return 5.5
        if "seed" in maturity or "early" in maturity:
            return 4.0
        # No memory → infer from employee estimate
        emp = ctx["company_registry"].get("employee_estimate") or 0
        if emp >= 5000:
            return 8.0
        if emp >= 1000:
            return 6.5
        if emp >= 200:
            return 5.0
        return BRAND_VALUE_DEFAULT

    def _score_commute_risk(self, job: dict, ctx: dict) -> float:
        job_loc = (job.get("location") or "").lower()
        user_city = self.p.location_city.lower()

        if not job_loc or "remote" in job_loc:
            return 10.0
        if user_city and user_city in job_loc:
            if user_city in ["bangalore", "bengaluru", "mumbai", "delhi"]:
                return 6.0
            if user_city in ["chennai", "hyderabad", "pune"]:
                return 7.0
            return 8.0
        if self.p.extended.get("willing_to_relocate"):
            relo = self.p.extended.get("relocation_cities", [])
            if any(c.lower() in job_loc for c in relo):
                return 8.0
            return 5.0
        return 2.0

    def _score_response_likelihood(self, job: dict, ctx: dict) -> float:
        """Estimate hiring velocity from ATS provider + posting recency + source quality."""
        base = 5.0
        source = (job.get("_source_type") or job.get("source") or "").lower()
        # Direct ATS/portal sources = verified live job, higher response rate
        if any(s in source for s in ["greenhouse", "lever", "ashby", "workday", "company_portal"]):
            base += 3.0
        elif any(s in source for s in ["scrapegraph", "naukri", "foundit", "instahyre", "cutshort"]):
            base += 1.5
        elif any(s in source for s in ["jobspy", "linkedin"]):
            base += 1.0
        # search/generic sources have lowest signal — snippet only, may be stale
        elif any(s in source for s in ["search", "generic_http", "glassdoor", "google_jobs"]):
            base += 0.0

        posted = job.get("posted_date") or job.get("posted_at") or job.get("source_date") or ""
        if posted:
            from datetime import datetime
            try:
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

        # Active companies in registry — recent hiring signal
        registry = ctx["company_registry"]
        if registry.get("last_job_count", 0) >= 5:
            base += 1.0

        return round(max(1.0, min(10.0, base)), 1)

    def _score_career_trajectory(self, job: dict, ctx: dict) -> float:
        """Seniority match + brand bump. No AI bias."""
        title = (job.get("title") or "").lower()
        base = 5.0

        seniority = ["senior", "staff", "principal", "lead", "head", "founding", "director"]
        for i, s in enumerate(seniority):
            if s in title:
                base += (i + 1) * 0.7
                break

        # Brand bump from memory
        brand = self._score_brand_value(job, ctx)
        if brand >= 8:
            base += 1.5
        elif brand >= 6:
            base += 0.5
        return round(max(1.0, min(10.0, base)), 1)
