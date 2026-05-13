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
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from careerloop.models import JobPosting, SourceType
from careerloop.role_strategy import RoleStrategyGenerator
from careerloop.sources.search_adapter import SearchAdapter
from careerloop.sources.scrapegraph_adapter import ScrapeGraphAdapter
from careerloop.sources.jobspy_adapter import JobSpyAdapter
from careerloop.india_filter import filter_india_jobs
from careerloop.verification import JobVerifier
from careerloop.apply_route import merge_cross_source, resolve_apply_route

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
            "extracted_jobs": [],
            "india_jobs": [],
            "rejected_jobs": [],
            "verified_jobs": [],
            "unverified_jobs": [],
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
        report["source_stats"]["ddg_urls"] = len(search_results)
        logger.info(f"DDG search found {len(search_results)} candidate URLs")

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
        extracted = []
        if search_results and self.scraper.available:
            logger.info(f"ScrapeGraphAI active. Processing up to 15 discovered URLs...")
            for i, r in enumerate(search_results[:15]):
                url = r["url"]
                logger.info(f"Deep Extraction [{i+1}/{min(len(search_results), 15)}]: {url}")
                data = self.scraper.extract(url)
                if data:
                    extracted.append(data)
                    job = self._extraction_to_job(data)
                    if job:
                        # Enrich with source query context
                        job["_search_query"] = r.get("source_query", "")
                        all_candidate_jobs.append(job)
                else:
                    logger.info(f"Extraction returned None for {url}, falling back to basic search info preservation.")
                    job = self._search_result_to_job(r)
                    if job:
                        all_candidate_jobs.append(job)
            
            # Process remaining search results beyond 15 with basic info fallback to guarantee zero URL loss
            for r in search_results[15:]:
                job = self._search_result_to_job(r)
                if job:
                    all_candidate_jobs.append(job)
        else:
            logger.info("ScrapeGraphAI unavailable or 0 search hits. Using basic search metadata mapping.")
            for r in search_results:
                job = self._search_result_to_job(r)
                if job:
                    all_candidate_jobs.append(job)

        report["extracted_jobs"] = extracted
        report["source_stats"]["scrapegraph_extracted"] = len(extracted)

        # Add JobSpy results
        for r in jobspy_results:
            job = self._jobspy_to_job(r)
            if job:
                all_candidate_jobs.append(job)

        # Add CSV imports
        for job in csv_jobs:
            all_candidate_jobs.append(job)

        logger.info(f"Total candidate jobs before filter: {len(all_candidate_jobs)}")

        # Step 4: India-only filter
        job_dicts = [self._job_to_filter_dict(j) for j in all_candidate_jobs]
        india_jobs, rejected = filter_india_jobs(job_dicts)
        report["india_jobs"] = india_jobs
        report["rejected_jobs"] = rejected
        report["source_stats"]["india_passed"] = len(india_jobs)
        report["source_stats"]["india_rejected"] = len(rejected)

        # Step 5: Cross-source merge
        merged = merge_cross_source(india_jobs)
        report["source_stats"]["after_merge"] = len(merged)

        # Step 6: Verify active
        verified_all = self.verifier.verify_batch(merged, max_verify=20)
        verified_active = self.verifier.get_verified_active(verified_all)
        unverified = [j for j in verified_all if j.get("verification_status") != "VERIFIED_ACTIVE"]

        report["verified_jobs"] = verified_active
        report["unverified_jobs"] = unverified
        report["source_stats"]["verified_active"] = len(verified_active)
        report["source_stats"]["unverified"] = len(unverified)

        # Step 7: Convert to JobPosting objects for scorer
        final = []
        for job_dict in verified_active:
            posting = self._dict_to_job_posting(job_dict)
            final.append(posting)

        report["final_shortlist"] = final
        report["source_stats"]["final_count"] = len(final)

        return report

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
            "location": data.get("location", ""),
            "url": data.get("_source_url", data.get("apply_url", "")),
            "apply_url": data.get("apply_url", ""),
            "description": data.get("description", ""),
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
            "description": result.get("snippet", ""),
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
            "description": result.get("description", ""),
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
            application_url=route.get("apply_url", url),
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
