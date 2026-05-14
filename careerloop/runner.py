#!/usr/bin/env python3
"""
CareerLoop Runner -- Phase 1 orchestrator.

Pipeline:
  Profile -> Role Queries -> Free Search -> Extract -> India Filter
  -> Verify Active -> Dedupe -> Score -> Verified Shortlist -> Chat Output

Usage:
  python -m careerloop.runner              # Full pipeline
  python -m careerloop.runner --csv-only   # CSV imports only
  python -m careerloop.runner --job JOBID --decision APPLY
  python -m careerloop.runner --audit-only
  python -m careerloop.runner --test
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

CAREER_OPS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CAREER_OPS_ROOT)

from careerloop.models import JobPosting, ScoredJob, UserVisibleOpportunity
from careerloop.discovery import DiscoveryEngine
from careerloop.dedupe import DedupeEngine
from careerloop.india_fit_llm import LLMIndiaFitEngine
from careerloop.india_fit_engine import IndiaFitEngine
from careerloop.application_ledger import ApplicationLedger
from careerloop.profile_manager import ProfileManager
from careerloop.approval import ApprovalWorkflow
from careerloop.audit import AuditReport
from careerloop.followup import FollowUpQueue
from careerloop.whatsapp_ux import (
    daily_brief, job_review_card, job_detail_card,
    follow_up_card, apply_confirmation
)

logger = logging.getLogger(__name__)


class CareerLoopRunner:
    """Phase 1 orchestrator -- India Job Discovery & Verification Engine."""

    def __init__(self, root: str = None):
        self.root = root or CAREER_OPS_ROOT
        self.discovery = DiscoveryEngine(self.root)
        self.ledger = ApplicationLedger(self.root)
        self.profile = ProfileManager(self.root)
        self.dedupe = DedupeEngine()
        self.heuristic_fitter = IndiaFitEngine(self.profile)
        self.fitter = LLMIndiaFitEngine()
        self.approval = ApprovalWorkflow(self.ledger)
        self.audit = AuditReport(self.root)
        self.followup = FollowUpQueue(self.ledger)

    def run(self, date: str = None, csv_only: bool = False) -> dict:
        """Run the full daily pipeline. Returns summary dict."""
        print("=" * 60)
        print("[CAREERLOOP] India Job Discovery Engine")
        print(f"   {datetime.now(timezone.utc).strftime('%B %d, %Y -- %H:%M UTC')}")
        print(f"   User: {self.profile.full_name}")
        print("=" * 60)
        print()

        user_profile = self.profile.get_full_profile()

        if csv_only:
            return self._run_csv_only(date, user_profile)

        # ?? Step 1: DISCOVER ???????????????????????????????????
        print("[STEP 1] Discovering India jobs...")
        print("   Architecture: SearchResult -> CandidateURL -> ExtractedJob -> VerifiedJob")
        report = self.discovery.discover_india_jobs(user_profile, date)

        stats = report["source_stats"]
        print(f"   Queries generated: {len(report['queries'])}")
        print(f"   DDG URLs found: {stats.get('ddg_urls', 0)}")
        print(f"   JobSpy results: {stats.get('jobspy_jobs', 0)}")
        print(f"   CSV imports: {stats.get('csv_imports', 0)}")
        print(f"   Raw search results: {stats.get('raw_search_results_count', 0)}")
        print(f"   Rejected noise: {stats.get('rejected_noise_count', 0)}")
        print(f"   Search/category pages: {stats.get('search_category_pages_count', 0)}")
        print(f"   ScrapeGraph extracted: {stats.get('scrapegraph_extracted', 0)}")
        print(f"   India filter: {stats.get('india_passed', 0)} passed, {stats.get('india_rejected', 0)} rejected")
        print(f"   After merge: {stats.get('after_merge', 0)}")
        print(f"   Verified active: {stats.get('verified_active', 0)}")

        verified_jobs = report["verified_job_postings"]

        if not verified_jobs:
            print()
            print("[WARN]  No verified active India jobs found.")
            print("   Reasons:")
            if stats.get("ddg_urls", 0) == 0:
                print("   - Search returned no URLs (DDG may be rate-limited)")
            if stats.get("india_rejected", 0) > 0:
                print(f"   - {stats['india_rejected']} jobs rejected by India filter")
            unverified = report.get("unverified_jobs", [])
            if unverified:
                print(f"   - {len(unverified)} jobs failed verification:")
                for j in unverified[:3]:
                    print(f"     • {j.get('title','')} @ {j.get('company','')}: {j.get('verification_reason','')}")
            return self._empty_result(report)

        # ?? Step 2: DEDUPE ?????????????????????????????????????
        print()
        print("[STEP 2] Deduplicating against ledger...")
        self.dedupe.load_from_ledger(self.ledger.entries)
        unique_jobs, merges = self.dedupe.process_new_jobs(verified_jobs)
        print(f"   {len(unique_jobs)} unique ({len(verified_jobs) - len(unique_jobs)} already in ledger)")

        # ?? Step 3: ADD TO LEDGER ??????????????????????????????
        print("[STEP 3] Adding to ledger...")
        for job in unique_jobs:
            jid = self.ledger.add_job(job.to_dict(), source=job.source)
            job.id = jid
        print(f"   {len(unique_jobs)} jobs added")

        # ?? Step 4: SCORE ??????????????????????????????????????
        print("[STEP 4] Scoring funnel: deterministic -> heuristic -> LLM top 15...")
        score_pool = [
            e for e in self.ledger.entries
            if e["status"] == "DISCOVERED"
            and not e.get("fit_result")
            and self._entry_is_scorable(e)
        ]
        heuristic_ranked = []
        for entry in score_pool:
            try:
                h_score, h_breakdown = self.heuristic_fitter.score_job(entry)
                entry["heuristic_score"] = h_score
                entry["heuristic_breakdown"] = h_breakdown
                heuristic_ranked.append((entry, h_score))
            except Exception as e:
                print(f"   [WARN] Heuristic score failed {entry.get('title')}: {e}")

        heuristic_ranked.sort(key=lambda x: x[1], reverse=True)
        llm_limit = int(os.getenv("MAX_LLM_SCORE_JOBS", 15))
        llm_candidates = heuristic_ranked[:llm_limit]
        scored = 0
        for entry, h_score in llm_candidates:
            try:
                job = JobPosting(
                    id=entry["job_id"],
                    source=entry.get("source", "unknown"),
                    source_url=entry.get("source_url", ""),
                    company=entry.get("company", ""),
                    role_title=entry.get("title") or entry.get("role_title", ""),
                    location=entry.get("location", ""),
                    application_url=entry.get("application_url", entry.get("source_url", "")),
                    raw_description=entry.get("raw_description") or entry.get("description", ""),
                    work_mode=entry.get("work_mode", ""),
                    salary_range=entry.get("salary_range", ""),
                    skills_required=entry.get("skills_required", []),
                )
                result = self.fitter.score_job(job, user_profile)
                entry["fit_result"] = result
                entry["fit_score"] = result.get("overall_score", h_score)
                entry["recommendation"] = result.get("recommendation", "MAYBE")
                scored += 1
            except Exception as e:
                print(f"   [WARN] LLM score failed {entry.get('title')}: {e}")
        self.ledger._save()
        print(f"   Deterministic scorable: {len(score_pool)}")
        print(f"   Heuristic scored: {len(heuristic_ranked)}")
        print(f"   LLM scored: {scored}")
        report["source_stats"]["scored_jobs_count"] = scored
        report["scored_jobs"] = [
            ScoredJob(
                job=JobPosting(
                    id=e["job_id"],
                    source=e.get("source", "unknown"),
                    source_url=e.get("source_url", ""),
                    company=e.get("company", ""),
                    role_title=e.get("title", ""),
                    location=e.get("location", ""),
                    application_url=e.get("application_url", e.get("source_url", "")),
                    raw_description=e.get("raw_description") or e.get("description", ""),
                ),
                heuristic_score=e.get("heuristic_score", 0),
                fit_score=e.get("fit_score"),
                fit_result=e.get("fit_result", {}),
            ).to_dict()
            for e, _ in heuristic_ranked
            if e.get("fit_score") is not None
        ]

        # ?? Step 5: SHORTLIST ??????????????????????????????????
        print("? Step 5: Generating verified shortlist...")
        scored_jobs = [
            e for e in self.ledger.entries
            if e.get("fit_score") is not None
            and e["status"] in ("DISCOVERED", "SHORTLISTED")
        ]
        scored_jobs.sort(key=lambda x: x.get("fit_score", 0), reverse=True)
        good_jobs = [j for j in scored_jobs if j.get("fit_score", 0) >= 60 and self._entry_is_scorable(j)]

        for entry in scored_jobs[:10]:
            if entry["status"] == "DISCOVERED":
                try:
                    self.ledger.transition(entry["job_id"], "SHORTLISTED", "Auto-shortlisted")
                except Exception:
                    pass

        follow_ups = self.followup.get_due()

        # ?? Step 6: CHAT OUTPUT ????????????????????????????????
        top_job = good_jobs[0] if good_jobs else None
        top_display = None
        if top_job:
            fit = top_job.get("fit_result", {})
            top_display = {
                "company": top_job.get("company", ""),
                "role_title": top_job.get("title", ""),
                "overall_score": top_job.get("fit_score", 0),
                "recommendation": top_job.get("recommendation", ""),
                "why_user_might_like_it": fit.get("why_user_might_like_it", ""),
                "risks": fit.get("risks", []),
            }

        user_visible = [self._to_user_visible_opportunity(j) for j in good_jobs[:10]]
        report["user_visible_opportunities"] = user_visible
        report["final_shortlist"] = user_visible
        report["source_stats"]["final_user_visible_opportunities"] = len(user_visible)

        brief = daily_brief(
            len(verified_jobs), len(good_jobs), top_display,
            len(follow_ups), self.profile.full_name.split()[0]
        )
        print()
        print(brief)

        # ?? Step 7: AUDIT ??????????????????????????????????????
        print()
        print("? Step 7: Generating audit report...")
        report_path = self.audit.generate(
            self.ledger.entries,
            person_name=self.profile.full_name,
            date=date
        )
        print(f"   Report: {report_path}")

        print()
        print("?" * 60)
        print(f"Raw search: {stats.get('raw_search_results_count', 0)} | Noise: {stats.get('rejected_noise_count', 0)} | Search/category: {stats.get('search_category_pages_count', 0)}")
        print(f"Verified: {len(verified_jobs)} | Scored: {scored} | User-visible: {len(user_visible)} | Follow-ups: {len(follow_ups)}")
        print("?" * 60)

        return {
            "discovery_report": report,
            "verified_jobs": len(verified_jobs),
            "unique_added": len(unique_jobs),
            "scored": scored,
            "good_jobs": len(good_jobs),
            "final_user_visible_opportunities": len(user_visible),
            "follow_ups_due": len(follow_ups),
            "audit_report": report_path,
            "brief": brief,
        }

    def _entry_is_scorable(self, entry: dict) -> bool:
        jd_text = entry.get("raw_description") or entry.get("description") or entry.get("jd_text", "")
        return all([
            entry.get("title") or entry.get("role_title"),
            entry.get("company"),
            entry.get("location"),
            str(jd_text).strip(),
            entry.get("source_url"),
            entry.get("application_url") or entry.get("source_url"),
        ])

    def _to_user_visible_opportunity(self, entry: dict) -> dict:
        fit = entry.get("fit_result", {})
        opportunity = UserVisibleOpportunity(
            company=entry.get("company", ""),
            role_title=entry.get("title", entry.get("role_title", "")),
            location=entry.get("location", ""),
            source_url=entry.get("source_url", ""),
            apply_url=entry.get("application_url", entry.get("source_url", "")),
            overall_score=entry.get("fit_score", 0),
            recommendation=entry.get("recommendation", fit.get("recommendation", "MAYBE")),
            why_user_might_like_it=fit.get("why_user_might_like_it", fit.get("reason", "")),
            risks=fit.get("risks", []),
            confidence=fit.get("confidence", 0),
        )
        return opportunity.to_dict()

    def _run_csv_only(self, date, profile):
        """Run with CSV imports only (no search)."""
        print("? Running CSV-only mode...")
        csv_jobs = self.discovery._discover_csv(date)
        print(f"   Found {len(csv_jobs)} CSV imports")
        # Process through normal pipeline minus search
        return {"csv_jobs": len(csv_jobs), "mode": "csv_only"}

    def _empty_result(self, report):
        return {
            "discovery_report": report,
            "verified_jobs": 0,
            "unique_added": 0,
            "scored": 0,
            "good_jobs": 0,
            "follow_ups_due": 0,
            "brief": "No verified India jobs found today.",
        }

    # ?? Decision handler ??????????????????????????????????????

    def decide(self, job_id: str, decision: str, reason: str = "") -> dict:
        return self.approval.process_decision(job_id, decision, reason)

    def show_job(self, job_id: str, detail: bool = False) -> str:
        entry = self.ledger.get_job(job_id)
        if not entry:
            return f"Job {job_id} not found."
        fit = entry.get("fit_result", {})
        display = {
            "company": entry.get("company", ""),
            "role_title": entry.get("title", ""),
            "location": entry.get("location", ""),
            "overall_score": entry.get("fit_score", 0),
            "recommendation": fit.get("recommendation", "MAYBE"),
            "why_user_might_like_it": fit.get("why_user_might_like_it", ""),
            "risks": fit.get("risks", []),
            "why_user_might_hate_it": fit.get("why_user_might_hate_it", ""),
            "confidence": fit.get("confidence", 0),
            "source_url": entry.get("source_url", ""),
            "dimensions": {k: v.get("raw", v) for k, v in fit.items()
                          if isinstance(v, dict) and "raw" in v},
        }
        if detail:
            return job_detail_card(display)
        total = len([e for e in self.ledger.entries
                    if e.get("fit_score") is not None
                    and e["status"] in ("DISCOVERED", "SHORTLISTED")])
        idx = list(self.ledger.entries).index(entry) + 1 if entry in self.ledger.entries else 1
        return job_review_card(display, idx, total)


# ?? CLI ????????????????????????????????????????????????????????

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="CareerLoop Phase 1 -- India Job Discovery")
    parser.add_argument("--csv-only", action="store_true", help="Only CSV imports")
    parser.add_argument("--job", type=str, help="Show job detail by ID")
    parser.add_argument("--detail", action="store_true", help="Show full job detail")
    parser.add_argument("--decision", type=str, help="APPLY/SKIP/MAYBE")
    parser.add_argument("--reason", type=str, default="", help="Reason for skip/maybe")
    parser.add_argument("--audit-only", action="store_true", help="Generate audit only")
    parser.add_argument("--follow-ups", action="store_true", help="Show follow-up queue")
    parser.add_argument("--stats", action="store_true", help="Show ledger stats")
    parser.add_argument("--template", action="store_true", help="Create CSV import template")
    parser.add_argument("--test", action="store_true", help="Run tests")
    args = parser.parse_args()

    runner = CareerLoopRunner()

    if args.template:
        path = runner.discovery.create_csv_template()
        print(f"CSV template created: {path}")
    elif args.test:
        from careerloop.tests import run_tests
        run_tests(runner)
    elif args.job and args.decision:
        result = runner.decide(args.job, args.decision, args.reason)
        print(json.dumps(result, indent=2))
    elif args.job:
        print(runner.show_job(args.job, detail=args.detail))
    elif args.audit_only:
        report_path = runner.audit.generate(
            runner.ledger.entries, person_name=runner.profile.full_name
        )
        print(f"Audit report: {report_path}")
    elif args.follow_ups:
        due = runner.followup.get_due()
        print(f"[NOTE] {len(due)} follow-ups due:")
        for i, fu in enumerate(due, 1):
            print(follow_up_card(fu, i, len(due)))
    elif args.stats:
        stats = runner.ledger.stats()
        fu_stats = runner.followup.stats()
        print(json.dumps({**stats, "follow_ups": fu_stats}, indent=2))
    else:
        runner.run(csv_only=args.csv_only)
