"""
Spire AI career portal adapter.

Spire AI (spire2grow.com) is used by Indian companies like Myntra.
Discovery: GET /ies/v1/p/workspaceId?domain={career_page_domain}
Jobs:       GET /ies/v1/p/requisition/_search with workspaceid header

Phase placement: Phase C (ATS portal scrape) — NOT Phase B (job boards).
Requires a company career_page_url input — no role/city searchable API.
Wire via Phase A company discovery → Phase C portal scrape once Phase A is re-enabled.
"""

import logging
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

BASE = "https://io.spire2grow.com/ies/v1/p"
TIMEOUT = 15


def _domain(career_page_url: str) -> str:
    return urlparse(career_page_url).netloc or career_page_url


def discover_workspace_id(career_page_url: str) -> str | None:
    """Return workspace ID for a given career page URL, or None."""
    domain = _domain(career_page_url)
    try:
        r = requests.get(f"{BASE}/workspaceId", params={"domain": domain}, timeout=TIMEOUT)
        if r.ok and r.text and not r.text.startswith("{"):
            return r.text.strip()
        if r.ok:
            data = r.json()
            return data if isinstance(data, str) else None
    except Exception as e:
        logger.debug(f"[SpireAI] workspace lookup failed for {domain}: {e}")
    return None


def fetch_jobs(workspace_id: str, company_name: str, career_page_url: str) -> list[dict]:
    """Fetch all open jobs for a Spire AI workspace."""
    headers = {
        "workspaceid": workspace_id,
        "Referer": career_page_url,
        "Origin": f"https://{_domain(career_page_url)}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    jobs = []
    page = 1
    while True:
        try:
            r = requests.get(
                f"{BASE}/requisition/_search",
                params={"page": page, "size": 50, "selectedSortOrder": "desc", "selectedSortField": "postedOn"},
                headers=headers,
                timeout=TIMEOUT,
            )
            if not r.ok:
                break
            data = r.json()
            entities = data.get("entities", [])
            if not entities:
                break
            for j in entities:
                locs = j.get("location") or []
                city = locs[0].get("city", "") if locs else ""
                country = locs[0].get("country", "India") if locs else "India"
                # build job URL from workspace + requisition id
                req_id = j.get("requisitionId") or j.get("id") or ""
                job_url = f"{career_page_url}/jobs/{req_id}" if req_id else career_page_url
                jobs.append({
                    "title": j.get("title") or j.get("jobTitle", ""),
                    "company": company_name,
                    "location": f"{city}, {country}".strip(", "),
                    "url": job_url,
                    "apply_url": job_url,
                    "description": j.get("jobDescription", ""),
                    "department": j.get("department") or j.get("jobFunction", ""),
                    "_source_type": "spireai",
                })
            if len(entities) < 50:
                break
            page += 1
        except Exception as e:
            logger.warning(f"[SpireAI] fetch_jobs page {page} failed: {e}")
            break
    logger.info(f"[SpireAI] {company_name}: {len(jobs)} jobs")
    return jobs
