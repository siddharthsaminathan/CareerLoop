"""
CareerLoop Glassdoor Adapter — job search via DuckDuckGo site:glassdoor.com queries.

JobSpy's Glassdoor integration is broken (400/API errors). This adapter uses DDG
to find glassdoor.com/job-listing URLs and returns normalized job dicts.
"""

import logging
import re
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Glassdoor individual job listing URL patterns
_JOB_URL_PATTERNS = [
    r"glassdoor\.com/job-listing/",
    r"glassdoor\.co\.in/job-listing/",
    r"glassdoor\.com/Jobs/",
    r"glassdoor\.co\.in/Jobs/",
]

_SEARCH_PAGE_PATTERNS = [
    r"glassdoor\.com/Jobs/?$",
    r"glassdoor\.com/Jobs/[a-z].*-SRCH",
    r"glassdoor\.com/Salaries/",
    r"glassdoor\.com/Reviews/",
    r"glassdoor\.com/Interview/",
    r"glassdoor\.com/Overview/",
    r"glassdoor\.com/Explore/",
    r"glassdoor\.com/about",
]


def _is_job_url(url: str) -> bool:
    for pat in _JOB_URL_PATTERNS:
        if re.search(pat, url, re.IGNORECASE):
            return True
    return False


def _is_search_page(url: str) -> bool:
    for pat in _SEARCH_PAGE_PATTERNS:
        if re.search(pat, url, re.IGNORECASE):
            return True
    return False


def _parse_title_company(title: str, snippet: str) -> tuple[str, str]:
    """
    Glassdoor DDG titles often look like: "Job Title - Company - City | Glassdoor"
    Try to extract job title and company from the title string.
    """
    # Strip Glassdoor suffix
    title = re.sub(r"\s*[\|\-]\s*Glassdoor.*$", "", title, flags=re.IGNORECASE).strip()
    # Try "Job Title - Company - City" split
    parts = [p.strip() for p in title.split(" - ")]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return title, ""


def _extract_location(snippet: str, city: str) -> str:
    """Best-effort location from snippet text."""
    # Look for city name in snippet
    if city and city.lower() in snippet.lower():
        return city
    # Try to find "City, State" or "City, India"
    m = re.search(r"([A-Z][a-z]+(?: [A-Z][a-z]+)?,\s*(?:India|[A-Z]{2}))", snippet)
    if m:
        return m.group(1)
    return ""


def _ddg_search(query: str, max_results: int) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results, region="in-en"))
    except Exception as e:
        logger.debug(f"[Glassdoor] DDG query failed: {e}")
        return []


def search_glassdoor(role: str, city: str, max_results: int = 30) -> list[dict]:
    """
    Search Glassdoor for jobs using DuckDuckGo site: queries.

    Returns normalized job dicts with _source_type='glassdoor'.
    Keys: title, company, location, url, apply_url, description, _source_type.
    """
    queries = [
        f'site:glassdoor.com/job-listing {role} {city} India',
        f'site:glassdoor.com "job-listing" "{role}" {city}',
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
            if _is_search_page(url):
                continue
            if not _is_job_url(url):
                # Accept glassdoor.com URLs that contain job-like paths
                parsed = urlparse(url)
                if "glassdoor" not in parsed.netloc:
                    continue
                # Keep borderline URLs — may be job detail pages with different URL format
            seen_urls.add(url)
            title_str = r.get("title", "")
            snippet = r.get("body", "") or r.get("snippet", "")
            job_title, company = _parse_title_company(title_str, snippet)
            location = _extract_location(snippet, city)
            jobs.append({
                "title": job_title,
                "company": company,
                "location": location,
                "url": url,
                "apply_url": url,
                "description": snippet,
                "_source_type": "glassdoor",
            })
            if len(jobs) >= max_results:
                break
        time.sleep(0.3)

    logger.info(f"[Glassdoor] {role} in {city}: {len(jobs)} jobs")
    return jobs
