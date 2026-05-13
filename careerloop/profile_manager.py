"""
CareerLoop Profile Manager — Extended user profiles with India-specific fields.

Extends career-ops config/profile.yml with fields needed for India Fit Engine:
- Notice period, CTC expectations, commute constraints
- Startup tolerance, assignment burden tolerance
- Confirmed skills (strengths) vs weak skills (gaps)
- Company preferences (names, sizes, types)
"""

import os
import sys
import yaml

# ── Default India-specific profile fields ─────────────────────────────

DEFAULT_INDIA_PROFILE = {
    "notice_period_days": 30,
    "current_ctc_lakhs": None,
    "expected_ctc_lakhs": None,
    "ctc_currency": "INR",
    "salary_floor_lakhs": None,
    "startup_tolerance": 7,          # 0-10, 10 = very startup-friendly
    "min_company_size": None,        # None = no preference
    "max_company_size": None,
    "preferred_company_types": [],   # ["mnc", "startup", "saas", "fintech", etc.]
    "rejected_company_types": [],    # ["consulting", "body-shop"]
    "max_commute_minutes": 60,
    "willing_to_relocate": False,
    "relocation_cities": [],
    "assignment_burden_tolerance": 5, # 0-10, 10 = willing to do heavy assignments
    "confirmed_skills": [],
    "weak_skills": [],
    "rejected_roles": [],
    "adjacent_roles": [],
    "preferred_sources": [],          # ["linkedin", "naukri", "referral", etc.]
    "resume_tone": "confident",       # confident | humble | technical | balanced
    "interview_weaknesses": [],
    "rejection_learnings": [],
}


class ProfileManager:
    """
    Manages extended user profile combining:
    1. career-ops config/profile.yml (base)
    2. CareerLoop India-specific fields (extended)
    """

    def __init__(self, career_ops_root: str):
        self.root = career_ops_root
        self.profile_path = os.path.join(career_ops_root, "config", "profile.yml")
        self.extended_path = os.path.join(career_ops_root, "careerloop", "profile_extended.yml")

        # Load base profile
        with open(self.profile_path) as f:
            self.base = yaml.safe_load(f)

        # Load or init extended profile
        if os.path.exists(self.extended_path):
            with open(self.extended_path) as f:
                self.extended = yaml.safe_load(f)
        else:
            self.extended = DEFAULT_INDIA_PROFILE.copy()
            self._save()

    def _save(self):
        with open(self.extended_path, "w") as f:
            yaml.dump(self.extended, f, default_flow_style=False, allow_unicode=True)

    # ── Convenience accessors ────────────────────────────────────────

    @property
    def full_name(self):
        return self.base.get("candidate", {}).get("full_name", "")

    @property
    def notice_period_days(self):
        return self.extended.get("notice_period_days", 30)

    @property
    def salary_floor_lakhs(self):
        return self.extended.get("salary_floor_lakhs") or self._parse_min_comp()

    def _parse_min_comp(self):
        """Extract minimum from profile.yml comp string like '₹35L-60L'"""
        comp = self.base.get("compensation", {})
        minimum = comp.get("minimum", "")
        if not minimum:
            return None
        import re
        match = re.search(r'[\d.]+', str(minimum).replace("₹", "").replace("L", ""))
        return float(match.group()) if match else None

    @property
    def target_roles(self):
        return self.base.get("target_roles", {}).get("primary", [])

    @property
    def archetypes(self):
        return self.base.get("target_roles", {}).get("archetypes", [])

    @property
    def location_city(self):
        return self.base.get("location", {}).get("city", "")

    @property
    def confirmed_skills(self):
        return self.extended.get("confirmed_skills", [])

    @property
    def weak_skills(self):
        return self.extended.get("weak_skills", [])

    @property
    def startup_tolerance(self):
        return self.extended.get("startup_tolerance", 7)

    @property
    def assignment_burden_tolerance(self):
        return self.extended.get("assignment_burden_tolerance", 5)

    @property
    def rejected_company_types(self):
        return self.extended.get("rejected_company_types", [])

    @property
    def rejected_roles(self):
        return self.extended.get("rejected_roles", [])

    # ── Mutators ─────────────────────────────────────────────────────

    def update(self, field: str, value):
        """Update an extended profile field and save."""
        self.extended[field] = value
        self._save()

    def add_skill(self, skill: str, confirmed: bool = True):
        if confirmed:
            if skill not in self.extended["confirmed_skills"]:
                self.extended["confirmed_skills"].append(skill)
        else:
            if skill not in self.extended["weak_skills"]:
                self.extended["weak_skills"].append(skill)
        self._save()

    def add_interview_learning(self, learning: str):
        self.extended["interview_weaknesses"].append(learning)
        self._save()

    def add_rejection_learning(self, learning: str):
        self.extended["rejection_learnings"].append(learning)
        self._save()

    def get_full_profile(self) -> dict:
        """Merge base + extended into single profile dict."""
        return {
            **self.base.get("candidate", {}),
            **self.base.get("narrative", {}),
            **self.base.get("location", {}),
            "target_roles": self.target_roles,
            "archetypes": self.archetypes,
            **self.extended,
        }
