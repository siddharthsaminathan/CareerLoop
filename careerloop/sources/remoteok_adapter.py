"""
RemoteOK adapter — public JSON API, no auth required.
API: https://remoteok.com/api  (first element is legal notice, skip it)
"""
import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_API_URL = "https://remoteok.com/api"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CareerLoopBot/1.0)",
    "Accept": "application/json",
}


def search_remoteok(role: str, city: str = "", max_results: int = 30) -> list[dict]:
    """Fetch remote jobs from RemoteOK API filtered by role keywords."""
    keywords = {t.lower() for t in re.split(r"[\s/\-]+", role) if len(t) > 2}
    try:
        resp = requests.get(_API_URL, headers=_HEADERS, timeout=15)
        if not resp.ok:
            logger.debug(f"[RemoteOK] API returned {resp.status_code}")
            return []
        data = resp.json()
    except Exception as e:
        logger.debug(f"[RemoteOK] request failed: {e}")
        return []

    out = []
    for job in data:
        if not isinstance(job, dict) or "position" not in job:
            continue
        title = job.get("position", "")
        tags = " ".join(job.get("tags") or []).lower()
        combined = (title + " " + tags).lower()
        if not any(kw in combined for kw in keywords):
            continue
        out.append({
            "title": title,
            "company": job.get("company", ""),
            "location": job.get("location", "remote") or "remote",
            "url": job.get("url", ""),
            "apply_url": job.get("apply_url") or job.get("url", ""),
            "description": _strip_html(job.get("description", "")),
            "skills": list(job.get("tags") or []),
            "salary": job.get("salary", ""),
            "work_mode": "remote",
            "_source_type": "remoteok",
        })
        if len(out) >= max_results:
            break

    logger.info(f"[RemoteOK] {len(out)} jobs for '{role}'")
    return out


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", re.sub(r"&\w+;", " ", html)).strip()
