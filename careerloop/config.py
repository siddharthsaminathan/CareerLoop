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

FIT_WEIGHTS = {
    "role_fit": 15,
    "skill_fit": 15,
    "salary_fit": 10,
    "location_fit": 10,
    "work_mode_fit": 8,
    "notice_period_fit": 5,
    "company_stability": 7,
    "startup_risk": 5,          # lower is better (inverted)
    "brand_value": 6,
    "commute_risk": 4,          # lower is better (inverted)
    "assignment_burden": 3,     # lower is better (inverted)
    "interview_difficulty": 3,  # lower is better (inverted)
    "response_likelihood": 5,
    "career_trajectory": 4,
}

# ── Follow-up Schedule (days after application) ─────────────────────────

FOLLOW_UP_SCHEDULE = [5, 10, 17, 25]  # Days after APPLIED to trigger follow-up

# ── Company Stability Signals ──────────────────────────────────────────

# Companies with known stability signals (funding, layoffs, growth)
# Score: 0-10 where 10 = most stable
COMPANY_STABILITY_SIGNALS = {
    # MNC / public companies = highly stable
    "stripe": 9, "atlassian": 9, "gitlab": 8, "cloudflare": 8,
    "datadog": 8, "mongodb": 8, "twilio": 7, "snowflake": 8,
    "uber": 8, "shopify": 8, "coinbase": 6, "spotify": 8,
    "redhat": 9, "elastic": 8, "salesforce": 10, "microsoft": 10,
    "google": 10, "amazon": 8, "apple": 10, "meta": 8,
    # Indian MNC / public
    "flipkart": 8, "zomato": 7, "swiggy": 7, "nykaa": 7,
    "policybazaar": 7, "delhivery": 7, "paytm": 5,
    # Indian unicorns
    "razorpay": 8, "cred": 7, "phonepe": 8, "groww": 7,
    "meesho": 7, "zepto": 6, "freshworks": 8, "postman": 8,
    "browserstack": 8, "chargebee": 7, "hasura": 6,
    "ola": 5, "unacademy": 5, "vedantu": 5,
    # AI labs
    "anthropic": 8, "openai": 8, "cohere": 7, "mistral": 6,
    # Default for unknown companies
    "__default__": 5,
}

# ── Brand Value Signals (career resume value) ─────────────────────────

BRAND_VALUE_SIGNALS = {
    "anthropic": 10, "openai": 10, "google": 10, "apple": 10,
    "stripe": 9, "atlassian": 9, "gitlab": 8, "cloudflare": 8,
    "datadog": 8, "mongodb": 8, "uber": 8, "shopify": 8,
    "vercel": 8, "supabase": 7, "langchain": 7,
    "razorpay": 7, "cred": 6, "phonepe": 7, "flipkart": 8,
    "zomato": 6, "swiggy": 6, "meesho": 6, "freshworks": 7,
    "postman": 7, "browserstack": 7, "zoho": 7,
    "__default__": 4,
}

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
