"""LinkedIn profile lookup for interactive onboarding.

DEPRECATED SHAPE — this module previously returned hardcoded mock profiles,
which violated the LOCKED no-mock / no-hardcoded rules. It now delegates to the
real SerpAPI-backed LinkedInIdentityProvider (careerloop/sources/identity_provider.py).

When SERPAPI_KEY is not configured, lookups return empty results (NOT fabricated
data) and the onboarding flow falls back to CV-first.
"""

import logging
from typing import Any, Dict, List

from careerloop.sources.identity_provider import LinkedInIdentityProvider

logger = logging.getLogger("careerloop.sources.linkedin_scraper")


class LinkedInScraper:
    """Thin compatibility wrapper over the real LinkedInIdentityProvider."""

    def __init__(self, serpapi_key: str = None):
        self.client = LinkedInIdentityProvider(api_key=serpapi_key)

    def search_profiles(self, name: str) -> List[Dict[str, Any]]:
        """Return matching LinkedIn profiles for a name. Empty list if none/unconfigured."""
        if not self.client.is_configured:
            logger.info("LinkedIn lookup unconfigured — returning no candidates.")
            return []
        candidate = self.client.find_by_name(name)
        if not candidate:
            return []
        card = candidate.to_card()
        card["snippet"] = candidate.headline
        return [card]

    def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """Return structured profile fields for a LinkedIn URL. Empty dict if unavailable."""
        candidate = self.client.get_profile(profile_url)
        if not candidate:
            return {}
        return {
            "full_name": candidate.full_name,
            "target_roles": candidate.target_roles,
            "target_cities": candidate.target_cities,
            "cv_content": candidate.cv_content,
        }
