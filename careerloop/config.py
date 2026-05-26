"""
CareerLoop — Shared configuration, constants, and status definitions.
"""

# ── Application Ledger Statuses ──────────────────────────────────────────

LEDGER_STATUSES = [
    "DISCOVERED",       # New job found by scanner
    "SHORTLISTED",      # Passed initial filter, queued for user
    "SENT_TO_USER",     # Shown to user in daily shortlist
    "SKIPPED",          # User rejected or system filtered out
    "MAYBE",            # User bookmarked for later
    "APPROVED",         # User wants to apply
    "RESUME_READY",     # Tailored resume generated
    "APPLIED",          # Application submitted
    "FOLLOW_UP_DUE",    # Time to follow up
    "INTERVIEW",        # In interview process
    "REJECTED",         # Rejected by company
    "OFFER",            # Offer received
    "ARCHIVED",         # No longer active (accepted another, closed, etc.)
]

# Statuses that mean "don't show this job again"
DORMANT_STATUSES = {"SKIPPED", "APPLIED", "REJECTED", "OFFER", "ARCHIVED"}

# Statuses that mean "this job is in active pipeline"
ACTIVE_STATUSES = {"DISCOVERED", "SHORTLISTED", "SENT_TO_USER", "MAYBE", "APPROVED", "RESUME_READY"}

# Statuses that need user action
ACTION_REQUIRED_STATUSES = {"SENT_TO_USER", "APPROVED", "FOLLOW_UP_DUE"}

# ── India Fit Engine Weights (total = 100) ─────────────────────────────
# Refactored 2026-05-18 — dynamic intent-based scoring, no AI bias.
# Dropped: interview_difficulty (hardcoded company list), assignment_burden (role bias).
# Added:   equity_fit, benefits_fit, sector_fit.

FIT_WEIGHTS = {
    "role_fit": 12,            # token overlap target_functions/roles vs title+role_summary
    "archetype_fit": 8,        # ontology archetype_match from _tag_jobs_with_ontology
    "skill_fit": 12,           # token overlap confirmed_skills vs requirements+responsibilities
    "salary_fit": 10,          # floor+ceiling band check on extracted comp
    "equity_fit": 4,           # ESOPs match
    "benefits_fit": 4,         # must-have benefits match
    "location_fit": 10,
    "work_mode_fit": 7,
    "notice_period_fit": 4,
    "sector_fit": 6,           # sector allow/deny preference
    "company_stability": 7,    # sourced from company_memory, not hardcoded
    "startup_risk": 4,
    "brand_value": 5,          # sourced from company_memory, not hardcoded
    "commute_risk": 3,
    "response_likelihood": 3,
    "career_trajectory": 1,    # seniority match
}

# ── Follow-up Schedule (days after application) ─────────────────────────

FOLLOW_UP_SCHEDULE = [5, 10, 17, 25]  # Days after APPLIED to trigger follow-up

# ── Company Signals — DEPRECATED ──────────────────────────────────────
# Old hardcoded tables removed 2026-05-18. Company stability and brand value
# now come from `company_memory` SQLite table (per-company, learned over time).
# These constants kept as neutral defaults only — never reference by company name.

COMPANY_STABILITY_DEFAULT = 5.0   # 0-10 neutral when no memory record exists
BRAND_VALUE_DEFAULT = 4.0         # 0-10 neutral when no memory record exists

# Back-compat shims — any old import that names these gets the default only.
COMPANY_STABILITY_SIGNALS = {"__default__": COMPANY_STABILITY_DEFAULT}
BRAND_VALUE_SIGNALS = {"__default__": BRAND_VALUE_DEFAULT}

# ── Indian Cities (for location matching) ──────────────────────────────

INDIAN_TECH_CITIES = {
    "bangalore": {"tier": 1, "aliases": ["bengaluru", "blr"]},
    "chennai": {"tier": 1, "aliases": ["madras"]},
    "hyderabad": {"tier": 1, "aliases": ["hyd", "secunderabad"]},
    "mumbai": {"tier": 1, "aliases": ["bombay", "navi mumbai"]},
    "pune": {"tier": 1, "aliases": []},
    "delhi": {"tier": 1, "aliases": ["new delhi", "delhi ncr", "ncr", "gurgaon", "gurugram", "noida"]},
    "kolkata": {"tier": 2, "aliases": ["calcutta"]},
    "ahmedabad": {"tier": 2, "aliases": ["gandhinagar"]},
    "kochi": {"tier": 2, "aliases": ["cochin"]},
    "coimbatore": {"tier": 2, "aliases": []},
    "jaipur": {"tier": 2, "aliases": []},
    "indore": {"tier": 2, "aliases": []},
    "chandigarh": {"tier": 2, "aliases": []},
    "bhubaneswar": {"tier": 2, "aliases": []},
    "visakhapatnam": {"tier": 2, "aliases": ["vizag"]},
}

# Work modes
WORK_MODES = ["remote", "hybrid", "onsite"]
