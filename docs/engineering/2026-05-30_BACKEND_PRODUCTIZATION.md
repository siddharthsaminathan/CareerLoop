# Backend Productization Journal — 2026-05-30

**Author:** Engineering Lead (Agent D)
**Session:** 4-agent stabilization + engineering lead sync

---

## 1. What Was Fixed Today

Based on git log and file state:

### Agent Deliverables (from commits)

| Agent | Commit | What |
|-------|--------|------|
| A (Product Lead) | `3027e5c` | Product lead review + dev blog + tracker update (late night session) |
| B (Data Quality) | `fd8b27d` | Empty company/location inference from URL/title. Cutshort parsing safety net. Brief item data quality hardening. |
| C (Code Review) | `07caa97` | Critical fixes: `_funnel_uid` NameError in scan_service.py, CHECK constraint on background_runs, SQLite `%s` placeholders for local dev. |
| — (Rules/Docs) | `a2a0e6a` | Updated locked rules for E2E workspace boundary. Compiled 2026-05-30 engineering journal. |
| B+C+Final | `bcfac36` | State consistency: filter saved/skipped jobs from briefs. Complete agent B, C, and final validation. |

### This session (Agent D — Engineering Lead)

- All canonical docs synced to actual system state (CLAUDE.md, AGENTS.md, GEMINI.md, CANONICAL_ARCHITECTURE.md, PRD.md, TECH_ROADMAP.md, TRACKER.md)
- API_ARCHITECTURE.md discrepancy banner added (target spec vs live reality)
- This journal written
- 13 files updated/created

---

## 2. What Remains (Deferred to Next Session)

| Item | Priority | Owner |
|------|----------|-------|
| API deployment to Fly.io (Dockerfile, fly.toml, GitHub Actions) | P0 | CTO |
| PostgresSaver interrupt/resume proof (currently 65%) | P1 | CTO |
| Company logo backfill (Clearbit enrichment job) | P2 | Data |
| Salary/description enrichment from scrapers | P2 | Data |
| Multi-worker readiness (Redis session cache, PostgresSaver hardening) | P1 | CTO |
| Scan thread lifecycle management (timeout → kill) | P1 | CTO |
| Build packs endpoint (POST /v1/jobs/{job_id}/packs) | P1 | CTO |
| API_ARCHITECTURE.md → as-built reference (currently target spec) | P2 | Docs |

---

## 3. Current System Architecture

### careerloop_api/ — REST API v1 (95% complete)

All files with one-line descriptions:

| File | Description |
|------|-------------|
| `main.py` | FastAPI entry point. Mounts 7 routers under /v1. CORS middleware. Error handlers. |
| `core/config.py` | DB_SCHEMA, DATABASE_URL, CORS_ORIGINS, DeepSeek config |
| `core/security.py` | Supabase JWT HS256 verification |
| `core/envelope.py` | Standardized `{ok, data, error, meta}` response shape |
| `deps/auth.py` | get_current_user: JWT verify + auto-provision careerloop.users (300s TTL cache) |
| `deps/db.py` | get_db: psycopg2 ThreadedConnectionPool injection |
| `routers/auth.py` | POST /v1/auth/me — provision + return profile |
| `routers/users.py` | GET /v1/me, GET /v1/me/preferences |
| `routers/briefs.py` | GET /v1/briefs/latest, POST /v1/briefs/{id}/items/{idx}/select |
| `routers/jobs.py` | GET /v1/jobs/{id}, POST save, POST skip |
| `routers/chat.py` | POST /v1/chat/message, GET /v1/chat/history |
| `routers/scans.py` | POST /v1/scans, GET /v1/scans/{run_id}/events (SSE), GET /v1/scans/{run_id}, GET /v1/scans/latest |
| `routers/debug.py` | GET /v1/debug/runtime — memory, threads, pool counts, scan state |
| `services/chat_service.py` | Wraps LangGraph supervisor graph (PROFILE_READY+) and OnboardingFlow (NEW_USER). Conversation persistence. 120s timeout per turn. |
| `services/scan_service.py` | Scan lifecycle: initiate (409 guard, 3-worker semaphore), background thread worker, SSE event streaming (1s poll, watermark dedup, 5min timeout), stale scan recovery. scan_more mode via OnDemandSearch. |
| `services/brief_service.py` | Brief reads + item selection with session persistence |
| `services/job_service.py` | Job detail + save/skip with user_job_relationships upsert |
| `services/user_service.py` | Profile + preferences from careerloop.users |
| `services/serializers.py` | TAL-style job card serialization. 3-tier logo fallback (explicit -> Clearbit -> initials avatar). fit_tier colors (strong/good/weak). Description snippets. |
| `repositories/users_repo.py` | careerloop.users CRUD |
| `repositories/briefs_repo.py` | daily_briefs + daily_brief_items queries |
| `repositories/jobs_repo.py` | careerloop.jobs + user_job_relationships |
| `e2e_api_test.py` | 15/15 API E2E tests (no pytest — real Supabase + DeepSeek) |
| `e2e_onboarding_test.py` | 7/7 onboarding E2E tests |

### Key careerloop/ Files Used by the API

| File | API Usage |
|------|-----------|
| `careerloop/session/session_store.py` | chat_service.py, brief_service.py — session/state management |
| `careerloop/session/states.py` | UserJourneyState enum (NEW_USER, PROFILE_READY, etc.) |
| `careerloop/session/supervisor_graph.py` | chat_service.py — LangGraph parent graph invocation |
| `careerloop/onboarding/onboarding_flow.py` | chat_service.py — NEW_USER message handling |
| `careerloop/memory/connection.py` | scan_service.py — DatabaseManager singleton for workers |
| `careerloop/memory/checkpointer.py` | chat_service.py — PostgresSaver / MemorySaver |
| `careerloop/memory/repository_v2.py` | scan_service.py — get_fresh_cached_jobs for cache path |
| `careerloop/on_demand.py` | scan_service.py — OnDemandSearch.run() canonical discovery engine |
| `careerloop/india_fit_engine.py` | scan_service.py — IndiaFitEngine scoring |
| `careerloop/india_fit_llm.py` | scan_service.py — LLMIndiaFitEngine deep scoring |
| `careerloop/models.py` | scan_service.py — JobPosting dataclass |
| `careerloop/policies/` | scan_service.py — is_india_location |
| `careerloop/profile_manager.py` | scan_service.py — fallback profile loading |

---

## 4. Next Priorities

Ranked by impact:

1. **Deploy to Fly.io** — Dockerfile + fly.toml + GitHub Actions. This is the P0 blocker for real user delivery. The API is E2E verified against live Supabase but only runs locally.

2. **PostgresSaver interrupt/resume proof** — Currently 65%. Checkpoint tables exist and reads work, but the resume-after-interrupt path is untested. Blocks multi-worker deployment (5+ concurrent users will hit the single-worker limit).

3. **Build packs endpoint** — POST /v1/jobs/{job_id}/packs is the largest gap between the API spec and reality. PackageAssembler + Playwright PDF pipeline exists, just needs a REST wrapper.

4. **Scan thread lifecycle management** — Currently no timeout-kill for stuck scan threads. The 5-min SSE timeout prevents client hangs, but the thread itself can run indefinitely.

5. **Company logo backfill** — All companies have NULL logo_url. The serializers handle this gracefully (initials avatar fallback), but real logos would improve UX significantly.

6. **API_ARCHITECTURE.md reconciliation** — Convert from target-spec to as-built reference. 36 spec endpoints defined vs 9 live. Schemas/, workers/, events/ directories in spec don't exist yet.

---

## 5. Known Issues (Do NOT Fix This Session)

| Issue | Severity | Why Deferred |
|-------|----------|-------------|
| PostgresSaver checkpointer leak: `get_checkpointer()` creates a new Pool on every chat turn (4 connections each) | P1 | Needs architectural fix (singleton pattern). Will cause connection exhaustion at ~4 concurrent users. Observed via /debug/runtime. |
| Brief select_item silently swallows session persistence failures | P2 | Causes "approve disappears on refresh" on the frontend. Non-fatal — the API succeeds but session state is lost. |
| SSE route is sync def — StreamingResponse iterates in thread pool, not event loop | P2 | Works correctly in practice (uvicorn's thread pool handles it). Could be blocking at high concurrency. |
| API_ARCHITECTURE.md lists 36 endpoints; only 9 route patterns are live | P2 | Spec is target-state, intentionally ahead of implementation. Documented with banner. |
| Polite closings misclassified as HELP in chat (2/7 E2E turns) | P2 | 1-line ActionResolver prompt fix pending. |
| companies.logo_url, domain, website NULL for all current companies | P2 | Handled gracefully by serializers (initials avatar). Needs Clearbit backfill. |
| salary_min/max and jd_text empty for scraped jobs | P2 | Handled gracefully by serializers. Needs scraper enrichment. |
| Career State Graph references `public.*` schema in data engineering rules (GEMINI.md line 189-199) | P3 | Legacy docs — schema is now `careerloop.*`. Not critical. |

---

## 6. Architecture Snapshot

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React/TS)                       │
│  ┌──────────────┐ ┌──────────────────┐ ┌─────────────────────┐  │
│  │ Supabase OAuth│ │ TAL Job Cards    │ │ SSE EventSource     │  │
│  └──────┬───────┘ └────────┬─────────┘ └──────────┬──────────┘  │
└─────────┼──────────────────┼──────────────────────┼─────────────┘
          │                  │                      │
          ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    REST API (careerloop_api/)                     │
│  FastAPI :8001 — 7 routers — {ok, data, error} envelope         │
│                                                                  │
│  auth ──► users ──► briefs ──► jobs ──► chat ──► scans ──► debug│
└───────────────────────────┬─────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                  ▼
┌──────────────────┐ ┌─────────────┐ ┌──────────────────┐
│  Chat Service     │ │Scan Service  │ │ Brief/Job/User   │
│  Supervisor Graph  │ │Background    │ │ Services         │
│  OnboardingFlow   │ │Worker Thread │ │ + Repositories   │
└────────┬─────────┘ └──────┬──────┘ └────────┬─────────┘
         │                  │                  │
         ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│              careerloop/ (Business Logic Layer)                   │
│  session/  onboarding/  on_demand.py  council/  memory/          │
│  sources/  india_fit_engine.py  india_fit_llm.py                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Supabase PostgreSQL (careerloop.*)                   │
│  users  jobs  user_job_relationships  daily_briefs               │
│  daily_brief_items  background_runs  run_events                  │
│  sessions  conversations  messages  company_memory               │
└─────────────────────────────────────────────────────────────────┘
```

---

*Journal compiled 2026-05-30 by Agent D (Engineering Lead). Based on full file audit of careerloop_api/ and careerloop/.*
