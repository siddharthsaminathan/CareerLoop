"""
CareerLoop Search Adapter — Free search layer for India job URLs.

Uses DuckDuckGo (free, no API key) as primary.
Input: search queries from RoleStrategyGenerator
Output: candidate job URLs for extraction
"""

import re
import time
import logging
from urllib.parse import urlparse

from careerloop.models import CandidateURL, SearchResult, URLType, VerificationOutcome, classify_url_type

logger = logging.getLogger(__name__)

# India-native job board URL patterns — ONLY these pass through.
# All non-India ATS boards (greenhouse, lever, etc.) are explicitly rejected.
INDIA_JOB_URL_PATTERNS = [
    r"linkedin\.com/jobs/view/\d+",          # individual job posting only (numeric ID required)
    r"linkedin\.com/jobs/collections/\d+",   # curated collection (numeric ID required)
    r"naukri\.com/job-listings-",
    r"naukri\.com/job/",
    r"cutshort\.io/[^/]+/jobs/",             # company-specific job: cutshort.io/{company}/jobs/{slug}
    r"cutshort\.io/jobs/[a-z0-9-]+-[a-z0-9]+$",  # individual job slug (ends with ID, not /jobs/)
    r"instahyre\.com/",
    r"wellfound\.com/jobs",
    r"wellfound\.com/l/",
    r"hirist\.tech/",
    r"iimjobs\.com/",
    r"foundit\.in/",
    r"workindia\.in/",
    r"apna\.co/",
    r"shine\.com/",
]

# URL patterns that look like job URLs but are actually search/category pages — reject these.
SEARCH_PAGE_PATTERNS = [
    # LinkedIn search result pages (not individual job posts)
    r"linkedin\.com/jobs/[a-z][a-z0-9-]+-jobs",      # /jobs/ai-engineer-jobs-in-bangalore
    r"linkedin\.com/jobs/search",                      # /jobs/search?keywords=...
    r"linkedin\.com/jobs/[a-z][a-z0-9-]+-openings",   # /jobs/data-science-openings
    # Naukri search/listing pages (not individual job posts)
    r"naukri\.com/[a-z][a-z0-9-]+-jobs(?:-in-[a-z-]+)?/?$",  # /ml-engineer-jobs or /ml-jobs-in-bangalore
    r"naukri\.com/[a-z][a-z0-9-]+-jobs/[0-9]",        # paginated: /ml-jobs/2
    # Cutshort category pages
    r"cutshort\.io/jobs/?$",                           # /jobs/ root = category listing
    r"cutshort\.io/jobs/[a-z][a-z0-9-]+/?$",          # /jobs/machine-learning = category
    # Foundit/Instahyre/Hirist category listings
    r"foundit\.in/srp/",                               # search results page
    r"instahyre\.com/search",
    r"hirist\.tech/c/",                                # category page
    # Blog / article / advice patterns
    r"/(blog|article|news|guide|tips|career-advice|how-to|interview-prep)/",
    r"highest[- ]paying[- ]jobs",
    r"how[- ]to[- ]become",
    r"top[- ]\d+[- ]jobs",
    r"best[- ]jobs[- ]for",
    r"salary[- ](?:guide|range|report)",
]

# India-native job board domains (fallback domain check)
INDIA_JOB_DOMAINS = [
    "naukri.com",
    "cutshort.io",
    "instahyre.com",
    "hirist.tech",
    "iimjobs.com",
    "foundit.in",
    "workindia.in",
    "apna.co",
    "shine.com",
]

# LinkedIn jobs are allowed but only the /jobs/view/ path (not company pages etc.)
LINKEDIN_JOBS_DOMAINS = ["linkedin.com"]

# Domains to always skip — non-India ATS boards, news, social, etc.
SKIP_DOMAINS = [
    # Non-India ATS boards — these surface global/US/EU jobs
    "greenhouse.io",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "lever.co",
    "jobs.lever.co",
    "ashbyhq.com",
    "jobs.ashbyhq.com",
    "workable.com",
    "apply.workable.com",
    "myworkdayjobs.com",
    "icims.com",
    "taleo.net",
    "smartrecruiters.com",
    "bamboohr.com",
    "jobvite.com",
    "recruitee.com",
    "indeed.com",       # Global, not India-specific
    "glassdoor.com",
    "monster.com",
    "ziprecruiter.com",
    "remotive.com",
    "weworkremotely.com",
    "remoteok.com",
    "wellfound.com/company",  # Company pages, not job listings
    # Social / news / review sites
    "youtube.com", "wikipedia.org", "quora.com", "reddit.com",
    "facebook.com", "twitter.com", "x.com", "medium.com",
    "glassdoor.com/Reviews", "glassdoor.com/Salaries",
    "ambitionbox.com", "payscale.com",
]


class SearchAdapter:
    """Free search layer for discovering India job URLs."""

    def __init__(self, max_results_per_query: int = 10, delay_seconds: float = 2.0):
        self.max_results = max_results_per_query
        self.delay = delay_seconds

    def search_all(self, queries: list[dict]) -> list[dict]:
        """Run all queries, return candidate job URL dicts."""
        all_results = []
        seen_urls = set()

        for i, q in enumerate(queries):
            query_str = q["query"]
            logger.info(f"Search [{i+1}/{len(queries)}]: {query_str}")

            try:
                results = self._search_google(query_str)
                if not results:
                    logger.info("Google Search returned 0 organic hits, trying DDG fallback...")
                    results = self._search_ddg(query_str)
            except Exception as e:
                logger.warning(f"Google Search failed for '{query_str}', trying DDG: {e}")
                try:
                    results = self._search_ddg(query_str)
                except Exception as ex:
                    logger.warning(f"DDG fallback also failed: {ex}")
                    results = []

            for r in results:
                url = r.get("url", "")
                if not url or url in seen_urls:
                    continue
                url_type = classify_url_type(url)
                if url_type == URLType.BLOG_ARTICLE:
                    continue
                if not self._is_job_url(url):
                    continue
                if self._is_skip_domain(url):
                    continue

                seen_urls.add(url)
                search_result = SearchResult(
                    url=url,
                    title=r.get("title", ""),
                    snippet=r.get("snippet", ""),
                    source_query=query_str,
                    source_role=q.get("role", ""),
                    source_city=q.get("city", ""),
                    source_site=q.get("site", ""),
                    search_engine=r.get("engine", "google"),
                )
                outcome = VerificationOutcome.VERIFIED_MAYBE.value
                reason = "classified candidate URL"
                if url_type in (URLType.SEARCH_PAGE, URLType.CATEGORY_PAGE, URLType.COMPANY_CAREERS_PAGE):
                    outcome = VerificationOutcome.NEEDS_MORE_DATA.value
                    reason = "discovery lead only"
                candidate = CandidateURL(
                    **search_result.to_dict(),
                    url_type=url_type.value,
                    verification_outcome=outcome,
                    reason=reason,
                )
                all_results.append(candidate.to_dict())

            if i < len(queries) - 1:
                time.sleep(self.delay)

        logger.info(f"Total candidate URLs: {len(all_results)}")
        return all_results

    def _search_google(self, query: str) -> list[dict]:
        """Scrape Google Search organic results directly."""
        import requests
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("BeautifulSoup4 not installed, skipping Google Search scraping")
            return []

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        url = f"https://www.google.com/search?q={query}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []
        except Exception as e:
            logger.warning(f"Google request failed: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # Find standard organic search block containers
        for g in soup.find_all("div", class_="g"):
            link_tag = g.find("a")
            if not link_tag or not link_tag.has_attr("href"):
                continue
            href = link_tag["href"]
            if not href.startswith("http"):
                continue

            title_tag = g.find("h3")
            title = title_tag.text if title_tag else ""

            snippet_tag = g.find("div", class_="VwiC3b") or g.find("div", style=lambda v: v and "line-clamp" in v)
            snippet = snippet_tag.text if snippet_tag else ""

            results.append({
                "url": href,
                "title": title,
                "snippet": snippet,
                "engine": "google",
            })

        # Fallback if standard classes aren't present
        if not results:
            for a in soup.find_all("a"):
                href = a.get("href", "")
                if href.startswith("http") and not "google.com" in href:
                    h3 = a.find("h3")
                    if h3:
                        results.append({
                            "url": href,
                            "title": h3.text,
                            "snippet": "",
                            "engine": "google",
                        })

        return results

    def _search_ddg(self, query: str) -> list[dict]:
        """Search using DuckDuckGo (free) via the ddgs library."""
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=self.max_results, region="in-en"))
        return [{"url": r.get("href",""), "title": r.get("title",""), "snippet": r.get("body",""), "engine": "duckduckgo"} for r in results]

    def _is_search_page(self, url: str) -> bool:
        """Return True if URL is a search/category page, not an individual job posting."""
        url_lower = url.lower()
        for p in SEARCH_PAGE_PATTERNS:
            if re.search(p, url_lower):
                return True
        return False

    def _is_job_url(self, url: str) -> bool:
        """Only allow individual job posting URLs from India-native job boards."""
        url_lower = url.lower()
        from urllib.parse import urlparse
        parsed = urlparse(url_lower)
        netloc = parsed.netloc

        # Reject search/category pages first — must come before pattern matching
        if self._is_search_page(url_lower):
            return False

        url_type = classify_url_type(url)
        if url_type == URLType.INDIVIDUAL_JOB:
            return True
        # Allow discovery leads but not pure search pages
        if url_type in (URLType.COMPANY_CAREERS_PAGE,):
            return True

        if "linkedin.com" in netloc:
            # Only numeric-ID job view pages, not search pages
            return bool(re.search(r"/jobs/view/\d+", url_lower))

        # Wellfound: only job listings, not company profile pages
        if "wellfound.com" in netloc:
            return "/jobs" in url_lower or "/l/" in url_lower

        # India-specific board URL patterns (already tightened above)
        for p in INDIA_JOB_URL_PATTERNS:
            if re.search(p, url_lower):
                return True

        # India-specific board domains (fallback)
        for d in INDIA_JOB_DOMAINS:
            if d in netloc:
                return True

        return False

    def _is_skip_domain(self, url: str) -> bool:
        url_lower = url.lower()
        return any(d in url_lower for d in SKIP_DOMAINS)
