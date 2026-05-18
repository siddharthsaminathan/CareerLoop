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
    3. Load ledger → deduplicate (remove already seen/applied/skipped)
    4. Run India Fit Engine → score all new jobs
    5. Update ledger with scores
    6. Generate daily shortlist
    7. Print to console (future: send via WhatsApp)
"""

import os
import sys
import subprocess
import re
import json
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path
CAREER_OPS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CAREER_OPS_ROOT)

from careerloop.profile_manager import ProfileManager
from careerloop.india_fit_engine import IndiaFitEngine
from careerloop.application_ledger import ApplicationLedger
from careerloop.shortlist_formatter import (
    format_daily_shortlist,
    format_job_detail,
    format_follow_up_message,
)


class DailyRunner:
    """
    Orchestrates the daily CareerLoop pipeline:

    1. Scan → 2. Parse → 3. Dedupe → 4. Score → 5. Shortlist → 6. Output
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
        print("=" * 60)
        print("🔁 CareerLoop Daily Runner")
        print(f"   {datetime.now(timezone.utc).strftime('%B %d, %Y — %H:%M UTC')}")
        print(f"   User: {self.profile.full_name}")
        print("=" * 60)
        print()

        # ── Step 1: Scan ─────────────────────────────────────────────
        new_raw_jobs = []
        if do_scan:
            print("📡 Step 1: Scanning job sources...")
            self._run_scanner()
            new_raw_jobs = self._parse_pipeline()
            print(f"   Found {len(new_raw_jobs)} new raw jobs in pipeline")
        else:
            print("📡 Step 1: Skipped (--no-scan)")
            new_raw_jobs = self._parse_pipeline()

        # ── Step 2: Dedupe ───────────────────────────────────────────
        print("🔍 Step 2: Deduplicating...")
        unique_jobs = []
        dupes = 0
        for job in new_raw_jobs:
            url = job.get("url", "")
            company = job.get("company", "")
            title = job.get("title", "")

            if self.ledger.is_duplicate(url=url, company=company, title=title):
                dupes += 1
                continue
            unique_jobs.append(job)
        print(f"   {len(unique_jobs)} unique ({dupes} duplicates skipped)")

        # ── Step 3: Add to ledger ────────────────────────────────────
        print("📝 Step 3: Adding to ledger...")
        added = 0
        for job in unique_jobs:
            source = job.get("source", "unknown")
            if not self.ledger.is_duplicate(url=job.get("url", "")):
                self.ledger.add_job(job, source=source)
                added += 1
        print(f"   {added} jobs added to ledger")

        # ── Step 4: Score ────────────────────────────────────────────
        print("🎯 Step 4: Scoring with India Fit Engine...")
        unscored = self.ledger.get_by_status("DISCOVERED")
        if not unscored:
            # Also check SHORTLISTED that haven't been scored
            unscored = [
                e for e in self.ledger.entries
                if e["status"] in ("DISCOVERED", "SHORTLISTED")
                and e.get("fit_score") is None
            ]

        scored_count = 0
        rejected_count = 0
        for entry in unscored:
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

        # ── Step 5: Shortlist ────────────────────────────────────────
        print("📋 Step 5: Generating shortlist...")
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
        ]
        scored_jobs.sort(key=lambda x: x["score"], reverse=True)

        follow_ups = self.ledger.get_follow_ups_due()

        # ── Step 6: Mark shown jobs ──────────────────────────────────
        for item in scored_jobs[:5]:
            job = item["job"]
            if job["status"] == "DISCOVERED":
                try:
                    self.ledger.transition(job["job_id"], "SHORTLISTED", "Auto-shortlisted by daily runner")
                except Exception:
                    pass

        # ── Step 7: Output ───────────────────────────────────────────
        shortlist_text = format_daily_shortlist(
            scored_jobs, follow_ups,
            user_name=self.profile.full_name.split()[0]
        )

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
        root = os.path.expanduser("~/projects/career-ops-gf")
    else:
        root = CAREER_OPS_ROOT

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
