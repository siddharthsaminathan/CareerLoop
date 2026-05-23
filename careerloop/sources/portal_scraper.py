"""
3-Layer portal scraper for JS-heavy career pages.

Layer 1 — Network interception  : captures XHR/fetch/JSON APIs during page load
Layer 2 — Rendered DOM extraction: parses JS-rendered HTML + iframes after networkidle
Layer 3 — Agentic navigation    : clicks "load more", scrolls, paginates

Single Playwright session per call — no repeated page loads.
Returns PortalScraperResult with discovered APIs + extracted jobs.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from careerloop.sources.api_interceptor import (
    DiscoveredAPI,
    _classify_url,
    _is_job_api_url,
)

logger = logging.getLogger(__name__)

# ── Selectors ─────────────────────────────────────────────────────────────────

JOB_CARD_SELECTORS = [
    # Generic class-based
    "[class*='job-card']",
    "[class*='job-listing']",
    "[class*='job-item']",
    "[class*='job-tile']",
    "[class*='career-card']",
    "[class*='position-card']",
    "[class*='opening-item']",
    "[class*='role-card']",
    "[class*='job-row']",
    "[class*='vacancy-item']",
    # ATS data attributes
    "[data-job-id]",
    "[data-requisition-id]",
    "[data-job]",
    "[data-automation='jobTitle']",       # Workday
    "[data-ph-at-id*='job']",             # Phenom
    # List/table-based
    "li[class*='job']",
    "li[class*='position']",
    "li[class*='opening']",
    "tr[class*='job']",
    "tr[data-row-id]",                     # SuccessFactors
    # iCIMS / keka / darwinbox
    ".iCIMS_JobsTable tr",
    "[class*='job-container']",
    "[class*='posting']",
]

TITLE_SELECTORS = [
    "h1", "h2", "h3", "h4",
    "[class*='job-title']", "[class*='position-title']", "[class*='role-title']",
    "[class*='title']", "[data-automation='jobTitle']",
    "a[href*='job']", "a[href*='career']", "a[href*='position']",
]

LOCATION_SELECTORS = [
    "[class*='location']", "[class*='city']", "[class*='place']",
    "[class*='office']", "[class*='region']",
    "address", "span[itemprop='addressLocality']",
]

LOAD_MORE_SELECTORS = [
    "button:has-text('Load More')",
    "button:has-text('Show More')",
    "button:has-text('View All Jobs')",
    "button:has-text('View All Openings')",
    "button:has-text('See All Jobs')",
    "a:has-text('Next')",
    "button:has-text('Next')",
    "button[aria-label*='next']",
    "[aria-label='Next page']",
    "[class*='pagination'] [class*='next']",
    "[class*='next-page']",
    "[class*='load-more']",
    "[class*='show-more']",
]

VIEW_JOBS_SELECTORS = [
    "a:has-text('View Jobs')",
    "a:has-text('See Jobs')",
    "a:has-text('Open Positions')",
    "a:has-text('All Openings')",
    "a:has-text('Explore Jobs')",
    "button:has-text('View Jobs')",
    "button:has-text('Browse Jobs')",
    "a:has-text('Join Us')",
    "a[href*='jobs']",
    "a[href*='careers/open']",
    "a[href*='careers/positions']",
]

# Signals that a frame src might contain job listings
FRAME_JOB_SIGNALS = [
    "jobs", "careers", "requisition", "posting", "positions",
    "greenhouse", "lever", "ashby", "successfactors", "taleo",
    "icims", "workday", "spire", "smartrecruiters",
]

INDIA_KEYWORDS = [
    "india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad",
    "chennai", "pune", "kolkata", "noida", "gurgaon", "gurugram",
    "remote", "hybrid",
]

WAIT_MS = 6000
NETWORKIDLE_TIMEOUT = 15000
TIMEOUT_MS = 30000
MAX_LOAD_MORE_CLICKS = 8
MIN_JOBS_THRESHOLD = 20   # L3 fires unless L2 already found 20+ jobs (catches infinite-scroll boards)


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class PortalScraperResult:
    career_page_url: str
    intercepted_apis: list = field(default_factory=list)   # list[DiscoveredAPI]
    raw_api_urls: list = field(default_factory=list)
    dom_jobs: list = field(default_factory=list)           # list[dict] from Layer 2
    agentive_jobs: list = field(default_factory=list)      # list[dict] from Layer 3
    layers_used: list = field(default_factory=list)        # ["api", "dom", "agentive"]
    elapsed_ms: int = 0

    @property
    def all_jobs(self) -> list[dict]:
        return self.dom_jobs + self.agentive_jobs

    @property
    def has_apis(self) -> bool:
        return bool(self.intercepted_apis)

    @property
    def has_jobs(self) -> bool:
        return bool(self.dom_jobs or self.agentive_jobs)


# ── DOM helpers ───────────────────────────────────────────────────────────────

def _extract_text(el, selectors: list[str]) -> str:
    for sel in selectors:
        found = el.select_one(sel)
        if found and found.get_text(strip=True):
            return found.get_text(strip=True)
    return el.get_text(separator=" ", strip=True)[:200]


def _is_india_location(text: str) -> bool:
    return any(kw in text.lower() for kw in INDIA_KEYWORDS)


def _extract_apply_url(el, base_url: str) -> str:
    link = el.find("a", href=True)
    if link:
        return urljoin(base_url, link["href"])
    return base_url


def _parse_job_cards(html: str, base_url: str, source_tag: str) -> list[dict]:
    """Parse job cards from rendered HTML using multiple CSS selectors."""
    soup = BeautifulSoup(html, "html.parser")
    seen_titles: set[str] = set()
    jobs = []

    for sel in JOB_CARD_SELECTORS:
        try:
            cards = soup.select(sel)
        except Exception:
            continue
        if not cards:
            continue

        for card in cards:
            title = _extract_text(card, TITLE_SELECTORS).strip()
            if not title or len(title) < 3 or len(title) > 200:
                continue
            if title in seen_titles:
                continue

            location_el = card.select_one(", ".join(LOCATION_SELECTORS))
            location = location_el.get_text(strip=True) if location_el else ""
            apply_url = _extract_apply_url(card, base_url)
            description = card.get_text(separator=" ", strip=True)[:500]

            seen_titles.add(title)
            jobs.append({
                "title": title,
                "location": location,
                "url": apply_url,
                "apply_url": apply_url,
                "description": description,
                "_source_layer": source_tag,
                "_source_type": "portal_dom",
            })

        if len(jobs) >= 3:
            # Found a working selector — no need to try more
            break

    return jobs


_UUID_HREF = re.compile(
    r"^/?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_JOB_HREF = re.compile(
    r"/(job|jobs|career|careers|opening|position|requisition|posting|vacancy)s?/",
    re.IGNORECASE,
)
_NAV_TAGS = {"nav", "header", "footer"}


def _extract_from_links(html: str, base_url: str, source_tag: str) -> list[dict]:
    """
    Fallback: grab all <a> tags whose href looks like an individual job posting.
    Handles:
    - Standard job paths  (/jobs/123, /careers/senior-engineer)
    - UUID paths (Skima ATS — /ab783fc3-f66c-4e73-8cd7-e3e272f3e4db)
    - Title text heuristics ("Role - Division - City" format)
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    jobs = []

    for a in soup.find_all("a", href=True):
        # Skip nav/header/footer links
        if any(p.name in _NAV_TAGS for p in a.parents):
            continue

        href = a["href"]
        full_url = urljoin(base_url, href)
        if full_url in seen:
            continue

        is_job_href = _JOB_HREF.search(full_url) or _UUID_HREF.match(href.lstrip("/"))
        if not is_job_href:
            continue

        raw_text = a.get_text(strip=True)
        if not raw_text or len(raw_text) < 5 or len(raw_text) > 300:
            continue

        # Skip nav-like labels
        if raw_text.lower() in ("apply", "view", "details", "read more", "learn more", "click here"):
            continue

        # Parse "Role - Division - City" format (Skima, Keka, custom)
        parts = [p.strip() for p in raw_text.split(" - ")]
        if len(parts) >= 2:
            title = " - ".join(parts[:-1])
            location_hint = parts[-1]
            location = location_hint if any(kw in location_hint.lower() for kw in INDIA_KEYWORDS) else ""
            if not location:
                # Try scanning sibling/parent text
                parent_text = a.parent.get_text(separator=" ", strip=True) if a.parent else ""
                for kw in INDIA_KEYWORDS:
                    if kw in parent_text.lower():
                        location = kw.title()
                        break
        else:
            title = raw_text
            parent_text = a.parent.get_text(separator=" ", strip=True) if a.parent else ""
            location = ""
            for kw in INDIA_KEYWORDS:
                if kw in parent_text.lower():
                    location = kw.title()
                    break

        seen.add(full_url)
        jobs.append({
            "title": title,
            "location": location,
            "url": full_url,
            "apply_url": full_url,
            "description": "",
            "_source_layer": source_tag,
            "_source_type": "portal_link",
        })

    return jobs


# ── Main class ─────────────────────────────────────────────────────────────────

class PortalScraper:
    """
    3-layer job extractor. Single browser session per call.
    Replace APIInterceptor in on_demand.py — this is a superset.
    """

    def scrape(self, career_url: str) -> PortalScraperResult:
        import time
        t0 = time.time()
        result = PortalScraperResult(career_page_url=career_url)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("[PortalScraper] Playwright not installed")
            return result

        captured_apis: dict[str, DiscoveredAPI] = {}
        raw_urls: list[str] = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                )
                page = context.new_page()

                # ── Layer 1: Network interception (runs during page load) ──────
                def on_response(response):
                    url = response.url
                    if not _is_job_api_url(url):
                        return
                    raw_urls.append(url)
                    api = _classify_url(url)
                    if api:
                        if api.platform not in captured_apis:
                            try:
                                ct = response.headers.get("content-type", "")
                                if "json" in ct:
                                    data = response.json()
                                    api.sample_data = data if isinstance(data, dict) else None
                            except Exception:
                                pass
                            captured_apis[api.platform] = api
                        return
                    # Generic custom JSON
                    if "json" in response.headers.get("content-type", ""):
                        try:
                            data = response.json()
                            items = None
                            if isinstance(data, list):
                                items = data
                            elif isinstance(data, dict):
                                for k in ["jobs", "results", "data", "items", "entities", "postings"]:
                                    if isinstance(data.get(k), list):
                                        items = data[k]
                                        break
                            if items and len(items) > 0:
                                sample = items[0] if isinstance(items[0], dict) else {}
                                if any(k in sample for k in ["title", "jobTitle", "name", "position"]):
                                    if "custom_json" not in captured_apis:
                                        captured_apis["custom_json"] = DiscoveredAPI(
                                            url=url, platform="custom_json",
                                            sample_data={"endpoint": url, "sample": sample},
                                            confidence=0.8,
                                        )
                        except Exception:
                            pass

                page.on("response", on_response)

                # Navigate
                try:
                    page.goto(career_url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
                    page.wait_for_timeout(WAIT_MS)
                except Exception as e:
                    logger.debug(f"[PortalScraper] Navigation error: {e}")

                result.intercepted_apis = list(captured_apis.values())
                result.raw_api_urls = raw_urls[:20]

                if result.intercepted_apis:
                    result.layers_used.append("api")
                    logger.info(
                        f"[PortalScraper] L1 {career_url} → "
                        f"{[a.platform for a in result.intercepted_apis]}"
                    )

                # ── Layer 2: Rendered DOM extraction ─────────────────────────
                dom_jobs = self._layer2_dom(page, career_url)
                if dom_jobs:
                    result.dom_jobs = dom_jobs
                    result.layers_used.append("dom")
                    logger.info(
                        f"[PortalScraper] L2 {career_url} → {len(dom_jobs)} DOM jobs"
                    )

                # ── Layer 3: Agentic navigation (only if L2 insufficient) ────
                if len(dom_jobs) < MIN_JOBS_THRESHOLD:
                    agentive_jobs = self._layer3_agentive(page, career_url)
                    if agentive_jobs:
                        result.agentive_jobs = agentive_jobs
                        result.layers_used.append("agentive")
                        logger.info(
                            f"[PortalScraper] L3 {career_url} → "
                            f"{len(agentive_jobs)} agentive jobs"
                        )

                browser.close()

        except Exception as e:
            logger.warning(f"[PortalScraper] Failed: {career_url}: {e}")

        result.elapsed_ms = int((time.time() - t0) * 1000)

        if not result.intercepted_apis and not result.has_jobs:
            logger.info(
                f"[PortalScraper] {career_url} → no signal "
                f"({len(result.raw_api_urls)} raw URLs)"
            )

        return result

    def _layer2_dom(self, page, base_url: str) -> list[dict]:
        """
        Layer 2: Extract jobs from fully rendered DOM.
        Also checks iframes and navigates to a 'View Jobs' link if needed.
        """
        jobs = []

        # Wait for JS to finish rendering
        try:
            page.wait_for_load_state("networkidle", timeout=NETWORKIDLE_TIMEOUT)
        except Exception:
            pass  # timeout OK — page may still have jobs

        # 2a. Main frame HTML
        try:
            html = page.content()
            jobs = _parse_job_cards(html, base_url, "l2_main")
            if not jobs:
                jobs = _extract_from_links(html, base_url, "l2_links")
        except Exception as e:
            logger.debug(f"[PortalScraper] L2 main frame error: {e}")

        if jobs:
            return jobs

        # 2b. Iframes — SuccessFactors, Taleo, iCIMS often embed inside iframes
        try:
            frames = page.frames[1:]  # skip main frame
            for frame in frames:
                try:
                    frame_url = frame.url
                    if not frame_url or frame_url == "about:blank":
                        continue
                    if not any(sig in frame_url.lower() for sig in FRAME_JOB_SIGNALS):
                        continue
                    frame_html = frame.content()
                    frame_jobs = _parse_job_cards(frame_html, frame_url, "l2_iframe")
                    if not frame_jobs:
                        frame_jobs = _extract_from_links(frame_html, frame_url, "l2_iframe_links")
                    jobs.extend(frame_jobs)
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"[PortalScraper] L2 iframe error: {e}")

        if jobs:
            return jobs

        # 2c. Try clicking a 'View Jobs' / 'Open Positions' link
        try:
            for sel in VIEW_JOBS_SELECTORS:
                try:
                    link = page.locator(sel).first
                    if link.count() > 0:
                        href = link.get_attribute("href")
                        if href:
                            target = urljoin(base_url, href)
                            page.goto(target, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
                            page.wait_for_load_state("networkidle", timeout=NETWORKIDLE_TIMEOUT)
                            html = page.content()
                            jobs = _parse_job_cards(html, target, "l2_view_jobs")
                            if not jobs:
                                jobs = _extract_from_links(html, target, "l2_view_jobs_links")
                            if jobs:
                                return jobs
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"[PortalScraper] L2 view-jobs click error: {e}")

        return jobs

    def _layer3_agentive(self, page, base_url: str) -> list[dict]:
        """
        Layer 3: Navigate, scroll, click 'Load More', paginate.
        Captures jobs from expanded DOM state.
        """
        jobs = []
        seen_titles: set[str] = set()

        def _snapshot_jobs(tag: str) -> list[dict]:
            try:
                html = page.content()
                new_jobs = _parse_job_cards(html, base_url, tag)
                if not new_jobs:
                    new_jobs = _extract_from_links(html, base_url, tag)
                fresh = [j for j in new_jobs if j["title"] not in seen_titles]
                for j in fresh:
                    seen_titles.add(j["title"])
                return fresh
            except Exception:
                return []

        # 3a. Scroll down to trigger lazy-loading / infinite scroll
        # Wait for network response after each scroll — not a fixed sleep
        try:
            prev_height = page.evaluate("document.body.scrollHeight")
            for scroll_round in range(6):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                # Wait for new content: either network goes idle or height changes
                try:
                    page.wait_for_function(
                        f"document.body.scrollHeight > {prev_height}",
                        timeout=3000,
                    )
                except Exception:
                    page.wait_for_timeout(1500)  # fallback: fixed wait
                new_height = page.evaluate("document.body.scrollHeight")
                fresh = _snapshot_jobs(f"l3_scroll_{scroll_round}")
                jobs.extend(fresh)
                if new_height == prev_height and not fresh:
                    break  # no new content loaded — stop scrolling
                prev_height = new_height
        except Exception as e:
            logger.debug(f"[PortalScraper] L3 scroll error: {e}")

        # 3b. Click 'Load More' / 'Show More' buttons up to MAX_LOAD_MORE_CLICKS times
        for _ in range(MAX_LOAD_MORE_CLICKS):
            clicked = False
            for sel in LOAD_MORE_SELECTORS:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        page.wait_for_timeout(2000)
                        fresh = _snapshot_jobs("l3_load_more")
                        jobs.extend(fresh)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                break  # No more buttons to click

        # 3c. Check for pagination — click through pages
        for page_num in range(2, 6):  # max 5 pages
            paginated = False
            for sel in [
                f"a:has-text('{page_num}')",
                "a[aria-label='Next page']",
                "button[aria-label='Go to next page']",
                "[class*='pagination'] a[rel='next']",
            ]:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        page.wait_for_load_state("networkidle", timeout=NETWORKIDLE_TIMEOUT)
                        fresh = _snapshot_jobs(f"l3_page{page_num}")
                        jobs.extend(fresh)
                        paginated = True
                        break
                except Exception:
                    continue
            if not paginated:
                break

        return jobs
