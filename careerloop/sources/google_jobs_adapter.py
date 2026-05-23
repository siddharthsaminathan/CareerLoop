"""
CareerLoop Google Jobs Adapter — ATS job discovery via DuckDuckGo.

Google Jobs direct API is rate-limited (429). This adapter uses DDG to find
jobs indexed on ATS platforms (Lever, Greenhouse, Ashby) that Google crawls,
effectively replicating the "Google Jobs" corpus without hitting the API.
"""

import logging
import re
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ATS platforms that Google Jobs indexes and are publicly accessible
_ATS_SITES = [
    "jobs.lever.co",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "ashbyhq.com",
    "jobs.ashbyhq.com",
    "apply.workable.com",
]

# URL patterns that indicate an individual job posting (not a company root)
_ATS_JOB_PATTERNS = [
    r"jobs\.lever\.co/[^/]+/[a-f0-9\-]{36}",   # Lever: /company/uuid
    r"boards\.greenhouse\.io/[^/]+/jobs/\d+",    # Greenhouse: /company/jobs/12345
    r"job-boards\.greenhouse\.io/[^/]+/jobs/\d+",
    r"ashbyhq\.com/[^/]+/[a-f0-9\-]{36}",       # Ashby: /company/uuid
    r"jobs\.ashbyhq\.com/[^/]+/[a-f0-9\-]{36}",
    r"apply\.workable\.com/[^/]+/j/[A-Z0-9]+",  # Workable: /company/j/ID
]


def _is_ats_job_url(url: str) -> bool:
    for pat in _ATS_JOB_PATTERNS:
        if re.search(pat, url, re.IGNORECASE):
            return True
    return False


def _is_ats_root(url: str) -> bool:
    """Reject company root pages like jobs.lever.co/company (no job ID)."""
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]
    domain = parsed.netloc.lower()
    if domain in ("jobs.lever.co",) and len(path_parts) < 2:
        return True
    if domain in ("boards.greenhouse.io", "job-boards.greenhouse.io") and len(path_parts) < 3:
        return True
    if domain in ("ashbyhq.com", "jobs.ashbyhq.com") and len(path_parts) < 2:
        return True
    return False


def _parse_title_company_ats(title: str, url: str, snippet: str) -> tuple[str, str]:
    """
    ATS DDG titles are usually: "Job Title at Company | Lever/Greenhouse"
    """
    # Strip trailing | Source suffix
    title = re.sub(r"\s*\|\s*(Lever|Greenhouse|Ashby|Workable).*$", "", title, flags=re.IGNORECASE).strip()
    # "Job Title at Company" pattern
    m = re.match(r"^(.+?)\s+at\s+(.+)$", title, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # "Job Title - Company" pattern
    parts = [p.strip() for p in re.split(r"\s+[-–]\s+", title)]
    if len(parts) >= 2:
        return parts[0], parts[1]
    # Extract company from URL path
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]
    company = path_parts[0].replace("-", " ").title() if path_parts else ""
    return title, company


def _ddg_search(query: str, max_results: int) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results, region="in-en"))
    except Exception as e:
        logger.debug(f"[GoogleJobs] DDG query failed: {e}")
        return []


def search_google_jobs(role: str, city: str, max_results: int = 30) -> list[dict]:
    """
    Search ATS-indexed jobs (Lever/Greenhouse/Ashby) via DuckDuckGo.

    These are the same jobs that appear in Google Jobs search results — indexed
    from public ATS career pages. No rate limits or API keys required.

    Returns normalized job dicts with _source_type='google_jobs'.
    Keys: title, company, location, url, apply_url, description, _source_type.
    """
    queries = [
        f'{role} site:jobs.lever.co {city} India',
        f'{role} site:boards.greenhouse.io {city} India',
        f'{role} site:ashbyhq.com {city} India',
        f'{role} site:apply.workable.com {city} India',
    ]

    seen_urls: set[str] = set()
    jobs: list[dict] = []

    for query in queries:
        if len(jobs) >= max_results:
            break
        raw = _ddg_search(query, max_results=max(max_results, 20))
        for r in raw:
            url = r.get("href", "") or r.get("url", "")
            if not url or url in seen_urls:
                continue
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if not any(site in domain for site in _ATS_SITES):
                continue
            if _is_ats_root(url):
                continue
            seen_urls.add(url)
            title_str = r.get("title", "")
            snippet = r.get("body", "") or r.get("snippet", "")
            job_title, company = _parse_title_company_ats(title_str, url, snippet)
            jobs.append({
                "title": job_title,
                "company": company,
                "location": city,
                "url": url,
                "apply_url": url,
                "description": snippet,
                "_source_type": "google_jobs",
            })
            if len(jobs) >= max_results:
                break
        time.sleep(0.3)

    logger.info(f"[GoogleJobs] {role} in {city}: {len(jobs)} jobs")
    return jobs
