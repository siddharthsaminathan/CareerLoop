# Dev Blog — 2026-05-24: Architecture Audit + Full Pipeline Stabilization

## What Was Done

- Ran a 7-subagent MECE architecture audit of the entire CareerLoop pipeline, covering state machine, persistence, discovery/geo, token economics, observability, intent routing, and ledger/brief lifecycle.
- Published the audit report at `docs/tech-backlog/ARCHITECTURE_AUDIT_2026-05-24.md` with 12 CRITICAL, 16 HIGH, and 17 MEDIUM findings, all with file paths and line numbers.
- Fixed all 22 items across 5 phases: emergency credential rotation, SQLite session persistence, geographic filter enforcement, token caps, structured logging, state rename (DAILY_BRIEF_SENT → PROFILE_COMPLETE), brief persistence, idempotency guard, and `/brief` command.
- Deduped the ledger from 1,268 entries (110 duplicates) to 1,216. Cleaned 1,103 non-India entries (90% pollution) from the ledger — they were scored and shortlisted by the pre-fix pipeline with no geo filter.
- Ran end-to-end pipeline test: 24 India jobs passed filter, 1,183 rejected. All 5 shortlisted jobs are in Chennai/Bangalore. Zero USA jobs.

## Key Decisions

- **Intent routing must never auto-fire pipelines.** Chat text "match me with jobs" now replies with a confirmation prompt instead of synchronously executing `DailyRunner.run()` (which was 156 API calls, 60-120s blocking the chat thread).
- **`DAILY_BRIEF_SENT` renamed to `PROFILE_COMPLETE`.** The old name was a lie — onboarding set it without generating any brief. Legacy state aliasing ensures old DB rows migrate automatically.
- **Geo filter is now applied at THREE choke points:** (1) DailyRunner pipeline entry, (2) `get_top_scored()` in ApplicationLedger, (3) shortlist builder in DailyRunner. A single filter is insufficient because scored jobs already in the ledger bypass the entry filter.
- **"remote" and "hybrid" no longer pass India filter without an India qualifier.** USA Remote, Remote (United States), and similar locations are now correctly rejected.
- **`score_batch()` hard-capped at 15 LLM calls.** Any caller passing more than 15 jobs gets a `ValueError`. Heuristic scoring capped at 50 per run in DailyRunner.

## Issues Encountered

- The idempotency guard replayed a pre-fix brief containing USA jobs, making the geo filter appear broken even though the code was correct. Clearing `.last_brief_date` and the old brief fixed this.
- Agents intermittently hit per-session token limits when dispatched via Agent tool, requiring manual follow-up on partially-applied changes.
- `chat_cli.py` had a sys.path ordering bug where `careerloop.logging_config` was imported before the `sys.path.insert(0, ..)` patch. Fixed by moving the path patch above the import.
- Ledger had two competing schemas (`fit_score` vs `fit_result`) from different runners. Unified in `_get_score()` static method.
- 1103 of 1216 ledger entries were non-India jobs — confirming the pre-fix pipeline had zero geographic filtering on the DailyRunner path.

## Files Changed

- `careerloop/session/states.py` — renamed DAILY_BRIEF_SENT → PROFILE_COMPLETE + legacy alias
- `careerloop/session/supervisor_graph.py` — removed unguarded scan, wired SHOW_PIPELINE, state rename
- `careerloop/session/session_store.py` — `_tbl()` SQLite/Postgres compat, profile completeness recovery
- `careerloop/session/message_router.py` — removed unguarded DailyRunner call
- `careerloop/onboarding/onboarding_flow.py` — save_session return checks, state rename
- `careerloop/memory/connection.py` — SQLite `users` + `sessions` tables
- `careerloop/application_ledger.py` — UUID IDs, `_get_score()` unified reader, follow-up fix, geo guard in get_top_scored()
- `careerloop/india_fit_llm.py` — token accounting, score_batch() hard cap
- `careerloop/india_fit_engine.py` — logged all silent except blocks
- `careerloop/daily_runner.py` — geo filter, role filter, scoring cap, brief persistence, idempotency, run_id logging, shortlist geo guard
- `careerloop/discovery.py` — location spoofing fix, CSV India filter
- `careerloop/on_demand.py` — LLM validator reordered after city filter + company cap
- `careerloop/chat_cli.py` — structured logging, `/brief` command, `/scan` wired to DailyRunner, sys.path fix
- `careerloop/logging_config.py` — NEW: JSONL structured logging module
- `careerloop/sources/ats_adapter.py` — remote/hybrid qualified with India check
- `careerloop/sources/ats_extended.py` — geo filter added to all adapter fallback paths
- `careerloop/ledger.json` — deduped + non-India entries cleaned
- `careerloop/models.py` — added RunMetrics dataclass
- `careerloop/scripts/migrate_sqlite_to_supabase.py` — removed hardcoded Supabase credentials
- `docs/tech-backlog/ARCHITECTURE_AUDIT_2026-05-24.md` — NEW: full audit report
- `docs/tech-backlog/TRACKER.md` — session log entry added

## Next Session

- Broaden target role filter or make it configurable — current narrow set (`AI Product Engineer`, `Applied AI Engineer`, `Founding Engineer (AI)`, `Senior AI Engineer`) matches only 3 of 24 India jobs.
- Wire the shared `JobFilterChain` class so all three pipelines (runner, daily_runner, on_demand) use identical filters.
- Add the token accounting wrapper (RunMetrics persister) to the council pipeline.
- Add company targeting data (company_memory JSON files) back into the fit engine so Indian employers get proper stability/brand scores instead of defaults.