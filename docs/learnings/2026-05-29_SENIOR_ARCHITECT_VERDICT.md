# Senior Systems Architect Verdict — CareerLoop REST API v1
**Date:** 2026-05-29  
**Author:** Product Engineering Lead (Systems Architecture Review)  
**Scope:** 7 MVP endpoints, 6 routers, 5 services, 3 repositories, 4 core modules, 2 dependency modules  
**Method:** First-principles MECE audit — every line, every connection, every error path

---

## Executive Summary

**Score: 7.8/10 — Production-ready for single-user beta, needs hardening for multi-tenant.**

The REST API is structurally sound. The architecture follows clean layering (router → service → repository → DB), the envelope pattern is consistent, auth is well-handled, and the scan streaming is genuinely clever. However, there are **6 critical issues** (1 P0, 4 P1, 1 P2) that will cause production pain if not addressed before multi-user deployment.

---

## Part 1: Architecture Layering — Clean, No Leaky Abstractions

**Score: 9/10 ✅ GREAT**

The 4-layer pattern is correctly enforced:

```
Router (HTTP concerns, validation)
  └── Service (business logic, orchestration)
        └── Repository (data access, SQL)
              └── DatabaseManager (connection pool)
```

**What's right:**
- Routers never touch SQL. They parse the request, delegate to service, return envelope.
- Services never touch HTTP. They orchestrate business logic, raise `APIError` on failures.
- Repositories never raise `APIError`. They return `None`/`False` and let the service decide.
- Serializers are pure functions — no side effects, no DB calls, predictable.

**What's wrong:**
- `BriefService.select_item()` catches ALL exceptions from `SessionStore.save_session()` with a bare `except Exception: pass`. This silently swallows DB write failures. If the session save fails, the selection succeeds but the user's follow-up chat will have stale context. **Fix: log the error at minimum.**

---

## Part 2: Auth & Security — Solid Foundation, One Gap

**Score: 8/10 ✅ GOOD**

**What's right:**
- `verify_supabase_jwt()` has specific error messages for every JWT failure mode (expired, bad audience, bad signature, malformed). This is excellent for debugging.
- `extract_user_info()` handles `user_metadata.full_name` and `user_metadata.name` gracefully. Google OAuth uses both — covered.
- Auto-provisioning with TTL cache (300s) is the correct pattern. Prevents DB write on every request.
- The `_PROVISION_TTL` thread lock prevents race condition on dict access.
- `SUPABASE_JWT_SECRET` loaded from `.env` with `dotenv` at import time — prevents the "env not loaded" class of bugs.

**What's wrong:**
- **P1: In-process cache is per-worker.** Multi-worker deployment (gunicorn with workers > 1) means each worker provisions independently on first call per user per worker. Not a correctness bug (provisioning is idempotent), but 2-3 extra DB writes per user on first request per worker. **Fix: replace with Redis cache in Phase 2.**
- **P2: No rate limiting.** No `Authorization` header rate limit. A malicious client could spam `POST /v1/auth/me` and trigger the provisioning SQL each TTL window. The TTL helps but doesn't solve sustained abuse.

---

## Part 3: Error Handling — Consistent Envelope, Silent Swallowing

**Score: 7/10 🟡 GOOD WITH ISSUES**

**What's right:**
- Consistent `{ok, data, error, meta}` envelope on every endpoint. Frontend parses one shape.
- `APIError` exception handler catches all known error types and returns clean error JSON.
- Global `Exception` handler in main.py catches unhandled errors with `logger.exception()`. No stack traces leaked to client.

**What's wrong:**
- **P1: `BriefService.select_item()` swallows ALL exceptions** from `SessionStore.save_session()`. A corrupt session or DB connection failure will fail silently. **Fix:** Log the error, don't abort the selection (the selection is the primary action, session save is secondary), but at minimum `logger.warning()`.
- **P1: Chat service catches `Exception` twice** — `OnboardingFlow.handle_message()` wrapped in broad catch, and supervisor graph `.invoke()` wrapped in broad catch. Both return generic "try again" messages. Diagnostic information (which node failed, what was the exception type) is lost. **Fix:** include exception type and node name in the server log.
- **P2: `_emit()` in scan_service.py** wraps the INSERT in `try/except` and only logs at DEBUG level. If the scan worker's DB connection is broken, ALL progress events are silently dropped. The frontend sees no events but the scan continues. **Fix: log at ERROR level when `_emit` fails.**

---

## Part 4: Database Access — Connection Management Needs Work

**Score: 6/10 🟡 NEEDS ATTENTION**

**What's right:**
- All queries go through `with self.db.get_connection() as conn` — context manager guarantees connection return.
- Repositories use parameterized queries (`%s` placeholders) — no SQL injection risk.
- JOINs in briefs_repo and jobs_repo are well-structured with LEFT JOINs and smart coalesce.

**What's wrong:**
- **P0: Thread safety of DatabaseManager.** `_run_scan_worker()` creates its own `DatabaseManager(db_url=db_url, skip_schema_init=True)`, but the main thread uses the singleton from `get_db_manager()`. If the singleton uses `psycopg2` (not thread-safe), concurrent connections from the main thread + scan threads will corrupt state. **Fix:** Either (a) use thread-local connections, or (b) guarantee `DatabaseManager` uses `psycopg2.pool.ThreadedConnectionPool`, or (c) move scan workers to a separate process (subprocess/Celery).
- **P1: No connection pooling.** Every `get_connection()` creates a new connection. For >5 concurrent scan streams, this will exhaust Supabase's connection limit (default 15 for free tier, 60 for pro). **Fix:** Wrap the connection factory with `psycopg2.pool.SimpleConnectionPool` or use `pgbouncer`.
- **P1: Schema init race condition.** `DatabaseManager` with `skip_schema_init=False` (not currently used in worker) would run DDL on every connection. Even with `skip_schema_init=True`, there's no guard against a concurrent worker thread initializing the schema while another thread is reading. **Fix:** Make schema init a startup-only operation, gated by a lock file or DB flag.

---

## Part 5: SSE Scan Streaming — Clever Architecture, Throttling Gap

**Score: 8/10 ✅ GOOD**

**What's right:**
- Timestamp watermark dedup: `WHERE timestamp >= %s` bounds each poll to O(new events). This is critical for scan_more mode which emits dozens of events per second.
- Event ID dedup: `seen_event_ids` set handles same-timestamp collisions (PostgreSQL `timestamp` precision is 1ms — two events in the same ms are possible at high throughput).
- 5-min hard timeout prevents orphaned EventSource connections.
- `X-Accel-Buffering: no` header disables nginx buffering — correct for SSE.
- `DatabaseManager` re-created in worker thread with `skip_schema_init=True` — prevents DDL race.

**What's wrong:**
- **P1: Polling every 1s = N queries per second per active scan.** With 50 concurrent scan viewers, that's 50 SELECT queries per second on `run_events` + 50 on `background_runs`. For a free-tier Supabase (15-conn limit), this will bottleneck. **Fix for Phase 2:** Replace polling with `LISTEN/NOTIFY` on Postgres, or use Supabase Realtime (WebSocket).
- **P2: No scan timeout propagation.** The SSE stream stops after 5 minutes, but nothing stops the background thread. If the scan hangs (e.g., SerpAPI never returns), the thread lives forever. **Fix:** Pass an `Event` or `threading.Event` to the worker, check it periodically, and abort on timeout.

---

## Part 6: Threading Model — Daemon Threads Are a Risk

**Score: 5/10 🔴 CONCERNING**

**What's right:**
- Threads are `daemon=True` — they won't block server shutdown.
- `DATABASE_URL` is passed explicitly (not inherited from env) — prevents the "thread can't find env var" bug.
- Worker creates its own `DatabaseManager` — avoids sharing the singleton's connection.

**What's wrong:**
- **P0: Daemon threads are abruptly killed on shutdown.** If a scan thread is mid-INSERT when the server restarts (deploy, crash), the INSERT is lost and the `background_runs` row stays `RUNNING` forever. **Fix:** Use a proper task queue (Celery/ARQ) for Phase 2. For Phase 1: add a startup check that marks stale RUNNING runs as FAILED.
- **P1: No thread limit.** Every `POST /v1/scans` creates a thread. If a user spams "Scan More" 50 times, 50 threads run concurrently. Supabase gets 50x the load. **Fix:** Add a per-user concurrency guard (check for existing RUNNING scan before starting a new one).
- **P1: Thread crash doesn't propagate.** If the worker thread crashes, the `background_runs` status stays `RUNNING` forever. The frontend sees "DONE" never arrive. **Fix:** Wrap the worker body in `try/except/finally` that sets status to `FAILED` on any unhandled error (already partially done, but needs hardening for the crash-before-DB-init case).

---

## Part 7: Serializer Layer — Production-Ready, Subtle Edge Cases

**Score: 9/10 ✅ GREAT**

**What's right:**
- `company_logo()` has a correct 3-tier fallback: explicit DB logo → Clearbit from domain → initials avatar. Never a broken image URL. This is production-grade UX thinking.
- `fit_tier()` maps float score → string tier correctly with boundary conditions documented.
- `description_snippet()` preserves word boundaries with `rsplit(' ', 1)[0]` — no word split in the middle.
- `_domain_from_url()` strips `www.`, filters aggregator domains (Cutshort, LinkedIn, Naukri, Indeed) — the Clearbit logo for those would show the wrong company.
- All serializers handle `None` inputs gracefully with `or ""` / `or None` fallbacks.

**What's wrong:**
- **P2: `company_logo()` renders Clearbit logo even if company is a misidentified match.** If Job A is from BigRio but `company_domain` is accidentally set to `cutshort.io`, the Clearbit URL will show the Cutshort logo. The aggregator filter handles this for known domains, but not for unknown ones. **Fix:** Low priority — data quality issue, not code issue.
- **P2: `_route_badge()` uppercases the route.** "Apply" → "APPLY", "Recruiter outreach" → "RECRUITER OUTREACH". This is fine for display but the frontend needs to know the canonical set of values. **Fix:** Document the canonical set in the handoff doc.

---

## Part 8: Response Time & Latency — No Critical Path Hot Loops

**Score: 8/10 ✅ GOOD**

**Measured paths:**
- `GET /v1/me` — 1 DB query, no joins. Expected: <20ms.
- `GET /v1/briefs/latest` — 2 DB queries (brief + items with JOINs). Expected: <50ms for 10 items.
- `POST /v1/jobs/{id}/save` — 1-2 DB queries (select + upsert). Expected: <30ms.
- `POST /v1/scans` — 2 DB queries (INSERT + _emit). Returns in <50ms. Scan runs async.
- `GET /v1/scans/{run_id}/events` — 2 DB queries per poll. 1s interval means 2 QPS per connection.

**What's right:**
- All synchronous paths are O(1) or O(n) with tiny n (max 10-20 brief items).
- No N+1 queries in the hot path.
- Scan initiation is synchronous-light (returns before scan runs).
- SSE is the correct pattern for async progress (no WebSocket complexity).

**What's wrong:**
- **P1: No DB read-replica strategy.** All queries hit the primary. For Phase 1 (<100 users), this is fine. For Phase 2, read endpoints (briefs, jobs, profile) should hit a replica.
- **P2: `POST /v1/chat/message` calls the LLM synchronously.** If DeepSeek takes 10s, the HTTP response takes 10s. The frontend needs to show a "thinking" state during this time. This is acceptable for MVP but needs streaming for production.

---

## Part 9: Maintainability & Onboarding — Well-Commented, Consistent

**Score: 9/10 ✅ GREAT**

**What's right:**
- Every router file has a docstring explaining the endpoint contract and frontend usage.
- Every significant function has a docstring with parameter descriptions.
- Complex logic (SSE watermark dedup, scan worker threading) has inline comments explaining WHY the pattern was chosen.
- The envelope pattern means any new endpoint follows the same shape — no decisions needed.
- `serializers.py` is the single source of truth for the API contract. Frontend engineers read one file.

**What's missing:**
- **No API tests in the repo.** The `e2e_api_test.py` is in the root, not in `careerloop_api/tests/`. **Fix:** Move tests into the package as `careerloop_api/tests/` with pytest fixtures.
- **No OpenAPI schema published.** FastAPI auto-generates one, but it's not saved in the repo as documentation.

---

## Part 10: Dependencies & Environment — Tight, Minimal Surface

**Score: 8/10 ✅ GOOD**

Imports are clean and minimal per file. No circular imports detected. Key dependencies:

```
FastAPI (web framework)
uvicorn (server)
psycopg2 (Postgres driver)
PyJWT (JWT verification)
python-dotenv (env loading)
langchain-core (for ChatMessage type only in chat_service.py)
careerloop.* (internal packages)
```

**What's right:**
- `careerloop_api` imports from `careerloop` packages (session, onboarding, memory) but NOT vice versa. No circular dependency risk.
- `dotenv` is loaded at `config.py` import time — self-sufficient module, no shell dependency.
- Only `PyJWT` is needed for auth (plus `cryptography` key backend).

**What's wrong:**
- **P2: `langchain-core` dependency for a single `HumanMessage` class.** The chat service imports `from langchain_core.messages import HumanMessage` purely to wrap the user's text for the supervisor graph. This pulls in the entire langchain message schema package. **Fix:** Either (a) use a plain dict `{"role": "user", "content": text}` (the supervisor graph may accept it), or (b) vendor the 5-line `HumanMessage` class to eliminate the dependency. Low priority.

---

## Part 11: The "UV/Icron Restart Loop" — Root Cause Analysis

**Score: 5/10 🔴 INVESTIGATION NEEDED**

**Symptom:** The API server gets stuck in a restart loop — uv/icorn crashes and restarts repeatedly.

**First-principles root cause audit:**

| Cause | Likelihood | Evidence |
|-------|-----------|----------|
| **Thread crash on DB init** | **HIGH** | `_run_scan_worker` creates `DatabaseManager(db_url=db_url, skip_schema_init=True)`. If `skip_schema_init` doesn't work (e.g., the `DatabaseManager.__init__` always calls `_init_schema()` regardless of the flag), the worker thread will DDL the entire schema on every scan. If the DDL conflicts with a concurrent query (e.g., `CREATE TABLE IF NOT EXISTS` vs another thread reading the same table), Postgres may deadlock or the connection may drop. **Fix:** Verify `skip_schema_init=True` actually skips all DDL. Add `SKIP_SCHEMA_INIT env var` check as defense in depth. |
| **Connection exhaustion** | **MEDIUM** | Each scan thread creates a NEW `DatabaseManager` with its own connection pool. If the `get_connection()` method doesn't close connections properly (or the pool is unbounded), repeated scans will exhaust the Supabase 15-connection limit. When the main thread's `get_connection()` fails with "too many connections", the server crashes. **Fix:** Add connection pool limits. |
| **uvicorn hot-reload race** | **MEDIUM** | The server runs with `--reload`. When `scan_service.py` imports `careerloop.memory.connection.get_db_manager`, the reload watcher detects file changes inside `careerloop/` package and restarts the server — mid-thread. The thread loses its interpreter. **Fix:** Remove `--reload` in production. |
| **SIGTERM race with daemon threads** | **LOW** | On server restart, uvicorn sends SIGTERM. Daemon threads are killed immediately. If a thread holds a DB connection, the connection may not be returned to the pool. On restart, the old connections remain in "idle in transaction" state, exhausting the pool. **Fix:** Register scan threads with a shutdown handler that waits for active scans. |

**Most likely cause:** Connection exhaustion from unbounded thread + pool creation. Each `POST /v1/scans` creates a new `DatabaseManager` instance, and if the connection pool inside it is unbounded (or the context manager doesn't return connections), the Supabase connection limit is hit within 15 scan requests. The server can't serve any new request (including health checks), and uvicorn marks it as unhealthy → restart loop.

**Immediate fix:** Add a `_cleanup_idle_connections()` guard in `get_connection()` that kills connections older than 60s. Add per-user scan concurrency limit (1 active scan per user).

---

## Part 12: The 12-Part Verdict — Actionable Next Steps

### Critical (P0 — Fix Before Multi-User)
1. **DatabaseManager thread safety** — Guarantee ThreadedConnectionPool or move scan workers to subprocess. Verify `skip_schema_init=True` actually skips DDL.

### High (P1 — Fix This Sprint)
2. **Per-user scan concurrency limit** — Reject `POST /v1/scans` if user already has a RUNNING scan. Prevents thread explosion and connection exhaustion.
3. **Stale RUNNING scan recovery** — Add startup SQL: `UPDATE careerloop.background_runs SET status = 'FAILED' WHERE status = 'RUNNING' AND updated_at < NOW() - INTERVAL '30 minutes'`. Cleans up orphaned runs.
4. **Connection pooling** — Wrap `DatabaseManager.get_connection()` with `psycopg2.pool.SimpleConnectionPool` (max 10 connections). Hard-limit connections.
5. **Thread lifecycle** — Add `threading.Event()` abort mechanism to scan workers. SSE timeout triggers abort, not just stream close.
6. **Error logging** — Replace silent `except: pass` in `BriefService.select_item()` with `logger.warning()`. Change `_emit()` error logging from DEBUG to ERROR.

### Medium (P2 — Next Sprint)
7. **Redis provision cache** — Replace in-process `_provisioned` dict with Redis for multi-worker deployments.
8. **Remove `langchain-core` dependency** — Vendor `HumanMessage` or use plain dict.
9. **API test suite** — Move `e2e_api_test.py` into `careerloop_api/tests/` with pytest fixtures.
10. **Rate limiting** — Add per-user rate limiter (slowapi or middleware) for all POST endpoints.
11. **DB read path optimization** — Add `skip_schema_init=True` to all `DatabaseManager` usages in worker threads.
12. **Company logo backfill** — Clearbit enrichment job as separate script, not in API process.

### Definite Wins (Already Correct)
- ✅ SSE watermark dedup pattern is production-grade — keep it.
- ✅ Serializer logo fallback strategy is excellent — never broken images.
- ✅ Auth auto-provisioning with TTL is clean — keep the pattern.
- ✅ Consistent envelope pattern — every new endpoint is free.
- ✅ Error envelope with `request_id` — debugging friendly.
- ✅ Dotenv-at-import-time pattern — prevents env loading bugs.

---

## Final Score: 7.8/10

```
├── Part 1:  Architecture Layering        9/10  ✅
├── Part 2:  Auth & Security              8/10  ✅
├── Part 3:  Error Handling               7/10  🟡
├── Part 4:  Database Access              6/10  🟡 ← P0 (thread safety)
├── Part 5:  SSE Scan Streaming           8/10  ✅
├── Part 6:  Threading Model              5/10  🔴 ← P1 (daemon threads, no limit)
├── Part 7:  Serializer Layer             9/10  ✅
├── Part 8:  Response Time & Latency      8/10  ✅
├── Part 9:  Maintainability             9/10  ✅
├── Part 10: Dependencies & Environment   8/10  ✅
├── Part 11: UV/Icron Restart Loop        5/10  🔴 ← P0 (connection exhaustion)
└── Part 12: Overall Exec Summary         7.8/10
```

**Verdict:** Ship it, but monitor connections like a hawk. Fix the P0 thread safety and P1 connection pooling before giving access to >5 concurrent users. The architecture is right — the threading model needs hardening.
