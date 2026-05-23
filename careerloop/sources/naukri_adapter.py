"""
CareerLoop Naukri Adapter — India job search via Naukri.com.

Primary: reverse-engineered JSON API (requests).
Fallback: Playwright-rendered HTML page (BeautifulSoup).
"""

import logging
import re
import time
from typing import Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

_API_URL = "https://www.naukri.com/jobapi/v3/search"
_API_HEADERS = {
    "appid": "109",
    "systemid": "Naukri",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.naukri.com/",
}

INDIA_CITIES = {
    "bangalore", "bengaluru", "blr", "chennai", "madras", "hyderabad", "hyd",
    "secunderabad", "mumbai", "bombay", "navi mumbai", "pune", "delhi",
    "new delhi", "ncr", "gurugram", "gurgaon", "noida", "ghaziabad",
    "faridabad", "kochi", "cochin", "coimbatore", "kolkata", "calcutta",
    "ahmedabad", "gandhinagar", "jaipur", "indore", "chandigarh",
    "bhubaneswar", "visakhapatnam", "vizag", "trivandrum",
    "thiruvananthapuram", "mysore", "mysuru", "nagpur", "lucknow", "patna",
    "surat", "vadodara", "rajkot", "agra", "nashik", "meerut",
}


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")


def _extract_location(placeholders: list[dict]) -> str:
    for p in placeholders or []:
        if p.get("label") == "location":
            return p.get("title", "")
    return ""


def _extract_experience(placeholders: list[dict]) -> str:
    for p in placeholders or []:
        if p.get("label") == "experience":
            return p.get("title", "")
    return ""


def _is_india_location(location: str) -> bool:
    if not location:
        return True  # Naukri is India-primary; no location = probably India
    loc = location.lower()
    if "india" in loc:
        return True
    if "remote" in loc:
        return True
    for city in INDIA_CITIES:
        if city in loc:
            return True
    return False


def _normalize_job(raw: dict) -> Optional[dict]:
    title = (raw.get("title") or "").strip()
    company = (raw.get("companyName") or "").strip()
    jd_url = (raw.get("jdURL") or "").strip()
    description = (raw.get("jobDescription") or "").strip()
    placeholders = raw.get("placeholders") or []

    location = _extract_location(placeholders)
    experience = _extract_experience(placeholders)

    if not title or not jd_url:
        return None

    if not _is_india_location(location):
        return None

    salary_info = raw.get("placeholders") or []
    salary = ""
    for p in salary_info:
        if p.get("label") in ("salary", "compensation"):
            salary = p.get("title", "")
            break

    return {
        "title": title,
        "company": company,
        "location": location,
        "url": jd_url,
        "apply_url": jd_url,
        "description": description,
        "salary": salary,
        "experience": experience,
        "_source_type": "naukri",
    }


def _search_via_api(role: str, city: str, max_results: int) -> list[dict]:
    try:
        import requests
    except ImportError:
        logger.warning("requests not installed; skipping Naukri API")
        return []

    results = []
    page_size = min(max_results, 20)
    pages_needed = (max_results + page_size - 1) // page_size

    session = requests.Session()
    session.headers.update(_API_HEADERS)

    for page in range(1, pages_needed + 1):
        if len(results) >= max_results:
            break

        params = {
            "noOfResults": page_size,
            "urlType": "search_by_keyword",
            "searchType": "adv",
            "keyword": role,
            "location": city,
            "k": role,
            "l": city,
            "pageNo": page,
        }

        try:
            resp = session.get(_API_URL, params=params, timeout=15)
            if resp.status_code == 429:
                logger.warning("Naukri API rate-limited (429)")
                return results
            if resp.status_code != 200:
                logger.warning("Naukri API returned %s", resp.status_code)
                return results

            data = resp.json()
            job_details = data.get("jobDetails") or []
            if not job_details:
                break

            for raw in job_details:
                job = _normalize_job(raw)
                if job:
                    results.append(job)
                if len(results) >= max_results:
                    break

            if page < pages_needed:
                time.sleep(0.5)

        except Exception as exc:
            logger.warning("Naukri API page %d failed: %s", page, exc)
            break

    return results


def _search_via_playwright(role: str, city: str, max_results: int) -> list[dict]:
    role_slug = _slugify(role)
    city_slug = _slugify(city)
    url = f"https://www.naukri.com/{role_slug}-jobs-in-{city_slug}"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright not installed; cannot use Naukri fallback")
        return []

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("beautifulsoup4 not installed; cannot parse Naukri fallback")
        return []

    results = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=_API_HEADERS["User-Agent"],
                locale="en-IN",
            )
            page = context.new_page()
            page.goto(url, timeout=30000, wait_until="networkidle")
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")

        job_cards = soup.select("article.jobTuple, div.jobTuple, div[class*='job-tuple']")
        if not job_cards:
            job_cards = soup.select("[data-job-id]")

        for card in job_cards:
            if len(results) >= max_results:
                break

            title_el = card.select_one("a.title, a[class*='title'], .jobtitle a, h2 a")
            company_el = card.select_one(".companyInfo a, a[class*='company']")
            location_el = card.select_one(".location span, li[class*='location']")
            link_el = card.select_one("a.title, a[href*='naukri.com/job']")

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            location = location_el.get_text(strip=True) if location_el else city
            href = (link_el.get("href") or "") if link_el else ""

            if not title or not href:
                continue
            if not _is_india_location(location):
                continue

            results.append({
                "title": title,
                "company": company,
                "location": location,
                "url": href,
                "apply_url": href,
                "description": "",
                "salary": "",
                "_source_type": "naukri",
            })

    except Exception as exc:
        logger.warning("Naukri Playwright fallback failed: %s", exc)

    return results


class NaukriAdapter:
    """Job search adapter for Naukri.com (India)."""

    def search(self, role: str, city: str, max_results: int = 50) -> list[dict]:
        try:
            results = _search_via_api(role, city, max_results)
            if results:
                return results[:max_results]
        except Exception as exc:
            logger.warning("Naukri API path failed entirely: %s", exc)

        try:
            return _search_via_playwright(role, city, max_results)
        except Exception as exc:
            logger.warning("Naukri Playwright path failed entirely: %s", exc)

        return []


def search_naukri(role: str, city: str, max_results: int = 50) -> list[dict]:
    return NaukriAdapter().search(role, city, max_results)
