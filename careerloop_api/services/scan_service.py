"""Scan service — async scan initiation + SSE event streaming.

Architecture:
  POST /v1/scans
    → creates background_run row immediately (run_id returned synchronously)
    → starts a Python background thread that runs the full scan pipeline
    → client receives run_id and starts listening to SSE stream

  GET /v1/scans/{run_id}/events
    → Server-Sent Events: polls run_events every 1s, pushes each new event
    → sends "event: done" when background_run.status = COMPLETED or FAILED
    → frontend EventSource closes on done, then calls GET /v1/briefs/latest

Event types emitted during a scan:
  SCAN_STARTED     — "Starting job discovery..."
  SOURCE_STARTED   — "Searching configured portals..."
  CACHE_HIT        — "X fresh jobs found in global cache"
  CANDIDATE_MATCHED— "MATCH #1 — Title @ Company — Location — Score/100"
  FILTER_SUMMARY   — "X raw, Y new, Z scored"
  BRIEF_CREATED    — "Brief created with top matches."
  SCAN_FAILED      — error message
"""

import json
import logging
import os
import threading
import time
import uuid
from typing import Generator, Optional

logger = logging.getLogger("careerloop_api.services.scan")


def initiate_scan(user_id: str, db) -> str:
    """Create a background_run row and start the scan in a thread. Returns run_id."""
    run_id = uuid.uuid4().hex[:12]

    # Write the initial row synchronously so SSE can start polling immediately.
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO careerloop.background_runs (run_id, user_id, run_type, status, started_at)
                VALUES (%s, %s, 'scan', 'RUNNING', NOW())
                """,
                (run_id, user_id),
            )
            _emit(cur, run_id, "Scan queued — starting shortly...", "QUEUED")

    # Pass DATABASE_URL explicitly — threads don't inherit uvicorn env reliably
    import os as _os
    db_url = _os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.error("DATABASE_URL not set — scan worker will fail")

    thread = threading.Thread(
        target=_run_scan_worker,
        args=(user_id, run_id, db_url),
        daemon=True,
    )
    thread.start()
    logger.info("Scan thread started for user %s run_id %s", user_id[:8], run_id)
    return run_id


def get_scan_status(run_id: str, db) -> Optional[dict]:
    """Return the background_run row for a given run_id."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT run_id, user_id, status, run_type, started_at FROM careerloop.background_runs WHERE run_id = %s",
                (run_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def stream_scan_events(run_id: str, db) -> Generator[str, None, None]:
    """
    Generator that yields Server-Sent Event strings for a scan run.

    Polls run_events every 1s and pushes any new events. Stops when
    background_run.status becomes COMPLETED or FAILED (or after 5-minute timeout).
    """
    seen_event_ids: set = set()
    deadline = time.time() + 300  # 5-minute hard timeout

    while time.time() < deadline:
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get new events since last poll
                    cur.execute(
                        """
                        SELECT event_id, event_type, message, timestamp
                        FROM careerloop.run_events
                        WHERE run_id = %s
                        ORDER BY timestamp ASC
                        """,
                        (run_id,),
                    )
                    rows = cur.fetchall()
                    for row in rows:
                        eid = str(row["event_id"])
                        if eid in seen_event_ids:
                            continue
                        seen_event_ids.add(eid)
                        payload = {
                            "event_type": row.get("event_type") or "info",
                            "message": row.get("message") or "",
                            "timestamp": row["timestamp"].isoformat() if hasattr(row.get("timestamp"), "isoformat") else str(row.get("timestamp", "")),
                        }
                        yield f"data: {json.dumps(payload)}\n\n"

                    # Check run status
                    cur.execute(
                        "SELECT status FROM careerloop.background_runs WHERE run_id = %s",
                        (run_id,),
                    )
                    status_row = cur.fetchone()
                    if status_row and status_row["status"] in ("COMPLETED", "FAILED"):
                        yield "data: {\"event_type\": \"DONE\", \"message\": \"Scan complete\"}\n\n"
                        return

        except Exception as e:
            logger.error("SSE poll error for run %s: %s", run_id, e)
            yield f"data: {{\"event_type\": \"ERROR\", \"message\": \"Stream error: {str(e)[:80]}\"}}\n\n"
            return

        time.sleep(1)

    # Timeout
    yield "data: {\"event_type\": \"TIMEOUT\", \"message\": \"Scan is taking longer than expected — check back shortly\"}\n\n"


# ── Background worker ──────────────────────────────────────────────────────────

def _emit(cur, run_id: str, message: str, event_type: str = "info"):
    """Write a run_event row. Must be called within an open cursor."""
    try:
        cur.execute(
            "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, %s)",
            (str(uuid.uuid4()), run_id, message, event_type),
        )
    except Exception as e:
        logger.debug("_emit failed: %s", e)


def _run_scan_worker(user_id: str, run_id: str, db_url: str = ""):
    """
    Runs the full scan pipeline in a background thread.
    Uses its own DB connection (psycopg2 connections are not thread-safe).
    """
    from careerloop.memory.connection import DatabaseManager
    import os as _os

    if not db_url:
        db_url = _os.environ.get("DATABASE_URL", "")

    if not db_url:
        logger.error("No DATABASE_URL in worker thread")
        return

    try:
        db = DatabaseManager(db_url=db_url)
    except Exception as e:
        logger.error("Worker DB init failed: %s", e)
        return

    try:
        _execute_scan(user_id, run_id, db)
    except Exception as e:
        logger.exception("Scan worker fatal error for run %s: %s", run_id, e)
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    _emit(cur, run_id, f"Scan failed: {str(e)[:200]}", "SCAN_FAILED")
                    cur.execute(
                        "UPDATE careerloop.background_runs SET status = 'FAILED', updated_at = NOW() WHERE run_id = %s",
                        (run_id,),
                    )
        except Exception:
            pass


def _execute_scan(user_id: str, run_id: str, db):
    """Core scan logic — runs synchronously inside the worker thread."""
    import re
    from datetime import datetime, timezone
    from careerloop.daily_runner import DailyRunner

    # scan_service.py lives at careerloop_api/services/ → go up 2 levels to repo root
    root = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    runner = DailyRunner(root)

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            _emit(cur, run_id, "Starting job discovery...", "SCAN_STARTED")
            _emit(cur, run_id, "Searching configured portals for new job postings...", "SOURCE_STARTED")

    # Cache-hit check
    try:
        from careerloop.memory.repository_v2 import get_fresh_cached_jobs
        prefs = {}
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        "SELECT work_style_prefs FROM careerloop.users WHERE id = %s",
                        (user_id,),
                    )
                    row = cur.fetchone()
                    if row and row.get("work_style_prefs"):
                        import json as _json
                        raw = row["work_style_prefs"]
                        prefs = _json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    pass

        cached = get_fresh_cached_jobs(prefs, freshness_window_days=14, limit=20)
        if len(cached) >= 5:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    _emit(cur, run_id, f"Cache-hit: {len(cached)} fresh jobs found in global cache", "CACHE_HIT")
    except Exception as e:
        logger.debug("Cache-hit check skipped: %s", e)

    # Run the actual scan
    res = runner.run(do_scan=True)
    today_str = datetime.now(timezone.utc).date().isoformat()
    new_jobs = res.get("new_jobs_found", 0)
    unique_added = res.get("unique_added", 0)
    scored = res.get("scored", 0)
    top_jobs = res.get("top_jobs") or []

    brief_id = str(uuid.uuid4())

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # Clear old brief for today
            cur.execute(
                "DELETE FROM careerloop.daily_brief_items WHERE brief_id IN (SELECT id FROM careerloop.daily_briefs WHERE user_id = %s AND date_str = %s)",
                (user_id, today_str),
            )
            cur.execute(
                "DELETE FROM careerloop.daily_briefs WHERE user_id = %s AND date_str = %s",
                (user_id, today_str),
            )
            cur.execute(
                "INSERT INTO careerloop.daily_briefs (id, user_id, date_str, run_id, summary) VALUES (%s, %s, %s, %s, %s)",
                (brief_id, user_id, today_str, run_id, res.get("shortlist_text", "")),
            )

            for idx, item in enumerate(top_jobs, 1):
                job = item["job"]
                score = item["score"]
                bd = item.get("breakdown", {})
                job_id = job.get("job_id") or job.get("id") or str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO careerloop.daily_brief_items "
                    "(id, brief_id, item_index, job_id, title, company, location, fit_score, recommendation_reason, risk_summary, route_recommendation) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        str(uuid.uuid4()), brief_id, idx, str(job_id),
                        job.get("title", ""), job.get("company", ""), job.get("location", ""),
                        score,
                        bd.get("recommendation_reason") or bd.get("reason") or "Strong match.",
                        bd.get("risk_summary") or bd.get("risks") or "No critical risks.",
                        bd.get("route_recommendation") or bd.get("outreach") or "APPLY",
                    ),
                )
                # Emit match event — frontend shows each as it arrives
                title = job.get("title", "?")
                company = job.get("company", "?")
                location = job.get("location", "?")
                # Parse Cutshort-style titles: "BigRio is hiring AI Engineer job in Chennai | Cutshort"
                m = re.match(r"(.+?)\s+is\s+hiring\s+(.+?)(?:\s+job)?\s+in\s+(.+?)(?:\s*\|.+)?$", title, re.IGNORECASE)
                if m:
                    company = m.group(1).strip()
                    title = m.group(2).strip()
                    location = m.group(3).strip().split("|")[0].strip()
                _emit(cur, run_id, f"MATCH #{idx} — {title} @ {company} ({location}) — {score:.0f}/100", "CANDIDATE_MATCHED")

            # Summary events
            _emit(cur, run_id, f"Scan complete: {new_jobs} raw jobs found, {unique_added} new, {scored} scored", "FILTER_SUMMARY")
            _emit(cur, run_id, "Brief created with top matches.", "BRIEF_CREATED")
            cur.execute(
                "UPDATE careerloop.background_runs SET status = 'COMPLETED', updated_at = NOW() WHERE run_id = %s",
                (run_id,),
            )

    logger.info("Scan completed: run_id=%s user=%s top_jobs=%d", run_id, user_id[:8], len(top_jobs))
