"""
Remotive adapter — public JSON API, no auth required.
API: https://remotive.com/api/remote-jobs?search=role&limit=100
"""
import logging
import re

import requests

logger = logging.getLogger(__name__)

_API_URL = "https://remotive.com/api/remote-jobs"


def search_remotive(role: str, city: str = "", max_results: int = 30) -> list[dict]:
    """Fetch remote jobs from Remotive API."""
    try:
        resp = requests.get(
            _API_URL,
            params={"search": role, "limit": max_results * 2},
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CareerLoopBot/1.0)"},
        )
        if not resp.ok:
            logger.debug(f"[Remotive] API returned {resp.status_code}")
            return []
        jobs = resp.json().get("jobs", [])
    except Exception as e:
        logger.debug(f"[Remotive] request failed: {e}")
        return []

    keywords = {t.lower() for t in re.split(r"[\s/\-]+", role) if len(t) > 2}
    out = []
    for job in jobs:
        title = job.get("title", "")
        combined = (title + " " + " ".join(job.get("tags") or [])).lower()
        if not any(kw in combined for kw in keywords):
            continue
        out.append({
            "title": title,
            "company": job.get("company_name", ""),
            "location": job.get("candidate_required_location", "remote") or "remote",
            "url": job.get("url", ""),
            "apply_url": job.get("url", ""),
            "description": _strip_html(job.get("description", "")),
            "skills": list(job.get("tags") or []),
            "salary": job.get("salary", ""),
            "work_mode": "remote",
            "_source_type": "remotive",
        })
        if len(out) >= max_results:
            break

    logger.info(f"[Remotive] {len(out)} jobs for '{role}'")
    return out


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", re.sub(r"&\w+;", " ", html)).strip()
