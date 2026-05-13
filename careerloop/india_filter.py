"""
CareerLoop India Filter — Hard filter for India-only jobs.

Reject: US, UK, Europe, Canada, global remote without India mention.
Accept: Indian cities, remote India, hybrid India.
"""

import re
import logging

logger = logging.getLogger(__name__)

INDIA_CITIES = {
    "bangalore", "bengaluru", "blr",
    "chennai", "madras",
    "hyderabad", "hyd", "secunderabad",
    "mumbai", "bombay", "navi mumbai",
    "pune",
    "delhi", "new delhi", "ncr", "gurugram", "gurgaon", "noida", "ghaziabad", "faridabad",
    "kochi", "cochin",
    "coimbatore",
    "kolkata", "calcutta",
    "ahmedabad", "gandhinagar",
    "jaipur",
    "indore",
    "chandigarh",
    "bhubaneswar",
    "visakhapatnam", "vizag",
    "trivandrum", "thiruvananthapuram",
    "mysore", "mysuru",
    "nagpur",
    "lucknow",
    "patna",
}

NON_INDIA_SIGNALS = {
    "united states", "usa", "u.s.", "new york", "san francisco",
    "seattle", "austin", "boston", "chicago", "los angeles", "denver",
    "silicon valley", "bay area", "mountain view", "palo alto", "menlo park",
    "united kingdom", "london", "manchester", "edinburgh",
    "canada", "toronto", "vancouver", "montreal",
    "germany", "berlin", "munich", "frankfurt",
    "france", "paris",
    "netherlands", "amsterdam",
    "singapore",
    "australia", "sydney", "melbourne",
    "japan", "tokyo",
    "dublin", "ireland",
    "tel aviv", "israel",
    "zurich", "switzerland",
}


def is_india_job(location: str, description: str = "", url: str = "") -> tuple[bool, str]:
    """
    Check if a job is in India.
    
    Returns: (is_india, reason)
    """
    # Check URL for India-specific boards FIRST (even if location/description empty)
    url_lower = (url or "").lower()
    if "naukri.com" in url_lower or "instahyre.com" in url_lower:
        return True, "India-specific job board URL"
    if "cutshort.io" in url_lower or "hirist.tech" in url_lower:
        return True, "India-specific job board URL"
    if "iimjobs.com" in url_lower or "foundit.in" in url_lower:
        return True, "India-specific job board URL"

    if not location and not description:
        return False, "no location info"

    loc_lower = (location or "").lower().strip()
    desc_lower = (description or "").lower()[:500]
    combined = f"{loc_lower} {desc_lower}"

    # Direct India city match
    for city in INDIA_CITIES:
        if city in loc_lower:
            return True, f"location contains {city}"

    # "India" in location
    if "india" in loc_lower:
        return True, "location contains India"

    # Remote India patterns
    india_remote_patterns = [
        r"remote.*india",
        r"india.*remote",
        r"work from home.*india",
        r"wfh.*india",
        r"india.*wfh",
    ]
    for pattern in india_remote_patterns:
        if re.search(pattern, combined):
            return True, f"matches remote India pattern"

    # (URL-based India board check is at the top of this function)

    # Non-India rejection
    for signal in NON_INDIA_SIGNALS:
        if signal in loc_lower:
            return False, f"non-India location: {signal}"

    # Global remote without India mention
    if "remote" in loc_lower and "india" not in combined:
        return False, "global remote without India mention"

    # Check description for India city mentions
    for city in INDIA_CITIES:
        if city in desc_lower:
            return True, f"description mentions {city}"

    # Check for Indian state codes and ", IN" suffix (common in JobSpy results)
    india_state_codes = {
        "tn", "ka", "mh", "ap", "ts", "kl", "dl", "hr", "up", "wb",
        "rj", "gj", "mp", "pb", "or", "br", "jh", "ct", "ga",
        "tamil nadu", "karnataka", "maharashtra", "andhra pradesh",
        "telangana", "kerala", "haryana", "uttar pradesh", "west bengal",
        "rajasthan", "gujarat", "madhya pradesh", "punjab", "odisha",
    }
    loc_parts = [p.strip() for p in loc_lower.split(",")]
    if loc_parts:
        last = loc_parts[-1].strip()
        if last in ("in", "india", "ind"):
            return True, f"location ends with India country code"
        if any(part in india_state_codes for part in loc_parts):
            return True, f"location contains Indian state code"

    # Unknown location — reject conservatively
    if loc_lower and loc_lower not in ("", "unknown", "not specified"):
        return False, f"unknown location: {location}"

    return False, "no India signals found"


def filter_india_jobs(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Filter a list of jobs to India-only.
    
    Returns: (india_jobs, rejected_jobs)
    Each rejected job gets a 'rejection_reason' field.
    """
    india = []
    rejected = []

    for job in jobs:
        location = job.get("location", "")
        description = job.get("description", job.get("raw_description", ""))
        url = job.get("url", job.get("source_url", ""))

        passed, reason = is_india_job(location, description, url)

        if passed:
            job["_india_filter"] = reason
            india.append(job)
        else:
            job["_rejection_reason"] = reason
            rejected.append(job)

    logger.info(f"India filter: {len(india)} passed, {len(rejected)} rejected")
    return india, rejected
