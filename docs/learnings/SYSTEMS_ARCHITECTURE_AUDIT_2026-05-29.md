# CareerLoop Systems Architecture Audit

**Date:** 2026-05-29
**Auditor:** Principal Systems Architect (Claude)
**Scope:** MECE reverse-engineering of the entire CareerLoop platform
**Methodology:** Code-path tracing, database introspection, cross-layer dependency analysis

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [System Diagram](#2-system-diagram)
3. [Workflow Diagrams](#3-workflow-diagrams)
4. [Database Map](#4-database-map)
5. [Event Map](#5-event-map)
6. [State Machine Map](#6-state-machine-map)
7. [Dead Code Report](#7-dead-code-report)
8. [Orphan Service Report](#8-orphan-service-report)
9. [Critical Dependency Report](#9-critical-dependency-report)
10. [Top 10 Architectural Risks](#10-top-10-architectural-risks)

---

## 1. Architecture Overview

CareerLoop is a layered AI career execution platform with three runtime entry points, four persistence stacks, and a dual-pipeline architecture (V2 CLI + V3 API). The system ingests job postings from 30+ external sources, scores them against user profiles using LLM-based fit engines, surfaces daily briefs, and generates application packs (resume + cover letter + outreach).

### Deployment Topology

```
                        +------------------+
                        |   Cloudflare     | (DNS + CDN for frontend)
                        +--------+---------+
                                 |
                    +------------+------------+
                    |                         |
          +--------v--------+      +---------v--------+
          | Vercel/Vite     |      | Railway/Render   |
          | (React SPA)     |      | FastAPI :8001    |  -- REST API
          | Frontend        |      |                  |
          +-----------------+      +------------------+ <- careerloop_api/main.py
                    |                         |
           Supabase Client            FastAPI (uvicorn)
           (Google OAuth)             |
                    |         +-------+-------+
                    |         |               |
                    |   +-----v-----+   +----v------+
                    |   | LangGraph  |   | Telegram  |
                    |   | Supervisor |   | Webhook   |
                    |   +-----+-----+   +----+------+
                    |         |              |
                    +---------+--------------+
                              |
                    +---------v---------+
                    |   Supabase        |
                    |   PostgreSQL      |
                    |   (prod)          |
                    |   + SQLite (dev)  |
                    +-------------------+
```

### Layer Architecture

```
LAYER 0: TRANSPORT — How users reach the system
  - Web (React SPA via Supabase OAuth -> FastAPI REST)
  - Telegram (Bot webhook -> FastAPI webhook server on :8000)
  - CLI (terminal_chat.py -> local python runner)

LAYER 1: AUTH & SESSION — Identity + state
  - Supabase Auth (Google OAuth, JWT)
  - careerloop_api/deps/auth.py (JWT verification + user provisioning)
  - careerloop/memory/checkpointer.py (LangGraph conversation persistence)
  - careerloop/session/session_store.py (UserJourneyState + ActiveContext)

LAYER 2: ROUTING — Intent resolution
  - careerloop/session/action_resolver.py (ActionType enum, 17 actions)
  - careerloop/session/states.py (UserJourneyState, BackgroundWorkStatus)
  - careerloop/session/supervisor_graph.py (LangGraph StateGraph)

LAYER 3: TOOLS — Business logic execution
  - careerloop/session/tool_registry.py (ToolRegistry, 17 tool handlers)
  - careerloop/onboarding/onboarding_flow.py (7-step state machine)
  - careerloop/daily_runner.py (9-step pipeline)
  - careerloop/company_intel.py (multi-source research engine)
  - careerloop/package_assembly.py (app pack generation)
  - careerloop/outreach_engine.py (people discovery)

LAYER 4: PERSISTENCE — Data storage
  - Supabase PostgreSQL (production)
  - SQLite (local dev)
  - careerloop/memory/connection.py (DatabaseManager with ThreadedConnectionPool)
  - careerloop/memory/repository_v2.py (Repository pattern)
  - careerloop/memory/checkpointer.py (LangGraph PostgresSaver)
  - careerloop/application_ledger.py (filesystem-based JSON ledger — LEGACY)

LAYER 5: DISCOVERY — Job sourcing
  - scan.mjs (Node.js portal scanner — 30+ ATS APIs)
  - careerloop/sources/* (Python adapters — Cutshort, LinkedIn, Naukri, etc.)
  - careerloop/memory/repository_v2.py (global job cache)
```

### Entry Point Inventory

| # | Entry Point | Transport | Auth | Backend Route | Layer |
|---|------------|-----------|------|---------------|-------|
| EP-01 | Google Login | Web SPA | Supabase OAuth | `POST /v1/auth/me` | L1 |
| EP-02 | Chat Message | Web SPA | Supabase JWT | `POST /v1/chat/message` | L2 |
| EP-03 | Chat History | Web SPA | Supabase JWT | `GET /v1/chat/history` | L2 |
| EP-04 | Start Scan | Web SPA | Supabase JWT | `POST /v1/scans` | L3 |
| EP-05 | SSE Scan Events | Web SPA | Supabase JWT | `GET /v1/scans/{run_id}/events` | L5 |
| EP-06 | Get Brief | Web SPA | Supabase JWT | `GET /v1/briefs/latest` | L4 |
| EP-07 | Select Brief Item | Web SPA | Supabase JWT | `POST /v1/briefs/{id}/items/{idx}/select` | L4 |
| EP-08 | Get Job Detail | Web SPA | Supabase JWT | `GET /v1/jobs/{job_id}` | L4 |
| EP-09 | Save Job | Web SPA | Supabase JWT | `POST /v1/jobs/{job_id}/save` | L4 |
| EP-10 | Skip Job | Web SPA | Supabase JWT | `POST /v1/jobs/{job_id}/skip` | L4 |
| EP-11 | Get User Profile | Web SPA | Supabase JWT | `GET /v1/me` | L1 |
| EP-12 | Get Preferences | Web SPA | Supabase JWT | `GET /v1/me/preferences` | L1 |
| EP-13 | Telegram Webhook | Telegram Bot | Telegram Chat ID | `POST /telegram/webhook` | L1 |
| EP-14 | Telegram Callback | Telegram Bot | Telegram Chat ID | `POST /telegram/webhook` | L1 |
| EP-15 | CLI Chat | Terminal | Email key | `careerloop/chat_cli.py` | L2 |
| EP-16 | CLI Scan | Terminal | Email key | `careerloop/daily_runner.py` | L3 |
| EP-17 | Health Check | HTTP | None | `GET /health` | N/A |

### Service Inventory

| # | Service | File | Purpose | Deployed |
|---|---------|------|---------|----------|
| SVC-01 | chat_service.py | careerloop_api/services/ | HTTP chat orchestrator | Yes |
| SVC-02 | scan_service.py | careerloop_api/services/ | Async scan + SSE | Yes |
| SVC-03 | brief_service.py | careerloop_api/services/ | Brief read + item select | Yes |
| SVC-04 | job_service.py | careerloop_api/services/ | Job detail + save/skip | Yes |
| SVC-05 | user_service.py | careerloop_api/services/ | Profile + preferences | Yes |
| SVC-06 | webhook_server.py | careerloop/transport/ | Telegram webhook entry | Yes |
| SVC-07 | supervisor_graph.py | careerloop/session/ | LangGraph intent router | In-process |
| SVC-08 | tool_registry.py | careerloop/session/ | 17 tool handler implementations | In-process |
| SVC-09 | action_resolver.py | careerloop/session/ | LLM-based intent resolution | In-process |
| SVC-10 | onboarding_flow.py | careerloop/onboarding/ | 7-step onboarding FSM | In-process |
| SVC-11 | daily_runner.py | careerloop/ | 9-step daily pipeline | On-demand/thread |
| SVC-12 | company_intel.py | careerloop/ | Multi-source company research | On-demand |
| SVC-13 | package_assembly.py | careerloop/ | Application pack generation | On-demand/thread |
| SVC-14 | outreach_engine.py | careerloop/ | LinkedIn people discovery | On-demand |
| SVC-15 | india_fit_engine.py | careerloop/ | Job-to-profile scoring | On-demand |

---

## 2. System Diagram

```
                          FRONTEND (React SPA)
                          ====================
    /login  /onboarding  /brief  /jobs/:id  /chat  /profile
       |         |          |        |         |        |
       |    POST /v1/chat/message    |    POST /v1/scans  |
       |         (Onboarding Flow)   |    SSE /v1/scans/{run_id}/events
       |              |              |         |        |
       +--------------+--------------+---------+--------+
                              |
                    +---------v---------+
                    |   FastAPI :8001   |
                    |  careerloop_api/  |
                    +----+----+----+----+
                         |    |    |
           +-------------+    |    +-------------+
           |                  |                  |
  +--------v--------+  +-----v------+  +--------v--------+
  |  Auth Dep       |  | Chat Svc   |  |  Scan Svc       |
  |  (JWT verify,   |  | (routes to |  |  (async thread   |
  |   user prov)    |  |  supervisor|  |   + SSE stream)  |
  +--------+--------+  |  or onboard|  +--------+--------+
           |           +-----+------+           |
           |                 |                  |
  +--------v--------+  +-----v------+  +--------v--------+
  |  users table    |  | LangGraph  |  |  DailyRunner    |
  |  (careerloop.)  |  | Supervisor |  |  (thread pool   |
  +-----------------+  +-----+------+  |   + scan.mjs)   |
                             |         +--------+--------+
                      +------v------+           |
                      | Action      |  +--------v--------+
                      | Resolver    |  |  IndiaFitEngine |
                      | (LLM call)  |  |  (job scoring)  |
                      +------+------+  +--------+--------+
                             |                  |
                      +------v------+  +--------v--------+
                      | Tool        |  |  Application    |
                      | Registry    |  |  Ledger (JSON)  |
                      | (17 tools)  |  +-----------------+
                      +------+------+
                             |
                  +----------+-----------+
                  |                      |
          +-------v-------+    +--------v-------+
          | SessionStore  |    |  RepositoryV2  |
          | (sessions     |    |  (jobs, briefs, |
          |  table)       |    |   relationships)|
          +-------+-------+    +--------+-------+
                  |                      |
          +-------v----------------------v-------+
          |         Supabase PostgreSQL          |
          |  + careerloop.* (38 tables)          |
          |  + public.checkpoint_* (LangGraph)   |
          |  + public.emote_* (Emote app)        |
          +--------------------------------------+

                    TELEGRAM BOT (Alternative Entry)
                    ==============================
    Telegram App  --->  Telegram Webhook Server (:8000)
                        careerloop/transport/webhook_server.py
                            |
                            +-- NEW_USER -> OnboardingFlow
                            +-- PROFILE_READY+ -> supervisor_graph
                            |
                            +-- TelegramAdapter (sendText, sendButtons, sendDocument)
```

---

## 3. Workflow Diagrams

### 3.1 User Login (Google OAuth)

```
User                   Frontend (SPA)              Supabase Auth        Backend API              PostgreSQL
 |                         |                           |                    |                        |
 |--Click Google Login---->|                           |                    |                        |
 |                         |--signInWithOAuth()------->|                    |                        |
 |                         |                           |--Google consent--->|                        |
 |                         |                           |<--OAuth code------|                        |
 |                         |                           |--exchange code---->|                        |
 |                         |                           |<--JWT + refresh---|                        |
 |                         |<--session established-----|                    |                        |
 |                         |                           |                    |                        |
 |                         |--POST /v1/auth/me-------->|                    |                        |
 |                         |   (Bearer JWT)            |                    |                        |
 |                         |                           |        verify_supabase_jwt(token)         |
 |                         |                           |                    |--extract sub,email--> |
 |                         |                           |                    |                        |
 |                         |                           |        _provision_user(user_id)            |
 |                         |                           |                    |--INSERT careerloop.    |
 |                         |                           |                    |  users ON CONFLICT     |
 |                         |                           |                    |  (id) DO UPDATE       |
 |                         |                           |                    |  last_active_at ---->  |
 |                         |                           |                    |                        |
 |                         |                           |        UserService.me(user_id)             |
 |                         |                           |                    |--SELECT FROM           |
 |                         |                           |                    |  careerloop.users ----> |
 |                         |                           |                    |<--user row-------------|
 |                         |<--{id, email, full_name}--|                    |                        |
 |                         |                           |                    |                        |
 |--Redirect to /brief---->|                           |                    |                        |
```

### 3.2 User Onboarding

```
User                   Frontend                ChatService              OnboardingFlow           SessionStore             PostgreSQL
 |                       |                        |                         |                        |                        |
 |--Open /onboarding---->|                        |                         |                        |                        |
 |                       |--sendChatMessage("hi")-->|                        |                        |                        |
 |                       |                        |--get_session(user_id)-->|                        |                        |
 |                       |                        |                         |                        |--SELECT FROM sessions->|
 |                       |                        |                         |                        |<--Session(NEW_USER)----|
 |                       |                        |--state==NEW_USER: flow.handle_message()--------->|                        |
 |                       |                        |                         |                        |                        |
 |                       |                        |     STEP_IDLE (0)       |                        |                        |
 |                       |                        |     _handle_idle()      |                        |                        |
 |                       |                        |     step=STEP_IDENTIFYING|                       |                        |
 |                       |                        |                         |--save_session()------->|                        |
 |                       |                        |                         |                        |--UPSERT sessions------>|
 |                       |                        |                         |                        |                        |
 |                       |                        |<--"What's your name?"---|                        |                        |
 |                       |<--reply----------------|                         |                        |                        |
 |                       |                        |                         |                        |                        |
 |--Type name----------->|                        |                         |                        |                        |
 |                       |--sendChatMessage()----->|                        |                        |                        |
 |                       |                        |--flow.handle_message()-->|                       |                        |
 |                       |                        |                         |                        |                        |
 |                       |                        |     STEP_IDENTIFYING (10)                       |                        |
 |                       |                        |     _handle_identifying()|                       |                        |
 |                       |                        |     LinkedInIdentityProvider.find_by_name()       |                        |
 |                       |                        |     -> SerpAPI lookup    |                        |                        |
 |                       |                        |     (or fallback to CV)  |                        |                        |
 |                       |                        |                         |                        |                        |
 |                       |                        |     STEP_PROFILE_CONFIRMATION (11)                |                        |
 |                       |                        |     "Is this you?" card  |                        |                        |
 |                       |                        |<--profile card----------|                        |                        |
 |                       |<--identity card data---|                         |                        |                        |
 |                       |                        |                         |                        |                        |
 |--Click YES----------->|                        |                         |                        |                        |
 |                       |                        |     hydrated from LinkedIn                       |                        |
 |                       |                        |     step=STEP_WAITING_CV (1)                     |                        |
 |                       |                        |     "Paste your CV"      |                        |                        |
 |                       |<--"Paste your CV"------|                         |                        |                        |
 |                       |                        |                         |                        |                        |
 |--Paste CV text------->|                        |                         |                        |                        |
 |                       |                        |     STEP_WAITING_CV (1)  |                        |                        |
 |                       |                        |     CVExtractionAgent    |                        |                        |
 |                       |                        |     -> DeepSeek extract  |                        |                        |
 |                       |                        |     step=STEP_CONFIRMING (2)                      |                        |
 |                       |                        |                         |                        |                        |
 |                       |<--"Here's what I extracted... Reply YES"---------|                        |                        |
 |--"yes"--------------->|                        |                         |                        |                        |
 |                       |                        |     _handle_confirming() |                        |                        |
 |                       |                        |     missing fields check  |                        |                        |
 |                       |                        |     step=STEP_COLLECTING (3) if gaps               |                        |
 |                       |                        |     "I still need: CTC, notice..."                  |                        |
 |                       |                        |                         |                        |                        |
 |--"30 LPA, 30 days"--->|                        |                         |                        |                        |
 |                       |                        |     _handle_collecting() |                        |                        |
 |                       |                        |     OnboardingAgent.process()                      |                        |
 |                       |                        |     all fields complete!  |                        |                        |
 |                       |                        |     _complete_onboarding()|                        |                        |
 |                       |                        |                         |                        |                        |
 |                       |                        |     _commit_profile_to_db()                        |                        |
 |                       |                        |                         |                        |--UPDATE careerloop.    |
 |                       |                        |                         |                        |  users SET             |
 |                       |                        |                         |                        |  master_cv_markdown,   |
 |                       |                        |                         |                        |  work_style_prefs,     |
 |                       |                        |                         |                        |  onboarding_complete-->|
 |                       |                        |                         |                        |                        |
 |                       |                        |     _seed_welcome_brief()|                        |                        |
 |                       |                        |                         |                        |--INSERT daily_briefs-->|
 |                       |                        |                         |                        |                        |
 |                       |                        |     state=PROFILE_READY  |                        |                        |
 |                       |                        |                         |--save_session(PROFILE_READY)----------------->|
 |                       |                        |<--"Profile complete!"---|                        |                        |
 |                       |<--state:PROFILE_READY--|                         |                        |                        |
 |                       |                        |                         |                        |                        |
 |--Auto-redirect /brief>|                        |                         |                        |                        |
```

### 3.3 Scan Jobs (/scan)

```
User              Frontend           ScanService            DailyRunner          scan.mjs         Supabase           RepositoryV2
 |                   |                    |                      |                   |                |                    |
 |--"/scan"--------->|                    |                      |                   |                |                    |
 |                   |--POST /v1/scans--->|                      |                   |                |                    |
 |                   |  {mode:"default"}  |                      |                   |                |                    |
 |                   |                    |--Concurrency guards:|                   |                |                    |
 |                   |                    |  1. has_running_scan?|                  |                |                    |
 |                   |                    |  2. semaphore.acquire|                  |                |                    |
 |                   |                    |                      |                   |                |                    |
 |                   |                    |--INSERT background_runs (RUNNING)------->|                |                    |
 |                   |                    |--_emit: QUEUED event--------------------->|                |                    |
 |                   |                    |                      |                   |                |                    |
 |                   |                    |--Thread.start()------>|                   |                |                    |
 |                   |<--{run_id, RUNNING}|                      |                   |                |                    |
 |                   |                    |                      |                   |                |                    |
 |                   |--SSE /scans/{id}/events------------------>|                   |                |                    |
 |                   |   (EventSource)    |                      |                   |                |                    |
 |                   |                    |                      |                   |                |                    |
 |                   |                    |  [Worker Thread]      |                   |                |                    |
 |                   |                    |                      |                   |                |                    |
 |                   |                    |                      |--DailyRunner.run()->|                |                    |
 |                   |                    |                      |  do_scan=True      |                |                    |
 |                   |                    |                      |                    |                |                    |
 |                   |                    |                      |  Idempotency guard |                |                    |
 |                   |                    |                      |  (check .last_brief_date)           |                    |
 |                   |                    |                      |                    |                |                    |
 |                   |                    |                      |  Step 1: Scan      |                |                    |
 |                   |                    |                      |  _run_scanner()---->|                |                    |
 |                   |                    |                      |                    |--subprocess----->|                    |
 |                   |                    |                      |                    |  node scan.mjs  |                    |
 |                   |                    |                      |                    |  -> Greenhouse  |                    |
 |                   |                    |                      |                    |  -> Lever       |                    |
 |                   |                    |                      |                    |  -> Ashby       |                    |
 |                   |                    |                      |                    |  -> Cutshort    |                    |
 |                   |                    |                      |                    |  (30+ portals)  |                    |
 |                   |                    |                      |                    |<--pipeline.md---|                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |                    |                      |  _emit: SCAN_STARTED, SOURCE_STARTED-->|                 |
 |                   |                    |                      |                    |                 |                    |
 |                   |                    |                      |  Step 2: Geo + Role Filter            |                    |
 |                   |                    |                      |  -> filter_india_jobs()               |                    |
 |                   |                    |                      |  -> role family filter                |                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |                    |                      |  Step 3: Dedupe     |                |                    |
 |                   |                    |                      |  -> ledger.is_duplicate()             |                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |                    |                      |  Step 4: Add to ledger                |                    |
 |                   |                    |                      |  -> ledger.add_job()                  |                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |                    |                      |  Step 5: Score      |                |                    |
 |                   |                    |                      |  -> IndiaFitEngine  |                |                    |
 |                   |                    |                      |  -> LLM: DeepSeek   |                |                    |
 |                   |                    |                      |  -> ledger.set_fit_score()            |                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |                    |                      |  Returns: top_jobs[]                  |                    |
 |                   |                    |<--res dict-----------|                    |                 |                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |                    |--Cache-hit check---->|                    |                 |                    |
 |                   |                    |                      |                    |        get_fresh_cached_jobs()           |
 |                   |                    |                      |                    |<--cached jobs-----|                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |                    |--DELETE old brief for today-------------->|                 |                    |
 |                   |                    |--INSERT new brief + items----------------->|                 |                    |
 |                   |                    |  careerloop.daily_briefs                   |                 |                    |
 |                   |                    |  careerloop.daily_brief_items              |                 |                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |                    |--V3 Canonical Pipeline (best-effort)------>|                 |                    |
 |                   |                    |  -> careerloop.job_candidates              |                 |                    |
 |                   |                    |  -> careerloop.jobs (ON CONFLICT fingerprint)               |                    |
 |                   |                    |  -> careerloop.companies (ON CONFLICT domain_slug)           |                    |
 |                   |                    |  -> careerloop.company_memory                               |                    |
 |                   |                    |  -> careerloop.user_job_relationships                       |                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |                    |--_emit events:------>|                    |                 |                    |
 |                   |                    |  CANDIDATE_MATCHED   |                    |                 |                    |
 |                   |                    |  FILTER_SUMMARY      |                    |                 |                    |
 |                   |                    |  BRIEF_CREATED       |                    |                 |                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |                    |--UPDATE background_runs.status='COMPLETED'----------------->|                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |   SSE stream        |                      |                    |                 |                    |
 |                   |   polls run_events  |                      |                    |                 |                    |
 |                   |   every 1s         |                      |                    |                 |                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |   {...CANDIDATE_MATCHED}                   |                    |                 |                    |
 |                   |   {...FILTER_SUMMARY}                      |                    |                 |                    |
 |                   |   {...BRIEF_CREATED}                       |                    |                 |                    |
 |                   |   {...DONE}         |                      |                    |                 |                    |
 |                   |                    |                      |                    |                 |                    |
 |                   |--Redirect /brief-->|                      |                    |                 |                    |
```

### 3.4 Scan More (/scan_more)

```
User              Frontend           ScanService                     scan.mjs                        Supabase
 |                   |                    |                             |                              |
 |--"/scan_more"--->|                    |                             |                              |
 |                   |--POST /v1/scans-->|                             |                              |
 |                   |  mode="scan_more" |                             |                              |
 |                   |                    |                             |                              |
 |                   |                    |--_execute_scan_more():      |                              |
 |                   |                    |  1. Load targets + seen keys from DB                 |
 |                   |                    |  2. Run scan.mjs as subprocess                       |
 |                   |                    |     with per-line streaming-->|                              |
 |                   |                    |                             |--Scan each portal           |
 |                   |                    |                             |--Emit SCAN_EVENT:: JSON     |
 |                   |                    |                             |  per company scanned         |
 |                   |                    |                             |  per job found               |
 |                   |                    |<--stdout line by line-------|                              |
 |                   |                    |                             |                              |
 |                   |                    |  3. Throttle: flush events   |                              |
 |                   |                    |     to run_events every 0.5s |                              |
 |                   |                    |     or every 12 buffered     |                              |
 |                   |                    |                             |                              |
 |                   |                    |  4. _matches_targets() check |                              |
 |                   |                    |     keyword-based lightweight|                              |
 |                   |                    |     Filter: JOB_EVALUATED    |                              |
 |                   |                    |                             |                              |
 |                   |                    |  5. _append_to_brief():       |                              |
 |                   |                    |     APPEND (never wipe) to   |                              |
 |                   |                    |     today's brief items       |                              |
 |                   |                    |     -> daily_brief_items------>|                             |
 |                   |                    |                             |                              |
 |                   |                    |  6. _emit: SCAN_STARTED,     |                              |
 |                   |                    |     SOURCE_STARTED,          |                              |
 |                   |                    |     SOURCE_SCANNING (per co),|                              |
 |                   |                    |     JOB_FOUND (per role),    |                              |
 |                   |                    |     JOB_EVALUATED (match/no),|                              |
 |                   |                    |     FILTER_SUMMARY,          |                              |
 |                   |                    |     BRIEF_CREATED            |                              |
 |                   |                    |                             |                              |
 |                   |                    |--UPDATE COMPLETED------------>|                             |
```

### 3.5 Generate Brief (Brief Retrieval)

```
User              Frontend           BriefService            BriefsRepo              Supabase
 |                   |                    |                       |                      |
 |--Open /brief----->|                    |                       |                      |
 |                   |--GET /v1/briefs/latest?offset=0----------->|                      |
 |                   |                    |                       |                      |
 |                   |                    |--get_latest_brief()-->|                      |
 |                   |                    |                       |--SELECT * FROM       |
 |                   |                    |                       |  daily_briefs WHERE   |
 |                   |                    |                       |  user_id ORDER BY     |
 |                   |                    |                       |  date_str DESC        |
 |                   |                    |                       |  LIMIT 1 OFFSET $0--> |
 |                   |                    |                       |<--brief row-----------|
 |                   |                    |                       |                      |
 |                   |                    |                       |--get_items(brief_id)->|
 |                   |                    |                       |--SELECT * FROM       |
 |                   |                    |                       |  daily_brief_items   |
 |                   |                    |                       |  WHERE brief_id       |
 |                   |                    |                       |  ORDER BY item_index->|
 |                   |                    |                       |<--items[]-------------|
 |                   |                    |                       |                      |
 |                   |                    |--get_latest_brief(offset+1) for has_more------>|
 |                   |                    |<--serializers.brief()--|                      |
 |                   |<--{brief + items}--|                       |                      |
 |                   |                    |                       |                      |
 |                   |--Render JobCard[]  |                       |                      |
 |                   |  for each item     |                       |                      |
```

### 3.6 Approve/Skip Job

```
User              Frontend           JobService            JobsRepo               Supabase
 |                   |                    |                    |                      |
 |--Click Save------>|                    |                    |                      |
 |                   |--POST /jobs/{id}/save------------------>|                      |
 |                   |                    |--_resolve_uuid()-->|                      |
 |                   |                    |                    |--get_by_any_id()---->|
 |                   |                    |                    |<--job row------------|
 |                   |                    |                    |                      |
 |                   |                    |                    |--set_match_status()-->|
 |                   |                    |                    |  INSERT INTO         |
 |                   |                    |                    |  user_job_relationships|
 |                   |                    |                    |  ON CONFLICT         |
 |                   |                    |                    |  SET match_status=   |
 |                   |                    |                    |  'saved',            |
 |                   |                    |                    |  swiped_action=------>|
 |                   |                    |                    |<--ok-----------------|
 |                   |<--{saved}----------|                    |                      |
 |                   |                    |                    |                      |
 |--Click Skip------>|                    |                    |                      |
 |                   |--POST /jobs/{id}/skip------------------>|                      |
 |                   |                    |                    |--set_match_status()-->|
 |                   |                    |                    |  match_status=       |
 |                   |                    |                    |  'skipped',          |
 |                   |                    |                    |  swiped_action=------>|
 |                   |                    |                    |<--ok-----------------|
 |                   |<--{skipped}--------|                    |                      |
```

### 3.7 Inspect Job (Job Detail)

```
User              Frontend           JobService            JobsRepo               Supabase
 |                   |                    |                    |                      |
 |                   |                    |                    |                      |
 |--Click job card-->|                    |                    |                      |
 |  OR type number-->|                    |                    |                      |
 |                   |                    |                    |                      |
 |                   |--Option A: Navigate to /jobs/{jobId}--->|                      |
 |                   |                    |                    |                      |
 |                   |--GET /v1/jobs/{id}--------------------->|                      |
 |                   |                    |--get_by_any_id()-->|                      |
 |                   |                    |                    |--SELECT FROM jobs    |
 |                   |                    |                    |  WHERE id OR         |
 |                   |                    |                    |  job_id = $1-------->|
 |                   |                    |                    |<--job row------------|
 |                   |                    |                    |                      |
 |                   |                    |                    |--get_relationship()-->|
 |                   |                    |                    |--SELECT FROM         |
 |                   |                    |                    |  user_job_relationships|
 |                   |                    |                    |  WHERE user + job--->|
 |                   |                    |                    |<--rel row------------|
 |                   |                    |                    |                      |
 |                   |                    |<--serializers.job_detail()---------------|
 |                   |<--{job + rel}------|                    |                      |
 |                   |                    |                    |                      |
 |                   |--Option B: Chat "why this job"--------->|                      |
 |                   |  -> ToolRegistry.review_job()           |                      |
 |                   |  -> Loads from ApplicationLedger        |                      |
 |                   |  -> + repository_v2 enrichment          |                      |
 |                   |  -> Returns fit breakdown cards         |                      |
 |                   |                    |                    |                      |
 |--Also available:  |                    |                    |                      |
 |  "company intel"  |--show_company_intel()                   |                      |
 |    -> company_memory table            |                    |                      |
 |    -> + LinkedIn/Glassdoor/Reddit     |                    |                      |
 |    -> company_intel.py multi-source   |                    |                      |
 |                   |                    |                    |                      |
 |  "who to contact" |--show_people_to_reach()                 |                      |
 |    -> OutreachEngine.discover_leads() |                    |                      |
 |    -> DuckDuckGo search               |                    |                      |
 |                   |                    |                    |                      |
 |  "prepare this"   |--prepare_application_pack()             |                      |
 |    -> PackageAssembler thread          |                    |                      |
 |    -> background_runs + run_events    |                    |                      |
```

### 3.8 Generate Application Pack

```
User              Frontend           ToolRegistry          PackageAssembler         Supabase
 |                   |                    |                       |                    |
 |--"prepare this"--->|                    |                       |                    |
 |                   |--sendChatMessage()-->|                      |                    |
 |                   |                    |                       |                    |
 |                   |  ActionResolver -> PREPARE_APPLICATION_PACK|                    |
 |                   |                    |                       |                    |
 |                   |                    |--pack_id, run_id------|                    |
 |                   |                    |--INSERT background_runs (pack_generation, RUNNING)---------->|
 |                   |                    |--INSERT run_events (PACK_STARTED)----------->|
 |                   |                    |                       |                    |
 |                   |                    |--Thread.start()------>|                    |
 |                   |<--"Generating..."--|                       |                    |
 |                   |                    |                       |                    |
 |                   |                    |  [Daemon Thread]      |                    |
 |                   |                    |                       |                    |
 |                   |                    |  1. Load job from DB: |                    |
 |                   |                    |     SELECT title, company, description     |
 |                   |                    |     FROM careerloop.jobs WHERE id--->      |
 |                   |                    |                       |<--job row----------|
 |                   |                    |                       |                    |
 |                   |                    |  2. Load user profile:|                    |
 |                   |                    |     session_store._load_profile_data()     |
 |                   |                    |     -> master_cv_markdown                  |
 |                   |                    |                       |                    |
 |                   |                    |  3. Build council_state:                   |
 |                   |                    |     + company, job_title                   |
 |                   |                    |     + master_cv                            |
 |                   |                    |     + cover_note draft                     |
 |                   |                    |     + company_intelligence                 |
 |                   |                    |                       |                    |
 |                   |                    |  4. PackageAssembler.assemble_package()    |
 |                   |                    |     -> Resume Council (LLM)                |
 |                   |                    |     -> Cover letter generation             |
 |                   |                    |     -> Outreach strategy                   |
 |                   |                    |     -> Save pack dir to disk               |
 |                   |                    |                       |                    |
 |                   |                    |  5. Persist:          |                    |
 |                   |                    |     INSERT INTO application_packs -------->|                    |
 |                   |                    |     (pack_id, user_id, job_id, COMPLETED)   |                    |
 |                   |                    |     INSERT run_events (PACK_COMPLETED)------>|                    |
 |                   |                    |     UPDATE background_runs COMPLETED-------->|                    |
 |                   |                    |                       |                    |
 |                   |  User checks background_runs or re-asks   |                    |
 |                   |  "show my pack" -> reads application_packs |                    |
```

### 3.9 Resume Editing

```
User              Frontend           ToolRegistry          LLM (DeepSeek)          Supabase
 |                   |                    |                       |                    |
 |--"edit resume:     |                    |                       |                    |
 |  add AWS cert"---->|                    |                       |                    |
 |                   |--sendChatMessage()-->|                      |                    |
 |                   |                    |                       |                    |
 |                   |  ActionResolver -> EDIT_APPLICATION_PACK   |                    |
 |                   |                    |                       |                    |
 |                   |                    |--INSERT background_runs (resume_edit, RUNNING)------------>|
 |                   |                    |--INSERT run_events (EDIT_STARTED)--------->|                    |
 |                   |                    |                       |                    |
 |                   |                    |--Thread.start()------>|                    |
 |                   |                    |                       |                    |
 |                   |                    |  [Daemon Thread]      |                    |
 |                   |                    |                       |                    |
 |                   |                    |  1. Load profile:     |                    |
 |                   |                    |     session_store._load_profile_data()     |
 |                   |                    |     -> master_cv_markdown                  |
 |                   |                    |                       |                    |
 |                   |                    |  2. LLM call:         |                    |
 |                   |                    |     _apply_resume_edit()                   |
 |                   |                    |     system: "You are a resume editor..."   |
 |                   |                    |     user: "RESUME: {cv}\nEDIT: {instr}"--->|
 |                   |                    |                       |--process---------->|
 |                   |                    |                       |<--updated CV-------|
 |                   |                    |                       |                    |
 |                   |                    |  3. Save to session + users table:         |
 |                   |                    |     session.temp_profile_data updated      |
 |                   |                    |     session_store.save_session()           |
 |                   |                    |     UPDATE careerloop.users                |
 |                   |                    |     SET master_cv_markdown -------------->|
 |                   |                    |                       |                    |
 |                   |                    |  4. INSERT run_events (EDIT_COMPLETED)---->|                    |
 |                   |                    |     UPDATE background_runs COMPLETED-------->|                    |
```

### 3.10 Chat History Persistence & Restoration

```
User              Frontend           ChatService           SessionStore          Supabase
 |                   |                    |                      |                   |
 |--Login/Refresh--->|                    |                      |                   |
 |                   |--GET /v1/chat/history------------------->|                   |
 |                   |                    |--get_history(user_id)|                   |
 |                   |                    |                      |                   |
 |                   |                    |--get_session()------>|                   |
 |                   |                    |                      |--SELECT FROM      |
 |                   |                    |                      |  sessions-------> |
 |                   |                    |                      |<--session---------|
 |                   |                    |                      |                   |
 |                   |                    |--Read _active_conversation_id from       |
 |                   |                    |  session.temp_profile_data               |
 |                   |                    |                      |                   |
 |                   |                    |--SELECT role, content, action_type,      |
 |                   |                    |  created_at FROM careerloop.messages     |
 |                   |                    |  WHERE conversation_id                  |
 |                   |                    |  ORDER BY created_at ASC LIMIT 50------> |
 |                   |                    |<--messages[]--------|                   |
 |                   |                    |                      |                   |
 |                   |<--{messages, state}|                      |                   |
 |                   |                    |                      |                   |
 |--Restore UI------>|                    |                      |                   |
 |                   |                    |                      |                   |
 |--Send new msg---->|                    |                      |                   |
 |                   |--POST /chat/message|                      |                   |
 |                   |  {text, conversation_id}                  |                   |
 |                   |                    |                      |                   |
 |                   |                    |--_ensure_conversation(user_id)           |
 |                   |                    |  (creates if not existing)               |
 |                   |                    |                      |                   |
 |                   |                    |--save_message(user, role="user")-------->|                   |
 |                   |                    |                      |--INSERT messages-->|
 |                   |                    |                      |                   |
 |                   |                    |--_load_conversation_history()            |
 |                   |                    |  last 20 messages for context            |
 |                   |                    |  -> LangChain HumanMessage/AIMessage     |
 |                   |                    |  -> passes to supervisor_graph           |
 |                   |                    |                      |                   |
 |                   |                    |--LangGraph PostgresSaver checkpointer    |
 |                   |                    |  -> public.checkpoints                   |
 |                   |                    |  -> public.checkpoint_blobs              |
 |                   |                    |  -> public.checkpoint_writes             |
 |                   |                    |  (auto-persists graph state)             |
 |                   |                    |                      |                   |
 |                   |                    |--After response:     |                   |
 |                   |                    |  save_message(assistant, content)-------->|                  |
 |                   |                    |  Persist artifact_context to session      |                   |
 |                   |                    |  -> session_store.save_session()         |                   |
```

---

## 4. Database Map

### Connection: Supabase PostgreSQL (aws-1-ap-southeast-1.pooler.supabase.com:6543)

### Schema: `careerloop` (38 tables)

| # | Table | Rows | Purpose | Writer | Reader | PK | Key FKs |
|---|-------|------|---------|--------|--------|----|---------|
| T-01 | `users` | 22 | User profiles, CV, preferences | auth.py, onboarding_flow.py, session_store.py | All services | `id` (uuid) | -- |
| T-02 | `sessions` | 18 | User journey state + active context | session_store.py, chat_service.py | supervisor_graph, chat_service | `user_id` (uuid) | `user_id` -> users.id |
| T-03 | `conversations` | 3 | Chat conversation containers | chat_service.py | chat_service.py | `id` (uuid) | `user_id` -> users.id |
| T-04 | `messages` | 18 | Individual chat messages | chat_service.py, session_store.py | chat_service.py | `id` (uuid) | `conversation_id` -> conversations.id |
| T-05 | `daily_briefs` | 5 | Generated daily job briefs | scan_service.py, tool_registry.py, daily_runner.py | brief_service.py, tool_registry.py | `id` (uuid) | `user_id` -> users.id |
| T-06 | `daily_brief_items` | 6 | Individual jobs within a brief | scan_service.py, tool_registry.py | brief_service.py, tool_registry.py | `id` (uuid) | `brief_id` -> daily_briefs.id |
| T-07 | `jobs` | 7 | Global job cache (deduped by fingerprint) | scan_service.py, tool_registry.py, repository_v2.py | job_service.py, brief_service.py | `id` (text), `job_id` (uuid) | `company_id` -> companies.id |
| T-08 | `job_candidates` | 5 | Raw scraped candidates before dedup | tool_registry.py (V3 pipeline) | -- | `candidate_id` (uuid) | `run_id` -> background_runs.run_id |
| T-09 | `user_job_relationships` | 10 | Per-user job match/skip/save state | tool_registry.py, jobs_repo.py | job_service.py, tool_registry.py | `(user_id, job_id)` | `user_id` -> users.id, `job_id` -> jobs.job_id |
| T-10 | `companies` | 5 | Company registry (deduped by domain_slug) | tool_registry.py, repository_v2.py | tool_registry.py | `id` (uuid) | -- |
| T-11 | `company_memory` | 5 | Company intelligence (multi-source research) | tool_registry.py | tool_registry.py | `id` (uuid) | `user_id` -> users.id |
| T-12 | `background_runs` | 35 | Async execution tracking (scans, packs, edits) | scan_service.py, tool_registry.py | scan_service.py, tool_registry.py | `run_id` (text) | `user_id` -> users.id |
| T-13 | `run_events` | 569 | Streamable execution events (SSE) | scan_service.py, tool_registry.py | scan_service.py (SSE) | `event_id` (text) | `run_id` -> background_runs.run_id |
| T-14 | `application_packs` | 0 | Generated application packs | tool_registry.py | tool_registry.py | `pack_id` (uuid) | `user_id` -> users.id |
| T-15 | `applications` | 0 | Submitted job applications | -- | -- | `application_id` (uuid) | `user_id` -> users.id |
| T-16 | `application_ledger` | 0 | V3 canonical application ledger | -- | -- | `id` (uuid) | `user_id` -> users.id |
| T-17 | `job_search_runs` | 0 | Search run analytics | -- | -- | `id` (uuid) | `user_id` -> users.id |
| T-18 | `job_sources` | 0 | Per-job source tracking | -- | -- | `id` (uuid) | `job_id` -> jobs.id |
| T-19 | `event_timeline` | 0 | Chronological user activity log | -- | -- | `id` (uuid) | `user_id` -> users.id |
| T-20 | `followups` | 0 | Application follow-up tracking | -- | -- | `followup_id` (uuid) | `user_id` -> users.id |
| T-21 | `memory_events` | 2 | Memory lifecycle events | -- | -- | `id` (uuid) | `user_id` -> users.id |
| T-22 | `outcome_events` | 0 | Job search outcome tracking | -- | -- | `outcome_id` (uuid) | `user_id` -> users.id |
| T-23 | `outreach_messages` | 0 | Sent outreach messages | -- | -- | `message_id` (uuid) | `user_id` -> users.id |
| T-24 | `people_to_reach` | 0 | Discovered contacts at companies | -- | -- | `person_id` (uuid) | `company_id` -> companies.id |
| T-25 | `positioning_memory` | 0 | Learned positioning strategies | -- | -- | `id` (uuid) | `user_id` -> users.id |
| T-26 | `recruiter_contacts` | 0 | Known recruiter contacts | -- | -- | `id` (uuid) | `company_id` -> companies.id |
| T-27 | `strategic_tracks` | 0 | Multi-track career strategies | -- | -- | `id` (uuid) | `user_id` -> users.id |
| T-28 | `user_evidence` | 0 | User's proof points / portfolio items | -- | -- | `evidence_id` (uuid) | `user_id` -> users.id |
| T-29 | `user_preferences` | 0 | Structured user preferences | -- | -- | `user_id` (uuid) | `user_id` -> users.id |

### Schema: `public` (LangGraph checkpointer + Emote app tables)

| # | Table | Rows | Purpose | Writer | Reader |
|---|-------|------|---------|--------|--------|
| P-01 | `checkpoints` | 83 | LangGraph conversation state snapshots | LangGraph PostgresSaver | LangGraph PostgresSaver |
| P-02 | `checkpoint_blobs` | 141 | LangGraph serialized state blobs | LangGraph PostgresSaver | LangGraph PostgresSaver |
| P-03 | `checkpoint_writes` | 271 | LangGraph pending writes | LangGraph PostgresSaver | LangGraph PostgresSaver |
| P-04 | `checkpoint_migrations` | 10 | LangGraph schema version tracking | LangGraph PostgresSaver | LangGraph PostgresSaver |
| P-05 | `emote_conversations` | 10,460 | Emote app conversation logs | Emote app | Emote app |
| P-06 | `emote_users` | 520 | Emote app user records | Emote app | Emote app |
| P-07 | `emote_starters` | 349 | Emote app starter messages | Emote app | Emote app |
| P-08 | `conversation_logs_json` | 0 | Legacy conversation logs (deprecated) | -- | -- |
| P-09 | `semantic_embeddings` | 2 | Vector embeddings for memory | -- | -- |
| P-10 | `user_embedding_stats` | 1 | Embedding usage statistics | -- | -- |
| P-11 | `users` | 14 | Alternative public users table (partial duplicate of careerloop.users) | -- | -- |

---

## 5. Event Map

### 5.1 SSE Event Stream (Scan)

**Producer:** `scan_service.py::stream_scan_events()` (polling)
**Consumer:** Frontend `ChatPage.tsx` via `EventSource`
**Medium:** `careerloop.run_events` table (polled every 1s)
**Transport:** HTTP SSE (`text/event-stream`)

Event types emitted during scan lifecycle:

| Event Type | Producer | Meaning |
|-----------|----------|---------|
| `QUEUED` | scan_service.py::initiate_scan | Scan accepted, queued for execution |
| `SCAN_STARTED` | scan_service.py::_execute_scan | Discovery initialized |
| `SOURCE_STARTED` | scan_service.py::_execute_scan | Portal querying started |
| `SOURCE_SCANNING` | scan_service.py::_execute_scan_more | Live per-company scan progress |
| `CACHE_HIT` | scan_service.py::_execute_scan | Fresh cached jobs found (>= 5) |
| `JOB_FOUND` | scan_service.py::_execute_scan_more | Raw job found during scan_more |
| `JOB_EVALUATED` | scan_service.py::_execute_scan_more | Job matched or skipped against targets |
| `CANDIDATE_MATCHED` | scan_service.py::_execute_scan, tool_registry.py::start_scan | "MATCH #N — Title @ Company — Score/100" |
| `FILTER_SUMMARY` | scan_service.py | "X raw, Y new, Z scored" |
| `BRIEF_CREATED` | scan_service.py, tool_registry.py | Brief persisted and ready for retrieval |
| `DONE` | scan_service.py::stream_scan_events | Stream complete, EventSource should close |
| `TIMEOUT` | scan_service.py::stream_scan_events | 5-minute hard timeout reached |
| `ERROR` | scan_service.py::stream_scan_events | Stream error |
| `SCAN_FAILED` | scan_service.py::_mark_scan_failed | Scan worker crashed |

### 5.2 Background Run Events (Pack Generation, Resume Edit)

**Producer:** `tool_registry.py` (daemon threads)
**Consumer:** Frontend polling `GET /v1/scans/{run_id}` or SSE
**Medium:** `careerloop.run_events` + `careerloop.background_runs`

| Event Type | Producer | Meaning |
|-----------|----------|---------|
| `PACK_STARTED` | tool_registry.py::prepare_application_pack | Pack generation started |
| `PACK_COMPLETED` | tool_registry.py::_pack_thread | Pack assembled successfully |
| `PACK_FAILED` | tool_registry.py::_pack_thread | Pack generation error |
| `EDIT_STARTED` | tool_registry.py::edit_application_pack | Resume edit started |
| `EDIT_COMPLETED` | tool_registry.py::_edit_thread | Resume edit applied successfully |
| `EDIT_FAILED` | tool_registry.py::_edit_thread | Resume edit error |

### 5.3 Daemon Threads

| Thread | Spawned By | Purpose | Lifecycle |
|--------|-----------|---------|-----------|
| Scan Worker | scan_service.py::initiate_scan | Runs full scan pipeline | Exits on COMPLETED/FAILED |
| Scan More Worker | scan_service.py::initiate_scan (mode=scan_more) | Runs live portal scan | Exits on COMPLETED/FAILED |
| Scan Thread (chat) | tool_registry.py::start_scan | Alternative scan from chat | Exits on COMPLETED/FAILED |
| Pack Thread | tool_registry.py::prepare_application_pack | Generates application pack | Exits on COMPLETED/FAILED |
| Edit Thread | tool_registry.py::edit_application_pack | Applies resume edit | Exits on COMPLETED/FAILED |
| Chat Timeout Thread | chat_service.py::_run_with_timeout | Guards against LLM/DB hangs | Exits after timeout or completion |
| DB Acquire Timeout Thread | connection.py::_acquire_conn_with_timeout | Guards against pool exhaustion | Exits after timeout or acquisition |

### 5.4 Concurrency Guards

| Guard | Type | Scope | Purpose |
|-------|------|-------|---------|
| `_active_scans` dict + lock | Mutex | Per-user | One scan per user at a time |
| `_worker_semaphore` (BoundedSemaphore(3)) | Semaphore | Global | Max 3 concurrent scan workers |
| `_PROVISION_TTL` (300s) + lock | Cache | Per-user | Skip DB write on repeated auth |
| `inFlight` Map (frontend) | Dedup | Per-request | Prevent duplicate concurrent API calls |
| `_db_singleton_lock` | Mutex | Global | Single DatabaseManager instance |

### 5.5 Event Architecture Summary

| System | Pattern | Dependency |
|--------|---------|------------|
| Scan SSE | Polling (1s) + DB as event bus | Depends on PostgreSQL |
| Chat (API) | Synchronous request-response with 120s timeout thread | Depends on LLM (DeepSeek) |
| Chat (Telegram) | Synchronous webhook -> push via Telegram API | Depends on Telegram |
| Pack Generation | Fire-and-forget daemon thread, result in DB | Depends on LLM (DeepSeek) |
| Resume Edit | Fire-and-forget daemon thread, result in DB | Depends on LLM (DeepSeek) |
| LangGraph Checkpoints | Automatic persistence on every graph invocation | Depends on PostgreSQL |
| Daily Runner (CLI) | Synchronous sequential execution | Depends on LLM (DeepSeek) + Node.js |

---

## 6. State Machine Map

### 6.1 User Journey State (UserJourneyState)

**File:** `careerloop/session/states.py`
**Persistence:** `careerloop.sessions.state` column
**Transitions managed by:** OnboardingFlow, ChatService, ToolRegistry

```
                    +-----------+
                    | NEW_USER  |
                    +-----+-----+
                          |
          +---------------+---------------+
          |                               |
    OnboardingFlow                  Tool call triggers
    handles messages                 (blocked: only /help, /reset allowed)
          |
    STEP_IDLE (0) -> ask name
    STEP_IDENTIFYING (10) -> LinkedIn lookup
    STEP_PROFILE_CONFIRMATION (11) -> "Is this you?"
    STEP_WAITING_CV (1) -> CV extraction
    STEP_CONFIRMING (2) -> "Is this correct?"
    STEP_COLLECTING (3) -> gap-fill missing fields
          |
    _complete_onboarding()
          |
          v
    +------------------+
    | PROFILE_READY    | <--- All tools unlocked
    +--------+---------+
             |
    +--------+---------+
    |                  |
    v                  v
+------------------+  +-------------------+
| APPLICATION_     |  | INTERVIEW_ACTIVE  |
| PENDING          |  | (planned, not     |
| (on MARK_APPLIED)|  |  yet implemented) |
+------------------+  +-------------------+
```

### 6.2 Onboarding Step State Machine

**File:** `careerloop/onboarding/onboarding_flow.py`
**Persistence:** `careerloop.sessions.onboarding_step` (integer)

```
STEP_IDLE (0)
    |-- user typed name in first message -> STEP_IDENTIFYING
    |-- else -> prompt "What's your name?" -> STEP_IDENTIFYING
    v
STEP_IDENTIFYING (10)
    |-- LinkedIn match found -> PROFILE_CONFIRMATION
    |-- LinkedIn fail / user pasted CV (len >= 80) -> STEP_WAITING_CV
    v
STEP_PROFILE_CONFIRMATION (11)
    |-- YES -> hydrate from LinkedIn -> STEP_WAITING_CV
    |-- NO / SKIP -> manual -> STEP_WAITING_CV
    v
STEP_WAITING_CV (1)
    |-- CV text pasted -> CVExtractionAgent -> STEP_CONFIRMING
    |-- SKIP (if LinkedIn hydrated) -> _proceed_after_linkedin
    v
STEP_CONFIRMING (2)
    |-- YES -> check REQUIRED_FIELDS
    |   |-- all present -> _complete_onboarding() -> PROFILE_READY
    |   |-- missing -> STEP_COLLECTING
    |-- correction -> OnboardingAgent.process() -> re-display -> STEP_CONFIRMING
    v
STEP_COLLECTING (3)
    |-- OnboardingAgent.process() each message
    |-- is_complete and no missing fields -> _complete_onboarding() -> PROFILE_READY
    |-- else -> stay in STEP_COLLECTING, ask remaining fields
```

### 6.3 Background Run State Machine

**File:** `careerloop/session/states.py::BackgroundWorkStatus`
**Persistence:** `careerloop.background_runs.status`

```
QUEUED --> RUNNING --> COMPLETED
            |       \-> FAILED
            \-> CANCELLED
```

**Run Types using this state machine:**
- `scan` — job discovery scans
- `pack_generation` — application pack assembly
- `resume_edit` — resume editing

**Stale Recovery:** On module import, scan_service.py marks any `RUNNING` scan older than 30 minutes as `FAILED`.

### 6.4 Legacy State Migration

**File:** `careerloop/session/states.py::_LEGACY_MAP`

18 legacy V1 states (IDLE, ONBOARDING_Q1_ROLES, SCAN_RUNNING, REVIEWING_JOB, PACK_GENERATING, etc.) are mapped to the 4 V2 UserJourneyStates on read. New writes always use V2 values.

---

## 7. Dead Code Report

### Confirmed Dead/Unused Tables (0 rows, no writer found)

| Table | Rows | Status | Assessment |
|-------|------|--------|------------|
| `careerloop.application_ledger` | 0 | DEAD | V3 canonical ledger — never populated by any code path |
| `careerloop.application_packs` | 0 | STALE | Pack generation saves to DB but no retrieval path exists |
| `careerloop.applications` | 0 | DEAD | No code path writes to this table |
| `careerloop.job_search_runs` | 0 | DEAD | Search run analytics — never written |
| `careerloop.job_sources` | 0 | DEAD | Per-job source tracking — never written |
| `careerloop.event_timeline` | 0 | DEAD | Activity log — never written |
| `careerloop.followups` | 0 | DEAD | Follow-up tracking — never written |
| `careerloop.outcome_events` | 0 | DEAD | Outcome tracking — never written |
| `careerloop.outreach_messages` | 0 | DEAD | Outreach message tracking — never written |
| `careerloop.people_to_reach` | 0 | DEAD | Contact discovery results — never written |
| `careerloop.positioning_memory` | 0 | DEAD | Positioning strategies — never written |
| `careerloop.recruiter_contacts` | 0 | DEAD | Recruiter contacts — never written |
| `careerloop.strategic_tracks` | 0 | DEAD | Multi-track strategies — never written |
| `careerloop.user_evidence` | 0 | DEAD | User proof points — never written |
| `careerloop.user_preferences` | 0 | DEAD | Structured preferences — never written; preferences stored in users.work_style_prefs JSONB instead |
| `public.conversation_logs_json` | 0 | DEAD | Legacy conversation logs — superseded by careerloop.messages |
| `public.users` | 14 | LEGACY | Partially duplicated from careerloop.users; appears to be an older schema |

### Dead/Unused Code Paths

| Code | File | Status | Assessment |
|------|------|--------|------------|
| `message_router.py` | careerloop/session/ | DEAD | V1 message router, superseded by action_resolver + supervisor_graph |
| `user_registry.py` | careerloop/session/ | DEAD | No references found in any active code path |
| `tests_router.py` | careerloop/session/ | DEAD | Test file, not imported anywhere |
| `crawl_cache.py` | careerloop/sources/ | LIKELY DEAD | No references found in scan pipeline |
| `portal_scraper.py` | careerloop/sources/ | LIKELY DEAD | Superseded by scan.mjs |
| `whatsapp_ux.py` | careerloop/ | DEAD | WhatsApp transport planned but never wired |
| `kimi_bridge.py` | careerloop/execution/ | STUB | Mock stub, never connected to real Hermes endpoint |
| `terminal_chat.py` | careerloop/transport/ | STALE | CLI transport exists but not integrated with supervisor_graph |

### ApplicationLedger — Filesystem JSON (Legacy Persistence)

The `ApplicationLedger` (`careerloop/application_ledger.py`) persists to `data/ledger.json` on disk. This is the legacy filesystem-based ledger that the V2 pipeline (DailyRunner, ToolRegistry skip/save/mark_applied) still uses. The V3 pipeline writes to `careerloop.user_job_relationships` table, creating a dual-persistence problem.

**Filesystem dependency locations:**
- `daily_runner.py` line 60: `self.ledger = ApplicationLedger(self.root)`
- `tool_registry.py` lines 759, 777, 795, 866, 1179: Various tool handlers use `ApplicationLedger`
- `tool_registry.py` line 407: `_ledger = ApplicationLedger(_root2)` in V3 pipeline fallback

---

## 8. Orphan Service Report

### Services Without Consumers

| Service | File | Problem |
|---------|------|---------|
| `application_packs` table | DB | Pack is generated and saved, but no API endpoint retrieves packs |
| `kimi_bridge.py` | careerloop/execution/ | Built as mock stub, never connected |
| `TransportAdapter` (base.py) | careerloop/transport/ | Abstract class; only TelegramAdapter implements it. Web (REST API) bypasses it entirely |
| `sync_profile.py` | careerloop/tools/ | Profile sync tool exists but was removed from DAILY_BRIEF_SENT handler |
| `jobs table` V2 columns | DB | Columns like `role_summary`, `responsibilities`, `requirements`, `benefits` are never populated |
| `companies table` enrichment fields | DB | `sector`, `subsector`, `employee_estimate`, `funding_stage` never populated by scan pipeline |

### Services With Dual Implementations

| Function | V1/V2 Implementation | V3 Implementation | Status |
|----------|---------------------|-------------------|--------|
| Job dedup | ApplicationLedger (JSON file) | jobs.content_fingerprint (DB) | Both active |
| Job scoring | IndiaFitEngine (LLM) | fit_score in user_job_relationships | Both active |
| Brief storage | filesystem (output/daily_briefs/) | careerloop.daily_briefs (DB) | Both active |
| Job persistence | pipeline.md (markdown file) | careerloop.jobs (DB) | Both active |
| Session state | sessions table (DB) | LangGraph checkpoints (DB) | Both active, no reconciliation |
| Chat history | messages table (DB) | LangGraph checkpoints (DB) | Both active, independent |

---

## 9. Critical Dependency Report

### Layer Dependency Graph

```
Frontend (React SPA)
  |-- depends on: Supabase Auth (Google OAuth)
  |-- depends on: careerloop_api (REST + SSE)
  |-- depends on: @microsoft/fetch-event-source (SSE client)
  |
careerloop_api (FastAPI :8001)
  |-- depends on: Supabase JWT verification
  |-- depends on: careerloop.session (supervisor_graph)
  |-- depends on: careerloop.onboarding (onboarding_flow)
  |-- depends on: careerloop.memory (connection, repository_v2)
  |-- depends on: careerloop.daily_runner (scan pipeline)
  |-- depends on: careerloop.package_assembly (pack generation)
  |-- depends on: scan.mjs (Node.js subprocess)
  |-- depends on: PostgreSQL (Supabase)
  |-- depends on: DeepSeek API (LLM)
  |-- depends on: SerpAPI (LinkedIn lookup — optional)
  |
careerloop.transport.webhook_server (FastAPI :8000)
  |-- depends on: careerloop.session (supervisor_graph)
  |-- depends on: careerloop.onboarding (onboarding_flow)
  |-- depends on: careerloop.transport.telegram (TelegramAdapter)
  |-- depends on: Telegram Bot API
  |-- depends on: PostgreSQL (Supabase)
  |
careerloop.session.supervisor_graph (LangGraph)
  |-- depends on: careerloop.session.action_resolver (LLM call)
  |-- depends on: careerloop.session.tool_registry (17 tools)
  |-- depends on: careerloop.session.session_store (DB)
  |-- depends on: careerloop.memory.connection (DB pool)
  |-- depends on: careerloop.memory.checkpointer (LangGraph persistence)
  |-- depends on: DeepSeek API (LLM)
  |
careerloop.daily_runner (CLI pipeline)
  |-- depends on: scan.mjs (Node.js subprocess)
  |-- depends on: careerloop.india_fit_engine (LLM scoring)
  |-- depends on: careerloop.application_ledger (JSON file)
  |-- depends on: careerloop.india_filter (geo filter)
  |-- depends on: careerloop.profile_manager (YAML config)
  |-- depends on: filesystem (pipeline.md, ledger.json)
  |-- depends on: DeepSeek API (LLM)
```

### Critical Single Points of Failure

| Component | Failure Impact | Mitigation |
|-----------|---------------|------------|
| Supabase PostgreSQL | ALL state lost — sessions, briefs, jobs, users, chat, onboarding | Connection pool with timeout; SQLite fallback for some functions |
| DeepSeek API | LLM calls fail — action resolution, onboarding, scoring, pack generation | Timeout guards (120s); fallback messages in tool handlers |
| scan.mjs (Node.js) | Job discovery fails completely | Subprocess timeout (60s); cache-first fallback |
| DatabaseManager singleton | If pool exhausts (maxconn=20), all DB operations hang | 10s acquire timeout; BoundedSemaphore(3) for scan workers |
| LangGraph PostgresSaver | Conversation state lost; chat amnesia on restart | MemorySaver fallback (in-memory, no persistence) |

### External API Dependencies

| API | Purpose | Optional? | Failure Mode |
|-----|---------|-----------|-------------|
| DeepSeek | All LLM operations | NO | All LLM features fail |
| Supabase PostgreSQL | All data persistence | NO | Complete system outage |
| Supabase Auth | Google OAuth + JWT | NO | Users cannot authenticate |
| Telegram Bot API | Telegram transport | YES (web still works) | Telegram bot offline |
| SerpAPI | LinkedIn profile lookup | YES | Manual CV entry fallback |
| Greenhouse/Lever/Ashby APIs | Job portal scanning | YES | Only cached jobs shown |

---

## 10a. Discovery Unification (2026-05-29)

**Change:** All job discovery now unified through `careerloop/on_demand.py::OnDemandSearch`.

**What was unified:**
- `scan.mjs` (Node.js ATS scanner) — deprecated, use `OnDemandSearch`
- `careerloop/discovery.py` (Python DDG search) — deprecated, use `OnDemandSearch`
- `careerloop/daily_runner.py::run()` (discovery path) — deprecated, use `OnDemandSearch`

**SSE contract canonicalized:**
- `careerloop_api/services/scan_service.py::stream_scan_events()` is the sole producer
- Frontend `EventSource` in `ChatPage.tsx` is the sole consumer
- 15 event types defined: SCAN_STARTED, SCAN_COMPLETED, SCAN_FAILED, SOURCE_SCANNING, JOB_FOUND, JOB_EVALUATED, JOB_REJECTED, CANDIDATE_MATCHED, BRIEF_ADDED, QUEUED, CACHE_HIT, FILTER_SUMMARY, BRIEF_CREATED, DONE, TIMEOUT, ERROR. See CANONICAL_ARCHITECTURE.md §9 for the full contract.

**Impact:** This eliminates Risk 3 (`scan.mjs` as Node.js dependency in Python backend) by making `OnDemandSearch` the canonical entry point. The Node.js subprocess still runs under the hood but is no longer a direct dependency of any production path — it is wrapped by `OnDemandSearch`.

## 11. Top 10 Architectural Risks

### Risk 1: Four Independent Persistence Stacks

**Severity: CRITICAL**
**Files:** session_store.py, checkpointer.py, application_ledger.py, daily_runner.py

The system has four separate persistence layers with no reconciliation:
1. `careerloop.sessions` table (UserJourneyState + ActiveContext)
2. LangGraph checkpoints (`public.checkpoints`) (conversation state)
3. `ApplicationLedger` (filesystem `data/ledger.json`)
4. File-based brief storage (`output/daily_briefs/{date}.md`)

Session state and LangGraph state can desync — a state transition in one is not reflected in the other. The `ApplicationLedger` (V2) and `user_job_relationships` (V3) both track job status independently, leading to "ghost" entries in one but not the other.

**Impact:** State desynchronization, "CV re-ask" bug (confirmed and documented), phantom job entries, inconsistent brief views.

### Risk 2: Hardcoded Database Credentials in Git History

**Severity: CRITICAL**
**Status:** Credential removed from current code (Phase 0-A fix applied 2026-05-24), but git history still contains the password `FS48TIvMiumRin8a` and full DATABASE_URL.

**Impact:** Any clone of the repository can extract production Supabase credentials from `git log`.

### Risk 3: scan.mjs Dependency — Node.js in Python Backend

**Severity: HIGH**
**File:** scan_service.py lines 423-427, daily_runner.py lines 329-335

The job discovery pipeline depends on `scan.mjs` (a Node.js script) being available on the server filesystem and invocable via `subprocess.Popen`. This creates a hard runtime dependency on Node.js in what is otherwise a Python-only backend. If `scan.mjs` is missing, crashes, or the Node.js runtime is unavailable, the entire scan pipeline fails.

**Impact:** No job discovery on servers without Node.js.

### Risk 4: Daemon Threads Without Supervision

**Severity: HIGH**
**Files:** scan_service.py line 159, tool_registry.py lines 532, 1037, 1160

Five different daemon threads are spawned throughout the codebase:
- Scan workers (scan_service.py)
- Scan workers from chat (tool_registry.py)
- Pack generation threads (tool_registry.py)
- Resume edit threads (tool_registry.py)
- Chat timeout threads (chat_service.py)

Daemon threads are killed silently on process exit. If the uvicorn worker restarts (e.g., Railway/Render auto-restart), running scans and pack generations are abandoned mid-execution. The stale scan recovery (30-min timeout) partially mitigates this but does not handle pack_generation or resume_edit runs.

**Impact:** Abandoned background runs, incomplete packs, zombie run_events.

### Risk 5: Frontend Route Architecture — Browser as Router

**Severity: MEDIUM**
**File:** App.tsx

The React SPA uses client-side routing only (react-router-dom). There is no server-side rendering or static file serving in the FastAPI backend. All routes (including `/brief`, `/jobs/:jobId`, `/chat`) are client-side only. If a user refreshes on `/brief`, the SPA re-mounts and re-fetches from scratch — the brief cache in `sessionStorage` is the only mitigation.

**Impact:** Full page reload on any refresh, loss of unsaved chat context, no deep-link SEO.

### Risk 6: General Chat with Hardcoded Profile Injection

**Severity: MEDIUM**
**File:** supervisor_graph.py lines 112-153

The GENERAL_CHAT handler injects user profile data (name, email, target roles, cities, salary, CV status) into the LLM prompt. This means every casual conversation sends the user's full profile context to the LLM, including PII (email). For a chatty user, this is a token cost multiplier and a privacy concern.

**Impact:** Unnecessary LLM token consumption, PII exposure in every chat turn.

### Risk 7: Connection Pool Exhaustion Risk

**Severity: MEDIUM**
**File:** connection.py lines 162-163

The `DatabaseManager` creates a `ThreadedConnectionPool` with default `maxconn=20`. The scan_service creates a separate `_build_components()` path that calls `get_db_manager()` — potentially creating a separate pool. Additionally, the LangGraph checkpointer creates its OWN `psycopg_pool.ConnectionPool` (checkpointer.py line 30), separate from the DatabaseManager pool.

**Impact:** Connection count = DatabaseManager pool (20) + Checkpointer pool (unknown) = potentially exceeding Supabase free tier limit (15 connections).

### Risk 8: Dual-Router Architecture for Chat

**Severity: MEDIUM**
**Files:** chat_service.py vs webhook_server.py

Chat messages take two completely different code paths depending on transport:
- **Web (chat_service.py):** NEW_USER -> OnboardingFlow, PROFILE_READY+ -> supervisor_graph WITH checkpointer and conversation history loading
- **Telegram (webhook_server.py):** Same logic but with NO checkpointer, NO conversation history loading, NO artifact context persistence, and direct `send_text()` instead of structured response

This means Telegram users get a degraded experience (no chat history, no context awareness) despite going through the "same" supervisor graph.

**Impact:** Feature parity gap between web and Telegram; Telegram users have no conversation memory.

### Risk 9: 15 Zero-Row Database Tables (Schema Bloat)

**Severity: LOW**

15 of 29 `careerloop.*` tables have zero rows and no code path writes to them. These represent planned but unimplemented features. They consume schema namespace, add confusion during debugging, and create false expectations about system capabilities.

**Impact:** Maintenance confusion, misleading schema documentation.

### Risk 10: ApplicationLedger as Filesystem-Based State

**Severity: MEDIUM**
**File:** careerloop/application_ledger.py

The ApplicationLedger persists to `data/ledger.json` — a local JSON file. In a multi-worker deployment (multiple uvicorn workers or multiple server instances), each instance has its own independent ledger file. Job save/skip/mark_applied operations in one instance are invisible to others. The V3 `user_job_relationships` table solves this, but the ToolRegistry still uses the filesystem ledger exclusively for save/skip/mark_applied operations.

**Impact:** Inconsistent job status across instances in multi-worker deployments.

---

## Appendix: File Index

### Core Session Layer
| File | Lines | Purpose |
|------|-------|---------|
| session/states.py | 107 | UserJourneyState enum + legacy migration |
| session/models.py | 47 | Action, ActionType, ResponseEnvelope |
| session/action_resolver.py | 167 | LLM-based intent resolution (17 action types) |
| session/supervisor_graph.py | 249 | LangGraph StateGraph (2 nodes: action_routing + execute_action) |
| session/tool_registry.py | 1237 | 17 tool handler implementations |
| session/session_store.py | 391 | Session CRUD + profile recovery |

### API Layer
| File | Lines | Purpose |
|------|-------|---------|
| api/main.py | 60 | FastAPI app with CORS + error handlers |
| api/routers/auth.py | 28 | POST /v1/auth/me |
| api/routers/chat.py | 29 | POST /v1/chat/message, GET /v1/chat/history |
| api/routers/scans.py | 126 | POST /v1/scans, GET SSE events + status |
| api/routers/briefs.py | 30 | GET /v1/briefs/latest, POST select item |
| api/routers/jobs.py | 26 | GET/POST /v1/jobs/{id}, save, skip |
| api/routers/users.py | 21 | GET /v1/me, GET /v1/me/preferences |
| api/services/chat_service.py | 285 | Chat orchestrator (onboarding + supervisor routing) |
| api/services/scan_service.py | 710 | Async scan + SSE streaming + concurrency guards |
| api/services/brief_service.py | 62 | Brief read + item selection |
| api/services/job_service.py | 48 | Job detail + save/skip to user_job_relationships |
| api/services/user_service.py | 27 | Profile + preferences read |
| api/deps/auth.py | 114 | Supabase JWT verification + user provisioning |
| api/deps/db.py | -- | Database dependency injection |

### Transport Layer
| File | Lines | Purpose |
|------|-------|---------|
| transport/base.py | 89 | TransportAdapter abstract class + UserEvent |
| transport/telegram.py | 185 | Telegram Bot API adapter |
| transport/webhook_server.py | 251 | Telegram webhook FastAPI server (:8000) |
| transport/terminal_chat.py | -- | CLI transport (stale, not integrated) |

### Onboarding Layer
| File | Lines | Purpose |
|------|-------|---------|
| onboarding/onboarding_flow.py | 471 | 7-step onboarding FSM |
| sources/identity_provider.py | -- | LinkedIn profile lookup via SerpAPI |
| llm_chat.py | -- | OnboardingAgent, CVExtractionAgent (LLM wrappers) |

### Memory/Repository Layer
| File | Lines | Purpose |
|------|-------|---------|
| memory/connection.py | 306 | DatabaseManager (ThreadedConnectionPool) + SQLite fallback |
| memory/checkpointer.py | 47 | LangGraph PostgresSaver/MemorySaver factory |
| memory/repository_v2.py | 300+ | Job/Brief/UserJob/Discovery/People repositories |

### Pipeline Layer
| File | Lines | Purpose |
|------|-------|---------|
| daily_runner.py | 432 | 9-step daily pipeline |
| india_fit_engine.py | -- | LLM-based job scoring |
| india_filter.py | -- | Geo + role family filters |
| application_ledger.py | -- | Filesystem-based JSON ledger (legacy) |
| company_intel.py | -- | Multi-source company research engine |
| package_assembly.py | -- | Application pack generation |
| outreach_engine.py | -- | LinkedIn people discovery |
| shortlist_formatter.py | -- | Daily brief markdown formatting |
| profile_manager.py | -- | YAML config reader |

### Frontend Layer
| File | Purpose |
|------|---------|
| App.tsx | Route definitions (6 protected + 1 public) |
| pages/LoginPage.tsx | Google OAuth via Supabase client |
| pages/OnboardingPage.tsx | Chat-based onboarding flow |
| pages/BriefPage.tsx | Daily brief TAL (swipe card UI) |
| pages/JobDetailPage.tsx | Job detail view |
| pages/ChatPage.tsx | Copilot chat + SSE scan integration |
| pages/ProfilePage.tsx | Profile view |
| lib/api.ts | ApiClient (all REST + SSE endpoints) |
| lib/auth.tsx | Auth context, ProtectedRoute, Google login |
| lib/ChatContext.tsx | Chat message state management |
| lib/supabase.ts | Supabase client initialization |
| lib/types.ts | TypeScript type definitions |

---

*Document generated by architectural reverse-engineering on 2026-05-29.*
*38 database tables analyzed. 40+ Python files traced. 7 workflows diagrammed. 7 state machines mapped.*
