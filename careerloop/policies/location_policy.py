"""LocationPolicy — single source of truth for geographic filtering.

Used by DailyRunner, scan_service._execute_scan_more, and _build_from_cache.
No other location filtering logic may exist in the codebase.
"""
import logging

logger = logging.getLogger(__name__)

# Canonical India cities — used by all scan paths
INDIA_CITIES = {
    "bangalore", "bengaluru", "chennai", "mumbai", "delhi", "new delhi",
    "hyderabad", "pune", "gurgaon", "gurugram", "noida", "kolkata",
    "ahmedabad", "kochi", "cochin", "jaipur", "chandigarh", "indore",
    "lucknow", "nagpur", "bhubaneswar", "mysore", "mysuru", "coimbatore",
    "visakhapatnam", "vizag", "trivandrum", "thiruvananthapuram",
}

INDIA_STATES = {
    "karnataka", "tamil nadu", "maharashtra", "delhi", "telangana",
    "andhra pradesh", "uttar pradesh", "west bengal", "gujarat",
    "rajasthan", "kerala", "madhyapradesh", "punjab", "haryana",
    "bihar", "odisha", "assam",
}

INDIA_KEYWORDS = {"india", "bangalore", "bengaluru", "chennai", "mumbai", "delhi",
                   "hyderabad", "pune", "gurgaon", "noida", "kolkata"}

INDIA_WORK_MODES = {"remote", "hybrid", "onsite", "on-site"}


def is_india_location(location: str) -> tuple:
    """Returns (is_india: bool, reason: str).

    Rules (in priority order):
    1. Explicitly non-India countries -> False
    2. Contains India city/state/keyword -> True
    3. "Remote" or "hybrid" WITHOUT India mention -> False (ambiguous)
    4. "Remote India" or "India Remote" -> True
    5. Empty location -> False (can't verify, don't assume)
    """
    if not location or not str(location).strip():
        return False, "empty location — cannot verify"

    loc = str(location).lower().strip()

    # Explicitly non-India
    non_india = {"usa", "united states", "uk", "united kingdom", "germany", "deutschland",
                 "france", "canada", "australia", "singapore", "japan", "dubai", "uae",
                 "netherlands", "switzerland", "sweden", "ireland", "spain", "italy",
                 "berlin", "paris", "london", "new york", "san francisco", "dublin",
                 "amsterdam", "toronto", "sydney", "zurich"}

    for country in non_india:
        if country in loc:
            # Check if India is ALSO mentioned — e.g. "India / Berlin" should be True
            if any(kw in loc for kw in INDIA_KEYWORDS):
                return True, f"India keyword present alongside {country}"
            return False, f"non-India country: {country}"

    # India keywords
    for kw in INDIA_KEYWORDS:
        if kw in loc:
            return True, f"India keyword: {kw}"

    # Indian cities
    for city in INDIA_CITIES:
        if city in loc:
            return True, f"Indian city: {city}"

    # Indian states
    for state in INDIA_STATES:
        if state in loc:
            return True, f"Indian state: {state}"

    # "Remote" / "hybrid" without India confirmation
    is_work_mode_only = all(
        word in INDIA_WORK_MODES or len(word) <= 2
        for word in loc.replace(",", " ").split()
    )
    if is_work_mode_only:
        return False, f"work mode only ({loc}) — no India confirmation"

    # Unknown location — keep it (don't filter out potentially valid jobs)
    return True, f"unknown location, keeping: {loc}"


def filter_india_jobs(jobs: list) -> tuple:
    """Split jobs into (india_jobs, rejected_jobs) based on location.

    Same interface as daily_runner's filter_india_jobs.
    """
    india_jobs = []
    rejected = []
    for job in jobs:
        location = job.get("location", "") or job.get("location_raw", "") or ""
        is_india, reason = is_india_location(location)
        if is_india:
            india_jobs.append(job)
        else:
            rejected.append({**job, "_rejection_reason": reason, "_rejection_stage": "LOCATION"})
    return india_jobs, rejected
