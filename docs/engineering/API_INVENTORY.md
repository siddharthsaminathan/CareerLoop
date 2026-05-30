# CareerLoop REST API: Complete Endpoint Inventory

This document defines every publicly reachable API endpoint in the CareerLoop production backend (`careerloop_api`).

---

## 1. Authentication Router (`careerloop_api/routers/auth.py`)

### `POST /v1/auth/me`
* **Purpose:** Called by the frontend immediately after Supabase Google OAuth completes. Validates the JWT, provisions a brand-new user record in the database if it doesn't exist, and returns the hydrated user profile.
* **Authentication Required:** Yes (Supabase JWT via `Authorization: Bearer <token>`)
* **Handler:** `provision_and_get_me`
* **Service:** `UserService.me(user_id)`
* **Database Tables Touched:**
  - `careerloop.users` (SELECT/INSERT/UPDATE)
  - `careerloop.sessions` (SELECT/INSERT if missing)

---

## 2. Users Router (`careerloop_api/routers/users.py`)

### `GET /v1/me`
* **Purpose:** Returns the authenticated user's profile information.
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `me`
* **Service:** `UserService.me(user_id)`
* **Database Tables Touched:**
  - `careerloop.users` (SELECT)

### `GET /v1/me/preferences`
* **Purpose:** Returns the user's work style preferences.
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `preferences`
* **Service:** `UserService.preferences(user_id)`
* **Database Tables Touched:**
  - `careerloop.users` (SELECT `work_style_prefs` column)

---

## 3. Daily Briefs Router (`careerloop_api/routers/briefs.py`)

### `GET /v1/briefs/latest`
* **Purpose:** Retrieves the latest generated daily brief summary and item list for the user, with pagination offset.
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `latest`
* **Service:** `BriefService.latest(user_id, offset)`
* **Database Tables Touched:**
  - `careerloop.daily_briefs` (SELECT)
  - `careerloop.daily_brief_items` (SELECT joins `public.jobs`)
  - `public.user_job_relationships` (SELECT)

### `POST /v1/briefs/{brief_id}/items/{item_index}/select`
* **Purpose:** Approves/selects a job card from a specific daily brief, updating its swipe relationship in PostgreSQL.
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `select_item`
* **Service:** `BriefService.select_item(user_id, brief_id, item_index)`
* **Database Tables Touched:**
  - `careerloop.daily_briefs` (SELECT)
  - `careerloop.daily_brief_items` (SELECT/UPDATE)
  - `public.user_job_relationships` (INSERT/UPDATE)

---

## 4. Jobs Router (`careerloop_api/routers/jobs.py`)

### `GET /v1/jobs/{job_id}`
* **Purpose:** Retrieves detailed profile and relationship status for a specific job.
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `get_job`
* **Service:** `JobService.get(user_id, job_id)`
* **Database Tables Touched:**
  - `public.jobs` (SELECT)
  - `public.user_job_relationships` (SELECT)

### `POST /v1/jobs/{job_id}/save`
* **Purpose:** Marks a job as saved/approved by the user.
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `save_job`
* **Service:** `JobService.save(user_id, job_id)`
* **Database Tables Touched:**
  - `public.user_job_relationships` (INSERT/UPDATE `status = 'approved'`)

### `POST /v1/jobs/{job_id}/skip`
* **Purpose:** Marks a job as skipped/discarded by the user.
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `skip_job`
* **Service:** `JobService.skip(user_id, job_id)`
* **Database Tables Touched:**
  - `public.user_job_relationships` (INSERT/UPDATE `status = 'skipped'`)

---

## 5. Conversational Chat Router (`careerloop_api/routers/chat.py`)

### `POST /v1/chat/message`
* **Purpose:** Submits a conversational text message. Routes to `OnboardingFlow` (if onboarding is incomplete) or to the LangGraph supervisor (if `PROFILE_READY`).
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `message`
* **Service:** `ChatService.message(user_id, text)`
* **Database Tables Touched:**
  - `careerloop.users` (SELECT/UPDATE)
  - `careerloop.sessions` (SELECT/UPSERT)
  - `careerloop.messages` (INSERT)

### `GET /v1/chat/history`
* **Purpose:** Retrieves the authenticated user's recent chat history to hydrate/restore chat bubbles on login.
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `history`
* **Service:** `ChatService.get_history(user_id)`
* **Database Tables Touched:**
  - `careerloop.messages` (SELECT order by created_at)

---

## 6. Job Scanners Router (`careerloop_api/routers/scans.py`)

### `POST /v1/scans`
* **Purpose:** Initiates a job discovery scan run in the background. Mode can be "default" (cache-first discovery) or "scan_more" (forced portal scrapers discovery).
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `start_scan`
* **Service:** `initiate_scan(user_id, db, mode)`
* **Database Tables Touched:**
  - `careerloop.background_runs` (INSERT)

### `GET /v1/scans/latest`
* **Purpose:** Retrieves the latest background scan run_id and status for the user.
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `latest_scan`
* **Service:** None (Direct SQL read)
* **Database Tables Touched:**
  - `careerloop.background_runs` (SELECT order by started_at DESC)

### `GET /v1/scans/{run_id}`
* **Purpose:** Retrieves status and details of a specific scan background run.
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `scan_status`
* **Service:** `get_scan_status(run_id, db)`
* **Database Tables Touched:**
  - `careerloop.background_runs` (SELECT)

### `GET /v1/scans/{run_id}/events`
* **Purpose:** Initiates a Server-Sent Events (SSE) streaming response of the live discovery, scoring, and matching status updates.
* **Authentication Required:** Yes (Supabase JWT)
* **Handler:** `scan_events`
* **Service:** `stream_scan_events(run_id, db)`
* **Database Tables Touched:**
  - `careerloop.run_events` (SELECT tailing/streaming events in real-time)

---

## 7. Diagnostics Router (`careerloop_api/routers/debug.py`)

### `GET /v1/debug/runtime`
* **Purpose:** Returns complete internal telemetry for the API server (uptime, memory RSS, open file descriptors, active threads, psycopg2 connection pool metrics, LangGraph connection pool metrics).
* **Authentication Required:** No (Exposed locally / localhost operational endpoint)
* **Handler:** `runtime`
* **Service:** `runtime_snapshot()`
* **Database Tables Touched:** None

### `GET /v1/debug/db-check`
* **Purpose:** Performs a database connection check and returns connectivity and latency metrics.
* **Authentication Required:** No
* **Handler:** `db_check`
* **Service:** `DatabaseManager.check_connection()`
* **Database Tables Touched:** None (Performs connection test)

### `GET /v1/debug/pool`
* **Purpose:** Returns connection pool size, free/in-use statistics, and DB latency.
* **Authentication Required:** No
* **Handler:** `pool_health`
* **Service:** `DatabaseManager.pool_health()`
* **Database Tables Touched:** None
