"""
Instahyre adapter — DDG site: search + snippet-first extraction.
Instahyre is a React SPA — requests returns empty shell. We use DDG snippet
as description. `_fetch_missing_jds` / ScrapeGraph will enrich later.

Note: Full JD requires JS rendering (Playwright). Currently snippet-only.
"""
import logging
import re

logger = logging.getLogger(__name__)


def search_instahyre(role: str, city: str = "", max_results: int = 30) -> list[dict]:
    """Search Instahyre via DDG site: query. Returns snippet-level data."""
    query = f'site:instahyre.com "{role}"'
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
        logger.debug(f"[Instahyre] DDG search failed: {e}")
        return []

    out = []
    seen = set()
    for r in results:
        url = r.get("href") or r.get("url", "")
        if not url or "instahyre.com" not in url or url in seen:
            continue
        # Only job detail pages
        if not re.search(r"/jobs/|/job/", url):
            continue
        seen.add(url)

        title = r.get("title", "")
        snippet = r.get("body", "") or r.get("snippet", "")

        out.append({
            "title": title,
            "company": _infer_company(url),
            "location": city or "India",
            "url": url,
            "apply_url": url,
            "description": snippet,
            "skills": [],
            "_source_type": "instahyre",
        })
        if len(out) >= max_results:
            break

    logger.info(f"[Instahyre] {len(out)} jobs for '{role}' / '{city}'")
    return out


def _infer_company(url: str) -> str:
    # instahyre.com/jobs/company-slug/role-slug → extract company
    parts = url.rstrip("/").split("/")
    for i, p in enumerate(parts):
        if p in ("jobs", "job") and i + 1 < len(parts):
            return parts[i + 1].replace("-", " ").title()
    return ""
