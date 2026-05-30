# Dev Blog — 2026-05-29: Discovery Unification & P0 Bug Hunt

## Summary

The single most impactful day in CareerLoop's product history. 10 commits shipped across 4 phases: a 31-bug P0/P1 hunt that stabilized the entire runtime, two comprehensive architecture audits producing permanent design laws, the application pack revenue path wired end-to-end, and the discovery pipeline unified under a single canonical engine (OnDemandSearch) with 13 board sources, canonical location policy enforcement, and structured SSE payloads for the frontend. The product went from "works in the CLI" to "works via a real REST API consumed by a live web app."

## Commits

| Hash | Description |
|------|-------------|
| `e6e305f` | P0/P1 bug hunt — 31 fixed, 5-layer verified across 18 files |
| `9fdc2c1` | Fix: onboarding name-first flow, outreach engine, session recovery, server stability |
| `c64b804` | Fix: add GET /v1/chat/history endpoint + frontend auto-load on mount |
| `e84880a` | Feat: application pack pipeline + resume editing + observability logging |
| `d2dd198` | Feat: structured SSE scan event payloads for frontend consumption |
| `9b27679` | Feat: P0 fixes + discovery funnel observability + architecture audits |
| `056fd92` | Docs: real user journey validation — Scan>Brief>Inspect>Approve>Pack E2E report |
| `822440f` | Fix: enforce canonical location policy in scan_more path |
| `60fe41d` | Docs: RCA — non-India jobs + uniform 70.0 scores in scan_more path |
| `01c5ae8` | Feat: unify discovery pipeline — OnDemandSearch as canonical engine |

## What Was Shipped

### Phase 1: P0 Bug Hunt (Morning)
- 31 bugs fixed across 18 files including 6 P0 critical, 23 P1 high, 4 P2 UX
- Message persistence wired to careerloop.messages + careerloop.conversations
- Hard timeouts added to onboarding flow + supervisor graph (120s, preventing 330-minute hangs)
- PostgresSaver checkpointer wired into API path with MemorySaver fallback
- SessionStore unified -- no more duplicate connection pools per request
- Conversation history (last 20 messages from DB) injected into LLM context
- Onboarding name-first flow stabilized, outreach engine fixed, session recovery working
- GET /v1/chat/history endpoint added + frontend auto-load on mount

### Phase 2: Architecture Audits (Afternoon)
- Systems Architecture Audit (1,299 lines) -- MECE decomposition of all 8 systemic failures
- Data Lineage Audit (515 lines) -- end-to-end trace of data from discovery to user-facing output
- Target Architecture V2 document produced with 3 permanent architectural laws for layering, persistence, and routing
- Cross-layer E2E audit validated synthetic user "Hayagreev Sivakumar" across all 4 layers
- Absolute workspace boundary established for frontend-only engineering scope

### Phase 3: Revenue Path Fixes (Evening)
- Application pack pipeline wired end-to-end from job approval to PDF generation
- Resume editing with DeepSeek -- surgical single-section edits without full Council rerun
- Structured SSE scan event payloads designed for frontend consumption (typed event IDs, progress tracking)
- Daily brief infinite loading fixed -- offset pagination added to GET /v1/briefs/latest
- Non-India jobs RCA documented -- root cause identified in scan_more path bypassing geo filters
- JSONB-to-column profile fallbacks hardened for LLM general chat context injection
- P0 threading race condition, auth email overwrite, and chat timeout fixed (3 root-cause fixes)

### Phase 4: Discovery Unification (Late Night)
- OnDemandSearch established as the canonical discovery engine -- DailyRunner.run() and scan.mjs paths unified
- 13 board sources replacing 3 legacy ATS APIs (RemoteOK, Remotive, WeWorkRemotely, Cutshort, Wellfound, IIMJobs, Instahyre, plus existing 6)
- IndiaFitEngine + IndiaFitLLM wired into the unified pipeline for persistent India-first scoring
- All persistence paths unified under OnDemandSearch -- no more divergent scan_more path writing to different tables
- scan.mjs officially deprecated -- all new discovery goes through OnDemandSearch
- Canonical location policy enforced in scan_more path -- fixes non-India jobs and uniform 70.0 score bug
- Discovery funnel observability added -- per-source job counts, filter pass/fail rates

## Key Decisions

1. **OnDemandSearch is THE canonical engine.** DailyRunner.run() and scan.mjs paths are unified. No more divergent pipelines.
2. **SSE event payloads are now structured TypedDicts** with explicit event_id, event_type, and progress counters -- not just raw text lines. Frontend can render progress bars per source.
3. **Location policy enforced at the choke point** (scan_more path), not at the individual adapter level. One check, not 14.
4. **Resume editing uses DeepSeek directly** for surgical edits -- no full Council rerun needed for a tone or section change.
5. **PostgresSaver is the primary checkpointer** with MemorySaver as fallback. The old @contextmanager pattern is dead.

## Issues Encountered

- **non-India jobs leaked through scan_more** -- scan_more path bypassed the IndiaFitEngine location filter that scan_path used. Root cause: two code paths with one filter. Fix: unify under OnDemandSearch.
- **Uniform 70.0 scores** -- JobSpy returns 500-char snippets, not full JDs. Without full JD context, the scorer has no signal and everything clusters at 60-70. `_fetch_missing_jds()` fix enriches before scoring.
- **Checkpointer crash** -- @contextmanager + yield returned _GeneratorContextManager, not BaseCheckpointSaver. LangGraph rejected it with TypeError.
- **msgpack serialization crash** -- SessionStore in graph state dict isn't serializable. Fixed by using shared DB singleton instead.
- **SSE event dedup needed** -- same-timestamp events from parallel board workers needed watermark + event ID double dedup.

## Files Changed (summary)

| Area | Files | Changes |
|------|-------|---------|
| API (careerloop_api/) | 15 | Fixed onboarding flow, added chat history, SSE payloads, pagination |
| Discovery pipeline | 20+ | OnDemandSearch unification, 13 board adapters, location policy enforcement |
| Session/orchestration | 8 | Checkpointer rewrite, SessionStore unification, message persistence |
| Frontend (src/) | 5 | Auth redirect, auto-load, retry guards, spinner timeout |
| Documentation | 7 | Architecture audits, RCA docs, E2E reports, workspace boundary |

## Next Session

- Deploy frontend to Netlify for real user testing
- Wire structured job payloads into BriefPage cards
- PostgresSaver checkpointer hardening (interrupt/resume proof)
- Application pack pipeline end-to-end validation
- Resume Council v3 wiring into chat
