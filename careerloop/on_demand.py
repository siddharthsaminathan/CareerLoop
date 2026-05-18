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
from careerloop.sources.search_adapter import SearchAdapter
from careerloop.sources.jobspy_adapter import JobSpyAdapter
from careerloop.sources.scrapegraph_adapter import ScrapeGraphAdapter
from careerloop.sources.indeed_scraper import IndeedScraper
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

        # 2. Targeted company portals (employer-first path)
        try:
            ranked_companies = self.targeting.top_n(
                function=role, city=city,
                n=portal_companies,
                min_function_probability=0.35,
            )
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

        # 4b. Role relevance prefilter
        role_tokens = set(role.lower().split())
        # Collect first-word signals from target_functions (not all tokens — avoids "manager" pollution)
        # e.g. "category manager fashion" → only "category", "fashion buyer" → "fashion"
        tf_head_tokens = set()
        # Generic business words that appear in almost every job title — exclude from domain signals
        _generic = {"with", "and", "for", "the", "that", "from", "into", "this", "your",
                    "manager", "senior", "associate", "lead", "head", "director", "specialist",
                    "analyst", "executive", "officer", "coordinator", "consultant", "principal"}
        for fn in (self.profile.target_functions or []):
            words = fn.lower().split()
            tf_head_tokens.update(w for w in words if len(w) >= 4 and w not in _generic)
        # role_signal: the search role tokens + domain words from profile functions
        role_signal = role_tokens | tf_head_tokens

        rejected_role_terms = {r.lower() for r in (self.profile.rejected_roles or [])}

        def _title_relevant(job: dict) -> bool:
            title = job.get("title", "").lower()
            title_tokens = set(title.split())

            # Profile-driven rejection
            for reject in rejected_role_terms:
                if reject in title:
                    return False

            # For "engineer" roles: tighten so we don't match QA/hardware/manufacturing engineers.
            if "engineer" in title_tokens and "engineer" in role_tokens:
                eng_qualifier = role_tokens - {"engineer"}
                generic_sw = {"software", "data", "platform", "backend", "frontend",
                              "fullstack", "full-stack", "sre", "cloud", "mobile"}
                if eng_qualifier and not (title_tokens & (eng_qualifier | generic_sw)):
                    return False

            # Title must overlap with the actual search role tokens first.
            # This is the primary signal — derived purely from the search query.
            if title_tokens & role_tokens:
                return True
            # Broader domain match from profile target_functions (domain-specific words only)
            return bool(title_tokens & tf_head_tokens)

        relevant = [j for j in india_filtered if _title_relevant(j)]
        result.notes.append(f"role filter: {len(india_filtered)} → {len(relevant)} relevant")

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
                    ats_jobs = ats.fetch_jobs(
                        company.id, company.name,
                        company.ats_provider, company.ats_url,
                    )
                    for aj in ats_jobs:
                        d = aj.to_dict()
                        d["_source_type"] = aj.source
                        jobs.append(d)
                elif company.career_page_url:
                    # Try Spire AI first (used by Myntra and other Indian companies)
                    ws_id = discover_workspace_id(company.career_page_url)
                    if ws_id:
                        spire_jobs = spire_fetch(ws_id, company.name, company.career_page_url)
                        jobs.extend(spire_jobs)
                        logger.info(f"[OnDemand] {company.name}: {len(spire_jobs)} jobs via SpireAI")
                    else:
                        # Fallback: crawl career page + extract JDs
                        urls = crawler.crawl(company.career_page_url)
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
