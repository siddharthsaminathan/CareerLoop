"""
CareerLoop ScrapeGraph Adapter — LLM-powered extraction for job URLs.

Replaced scrapegraphai OSS dependency (broken: ChatOllama import error) with
direct Playwright fetch + DeepSeek extraction. Same output interface.

Architecture:
  1. Playwright fetches page (handles JS-heavy pages, SPAs)
  2. Fallback: requests for static pages
  3. DeepSeek extracts structured job data from cleaned HTML text
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract job posting details from this page text. Return ONLY valid JSON with these exact keys:
{
  "title": "job title",
  "company": "company name",
  "location": "city, country",
  "apply_url": "direct application URL if found",
  "description": "full job description text (verbatim from page)",
  "skills": ["skill1", "skill2"],
  "salary": "salary range if mentioned",
  "work_mode": "remote/hybrid/onsite",
  "posted_at": "posting date if visible",
  "experience": "experience required"
}
Use empty string or empty list for missing fields. Do NOT invent content."""

# Skip domains that block scrapers and waste time
_SKIP_DOMAINS = frozenset([
    "linkedin.com", "glassdoor.com", "ambitionbox.com",
])


def _clean_html(html: str) -> str:
    """Strip tags and collapse whitespace. Returns plain text."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&#?\w+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class ScrapeGraphAdapter:
    """
    LLM-powered job data extractor.
    Playwright fetch → DeepSeek extraction → structured dict.
    No scrapegraphai library required.
    """

    def __init__(self):
        self._available = None
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.model = os.getenv("CAREERLOOP_SCRAPE_MODEL", "deepseek-chat")

    @property
    def available(self) -> bool:
        """True if DeepSeek API key is present — no other deps required."""
        if self._available is None:
            self._available = bool(self.api_key)
        return self._available

    def extract(self, url: str) -> Optional[dict]:
        """
        Extract job details from a URL using Playwright + DeepSeek.
        Returns dict with title, company, location, description, etc. or None on failure.
        """
        if not self.available:
            logger.debug("[ScrapeGraph] No DEEPSEEK_API_KEY — skipping")
            return None

        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower().lstrip("www.")
        if any(skip in domain for skip in _SKIP_DOMAINS):
            logger.debug(f"[ScrapeGraph] Skipping blocked domain: {domain}")
            return None

        # 1. Fetch page content
        page_text = self._fetch_playwright(url) or self._fetch_requests(url)
        if not page_text or len(page_text) < 200:
            logger.debug(f"[ScrapeGraph] Could not fetch content from {url}")
            return None

        # Truncate to ~6000 chars to stay within token budget
        page_text = page_text[:6000]

        # 2. LLM extraction
        result = self._extract_with_llm(page_text, url)
        if result:
            result["_source_url"] = url
            result["_extraction_method"] = "scrapegraphai"  # keep tag for compatibility
        return result

    def extract_batch(self, urls: list[str], max_extract: int = 15) -> list[dict]:
        """Extract from multiple URLs. Returns list of successful extractions."""
        results = []
        for i, url in enumerate(urls[:max_extract]):
            logger.info(f"[ScrapeGraph] Extracting [{i+1}/{min(len(urls), max_extract)}]: {url}")
            data = self.extract(url)
            if data:
                results.append(data)
        return results

    # ── Fetch methods ──────────────────────────────────────────────────

    def _fetch_playwright(self, url: str) -> Optional[str]:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                page.set_extra_http_headers({
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
                    )
                })
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()
                return _clean_html(html)
        except Exception as e:
            logger.debug(f"[ScrapeGraph] Playwright fetch failed for {url}: {e}")
            return None

    def _fetch_requests(self, url: str) -> Optional[str]:
        try:
            import requests
            resp = requests.get(
                url, timeout=12,
                headers={"User-Agent": "Mozilla/5.0 (compatible; CareerLoopBot/1.0)"},
                allow_redirects=True,
            )
            if resp.ok and "text/html" in resp.headers.get("content-type", ""):
                return _clean_html(resp.text)
        except Exception as e:
            logger.debug(f"[ScrapeGraph] requests fetch failed for {url}: {e}")
        return None

    # ── LLM extraction ─────────────────────────────────────────────────

    def _extract_with_llm(self, page_text: str, url: str) -> Optional[dict]:
        import requests as req

        prompt = f"{EXTRACTION_PROMPT}\n\nPAGE TEXT:\n{page_text}"

        try:
            resp = req.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 1000,
                },
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

            # Parse JSON from response
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"[ScrapeGraph] LLM extraction failed for {url}: {e}")

        return None
