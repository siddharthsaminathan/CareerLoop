"""
CareerLoop ScrapeGraph Adapter — Extraction engine for job URLs.

NOT discovery. This is called AFTER URLs are found by search.
Extracts structured job data from any job page URL.
"""

import os
import json
import logging
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract job posting details from this page. Return ONLY valid JSON:
{
  "title": "job title",
  "company": "company name",
  "location": "city, country",
  "apply_url": "direct application URL if found",
  "description": "full job description text",
  "skills": ["skill1", "skill2"],
  "salary": "salary range if mentioned",
  "work_mode": "remote/hybrid/onsite",
  "posted_at": "posting date if visible",
  "experience": "experience required"
}
If a field is not available, use empty string or empty list."""


class ScrapeGraphAdapter:
    """Extract structured job data from URLs using ScrapeGraphAI."""

    def __init__(self):
        self._available = None
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                from scrapegraphai.graphs import SmartScraperGraph
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def extract(self, url: str) -> Optional[dict]:
        """
        Extract job details from a URL.
        Returns dict with title, company, location, etc. or None on failure.
        """
        if not self.available:
            logger.warning("ScrapeGraphAI not installed")
            return None

        if not self.api_key:
            logger.warning("No DEEPSEEK_API_KEY for ScrapeGraphAI LLM")
            return None

        from scrapegraphai.graphs import SmartScraperGraph

        config = {
            "llm": {
                "api_key": self.api_key,
                "model": "deepseek/deepseek-chat",
                "base_url": self.base_url,
            },
            "headless": True,
        }

        try:
            scraper = SmartScraperGraph(
                prompt=EXTRACTION_PROMPT,
                source=url,
                config=config,
            )
            result = scraper.run()

            if isinstance(result, dict):
                result["_source_url"] = url
                result["_extraction_method"] = "scrapegraphai"
                return result
            else:
                logger.warning(f"ScrapeGraph returned non-dict: {type(result)}")
                return None

        except Exception as e:
            logger.warning(f"ScrapeGraph extraction failed for {url}: {e}")
            return None

    def extract_batch(self, urls: list[str], max_extract: int = 15) -> list[dict]:
        """Extract from multiple URLs. Returns list of successful extractions."""
        results = []
        for i, url in enumerate(urls[:max_extract]):
            logger.info(f"Extracting [{i+1}/{min(len(urls), max_extract)}]: {url}")
            data = self.extract(url)
            if data:
                results.append(data)
        return results
