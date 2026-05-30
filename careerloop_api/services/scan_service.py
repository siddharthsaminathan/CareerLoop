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
  SCAN_STARTED        — "Starting job discovery..."
  SOURCE_STARTED      — "Searching configured portals..."
  CACHE_HIT           — "X fresh jobs found in global cache"
  JD_ENRICHED         — "Fetched full JD text for a job"
  JD_SNIPPET          — "Snippet only — full JD not available"
  SCORING_STARTED     — "Scoring N net-new jobs..."
  HEURISTIC_SCORING   — "Running IndiaFitEngine on N jobs..."
  HEURISTIC_SCORING_DONE — "N jobs scored"
  LLM_VALIDATION       — "Validating top N jobs with LLM..."
  LLM_VALIDATION_DONE  — "M/N jobs passed LLM validation"
  CANDIDATE_MATCHED   — "MATCH #1 — Title @ Company — Location — Score/100"
  FILTER_SUMMARY      — "X raw, Y new, Z scored"
  BRIEF_CREATED       — "Brief created with top matches."
  SCAN_FAILED         — error message
"""

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from typing import Generator, Optional

from careerloop.policies import is_india_location
from careerloop.india_fit_llm import LLMIndiaFitEngine

from careerloop_api.core.envelope import APIError

logger = logging.getLogger("careerloop_api.services.scan")

# ── Job persistence helpers ──────────────────────────────────────────────────────

# India city keywords used to tag is_india_role during job persistence.
_INDIA_CITY_KEYWORDS = frozenset([
    "india", "bangalore", "bengaluru", "mumbai", "bombay", "chennai", "madras",
    "delhi", "new delhi", "hyderabad", "pune", "gurgaon", "gurugram", "noida",
    "kolkata", "calcutta", "ahmedabad", "remote", "pan india", "pan-india",
    "anywhere in india",
])


def _phase_a_enabled() -> bool:
    """Phase A (employer discovery) is OFF by default — it adds 3-5 min before the
    first job and the user does not care about company discovery. Set ENABLE_PHASE_A=true
    to turn it back on."""
    return os.getenv("ENABLE_PHASE_A", "false").strip().lower() in ("1", "true", "yes", "on")


# Event types that represent a concrete job/match surfacing to the user.
_FIRST_JOB_EVENTS = {"JOB_FOUND", "SOURCE_SCANNING", "JD_ENRICHED", "JD_SNIPPET"}
_FIRST_MATCH_EVENTS = {"CANDIDATE_MATCHED", "JOB_EVALUATED"}
_BRIEF_EVENTS = {"BRIEF_CREATED"}


class _ScanMetrics:
    """Records responsiveness metrics for one scan. Success metric = TTFE < 2s.

    TTFE              — time to first event (any)
    time_to_first_job — time to first job-surfacing event
    time_to_first_match — time to first scored match
    time_to_brief     — time the brief was created
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.t0 = time.time()
        self.ttfe = None
        self.first_job = None
        self.first_match = None
        self.to_brief = None

    def observe(self, event_type: str):
        dt = time.time() - self.t0
        if self.ttfe is None:
            self.ttfe = dt
        et = (event_type or "").upper()
        if self.first_job is None and et in _FIRST_JOB_EVENTS:
            self.first_job = dt
        if self.first_match is None and et in _FIRST_MATCH_EVENTS:
            self.first_match = dt
        if self.to_brief is None and et in _BRIEF_EVENTS:
            self.to_brief = dt

    def log(self, extra: str = ""):
        def f(v):
            return f"{v:.2f}s" if v is not None else "—"
        logger.info(
            "SCAN_METRICS run=%s TTFE=%s time_to_first_job=%s time_to_first_match=%s time_to_brief=%s %s",
            self.run_id, f(self.ttfe), f(self.first_job), f(self.first_match), f(self.to_brief), extra,
        )


def _compute_job_fingerprint(job: dict) -> str:
    """Deterministic SHA-256 fingerprint from identity fields for dedup.

    Uses title + company_name + apply_url + url. Strips whitespace/lowercases.
    Returns first 40 hex chars — sufficient uniqueness for gigascale.
    """
    title = (job.get("title") or "").strip().lower()
    company = (job.get("company") or job.get("company_name") or "").strip().lower()
    apply_url = (job.get("apply_url") or job.get("url") or "").strip().lower()
    url = (job.get("url") or "").strip().lower()
    raw = f"{title}|{company}|{apply_url}|{url}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def _is_india_location(location: str) -> bool:
    """Check if a location string indicates an India-based role."""
    loc = (location or "").lower().strip()
    if not loc:
        return False
    return any(kw in loc for kw in _INDIA_CITY_KEYWORDS)


def _persist_scan_jobs(db, user_id: str, top_jobs: list) -> list:
    """Persist every discovered job to careerloop.jobs and create user_job_relationships.

    Each job is upserted by content_fingerprint (SHA-256 of title|company|url).
    Existing jobs get their metadata refreshed (last_seen_at, title, apply_url).
    Returns the same top_jobs list with real UUID ``job_id`` and ``id`` fields set
    on each job dict, so downstream brief creation uses correct FK references.

    Called once per scan run, BEFORE brief items are created.
    """
    from datetime import datetime, timezone
    log = logging.getLogger("careerloop_api.services.scan.persist")
    if not top_jobs:
        return top_jobs

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            for item in top_jobs:
                job = item.get("job", item)
                score = item.get("score")

                fp = _compute_job_fingerprint(job)
                title = (job.get("title") or "")[:500]
                company = (job.get("company") or job.get("company_name") or "")[:300]
                location = (job.get("location") or "")[:300]
                apply_url = (job.get("apply_url") or job.get("url") or "")[:1000]
                canonical_url = (job.get("url") or apply_url)[:1000]
                jd_text = (
                    job.get("description")
                    or job.get("jd_text")
                    or job.get("raw_jd_text")
                    or ""
                )[:50000]
                is_india = _is_india_location(location)

                cur.execute(
                    """
                    INSERT INTO careerloop.jobs (
                        id, source, title, company_name, location,
                        location_raw, apply_url, jd_text,
                        content_fingerprint, is_india_role, status,
                        scraped_at
                    ) VALUES (
                        gen_random_uuid(), %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, 'active',
                        NOW()
                    )
                    ON CONFLICT (content_fingerprint) DO UPDATE SET
                        title            = EXCLUDED.title,
                        company_name     = EXCLUDED.company_name,
                        location         = EXCLUDED.location,
                        location_raw     = EXCLUDED.location_raw,
                        apply_url        = EXCLUDED.apply_url,
                        jd_text          = EXCLUDED.jd_text,
                        scraped_at      = NOW(),
                        last_seen_at     = NOW(),
                        updated_at       = NOW()
                    RETURNING id
                    """,
                    (
                        "on_demand",
                        title,
                        company,
                        location,
                        location,
                        apply_url,
                        jd_text,
                        fp,
                        is_india,
                    ),
                )
                row = cur.fetchone()
                if row:
                    job_id = str(row["id"])
                else:
                    # Fallback: query by fingerprint (should not normally happen)
                    cur.execute(
                        "SELECT id FROM careerloop.jobs WHERE content_fingerprint = %s",
                        (fp,),
                    )
                    r2 = cur.fetchone()
                    job_id = str(r2["id"]) if r2 else str(uuid.uuid4())

                # Stamp the real UUID onto the job dict so downstream brief_items
                # and event emission use the canonical FK.
                job["job_id"] = job_id
                job["id"] = job_id  # v1 compat

                # Create user_job_relationship row
                cur.execute(
                    """
                    INSERT INTO careerloop.user_job_relationships
                        (user_id, job_id, match_status, fit_score,
                         user_seen_at, created_at, updated_at)
                    VALUES (%s, %s, 'matched', %s, NOW(), NOW(), NOW())
                    ON CONFLICT (user_id, job_id) DO UPDATE SET
                        fit_score  = EXCLUDED.fit_score,
                        updated_at = NOW()
                    """,
                    (user_id, job_id, score),
                )

    log.info(
        "Persisted %d jobs to careerloop.jobs for user %s",
        len(top_jobs),
        user_id[:8],
    )
    return top_jobs

# Per-user scan lock: prevents initiating a new scan while another is RUNNING.
_active_scans_lock = threading.Lock()
_active_scans: dict = {}  # user_id → run_id

# Global semaphore: at most 3 concurrent scan workers across ALL users.
# This prevents connection pool exhaustion (Supabase free tier = 15 conns).
_WORKER_LIMIT = 3
_worker_semaphore = threading.BoundedSemaphore(_WORKER_LIMIT)

# Live SSE stream registry — observability for /debug/runtime and leak detection.
# Incremented when a client opens GET /scans/{run_id}/events, decremented in the
# generator's finally (fires on normal completion AND on client disconnect/GC).
_active_streams_lock = threading.Lock()
_active_streams: dict = {}  # stream_uuid → {"run_id":..., "started": epoch}


def runtime_snapshot() -> dict:
    """Read-only snapshot of scan/stream runtime state for /debug/runtime."""
    with _active_scans_lock:
        scans = dict(_active_scans)
    with _active_streams_lock:
        streams = [
            {"run_id": v["run_id"], "age_s": round(time.time() - v["started"], 1)}
            for v in _active_streams.values()
        ]
    # BoundedSemaphore exposes its current value via the internal counter.
    try:
        free_workers = _worker_semaphore._value  # type: ignore[attr-defined]
    except Exception:
        free_workers = None
    return {
        "active_scans": scans,
        "active_scan_count": len(scans),
        "worker_slots_total": _WORKER_LIMIT,
        "worker_slots_free": free_workers,
        "worker_slots_in_use": (_WORKER_LIMIT - free_workers) if free_workers is not None else None,
        "active_sse_streams": len(streams),
        "sse_streams": streams,
    }

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

    stream_uid = uuid.uuid4().hex
    with _active_streams_lock:
        _active_streams[stream_uid] = {"run_id": run_id, "started": time.time()}
    try:
        yield from _stream_loop(run_id, db, deadline, last_ts, seen_event_ids)
    finally:
        with _active_streams_lock:
            _active_streams.pop(stream_uid, None)


def _stream_loop(run_id, db, deadline, last_ts, seen_event_ids):
    while time.time() < deadline:
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    if last_ts is None:
                        cur.execute(
                            "SELECT event_id, event_type, message, timestamp, payload FROM careerloop.run_events "
                            "WHERE run_id = %s ORDER BY timestamp ASC",
                            (run_id,),
                        )
                    else:
                        cur.execute(
                            "SELECT event_id, event_type, message, timestamp, payload FROM careerloop.run_events "
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
                        # Start with the structured payload from the DB (if any), then
                        # overlay event_type/message/timestamp so those always win.
                        raw_payload = row.get("payload")
                        if isinstance(raw_payload, str):
                            try:
                                raw_payload = json.loads(raw_payload)
                            except Exception:
                                raw_payload = None
                        payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
                        payload["event_type"] = row.get("event_type") or "info"
                        payload["message"] = row.get("message") or ""
                        payload["timestamp"] = row["timestamp"].isoformat() if hasattr(row.get("timestamp"), "isoformat") else str(row.get("timestamp", ""))
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

def _emit(cur, run_id: str, message: str, event_type: str = "info", payload: dict = None):
    """Write a run_event row. Must be called within an open cursor."""
    try:
        cur.execute(
            "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type, payload) VALUES (%s, %s, %s, %s, %s)",
            (str(uuid.uuid4()), run_id, message, event_type, json.dumps(payload) if payload else None),
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
                      AND (j.location ILIKE '%india%'
                           OR j.location ILIKE '%bangalore%'
                           OR j.location ILIKE '%bengaluru%'
                           OR j.location ILIKE '%chennai%'
                           OR j.location ILIKE '%mumbai%'
                           OR j.location ILIKE '%delhi%'
                           OR j.location ILIKE '%hyderabad%'
                           OR j.location ILIKE '%pune%'
                           OR j.location ILIKE '%gurgaon%'
                           OR j.location ILIKE '%noida%'
                           OR j.location IS NULL)
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
            logger.warning("_build_from_cache: job '%s' has no fit_score — skipping (will be rescored on next full scan)", r.get("title", "?"))
            continue  # skip unscored; IndiaFitEngine will score on next full scan
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
    """Forced fresh discovery for "Scan More" — via OnDemandSearch pipeline.

    Replaces the old subprocess-based scan.mjs path. Uses the canonical
    OnDemandSearch discovery engine (Phase A + Phase B + filtering + scoring)
    and streams structured SSE events from each pipeline stage. Net-new matches
    are appended to today's brief (append, never wipe). NO cache shortcut —
    the user explicitly wants jobs beyond their brief.
    """
    import json
    import time as _time

    root = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))

    # 1. User's target roles + existing brief dedupe set
    target_roles, seen_keys = _load_targets_and_seen(user_id, db)
    if not target_roles:
        target_roles = ["AI Engineer"]  # sensible fallback

    # 2. Preferred city from user profile (work_style_prefs)
    city = ""
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT work_style_prefs FROM careerloop.users WHERE id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                if row and row.get("work_style_prefs"):
                    raw = row["work_style_prefs"]
                    prefs = json.loads(raw) if isinstance(raw, str) else raw
                    city = prefs.get("city", "") or prefs.get("location", "") or ""
    except Exception:
        pass
    if not city:
        city = "Bangalore"

    # 3. Direct event emitter — writes to DB immediately on each call, and
    #    records TTFE responsiveness metrics (success metric: TTFE < 2s).
    metrics = _ScanMetrics(run_id)

    def _event_emitter(event_type: str, message: str, payload: dict = None):
        """Write event to run_events IMMEDIATELY — no buffering, no delay."""
        metrics.observe(event_type)
        try:
            with db.get_connection() as emit_conn:
                with emit_conn.cursor() as emit_cur:
                    _emit(emit_cur, run_id, message, event_type, payload or {})
        except Exception:
            pass  # Non-fatal — scan continues even if event logging fails

    # 4. Kick off SCAN_STARTED — event_emitter writes immediately (this is TTFE)
    _event_emitter("SCAN_STARTED",
        f"Scanning for: {', '.join(target_roles)} in {city}",
        {"event_type": "SCAN_STARTED", "mode": "scan_more",
         "target_roles": target_roles, "city": city})

    # 5. Run OnDemandSearch — the canonical discovery engine.
    #    Phase A (employer discovery) is the 3-5 min TTFE killer. It is feature-
    #    flagged OFF by default. scan_more runs Phase B (board search) only, which
    #    streams jobs in seconds. To re-enable Phase A: set ENABLE_PHASE_A=true in
    #    the environment (.env). See docs — disabling it is the responsiveness fix.
    from careerloop.on_demand import OnDemandSearch

    primary_role = target_roles[0]
    ods = OnDemandSearch(root)
    try:
        result = ods.run(
            role=primary_role,
            city=city,
            max_results=10,
            portal_companies=20,
            include_boards=True,
            include_phase_a=_phase_a_enabled(),  # default False — board search only
            event_emitter=_event_emitter,
        )
    except Exception as e:
        logger.exception("OnDemandSearch failed for scan_more run %s: %s", run_id, e)
        _mark_scan_failed(run_id, user_id, f"Scan failed: {str(e)[:200]}")
        return

    # 6. Dedupe ranked jobs against existing brief items (keep full scored items)
    net_new_items = []
    for item in result.ranked_jobs:
        job = item.get("job", item)
        comp = (job.get("company") or job.get("company_name") or "").lower().strip()
        title = (job.get("title") or "").lower().strip()
        key = f"{comp}::{title}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        net_new_items.append(item)  # keep score + breakdown

    # 7. Append net-new matches to today's brief (pre-scored by IndiaFitEngine + LLM)
    appended = _append_to_brief(user_id, run_id, net_new_items, db)

    # 8. Finalize — summary event + mark COMPLETED
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            filter_payload = {
                "event": "FILTER_SUMMARY",
                "candidates": result.candidate_count,
                "after_dedup": result.after_dedup_count,
                "net_new_matches": appended,
                "source": "on_demand_search",
            }
            _emit(cur, run_id,
                  f"Discovery: {result.candidate_count} candidates · "
                  f"{result.after_dedup_count} after dedup · {appended} net-new matches",
                  "FILTER_SUMMARY", filter_payload)
            if appended == 0:
                _emit(cur, run_id, "No new matches beyond your current brief right now.", "BRIEF_CREATED",
                      {"event": "BRIEF_CREATED", "new_matches": 0})
            else:
                _emit(cur, run_id, f"{appended} fresh roles added to your brief.", "BRIEF_CREATED",
                      {"event": "BRIEF_CREATED", "new_matches": appended})
            cur.execute(
                "UPDATE careerloop.background_runs SET status = 'COMPLETED', updated_at = NOW() WHERE run_id = %s",
                (run_id,),
            )
    if metrics.to_brief is None:
        metrics.to_brief = time.time() - metrics.t0
    metrics.log(extra=f"phase_a={_phase_a_enabled()} candidates={result.candidate_count} appended={appended}")
    logger.info("scan_more (OnDemandSearch) done: run=%s candidates=%d appended=%d",
                run_id, result.candidate_count, appended)



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


def _score_scan_more_jobs(jobs: list[dict], run_id: str, root: str, db, role: str = "") -> list[dict]:
    """
    Score scan_more net-new jobs with IndiaFitEngine heuristic + LLM DeepSeek validation.

    For each job from scan.mjs (title/company/location/URL only), attempts to fetch
    full JD text via generic HTTP extraction. Jobs that lack JD text receive a
    conservative default score from IndiaFitEngine on title+company+location alone.

    Returns scored_items in format [{"job": {...}, "score": N, "breakdown": {...}}, ...].
    """
    if not jobs:
        return []

    # SSE: scoring started
    try:
        from careerloop.on_demand import OnDemandSearch
        on_demand = OnDemandSearch(root)
    except Exception as e:
        logger.error("_score_scan_more_jobs: failed to create OnDemandSearch: %s", e)
        # Fallback: return jobs with a neutral score so brief creation still works
        return [{"job": j, "score": 50.0, "breakdown": {}} for j in jobs]

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            _emit(cur, run_id, f"Scoring {len(jobs)} net-new roles with IndiaFitEngine...",
                  "SCORING_STARTED", {"event": "SCORING_STARTED", "candidates": len(jobs)})

    # Step 1: Enrich each job with JD text (fetch URL → generic HTTP extraction)
    enriched = []
    enrich_ok = 0
    for ev in jobs:
        url = (ev.get("url") or ev.get("apply_url") or "").strip()
        enriched_jd = None
        if url and url.startswith("http"):
            enriched_jd = on_demand._extract_generic_jd(url, fallback_title=ev.get("title", ""))
        if enriched_jd:
            enriched_jd["company"] = ev.get("company", enriched_jd.get("company", ""))
            enriched_jd["location"] = ev.get("location", enriched_jd.get("location", ""))
            enriched_jd["apply_url"] = url
            enriched_jd["url"] = url
            enriched_jd["_source_type"] = "scan_more_enriched"
            job_dict = enriched_jd
            enrich_ok += 1
        else:
            # Keep as-is with available fields — IndiaFitEngine scores conservatively on partial data
            job_dict = {
                "title": ev.get("title", ""),
                "company": ev.get("company", ""),
                "location": ev.get("location", ""),
                "url": url,
                "apply_url": url,
                "_source_type": "scan_more_snippet",
            }
        enriched.append(job_dict)
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                _emit(cur, run_id,
                      f"{'Enriched' if enriched_jd else 'Snippet'}: {ev.get('title','?')} @ {ev.get('company','?')}",
                      "JD_ENRICHED" if enriched_jd else "JD_SNIPPET",
                      {"event": "JD_ENRICHED" if enriched_jd else "JD_SNIPPET",
                       "job_title": ev.get("title", ""),
                       "company": ev.get("company", "")})

    # SSE: heuristic scoring
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            _emit(cur, run_id, f"Running IndiaFitEngine on {len(enriched)} jobs ({enrich_ok} with full JD)...",
                  "HEURISTIC_SCORING",
                  {"event": "HEURISTIC_SCORING", "candidates": len(enriched), "full_jd": enrich_ok})

    # Step 2: Score with IndiaFitEngine
    scored = on_demand.fit_engine.score_jobs_batch(enriched)

    # SSE: heuristic scoring complete
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            _emit(cur, run_id, f"IndiaFitEngine scored {len(scored)} jobs.",
                  "HEURISTIC_SCORING_DONE",
                  {"event": "HEURISTIC_SCORING_DONE", "scored": len(scored)})

    # Step 3: LLM validation on top 60 (single batch call, fast — ~5-10s)
    if role and scored:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                _emit(cur, run_id, f"Validating top {min(60, len(scored))} jobs with LLM...",
                      "LLM_VALIDATION",
                      {"event": "LLM_VALIDATION", "candidates": min(60, len(scored))})
        try:
            pre_llm = len(scored)
            validated = on_demand._llm_validate(scored[:60], role=role) + scored[60:]
            llm_rejected = pre_llm - len(validated)
        except Exception as e:
            logger.debug("_score_scan_more_jobs: LLM validate skipped: %s", e)
            validated = scored
            llm_rejected = 0
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                _emit(cur, run_id,
                      f"LLM validation: {len(validated)}/{len(scored)} jobs passed (rejected {llm_rejected}).",
                      "LLM_VALIDATION_DONE",
                      {"event": "LLM_VALIDATION_DONE", "input": len(scored), "output": len(validated)})
    else:
        validated = scored

    return validated


def _append_to_brief(user_id: str, run_id: str, scored_items: list, db) -> int:
    """Append net-new matched jobs to today's brief (creating it if absent). Returns count added.

    Accepts scored_items in the same format as IndiaFitEngine.score_jobs_batch output:
        [{"job": {..., "job_id": ...}, "score": 85.0, "breakdown": {...}}, ...]
    Each item must have a "job" dict and a "score" float.
    Persists each job to careerloop.jobs (idempotent by content_fingerprint)
    and creates user_job_relationships before appending to the brief.
    """
    if not scored_items:
        return 0
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    added = 0

    # ── Persist each job to careerloop.jobs ────────────────────────────────
    scan_more_items = _persist_scan_jobs(db, user_id, scored_items)
    # After _persist_scan_jobs, each job dict has real job_id set.

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
                for item in scan_more_items:
                    ev = item["job"]
                    score = item["score"]
                    idx += 1
                    added += 1
                    job_id = ev.get("job_id") or ev.get("id") or str(uuid.uuid4())
                    co = ev.get("company", "") or ev.get("company_name", "")
                    loc = ev.get("location", "")
                    # DATA QUALITY: safety net — infer company from title/URL if still empty
                    if not co:
                        try:
                            from careerloop.on_demand import _infer_company_from_title, _infer_company_from_url
                            co = _infer_company_from_title(ev.get("title", "")) or _infer_company_from_url(ev.get("apply_url", "") or ev.get("url", ""))
                        except ImportError:
                            pass
                    if not loc:
                        loc = "India"
                    cur.execute(
                        "INSERT INTO careerloop.daily_brief_items "
                        "(id, brief_id, item_index, job_id, title, company, location, fit_score, recommendation_reason, risk_summary, route_recommendation) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            str(uuid.uuid4()), brief_id, idx, str(job_id),
                            ev.get("title", ""), co, loc,
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
    from careerloop.on_demand import OnDemandSearch

    # P0: Prevent duplicate scan while another is running for this user
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM careerloop.background_runs WHERE user_id = %s AND run_type = 'scan' AND status = 'RUNNING' AND run_id != %s",
                    (user_id, run_id),
                )
                if cur.fetchone()[0] > 0:
                    _mark_scan_failed(run_id, user_id, "Concurrent scan prevented")
                    return
    except Exception:
        pass

    # scan_service.py lives at careerloop_api/services/ → go up 2 levels to repo root
    root = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    today_str = datetime.now(timezone.utc).date().isoformat()

    # ── SCAN STARTED event ──────────────────────────────────────────────
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            _emit(cur, run_id, "Starting job discovery...", "SCAN_STARTED", {"event": "SCAN_STARTED", "mode": "default"})

    # ── Load user profile from DB ───────────────────────────────────────
    import json as _json
    target_role = ""
    target_city = ""
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT target_roles, location_city FROM careerloop.users WHERE id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                if row:
                    raw_roles = row.get("target_roles", [])
                    if isinstance(raw_roles, list) and len(raw_roles) > 0:
                        target_role = raw_roles[0]
                    elif isinstance(raw_roles, str):
                        try:
                            parsed = _json.loads(raw_roles)
                            target_role = parsed[0] if isinstance(parsed, list) and len(parsed) > 0 else raw_roles
                        except Exception:
                            target_role = raw_roles.split(",")[0].strip()
                    target_city = row.get("location_city") or ""
    except Exception as e:
        logger.error("_execute_scan: failed to load user profile from DB: %s", e)

    if not target_role:
        logger.warning("_execute_scan: no target role found for user %s", user_id[:8])
        # Fallback: try the current file-based profile
        try:
            from careerloop.profile_manager import ProfileManager as _PM
            _pm = _PM(root)
            target_role = (_pm.target_roles or ["software engineer"])[0]
            target_city = _pm.location_city or ""
        except Exception:
            target_role = "software engineer"

    # ── SOURCE STARTED event ────────────────────────────────────────────
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            _emit(cur, run_id,
                  f"Searching job portals for: {target_role} in {target_city}",
                  "SOURCE_STARTED",
                  {"event": "SOURCE_STARTED", "role": target_role, "city": target_city, "mode": "default"})

    # ── Run canonical discovery engine ──────────────────────────────────
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            _emit(cur, run_id,
                  f"Phase A: discovering employers for '{target_role}' in {target_city}...",
                  "PHASE_A_STARTED",
                  {"event": "PHASE_A_STARTED", "role": target_role, "city": target_city})

    # Direct-write emitter: every OnDemandSearch event reaches DB immediately
    def _scan_emitter(event_type: str, message: str, payload: dict = None):
        try:
            with db.get_connection() as emit_conn:
                with emit_conn.cursor() as emit_cur:
                    _emit(emit_cur, run_id, message, event_type, payload or {})
        except Exception:
            pass

    searcher = OnDemandSearch(root)
    result = searcher.run(
        role=target_role,
        city=target_city,
        max_results=25,
        include_phase_a=True,
        event_emitter=_scan_emitter,
    )

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            _emit(cur, run_id,
                  f"Phase A complete: discovered {len(result.targeted_companies)} employers with {result.candidate_count} raw jobs",
                  "PHASE_A_COMPLETED",
                  {"event": "PHASE_A_COMPLETED", "companies_found": len(result.targeted_companies), "raw_jobs": result.candidate_count,
                   "elapsed_seconds": result.elapsed_seconds})

    # ── Extract results ─────────────────────────────────────────────────
    top_jobs = result.ranked_jobs
    new_jobs = result.candidate_count
    unique_added = result.after_dedup_count
    scored = len(top_jobs)

    # ── Emit JOB_FOUND + JOB_EVALUATED for each ranked job ───────────────
    for item in top_jobs:
        job = item.get("job", item)
        title = job.get("title", "?")
        company = job.get("company", "") or job.get("company_name", "") or "?"
        loc = job.get("location", "?")
        score = item.get("score", 0)
        job_payload = {
            "event": "JOB_FOUND",
            "job_title": title,
            "company": company,
            "location": loc,
        }
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                _emit(cur, run_id, f"Found: {title} @ {company}", "JOB_FOUND", job_payload)
                eval_payload = {
                    "event": "JOB_EVALUATED",
                    "job_title": title,
                    "company": company,
                    "location": loc,
                    "fit_score": score,
                    "rejection_reason": None,
                }
                _emit(cur, run_id, f"MATCH: {title} @ {company} — score: {score:.0f}/100", "JOB_EVALUATED", eval_payload)

    # ── LLMIndiaFitEngine deep scoring (top 5 only — single calls, ~15s total) ─
    if top_jobs and target_role:
        from careerloop.models import JobPosting
        _llm_profile = {
            "target_roles": [target_role],
            "confirmed_skills": getattr(searcher.profile, "confirmed_skills", []),
            "weak_skills": getattr(searcher.profile, "weak_skills", []),
            "rejected_roles": getattr(searcher.profile, "rejected_roles", []),
            "rejected_company_types": getattr(searcher.profile, "rejected_company_types", []),
            "preferred_company_types": getattr(searcher.profile, "preferred_company_types", []),
            "notice_period_days": getattr(searcher.profile, "notice_period_days", 30),
            "salary_floor_lakhs": getattr(searcher.profile, "salary_floor_lakhs", 0),
            "expected_ctc_lakhs": getattr(searcher.profile, "expected_ctc_lakhs", 0),
            "startup_tolerance": getattr(searcher.profile, "startup_tolerance", 5),
            "assignment_burden_tolerance": getattr(searcher.profile, "assignment_burden_tolerance", 5),
            "location_city": target_city,
            "location_flexibility": getattr(searcher.profile, "location_flexibility", ""),
        }
        _llm_candidates = top_jobs[:5]
        _llm_posting_list = []
        for item in _llm_candidates:
            j = item.get("job", item)
            _llm_posting_list.append(JobPosting(
                source=j.get("_source_type", "on_demand_scan"),
                source_url=j.get("url", "") or j.get("apply_url", ""),
                company=j.get("company", "") or j.get("company_name", ""),
                role_title=j.get("title", ""),
                location=j.get("location", ""),
                application_url=j.get("apply_url", "") or j.get("url", ""),
                raw_description=j.get("description", "") or j.get("jd_text", "") or "",
                work_mode=j.get("work_mode", ""),
                salary_range=j.get("salary", "") or j.get("salary_text", ""),
                skills_required=j.get("skills", []),
            ))
        try:
            _llm_engine = LLMIndiaFitEngine()
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    _emit(cur, run_id, f"Deep LLM scoring {len(_llm_posting_list)} top jobs...",
                          "LLM_VALIDATION",
                          {"event": "LLM_VALIDATION", "candidates": len(_llm_posting_list), "mode": "deep_score"})
            _llm_results = _llm_engine.score_batch(_llm_posting_list, _llm_profile,
                                                    min_heuristic_score=50)
            # Merge LLM scores back into top_jobs
            for llm_r in _llm_results:
                fp = llm_r.get("_job_fingerprint", "")
                for item in _llm_candidates:
                    j = item.get("job", item)
                    if fp and (j.get("url", "") + j.get("title", "")).encode("utf-8").hex()[:16] == fp:
                        item["llm_score"] = llm_r.get("overall_score", item.get("score", 0))
                        item["llm_detail"] = llm_r
                        break
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    _emit(cur, run_id, f"Deep LLM scoring complete for {len(_llm_results)} jobs.",
                          "LLM_VALIDATION_DONE",
                          {"event": "LLM_VALIDATION_DONE", "scored": len(_llm_results)})
        except Exception as e:
            logger.debug("_execute_scan: LLMIndiaFitEngine deep scoring skipped: %s", e)

    # ── Persist jobs to careerloop.jobs + user_job_relationships ──────────
    _persist_scan_jobs(db, user_id, top_jobs)

    # ── Cache-hit check (supplementary — may surface additional cached jobs) ──
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
                        raw = row["work_style_prefs"]
                        prefs = _json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    pass

        cached = get_fresh_cached_jobs(prefs, freshness_window_days=14, limit=20)
        if len(cached) >= 5:
            cache_payload = {
                "event": "CACHE_HIT",
                "cached_count": len(cached),
                "source": "global_jobs_cache",
            }
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    _emit(cur, run_id, f"Cache-hit: {len(cached)} fresh jobs found in global cache", "CACHE_HIT", cache_payload)
    except Exception as e:
        logger.debug("Cache-hit check skipped: %s", e)

    # Cache-first fallback: if the runner produced no fresh shortlist (already
    # generated today, or no NEW external jobs found), build the brief from the
    # global jobs cache so the user always sees real jobs from the DB.
    if not top_jobs:
        top_jobs = _build_from_cache(user_id, db)
        if top_jobs:
            cache_fallback_payload = {
                "event": "CACHE_HIT",
                "cached_count": len(top_jobs),
                "source": "cache_fallback",
            }
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    _emit(cur, run_id, f"Surfacing {len(top_jobs)} matching roles from cache", "CACHE_HIT", cache_fallback_payload)
            # Cache-fallback jobs already exist in careerloop.jobs but need
            # user_job_relationships rows created. Idempotent ON CONFLICT.
            _persist_scan_jobs(db, user_id, top_jobs)

    # If there is genuinely nothing to show, keep any existing brief intact and stop.
    if not top_jobs:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                _emit(cur, run_id, "No matching roles found right now — try again later.", "FILTER_SUMMARY",
                      {"event": "FILTER_SUMMARY", "raw_jobs": 0, "unique_added": 0, "scored": 0})
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
                (brief_id, user_id, today_str, run_id, f"On-demand search: {target_role} in {target_city} — {len(top_jobs)} matches"),
            )

            for idx, item in enumerate(top_jobs, 1):
                job = item["job"]
                score = item["score"]
                bd = item.get("breakdown", {})
                job_id = job.get("job_id") or job.get("id") or str(uuid.uuid4())

                title = job.get("title", "")
                company = job.get("company", "") or job.get("company_name", "")
                location = job.get("location", "")

                # DATA QUALITY: Parse "Company is hiring Title in Location | Source" patterns
                # (Cutshort, LinkedIn, and many Indian job boards use this format)
                m = re.match(r"(.+?)\s+is\s+hiring\s+(.+?)(?:\s+job)?\s+in\s+(.+?)(?:\s*\|.+)?$", title, re.IGNORECASE)
                if m:
                    parsed_co = m.group(1).strip()
                    parsed_title = m.group(2).strip()
                    parsed_loc = m.group(3).strip().split("|")[0].strip()
                    if not company:
                        company = parsed_co
                    if len(parsed_title) > 3:
                        title = parsed_title
                    if not location:
                        location = parsed_loc

                # DATA QUALITY: Safety net — infer company from title/URL if still empty
                if not company:
                    try:
                        from careerloop.on_demand import _infer_company_from_title, _infer_company_from_url
                        co_url = job.get("apply_url", "") or job.get("url", "")
                        company = _infer_company_from_title(title) or _infer_company_from_url(co_url)
                    except ImportError:
                        pass
                if not location:
                    location = "India"

                cur.execute(
                    "INSERT INTO careerloop.daily_brief_items "
                    "(id, brief_id, item_index, job_id, title, company, location, fit_score, recommendation_reason, risk_summary, route_recommendation) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        str(uuid.uuid4()), brief_id, idx, str(job_id),
                        title, company, location,
                        score,
                        bd.get("recommendation_reason") or bd.get("reason") or "Strong match.",
                        bd.get("risk_summary") or bd.get("risks") or "No critical risks.",
                        bd.get("route_recommendation") or bd.get("outreach") or "APPLY",
                    ),
                )
                # Emit match event — frontend shows each as it arrives
                match_payload = {
                    "event": "CANDIDATE_MATCHED",
                    "job_title": title,
                    "company": company,
                    "location": location,
                    "fit_score": score,
                    "match_index": idx,
                }
                _emit(cur, run_id, f"MATCH #{idx} — {title} @ {company} ({location}) — {score:.0f}/100", "CANDIDATE_MATCHED", match_payload)

            # Summary events
            _emit(cur, run_id, f"Scan complete: {new_jobs} raw jobs found, {unique_added} new, {scored} scored", "FILTER_SUMMARY",
                  {"event": "FILTER_SUMMARY", "raw_jobs": new_jobs, "unique_added": unique_added, "scored": scored})
            _emit(cur, run_id, "Brief created with top matches.", "BRIEF_CREATED",
                  {"event": "BRIEF_CREATED", "top_matches": len(top_jobs)})
            cur.execute(
                "UPDATE careerloop.background_runs SET status = 'COMPLETED', updated_at = NOW() WHERE run_id = %s",
                (run_id,),
            )

    logger.info("Scan completed: run_id=%s user=%s top_jobs=%d", run_id, user_id[:8], len(top_jobs))
