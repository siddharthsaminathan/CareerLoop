#!/usr/bin/env python3
"""
CareerLoop Daily Runner — Orchestrates the morning pipeline.

Usage:
    python -m careerloop.daily_runner              # Full run: scan + score + shortlist
    python -m careerloop.daily_runner --no-scan     # Score existing pipeline only
    python -m careerloop.daily_runner --user gf     # Run for girlfriend's instance

Flow:
    1. Run scan.mjs → discover new jobs
    2. Read pipeline.md → parse new job URLs
    3. India geo filter + role family filter
    4. Load ledger → deduplicate (remove already seen/applied/skipped)
    5. Add new jobs to ledger
    6. Run India Fit Engine → score all new jobs (capped at MAX_SCORE_PER_RUN)
    7. Update ledger with scores
    8. Generate daily shortlist + persist to disk
    9. Print to console (future: send via WhatsApp)
"""

import os
import sys
import uuid
import logging
import subprocess
import re
import json
from datetime import datetime, timezone, date
from pathlib import Path

logger = logging.getLogger(__name__)

# Add parent to path
CAREER_OPS_ROOT = os.path.realpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, CAREER_OPS_ROOT)

from careerloop.profile_manager import ProfileManager
from careerloop.india_fit_engine import IndiaFitEngine
from careerloop.application_ledger import ApplicationLedger
from careerloop.india_filter import filter_india_jobs
from careerloop.shortlist_formatter import (
    format_daily_shortlist,
    format_job_detail,
    format_follow_up_message,
)


class DailyRunner:
    """
    Orchestrates the daily CareerLoop pipeline:

    1. Scan → 2. Parse → 3. India + Role Filter → 4. Dedupe → 5. Add → 6. Score → 7. Shortlist → 8. Persist → 9. Output
    """

    def __init__(self, career_ops_root: str = None):
        self.root = career_ops_root or CAREER_OPS_ROOT
        self.profile = ProfileManager(self.root)
        self.engine = IndiaFitEngine(self.profile)
        self.ledger = ApplicationLedger(self.root)

        self.pipeline_path = os.path.join(self.root, "data", "pipeline.md")
        self.scan_script = os.path.join(self.root, "scan.mjs")

    def run(self, do_scan: bool = True) -> dict:
        """Run the full daily pipeline. Returns summary dict."""

        # ── Pipeline observability: run_id + start timestamp ──────
        run_id = uuid.uuid4().hex[:12]
        started_at = datetime.now(timezone.utc).isoformat()
        logger.info("daily_run_started", extra={"extra": {"run_id": run_id, "event": "pipeline_start"}})

        print("=" * 60)
        print("🔁 CareerLoop Daily Runner")
        print(f"   {datetime.now(timezone.utc).strftime('%B %d, %Y — %H:%M UTC')}")
        print(f"   User: {self.profile.full_name}")
        print("=" * 60)
        print()

        # ── Idempotency guard: skip if brief already generated today ──
        today_str = datetime.now(timezone.utc).date().isoformat()
        brief_date_file = os.path.join(self.root, "careerloop", ".last_brief_date")
        if os.path.exists(brief_date_file):
            with open(brief_date_file) as f:
                if f.read().strip() == today_str:
                    print(f"Brief already generated today ({today_str}). Use --no-scan --force to re-run.")
                    return {
                        "new_jobs_found": 0,
                        "unique_added": 0,
                        "scored": 0,
                        "shortlist_count": 0,
                        "follow_ups_due": 0,
                        "shortlist_text": "",
                        "top_jobs": [],
                        "already_generated": True,
                    }

        # ── Step 1: Scan ─────────────────────────────────────────────
        new_raw_jobs = []
        if do_scan:
            print("📡 Step 1: Pulling active roles from Top-of-Funnel discovery hook...")
            self._run_scanner()
            new_raw_jobs = self._parse_pipeline()
            print(f"   Discovery complete. Filtering top-of-funnel noise...")
        else:
            print("📡 Step 1: Skipped (--no-scan)")
            new_raw_jobs = self._parse_pipeline()

        logger.info("scan_completed", extra={"extra": {"run_id": run_id, "event": "scan_completed", "jobs_found": len(new_raw_jobs), "do_scan": do_scan}})

        # ── Step 2: Geo & Role Family Filters ────────────────────────
        print("📍 Step 2: Applying India geo filter & role family filter...")
        india_jobs, rejected_india = filter_india_jobs(new_raw_jobs)
        print(f"   India filter: {len(india_jobs)} passed, {len(rejected_india)} rejected")
        for rj in rejected_india[:3]:
            print(f"     ✗ {rj.get('title','?')} @ {rj.get('company','?')} — {rj.get('_rejection_reason','?')}")

        # Role family filter: keep only jobs matching target roles
        target_roles = self.profile.target_roles or []
        if target_roles:
            role_filtered = []
            for job in india_jobs:
                title = (job.get("title", "") or "").lower()
                if any(role.lower() in title for role in target_roles):
                    role_filtered.append(job)
            print(f"   Role filter: {len(role_filtered)} of {len(india_jobs)} match target roles {target_roles}")
            india_jobs = role_filtered

        logger.info("filter_completed", extra={"extra": {"run_id": run_id, "event": "filter_completed", "india_passed": len(india_jobs), "rejected": len(rejected_india)}})

        # ── Step 3: Dedupe ───────────────────────────────────────────
        print("🔍 Step 3: Running baseline deduplication...")
        unique_jobs = []
        dupes = 0
        for job in india_jobs:
            url = job.get("url", "")
            company = job.get("company", "")
            title = job.get("title", "")

            if self.ledger.is_duplicate(url=url, company=company, title=title):
                dupes += 1
                continue
            unique_jobs.append(job)
        print(f"   {len(unique_jobs)} unique roles survived deduplication")

        logger.info("dedup_completed", extra={"extra": {"run_id": run_id, "event": "dedup_completed", "unique": len(unique_jobs), "dupes": dupes}})

        # ── Step 4: Add to ledger ────────────────────────────────────
        print("📝 Step 4: Adding to ledger...")
        added = 0
        for job in unique_jobs:
            source = job.get("source", "unknown")
            if not self.ledger.is_duplicate(url=job.get("url", "")):
                self.ledger.add_job(job, source=source)
                added += 1
        print(f"   {added} jobs added to ledger")

        logger.info("ledger_updated", extra={"extra": {"run_id": run_id, "event": "ledger_updated", "added": added}})

        # ── Step 5: Score ────────────────────────────────────────────
        print("🎯 Step 5: Scoring with India Fit Engine...")
        unscored = self.ledger.get_by_status("DISCOVERED")
        if not unscored:
            # Also check SHORTLISTED that haven't been scored
            unscored = [
                e for e in self.ledger.entries
                if e["status"] in ("DISCOVERED", "SHORTLISTED")
                and e.get("fit_score") is None
            ]

        MAX_SCORE_PER_RUN = int(os.getenv("MAX_SCORE_PER_RUN", "50"))
        scored_count = 0
        rejected_count = 0
        for entry in unscored:
            if scored_count >= MAX_SCORE_PER_RUN:
                print(f"   ⚠️ Scoring cap reached ({MAX_SCORE_PER_RUN}). {len(unscored) - scored_count} jobs left unscored.")
                break
            try:
                score, breakdown = self.engine.score_job(entry)
                if breakdown.get("rejected"):
                    self.ledger.set_fit_score(entry["job_id"], 0, breakdown)
                    self.ledger.transition(entry["job_id"], "SKIPPED", breakdown["rejected"])
                    rejected_count += 1
                    continue
                self.ledger.set_fit_score(entry["job_id"], score, breakdown)
                scored_count += 1
            except Exception as e:
                print(f"   ⚠️ Failed to score {entry.get('title')}: {e}")

        print(f"   {scored_count} jobs scored, {rejected_count} rejected (search pages/articles)")

        logger.info("scoring_completed", extra={"extra": {"run_id": run_id, "event": "scoring_completed", "scored_count": scored_count, "rejected_count": rejected_count}})

        # ── Step 6: Shortlist ────────────────────────────────────────
        print("📋 Step 6: Generating shortlist...")
        # Import India check for geo-guarding the shortlist
        from careerloop.india_filter import is_india_job as _india_guard
        scored_jobs = [
            {
                "job": e,
                "score": e.get("fit_score", 0),
                "breakdown": e.get("fit_breakdown", {}),
                "status": e.get("status"),
            }
            for e in self.ledger.entries
            if e.get("fit_score") is not None
            and e["status"] in ("DISCOVERED", "SHORTLISTED", "SENT_TO_USER")
            and _india_guard(e.get("location", ""), "", e.get("source_url", "") or e.get("url", ""))[0]
        ]
        scored_jobs.sort(key=lambda x: x["score"], reverse=True)

        shortlist_count = len([j for j in scored_jobs if j["score"] >= 60])
        logger.info("shortlist_completed", extra={"extra": {"run_id": run_id, "event": "shortlist_completed", "total_scored": len(scored_jobs), "shortlist_count": shortlist_count}})

        follow_ups = self.ledger.get_follow_ups_due()

        # ── Step 7: Mark shown jobs ──────────────────────────────────
        for item in scored_jobs[:5]:
            job = item["job"]
            if job["status"] == "DISCOVERED":
                try:
                    self.ledger.transition(job["job_id"], "SHORTLISTED", "Auto-shortlisted by daily runner")
                except Exception:
                    pass

        # ── Step 8: Output ───────────────────────────────────────────
        shortlist_text = format_daily_shortlist(
            scored_jobs, follow_ups,
            user_name=self.profile.full_name.split()[0]
        )

        # Persist daily brief to disk so it can be retrieved later
        brief_dir = os.path.join(self.root, "output", "daily_briefs")
        os.makedirs(brief_dir, exist_ok=True)
        brief_path = os.path.join(brief_dir, f"{today_str}.md")
        with open(brief_path, 'w') as f:
            f.write(f"# Daily Brief — {today_str}\n\n")
            f.write(shortlist_text)

        print()
        print(shortlist_text)
        print()

        # Stats
        stats = self.ledger.stats()
        print("─" * 60)
        print(f"Ledger: {stats['total_jobs']} total | {stats['active_count']} active | "
              f"{stats['follow_ups_due']} follow-ups due")
        print(f"Avg fit score: {stats['avg_fit_score']}/100 | {stats['scored_count']} scored")
        print("─" * 60)

        # Write sentinel so we skip re-runs today
        with open(brief_date_file, 'w') as f:
            f.write(today_str)

        # ── Pipeline end: elapsed time ──────────────────────────
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(started_at)).total_seconds()
        logger.info("daily_run_completed", extra={"extra": {"run_id": run_id, "event": "pipeline_end", "elapsed_s": elapsed}})

        return {
            "new_jobs_found": len(new_raw_jobs),
            "unique_added": added,
            "scored": scored_count,
            "shortlist_count": len([j for j in scored_jobs if j["score"] >= 60]),
            "follow_ups_due": len(follow_ups),
            "shortlist_text": shortlist_text,
            "top_jobs": scored_jobs[:5],
        }

    # ── Internal ─────────────────────────────────────────────────────

    def _run_scanner(self):
        """Run scan.mjs to discover new jobs."""
        try:
            result = subprocess.run(
                ["node", self.scan_script],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                print(f"   ⚠️ Scanner error: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print("   ⚠️ Scanner timed out")
        except Exception as e:
            print(f"   ⚠️ Scanner failed: {e}")

    def _parse_pipeline(self) -> list[dict]:
        """Parse pipeline.md into job dicts."""
        jobs = []
        if not os.path.exists(self.pipeline_path):
            return jobs

        with open(self.pipeline_path) as f:
            content = f.read()

        # Parse: "- [ ] URL | Company | Title | Location"
        # Location is optional (new format includes it, old format doesn't)
        pattern = r'- \[[ x]\] (\S+)\s*\|\s*([^|]+)\s*\|\s*([^|]+?)(?:\s*\|\s*(.+))?$'
        for match in re.finditer(pattern, content, re.MULTILINE):
            url = match.group(1).strip()
            company = match.group(2).strip()
            title = match.group(3).strip()
            location = (match.group(4) or "").strip() if match.lastindex and match.lastindex >= 4 else ""

            # Detect source from URL
            source = "unknown"
            if "greenhouse" in url:
                source = "greenhouse-api"
            elif "lever.co" in url:
                source = "lever-api"
            elif "ashbyhq.com" in url:
                source = "ashby-api"
            elif "linkedin.com" in url:
                source = "linkedin"
            elif "naukri.com" in url:
                source = "naukri"

            # Try to extract location from URL (Greenhouse embeds it)
            if not location:
                loc_match = re.search(r'location=([^&]+)', url)
                if loc_match:
                    from urllib.parse import unquote
                    location = unquote(loc_match.group(1))

            jobs.append({
                "url": url,
                "company": company,
                "title": title,
                "location": location,
                "source": source,
                "source_date": datetime.now(timezone.utc).isoformat(),
            })

        return jobs


# ── CLI ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CareerLoop Daily Runner")
    parser.add_argument("--no-scan", action="store_true", help="Skip scanning, use existing pipeline")
    parser.add_argument("--user", default="siddharth", help="User instance (siddharth/gf)")
    parser.add_argument("--job", type=str, help="Show detail for a specific job ID")
    parser.add_argument("--follow-ups", action="store_true", help="Show follow-up queue only")
    parser.add_argument("--stats", action="store_true", help="Show ledger stats only")
    args = parser.parse_args()

    # Determine root directory based on user
    if args.user == "gf":
        root = os.path.realpath(os.path.expanduser("~/projects/career-ops-gf"))
    else:
        root = os.path.realpath(CAREER_OPS_ROOT)

    runner = DailyRunner(root)

    if args.stats:
        stats = runner.ledger.stats()
        print(json.dumps(stats, indent=2))
    elif args.follow_ups:
        follow_ups = runner.ledger.get_follow_ups_due()
        print(f"📬 {len(follow_ups)} follow-ups due:")
        for fu in follow_ups:
            print(f"  • {fu['company']} — {fu['title']}")
    elif args.job:
        entry = runner.ledger.get_job(args.job)
        if entry:
            breakdown = runner.engine.score_job(entry)
            item = {"job": entry, "score": breakdown[0], "breakdown": breakdown[1]}
            print(format_job_detail(item))
        else:
            print(f"Job {args.job} not found")
    else:
        runner.run(do_scan=not args.no_scan)
