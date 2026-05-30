"""Forensic trace of ONE scan_more, run in-process. No source edits.

- Monkeypatches key functions with enter/exit timing.
- Runs the real _execute_scan_more in a worker thread.
- If the worker hasn't finished, dumps its EXACT stack (file:line) at intervals.
- Snapshots DB pg_stat_activity + run_events alongside.
Output: a timeline with T+ms, durations, success/failure, and the blocking line.
"""
import os, sys, time, threading, traceback, json

T0 = time.time()
EVENTS = []
_lock = threading.Lock()

def log(msg):
    t = (time.time() - T0) * 1000
    line = f"T+{t:8.1f}ms  {msg}"
    with _lock:
        EVENTS.append(line)
    print(line, flush=True)

def wrap(obj, name, label=None):
    """Monkeypatch obj.name to log enter/exit/duration/exception."""
    label = label or name
    orig = getattr(obj, name)
    def timed(*a, **k):
        log(f"┏━ ENTER {label}")
        s = time.time()
        try:
            r = orig(*a, **k)
            log(f"┗━ EXIT  {label}  dur={ (time.time()-s)*1000:.1f}ms  OK")
            return r
        except Exception as e:
            log(f"┗━ FAIL  {label}  dur={ (time.time()-s)*1000:.1f}ms  EXC={type(e).__name__}: {str(e)[:160]}")
            raise
    setattr(obj, name, timed)

def main():
    from dotenv import dotenv_values
    vals = dotenv_values("/Users/siddharthsaminathan/Projects/CareerLoop/.env")
    for kk, vv in vals.items():
        os.environ.setdefault(kk, vv)

    user_id = sys.argv[1] if len(sys.argv) > 1 else "730d5bab-0000-0000-0000-000000000000"
    log(f"START trace user={user_id[:8]} mode=scan_more")

    from careerloop.memory.connection import get_db_manager
    import careerloop_api.services.scan_service as ss
    from careerloop.on_demand import OnDemandSearch
    from careerloop.india_fit_engine import IndiaFitEngine

    # ── instrument ────────────────────────────────────────────────
    wrap(OnDemandSearch, "run", "OnDemandSearch.run")
    for m in ("_extract_generic_jd", "_llm_validate"):
        if hasattr(OnDemandSearch, m):
            wrap(OnDemandSearch, m, f"OnDemandSearch.{m}")
    if hasattr(IndiaFitEngine, "score_jobs_batch"):
        wrap(IndiaFitEngine, "score_jobs_batch", "IndiaFitEngine.score_jobs_batch")
    wrap(ss, "_append_to_brief", "_append_to_brief")
    wrap(ss, "_persist_scan_jobs", "_persist_scan_jobs")
    wrap(ss, "_load_targets_and_seen", "_load_targets_and_seen")

    db = get_db_manager()

    # Create the background_run row (what initiate_scan does synchronously)
    import uuid
    run_id = uuid.uuid4().hex[:12]
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO careerloop.background_runs (run_id, user_id, run_type, status, started_at) "
                "VALUES (%s,%s,'scan','RUNNING',NOW())", (run_id, user_id))
    log(f"background_run inserted run_id={run_id}")

    # ── run the real worker body in a thread ─────────────────────
    done = threading.Event()
    err = [None]
    def worker():
        try:
            ss._execute_scan_more(user_id, run_id, db)
        except Exception as e:
            err[0] = e
            log(f"WORKER EXCEPTION: {type(e).__name__}: {str(e)[:200]}")
        finally:
            done.set()
    wt = threading.Thread(target=worker, name="ScanWorker", daemon=True)
    wt.start()

    def dump_worker_stack(tag):
        frames = sys._current_frames()
        fr = frames.get(wt.ident)
        log(f"════ THREAD STACK DUMP [{tag}] — worker alive={wt.is_alive()} ════")
        if fr:
            for ln in traceback.format_stack(fr):
                for sub in ln.rstrip().split("\n"):
                    print("    " + sub, flush=True)
        else:
            log("  (no frame — worker finished)")

    def db_snapshot(tag):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            c = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=5, cursor_factory=RealDictCursor); c.autocommit=True
            cu = c.cursor()
            cu.execute("SELECT count(*) n, state FROM pg_stat_activity WHERE usename=current_user GROUP BY state")
            st = cu.fetchall()
            cu.execute("SELECT count(*) n FROM careerloop.run_events WHERE run_id=%s", (run_id,))
            ev = cu.fetchone()["n"]
            cu.execute("SELECT status FROM careerloop.background_runs WHERE run_id=%s", (run_id,))
            status = cu.fetchone()["status"]
            c.close()
            log(f"DB[{tag}] run_status={status} run_events={ev} conns_by_state={[(r['n'],r['state']) for r in st]}")
        except Exception as e:
            log(f"DB[{tag}] snapshot err: {str(e)[:120]}")

    deadline = 150
    checkpoints = {15, 30, 45, 60, 90, 120}
    last = 0
    while not done.wait(timeout=1):
        el = int(time.time() - T0)
        if el != last:
            last = el
            if el in checkpoints:
                db_snapshot(f"{el}s")
                dump_worker_stack(f"{el}s")
        if el >= deadline:
            log(f"DEADLINE {deadline}s reached — worker still alive={wt.is_alive()}")
            dump_worker_stack("FINAL")
            db_snapshot("FINAL")
            break

    if done.is_set():
        log(f"WORKER FINISHED  total={ (time.time()-T0)*1000:.1f}ms  err={err[0]}")
        db_snapshot("after-finish")

    # ── Raw SSE capture + structured-field verification ──────────────
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        c = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=5, cursor_factory=RealDictCursor); c.autocommit=True
        cu = c.cursor()
        cu.execute("SELECT event_type, message, payload, timestamp FROM careerloop.run_events WHERE run_id=%s ORDER BY timestamp", (run_id,))
        rows = cu.fetchall(); c.close()
        cap_path = f"/Users/siddharthsaminathan/Projects/CareerLoop/logs/sse_capture_{run_id}.txt"
        REQUIRED = ("job_title", "company", "location", "fit_score")
        job_events = 0; field_fail = 0
        with open(cap_path, "w") as f:
            f.write(f"# Raw SSE stream — run {run_id} — {len(rows)} events\n\n")
            prev = None
            for r in rows:
                p = r["payload"]
                if isinstance(p, str):
                    try: p = json.loads(p)
                    except Exception: p = {}
                p = p or {}
                ts = r["timestamp"]
                gap = (ts - prev).total_seconds() if prev else 0.0
                prev = ts
                f.write(f"data: {json.dumps({'event_type': r['event_type'], 'message': r['message'], **p})}\n")
                f.write(f"   [+{gap:5.2f}s]\n\n")
                if (r["event_type"] or "").upper() in ("CANDIDATE_MATCHED", "JOB_EVALUATED"):
                    job_events += 1
                    missing = [k for k in REQUIRED if k not in p or p.get(k) in (None, "")]
                    if missing:
                        field_fail += 1
                        f.write(f"   ✗ MISSING FIELDS: {missing}\n\n")
        log(f"SSE capture written: {cap_path}  events={len(rows)} job_events={job_events} field_failures={field_fail}")
        log(f"FIELD VERIFICATION: {'✓ all job events have job_title/company/location/fit_score' if (job_events and field_fail==0) else ('✗ '+str(field_fail)+' job events missing fields' if job_events else 'no job events to verify')}")
    except Exception as e:
        log(f"SSE capture failed: {str(e)[:160]}")

    print("\n================ TIMELINE ================", flush=True)
    for e in EVENTS:
        print(e, flush=True)

if __name__ == "__main__":
    main()
