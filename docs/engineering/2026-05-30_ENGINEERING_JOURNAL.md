# CareerLoop — Engineering Journal (May 30, 2026)

**Session Date:** May 30, 2026  
**Role:** Senior Tech Lead / Senior Backend Reliability & Frontend Engineer  
**Workspace:** `/Users/siddharthsaminathan/projects/CareerLoop`  
**Focus:** REST API Productization, PostgreSQL-Native Caching & Connection Reliability

---

## 1. Overview of Session Work
This session centered on stabilizing the **CareerLoop REST API (v1)** and completing the transition from legacy, file-based SQLite backends to a robust, single-source-of-truth **production PostgreSQL/Supabase database**. Key efforts resolved major architectural bugs—such as connection pools leaking on every chat message turn and the SQL caching layers failing silently when executing raw SQLite queries against Postgres. 

Additionally, we conducted a deep-dive Root Cause Analysis (RCA) on the **Daily Brief Infinite Loading** frontend bug, which was causing the UI to hang for 20-30 seconds during page transitions.

---

## 2. Work Completed

### 1. PostgreSQL-Native Tool Registry Migration (`tool_registry.py`)
- **Refactoring:** Fully migrated the state-modifying actions inside the chatbot's `ToolRegistry` (`review_job`, `skip_job`, and `save_job`) to read and write directly to `careerloop.jobs` and `careerloop.user_job_relationships` inside the PostgreSQL database.
- **Legacy Removal:** Excised dependencies on the legacy `ApplicationLedger` Python class and associated local SQLite JSON/ledger files, establishing PostgreSQL as the canonical source of truth for conversational job state changes.
- **Metadata Mapping:** Aligned card responses to serialize DB column properties (e.g. `company_name`, `fit_score`, and `match_status`) instead of SQLite placeholder keys.

### 2. Cache Infrastructure Generalization (`role_keywords.py` & `role_archetype.py`)
- **Dual-Backend Execution Helper:** Created a backend-agnostic database utility `db_execute` inside `careerloop/memory/connection.py` that translates SQLite-style `?` query placeholders to PostgreSQL-compatible `%s` format dynamically.
- **Idempotent Cache Provisioning:** Added process-guarded initialization methods (`_ensure_table` and `_ensure_archetype_table`) to dynamically provision caching tables in PostgreSQL on demand, eliminating silent cache-miss lookup crashes in production.
- **Schema Qualification:** Implemented `cache_table()` helper to properly qualify tables under the `careerloop.` schema in Postgres while gracefully falling back to bare strings in SQLite for local testing.

### 3. Database Schema Alignment (`supabase_schema.sql`)
- **Database Migrations:** Officially integrated `careerloop.role_keywords` and `careerloop.role_archetypes` into the default database initialization file.
- **Row-Level Security (RLS):** Provisioned standard select policies for authenticated users to ensure secure global read access to cached role parameters and keyword dictionaries.

### 4. Codebase Simplification (`job_service.py` & `scan_service.py`)
- **PK Mapping:** Simplified `JobService::save()` and `JobService::skip()` to map records directly to the canonical integer/text primary keys `id` inside `careerloop.jobs` instead of relying on a fragile UUID backfill routine.
- **Type Mismatch Resolution:** Fixed standard E2E type mismatch crashes inside `_build_from_cache` by updating join statements on the user relationships table to compare keys directly.

---

## 3. Fixes Completed

### 1. Checkpointer Connection & Thread Leak (`checkpointer.py`)
- **The Issue:** `get_checkpointer()` was previously called dynamically on every chat message turn. Without caching, each call instantiated a new `psycopg_pool.ConnectionPool` (maintaining a minimum of 4 connection sessions and auxiliary worker threads) that was never garbage collected. This caused uvicorn thread pools and database connections to be exhausted after a few hours of uptime.
- **The Fix:** Implemented a lazy, thread-safe, process-wide **Checkpointer Singleton** pattern using a standard threading lock (`_checkpointer_lock`). Connection pool instantiation is now restricted to a single process-wide instance, maintaining perfect server stability.

### 2. Caching Crashes in Production PostgreSQL
- **The Issue:** Cache lookup and insert paths in the keyword generator (`role_keywords.py`) and job parser (`role_archetype.py`) threw errors or failed silently on PostgreSQL because `psycopg2` connections do not support SQLite's `.execute` API or `?` placeholders.
- **The Fix:** Integrated the newly created `db_execute` and `cache_table` utilities across the caching layer. All lookups are now safely translated and run on both SQLite and PostgreSQL backends.

### 3. Scan Concurrency & Registry Robustness (`scan_service.py`)
- **The Issue:** The scanner concurrency checks inside `initiate_scan` lacked atomicity, leading to race conditions under heavy concurrent request spikes.
- **The Fix:** Moved user run registration and active scan verification under the process-wide memory lock (`_active_scans_lock`). Added `try/except` catch blocks to release worker semaphores and clean up registration records if background run inserts fail.

---

## 4. Blockers Removed

1. **SQLite Legacy Bindings:** Solved the division where backend tools mutated SQLite files while the API queried Postgres. The entire pipeline now operates on a unified data store.
2. **Uvicorn Connection Crash:** Resolved the connection pool leakage which was a critical blocker for staging and production web deployment.
3. **Database Caching Misses:** Fixed the empty keyword and archetype caching failures, leading to dramatic reductions in LLM query latencies.

---

## 5. Root Cause Analysis (RCA): Daily Brief Infinite Loading
- **Root Cause:** In the frontend React application, `BriefPage.tsx` unconditionally fired API requests on every mount. On returning to `/brief`, it sent stale tokens which triggered a `401 Unauthorized` response. The api interceptor then fired `supabase.auth.refreshSession()` which lacked a timeout parameter and would hang indefinitely if Supabase servers had DNS latencies, causing a permanent spinning loading wheel.
- **Detailed Log:** Archived in `docs/learnings/RCA_BRIEF_INFINITE_LOADING_2026-05-30.md`.
- **Proposed Frontend Mitigations:**
  1. Implement a 5-minute cooldown timer inside `BriefPage.tsx`'s `useEffect` to skip calls if a valid brief was recently loaded in `sessionStorage`.
  2. Implement a `10,000ms` maximum race timeout on `refreshSession()` to prevent token fetches from hanging indefinitely.
  3. Start the page `loading` state as `false` if local cached data is present, loading new data silently in the background.

---

## 6. Next Priorities

1. **Fly.io Staging Deployment:** Set up staging Docker containers and configuration scripts (`Dockerfile`, `fly.toml`) to host the REST API on Fly.io.
2. **Frontend Brief Loading Fixes:** Apply the three-phase client-side token refresh and cache bypass fixes inside the React codebase to eliminate the loading spinners.
3. **Clearbit Company Logo Job:** Write and schedule an automated cron script to backfill company logos using Clearbit enrichment APIs.
4. **PostgresSaver Checkpointer Audit:** Optimize the database save checks to prevent performance degradation under massive multi-worker concurrent thread loads.
