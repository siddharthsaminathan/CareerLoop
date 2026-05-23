"""
CareerLoop Monster Adapter — job search via Monster India (foundit.in) and Monster.com.

Monster India rebranded to foundit.in in 2022 but Monster.com still has India listings.
Primary: Monster.com public search API (JSON, no auth required).
Fallback: requests + BeautifulSoup HTML scrape of search results page.
"""

import logging
import re
import time
from typing import Optional
from urllib.parse import quote_plus

import requests

logger = logging.getLogger(__name__)

_MONSTER_SEARCH_URL = "https://www.monster.com/jobs/search"
_FOUNDIT_API_URL = "https://www.foundit.in/middleware/jobsearch/api/v2/search"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.foundit.in/",
}

_FOUNDIT_HEADERS = {
    **_HEADERS,
    "x-requested-with": "XMLHttpRequest",
}

# foundit.in location IDs for major Indian cities
_FOUNDIT_CITY_IDS = {
    "bangalore": "city~bangalore~11~3",
    "bengaluru": "city~bangalore~11~3",
    "chennai": "city~chennai~12~3",
    "mumbai": "city~mumbai~9~3",
    "delhi": "city~delhi~1~3",
    "ncr": "city~delhi~1~3",
    "hyderabad": "city~hyderabad~48~3",
    "pune": "city~pune~2~3",
    "kolkata": "city~kolkata~3~3",
}


def _clean_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", text).strip()


def _normalize_job(raw: dict, source_tag: str = "monster") -> dict:
    return {
        "title": raw.get("designation") or raw.get("title") or "",
        "company": raw.get("companyName") or raw.get("company") or "",
        "location": raw.get("locations") or raw.get("location") or "",
        "url": raw.get("jdURL") or raw.get("applyUrl") or raw.get("url") or "",
        "apply_url": raw.get("applyUrl") or raw.get("jdURL") or raw.get("url") or "",
        "description": _clean_html(raw.get("jobDescription") or raw.get("summary") or ""),
        "salary": raw.get("salary") or raw.get("salaryDetail") or "",
        "skills": raw.get("keySkills") or [],
        "experience": raw.get("experience") or "",
        "_source_type": source_tag,
    }


# ── Primary: foundit.in API ───────────────────────────────────────────────

def _search_foundit(role: str, city: str, max_results: int = 50) -> list[dict]:
    """
    foundit.in job search via DDG. The foundit.in API and SRP are bot-blocked.
    DDG site-scoped search reliably finds individual job listing URLs.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        logger.debug("[Monster/foundit] ddgs not installed")
        return []

    query = f'"{role}" {city} site:foundit.in'
    results = []
    seen = set()
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results, region="in-en"))
        for r in raw:
            url = r.get("href", "")
            if "foundit.in" not in url or url in seen:
                continue
            seen.add(url)
            title = r.get("title", "").split(" - ")[0].strip()
            snippet = r.get("body", "")
            company = ""
            m = re.search(r" - ([A-Za-z0-9 &.,]+) - foundit", r.get("title", ""), re.IGNORECASE)
            if m:
                company = m.group(1).strip()
            results.append({
                "title": title,
                "company": company,
                "location": city,
                "url": url,
                "apply_url": url,
                "description": snippet,
                "_source_type": "foundit",
            })
        logger.info(f"[Monster/foundit] DDG: {role} in {city}: {len(results)} jobs")
    except Exception as e:
        logger.debug(f"[Monster/foundit] DDG search failed: {e}")
    return results


# ── Fallback: Monster.com HTML scrape ────────────────────────────────────

def _search_monster_html(role: str, city: str, max_results: int = 30) -> list[dict]:
    """
    Scrape Monster.com search results page as fallback.
    Parses JSON-LD structured data embedded in the page.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.debug("[Monster] BeautifulSoup not installed — skipping HTML fallback")
        return []

    query = quote_plus(f"{role} {city}")
    url = f"{_MONSTER_SEARCH_URL}?q={query}&where=India"

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []

        # Try JSON-LD first (structured data)
        import json
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") != "JobPosting":
                        continue
                    results.append({
                        "title": item.get("title", ""),
                        "company": (item.get("hiringOrganization") or {}).get("name", ""),
                        "location": str((item.get("jobLocation") or {}).get("address") or ""),
                        "url": item.get("url") or item.get("identifier", {}).get("value", ""),
                        "apply_url": item.get("url", ""),
                        "description": _clean_html(item.get("description", ""))[:500],
                        "salary": "",
                        "skills": [],
                        "_source_type": "monster",
                    })
                    if len(results) >= max_results:
                        break
            except Exception:
                continue

        if results:
            logger.info(f"[Monster/html] {role} in {city}: {len(results)} jobs (JSON-LD)")
            return results

        # Fallback: card-based scraping
        cards = soup.select("[data-jobid], .job-search-card, .results-card")
        for card in cards[:max_results]:
            title_el = card.select_one("h2 a, .title a, [data-cy='card-title']")
            company_el = card.select_one(".company-name, [data-cy='company-name']")
            loc_el = card.select_one(".location, [data-cy='card-location']")
            link = title_el.get("href", "") if title_el else ""
            results.append({
                "title": title_el.get_text(strip=True) if title_el else "",
                "company": company_el.get_text(strip=True) if company_el else "",
                "location": loc_el.get_text(strip=True) if loc_el else "",
                "url": link if link.startswith("http") else f"https://www.monster.com{link}",
                "apply_url": link,
                "description": "",
                "salary": "",
                "skills": [],
                "_source_type": "monster",
            })

        logger.info(f"[Monster/html] {role} in {city}: {len(results)} jobs (HTML cards)")
        return results

    except Exception as e:
        logger.debug(f"[Monster/html] failed: {e}")
        return []


# ── Public API ────────────────────────────────────────────────────────────

def search_monster(role: str, city: str, max_results: int = 50) -> list[dict]:
    """
    Search Monster/foundit for jobs. Primary: foundit.in API. Fallback: monster.com HTML.
    Returns normalized job dicts with _source_type='foundit' or 'monster'.
    """
    results = _search_foundit(role, city, max_results)
    if not results:
        time.sleep(0.5)
        results = _search_monster_html(role, city, max_results)
    return results
