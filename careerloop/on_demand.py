"""
On-Demand Search — synchronous "find jobs for this role in this city, NOW".

Replaces the cron-only batch model. User types a role + city, gets top results
in under ~60 seconds. Uses:
1. RoleKeywordCache for query generation
2. CompanyTargeting for portal-side targeted scrape
3. SearchAdapter + JobSpyAdapter for board-side discovery
4. IndiaFitEngine for fast scoring
5. deduplicate_canonical for cross-source merge

Returns a small ranked list with full breakdown.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from careerloop.apply_route import deduplicate_canonical, resolve_apply_route
from careerloop.india_filter import filter_india_jobs
from careerloop.india_fit_engine import IndiaFitEngine
from careerloop.role_keywords import RoleKeywordCache
from careerloop.company_targeting import CompanyTargeting
from careerloop.role_similarity import RoleSimilarityFilter
from careerloop.sources.search_adapter import SearchAdapter
from careerloop.sources.jobspy_adapter import JobSpyAdapter
from careerloop.sources.scrapegraph_adapter import ScrapeGraphAdapter
from careerloop.sources.indeed_scraper import IndeedScraper
from careerloop.sources.api_interceptor import APIInterceptor
from careerloop.sources.portal_scraper import PortalScraper
from careerloop.models import URLType, classify_url_type
from careerloop.profile_manager import ProfileManager

logger = logging.getLogger(__name__)


@dataclass
class OnDemandResult:
    role: str
    city: str
    keywords_used: list = field(default_factory=list)
    targeted_companies: list = field(default_factory=list)
    candidate_count: int = 0
    after_dedup_count: int = 0
    ranked_jobs: list = field(default_factory=list)
    elapsed_seconds: float = 0.0
    notes: list = field(default_factory=list)


class OnDemandSearch:
    """Run a synchronous targeted discovery for one (role, city)."""

    def __init__(self, career_ops_root: str):
        self.root = career_ops_root
        self.profile = ProfileManager(career_ops_root)
        self.fit_engine = IndiaFitEngine(self.profile)
        self.keywords = RoleKeywordCache(career_ops_root)
        self.targeting = CompanyTargeting(career_ops_root)
        self.search = SearchAdapter()
        self.jobspy = JobSpyAdapter()
        self.scraper = ScrapeGraphAdapter()
        self._indeed = IndeedScraper()
        self._interceptor = APIInterceptor()   # kept for backward compat
        self._portal_scraper = PortalScraper()  # 3-layer replacement
        self._role_filter = RoleSimilarityFilter()
        self._ats = None
        self._portal = None

    def _get_ats(self):
        if self._ats is None:
            from careerloop.sources.ats_adapter import ATSAdapter
            self._ats = ATSAdapter()
        return self._ats

    def _get_portal(self):
        if self._portal is None:
            from careerloop.sources.company_portal_scraper import (
                CareerPageCrawler, JDSectionExtractor,
            )
            self._portal = (CareerPageCrawler(), JDSectionExtractor())
        return self._portal

    # ── Public API ────────────────────────────────────────────────────

    def run(
        self,
        role: str,
        city: str = "",
        max_results: int = 10,
        portal_companies: int = 20,
        include_boards: bool = True,
    ) -> OnDemandResult:
        """Run a targeted discovery pass. Returns top-N ranked jobs."""
        import time
        t0 = time.time()
        city = city or self.profile.location_city
        result = OnDemandResult(role=role, city=city)

        # 1. Dynamic keywords for this role
        kw_data = self.keywords.get(role, city)
        result.keywords_used = kw_data.get("keywords", [])[:10]
        queries = kw_data.get("search_queries", [])

        all_jobs: list[dict] = []

        # 2. Phase A — Employer discovery + portal scrape
        try:
            ranked_companies = self.targeting.top_n(
                function=role, city=city,
                n=portal_companies,
                min_function_probability=0.35,
            )
            # Phase A fallback: if DB has < 5 candidates, run live discovery
            if len(ranked_companies) < 5:
                result.notes.append("Phase A: sparse DB — running live employer discovery")
                ranked_companies = self._discover_and_rank(role, city, portal_companies)
            result.targeted_companies = [rc.company.name for rc in ranked_companies]
            portal_jobs = self._scrape_targeted_companies(ranked_companies)
            all_jobs.extend(portal_jobs)
        except Exception as e:
            result.notes.append(f"portal layer error: {e}")
            logger.warning(f"[OnDemand] Portal layer failed: {e}")

        # 3. Job boards (DDG + JobSpy) — bounded
        if include_boards and queries:
            try:
                board_jobs = self._board_search(queries[:6], role=role, city=city)
                all_jobs.extend(board_jobs)
            except Exception as e:
                result.notes.append(f"board search error: {e}")
                logger.warning(f"[OnDemand] Board search failed: {e}")

        result.candidate_count = len(all_jobs)

        # 4. India filter
        india_filtered, _ = filter_india_jobs(all_jobs)

        # Phase E — Role relevance filter (embedding similarity + profile rejection)
        relevant, rejected_count = self._role_filter.filter_jobs(
            india_filtered,
            target_role=role,
            target_functions=self.profile.target_functions or [],
            rejected_roles=self.profile.rejected_roles or [],
        )
        result.notes.append(f"role filter: {len(india_filtered)} → {len(relevant)} relevant ({rejected_count} rejected)")

        # 5. Canonical dedup
        deduped = deduplicate_canonical(relevant)
        for job in deduped:
            job["apply_route"] = resolve_apply_route(job)
        result.after_dedup_count = len(deduped)

        # 6. Score with IndiaFitEngine
        scored = self.fit_engine.score_jobs_batch(deduped)

        # 7. Trim to max_results
        result.ranked_jobs = scored[:max_results]
        result.elapsed_seconds = round(time.time() - t0, 2)
        return result

    # ── Internals ─────────────────────────────────────────────────────

    def _scrape_targeted_companies(self, ranked) -> list[dict]:
        from careerloop.sources.spireai_adapter import discover_workspace_id, fetch_jobs as spire_fetch
        ats = self._get_ats()
        crawler, extractor = self._get_portal()
        jobs: list[dict] = []
        for rc in ranked:
            company = rc.company
            try:
                if company.ats_provider not in ("unknown", "none", ""):
                    # Phase D — extract via known ATS adapter
                    ats_jobs = ats.fetch_jobs(
                        company.id, company.name,
                        company.ats_provider, company.ats_url,
                    )
                    for aj in ats_jobs:
                        d = aj.to_dict()
                        d["_source_type"] = aj.source
                        jobs.append(d)
                elif company.career_page_url:
                    # Phase B — find/confirm career page URL
                    career_url = company.career_page_url

                    # Try Spire AI first (fast, no Playwright)
                    ws_id = discover_workspace_id(career_url)
                    if ws_id:
                        spire_jobs = spire_fetch(ws_id, company.name, career_url)
                        jobs.extend(spire_jobs)
                        logger.info(f"[OnDemand] {company.name}: {len(spire_jobs)} via SpireAI")
                        continue

                    # Phases C+D — 3-layer portal scraper (single browser session)
                    portal_result = self._portal_scraper.scrape(career_url)

                    # Layer 1: structured API interception
                    if portal_result.intercepted_apis:
                        discovered = self._resolve_intercepted_apis(portal_result, company, ats)
                        if discovered:
                            jobs.extend(discovered)
                            platform = portal_result.intercepted_apis[0].platform
                            logger.info(f"[OnDemand] {company.name}: {len(discovered)} via L1 API ({platform})")
                            continue

                    # Layer 2+3: DOM + agentive jobs
                    if portal_result.has_jobs:
                        all_dom = portal_result.all_jobs
                        for j in all_dom:
                            j.setdefault("company", company.name)
                        jobs.extend(all_dom)
                        logger.info(
                            f"[OnDemand] {company.name}: {len(all_dom)} via "
                            f"L{'2+3' if portal_result.agentive_jobs else '2'} DOM "
                            f"(layers={portal_result.layers_used})"
                        )
                        continue

                    # Phase D final fallback — static HTML crawl (rarely needed now)
                    urls = crawler.crawl(career_url)
                    for url in urls[:10]:
                        try:
                            jd = extractor.extract(url)
                            if jd.extraction_confidence >= 0.6:
                                jobs.append({
                                    "title": jd.job_title,
                                    "company": company.name,
                                    "location": jd.location,
                                    "url": url,
                                    "apply_url": url,
                                    "url_type": URLType.INDIVIDUAL_JOB.value,
                                    "description": jd.raw_text,
                                    "role_summary": jd.role_summary,
                                    "responsibilities": jd.responsibilities,
                                    "requirements": jd.requirements,
                                    "benefits": jd.benefits,
                                    "extraction_confidence": jd.extraction_confidence,
                                    "_source_type": "company_portal",
                                })
                        except Exception:
                            pass
            except Exception as e:
                logger.debug(f"[OnDemand] {company.name}: {e}")
        return jobs

    def _resolve_intercepted_apis(self, interception, company, ats) -> list[dict]:
        """Phase C+D: given intercepted APIs, fetch jobs via the right adapter."""
        jobs = []
        # PortalScraperResult uses .intercepted_apis; InterceptionResult uses .apis
        api_list = getattr(interception, "intercepted_apis", None) or getattr(interception, "apis", [])
        for api in api_list:
            try:
                if api.platform in ("lever", "greenhouse", "ashby", "workday"):
                    # Build canonical ATS URL and fetch
                    ats_url = self._build_ats_url(api)
                    if ats_url:
                        ats_jobs = ats.fetch_jobs(company.id, company.name, api.platform, ats_url)
                        for aj in ats_jobs:
                            d = aj.to_dict()
                            d["_source_type"] = aj.source
                            jobs.append(d)
                        # Cache discovery in DB
                        self._update_company_ats(company.id, api.platform, ats_url)
                elif api.platform == "spireai":
                    from careerloop.sources.spireai_adapter import fetch_jobs as spire_fetch
                    ws_id = api.slug or ""
                    if not ws_id and api.sample_data:
                        ws_id = api.sample_data.get("workspaceId", "")
                    if ws_id:
                        jobs.extend(spire_fetch(ws_id, company.name, company.career_page_url or api.url))
                elif api.platform == "custom_json" and api.sample_data:
                    # Direct fetch of the discovered endpoint
                    endpoint = api.sample_data.get("endpoint", "")
                    if endpoint:
                        jobs.extend(self._fetch_custom_json(endpoint, company.name))
            except Exception as e:
                logger.debug(f"[OnDemand] intercept resolve {api.platform}: {e}")
        return jobs

    def _build_ats_url(self, api) -> Optional[str]:
        slug = api.slug
        if not slug:
            return None
        if api.platform == "lever":
            return f"https://api.lever.co/v0/postings/{slug}?mode=json"
        if api.platform == "greenhouse":
            return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        if api.platform == "ashby":
            return f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        return None

    def _update_company_ats(self, company_id: str, provider: str, ats_url: str):
        try:
            from careerloop.memory.connection import get_db_manager
            db = get_db_manager(self.root)
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE companies SET ats_provider=?, ats_url=? WHERE id=?",
                    [provider, ats_url, company_id],
                )
            logger.info(f"[OnDemand] Cached ATS discovery: {company_id} → {provider}")
        except Exception as e:
            logger.debug(f"[OnDemand] ATS cache write failed: {e}")

    def _fetch_custom_json(self, endpoint: str, company_name: str) -> list[dict]:
        import requests
        try:
            r = requests.get(endpoint, timeout=10,
                             headers={"User-Agent": "Mozilla/5.0"})
            if not r.ok:
                return []
            data = r.json()
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for k in ["jobs", "results", "data", "items", "entities", "postings"]:
                    if isinstance(data.get(k), list):
                        items = data[k]
                        break
            jobs = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("jobTitle") or item.get("name") or ""
                if not title:
                    continue
                locs = item.get("location") or item.get("locations") or ""
                if isinstance(locs, list):
                    locs = locs[0] if locs else ""
                if isinstance(locs, dict):
                    locs = locs.get("city") or locs.get("name") or ""
                jobs.append({
                    "title": title,
                    "company": company_name,
                    "location": str(locs),
                    "url": item.get("url") or item.get("apply_url") or endpoint,
                    "apply_url": item.get("apply_url") or item.get("url") or endpoint,
                    "description": item.get("description") or item.get("content") or "",
                    "_source_type": "custom_api",
                })
            return jobs
        except Exception as e:
            logger.debug(f"[OnDemand] custom JSON fetch failed: {e}")
            return []

    def _discover_and_rank(self, role: str, city: str, n: int):
        """Phase A fallback: run live company discovery when DB is sparse."""
        try:
            from careerloop.sources.company_discovery import CompanyDiscoveryEngine
            from careerloop.company_targeting import RankedCompany
            engine = CompanyDiscoveryEngine(self.root)
            discovered = engine.discover(city=city, function_hint=role, limit=n * 2)
            # After discovery, re-run targeting (DB now has new companies)
            return self.targeting.top_n(
                function=role, city=city, n=n,
                min_function_probability=0.25,
            )
        except Exception as e:
            logger.warning(f"[OnDemand] Phase A discovery failed: {e}")
            return []

    def _board_search(self, queries: list[str], role: str = "", city: str = "") -> list[dict]:
        # Reuse SearchAdapter's queries interface
        search_results = self.search.search_queries(queries) if hasattr(self.search, "search_queries") else self.search.search_all(
            [{"query": q, "city": "", "site": ""} for q in queries]
        )
        jobs: list[dict] = []
        for r in search_results:
            url = r.get("url", "")
            if not url:
                continue
            url_type = classify_url_type(url).value
            if url_type != URLType.INDIVIDUAL_JOB.value:
                continue
            # Try deep extraction: ScrapeGraph first, then Indeed for Indeed URLs
            data = self.scraper.extract(url) if self.scraper.available else None
            if not data and self._indeed.can_handle(url):
                data = self._indeed.extract(url)
            if data:
                extraction_method = data.get("_extraction_method", "scrapegraph")
                source_type = "scrapegraph" if extraction_method == "scrapegraphai" else "indeed_direct"
                jobs.append({
                    "title": data.get("title", r.get("title", "")),
                    "company": data.get("company", ""),
                    "location": data.get("location", ""),
                    "url": url,
                    "apply_url": data.get("apply_url", url),
                    "url_type": url_type,
                    "description": data.get("description", ""),
                    "skills": data.get("skills", []),
                    "salary": data.get("salary", ""),
                    "work_mode": data.get("work_mode", ""),
                    "_source_type": source_type,
                })
            else:
                jobs.append({
                    "title": r.get("title", ""),
                    "company": "",
                    "location": r.get("source_city", ""),
                    "url": url,
                    "url_type": url_type,
                    "description": r.get("snippet", ""),
                    "_source_type": "search",
                })

        # JobSpy as a parallel board source — pass role + city correctly
        try:
            jobspy_results = self.jobspy.search_from_queries([
                {"role": role, "city": city or "India", "query": q} for q in queries[:2]
            ])
            for r in jobspy_results:
                jobs.append({
                    "title": r.get("title", ""),
                    "company": r.get("company", ""),
                    "location": r.get("location", ""),
                    "url": r.get("url", ""),
                    "apply_url": r.get("url", ""),
                    "url_type": classify_url_type(r.get("url", "")).value,
                    "description": r.get("description", ""),
                    "_source_type": "jobspy",
                })
        except Exception as e:
            logger.debug(f"[OnDemand] JobSpy: {e}")

        return jobs


# ── CLI entry ────────────────────────────────────────────────────────────

def main():
    """Usage: python -m careerloop.on_demand "fashion buyer" "Mumbai" 10"""
    import sys
    if len(sys.argv) < 2:
        print('Usage: python -m careerloop.on_demand "<role>" [city] [max_results]')
        sys.exit(1)
    role = sys.argv[1]
    city = sys.argv[2] if len(sys.argv) > 2 else ""
    max_results = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    root = os.getcwd()
    od = OnDemandSearch(root)
    result = od.run(role, city, max_results=max_results)

    print(f"\nOn-demand search: {role} / {city}")
    print(f"Elapsed: {result.elapsed_seconds}s")
    print(f"Keywords: {', '.join(result.keywords_used)}")
    print(f"Targeted companies: {len(result.targeted_companies)} — {', '.join(result.targeted_companies[:5])}{'...' if len(result.targeted_companies) > 5 else ''}")
    print(f"Candidates: {result.candidate_count} → after dedup: {result.after_dedup_count}")
    if result.notes:
        for n in result.notes:
            print(f"  note: {n}")
    print(f"\nTop {len(result.ranked_jobs)} jobs:")
    for i, item in enumerate(result.ranked_jobs, 1):
        job = item["job"]
        print(f"  {i}. [{item['score']}/100] {job.get('company', '')} — {job.get('title', '')}")
        print(f"     {job.get('location', '')} | {job.get('apply_url') or job.get('url', '')}")


if __name__ == "__main__":
    main()
