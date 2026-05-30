"""
Cutshort adapter — DDG site: search + __NEXT_DATA__ JSON extraction.
Cutshort job pages are Next.js SSR — requests gets full HTML with embedded JSON.
"""
import json
import logging
import re
import time
from urllib.parse import quote_plus

import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}
_JOB_URL_RE = re.compile(r"cutshort\.io/job/[^\"'\s>]+", re.I)


def search_cutshort(role: str, city: str = "", max_results: int = 30) -> list[dict]:
    """Search Cutshort.io via DDG site: query, extract jobs from SSR pages."""
    query = f'site:cutshort.io/job "{role}"'
    if city:
        query += f' "{city}"'

    urls = _ddg_urls(query, limit=max_results)
    if not urls:
        logger.debug(f"[Cutshort] DDG returned 0 URLs for '{role}' / '{city}'")
        return []

    out = []
    for url in urls[:max_results]:
        job = _fetch_job(url)
        if job:
            out.append(job)
        time.sleep(0.3)

    logger.info(f"[Cutshort] {len(out)} jobs for '{role}' / '{city}'")
    return out


def _ddg_urls(query: str, limit: int = 20) -> list[str]:
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=limit, region="in-en"))
        seen = set()
        urls = []
        for r in results:
            url = r.get("href") or r.get("url", "")
            if url and "cutshort.io/job/" in url and url not in seen:
                seen.add(url)
                urls.append(url)
        return urls
    except Exception as e:
        logger.debug(f"[Cutshort] DDG search failed: {e}")
        return []


def _fetch_job(url: str) -> dict | None:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10, allow_redirects=True)
        if not resp.ok:
            return None
        html = resp.text

        # Try __NEXT_DATA__ first (SSR JSON)
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                props = data.get("props", {}).get("pageProps", {})
                job = props.get("job") or props.get("jobData") or {}
                if job:
                    return {
                        "title": job.get("title", ""),
                        "company": (job.get("company") or {}).get("name", ""),
                        "location": _extract_location(job),
                        "url": url,
                        "apply_url": url,
                        "description": _strip_html(
                            job.get("description", "") or job.get("descriptionHtml", "")
                        ),
                        "skills": job.get("skills") or [],
                        "work_mode": job.get("workMode", "") or job.get("remote", ""),
                        "_source_type": "cutshort",
                    }
            except (json.JSONDecodeError, KeyError):
                pass

        # Fallback: BS4 heuristic
        return _bs4_extract(url, html)
    except Exception as e:
        logger.debug(f"[Cutshort] fetch failed for {url}: {e}")
        return None


def _extract_location(job: dict) -> str:
    locs = job.get("locations") or []
    if locs and isinstance(locs[0], dict):
        return locs[0].get("name", "India")
    if isinstance(locs, list) and locs:
        return str(locs[0])
    return job.get("location", "India")


def _bs4_extract(url: str, html: str) -> dict | None:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        title = (soup.find("h1") or soup.find("h2") or soup.new_tag("x")).get_text(strip=True)
        body = soup.get_text(" ", strip=True)
        if len(body) < 100:
            return None

        # Extract company from the page (not hardcoded empty anymore)
        company = ""
        # Try meta tags first
        for meta_attr in [{"property": "og:site_name"}, {"name": "og:site_name"},
                          {"name": "author"}]:
            meta = soup.find("meta", attrs=meta_attr)
            if meta and meta.get("content", "").strip():
                company = meta["content"].strip()
                break
        # Try company name elements
        if not company:
            for cls_pat in [r"company.?name", r"employer", r"organization", r"org.?name"]:
                el = soup.find(class_=re.compile(cls_pat, re.I))
                if el:
                    c = el.get_text(" ", strip=True)
                    if 2 < len(c) < 80:
                        company = c
                        break

        # Fallback: infer from URL slug (Cutshort URLs encode company in the path)
        if not company and url:
            from urllib.parse import urlparse as _urlparse
            parsed = _urlparse(url)
            path = parsed.path.strip("/")
            if "/job/" in path:
                parts = path.split("/")[-1].split("-")
                # Same logic as on_demand._infer_company_from_url
                _skip = frozenset({
                    "bangalore", "bengaluru", "chennai", "mumbai", "delhi", "india",
                    "hyderabad", "pune", "remote", "gurgaon", "noida", "kolkata",
                    "fulltime", "full-time", "job", "apply",
                })
                # Job title keywords that should never be parsed as company name
                _job_kw = frozenset({
                    "engineer", "manager", "developer", "analyst", "consultant",
                    "director", "lead", "head", "architect", "scientist", "product",
                    "designer", "specialist", "coordinator", "associate", "vp",
                    "admin", "assistant", "intern", "trainee", "gen", "ai", "ml",
                    "software", "data", "cloud", "fullstack", "devops", "qa",
                    "frontend", "backend", "platform", "infrastructure",
                })
                for i in range(len(parts) - 1, 0, -1):
                    part = parts[i]
                    # Skip hash-like fragments (mixed case+digits which indicate IDs)
                    is_hash = (len(part) >= 6
                               and bool(re.search(r"\d", part))
                               and (bool(re.search(r"[A-Z]", part)) or bool(re.search(r"[a-z]", part))))
                    if is_hash or part.lower() in _skip:
                        continue
                    if len(part) >= 3:
                        comp_parts = []
                        for j in range(i, max(i - 3, -1), -1):
                            pj = parts[j]
                            pj_is_hash = (len(pj) >= 6
                                          and bool(re.search(r"\d", pj))
                                          and (bool(re.search(r"[A-Z]", pj)) or bool(re.search(r"[a-z]", pj))))
                            if pj_is_hash or pj.lower() in _skip:
                                break
                            comp_parts.insert(0, pj)
                        if comp_parts and not any(p.lower() in _job_kw for p in comp_parts):
                            company = " ".join(comp_parts).replace("-", " ").title()
                        break

        return {
            "title": title,
            "company": company,
            "location": "India",
            "url": url,
            "apply_url": url,
            "description": body[:6000],
            "skills": [],
            "_source_type": "cutshort",
        }
    except Exception:
        return None


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", re.sub(r"&\w+;", " ", html or "")).strip()
