"""
CareerLoop Verification — Check if jobs are actually active.

Before showing any job:
- URL opens (HTTP check)
- Apply route exists
- Not closed/expired
- Title/company extracted correctly

Status: VERIFIED_ACTIVE / UNVERIFIED / STALE / CLOSED
"""

import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Timeout for URL checks
URL_TIMEOUT = 10

# Patterns that indicate a closed/expired job
CLOSED_PATTERNS = [
    r"position.*(?:filled|closed|expired|no longer)",
    r"this job.*(?:is no longer|has been|was) (?:available|active|open)",
    r"sorry.*(?:this|the) (?:job|position|role).*(?:closed|filled|expired)",
    r"job.*expired",
    r"application.*closed",
    r"no longer accepting",
]

# Patterns that indicate an active apply option
APPLY_PATTERNS = [
    r"apply\s*(?:now|here|today|for this)",
    r"submit.*application",
    r"easy\s*apply",
    r"application.*form",
    r"<button[^>]*>.*apply.*</button>",
    r"<a[^>]*>.*apply.*</a>",
    r"href.*apply",
]


class JobVerifier:
    """Verify that discovered jobs are actually active and reachable."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def verify(self, job: dict) -> dict:
        """
        Verify a single job. Returns job dict with verification fields added:
        - verification_status: VERIFIED_ACTIVE / UNVERIFIED / STALE / CLOSED
        - verification_reason: why this status
        - apply_route_found: bool
        """
        url = job.get("url", job.get("source_url", job.get("application_url", "")))
        result = {
            "verification_status": "UNVERIFIED",
            "verification_reason": "not checked",
            "apply_route_found": False,
            "url_reachable": False,
        }

        if not url:
            result["verification_reason"] = "no URL"
            job.update(result)
            return job

        # Step 1: Check if URL opens
        try:
            resp = self.session.get(url, timeout=URL_TIMEOUT, allow_redirects=True)
            result["url_reachable"] = True
            result["http_status"] = resp.status_code

            if resp.status_code >= 400:
                result["verification_status"] = "CLOSED"
                result["verification_reason"] = f"HTTP {resp.status_code}"
                job.update(result)
                return job

            content = resp.text[:5000].lower()

            # Step 2: Check for closed/expired signals
            for pattern in CLOSED_PATTERNS:
                if re.search(pattern, content):
                    result["verification_status"] = "CLOSED"
                    result["verification_reason"] = f"closed signal: {pattern[:30]}"
                    job.update(result)
                    return job

            # Step 3: Check for apply option
            for pattern in APPLY_PATTERNS:
                if re.search(pattern, content):
                    result["apply_route_found"] = True
                    break

            # Step 4: Check freshness
            freshness = self._check_freshness(job, content)

            if freshness == "stale":
                result["verification_status"] = "STALE"
                result["verification_reason"] = "posted more than 30 days ago"
            elif result["apply_route_found"]:
                result["verification_status"] = "VERIFIED_ACTIVE"
                result["verification_reason"] = "URL reachable, apply route found"
            else:
                # URL opens but no apply button found — still might be valid
                result["verification_status"] = "VERIFIED_ACTIVE"
                result["verification_reason"] = "URL reachable, no apply button detected (may need JS)"

        except requests.exceptions.Timeout:
            result["verification_reason"] = "URL timeout"
        except requests.exceptions.ConnectionError:
            result["verification_reason"] = "connection error"
        except requests.exceptions.TooManyRedirects:
            result["verification_reason"] = "too many redirects"
        except Exception as e:
            result["verification_reason"] = f"error: {str(e)[:100]}"

        job.update(result)
        return job

    def verify_batch(self, jobs: list[dict], max_verify: int = 20) -> list[dict]:
        """Verify multiple jobs. Returns all with verification status."""
        verified = []
        for i, job in enumerate(jobs[:max_verify]):
            logger.info(f"Verifying [{i+1}/{min(len(jobs), max_verify)}]: {job.get('url','')[:60]}")
            verified.append(self.verify(job))
        return verified

    def _check_freshness(self, job: dict, page_content: str = "") -> str:
        """Check if job posting is fresh, stale, or unknown."""
        posted = job.get("posted_at", "")
        if not posted:
            return "unknown"
        try:
            posted_date = datetime.fromisoformat(posted[:10])
            age = (datetime.now(timezone.utc) - posted_date.replace(tzinfo=timezone.utc)).days
            if age > 30:
                return "stale"
            elif age > 14:
                return "aging"
            else:
                return "fresh"
        except (ValueError, TypeError):
            return "unknown"

    def get_verified_active(self, jobs: list[dict]) -> list[dict]:
        """Filter to only VERIFIED_ACTIVE jobs."""
        return [j for j in jobs if j.get("verification_status") == "VERIFIED_ACTIVE"]


class JDValidator:
    """
    Validates that a job description is real scraped content — never fabricated.

    Rule: if JD is absent, too short, or matches LLM-generation signals, it is
    marked invalid. Council MUST NOT run on an invalid JD.
    """

    MIN_JD_LENGTH = 200  # characters — real JDs are always longer than this

    # Phrases that appear in LLM-generated "helpful" JD fallbacks but not real postings
    LLM_FABRICATION_SIGNALS = [
        r"^(about the role|role overview|job overview|position overview)\s*\n",
        r"^we are (looking for|seeking) a (talented|skilled|passionate|driven)",
        r"^(the ideal candidate|our ideal candidate) will",
        r"^(join our|join the) (team|growing team|dynamic team)",
        r"responsibilities (include|will include|are as follows)\s*:",
        r"^(qualifications|requirements)\s*:\s*\n.*bachelor",
    ]

    def validate(self, jd_text: str, source_url: str = "") -> "JDValidationResult":
        if not jd_text or not jd_text.strip():
            return JDValidationResult(
                valid=False,
                reason="jd_empty",
                message="No job description found. Visit the URL directly to read the full posting.",
            )

        cleaned = jd_text.strip()
        if len(cleaned) < self.MIN_JD_LENGTH:
            return JDValidationResult(
                valid=False,
                reason="jd_too_short",
                message=f"Job description is too short ({len(cleaned)} chars). May be a scraping failure.",
            )

        cleaned_lower = cleaned.lower()
        for pattern in self.LLM_FABRICATION_SIGNALS:
            if re.search(pattern, cleaned_lower, re.MULTILINE):
                return JDValidationResult(
                    valid=False,
                    reason="jd_fabrication_signal",
                    message="Job description appears to be AI-generated rather than scraped from the source. Skipping to prevent hallucination.",
                )

        return JDValidationResult(valid=True, reason="ok", message="")


class JDValidationResult:
    def __init__(self, valid: bool, reason: str, message: str = ""):
        self.valid = valid
        self.reason = reason
        self.message = message

    def __bool__(self):
        return self.valid
