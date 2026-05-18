"""
CareerLoop ATS Adapter Layer — Structured job fetching from Greenhouse, Lever, Ashby.

These are free public endpoints — no scraping, no API key.
Returns clean structured job objects directly from ATS JSON APIs.

Priority: ATS APIs > career page HTML scraping > job board fallback.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
INDIA_CITY_KEYWORDS = [
    "india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad",
    "chennai", "pune", "kolkata", "noida", "gurgaon", "gurugram",
    "remote", "hybrid",  # remote/hybrid roles are fair game
]


@dataclass
class ATSJob:
    """Structured job from an ATS API — never fabricated, always sourced."""
    title: str
    company_id: str
    company_name: str
    source: str                        # greenhouse|lever|ashby|workday
    source_url: str                    # direct apply URL
    location_raw: str = ""
    role_summary: str = ""             # opening description
    responsibilities: str = ""        # what you'll do
    requirements: str = ""            # what you need
    benefits: str = ""                # what you get
    raw_jd_text: str = ""             # full combined JD text (for scoring)
    jd_confidence: float = 1.0        # ATS APIs = 1.0 (structured, not scraped)
    posted_at: Optional[str] = None
    job_id_ats: str = ""              # native ATS job ID
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company_name,
            "company_id": self.company_id,
            "source": self.source,
            "source_url": self.source_url,
            "url": self.source_url,
            "location": self.location_raw,
            "description": self.raw_jd_text,
            "role_summary": self.role_summary,
            "responsibilities": self.responsibilities,
            "requirements": self.requirements,
            "benefits": self.benefits,
            "jd_confidence": self.jd_confidence,
            "posted_at": self.posted_at,
            "job_id_ats": self.job_id_ats,
            "scraped_at": self.scraped_at,
            "from_company_portal": True,
        }


def _is_india_location(location: str) -> bool:
    """Return True if location string suggests India or remote."""
    if not location:
        return False
    loc = location.lower()
    return any(kw in loc for kw in INDIA_CITY_KEYWORDS)


def _strip_html(html: str) -> str:
    """Remove HTML tags, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_jd_sections(raw_text: str) -> dict:
    """
    Heuristically split a JD into 3 sections.
    Returns: {role_summary, responsibilities, requirements, benefits}
    All sections contain verbatim text from raw_text — nothing invented.
    """
    sections = {"role_summary": "", "responsibilities": "", "requirements": "", "benefits": ""}
    if not raw_text:
        return sections

    text = raw_text.strip()

    # Section header patterns (case-insensitive)
    resp_pattern = re.compile(
        r"(what you.?ll do|responsibilities|key responsibilities|your role|"
        r"about the role|the role|what you will do|duties|job duties)",
        re.IGNORECASE,
    )
    req_pattern = re.compile(
        r"(what you.?ll need|requirements|qualifications|what we.?re looking for|"
        r"must have|skills required|experience required|what you bring)",
        re.IGNORECASE,
    )
    benefits_pattern = re.compile(
        r"(what we offer|benefits|perks|compensation|why join us|"
        r"what you get|our benefits|what.?s in it for you)",
        re.IGNORECASE,
    )

    # Find section positions
    resp_match = resp_pattern.search(text)
    req_match = req_pattern.search(text)
    benefits_match = benefits_pattern.search(text)

    positions = []
    if resp_match:
        positions.append(("responsibilities", resp_match.start()))
    if req_match:
        positions.append(("requirements", req_match.start()))
    if benefits_match:
        positions.append(("benefits", benefits_match.start()))
    positions.sort(key=lambda x: x[1])

    if not positions:
        # No section headers found — entire text goes to role_summary
        sections["role_summary"] = text
        return sections

    # Everything before first section header = role_summary
    sections["role_summary"] = text[: positions[0][1]].strip()

    for i, (section_name, start) in enumerate(positions):
        end = positions[i + 1][1] if i + 1 < len(positions) else len(text)
        sections[section_name] = text[start:end].strip()

    return sections


class GreenhouseAdapter:
    """
    Fetches jobs from Greenhouse public job board API.
    Endpoint: https://boards.greenhouse.io/embed/job_board/jobs?for={token}
    """

    BASE = "https://boards.greenhouse.io/embed/job_board/jobs?for={token}"
    JOB_URL = "https://boards.greenhouse.io/embed/job_board/job_json?for={token}&token={job_id}"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (compatible; CareerLoopBot/1.0)"
        )

    def _token_from_url(self, ats_url: str) -> Optional[str]:
        """Extract company token from ATS URL."""
        m = re.search(r"greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)", ats_url, re.IGNORECASE)
        return m.group(1) if m else None

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[ATSJob]:
        token = self._token_from_url(ats_url)
        if not token:
            logger.warning(f"[Greenhouse] Could not extract token from {ats_url}")
            return []

        try:
            resp = self.session.get(self.BASE.format(token=token), timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"[Greenhouse] fetch failed for {company_name}: {e}")
            return []

        jobs_raw = data.get("jobs", [])
        results = []
        for job in jobs_raw:
            location = job.get("location", {}).get("name", "")
            if not _is_india_location(location):
                continue

            # Fetch individual job for full description
            jd_sections = self._fetch_jd(token, str(job.get("id", "")))
            raw_text = " ".join(jd_sections.values()).strip()

            results.append(ATSJob(
                title=job.get("title", ""),
                company_id=company_id,
                company_name=company_name,
                source="greenhouse",
                source_url=job.get("absolute_url", ""),
                location_raw=location,
                role_summary=jd_sections.get("role_summary", ""),
                responsibilities=jd_sections.get("responsibilities", ""),
                requirements=jd_sections.get("requirements", ""),
                benefits=jd_sections.get("benefits", ""),
                raw_jd_text=raw_text,
                job_id_ats=str(job.get("id", "")),
                posted_at=job.get("updated_at", ""),
            ))
            time.sleep(0.3)  # polite rate limiting

        logger.info(f"[Greenhouse] {company_name}: {len(results)} India jobs")
        return results

    def _fetch_jd(self, token: str, job_id: str) -> dict:
        try:
            url = self.JOB_URL.format(token=token, job_id=job_id)
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            content_html = data.get("content", "")
            raw = _strip_html(content_html)
            return _split_jd_sections(raw)
        except Exception:
            return {"role_summary": "", "responsibilities": "", "requirements": "", "benefits": ""}


class LeverAdapter:
    """
    Fetches jobs from Lever public postings API.
    Endpoint: https://api.lever.co/v0/postings/{company}?mode=json
    """

    BASE = "https://api.lever.co/v0/postings/{slug}?mode=json"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0 (compatible; CareerLoopBot/1.0)"

    def _slug_from_url(self, ats_url: str) -> Optional[str]:
        m = re.search(r"lever\.co/([a-z0-9_-]+)", ats_url, re.IGNORECASE)
        return m.group(1) if m else None

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[ATSJob]:
        slug = self._slug_from_url(ats_url)
        if not slug:
            logger.warning(f"[Lever] Could not extract slug from {ats_url}")
            return []

        try:
            resp = self.session.get(self.BASE.format(slug=slug), timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            jobs_raw = resp.json()
        except Exception as e:
            logger.warning(f"[Lever] fetch failed for {company_name}: {e}")
            return []

        results = []
        for job in jobs_raw:
            location = job.get("categories", {}).get("location", "")
            if not _is_india_location(location):
                continue

            # Lever provides plain text description sections
            desc_plain = job.get("descriptionPlain", "") or _strip_html(job.get("description", ""))
            lists = job.get("lists", [])
            responsibilities = ""
            requirements = ""
            benefits = ""
            for lst in lists:
                name = lst.get("text", "").lower()
                content = _strip_html(lst.get("content", ""))
                if any(w in name for w in ["responsibilit", "what you'll do", "duties", "role"]):
                    responsibilities = content
                elif any(w in name for w in ["requirement", "qualif", "what you need", "must have"]):
                    requirements = content
                elif any(w in name for w in ["benefit", "offer", "perk", "why join"]):
                    benefits = content

            # If structured sections missing, heuristic-split the plain description
            if not responsibilities and not requirements:
                sections = _split_jd_sections(desc_plain)
                responsibilities = sections["responsibilities"]
                requirements = sections["requirements"]
                benefits = sections["benefits"]
                role_summary = sections["role_summary"]
            else:
                role_summary = desc_plain[:500] if desc_plain else ""

            raw_text = " ".join([role_summary, responsibilities, requirements, benefits]).strip()

            results.append(ATSJob(
                title=job.get("text", ""),
                company_id=company_id,
                company_name=company_name,
                source="lever",
                source_url=job.get("hostedUrl", job.get("applyUrl", "")),
                location_raw=location,
                role_summary=role_summary,
                responsibilities=responsibilities,
                requirements=requirements,
                benefits=benefits,
                raw_jd_text=raw_text,
                job_id_ats=job.get("id", ""),
                posted_at=str(job.get("createdAt", "")),
            ))

        logger.info(f"[Lever] {company_name}: {len(results)} India jobs")
        return results


class AshbyAdapter:
    """
    Fetches jobs from Ashby public job board.
    Endpoint: https://{slug}.ashbyhq.com/api/non-user-facing/job-board
    """

    BASE = "https://{slug}.ashbyhq.com/api/non-user-facing/job-board"
    JOB_BASE = "https://{slug}.ashbyhq.com/api/non-user-facing/job-board/job-posting/{job_id}"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0 (compatible; CareerLoopBot/1.0)"

    def _slug_from_url(self, ats_url: str) -> Optional[str]:
        # subdomain form: {slug}.ashbyhq.com
        m = re.search(r"([a-z0-9_-]+)\.ashbyhq\.com", ats_url, re.IGNORECASE)
        if m:
            return m.group(1)
        # posting-api form: api.ashbyhq.com/posting-api/job-board/{slug}
        m2 = re.search(r"job-board/([a-z0-9_-]+)", ats_url, re.IGNORECASE)
        return m2.group(1) if m2 else None

    def _board_url(self, slug: str) -> str:
        """Try posting-api first (public), fall back to non-user-facing."""
        return f"https://api.ashbyhq.com/posting-api/job-board/{slug}"

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[ATSJob]:
        slug = self._slug_from_url(ats_url)
        if not slug:
            logger.warning(f"[Ashby] Could not extract slug from {ats_url}")
            return []

        url = self._board_url(slug)
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 404:
                # Fallback to non-user-facing API
                resp = self.session.get(self.BASE.format(slug=slug), timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"[Ashby] fetch failed for {company_name}: {e}")
            return []

        # posting-api returns {"jobs": [...]} ; non-user-facing returns {"jobPostings": [...]}
        job_postings = data.get("jobs") or data.get("jobPostings", [])
        results = []

        for job in job_postings:
            # Resolve location — posting-api has it as a string directly
            location_name = job.get("location", "")
            if isinstance(location_name, dict):
                location_name = location_name.get("name", "")
            if job.get("isRemote") or job.get("workplaceType") == "Remote":
                location_name = location_name or "Remote"

            if not location_name and job.get("secondaryLocations"):
                location_name = job["secondaryLocations"][0].get("name", "")

            # Filter to India jobs
            if not job.get("isRemote") and not _is_india_location(location_name):
                # posting-api has full JD inline — no extra fetch needed
                if "descriptionPlain" not in job and "descriptionHtml" not in job:
                    full = self._fetch_job(slug, job.get("id", ""))
                    if full:
                        location_name = full.get("location", "")
                        if not _is_india_location(location_name):
                            continue
                    else:
                        continue
                else:
                    continue

            # Extract JD text — posting-api has inline, else fetch
            if "descriptionPlain" in job or "descriptionHtml" in job:
                raw = job.get("descriptionPlain", "") or _strip_html(job.get("descriptionHtml", ""))
            else:
                full = self._fetch_job(slug, job.get("id", ""))
                if not full:
                    continue
                desc_html = full.get("descriptionHtml", "") or full.get("descriptionSafe", "")
                raw = _strip_html(desc_html)

            sections = _split_jd_sections(raw)

            apply_url = (
                job.get("applyUrl") or
                job.get("jobUrl") or
                f"https://{slug}.ashbyhq.com/job/{job.get('id', '')}"
            )

            results.append(ATSJob(
                title=job.get("title", ""),
                company_id=company_id,
                company_name=company_name,
                source="ashby",
                source_url=apply_url,
                location_raw=location_name,
                role_summary=sections["role_summary"],
                responsibilities=sections["responsibilities"],
                requirements=sections["requirements"],
                benefits=sections["benefits"],
                raw_jd_text=raw,
                job_id_ats=str(job.get("id", "")),
            ))

        logger.info(f"[Ashby] {company_name}: {len(results)} India jobs")
        return results

    def _fetch_job(self, slug: str, job_id: str) -> Optional[dict]:
        try:
            url = self.JOB_BASE.format(slug=slug, job_id=job_id)
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None


class ATSAdapter:
    """
    Unified adapter — routes to correct ATS based on company ats_provider field.
    Returns list[ATSJob] regardless of source.
    """

    def __init__(self):
        self._greenhouse = GreenhouseAdapter()
        self._lever = LeverAdapter()
        self._ashby = AshbyAdapter()

    def fetch_jobs(self, company_id: str, company_name: str,
                   ats_provider: str, ats_url: str) -> list[ATSJob]:
        """
        Fetch jobs for a company from its ATS.
        Returns empty list on any failure — never raises.
        """
        if not ats_url:
            return []

        try:
            if ats_provider == "greenhouse":
                return self._greenhouse.fetch(company_id, company_name, ats_url)
            elif ats_provider == "lever":
                return self._lever.fetch(company_id, company_name, ats_url)
            elif ats_provider == "ashby":
                return self._ashby.fetch(company_id, company_name, ats_url)
            elif ats_provider in ("workday", "successfactors", "icims", "taleo", "none", "custom"):
                # No structured API adapter — caller falls back to career page crawler
                logger.debug(f"[ATS] {ats_provider} for {company_name}: no API adapter, use career page crawler")
                return []
            else:
                logger.debug(f"[ATS] Unknown provider '{ats_provider}' for {company_name}")
                return []
        except Exception as e:
            logger.warning(f"[ATS] Unexpected error for {company_name} ({ats_provider}): {e}")
            return []

    def detect_ats(self, domain: str) -> tuple[str, str]:
        """
        Probe common ATS endpoints for a domain.
        Returns (ats_provider, ats_url) or ("none", "") if nothing found.
        """
        slug = re.sub(r"\.(com|in|io|co|net|org|ai)$", "", domain.lower())
        candidates = [
            ("greenhouse", f"https://boards.greenhouse.io/embed/job_board/jobs?for={slug}"),
            ("lever", f"https://api.lever.co/v0/postings/{slug}?mode=json"),
            ("ashby", f"https://{slug}.ashbyhq.com/api/non-user-facing/job-board"),
        ]

        session = requests.Session()
        session.headers["User-Agent"] = "Mozilla/5.0 (compatible; CareerLoopBot/1.0)"

        for provider, url in candidates:
            try:
                resp = session.head(url, timeout=8, allow_redirects=True)
                if resp.status_code == 200:
                    logger.info(f"[ATS detect] {domain} → {provider} ({url})")
                    return provider, url
            except Exception:
                continue

        return "none", ""
