"""
IIMJobs adapter — DDG site: search + requests HTML extraction.
IIMJobs is a legacy PHP/server-rendered site — requests gets full page.
Targets MBA/consulting/product management roles in India.
"""
import logging
import re
import time

import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Referer": "https://www.iimjobs.com/",
}


def search_iimjobs(role: str, city: str = "", max_results: int = 30) -> list[dict]:
    """Search IIMJobs via DDG site: query."""
    query = f'site:iimjobs.com "{role}"'
    if city:
        query += f' "{city}"'

    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region="in-en"))
    except Exception as e:
        logger.debug(f"[IIMJobs] DDG search failed: {e}")
        return []

    out = []
    seen = set()
    for r in results:
        url = r.get("href") or r.get("url", "")
        if not url or "iimjobs.com" not in url or url in seen:
            continue
        # Only job detail pages (not search/category pages)
        if not re.search(r"/j/|/job/", url):
            continue
        seen.add(url)

        title = r.get("title", "")
        snippet = r.get("body", "") or r.get("snippet", "")

        enriched = _fetch_job(url, title, snippet, city)
        out.append(enriched)
        if len(out) >= max_results:
            break
        time.sleep(0.3)

    logger.info(f"[IIMJobs] {len(out)} jobs for '{role}' / '{city}'")
    return out


def _fetch_job(url: str, fallback_title: str, fallback_snippet: str, city: str) -> dict:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10, allow_redirects=True)
        if not resp.ok:
            raise ValueError(f"HTTP {resp.status_code}")

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        title_el = soup.find("h1") or soup.find("h2")
        title = title_el.get_text(strip=True) if title_el else fallback_title

        # IIMJobs job detail containers
        desc_el = (
            soup.find(class_=re.compile(r"job.?desc|jobDesc|description|jd", re.I))
            or soup.find(id=re.compile(r"job.?desc|description", re.I))
            or soup.find("article")
            or soup.find("main")
        )
        description = desc_el.get_text(" ", strip=True) if desc_el else fallback_snippet

        company_el = soup.find(class_=re.compile(r"company.?name|employer|org", re.I))
        company = company_el.get_text(strip=True) if company_el else ""

        loc_el = soup.find(class_=re.compile(r"location|city", re.I))
        location = loc_el.get_text(strip=True) if loc_el else city or "India"

        return {
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "apply_url": url,
            "description": description[:6000],
            "skills": [],
            "_source_type": "iimjobs",
        }
    except Exception as e:
        logger.debug(f"[IIMJobs] fetch failed for {url}: {e}")
        # Try to infer company from the fallback title (DDG search result often
        # includes "Company Name - Job Title" or "Job Title at Company")
        company = ""
        if fallback_title:
            # Pattern: "Company - Title" or "Title - Company"
            for sep in (" - ", " — ", " | "):
                parts = fallback_title.rsplit(sep, 1)
                if len(parts) == 2 and 2 < len(parts[1]) < 80:
                    # Pick the part that is NOT all-caps and NOT a known job title pattern
                    for candidate in (parts[1], parts[0]):
                        candidate = candidate.strip()
                        if (not candidate.isupper()
                                and not re.search(r"\b(manager|engineer|developer|analyst|consultant|director|lead|head|vp|chief|architect)\b", candidate, re.I)
                                and 2 < len(candidate) < 80):
                            company = candidate
                            break
                    if company:
                        break
        return {
            "title": fallback_title,
            "company": company,
            "location": city or "India",
            "url": url,
            "apply_url": url,
            "description": fallback_snippet,
            "skills": [],
            "_source_type": "iimjobs",
        }
