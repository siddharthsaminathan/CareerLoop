"""
CareerLoop Company Portal Scraper — Career page crawler + JD section extractor.

Two responsibilities:
1. CareerPageCrawler: given a company's careers URL, find all individual job listing URLs.
2. JDSectionExtractor: given a single job page URL, extract verbatim 3-section JD.

Hard rule: NEVER invent or paraphrase JD content.
If extraction confidence < 0.6, the job is flagged — not shown with a fabricated description.
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
MIN_JD_LENGTH = 200
MIN_CONFIDENCE_THRESHOLD = 0.6

# Career page path suffixes to probe when /careers doesn't exist
CAREER_PAGE_PATHS = [
    "/careers", "/jobs", "/work-with-us", "/join-us", "/join",
    "/open-roles", "/openings", "/about/careers", "/en/careers",
    "/company/careers", "/hiring", "/work-here",
]

# Anchors/link text that signal individual job listings
JOB_LINK_SIGNALS = [
    "apply", "view job", "learn more", "see details", "read more",
    "view position", "view opening", "job details",
]

# Paths/URL patterns that indicate individual job postings (not category pages)
JOB_URL_PATTERNS = [
    r"/careers?/[a-z0-9][a-z0-9_-]{3,}/?$",       # /careers/senior-ml-engineer
    r"/jobs?/[a-z0-9][a-z0-9_-]{3,}/?$",           # /jobs/data-scientist-bangalore
    r"/openings?/[a-z0-9][a-z0-9_-]{3,}/?$",
    r"/roles?/[a-z0-9][a-z0-9_-]{3,}/?$",
    r"/positions?/[a-z0-9][a-z0-9_-]{3,}/?$",
    r"/careers?/.*\d{4,}",                          # URL with numeric ID
    r"/jobs?/.*\d{4,}",
]

# Patterns that indicate a page is NOT an individual job (category/search)
NOT_JOB_PATTERNS = [
    r"/careers?/?$",           # bare /careers root
    r"/jobs?/?$",
    r"/careers?/department/",
    r"/careers?/location/",
    r"/careers?/team/",
    r"/careers?/category/",
    r"\?(?:department|team|location|filter|page|q)=",
]

INDIA_CITY_KEYWORDS = [
    "india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad",
    "chennai", "pune", "kolkata", "noida", "gurgaon", "gurugram",
    "remote", "hybrid",
]


def _strip_html(html: str) -> str:
    """Remove HTML tags, decode common entities, collapse whitespace."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<nav[^>]*>.*?</nav>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<footer[^>]*>.*?</footer>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<header[^>]*>.*?</header>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#?\w+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_india_location(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in INDIA_CITY_KEYWORDS)


def _is_job_url(url: str, base_domain: str) -> bool:
    """True if URL looks like an individual job posting on the same domain."""
    parsed = urlparse(url.lower())
    if base_domain not in parsed.netloc:
        return False
    path = parsed.path
    if any(re.search(p, path) for p in NOT_JOB_PATTERNS):
        return False
    if any(re.search(p, url.lower()) for p in JOB_URL_PATTERNS):
        return True
    return False


# ── Career Page Crawler ───────────────────────────────────────────────

class CareerPageCrawler:
    """
    Given a company's career page URL, extract all individual job listing URLs.
    Uses requests + BeautifulSoup. Falls back to Playwright for JS-heavy pages.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

    def find_career_page(self, domain: str) -> Optional[str]:
        """
        Find careers URL: Playwright click-nav first (handles JS sites),
        static HEAD probing as fallback.
        """
        # Try Playwright click-nav — renders JS homepage and finds careers link
        result = self._find_via_playwright(domain)
        if result:
            return result

        # Fallback: static HEAD probing for static sites
        base = f"https://{domain}"
        for path in CAREER_PAGE_PATHS:
            url = base + path
            try:
                resp = self.session.head(url, timeout=8, allow_redirects=True)
                if resp.status_code == 200:
                    logger.info(f"[CareerPage] Found (static): {url}")
                    return url
            except Exception:
                continue
        return None

    def _find_via_playwright(self, domain: str) -> Optional[str]:
        """
        Open company homepage with Playwright, score all candidate career links,
        return highest-scoring match (not first match).
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None

        SOCIAL = frozenset(["linkedin.com", "twitter.com", "facebook.com",
                            "instagram.com", "youtube.com", "glassdoor.com"])
        homepage = f"https://{domain}"
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                page.set_extra_http_headers({"User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
                )})
                page.goto(homepage, timeout=15000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

                candidates: list[tuple[int, str]] = []  # (score, url)

                links = page.query_selector_all("a[href]")
                for link in links:
                    try:
                        text = (link.inner_text() or "").strip().lower()
                        href = link.get_attribute("href") or ""
                        href_lower = href.lower()
                        full = urljoin(homepage, href)

                        # Skip: social, off-domain, anchors, mailto
                        if any(s in full for s in SOCIAL):
                            continue
                        if not full.startswith("http"):
                            continue
                        if domain not in full:
                            continue

                        score = self._score_career_link(text, href_lower)
                        if score > 0:
                            candidates.append((score, full))
                    except Exception:
                        continue

                browser.close()

                if not candidates:
                    return None

                # Return highest-scoring link
                candidates.sort(key=lambda x: x[0], reverse=True)
                best_score, best_url = candidates[0]
                logger.info(f"[CareerPage] Found via Playwright (score={best_score}): {best_url}")
                return best_url

        except Exception as e:
            logger.debug(f"[CareerPage] Playwright find_career_page failed for {domain}: {e}")
        return None

    @staticmethod
    def _score_career_link(text: str, href_lower: str) -> int:
        """
        Score a candidate career link. Higher = more likely to be the careers page.
        Returns 0 if not a career link at all.
        """
        score = 0

        # Exact path matches (highest confidence)
        if "/careers" in href_lower:
            score += 10
        elif "/jobs" in href_lower:
            score += 9
        elif "/work-with-us" in href_lower or "/work_with_us" in href_lower:
            score += 8
        elif "/join-us" in href_lower or "/join_us" in href_lower:
            score += 7
        elif "/hiring" in href_lower:
            score += 7
        elif "/openings" in href_lower:
            score += 7
        elif "/open-positions" in href_lower or "/open_positions" in href_lower:
            score += 8
        elif "/opportunities" in href_lower:
            score += 6

        # Text label matches
        if text in ("careers", "jobs"):
            score += 5
        elif "careers" in text or "join us" in text:
            score += 4
        elif "open positions" in text or "open roles" in text:
            score += 4
        elif "work with us" in text or "we're hiring" in text:
            score += 3
        elif "jobs" in text or "hiring" in text or "openings" in text:
            score += 2

        return score

    def crawl(self, career_page_url: str) -> list[str]:
        """
        Fetch career page and extract all individual job listing URLs.
        Returns deduplicated list.
        """
        parsed = urlparse(career_page_url.lower())
        base_domain = parsed.netloc

        html = self._fetch_html(career_page_url)
        if not html:
            logger.warning(f"[CareerPage] Could not fetch {career_page_url}")
            return []

        job_urls = self._extract_job_urls(html, career_page_url, base_domain)

        # If nothing found with static fetch, try Playwright
        if not job_urls:
            job_urls = self._crawl_playwright(career_page_url, base_domain)

        logger.info(f"[CareerPage] {career_page_url} → {len(job_urls)} job URLs")
        return job_urls

    def _fetch_html(self, url: str) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            logger.debug(f"[CareerPage] Static fetch failed: {e}")
        return None

    def _extract_job_urls(self, html: str, base_url: str, base_domain: str) -> list[str]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("[CareerPage] BeautifulSoup not installed — install beautifulsoup4")
            return []

        soup = BeautifulSoup(html, "html.parser")
        found = set()

        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            if not href or href.startswith("#") or href.startswith("mailto:"):
                continue

            full_url = urljoin(base_url, href)
            if _is_job_url(full_url, base_domain):
                found.add(full_url)
                continue

            # Also check anchor text for job signals
            link_text = tag.get_text(strip=True).lower()
            if any(s in link_text for s in JOB_LINK_SIGNALS):
                if urlparse(full_url.lower()).netloc == base_domain:
                    found.add(full_url)

        return list(found)

    def _crawl_playwright(self, url: str, base_domain: str) -> list[str]:
        """Playwright fallback for JS-rendered career pages."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.debug("[CareerPage] Playwright not available for JS-heavy page")
            return []

        found = set()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                page.set_extra_http_headers({"User-Agent": self.session.headers["User-Agent"]})
                page.goto(url, wait_until="networkidle", timeout=20000)
                time.sleep(2)

                links = page.query_selector_all("a[href]")
                for link in links:
                    href = link.get_attribute("href") or ""
                    full_url = urljoin(url, href)
                    if _is_job_url(full_url, base_domain):
                        found.add(full_url)

                browser.close()
        except Exception as e:
            logger.warning(f"[CareerPage] Playwright failed: {e}")

        return list(found)


# ── JD Section Extractor ──────────────────────────────────────────────

@dataclass
class JDSections:
    role_summary: str = ""        # opening: what the role is, team context
    responsibilities: str = ""   # what you'll do
    requirements: str = ""       # must-have skills, qualifications
    benefits: str = ""           # compensation, perks (may be empty)
    raw_text: str = ""           # full page text — always kept
    job_title: str = ""
    company_name: str = ""
    location: str = ""
    source_url: str = ""
    extraction_confidence: float = 0.0


class JDSectionExtractor:
    """
    Scrapes a single job posting URL and extracts 3 structured sections verbatim.

    Hard rules:
    - ONLY use text present on the page. Never paraphrase or invent.
    - If confidence < MIN_CONFIDENCE_THRESHOLD, return with low confidence flagged.
    - raw_text is always populated so the caller can validate.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self._llm = None  # lazy init

    def _get_llm(self):
        if self._llm is None:
            from careerloop.council.llm import CouncilLLMClient
            self._llm = CouncilLLMClient("extraction")
        return self._llm

    def extract(self, url: str) -> JDSections:
        """
        Fetch URL and extract structured JD sections.
        Returns JDSections with extraction_confidence set.
        """
        result = JDSections(source_url=url)

        html = self._fetch(url)
        if not html:
            # Try Playwright for JS-heavy pages
            html = self._fetch_playwright(url)

        if not html:
            result.extraction_confidence = 0.0
            return result

        raw_text = _strip_html(html)
        result.raw_text = raw_text

        if len(raw_text.strip()) < MIN_JD_LENGTH:
            result.extraction_confidence = 0.0
            return result

        # Try heuristic section split first (fast, no LLM cost)
        heuristic = self._heuristic_extract(raw_text)
        heuristic_confidence = self._score_confidence(heuristic, raw_text)

        if heuristic_confidence >= 0.75:
            result.role_summary = heuristic["role_summary"]
            result.responsibilities = heuristic["responsibilities"]
            result.requirements = heuristic["requirements"]
            result.benefits = heuristic["benefits"]
            result.extraction_confidence = heuristic_confidence
            self._extract_metadata(result, raw_text, html)
            return result

        # LLM extraction for complex layouts
        llm_sections = self._llm_extract(raw_text)
        if llm_sections:
            llm_confidence = self._score_confidence(llm_sections, raw_text)
            result.role_summary = llm_sections.get("role_summary", "")
            result.responsibilities = llm_sections.get("responsibilities", "")
            result.requirements = llm_sections.get("requirements", "")
            result.benefits = llm_sections.get("benefits", "")
            result.extraction_confidence = llm_confidence
        else:
            # Last resort: entire cleaned text as role_summary
            result.role_summary = raw_text[:3000]
            result.extraction_confidence = 0.4

        self._extract_metadata(result, raw_text, html)
        return result

    def _fetch(self, url: str) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            logger.debug(f"[JDExtract] Static fetch failed for {url}: {e}")
        return None

    def _fetch_playwright(self, url: str) -> Optional[str]:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=20000)
                time.sleep(1)
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            logger.debug(f"[JDExtract] Playwright fallback failed: {e}")
        return None

    def _heuristic_extract(self, raw_text: str) -> dict:
        """Fast section split without LLM."""
        from careerloop.sources.ats_adapter import _split_jd_sections
        return _split_jd_sections(raw_text)

    def _llm_extract(self, raw_text: str) -> Optional[dict]:
        """
        LLM-based section extraction.
        Strict prompt: only use text present in input, no paraphrasing.
        """
        import json

        # Truncate to avoid token overflow — real JDs are < 3000 words
        text_truncated = raw_text[:6000]

        system = (
            "You are a job description parser. Your ONLY task is to extract text "
            "that is LITERALLY PRESENT in the input. You must NOT paraphrase, summarize, "
            "or invent any content. If a section does not exist in the input, return an empty string. "
            "Never add skills, responsibilities, or requirements that are not explicitly stated."
        )
        prompt = f"""Extract the job description sections from the text below.

RULES:
1. Only use text verbatim from the INPUT TEXT. Do not rephrase or improve it.
2. role_summary = the opening paragraphs describing the role, team, and company context.
3. responsibilities = the "What you'll do" / "Key responsibilities" section text.
4. requirements = the "What you need" / "Requirements" / "Qualifications" section text.
5. benefits = the "What we offer" / "Benefits" / "Perks" section text.
6. If a section is not present in the input, return "" for that key.
7. Do NOT invent any content not present in the input.

INPUT TEXT:
{text_truncated}

Return valid JSON only with keys: role_summary, responsibilities, requirements, benefits"""

        try:
            llm = self._get_llm()
            response = llm.call(system, prompt)
            # Parse JSON from response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"[JDExtract] LLM extraction failed: {e}")

        return None

    def _score_confidence(self, sections: dict, raw_text: str) -> float:
        """
        Anti-hallucination check: what fraction of extracted text came from raw_text?
        Confidence = overlap ratio.
        """
        extracted = " ".join(sections.values()).strip()
        if not extracted:
            return 0.0
        if len(extracted) < MIN_JD_LENGTH:
            return 0.2

        # Sample 10-word n-grams from extracted text and check presence in raw
        words = extracted.split()
        if len(words) < 10:
            return 0.5

        n = 10
        ngrams = [" ".join(words[i:i+n]) for i in range(0, len(words) - n, n)]
        if not ngrams:
            return 0.5

        raw_lower = raw_text.lower()
        hits = sum(1 for ng in ngrams if ng.lower() in raw_lower)
        confidence = hits / len(ngrams)

        # Bonus if sections are reasonably sized
        if len(sections.get("responsibilities", "")) > 100:
            confidence = min(1.0, confidence + 0.1)
        if len(sections.get("requirements", "")) > 100:
            confidence = min(1.0, confidence + 0.1)

        return round(confidence, 2)

    def _extract_metadata(self, result: JDSections, raw_text: str, html: str):
        """Extract job title, company name, and location from page metadata."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            title_tag = soup.find("h1") or soup.find("title")
            if title_tag:
                result.job_title = title_tag.get_text(strip=True)[:200]

            # Location: look for common patterns
            loc_match = re.search(
                r"(?:location|based in|office)\s*:?\s*([A-Za-z ,/]+(?:India|Bangalore|Mumbai|Delhi|Hyderabad|Chennai|Pune)[A-Za-z ,/]*)",
                raw_text, re.IGNORECASE
            )
            if loc_match:
                result.location = loc_match.group(1).strip()[:100]

        except Exception:
            pass
