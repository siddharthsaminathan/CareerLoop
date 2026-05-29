"""Scans router — async scan + SSE event stream.

POST /v1/scans
  Start a scan. Returns run_id immediately. Scan runs in background.

GET /v1/scans/{run_id}/events
  SSE stream of scan events. Frontend connects here with EventSource.
  Each event: data: {"event_type": "...", "message": "...", "timestamp": "..."}
  Final event: data: {"event_type": "DONE", ...}

GET /v1/scans/{run_id}
  Scan status (RUNNING / COMPLETED / FAILED).

GET /v1/scans/latest
  Latest scan run_id for the authenticated user.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from careerloop_api.core.envelope import APIError, ok
from careerloop_api.deps.auth import get_current_user
from careerloop_api.deps.db import get_db
from careerloop_api.services.scan_service import (
    get_scan_status,
    initiate_scan,
    stream_scan_events,
)

router = APIRouter(prefix="/scans", tags=["scans"])


class ScanRequest(BaseModel):
    # "default"  → cache-first brief (fast)
    # "scan_more"→ forced fresh discovery across portals, streamed live, deduped
    mode: Optional[str] = "default"


@router.post("")
def start_scan(
    body: Optional[ScanRequest] = None,
    user_id: str = Depends(get_current_user),
    db=Depends(get_db),
):
    """Start a scan. Returns run_id immediately — scan runs in background.

    Body (optional): {"mode": "scan_more"} to force fresh portal discovery.
    The "Scan More" button must send mode="scan_more".
    """
    mode = (body.mode if body else "default") or "default"
    run_id = initiate_scan(user_id, db, mode=mode)
    return ok({"run_id": run_id, "status": "RUNNING", "mode": mode})


@router.get("/latest")
def latest_scan(user_id: str = Depends(get_current_user), db=Depends(get_db)):
    """Latest scan run for the authenticated user."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, status, started_at
                FROM careerloop.background_runs
                WHERE user_id = %s AND run_type = 'scan'
                ORDER BY started_at DESC LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
    if not row:
        raise APIError("No scan found.", status_code=404, code="no_scan")
    return ok(dict(row))


@router.get("/{run_id}")
def scan_status(run_id: str, user_id: str = Depends(get_current_user), db=Depends(get_db)):
    """Scan status for a specific run_id."""
    run = get_scan_status(run_id, db)
    if not run:
        raise APIError("Scan not found.", status_code=404, code="scan_not_found")
    return ok(run)


@router.get("/{run_id}/events")
def scan_events(run_id: str, user_id: str = Depends(get_current_user), db=Depends(get_db)):
    """
    SSE stream of scan events.

    Frontend usage:
        const es = new EventSource(`/v1/scans/${runId}/events`, {
            headers: { Authorization: `Bearer ${token}` }
        })
        es.onmessage = (e) => {
            const evt = JSON.parse(e.data)
            if (evt.event_type === 'DONE') { es.close(); fetchBrief() }
            else renderScanEvent(evt)
        }

    Event types:
        QUEUED           → scan is starting
        SCAN_STARTED     → discovery initialized
        SOURCE_STARTED   → searching portals
        CACHE_HIT        → found fresh cached jobs
        CANDIDATE_MATCHED→ "MATCH #1 — Title @ Company — Score/100"
        FILTER_SUMMARY   → "X raw, Y new, Z scored"
        BRIEF_CREATED    → brief is ready, call GET /v1/briefs/latest
        DONE             → stream complete, close EventSource
    """
    # Verify the scan exists (auth guard)
    run = get_scan_status(run_id, db)
    if not run:
        raise APIError("Scan not found.", status_code=404, code="scan_not_found")

    return StreamingResponse(
        stream_scan_events(run_id, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",      # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
