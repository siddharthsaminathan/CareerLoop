"""
CareerLoop Discovery — India Job Discovery & Verification Engine.

Architecture:
  Profile → Role Queries → Free Search (DDG) → Candidate URLs
  → ScrapeGraphAI Extract → India Filter → Verify Active
  → Dedupe/Merge → Score → Verified Shortlist

No ATS-first. No paid APIs. No fake fallbacks.
"""

import csv
import os
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from careerloop.models import JobPosting, SourceType, URLType, VerificationOutcome, classify_url_type
from careerloop.role_strategy import RoleStrategyGenerator
from careerloop.sources.search_adapter import SearchAdapter
from careerloop.sources.scrapegraph_adapter import ScrapeGraphAdapter
from careerloop.sources.jobspy_adapter import JobSpyAdapter
from careerloop.india_filter import filter_india_jobs
from careerloop.verification import JobVerifier
from careerloop.apply_route import merge_cross_source, resolve_apply_route, deduplicate_canonical

logger = logging.getLogger(__name__)


class DiscoveryEngine:
    """
    India Job Discovery & Verification Engine.

    Sources (in priority order):
    1. Free search (DuckDuckGo) → site-scoped queries → candidate URLs
    2. JobSpy multi-board search (LinkedIn, Indeed, Glassdoor)
    3. CSV imports — manual fallback/import path
    4. ScrapeGraphAI — enrichment/extraction (NOT discovery)

    ATS APIs are NOT used for primary discovery.
    """

    def __init__(self, career_ops_root: str):
        self.root = Path(career_ops_root)
        self.import_dir = self.root / "data" / "imports" / "jobs"
        self.import_dir.mkdir(parents=True, exist_ok=True)

        self.search = SearchAdapter()
        self.scraper = ScrapeGraphAdapter()
        self.jobspy = JobSpyAdapter()
        self.verifier = JobVerifier()
        self._ats_adapter = None      # lazy — avoid import cost when portal discovery off
        self._portal_scraper = None

    # ── Main Discovery Pipeline ────────────────────────────────────

    def discover_india_jobs(self, profile: dict, date: str = None) -> dict:
        """
        Full India job discovery pipeline.

        Returns:
        {
            "queries": [...],
            "search_results": [...],
            "extracted_jobs": [...],
            "india_jobs": [...],
            "rejected_jobs": [...],
            "verified_jobs": [...],
            "final_shortlist": [...],
            "source_stats": {...},
        }
        """
        report = {
            "queries": [],
            "search_results": [],
            "jobspy_results": [],
            "candidate_urls": [],
            "discovery_leads": [],
            "extracted_jobs": [],
            "india_jobs": [],
            "rejected_jobs": [],
            "verified_jobs": [],
            "unverified_jobs": [],
            "verified_job_postings": [],
            "scored_jobs": [],
            "user_visible_opportunities": [],
            "final_shortlist": [],
            "source_stats": {},
        }

        # Step 1: Generate search queries from profile
        strategy = RoleStrategyGenerator(profile)
        queries = strategy.generate_queries()
        report["queries"] = queries
        logger.info(f"Generated {len(queries)} search queries")

        all_candidate_jobs = []

        # Step 2a: Free search → candidate URLs
        search_results = self.search.search_all(queries)
        report["search_results"] = search_results
        report["candidate_urls"] = search_results
        report["source_stats"]["ddg_urls"] = len(search_results)
        logger.info(f"DDG search found {len(search_results)} candidate URLs")

        report["source_stats"]["raw_search_results_count"] = len(search_results)
        report["source_stats"]["rejected_noise_count"] = len([
            r for r in search_results
            if r.get("verification_outcome") == VerificationOutcome.NOISE.value
            or r.get("url_type") == URLType.BLOG_ARTICLE.value
        ])
        report["source_stats"]["search_category_pages_count"] = len([
            r for r in search_results
            if r.get("url_type") in (URLType.SEARCH_PAGE.value, URLType.CATEGORY_PAGE.value)
        ])

        # Step 2b: JobSpy multi-board search
        try:
            jobspy_results = self.jobspy.search_from_queries(queries)
            report["jobspy_results"] = jobspy_results
            report["source_stats"]["jobspy_jobs"] = len(jobspy_results)
            logger.info(f"JobSpy found {len(jobspy_results)} jobs")
        except Exception as e:
            logger.warning(f"JobSpy failed: {e}")
            report["source_stats"]["jobspy_jobs"] = 0
            jobspy_results = []

        # Step 2c: CSV imports (fallback)
        csv_jobs = self._discover_csv(date)
        report["source_stats"]["csv_imports"] = len(csv_jobs)

        # Step 3: Extract structured data from search URLs using ScrapeGraphAI
        # IMPORTANT: India filter runs AFTER extraction so we use the REAL scraped
        # location, not the fake query city passed by the search adapter.
        extracted = []
        scorable_search_results = []
        discovery_leads = []
        rejected_noise = []
        for r in search_results:
            url_type = r.get("url_type") or classify_url_type(r.get("url", "")).value
            r["url_type"] = url_type
            if url_type == URLType.BLOG_ARTICLE.value:
                r["verification_outcome"] = VerificationOutcome.NOISE.value
                r["reason"] = "blog/article rejected from scoring"
                rejected_noise.append(r)
            elif url_type in (URLType.SEARCH_PAGE.value, URLType.CATEGORY_PAGE.value, URLType.COMPANY_CAREERS_PAGE.value):
                r["verification_outcome"] = VerificationOutcome.NEEDS_MORE_DATA.value
                r["reason"] = "discovery lead only"
                discovery_leads.append(r)
            elif url_type == URLType.INDIVIDUAL_JOB.value:
                scorable_search_results.append(r)
            else:
                r["verification_outcome"] = VerificationOutcome.NEEDS_MORE_DATA.value
                r["reason"] = "unknown URL shape"
                discovery_leads.append(r)

        report["discovery_leads"] = discovery_leads
        report["rejected_jobs"].extend(rejected_noise)
        report["source_stats"]["rejected_noise_count"] = len(rejected_noise)
        report["source_stats"]["search_category_pages_count"] = len([
            r for r in discovery_leads
            if r.get("url_type") in (URLType.SEARCH_PAGE.value, URLType.CATEGORY_PAGE.value)
        ])

        if scorable_search_results and self.scraper.available:
            logger.info(f"ScrapeGraphAI active. Processing up to 15 individual job URLs...")
            for i, r in enumerate(scorable_search_results[:15]):
                url = r["url"]
                logger.info(f"Deep Extraction [{i+1}/{min(len(scorable_search_results), 15)}]: {url}")
                data = self.scraper.extract(url)
                if data:
                    extracted.append(data)
                    job = self._extraction_to_job(data)
                    if job:
                        job["_search_query"] = r.get("source_query", "")
                        job["url_type"] = r.get("url_type", URLType.INDIVIDUAL_JOB.value)
                        if not job.get("location"):
                            job["location"] = self._infer_location_from_url(url)
                        # Filter here — real location now available from extraction
                        if self._is_scorable_job_dict(job):
                            india_jobs_single, _ = filter_india_jobs([self._job_to_filter_dict(job)])
                        else:
                            india_jobs_single = []
                            job["verification_outcome"] = VerificationOutcome.NEEDS_MORE_DATA.value
                            report["discovery_leads"].append(job)
                        if india_jobs_single:
                            job["verification_outcome"] = VerificationOutcome.VERIFIED_MAYBE.value
                            all_candidate_jobs.append(job)
                        else:
                            logger.info(f"Rejected post-extraction (non-India): {job.get('location', '')} — {url}")
                else:
                    # Fallback: use search snippet metadata
                    # These have no real location, so apply a strict URL-based filter only.
                    job = self._search_result_to_job(r)
                    if job:
                        job["verification_outcome"] = VerificationOutcome.NEEDS_MORE_DATA.value
                        report["discovery_leads"].append(job)

            # Remaining search results beyond 15 — basic metadata fallback
            for r in scorable_search_results[15:]:
                job = self._search_result_to_job(r)
                if job:
                    job["verification_outcome"] = VerificationOutcome.NEEDS_MORE_DATA.value
                    report["discovery_leads"].append(job)
        else:
            logger.info("ScrapeGraphAI unavailable or 0 search hits. Using basic search metadata mapping.")
            for r in scorable_search_results:
                job = self._search_result_to_job(r)
                if job:
                    job["verification_outcome"] = VerificationOutcome.NEEDS_MORE_DATA.value
                    report["discovery_leads"].append(job)

        report["extracted_jobs"] = extracted
        report["source_stats"]["scrapegraph_extracted"] = len(extracted)

        # Add JobSpy results — these have real locations from the board scraper
        for r in jobspy_results:
            job = self._jobspy_to_job(r)
            if job:
                if self._is_scorable_job_dict(job):
                    india_jobs_single, _ = filter_india_jobs([self._job_to_filter_dict(job)])
                else:
                    india_jobs_single = []
                    job["verification_outcome"] = VerificationOutcome.NEEDS_MORE_DATA.value
                    report["discovery_leads"].append(job)
                if india_jobs_single:
                    job["verification_outcome"] = VerificationOutcome.VERIFIED_MAYBE.value
                    all_candidate_jobs.append(job)

        # Add CSV imports — always trusted as manually curated India jobs
        for job in csv_jobs:
            if self._is_scorable_job_dict(job):
                job["verification_outcome"] = VerificationOutcome.VERIFIED_MAYBE.value
                all_candidate_jobs.append(job)
            else:
                job["verification_outcome"] = VerificationOutcome.NEEDS_MORE_DATA.value
                report["discovery_leads"].append(job)

        # Step 2d: Company portal / ATS direct discovery
        # Gated by CAREERLOOP_PORTAL_DISCOVERY=1 to avoid unwanted HTTP calls.
        if os.getenv("CAREERLOOP_PORTAL_DISCOVERY", "0") == "1":
            portal_jobs = self._discover_company_portal(profile)
            report["source_stats"]["portal_jobs"] = len(portal_jobs)
            logger.info(f"Company portal layer found {len(portal_jobs)} jobs")
            for job in portal_jobs:
                if self._is_scorable_job_dict(job):
                    job["verification_outcome"] = VerificationOutcome.VERIFIED_MAYBE.value
                    all_candidate_jobs.append(job)
                else:
                    job["verification_outcome"] = VerificationOutcome.NEEDS_MORE_DATA.value
                    report["discovery_leads"].append(job)
        else:
            report["source_stats"]["portal_jobs"] = 0

        logger.info(f"Total India-verified candidate jobs: {len(all_candidate_jobs)}")

        # Step 4: Final pass to collect filter stats (all jobs already filtered above)
        india_jobs = [self._job_to_filter_dict(j) for j in all_candidate_jobs]
        rejected_count = (
            len(search_results) + len(jobspy_results)
            - len(india_jobs)  # approximate
        )
        report["india_jobs"] = india_jobs
        report["source_stats"]["india_passed"] = len(india_jobs)
        report["source_stats"]["india_rejected"] = max(0, rejected_count)

        # Step 5: Cross-source canonical dedup (sha256 fingerprint, source priority)
        merged = deduplicate_canonical(india_jobs)
        report["source_stats"]["after_merge"] = len(merged)

        # Step 6: Verify active
        max_v = int(os.getenv("MAX_VERIFY_JOBS", 100))
        verified_all = self.verifier.verify_batch(merged, max_verify=max_v)
        verified_active = self.verifier.get_verified_active(verified_all)
        unverified = [j for j in verified_all if j.get("verification_status") != "VERIFIED_ACTIVE"]

        for job in verified_active:
            job["verification_outcome"] = VerificationOutcome.VERIFIED_STRONG.value
        for job in unverified:
            job["verification_outcome"] = VerificationOutcome.REJECTED.value

        report["verified_jobs"] = verified_active
        report["unverified_jobs"] = unverified
        report["source_stats"]["verified_active"] = len(verified_active)
        report["source_stats"]["verified_jobs_count"] = len(verified_active)
        report["source_stats"]["unverified"] = len(unverified)

        # Step 7: Convert to JobPosting objects for scorer
        final = []
        for job_dict in verified_active:
            posting = self._dict_to_job_posting(job_dict)
            final.append(posting)

        report["verified_job_postings"] = final
        report["source_stats"]["final_count"] = len(final)
        report["source_stats"]["final_user_visible_opportunities"] = 0

        return report

    # ── Company Portal / ATS Layer ────────────────────────────────

    def _get_ats_adapter(self):
        if self._ats_adapter is None:
            from careerloop.sources.ats_adapter import ATSAdapter
            self._ats_adapter = ATSAdapter()
        return self._ats_adapter

    def _get_portal_scraper(self):
        if self._portal_scraper is None:
            from careerloop.sources.company_portal_scraper import CareerPageCrawler, JDSectionExtractor
            self._portal_scraper = (CareerPageCrawler(), JDSectionExtractor())
        return self._portal_scraper

    def _discover_company_portal(self, profile: dict, max_companies: int = 30) -> list[dict]:
        """
        Discover jobs from company career pages and ATS APIs.

        Flow:
        1. Pull companies from registry for the profile city/sector.
        2. If registry < 10, trigger CompanyDiscoveryEngine to populate it.
        3. For each company: ATS API first, then career page crawl + JD extraction.
        4. Return list of job dicts in the standard pipeline format.
        """
        try:
            from careerloop.company_registry import CompanyRegistry
            registry = CompanyRegistry(str(self.root))
        except Exception as e:
            logger.warning(f"[PortalLayer] Registry unavailable: {e}")
            return []

        city = profile.get("location", profile.get("city", ""))
        sector = profile.get("target_sector", "")
        function_hint = profile.get("target_role", profile.get("target_roles", [""])[0] if isinstance(profile.get("target_roles"), list) else "")

        companies = registry.list_by_city_sector(
            city=city, sector=sector,
            crawl_status=["pending", "active", "warm"],
            limit=max_companies,
        )

        # Seed registry if thin
        if len(companies) < 10 and city:
            try:
                from careerloop.sources.company_discovery import CompanyDiscoveryEngine
                engine = CompanyDiscoveryEngine(str(self.root))
                discovered = engine.discover(
                    city=city, sector=sector,
                    function_hint=str(function_hint),
                    max_companies=50,
                )
                logger.info(f"[PortalLayer] Discovery seeded {len(discovered)} companies for {city}")
                companies = registry.list_by_city_sector(
                    city=city, sector=sector,
                    crawl_status=["pending", "active", "warm"],
                    limit=max_companies,
                )
            except Exception as e:
                logger.warning(f"[PortalLayer] Discovery seed failed: {e}")

        ats = self._get_ats_adapter()
        crawler, extractor = self._get_portal_scraper()
        jobs: list[dict] = []

        for company in companies[:max_companies]:
            try:
                if company.ats_provider not in ("unknown", "none", ""):
                    # Structured ATS fetch — highest fidelity
                    ats_jobs = ats.fetch_jobs(
                        company.id, company.name,
                        company.ats_provider, company.ats_url,
                    )
                    for aj in ats_jobs:
                        jobs.append(self._ats_job_to_dict(aj))
                    registry.mark_crawled(company.id, len(ats_jobs))

                elif company.career_page_url:
                    # Career page crawl → per-URL JD extraction
                    job_urls = crawler.crawl(company.career_page_url)
                    for url in job_urls[:20]:  # cap per-company to 20
                        try:
                            jd = extractor.extract(url)
                            if jd.extraction_confidence >= 0.6:
                                jobs.append(self._portal_job_to_dict(jd, company.name, url))
                        except Exception:
                            pass
                    registry.mark_crawled(company.id, len(job_urls))

            except Exception as e:
                logger.debug(f"[PortalLayer] {company.name}: {e}")

        logger.info(f"[PortalLayer] {len(companies)} companies → {len(jobs)} jobs")
        return jobs

    def _ats_job_to_dict(self, ats_job) -> dict:
        return {
            "title": ats_job.title,
            "company": ats_job.company,
            "location": ats_job.location,
            "url": ats_job.apply_url,
            "apply_url": ats_job.apply_url,
            "url_type": URLType.INDIVIDUAL_JOB.value,
            "description": ats_job.raw_description,
            "jd_text": ats_job.raw_description,
            "role_summary": ats_job.role_summary,
            "responsibilities": ats_job.responsibilities,
            "requirements": ats_job.requirements,
            "benefits": ats_job.benefits,
            "skills": [],
            "salary": "",
            "work_mode": "",
            "posted_at": ats_job.posted_at or "",
            "_source_type": ats_job.source,
            "extraction_confidence": ats_job.jd_confidence,
        }

    def _portal_job_to_dict(self, jd_sections, company_name: str, source_url: str) -> dict:
        return {
            "title": jd_sections.job_title,
            "company": company_name,
            "location": jd_sections.location,
            "url": source_url,
            "apply_url": source_url,
            "url_type": URLType.INDIVIDUAL_JOB.value,
            "description": jd_sections.raw_text,
            "jd_text": jd_sections.raw_text,
            "role_summary": jd_sections.role_summary,
            "responsibilities": jd_sections.responsibilities,
            "requirements": jd_sections.requirements,
            "benefits": jd_sections.benefits,
            "skills": [],
            "salary": "",
            "work_mode": "",
            "posted_at": "",
            "_source_type": "company_portal",
            "extraction_confidence": jd_sections.extraction_confidence,
        }

    # ── CSV Import (fallback) ──────────────────────────────────────

    def _discover_csv(self, date: str = None) -> list[dict]:
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        csv_path = self.import_dir / f"{date}.csv"
        if not csv_path.exists():
            return []
        jobs = []
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                jobs.append({
                    "source": row.get("source", "csv_import"),
                    "url": row.get("url", ""),
                    "company": row.get("company", ""),
                    "title": row.get("role", ""),
                    "location": row.get("location", ""),
                    "description": row.get("description", ""),
                    "work_mode": row.get("work_mode", ""),
                    "salary": row.get("salary_range", ""),
                    "posted_at": row.get("posted_at", ""),
                    "skills": [s.strip() for s in row.get("skills_required", "").split(",") if s.strip()],
                    "_source_type": "csv",
                })
        return jobs

    # ── Conversion helpers ─────────────────────────────────────────

    def _extraction_to_job(self, data: dict) -> Optional[dict]:
        """Convert ScrapeGraphAI extraction to job dict."""
        if not data:
            return None
        return {
            "title": data.get("title", ""),
            "company": data.get("company", ""),
            "location": data.get("location", "") or self._infer_location_from_url(data.get("_source_url", data.get("apply_url", ""))),
            "url": data.get("_source_url", data.get("apply_url", "")),
            "apply_url": data.get("apply_url", ""),
            "description": data.get("description", ""),
            "jd_text": data.get("description", ""),
            "skills": data.get("skills", []),
            "salary": data.get("salary", ""),
            "work_mode": data.get("work_mode", ""),
            "posted_at": data.get("posted_at", ""),
            "_source_type": "scrapegraph",
        }

    def _search_result_to_job(self, result: dict) -> Optional[dict]:
        """Convert raw search result to basic job dict."""
        title = result.get("title", "")
        if not title:
            return None
        return {
            "title": title,
            "company": "",
            "location": result.get("source_city", ""),
            "url": result.get("url", ""),
            "url_type": result.get("url_type", classify_url_type(result.get("url", "")).value),
            "description": result.get("snippet", ""),
            "jd_text": "",
            "skills": [],
            "salary": "",
            "work_mode": "",
            "posted_at": "",
            "_source_type": "search",
            "_search_query": result.get("source_query", ""),
        }

    def _jobspy_to_job(self, result: dict) -> Optional[dict]:
        """Convert JobSpy result to job dict."""
        return {
            "title": result.get("title", ""),
            "company": result.get("company", ""),
            "location": result.get("location", ""),
            "url": result.get("url", ""),
            "url_type": classify_url_type(result.get("url", "")).value,
            "apply_url": result.get("url", ""),
            "description": result.get("description", ""),
            "jd_text": result.get("description", ""),
            "skills": [],
            "salary": result.get("salary", ""),
            "work_mode": "remote" if "True" in str(result.get("work_mode", "")) else "",
            "posted_at": result.get("posted_at", ""),
            "_source_type": "jobspy",
            "_source_board": result.get("source_board", ""),
        }

    def _job_to_filter_dict(self, job) -> dict:
        """Ensure job is a dict for filtering."""
        if isinstance(job, dict):
            return job
        if hasattr(job, 'to_dict'):
            return job.to_dict()
        return {}

    def _infer_location_from_url(self, url: str) -> str:
        url_lower = (url or "").lower()
        cities = [
            "chennai", "bengaluru", "bangalore", "hyderabad", "mumbai", "pune",
            "delhi", "gurugram", "gurgaon", "noida", "kolkata", "kochi",
            "coimbatore", "ahmedabad", "jaipur", "chandigarh", "lucknow", "indore",
        ]
        found = []
        for city in cities:
            if re.search(rf"(^|[-_/]){re.escape(city)}($|[-_/])", url_lower):
                found.append("Bangalore" if city == "bengaluru" else "Gurugram" if city == "gurgaon" else city.title())
        return ", ".join(dict.fromkeys(found))

    def _is_scorable_job_dict(self, job: dict) -> bool:
        url = job.get("url", job.get("source_url", ""))
        url_type = job.get("url_type") or classify_url_type(url).value
        apply_url = job.get("apply_url") or job.get("application_url") or url
        jd_text = job.get("jd_text") or job.get("description") or job.get("raw_description") or ""
        return (
            url_type == URLType.INDIVIDUAL_JOB.value
            and bool(job.get("title") or job.get("role_title"))
            and bool(job.get("company"))
            and bool(job.get("location"))
            and bool(str(jd_text).strip())
            and bool(apply_url)
        )

    def _dict_to_job_posting(self, d: dict) -> JobPosting:
        """Convert verified job dict to JobPosting for scoring."""
        source = d.get("_source_type", "unknown")
        url = d.get("url", d.get("source_url", ""))

        # Detect source from URL if not set
        if source in ("search", "scrapegraph", "jobspy"):
            from careerloop.models import SourceType
            url_lower = url.lower()
            if "linkedin" in url_lower:
                source = SourceType.LINKEDIN.value
            elif "naukri" in url_lower:
                source = SourceType.NAUKRI.value
            elif "instahyre" in url_lower:
                source = SourceType.INSTAHYRE.value
            elif "cutshort" in url_lower:
                source = SourceType.CUTSHORT.value
            elif "greenhouse" in url_lower:
                source = SourceType.GREENHOUSE.value
            elif "lever" in url_lower:
                source = SourceType.LEVER.value
            elif "wellfound" in url_lower:
                source = SourceType.WELLFOUND.value

        skills = d.get("skills", d.get("skills_required", []))
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]

        route = d.get("apply_route", {})
        apply_url = route.get("apply_url") or d.get("apply_url") or d.get("application_url") or url

        return JobPosting(
            source=source,
            source_url=url,
            company=d.get("company", ""),
            role_title=d.get("title", d.get("role_title", "")),
            location=d.get("location", ""),
            work_mode=d.get("work_mode", ""),
            salary_range=d.get("salary", d.get("salary_range", "")),
            skills_required=skills if isinstance(skills, list) else [],
            raw_description=d.get("description", d.get("raw_description", "")),
            application_url=apply_url,
            posted_at=d.get("posted_at", ""),
            extraction_confidence=0.8 if d.get("_source_type") == "scrapegraph" else 0.6,
        )

    # ── Legacy CSV template ────────────────────────────────────────

    def create_csv_template(self, date: str = None) -> str:
        """Create import CSV template. Returns path."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        csv_path = self.import_dir / f"{date}.csv"
        if not csv_path.exists():
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "source", "company", "role", "url", "location", "description",
                    "posted_at", "work_mode", "salary_range", "experience_required",
                    "skills_required", "company_type", "responsibilities"
                ])
        return str(csv_path)
