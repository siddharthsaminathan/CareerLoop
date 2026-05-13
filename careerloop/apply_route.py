"""
CareerLoop Apply Route Resolver — Best apply URL for each job.

Priority:
1. Company/ATS apply URL (direct)
2. Naukri / Instahyre
3. LinkedIn
4. Manual

Also handles cross-source merge when same job appears on multiple sites.
"""

import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Priority order for apply routes (lower = better)
APPLY_PRIORITY = {
    "company_site": 1,
    "greenhouse": 2,
    "lever": 2,
    "ashby": 2,
    "workday": 2,
    "naukri": 3,
    "instahyre": 3,
    "cutshort": 4,
    "foundit": 4,
    "linkedin": 5,
    "indeed": 6,
    "glassdoor": 7,
    "wellfound": 5,
    "manual": 8,
    "unknown": 9,
}

# Risk levels by apply route
ROUTE_RISK = {
    "company_site": "low",
    "greenhouse": "low",
    "lever": "low",
    "ashby": "low",
    "naukri": "low",
    "instahyre": "low",
    "linkedin": "medium",
    "indeed": "medium",
    "wellfound": "medium",
    "manual": "high",
    "unknown": "high",
}


def detect_apply_source(url: str) -> str:
    """Detect the source type from a URL."""
    if not url:
        return "unknown"
    url_lower = url.lower()
    patterns = {
        "greenhouse": ["greenhouse.io", "boards.greenhouse"],
        "lever": ["lever.co", "jobs.lever"],
        "ashby": ["ashbyhq.com"],
        "workday": ["workday.com", "myworkday.com"],
        "naukri": ["naukri.com"],
        "instahyre": ["instahyre.com"],
        "cutshort": ["cutshort.io"],
        "foundit": ["foundit.in"],
        "linkedin": ["linkedin.com"],
        "indeed": ["indeed.com", "indeed.co.in"],
        "glassdoor": ["glassdoor.com", "glassdoor.co.in"],
        "wellfound": ["wellfound.com"],
    }
    for source, domains in patterns.items():
        if any(d in url_lower for d in domains):
            return source

    # Check for company career pages
    if any(seg in url_lower for seg in ["/careers/", "/jobs/", "/openings/"]):
        return "company_site"

    return "unknown"


def resolve_apply_route(job: dict) -> dict:
    """
    Compute the best apply route for a job.

    Returns:
    {
        "best_apply_route": "company_site|naukri|linkedin|...",
        "apply_url": "...",
        "backup_urls": [],
        "reason": "...",
        "risk": "low|medium|high"
    }
    """
    urls = []

    # Collect all known URLs
    for key in ["url", "source_url", "application_url", "apply_url"]:
        val = job.get(key, "")
        if val and val not in urls:
            urls.append(val)

    # Alternate sources
    for alt in job.get("alternate_sources", []):
        if alt and alt not in urls:
            urls.append(alt)

    if not urls:
        return {
            "best_apply_route": "manual",
            "apply_url": "",
            "backup_urls": [],
            "reason": "no URLs found",
            "risk": "high",
        }

    # Score each URL by source priority
    scored = []
    for url in urls:
        source = detect_apply_source(url)
        priority = APPLY_PRIORITY.get(source, 9)
        scored.append({"url": url, "source": source, "priority": priority})

    scored.sort(key=lambda x: x["priority"])
    best = scored[0]
    backups = [s["url"] for s in scored[1:]]

    return {
        "best_apply_route": best["source"],
        "apply_url": best["url"],
        "backup_urls": backups,
        "reason": f"best route: {best['source']} (priority {best['priority']})",
        "risk": ROUTE_RISK.get(best["source"], "medium"),
    }


def merge_cross_source(jobs: list[dict]) -> list[dict]:
    """
    Merge jobs that appear on multiple sources.
    Uses normalized company + role + location as key.
    """
    from careerloop.models import normalize_company, normalize_role, normalize_location

    merged = {}

    for job in jobs:
        company = normalize_company(job.get("company", ""))
        role = normalize_role(job.get("title", job.get("role_title", "")))
        location = normalize_location(job.get("location", ""))
        key = f"{company}|{role}|{location}"

        if key in merged:
            existing = merged[key]
            # Add this URL as alternate source
            url = job.get("url", job.get("source_url", ""))
            if url:
                if "alternate_sources" not in existing:
                    existing["alternate_sources"] = []
                existing["alternate_sources"].append(url)

            # Merge descriptions (keep longer)
            new_desc = job.get("description", job.get("raw_description", ""))
            old_desc = existing.get("description", existing.get("raw_description", ""))
            if len(str(new_desc)) > len(str(old_desc)):
                existing["description"] = new_desc

            # Merge skills
            new_skills = job.get("skills", job.get("skills_required", []))
            old_skills = existing.get("skills", existing.get("skills_required", []))
            if isinstance(new_skills, list) and isinstance(old_skills, list):
                combined = list(set(old_skills + new_skills))
                existing["skills"] = combined

            existing["_merge_count"] = existing.get("_merge_count", 1) + 1
        else:
            job["_merge_key"] = key
            job["_merge_count"] = 1
            merged[key] = job

    result = list(merged.values())

    # Resolve apply routes for merged jobs
    for job in result:
        route = resolve_apply_route(job)
        job["apply_route"] = route

    logger.info(f"Cross-source merge: {len(jobs)} → {len(result)} unique jobs")
    return result
