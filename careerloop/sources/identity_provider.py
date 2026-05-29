"""LinkedIn identity provider — SerpAPI (Google search) based.

Powers the Tal-inspired "find me on LinkedIn" onboarding step using the SerpAPI
Google integration that already exists in this codebase (same SERPAPI_KEY as
careerloop/sources/company_discovery.py). No paid per-profile API.

Flow:
  name → Google search (site:linkedin.com/in) → FILTER by name match → candidate
       → "Is this you?" card → user confirms → CV step fills proof points.

Because Google search returns only the public title/snippet (not structured
profile data), we surface name + headline + company + URL for confirmation, then
rely on the CV step to capture detailed experience. The critical safeguard is the
NAME-MATCH FILTER (_name_matches): we only present a candidate when the result's
profile name actually matches what the user typed — so we don't claim a stranger
is them.

Configuration:
  SERPAPI_KEY must be set. If absent, is_configured is False and onboarding
  gracefully falls back to CV-first. No mock/fabricated profiles are ever returned.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

import requests

logger = logging.getLogger("careerloop.sources.identity_provider")

_ENDPOINT = "https://serpapi.com/search"
_TIMEOUT = 15
# Minimum share of the user's name tokens that must appear in a result's profile
# name for us to treat it as "probably them".
_NAME_MATCH_THRESHOLD = 0.6


@dataclass
class ProfileCandidate:
    """A LinkedIn profile resolved for the 'Is this you?' confirmation card."""
    full_name: str
    headline: str = ""
    current_company: str = ""
    location: str = ""
    linkedin_url: str = ""
    avatar_url: str = ""
    snippet: str = ""
    match_score: float = 0.0
    # Hydration fields (best-effort; CV step fills the rest)
    target_roles: str = ""
    target_cities: str = ""
    cv_content: str = ""
    experiences: List[dict] = field(default_factory=list)

    def to_card(self) -> dict:
        """Structured payload the frontend renders as a Tal-style identity card."""
        return {
            "full_name": self.full_name,
            "headline": self.headline,
            "current_company": self.current_company,
            "location": self.location,
            "linkedin_url": self.linkedin_url,
            "avatar_url": self.avatar_url,
        }


def _tokens(name: str) -> List[str]:
    return [t for t in re.findall(r"[a-zA-Z]+", (name or "").lower()) if len(t) > 1]


def _parse_title(title: str) -> dict:
    """LinkedIn Google result title → {name, headline, company}.

    Typical title: "Priya Sharma - Senior ML Engineer - FinScale | LinkedIn"
    """
    if not title:
        return {"name": "", "headline": "", "company": ""}
    # Drop the trailing "| LinkedIn" (or "- LinkedIn")
    cleaned = re.split(r"\s*[|\-]\s*linkedin\b", title, flags=re.IGNORECASE)[0].strip()
    parts = [p.strip() for p in cleaned.split(" - ") if p.strip()]
    name = parts[0] if parts else ""
    headline = parts[1] if len(parts) > 1 else ""
    company = parts[2] if len(parts) > 2 else ""
    return {"name": name, "headline": headline, "company": company}


class LinkedInIdentityProvider:
    """SerpAPI Google-search LinkedIn lookup with name-match filtering."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SERPAPI_KEY", "")
        self.session = requests.Session()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    # ── Name-match filter — "is this actually the user?" ────────────────────────

    @staticmethod
    def _name_matches(query_name: str, result_name: str) -> float:
        """Return a 0..1 match score between the searched name and a result's name.

        Requires the first-name token to match, then scores by token overlap.
        Returns 0.0 when the first name doesn't match (definitely not them).
        """
        q = _tokens(query_name)
        r = _tokens(result_name)
        if not q or not r:
            return 0.0
        # First name must be present in the result name.
        if q[0] not in r:
            return 0.0
        overlap = sum(1 for t in q if t in r)
        return overlap / len(q)

    # ── Search ──────────────────────────────────────────────────────────────────

    def search_candidates(
        self, full_name: str, location: Optional[str] = None, limit: int = 5
    ) -> List[ProfileCandidate]:
        """Google-search LinkedIn for a name, filtered to confident matches only."""
        if not self.is_configured:
            logger.info("SerpAPI not configured — skipping LinkedIn search.")
            return []

        name = (full_name or "").strip()
        if not name:
            return []

        query = f'"{name}" site:linkedin.com/in'
        if location:
            query += f" {location}"

        try:
            resp = self.session.get(
                _ENDPOINT,
                params={
                    "engine": "google", "q": query,
                    "gl": "in", "hl": "en", "num": "10",
                    "api_key": self.api_key,
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("SerpAPI LinkedIn search failed: %s", e)
            return []

        candidates: List[ProfileCandidate] = []
        for result in data.get("organic_results", []):
            link = result.get("link", "")
            if "linkedin.com/in/" not in link:
                continue
            parsed = _parse_title(result.get("title", ""))
            score = self._name_matches(name, parsed["name"])
            if score < _NAME_MATCH_THRESHOLD:
                # Filtered out — not confidently the same person.
                logger.debug("Filtered LinkedIn result (score %.2f): %s", score, parsed["name"])
                continue
            snippet = result.get("snippet", "")
            candidates.append(
                ProfileCandidate(
                    full_name=parsed["name"] or name,
                    headline=parsed["headline"],
                    current_company=parsed["company"],
                    location=self._guess_location(snippet),
                    linkedin_url=link.split("?")[0],
                    snippet=snippet,
                    match_score=round(score, 2),
                    target_roles=parsed["headline"],
                )
            )

        # Best match first.
        candidates.sort(key=lambda c: c.match_score, reverse=True)
        return candidates[:limit]

    def find_by_name(
        self, full_name: str, location: Optional[str] = None, company_domain: Optional[str] = None
    ) -> Optional[ProfileCandidate]:
        """Return the single best-matching candidate, or None if no confident match."""
        candidates = self.search_candidates(full_name, location=location)
        return candidates[0] if candidates else None

    def get_profile(self, linkedin_url: str) -> Optional[ProfileCandidate]:
        """Best-effort profile from a LinkedIn URL via a targeted Google search.

        Google search can't return structured profile data, so this returns a
        lightweight candidate from the public title/snippet, or None.
        """
        if not self.is_configured or not linkedin_url:
            return None
        try:
            resp = self.session.get(
                _ENDPOINT,
                params={
                    "engine": "google", "q": linkedin_url,
                    "gl": "in", "hl": "en", "num": "3", "api_key": self.api_key,
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("SerpAPI profile fetch failed: %s", e)
            return None

        for result in data.get("organic_results", []):
            if linkedin_url.split("?")[0] in result.get("link", ""):
                parsed = _parse_title(result.get("title", ""))
                return ProfileCandidate(
                    full_name=parsed["name"],
                    headline=parsed["headline"],
                    current_company=parsed["company"],
                    linkedin_url=linkedin_url,
                    snippet=result.get("snippet", ""),
                    target_roles=parsed["headline"],
                )
        return None

    @staticmethod
    def _guess_location(snippet: str) -> str:
        """Best-effort: pull an Indian city from the snippet if present."""
        if not snippet:
            return ""
        cities = ["Bengaluru", "Bangalore", "Chennai", "Mumbai", "Hyderabad", "Pune",
                  "Delhi", "Gurgaon", "Gurugram", "Noida", "Kolkata", "Ahmedabad"]
        for city in cities:
            if re.search(rf"\b{re.escape(city)}\b", snippet, re.IGNORECASE):
                return city
        return ""
