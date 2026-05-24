# CareerLoop Architecture Audit — 2026-05-24

> **Methodology:** 7 parallel read-only subagents, each owning one MECE domain. No patches applied. All findings are structural.

---

## TL;DR — What Is Broken and Why

CareerLoop has **three completely separate execution pipelines** (`runner.py`, `daily_runner.py`, `on_demand.py`) with no shared filter chain, no shared persistence layer, and no shared state. This is the root of every bug the CLI logs exposed. Fixes to one pipeline silently don't apply to the others.

Additionally: the system has **three independent persistence stacks** (JSON flat file, SQLite, Supabase/Postgres) that are never reconciled and that each think they are canonical.

These two structural facts produce all observable failures.

---

## 1. Current Architecture (What Actually Exists)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Entry Points (3 separate, no shared code)                          │
│                                                                     │
│  chat_cli.py ──→ supervisor_graph.py ──→ intent_router              │
│                        │                    │                       │
│                        │         "SCAN_JOBS" intent                 │
│                        │              ↓ (synchronous, blocking)     │
│                        └──────→ DailyRunner.run()  ←── NO FILTERS  │
│                                                                     │
│  runner.py (direct CLI) ──→ CareerLoopRunner ──→ CORRECT PIPELINE  │
│                                                                     │
│  on_demand.py ──→ OnDemandSearch ──→ PARTIAL FILTERS               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  Persistence (3 stacks, never reconciled)                           │
│                                                                     │
│  ledger.json ──── 1,268 jobs, LIVE WORKING STORE                   │
│  careerloop.db ── 19 job rows, FROZEN (never written by pipeline)  │
│  Supabase/PG ──── Sessions, Users, LangGraph state (Prod only)     │
│                                                                     │
│  DailyRunner reads: ledger.json + YAML files                       │
│  LangGraph reads:   public.sessions (Postgres)                     │
│  These two code paths SHARE ZERO DATA                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. CRITICAL Failure Table

All items below block production use. Must fix before any user-facing deployment.

| ID | Domain | File | Line(s) | Description |
|----|--------|------|---------|-------------|
| C-01 | State | `session/session_store.py` | 33–75 | All SQL uses `public.sessions` (Postgres prefix). SQLite raises `OperationalError: no such table: public.sessions` on EVERY call. Exception handler returns `Session(state=IDLE)` silently. **Direct cause of the CV re-ask loop.** |
| C-02 | State | `onboarding/onboarding_flow.py` | 40, 47 | `save_session()` return value never checked. On DB failure, state reverts to `ONBOARDING_WAITING_CV` on next restart. CV asked again. |
| C-03 | State | `memory/checkpointer.py` | 13–15 | Raises `ValueError` if `DATABASE_URL` not set. `chat_cli.py` catches it and falls back to `checkpointer=None`. Zero cross-invocation conversation continuity in local mode. |
| C-04 | Intent | `session/supervisor_graph.py` | 141–161 | Any post-onboarding chat message classified as `SCAN_JOBS` synchronously fires `DailyRunner.run(do_scan=True)` — 156 HTTP calls + full scoring loop — with ZERO confirmation, ZERO cooldown, ZERO async. |
| C-05 | Intent | `session/supervisor_graph.py` | 150–151 | `sync_profile_data(profile_data)` overwrites `portals.yml` on disk before every scan trigger using potentially stale `temp_profile_data`. Silently corrupts portal config. |
| C-06 | Discovery | `daily_runner.py` | 204–127 | The entire DailyRunner path — the actual daily pipeline — has ZERO geographic filtering. Any URL in `data/pipeline.md` is scored and can reach the shortlist. Primary source of NYC/San Jose/USA Remote in results. |
| C-07 | Discovery | `discovery.py` | 496 | Search results use query city as `location` field. NYC job tagged by a "Bangalore" query carries `location="Bangalore"` and passes all downstream geo filters. |
| C-08 | Ledger | `onboarding/onboarding_flow.py` | 39, 44 | State transitions to `DAILY_BRIEF_SENT` at onboarding completion but `DailyRunner.run()` is never called. No brief is generated. The state name is a lie. |
| C-09 | Ledger | `daily_runner.py` | 158–181 | Brief is computed and returned as a string but never written to disk, DB, or session. "Show me today's brief" is architecturally impossible without a persistence layer. |
| C-10 | Discovery | `sources/ats_adapter.py` | 27–28 | `"remote"` and `"hybrid"` are bare keywords in the India ATS city filter with no India qualifier. `location="Remote (USA)"` and `location="Hybrid — New York"` both pass `_is_india_location()`. **Confirmed source of USA Remote entries in shortlist.** |
| C-11 | Persistence | `application_ledger.py` | 78 | `job_id = f"loop-{len(self.entries) + 1:04d}"` — non-atomic ID generation. Two concurrent loads produce identical IDs. **110 duplicate entries confirmed in `ledger.json`.** |
| C-12 | Persistence | `scripts/migrate_sqlite_to_supabase.py` | 22 | **SECURITY: Supabase `DATABASE_URL` with full credentials hardcoded as a default fallback string in a version-controlled file.** Rotate credentials immediately. |

---

## 3. HIGH Severity Failures

Must fix before multi-user use or any real data processing.

| ID | Domain | File | Line(s) | Description |
|----|--------|------|---------|-------------|
| H-01 | State | `session/supervisor_graph.py` | 146 | `temp_profile_data` is cleared to `None` on onboarding completion (`onboarding_flow.py:38`). The `DAILY_BRIEF_SENT` handler reads `state.get("temp_profile_data", {})` → always `{}`. `ChatIntentAgent` is permanently blind to CV, roles, and salary target after onboarding. |
| H-02 | State | `session/supervisor_graph.py` | 91 | `db = DatabaseManager(os.getenv("DATABASE_URL"))` inside `intent_router` — new DB connection created on every message, bypasses singleton, exhausts connection pool under load. |
| H-03 | Discovery | `discovery.py` | 232–239 | CSV imports bypass `filter_india_jobs()` entirely. Comment claims they are "manually curated India jobs" but there is no enforcement. |
| H-04 | Discovery | `sources/ats_extended.py` | 514–575 | `TalentRecruitAdapter`: no geo filter on any code path (API or XHR). |
| H-05 | Discovery | `sources/ats_extended.py` | 621–649 | `DarwinboxAdapter`: no geo filter on any code path. Darwinbox is used by many UAE/Middle East companies. |
| H-06 | Token | `on_demand.py` | 238 vs 244–276 | LLM batch validator runs on top-60 jobs BEFORE city filter and company cap. ~30% of validated jobs are discarded post-validation. Tokens wasted. Fix: move city filter + company cap before `_llm_validate`. |
| H-07 | Token | `on_demand.py` | 111–117 | Cache hit path bypasses the entire filter chain (recruiter, company type, role similarity, city) and also skips the LLM validator. Stale cached results with noise pass straight to output. |
| H-08 | Token | `india_fit_llm.py` | 230–241 | `score_batch()` has no internal cap. Any caller passing the raw 1,268-entry ledger triggers 1,268 LLM API calls. This is the mechanism for the "1182 scored" event. |
| H-09 | Observability | `india_fit_engine.py` | 80–108 | Both `_company_memory_lookup` and `_company_registry_lookup` swallow all exceptions with `except Exception: return {}`. DB connection failure is indistinguishable from "no company data." Scoring silently uses defaults for all companies. |
| H-10 | Observability | `session/supervisor_graph.py` | 96–102 | `intent_router` user insert wrapped in `except Exception: pass`. In SQLite mode this always throws and is always silently swallowed. |
| H-11 | Observability | `company_intel.py` | 497, 522, 574, 654 | Four `except Exception: pass` blocks in the S3 intelligence pipeline. Research failures are invisible. |
| H-12 | Ledger | `application_ledger.py` | 205–213 | `get_top_scored()` filters on `e.get("fit_score") is not None`. 140 entries have `fit_result` key only (written by the old runner). Those jobs are invisible to the shortlist engine. |
| H-13 | Ledger | `application_ledger.py` | 197 | `get_follow_ups_due()` date window `(midnight_today, now]` silently drops all follow-ups from prior days. Follow-ups from yesterday are never returned. |
| H-14 | Persistence | `daily_runner.py` | 87–99 | Double `is_duplicate` check with different key sets (URL+company+title vs URL-only) creates a logic hole that allows duplicates when URL is empty. Confirmed cause of 110 duplicate entries. |
| H-15 | Persistence | `memory/migrate_to_sqlite.py` | 20–33 | Fingerprint logic diverges from `models.py:_extract_domain()` (does not strip `job-boards.` prefix). Dedup across migration and pipeline is broken. |
| H-16 | Intent | `session/supervisor_graph.py` | 153–160 | `DailyRunner.run()` called synchronously inside LangGraph node. Blocks graph for 60–120 seconds. LangGraph state corruption possible if user sends another message during scan. |

---

## 4. MEDIUM Severity Failures

Should fix before stable v1.

| ID | Domain | File | Line(s) | Description |
|----|--------|------|---------|-------------|
| M-01 | State | `session/states.py` | 7–11 | `ONBOARDING_Q1–Q5` states defined but never set anywhere. Dead code. Onboarding stays at `ONBOARDING_WAITING_CV` for all turns. |
| M-02 | State | `session/supervisor_graph.py` | 66 | `messages: list[BaseMessage]` with no `add_messages` reducer. LangGraph replaces the list on each invocation. Conversation history is amnesiac between turns. |
| M-03 | State | `memory/` (all files) | — | `MemoryRepository`, `MemoryRetrievalService`, `EventTimelineModel`, `UserModel` are fully implemented but never called from any active code path. Full memory layer is dead code. |
| M-04 | State | `session/user_registry.py` | 11 | Hardcoded absolute path `/Users/siddharthsaminathan/projects/CareerLoop/...` with lowercase `/projects/`. Breaks on any other machine. |
| M-05 | Discovery | `sources/ats_extended.py` | 325–373 | Taleo JSON and DOM paths return jobs without geo filtering. |
| M-06 | Discovery | `sources/ats_extended.py` | 435–463 | iCIMS DOM Playwright fallback has no geo filter. |
| M-07 | Discovery | `sources/ats_extended.py` | 257–270 | SuccessFactors DOM fallback has no geo filter. |
| M-08 | Token | `runner.py` | 142–144 | No minimum heuristic score threshold before LLM candidacy. Top-15 taken by rank alone; a mediocre-job run sends 15 bad-fit jobs to the LLM. |
| M-09 | Token | None | — | Zero token counting anywhere. `response.usage.prompt_tokens` never read. No way to detect a repeat of the 1,182-job scoring event until it appears on an invoice. |
| M-10 | Observability | Multiple | — | Four competing `logging.basicConfig()` calls across entry points. Import order determines which format wins. Modules imported by another entry point get no handler. |
| M-11 | Observability | `metrics.py` | — | `MetricsEngine` reads from `event_timeline` table but nothing in the pipeline ever writes to it. It is a SQL shell with no data. |
| M-12 | Observability | `daily_runner.py` | All | Zero `logger.*` calls. 30 `print()` calls. Scheduling failures, scoring errors, and all pipeline boundaries are invisible in non-interactive runs. |
| M-13 | Ledger | `session/message_router.py` | 45–49 | Dead code `MessageRouter` contains the identical unguarded `DailyRunner.run()` coupling. If this class is ever imported (it isn't currently), the same blast radius reopens. |
| M-14 | Ledger | `session/supervisor_graph.py` | 149 | `SHOW_PIPELINE` intent is classified by `ChatIntentAgent` but no branch in the supervisor handles it. Users asking to see their pipeline silently get a chat reply and nothing happens. |
| M-15 | Ledger | `application_ledger.py` | 78 | Sequential ID `loop-{len+1}` means deleting any entry makes the next ID collide with an existing one. No uniqueness check before assignment. |
| M-16 | Persistence | `memory/connection.py` | 130–189 | Inline SQLite DDL diverges from `schema.sql`: `role_key` vs `role_name` as primary key column. Queries using the wrong column name silently fail. |
| M-17 | Persistence | `session/supervisor_graph.py` | 295 | `LangGraph state` and `SessionStore.public.sessions` written independently with no atomic guarantee. If `save_session()` fails after LangGraph checkpoint succeeds, the two stores diverge permanently. |

---

## 5. Architecture Diagrams

### 5a. Current State Machine

```
┌─────────┐    boot    ┌──────────────────────┐
│  IDLE   │ ─────────→ │ ONBOARDING_WAITING_CV │ ← Also entered on every
└─────────┘            └──────────────────────┘   restart when DB missing
                                │
                    LLM says is_complete=True
                       (save_session unchecked)
                                │
                                ↓
                     ┌──────────────────┐
                     │ DAILY_BRIEF_SENT │ ← PERMANENT steady state.
                     │  (no brief sent) │   ALL messages land here.
                     └──────────────────┘
                                │
                    ChatIntentAgent classifies
                                │
               ┌────────────────┼────────────────┐
               ↓                ↓                ↓
         SCAN_JOBS        SHOW_PIPELINE     GENERAL_CHAT
              │             (no handler)
              ↓
      DailyRunner.run()
      (synchronous, 60-120s)
              │
    (returns to DAILY_BRIEF_SENT)

    APPLIED / FOLLOWUP_DUE / INTERVIEW_* ← Defined in states.py, never set
```

### 5b. Target State Machine

```
IDLE ──→ ONBOARDING ──→ PROFILE_COMPLETE ──→ [normal flow]
                                                    │
                                            ┌───────┴──────────┐
                                            ↓                  ↓
                                    BRIEF_AVAILABLE      AWAITING_SCAN
                                            │             (with cooldown)
                                       user reads              │
                                            │         user says /scan
                                            ↓                  ↓
                                    REVIEWING_JOB      SCAN_RUNNING (async)
                                            │                  │
                                    approves job       BRIEF_AVAILABLE
                                            │
                                    PACK_GENERATING
                                            │
                                    PACK_READY
                                            │
                                   AWAITING_APPLY_CONFIRM
                                            │
                                        APPLIED
```

### 5c. Persistence Map (Current vs Target)

```
CURRENT (broken):
                    ┌─── ledger.json ─────────────────── DailyRunner
                    │         (1,268 jobs, LIVE)          OnDemandSearch
                    │
User data ──────────┼─── config/profile.yml ──────────── DailyRunner
                    │    profile_extended.yml              IndiaFitEngine
                    │
                    ├─── careerloop.db ──────────────── NOTHING (frozen)
                    │         (19 rows, dead)
                    │
                    └─── Supabase public.sessions ────── chat_cli
                              (prod only)                  supervisor_graph
                              (local = IDLE always)

The two execution paths (DailyRunner vs chat_cli) share ZERO data.

TARGET (correct):
                    ┌─── Supabase (canonical) ──────────┐
                    │    - public.sessions               │
                    │    - public.users (profile)        ├── ALL paths
                    │    - public.application_ledger     │
                    │    - public.daily_briefs (new)     │
                    │    - public.event_timeline         │
                    └────────────────────────────────────┘
                    
                    ledger.json: local cache only (write-through to Supabase)
                    profile.yml: read-only defaults (never canonical)
```

### 5d. Token-Cost Map

```
Pipeline           Filters before LLM     LLM calls    Cost/run
─────────          ──────────────────     ─────────    ────────
runner.py          India→verify→dedup     top 15 only  ~73,500 tok ✓ CORRECT
daily_runner.py    NONE                   NONE         0 tok but
                                                       1,182 CPU scores ✗
on_demand.py       India→role→dedup       batch-60     ~4,500 tok
                   then city filter       BEFORE city  ~30% wasted ✗

Correct target:
  All paths →  India→role→city→company cap→dedup  → heuristic  → LLM top 15
                                                    (all paths use same chain)
               0 tok   0 tok  0 tok   0 tok   0 tok   0 tok    ~73,500 tok
```

---

## 6. Root Cause Map — Observed Failures to Code Locations

| Observed Symptom | Root Cause | Fix Location |
|-----------------|------------|--------------|
| "Match me with jobs" triggers full pipeline | `supervisor_graph.py:141–161` — no confirmation gate, no intent disambiguation | Add explicit `/scan` command as only valid trigger; no auto-firing on chat |
| NYC / San Jose in shortlist | `daily_runner.py` — no geo filter; `ats_adapter.py:27–28` — "remote" passes India filter | Add `filter_india_jobs()` to DailyRunner; qualify "remote" with India check |
| CV asked again after onboarding | `session_store.py` — `public.sessions` fails on SQLite; `save_session()` return never checked | Add SQLite `sessions` table; check return value; add startup state verification |
| State says DAILY_BRIEF_SENT but no brief | `onboarding_flow.py:39` — state set without generating brief | Rename state to `PROFILE_COMPLETE`; generate and persist brief separately |
| "Show me today's brief" impossible | `daily_runner.py:158–181` — brief is print-to-stdout only | Create `DailyBrief` table; persist on generation; serve on demand |
| 1,182 jobs scored (potential LLM cost) | `india_fit_llm.py:230–241` — `score_batch()` has no internal cap | Add `MAX_BATCH=15` guard inside `score_batch()` |
| Scoring silently uses wrong company data | `india_fit_engine.py:80–108` — DB failures swallowed silently | Replace `except Exception: return {}` with logged fallback |
| 110 duplicate ledger entries | `application_ledger.py:78` — non-atomic `len+1` ID; double-dedup logic hole | Use `uuid4()` for IDs; single dedup call with all keys |
| Pipeline scores but `get_top_scored()` returns nothing | `application_ledger.py:205` — reads `fit_score` but old runner writes `fit_result` | Normalize all ledger entries to `fit_score` field; add migration script |
| Credentials in source code | `scripts/migrate_sqlite_to_supabase.py:22` | Remove immediately; require env var; rotate leaked credentials |

---

## 7. Prioritized Refactor Plan

### Phase 0 — Emergency (do before any further feature work)

**0-A: Rotate leaked Supabase credentials**
- File: `scripts/migrate_sqlite_to_supabase.py:22`
- Remove hardcoded `DATABASE_URL`. Change the password on the Supabase project.
- Time: 10 minutes.

**0-B: Add confirmation gate to scan**
- File: `session/supervisor_graph.py:141–161`
- Remove `DailyRunner.run()` from `intent_router`. Add explicit `/scan` slash command handler.
- `ChatIntentAgent` output of `SCAN_JOBS` should only reply "Ready to scan. Type `/scan` to begin."
- Time: 2–3 hours.

**0-C: Remove `portals.yml` mutation from chat path**
- File: `session/supervisor_graph.py:150–151`
- Delete the `sync_profile_data()` call from the intent router.
- Only call `sync_profile_data()` explicitly from `/scan` or onboarding completion.
- Time: 30 minutes.

---

### Phase 1 — Fix Persistence (1–2 days)

**1-A: Fix SQLite session persistence**
- Add `users` and `sessions` tables to `connection.py:_init_sqlite_schema()`
- Remove `public.` schema prefix from all SQL in `session_store.py` (use parameterized schema or strip prefix in the SQLite shim)
- Test: restart the chat CLI in local mode (no `DATABASE_URL`). Onboarding should persist across restarts.

**1-B: Check `save_session()` return value in onboarding**
- File: `onboarding/onboarding_flow.py:40,47`
- Add: `if not self.session_store.save_session(session): raise RuntimeError("State save failed")`
- Propagate the error to the user. Do not silently continue.

**1-C: Fix ledger entry schema split (`fit_score` vs `fit_result`)**
- Write a one-time migration script: for all `ledger.json` entries with `fit_result` but no `fit_score`, copy `fit_result["overall_score"]` to `fit_score`.
- Verify `get_top_scored()` now returns all entries.

**1-D: Fix non-atomic ID generation**
- Replace `len(self.entries) + 1` with `str(uuid.uuid4())[:8]` or a SQLite AUTOINCREMENT via the DB.
- Run dedup pass on existing `ledger.json` to collapse the 110 duplicates.

---

### Phase 2 — Fix Geographic Filtering (1 day)

**2-A: Add India filter to DailyRunner**
- File: `daily_runner.py`
- After `_parse_pipeline()`, call `filter_india_jobs(raw_jobs)` before adding to ledger.
- Add role family filter (string match against target roles from profile).

**2-B: Fix "remote"/"hybrid" India filter bypass**
- File: `sources/ats_adapter.py:27–28` and `sources/ats_extended.py:29–33`
- Replace `"remote"` → `"remote (india)"`, `"remote, india"`, `"india remote"` (qualified forms only)
- Or: check for India city name co-occurrence: `any(city in location.lower() for city in INDIA_CITIES) or ("india" in location.lower() and any(mode in location.lower() for mode in ["remote", "hybrid"]))`

**2-C: Add geo filters to TalentRecruit, Darwinbox, Taleo, iCIMS DOM, SuccessFactors DOM**
- Files: `sources/ats_extended.py` (multiple locations listed in audit)
- Apply `_is_india_location()` or `_is_india()` to each result before appending in those adapters.

**2-D: Fix location spoofing in search results**
- File: `discovery.py:496`
- Do not set `location = source_city` for jobs that don't have a real extracted location. Set `location = ""` and let the India filter reject them (empty location with no India evidence → rejected).

---

### Phase 3 — Unified Filter Chain (2–3 days)

**3-A: Extract a shared `JobFilterChain` class**
- All three pipelines (`runner.py`, `daily_runner.py`, `on_demand.py`) call the same chain:
  1. `filter_india_jobs()` — geo hard block
  2. `filter_role_family()` — role match hard block
  3. `filter_recruiter_agency()` — noise removal
  4. `filter_company_type()` — company category
  5. `filter_work_mode()` — work mode
  6. `deduplicate_canonical()` — fingerprint dedup
- Test: adding a new filter to `JobFilterChain` applies to all three pipelines automatically.

**3-B: Move `DailyRunner.run()` to background task**
- File: `session/supervisor_graph.py:153–160`
- Use `asyncio.create_task()` or a simple thread-based queue.
- Return immediately to the user with "Scan started. I'll message you when it's done."
- LangGraph node becomes non-blocking (<1s execution).

---

### Phase 4 — Brief Persistence + State Rename (1 day)

**4-A: Rename `DAILY_BRIEF_SENT` → `PROFILE_COMPLETE`**
- `session/states.py:13` + all references
- The name should reflect actual state (profile collected), not an action that didn't happen.

**4-B: Create `DailyBrief` persistence**
- Add `public.daily_briefs` table: `brief_id`, `user_id`, `generated_at`, `shortlist_text`, `job_ids`, `delivered_at`
- `DailyRunner.run()` writes to this table after generating the shortlist text.
- Add idempotency guard: `SELECT 1 FROM daily_briefs WHERE user_id=? AND generated_at::date = CURRENT_DATE` before running.

**4-C: Wire `SHOW_PIPELINE` intent**
- File: `session/supervisor_graph.py`
- Add branch: `elif intent == "SHOW_PIPELINE"` → query `daily_briefs` and `application_ledger` and return formatted summary.

---

### Phase 5 — Token Economics + Observability (2–3 days)

**5-A: Hard cap on `score_batch()` in `india_fit_llm.py`**
- Add `MAX_BATCH_SIZE = int(os.getenv("MAX_LLM_SCORE_JOBS", 15))`
- If `len(jobs) > MAX_BATCH_SIZE`, raise `ValueError` at call site.
- All callers must pre-filter before calling `score_batch()`.

**5-B: Add token accounting wrapper**
- Wrap every LLM call to read `response.usage.prompt_tokens` and `completion_tokens`.
- Write `event_timeline` row: `type="llm_call", metadata={model, prompt_tokens, completion_tokens, cost_usd, pipeline_stage}`.
- This makes `MetricsEngine.applications_per_week()` live.

**5-C: Add single structured logging config**
- Create `careerloop/logging_config.py` with JSON formatter + single `FileHandler`.
- All four entry points call `configure()` at startup instead of their own `basicConfig`.
- Replace `except Exception: pass` and `except Exception: return {}` blocks with logged fallbacks.

**5-D: Add `run_id` propagation**
- Generate `run_id = str(uuid.uuid4())` at the start of `DailyRunner.run()` and `DiscoveryEngine.discover_india_jobs()`.
- Pass to all sub-calls. Include in every log event and `event_timeline` row.

---

## 8. Critical Blockers Before Production

The following must be completed before this system processes real job applications for any user other than the developer.

| Blocker | Why It Blocks | Phase |
|---------|--------------|-------|
| Rotate leaked Supabase credentials | Anyone with repo access has DB write access right now | 0-A |
| Remove unguarded `DailyRunner.run()` from chat | Users will accidentally trigger costly scans conversationally | 0-B |
| Remove `portals.yml` mutation from chat path | Conversational messages silently corrupt the portal config | 0-C |
| Fix SQLite session persistence | Local dev/testing is impossible without this; state always resets | 1-A, 1-B |
| Fix `fit_score`/`fit_result` schema split | Current shortlist is wrong; ~140 jobs are invisible | 1-C |
| Add geo filter to DailyRunner | Non-India jobs are actively being shortlisted in the main pipeline | 2-A, 2-B |
| Fix "remote" keyword in India filter | USA Remote jobs pass the India filter by design right now | 2-B |
| Persist the daily brief | `DAILY_BRIEF_SENT` state is a lie; "show me today's brief" always fails | 4-B |
| Cap `score_batch()` | A single misrouted call scores 1,268 jobs with LLM; no protection exists | 5-A |

---

## 9. What Is Actually Working Well

Not everything is broken. These architectural decisions are correct and should be preserved:

- **`runner.py` pipeline funnel** — India filter → verify → dedup → heuristic → LLM top-15 is the correct architecture. Extend this, don't replace it.
- **`ApplicationLedger` atomic write** — `os.replace()` pattern is correct for single-writer flat file.
- **`IndiaFitEngine` 15-dimension heuristic** — CPU-only, well-structured, zero LLM cost. Right place for bulk scoring.
- **LangGraph `supervisor_graph.py` topology** — The graph structure (intent routing → pack generation → END) is the right skeleton. It just needs the routing logic cleaned up and the sync execution moved to background.
- **`OnboardingAgent` design** — Single LLM call accumulating fields until `is_complete` is an elegant pattern. The persistence layer around it is broken, not the agent itself.
- **`deduplicate_canonical()` fingerprinting** — SHA-256 fingerprint approach is solid. The ID generation bug is separate from the dedup logic.

---

*Audit performed 2026-05-24 by 7 parallel read-only subagents covering state machine, persistence, discovery/geo, token economics, observability, intent routing, and ledger/brief lifecycle.*
