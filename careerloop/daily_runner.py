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
from careerloop.scan_funnel import ScanFunnel
from careerloop.india_fit_engine import IndiaFitEngine
from careerloop.application_ledger import ApplicationLedger
from careerloop.policies import filter_india_jobs, is_india_location
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
        """
        DEPRECATED: Use OnDemandSearch in careerloop/on_demand.py instead.

        Run the full daily pipeline. Returns summary dict.

        This method's discovery path (scan.mjs subprocess, pipeline.md parsing,
        India fit scoring) is deprecated. All job discovery should go through
        careerloop/on_demand.py::OnDemandSearch.run() for unified event streaming,
        dedup, caching, and scoring.

        This method is retained only for backward compatibility with existing
        CLI workflows. It will be removed in v2.
        """

        # ── Pipeline observability: run_id + start timestamp ──────
        run_id = uuid.uuid4().hex[:12]
        started_at = datetime.now(timezone.utc).isoformat()
        logger.info("daily_run_started", extra={"extra": {"run_id": run_id, "event": "pipeline_start"}})

        # ── Discovery funnel tracking (non-blocking) ─────────────
        try:
            from careerloop.memory.connection import get_db_manager
            _funnel_email = self.profile.base.get("candidate", {}).get("email", "") or self.profile.base.get("email", "")
            _funnel_ns = uuid.UUID('12345678-1234-5678-1234-567812345678')
            brief_user_id = str(uuid.uuid5(_funnel_ns, _funnel_email)) if _funnel_email else "unknown"
            self.funnel = ScanFunnel(run_id, brief_user_id, get_db_manager(self.root))
        except Exception:
            self.funnel = None
            brief_user_id = "unknown"

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

        # ── Funnel: DISCOVERED ──
        if self.funnel:
            self.funnel.record_stage("discovered", 0, len(new_raw_jobs))

        # ── Step 2: Geo & Role Family Filters ────────────────────────
        print("📍 Step 2: Applying India geo filter & role family filter...")
        india_jobs, rejected_india = filter_india_jobs(new_raw_jobs)
        print(f"   India filter: {len(india_jobs)} passed, {len(rejected_india)} rejected")
        for rj in rejected_india[:3]:
            print(f"     ✗ {rj.get('title','?')} @ {rj.get('company','?')} — {rj.get('_rejection_reason','?')}")

        # ── Funnel: LOCATION ──
        if self.funnel:
            self.funnel.record_stage("location", len(new_raw_jobs), len(india_jobs))
            for rj in rejected_india:
                self.funnel.record_rejection(
                    rj.get("title", ""), rj.get("company", ""), rj.get("url", ""),
                    "LOCATION", f"Location {rj.get('location','unknown')} not India"
                )

        # ── Save pre-role count for funnel ──
        _funnel_role_before = len(india_jobs)

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

        # ── Funnel: ROLE ──
        if self.funnel:
            self.funnel.record_stage("role", _funnel_role_before, len(india_jobs))

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
                if self.funnel:
                    self.funnel.record_rejection(
                        title, company, url,
                        "DUPLICATE", "Duplicate job already in ledger"
                    )
                continue
            unique_jobs.append(job)
        print(f"   {len(unique_jobs)} unique roles survived deduplication")

        # ── Funnel: DEDUPED ──
        if self.funnel:
            self.funnel.record_stage("deduped", len(india_jobs), len(unique_jobs))

        logger.info("dedup_completed", extra={"extra": {"run_id": run_id, "event": "dedup_completed", "unique": len(unique_jobs), "dupes": dupes}})

        # ── Step 4: Add to ledger ────────────────────────────────────
        # NOTE: All jobs reaching this point passed the initial dedup
        # check in Step 3 (line ~140).  No second is_duplicate check needed.
        print("📝 Step 4: Adding to ledger...")
        added = 0
        for job in unique_jobs:
            source = job.get("source", "unknown")
            self.ledger.add_job(job, source=source)
            added += 1
        print(f"   {added} jobs added to ledger")

        logger.info("ledger_updated", extra={"extra": {"run_id": run_id, "event": "ledger_updated", "added": added}})

        # Structured logging: scan completed
        scan_elapsed_ms = int((datetime.now(timezone.utc) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        logger.info(
            "SCAN_COMPLETED user_id=%s jobs_found=%d new_jobs=%d elapsed_ms=%d",
            brief_user_id,
            len(new_raw_jobs),
            added,
            scan_elapsed_ms,
        )

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

        # ── Funnel: SCORED ──
        if self.funnel:
            self.funnel.record_stage("scored", len(unscored), scored_count)

        logger.info("scoring_completed", extra={"extra": {"run_id": run_id, "event": "scoring_completed", "scored_count": scored_count, "rejected_count": rejected_count}})

        # ── Step 6: Shortlist ────────────────────────────────────────
        print("📋 Step 6: Generating shortlist...")
        # Second geo guard: jobs that passed the initial India filter
        # (filter_india_jobs at line ~113) are re-checked here because
        # scored entries in the ledger may have been added during a
        # previous run with different geo criteria, or may lack location
        # data that is now available.
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
            and is_india_location(e.get("location", ""))[0]
        ]
        scored_jobs.sort(key=lambda x: x["score"], reverse=True)

        shortlist_count = len([j for j in scored_jobs if j["score"] >= 60])

        # ── Funnel: THRESHOLD ──
        if self.funnel:
            self.funnel.record_stage("threshold", len(scored_jobs), shortlist_count)
            # Track jobs rejected by fit score threshold
            for j in scored_jobs:
                if j["score"] < 60:
                    self.funnel.record_rejection(
                        j["job"].get("title", ""), j["job"].get("company", ""),
                        j["job"].get("source_url", "") or j["job"].get("url", ""),
                        "FIT_SCORE", f"Score {j['score']} below threshold"
                    )

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

        # ── Funnel: BRIEFED ──
        if self.funnel:
            self.funnel.record_stage("briefed", shortlist_count, len(scored_jobs[:5]))

        # ── Step 8: Output ───────────────────────────────────────────
        shortlist_text = format_daily_shortlist(
            scored_jobs, follow_ups,
            user_name=self.profile.full_name.split()[0]
        )

        # Structured logging: brief generated
        # brief_user_id computed at function entry (funnel init block)
        elapsed_ms = int((datetime.now(timezone.utc) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        logger.info(
            "BRIEF_GENERATED user_id=%s date=%s items=%d run_id=%s elapsed_ms=%d",
            brief_user_id,
            today_str,
            shortlist_count,
            run_id,
            elapsed_ms,
        )

        # Persist daily brief to disk so it can be retrieved later
        brief_dir = os.path.join(self.root, "output", "daily_briefs")
        os.makedirs(brief_dir, exist_ok=True)
        brief_path = os.path.join(brief_dir, f"{today_str}.md")
        with open(brief_path, 'w') as f:
            f.write(f"# Daily Brief — {today_str}\n\n")
            f.write(shortlist_text)

        # P0-1: Persist every discovered job to careerloop.jobs so API can serve them
        try:
            import hashlib
            from careerloop.memory.connection import get_db_manager
            email = self.profile.base.get("candidate", {}).get("email", "") or self.profile.base.get("email", "")
            if email:
                db = get_db_manager(self.root)
                with db.get_connection() as conn:
                    with conn.cursor() as cur:
                        persisted = 0
                        for entry in self.ledger.entries:
                            job_id = entry.get("job_id")
                            if not job_id:
                                continue
                            source_url = entry.get("source_url") or ""
                            fingerprint = hashlib.md5(
                                (source_url + (entry.get("title") or "")).encode()
                            ).hexdigest()
                            cur.execute("""
                                INSERT INTO careerloop.jobs
                                    (job_id, source, title, company_name, location_raw,
                                     jd_text, canonical_url, apply_url, content_fingerprint)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (job_id) DO UPDATE SET
                                    title           = EXCLUDED.title,
                                    company_name    = EXCLUDED.company_name,
                                    location_raw    = EXCLUDED.location_raw,
                                    jd_text         = COALESCE(EXCLUDED.jd_text, careerloop.jobs.jd_text),
                                    canonical_url   = COALESCE(EXCLUDED.canonical_url, careerloop.jobs.canonical_url),
                                    apply_url       = COALESCE(EXCLUDED.apply_url, careerloop.jobs.apply_url),
                                    source          = EXCLUDED.source,
                                    updated_at      = CURRENT_TIMESTAMP
                            """, (
                                job_id,
                                (entry.get("source") or "unknown")[:50],
                                (entry.get("title") or "")[:500],
                                (entry.get("company") or "")[:255],
                                (entry.get("location") or "")[:255],
                                (entry.get("raw_description") or entry.get("description") or "")[:10000],
                                source_url[:2048],
                                (entry.get("application_url") or "")[:2048],
                                fingerprint,
                            ))
                            persisted += 1
                    conn.commit()
                logger.info(f"Persisted {persisted} jobs to careerloop.jobs")
            else:
                logger.warning("No email in profile — cannot persist jobs to DB")
        except Exception as e:
            logger.warning(f"Failed to persist jobs to DB: {e}")

        # Persist brief to DB so API can serve it (careerloop.daily_briefs table)
        try:
            from careerloop.memory.connection import get_db_manager
            # Derive user_id from profile email (consistent with chat_cli.py authenticate_cli_user)
            email = self.profile.base.get("candidate", {}).get("email", "") or self.profile.base.get("email", "")
            if email:
                NAMESPACE_CAREERLOOP = uuid.UUID('12345678-1234-5678-1234-567812345678')
                user_id = str(uuid.uuid5(NAMESPACE_CAREERLOOP, email))
                db = get_db_manager(self.root)
                brief_id = str(uuid.uuid4())
                with db.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO careerloop.daily_briefs (id, user_id, date_str, run_id, summary) "
                            "VALUES (%s, %s, %s, %s, %s) "
                            "ON CONFLICT (user_id, date_str) DO UPDATE SET "
                            "  run_id = EXCLUDED.run_id, summary = EXCLUDED.summary",
                            (brief_id, user_id, today_str, run_id, shortlist_text),
                        )
                    conn.commit()
                logger.info("brief_persisted_to_db", extra={"extra": {"brief_id": brief_id, "user_id": user_id}})
            else:
                logger.warning("No email in profile — cannot derive user_id, skipping DB persistence")
        except Exception as e:
            logger.warning(f"Failed to persist brief to DB: {e}")

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

        # ── Funnel: emit final summary ──────────────────────────
        if self.funnel:
            self.funnel.emit_funnel_complete({
                "run_id": run_id,
                "user_id": _funnel_uid,
                "discovered": len(new_raw_jobs),
                "deduped": len(unique_jobs),
                "location_passed": _funnel_role_before,
                "role_passed": len(india_jobs),
                "scored": scored_count,
                "above_threshold": shortlist_count,
                "briefed": len(scored_jobs[:5]),
            })

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
