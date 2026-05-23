# CareerLoop Handoff: CLI Stabilization & Ledger Safety
**Date:** 2026-05-23
**Author:** AI Product Engineering Lead

### 1. Objective / Overview
The goal of this session was to transform the CLI from an unstable, crashing prototype into a hardened, persistent transport mechanism. The Pydantic boot loop has been eliminated, session-auth persistence implemented, and the crucial JSON data store has been vaccinated against mid-save corruption.

### 2. Architecture Decisions & Changes
- **Data Contract over Type Strictness:** Removed the rigid LangChain `@tool` decorator from `sync_profile_data`. The Pydantic wrapper was preventing LangGraph from successfully booting the state graph in the CLI. By treating it as a vanilla Python function inside the graph execution, we avoid Pydantic schema validation failures entirely.
- **OS-Level Atomic Saves:** `_save()` in `ApplicationLedger` now uses a `.tmp` file and `os.replace()`. This provides OS-guaranteed atomic file replacement. Mid-save `SIGKILL`s (like `Ctrl+C`) can no longer leave `ledger.json` truncated and unparseable.
- **Local Credential Cache:** Implemented `~/.careerloop_session` caching in `authenticate_cli_user`. The mock CLI no longer interrogates the user for an email on every single process start.

### 3. PRD & Vision Alignment
✅ **ALIGNED.** Stabilizing the user interface and preventing data-loss in the local backend directly supports PRD §21-23 (Delivery Foundation). The underlying AI engines cannot deliver value if the CLI transport layer crashes constantly.

### 4. Code & Files Modified
- `careerloop/chat_cli.py` (Local `.careerloop_session` logic)
- `careerloop/application_ledger.py` (Atomic `_save` implementation)
- `careerloop/tools/sync_profile.py` (De-decorated from `@tool`)
- `careerloop/session/supervisor_graph.py` (Direct invocation of profile sync)

### 5. Data & State Management
- `careerloop/ledger.json` was repaired via a standalone script to manually close the truncated arrays/dictionaries.
- The state graph successfully deserializes `UserState.DAILY_BRIEF_SENT` from the LangGraph PostgreSQL checkpointer on reboot.

### 6. Transport & Interface Status
The Terminal CLI is now functional and persistent. 
- Multi-line pasting drops correctly.
- Email auth is automated on consecutive boots.
- State resumes perfectly at `DAILY_BRIEF_SENT`.

### 7. Current Blockers (Resolved vs Open)
- **Resolved:** `B-TRANSPORT` (CLI crashing on boot).
- **Resolved:** JSON parse exception blocking `DailyRunner`.
- **Open:** The `DailyRunner` step 4 (India Fit Engine Scoring) either hangs or takes extremely long. The `scan.mjs` deduplication reports `1151 duplicates skipped`, which may indicate bad scanner payload matching.

### 8. Testing & Validation
- Executed `uv run python -m careerloop.chat_cli`.
- Booted successfully, auto-logged in, bypassed Pydantic schema crash.
- Sent `scan for jobs` successfully, routing directly to `DailyRunner`.

### 9. Edge Cases Addressed
- **Abrupt Termination (`SIGKILL` / `Ctrl+C`):** Handled for the ledger writing process. The `DailyRunner` handles over 1000 jobs, making it highly susceptible to user interruption during processing. Atomic saves ensure safety here.

### 10. Required Follow-Ups
- Investigate `scan.mjs` output format vs `ApplicationLedger.is_duplicate()` logic. The terminal log showed 1151 jobs were duplicated and skipped. Is the scanner failing to extract the unique URLs?
- Investigate `IndiaFitEngine` performance. Why did it hang/take so long on Step 4?

### 11. Known Risks
- The `DailyRunner` is currently synchronously blocking the chat loop. Processing 1000+ jobs via LLM scoring will lock up the user's terminal. It must eventually be backgrounded or streamed.
- LangGraph checkpointer emits a JSONPlus deserialization warning for `UserState` enums. It is currently a warning but will become a fatal error in future `langgraph` versions.

### 12. Context for Next Agent
The CLI is functional and stable. The next critical domain is the **Discovery / India Fit Engine Evaluation Phase**. The CEO has heavily optimized the Phase 1 scripts, but we need to verify why the scanner returned 1151 duplicates and how the India Fit Engine is orchestrating those jobs. Do not touch the CLI unless explicitly asked. Your domain is now the pipeline integration between discovery (scrapers) and evaluation (LLM council).
