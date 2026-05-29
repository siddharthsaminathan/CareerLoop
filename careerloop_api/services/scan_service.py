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

Thread Safety (FIXED 2026-05-29):
  - Per-user scan concurrency guard: reject if user already has a RUNNING scan
  - Workers use the SHARED DatabaseManager pool (not a separate pool per thread)
  - Hard limit on concurrent scan workers (max 3 globally)
  - 30-min stale scan recovery runs at module import time
  - Connection pool maxconn set to 3 for workers to avoid Supabase 15-conn limit

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

from careerloop_api.core.envelope import APIError

logger = logging.getLogger("careerloop_api.services.scan")

# ── Concurrency guards ──────────────────────────────────────────────────────────

# Per-user scan lock: prevents initiating a new scan while another is RUNNING.
_active_scans_lock = threading.Lock()
_active_scans: dict = {}  # user_id → run_id

# Global semaphore: at most 3 concurrent scan workers across ALL users.
# This prevents connection pool exhaustion (Supabase free tier = 15 conns).
_worker_semaphore = threading.BoundedSemaphore(3)

# Stale scan recovery — run once at module import.
def _recover_stale_scans():
    """Mark any RUNNING scan older than 30 minutes as FAILED.

    This prevents orphaned scans from blocking new scans after a server restart.
    Runs automatically at import time.
    """
    try:
        from careerloop.memory.connection import get_db_manager
        db = get_db_manager()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE careerloop.background_runs
                    SET status = 'FAILED', updated_at = NOW()
                    WHERE status = 'RUNNING' AND run_type = 'scan'
                      AND started_at < NOW() - INTERVAL '30 minutes'
                    """
                )
                recovered = cur.rowcount
                if recovered:
                    logger.info("Stale scan recovery: marked %d RUNNING scans as FAILED", recovered)
    except Exception as e:
        logger.debug("Stale scan recovery skipped (non-fatal): %s", e)


_recover_stale_scans()


def _has_running_scan(user_id: str) -> Optional[str]:
    """Return the run_id of a RUNNING scan for this user, or None."""
    with _active_scans_lock:
        run_id = _active_scans.get(user_id)
        if run_id:
            return run_id
    # Fallback: check the DB in case this worker restarted
    try:
        from careerloop.memory.connection import get_db_manager
        db = get_db_manager()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT run_id FROM careerloop.background_runs "
                    "WHERE user_id = %s AND status = 'RUNNING' AND run_type = 'scan' "
                    "ORDER BY started_at DESC LIMIT 1",
                    (user_id,),
                )
                row = cur.fetchone()
                if row:
                    return row["run_id"]
    except Exception:
        pass
    return None


def initiate_scan(user_id: str, db, mode: str = "default") -> str:
    """Create a background_run row and start the scan in a thread. Returns run_id.

    mode="default"   → cache-first brief (fast; used for the first/daily brief)
    mode="scan_more" → forced fresh discovery across job portals, streamed live,
                       deduped against the user's existing brief (no cache hit)

    Raises 409 if the user already has a RUNNING scan.
    """
    # ── Concurrency guard: one active scan per user ───────────────────────
    existing = _has_running_scan(user_id)
    if existing:
        logger.warning("Scan blocked: user %s already has RUNNING scan %s", user_id[:8], existing)
        raise APIError(
            f"A scan is already running (ID: {existing}). Please wait for it to complete.",
            status_code=409, code="scan_already_running",
        )

    # ── Global semaphore: at most 3 concurrent workers ────────────────────
    if not _worker_semaphore.acquire(blocking=False):
        logger.warning("Scan blocked: too many concurrent workers (max 3)")
        raise APIError(
            "Our job scanners are busy right now. Please try again in a few minutes.",
            status_code=503, code="scan_busy",
        )

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

    # Register in the active-scans tracker
    with _active_scans_lock:
        _active_scans[user_id] = run_id

    # Pass DATABASE_URL explicitly — threads don't inherit uvicorn env reliably
    import os as _os
    db_url = _os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.error("DATABASE_URL not set — scan worker will fail")

    thread = threading.Thread(
        target=_run_scan_worker,
        args=(user_id, run_id, db_url, mode),
        daemon=True,
    )
    thread.start()
    logger.info("Scan thread started for user %s run_id %s mode=%s", user_id[:8], run_id, mode)
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
    deadline = time.time() + 300  # 5-minute hard timeout
    # Watermark + dedupe: query only events at/after the last timestamp (bounds each
    # poll to O(new events), critical when scan_more emits dozens of events and for
    # many concurrent streams), and dedupe by event_id to handle equal timestamps.
    last_ts = None
    seen_event_ids: set = set()

    while time.time() < deadline:
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    if last_ts is None:
                        cur.execute(
                            "SELECT event_id, event_type, message, timestamp FROM careerloop.run_events "
                            "WHERE run_id = %s ORDER BY timestamp ASC",
                            (run_id,),
                        )
                    else:
                        cur.execute(
                            "SELECT event_id, event_type, message, timestamp FROM careerloop.run_events "
                            "WHERE run_id = %s AND timestamp >= %s ORDER BY timestamp ASC",
                            (run_id, last_ts),
                        )
                    rows = cur.fetchall()
                    for row in rows:
                        eid = str(row["event_id"])
                        if eid in seen_event_ids:
                            continue
                        seen_event_ids.add(eid)
                        if row.get("timestamp") is not None:
                            last_ts = row["timestamp"]
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
        logger.error("_emit failed for run %s (event_type=%s): %s", run_id, event_type, e)


def _mark_scan_failed(run_id: str, user_id: str, message: str):
    """Write a SCAN_FAILED event and mark the background_run as FAILED.

    Uses its own connection (called from worker thread or error handlers).
    """
    try:
        from careerloop.memory.connection import get_db_manager
        db = get_db_manager()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                _emit(cur, run_id, message[:200], "SCAN_FAILED")
                cur.execute(
                    "UPDATE careerloop.background_runs SET status = 'FAILED', updated_at = NOW() WHERE run_id = %s",
                    (run_id,),
                )
    except Exception:
        pass


def _cleanup_scan(run_id: str, user_id: str):
    """Release concurrency guards after scan completes (success or failure)."""
    with _active_scans_lock:
        if _active_scans.get(user_id) == run_id:
            del _active_scans[user_id]
    _worker_semaphore.release()
    logger.info("Scan cleanup: run_id=%s user=%s — guards released", run_id, user_id[:8])


def _run_scan_worker(user_id: str, run_id: str, db_url: str = "", mode: str = "default"):
    """
    Runs the scan pipeline in a background thread.
    Uses the SHARED DatabaseManager singleton (not a separate pool per thread).
    This prevents connection exhaustion — every thread shares the same pool.
    """
    import os as _os

    if not db_url:
        db_url = _os.environ.get("DATABASE_URL", "")

    if not db_url:
        logger.error("No DATABASE_URL in worker thread")
        _cleanup_scan(run_id, user_id)
        return

    try:
        # Use the shared DatabaseManager singleton — NOT a new instance per thread.
        # The singleton's ThreadedConnectionPool handles thread safety.
        from careerloop.memory.connection import get_db_manager
        db = get_db_manager()
    except Exception as e:
        logger.error("Worker DB singleton access failed: %s", e)
        _cleanup_scan(run_id, user_id)
        return

    try:
        if mode == "scan_more":
            _execute_scan_more(user_id, run_id, db)
        else:
            _execute_scan(user_id, run_id, db)
    except Exception as e:
        logger.exception("Scan worker fatal error for run %s: %s", run_id, e)
        _mark_scan_failed(run_id, user_id, f"Scan failed: {str(e)[:200]}")
    finally:
        _cleanup_scan(run_id, user_id)


def _build_from_cache(user_id: str, db, limit: int = 10) -> list:
    """Build a top_jobs list from the global jobs cache (cache-first behavior).

    Returns the same shape as DailyRunner's top_jobs: [{"job":..., "score":..., "breakdown":...}].
    Pulls fit_score / reasons from user_job_relationships when present, else sensible defaults.
    """
    rows = []
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT j.job_id, j.id AS legacy_id, j.title, j.company_name, j.location,
                           j.apply_url, j.role_summary, j.jd_text,
                           r.fit_score, r.route_recommendation
                    FROM careerloop.jobs j
                    LEFT JOIN careerloop.user_job_relationships r
                        ON r.job_id::text = j.job_id::text AND r.user_id::text = %s
                    WHERE COALESCE(j.status, 'active') = 'active'
                    ORDER BY COALESCE(r.fit_score, 0) DESC, j.scraped_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                rows = cur.fetchall()
    except Exception as e:
        logger.error("_build_from_cache failed: %s", e)
        return []

    top = []
    for row in rows:
        r = dict(row)
        score = float(r["fit_score"]) if r.get("fit_score") is not None else None
        if score is None:
            logger.warning("_build_from_cache: job '%s' has no fit_score — using default 65.0", r.get("title", "?"))
            score = 65.0
        top.append({
            "job": {
                "job_id": str(r.get("job_id")) if r.get("job_id") else r.get("legacy_id"),
                "id": r.get("legacy_id"),
                "title": r.get("title") or "",
                "company": r.get("company_name") or "",
                "location": r.get("location") or "",
                "apply_url": r.get("apply_url") or "",
            },
            "score": score,
            "breakdown": {
                "recommendation_reason": r.get("recommendation_reason") or "Matches your target roles and location.",
                "risk_summary": r.get("risk_summary") or "No critical risks identified.",
                "route_recommendation": r.get("route_recommendation") or "APPLY",
            },
        })
    return top


def _execute_scan_more(user_id: str, run_id: str, db):
    """Forced fresh discovery for "Scan More" — streamed live, deduped, no cache.

    Runs scan.mjs across the configured job portals and streams each company as
    it's scanned + each role found, in real time. Then scores net-new roles
    against the user's target roles and appends matches to today's brief.
    NO cache-hit shortcut — the user explicitly wants jobs beyond their brief.
    """
    import os
    import json as _json
    import subprocess
    import time as _time

    root = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))

    # 1. User's target roles (for real match/skip decisions) + existing brief dedupe set.
    target_roles, seen_keys = _load_targets_and_seen(user_id, db)

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            _emit(cur, run_id, "Hunting for fresh roles beyond your brief…", "SCAN_STARTED")
            _emit(cur, run_id, f"Scanning live job portals for: {', '.join(target_roles) or 'your targets'}", "SOURCE_STARTED")

    # 2. Run scan.mjs and stream its per-company output live.
    found_jobs = []
    scanned_count = 0
    emitted_scanned = 0
    SCANNED_EMIT_CAP = 60   # bound run_events rows; counter keeps progress honest
    buffer = []             # batched (event_type, message) for throttled writes
    last_flush = _time.time()

    def flush():
        nonlocal buffer, last_flush
        if not buffer:
            return
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    for et, msg in buffer:
                        _emit(cur, run_id, msg, et)
        except Exception as e:
            logger.error("scan_more flush failed for run %s: %s", run_id, e)
        buffer = []
        last_flush = _time.time()

    try:
        proc = subprocess.Popen(
            ["node", "scan.mjs"], cwd=root,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        for line in proc.stdout:
            line = line.strip()
            if not line.startswith("SCAN_EVENT::"):
                continue
            try:
                ev = _json.loads(line[len("SCAN_EVENT::"):])
            except Exception:
                continue
            if ev.get("t") == "scanned":
                scanned_count += 1
                if emitted_scanned < SCANNED_EMIT_CAP:
                    emitted_scanned += 1
                    buffer.append(("SOURCE_SCANNING", f"🔍 Scanned {ev.get('company','?')} — {ev.get('found',0)} roles"))
            elif ev.get("t") == "found":
                found_jobs.append(ev)
                buffer.append(("JOB_FOUND", f"Found: {ev.get('title','?')} @ {ev.get('company','?')}"))
            # Throttle DB writes: flush every ~0.5s or every 12 buffered events.
            if len(buffer) >= 12 or (_time.time() - last_flush) > 0.5:
                flush()
        proc.wait(timeout=120)
    except Exception as e:
        logger.error("scan_more discovery failed: %s", e)
    flush()

    # 3. Score net-new roles against target roles; dedupe vs existing brief.
    net_new = []
    for ev in found_jobs:
        title = (ev.get("title") or "").strip()
        company = (ev.get("company") or "").strip()
        key = f"{company.lower()}::{title.lower()}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        matched = _matches_targets(title, target_roles)
        if matched:
            net_new.append(ev)
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    _emit(cur, run_id, f"✓ {title} @ {company} — matches your targets", "JOB_EVALUATED")
        else:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    _emit(cur, run_id, f"✗ {title} @ {company} — off-target, skipped", "JOB_EVALUATED")

    # 4. Append net-new matches to today's brief (append, never wipe).
    appended = _append_to_brief(user_id, run_id, net_new, db)

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            _emit(cur, run_id,
                  f"Scanned {scanned_count} companies · {len(found_jobs)} roles seen · {appended} new matches added",
                  "FILTER_SUMMARY")
            if appended == 0:
                _emit(cur, run_id, "No new matches beyond your current brief right now.", "BRIEF_CREATED")
            else:
                _emit(cur, run_id, f"{appended} fresh roles added to your brief.", "BRIEF_CREATED")
            cur.execute(
                "UPDATE careerloop.background_runs SET status = 'COMPLETED', updated_at = NOW() WHERE run_id = %s",
                (run_id,),
            )
    logger.info("scan_more done: run=%s scanned=%d found=%d appended=%d", run_id, scanned_count, len(found_jobs), appended)


def _load_targets_and_seen(user_id: str, db):
    """Return (target_roles list, set of 'company::title' keys already in the user's brief)."""
    target_roles, seen = [], set()
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT target_roles FROM careerloop.users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if row and row.get("target_roles"):
                    raw = row["target_roles"]
                    if isinstance(raw, list):
                        target_roles = raw
                    elif isinstance(raw, str):
                        try:
                            import json as _j
                            parsed = _j.loads(raw)
                            target_roles = parsed if isinstance(parsed, list) else [p.strip() for p in raw.split(",") if p.strip()]
                        except Exception:
                            target_roles = [p.strip() for p in raw.split(",") if p.strip()]
                # existing brief items → dedupe set
                cur.execute(
                    """
                    SELECT bi.title, bi.company FROM careerloop.daily_brief_items bi
                    JOIN careerloop.daily_briefs b ON b.id = bi.brief_id
                    WHERE b.user_id = %s
                    """,
                    (user_id,),
                )
                for r in cur.fetchall():
                    seen.add(f"{(r.get('company') or '').lower()}::{(r.get('title') or '').lower()}")
    except Exception as e:
        logger.debug("_load_targets_and_seen failed: %s", e)
    return target_roles, seen


def _matches_targets(title: str, target_roles: list) -> bool:
    """Lightweight, real relevance check: title shares a keyword with a target role."""
    if not target_roles:
        return True  # no targets set → don't reject
    t = title.lower()
    for role in target_roles:
        for tok in str(role).lower().split():
            if len(tok) > 3 and tok in t:
                return True
    return False


def _compute_title_match_score(title: str, target_roles: list) -> float:
    """Compute a quick heuristic score (0-100) from title/target-role keyword overlap.

    Used in scan_more path where full job data (JD, salary, etc.) isn't available
    for the 15-dimension heuristic scorer.
    """
    if not target_roles or not title:
        return 65.0  # neutral default — no targets to match against
    t = title.lower()
    # Collect all non-trivial keywords from target roles
    all_keywords = set()
    for role in target_roles:
        for tok in str(role).lower().split():
            if len(tok) > 3:
                all_keywords.add(tok)
    if not all_keywords:
        return 65.0
    # How many target keywords appear in the title?
    matched = sum(1 for kw in all_keywords if kw in t)
    ratio = matched / len(all_keywords)
    # Scale: 0% match = 50, 50% match = 65, 100% match = 85
    return round(50.0 + ratio * 35.0, 1)


def _append_to_brief(user_id: str, run_id: str, jobs: list, db) -> int:
    """Append net-new matched jobs to today's brief (creating it if absent). Returns count added."""
    if not jobs:
        return 0
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    added = 0
    # Load target roles so we can compute real scores
    target_roles, _ = _load_targets_and_seen(user_id, db)
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM careerloop.daily_briefs WHERE user_id = %s AND date_str = %s ORDER BY created_at DESC LIMIT 1",
                    (user_id, today),
                )
                row = cur.fetchone()
                if row:
                    brief_id = row["id"]
                else:
                    brief_id = str(uuid.uuid4())
                    cur.execute(
                        "INSERT INTO careerloop.daily_briefs (id, user_id, date_str, run_id, summary) VALUES (%s,%s,%s,%s,%s)",
                        (brief_id, user_id, today, run_id, ""),
                    )
                cur.execute("SELECT COALESCE(MAX(item_index),0) AS mx FROM careerloop.daily_brief_items WHERE brief_id = %s", (brief_id,))
                idx = (cur.fetchone() or {}).get("mx", 0)
                for ev in jobs:
                    idx += 1
                    added += 1
                    score = _compute_title_match_score(ev.get("title", ""), target_roles)
                    cur.execute(
                        "INSERT INTO careerloop.daily_brief_items "
                        "(id, brief_id, item_index, job_id, title, company, location, fit_score, recommendation_reason, risk_summary, route_recommendation) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            str(uuid.uuid4()), brief_id, idx, str(uuid.uuid4()),
                            ev.get("title", ""), ev.get("company", ""), ev.get("location", ""),
                            score, "Fresh match from live portal scan.", "Newly discovered — verify details.", "APPLY",
                        ),
                    )
    except Exception as e:
        logger.error("_append_to_brief failed: %s", e)
    return added


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

    # Cache-first fallback: if the runner produced no fresh shortlist (already
    # generated today, or no NEW external jobs found), build the brief from the
    # global jobs cache so the user always sees real jobs from the DB.
    if not top_jobs:
        top_jobs = _build_from_cache(user_id, db)
        if top_jobs:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    _emit(cur, run_id, f"Surfacing {len(top_jobs)} matching roles from cache", "CACHE_HIT")

    # If there is genuinely nothing to show, keep any existing brief intact and stop.
    if not top_jobs:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                _emit(cur, run_id, "No matching roles found right now — try again later.", "FILTER_SUMMARY")
                cur.execute(
                    "UPDATE careerloop.background_runs SET status = 'COMPLETED', updated_at = NOW() WHERE run_id = %s",
                    (run_id,),
                )
        logger.info("Scan produced no jobs (cache empty): run_id=%s", run_id)
        return

    brief_id = str(uuid.uuid4())

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # Only now (we have items to write) clear today's old brief and rewrite.
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
