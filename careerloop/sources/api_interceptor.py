"""
Phase C — Network/API Discovery.

Playwright renders a career page and intercepts all XHR/fetch/JSON responses.
Discovers hidden APIs: Greenhouse, Lever, Ashby, Workday, SpireAI, custom.
Returns structured endpoint records + sample job data.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Patterns that indicate a jobs/careers API response
JOB_URL_SIGNALS = [
    "jobs", "careers", "requisition", "posting", "positions",
    "vacancy", "vacancies", "openings", "hiring",
    "graphql", "api/v", "/v1/", "/v2/",
]

# Known platform fingerprints: (regex on URL, platform_name, slug_group)
PLATFORM_PATTERNS = [
    (re.compile(r"api\.lever\.co/v0/postings/([a-z0-9_-]+)"),        "lever",        1),
    (re.compile(r"boards\.greenhouse\.io.*for=([a-z0-9_-]+)"),                "greenhouse",   1),
    (re.compile(r"boards-api\.greenhouse\.io/v\d+/boards/([a-z0-9_-]+)"),   "greenhouse",   1),
    (re.compile(r"api\.ashbyhq\.com/posting-api/job-board/([a-z0-9_-]+)"), "ashby",  1),
    (re.compile(r"([a-z0-9_-]+)\.ashbyhq\.com"),                      "ashby",        1),
    (re.compile(r"([a-z0-9_-]+)\.wd\d+\.myworkdayjobs\.com"),         "workday",      1),
    (re.compile(r"io\.spire2grow\.com.*workspaceId=([A-Z0-9_-]+)"),   "spireai",      1),
    (re.compile(r"io\.spire2grow\.com/ies/v1/p/requisition"),          "spireai",      None),
    (re.compile(r"([a-z0-9_-]+)\.smartrecruiters\.com"),               "smartrecruiters", 1),
    (re.compile(r"api\.smartrecruiters\.com/v1/companies/([a-z0-9_-]+)"), "smartrecruiters", 1),
    (re.compile(r"([a-z0-9_-]+)\.successfactors\.(com|eu)"),           "successfactors", 1),
    (re.compile(r"taleo\.net/careersection"),                           "taleo",        None),
    (re.compile(r"icims\.com"),                                         "icims",        None),
    (re.compile(r"keka\.com/careers"),                                  "keka",         None),
    (re.compile(r"darwinbox\.com"),                                     "darwinbox",    None),
    (re.compile(r"skima-prod\.s3.*companies/logo/(\d+)_"),              "skima",        1),
    (re.compile(r"api\.skima\.ai"),                                     "skima",        None),
    (re.compile(r"skima-careers-frontend\.pages\.dev"),                 "skima",        None),
]


@dataclass
class DiscoveredAPI:
    url: str
    platform: str
    slug: Optional[str] = None
    sample_data: Optional[dict] = None
    confidence: float = 1.0


@dataclass
class InterceptionResult:
    career_page_url: str
    apis: list = field(default_factory=list)
    raw_api_urls: list = field(default_factory=list)
    elapsed_ms: int = 0


def _classify_url(url: str) -> Optional[DiscoveredAPI]:
    """Match URL against known platform patterns."""
    for pattern, platform, slug_group in PLATFORM_PATTERNS:
        m = pattern.search(url)
        if m:
            slug = m.group(slug_group) if slug_group and m.lastindex and slug_group <= m.lastindex else None
            return DiscoveredAPI(url=url, platform=platform, slug=slug)
    return None


def _is_job_api_url(url: str) -> bool:
    url_lower = url.lower()
    # Skip static assets, analytics, fonts, JS bundles
    skip_substr = [
        "google-analytics", "gtag", "/analytics", "fonts", ".css", ".woff",
        ".png", ".jpg", ".svg", ".ico", "firebase", "gstatic", "doubleclick",
        "facebook", "twitter", "linkedin.com/li/", "segment.io",
        "/_next/static/", "webpack", "hot-update",
    ]
    # Exact suffix checks (avoid .js matching .json)
    skip_suffix = (".js", ".ttf", ".otf", ".woff2", ".eot", ".map")
    if any(s in url_lower for s in skip_substr):
        return False
    if url_lower.split("?")[0].endswith(skip_suffix):
        return False
    return any(s in url_lower for s in JOB_URL_SIGNALS)


class APIInterceptor:
    """
    Given a career page URL, navigate with Playwright and capture
    all network responses that look like job API calls.
    Returns discovered API endpoints with platform classification.
    """

    WAIT_MS = 6000  # wait after page load for async requests to fire
    TIMEOUT_MS = 30000

    def intercept(self, career_page_url: str) -> InterceptionResult:
        import time
        t0 = time.time()
        result = InterceptionResult(career_page_url=career_page_url)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("[APIInterceptor] Playwright not installed")
            return result

        captured_apis: dict[str, DiscoveredAPI] = {}
        raw_urls: list[str] = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                def on_response(response):
                    url = response.url
                    if not _is_job_api_url(url):
                        return
                    raw_urls.append(url)

                    # Try to classify
                    api = _classify_url(url)
                    if api:
                        if api.platform not in captured_apis:
                            # Try to capture sample data from JSON responses
                            try:
                                ct = response.headers.get("content-type", "")
                                if "json" in ct:
                                    data = response.json()
                                    api.sample_data = data if isinstance(data, dict) else None
                            except Exception:
                                pass
                            captured_apis[api.platform] = api
                        return

                    # Unrecognized but looks like jobs API → capture as generic
                    if "json" in response.headers.get("content-type", ""):
                        try:
                            data = response.json()
                            # Heuristic: JSON with list of objects that have title-like keys
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
                                has_title = any(k in sample for k in ["title", "jobTitle", "name", "position"])
                                if has_title:
                                    parsed = urlparse(url)
                                    generic = DiscoveredAPI(
                                        url=url, platform="custom_json",
                                        sample_data={"endpoint": url, "sample": sample},
                                        confidence=0.8,
                                    )
                                    if "custom_json" not in captured_apis:
                                        captured_apis["custom_json"] = generic
                        except Exception:
                            pass

                page.on("response", on_response)

                try:
                    page.goto(career_page_url, timeout=self.TIMEOUT_MS, wait_until="domcontentloaded")
                    page.wait_for_timeout(self.WAIT_MS)
                except Exception as e:
                    logger.debug(f"[APIInterceptor] Navigation error for {career_page_url}: {e}")

                browser.close()

        except Exception as e:
            logger.warning(f"[APIInterceptor] Failed: {career_page_url}: {e}")

        result.apis = list(captured_apis.values())
        result.raw_api_urls = raw_urls[:20]
        result.elapsed_ms = int((time.time() - t0) * 1000)

        if result.apis:
            logger.info(f"[APIInterceptor] {career_page_url} → {[a.platform for a in result.apis]}")
        else:
            logger.info(f"[APIInterceptor] {career_page_url} → no APIs detected ({len(raw_urls)} raw signals)")

        return result
