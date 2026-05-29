"""
Wellfound adapter — DDG site: search + snippet-first extraction.
Wellfound is a React SPA — requests returns shell HTML. We rely on DDG snippet
as description fallback. __NEXT_DATA__ attempted if page has SSR content.

Note: Full JD requires JS rendering (Playwright). Without it, description = DDG snippet.
`_fetch_missing_jds` in on_demand.py will try to enrich later.
"""
import json
import logging
import re
import time

import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}


def search_wellfound(role: str, city: str = "", max_results: int = 30) -> list[dict]:
    """Search Wellfound via DDG site: query. Returns snippet-level data."""
    query = f'site:wellfound.com/l/job-listings "{role}"'
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
        logger.debug(f"[Wellfound] DDG search failed: {e}")
        return []

    out = []
    seen = set()
    for r in results:
        url = r.get("href") or r.get("url", "")
        if not url or "wellfound.com" not in url or url in seen:
            continue
        seen.add(url)

        title = r.get("title", "")
        snippet = r.get("body", "") or r.get("snippet", "")

        # Try to enrich with SSR JSON if available
        enriched = _try_fetch(url)
        if enriched:
            out.append(enriched)
        else:
            out.append({
                "title": title,
                "company": _infer_company(url, title),
                "location": city or "India",
                "url": url,
                "apply_url": url,
                "description": snippet,
                "skills": [],
                "_source_type": "wellfound",
            })
        if len(out) >= max_results:
            break

    logger.info(f"[Wellfound] {len(out)} jobs for '{role}' / '{city}'")
    return out


def _try_fetch(url: str) -> dict | None:
    """Attempt requests fetch — succeeds if Wellfound SSR includes __NEXT_DATA__."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10, allow_redirects=True)
        if not resp.ok:
            return None
        html = resp.text
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(1))
        props = data.get("props", {}).get("pageProps", {})
        job = props.get("job") or props.get("listing") or {}
        if not job.get("title"):
            return None
        return {
            "title": job.get("title", ""),
            "company": (job.get("startupName") or job.get("company") or {}).get("name", "") if isinstance(job.get("startupName") or job.get("company"), dict) else str(job.get("startupName") or job.get("company") or ""),
            "location": job.get("locationNames", [city])[0] if job.get("locationNames") else city,
            "url": url,
            "apply_url": url,
            "description": _strip_html(job.get("description", "")),
            "skills": job.get("skills") or [],
            "work_mode": "remote" if job.get("remote") else "",
            "_source_type": "wellfound",
        }
    except Exception:
        return None


def _infer_company(url: str, title: str) -> str:
    # wellfound.com/l/job-listings/company-name/role → extract company slug
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2:
        slug = parts[-2].replace("-", " ").title()
        if slug not in ("Job Listings", "L", ""):
            return slug
    return ""


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", re.sub(r"&\w+;", " ", html or "")).strip()
