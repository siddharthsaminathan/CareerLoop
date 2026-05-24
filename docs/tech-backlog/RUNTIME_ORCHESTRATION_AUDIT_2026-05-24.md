# CareerLoop Runtime Orchestration Audit — 2026-05-24

> **Brutally honest.** No sugarcoating. The THREE_LAYER_STATE_ARCHITECTURE.md is aspirational fiction.

---

## Executive Summary

The previous engineer shipped a **partial V2 migration** that looks real at a glance but collapses under scrutiny. The `states.py` rename (`UserState` → `UserJourneyState`) and DB table creation (`background_runs`, `run_events`, `daily_briefs`, `daily_brief_items`) are real. But **8 of 17 tool handlers return hardcoded strings**, the tests import a dead enum, the "verified E2E" transcript in THREE_LAYER_STATE_ARCHITECTURE.md references test results that don't match reality, and the architecture document claims completion of work that was never done.

**The system is in a halfway state — more honest than before (DB tables exist, some tools are real) but still polluted with fake runtime behavior.**

---

## A. Remaining Fake Runtime Behavior

### Fake Data / Hardcoded Artifacts

| # | File | Line(s) | Fake Artifact | Severity |
|---|------|---------|---------------|----------|
| A1 | `tool_registry.py` | 55-59 | `general_chat()` returns `"I'm here to help. Try asking for your 'daily brief' or 'pipeline' to get started."` — hardcoded, no LLM | **P0** |
| A2 | `tool_registry.py` | 61-65 | `show_help()` returns hardcoded command list string | **P1** |
| A3 | `tool_registry.py` | 80-84 | `show_profile()` returns `"Profile context is active. Let's review your details."` — no actual profile data lookup | **P0** |
| A4 | `tool_registry.py` | 74-78 | `show_status()` returns bare `f"Current State: {state.value}\nActive Context: {context}"` — dumps raw dict to user | **P1** |
| A5 | `tool_registry.py` | 378-392 | `show_company_intel()` returns `"They are currently well-funded, scaling their engineering footprint in India..."` — COMPLETELY FAKE, no DB query, same text for every company | **P0** |
| A6 | `tool_registry.py` | 394-395 | `show_people_to_reach()` returns `"Suggested Recruiter outreach plays: Warm intro to the Talent Acquisition lead..."` — hardcoded, no role/company awareness | **P1** |
| A7 | `tool_registry.py` | 397-420 | `prepare_application_pack()` returns a `pack_id` string but NEVER invokes the Resume Council graph. The pack is an ID with no content. | **P0** |
| A8 | `tool_registry.py` | 312-344 | `review_job()` tries to instantiate `ApplicationLedger` with `self.session_store.db_manager._sqlite_path` — accessing a private attribute. The `_load_profile_data` call on line 317 is nonsensical (passes user_id but iterates with `if False`). | **P0** |
| A9 | `tool_registry.py` | 422-424 | `edit_application_pack()` returns `f"Editing outreach assets with instruction: '{instruction}'"` — no actual editing occurs | **P1** |

### Hardcoded Static Text (Not Fake Runtime Data, But Still Slop)

These return `ResponseEnvelope(response_type="text", text=...)` with static user-facing text. The THREE_LAYER doc says "Tools return data, not strings. The LLM synthesizes the final response." None of these follow that rule.

| # | File | Lines | Handler | What it should do instead |
|---|------|-------|---------|--------------------------|
| A10 | `tool_registry.py` | 55-59 | `general_chat` | Delegate to LLM with full conversation context |
| A11 | `tool_registry.py` | 61-65 | `show_help` | Return structured help data; let LLM format response |
| A12 | `tool_registry.py` | 67-72 | `reset_session` | Works, but text is hardcoded |
| A13 | `tool_registry.py` | 80-84 | `show_profile` | Query DB for actual profile; return data, not text |

### Fake Artifact Grep Results

```
Stripe:      tests.py only (test company name — acceptable)
Vercel:      ZERO matches in production code ✅
pack_456:    ZERO matches — replaced by pack_{uuid} ✅  
latest_brief_123: ZERO matches ✅
"would kick off": ZERO matches ✅
"simulated":  ZERO matches except supervised_graph.py:436 `"simulated scan language"` in old scan_jobs_tool comment
"mock":       ZERO matches in production code ✅
"placeholder": ZERO matches ✅
"TODO"/"FIXME"/"HACK": ZERO matches ✅
```

**Verdict:** The specific fake artifacts listed in the prompt (Stripe, Vercel, pack_456, latest_brief_123) are gone. But 9 tool handlers still produce hardcoded slop — different flavor of fake, same problem.

---

## B. Runtime Flow Gaps

### B1: Conversation Continuity — BROKEN

The `add_messages` reducer exists in `supervisor_graph.py:22` with `Annotated[list[BaseMessage], add_messages]`. Each return dict appends `AIMessage(content=reply)`. But the `action_resolver.py` LLM prompt at line 97-100 sends ONLY the current state + artifact context + user message:

```python
prompt = f"""Current State: {state.value}
Active Artifact Context: {json.dumps(artifact_context)}
User Message: {user_message}
"""
```

**No conversation history is injected.** The `messages` parameter of `resolve()` is typed `Optional[List[BaseMessage]]` but the prompt doesn't use it. Every turn is contextually blind.

**Where:** `action_resolver.py:97-100`

### B2: Context Loss — User Journey Stage 1 Degradation

The V2 `UserJourneyState` has only 4 states (NEW_USER, PROFILE_READY, APPLICATION_PENDING, INTERVIEW_ACTIVE). All V1 states (17 of them) collapse into these 4. But the legacy map at `states.py:46-55` maps 11 distinct V1 job/lifecycle states to a single `PROFILE_READY` — including `REVIEWING_JOB`, `PACK_GENERATING`, `PACK_READY`, `RESEARCHING_COMPANY`.

**A user reviewing job #5 who restarts will resume as PROFILE_READY with ZERO context about which job they were reviewing.** The Active Context layer (active_job_id, active_brief_id) should carry this, but it's not hydrated from the DB on restart.

**Where:** `states.py:44-55`, `session_store.py:140-150`

### B3: Intent Degradation — "daily briefing" → Robotic Static Text

When the LLM classifies "daily briefing" as SHOW_BRIEF, `tool_registry.show_brief()` runs a real DB query and returns a hardcoded-format string. The THREE_LAYER doc says "Tools return data, not strings. The LLM synthesizes the final response." This is never implemented — tools return `ResponseEnvelope(text=hardcoded_string)` directly to the user.

**Where:** `tool_registry.py:252-263` (show_brief), `tool_registry.py:265-310` (select_brief_item)

### B4: artifact_context Incomplete

The `ResponseEnvelope.artifact_context_updates` dict is returned by tools, but no code writes these updates to the session/DB. The `action_resolver.py:86-94` reads `artifact_context.get("active_artifact_type")` from the context dict, but this dict is passed in from the supervisor — if the supervisor doesn't merge `artifact_context_updates` back into the session, the context evaporates on the next turn.

**Where:** `tool_registry.py` (multiple return points with `artifact_context_updates`), no corresponding update logic in `supervisor_graph.py`

### B5: add_messages Reducer Present But Unused by ActionResolver

The `ConversationState` has `add_messages` reducer. But the `action_resolver` doesn't send `messages` to the LLM (see B1). The history is stored but never injected into the LLM prompt. It's persisted for free but useless.

**Where:** `supervisor_graph.py:22`, `action_resolver.py:97-100`

---

## C. Persistence Gaps

### C1: Filesystem Dependencies — Partially Cleared

| Dependency | Status | Should Be |
|-----------|--------|-----------|
| `output/daily_briefs/{date}.md` | Still used by CommandRouter.brief() | DB `daily_briefs` table |
| `.last_brief_date` sentinel file | Still used by DailyRunner | `background_runs` table |
| `ledger.json` (1,216 entries) | Primary job store | Move to `application_ledger` DB table |
| `careerloop.db` (SQLite) | Secondary store, 519 companies | Merge with Supabase or stay SQLite in local mode |

**Where:** `command_router.py:17-20` (reads brief from filesystem), `daily_runner.py` (writes .last_brief_date), `application_ledger.py` (flat JSON file)

### C2: DB Tables Exist But Are Underutilized

The SQLite DB has `daily_briefs`, `daily_brief_items`, `background_runs`, `run_events` tables. `tool_registry.start_scan()` writes to them correctly. But:

- `show_brief()` queries them — correct ✅
- `select_brief_item()` queries them — correct ✅
- `show_company_intel()` ignores `company_memory` table — broken ❌
- `review_job()` uses `ApplicationLedger` (JSON file) not DB — broken ❌
- `show_pipeline()` uses `ApplicationLedger` (JSON file) — partially correct ⚠️

**Where:** `tool_registry.py` — mixed DB vs filesystem access

### C3: Session Persistence — Still Has Side-Effect Migration

`session_store.py` performs state migration (legacy → V2) inside `get_session()`, which is a read operation. The THREE_LAYER doc explicitly calls this out as a violation. The migration should happen once, explicitly, not on every read.

**Where:** `session_store.py:106-158`, `THREE_LAYER_STATE_ARCHITECTURE.md:161-162`

### C4: Active Context Not Persisted

The `active_artifact_type`, `active_artifact_id`, `active_job_id` fields are returned by `tool_registry` via `artifact_context_updates` but never written to the sessions table. They exist only in the in-memory graph state. On restart, all active context is gone.

**Where:** `session_store.py` — no `update_context()` method, no context columns in sessions table

---

## D. Action Architecture Gaps

### D1: Old Intent Classification Still Leaks Through

`action_resolver.py:67-83` — Hardcoded if/elif chain for slash commands (`/brief`, `/scan`, `/pipeline`, `/status`, `/profile`, `/reset`, `/help`). This is the EXACT pattern the THREE_LAYER doc says must die.

`action_resolver.py:86-94` — `if msg_lower.isdigit()` — bypasses LLM entirely. The THREE_LAYER doc says this is a "MUST DIE" violation.

`action_resolver.py:96-118` — LLM-based resolution exists but is the FALLBACK, not the primary path.

**Verdict:** The ActionResolver is a hybrid — hardcoded routing first, LLM as fallback. The THREE_LAYER doc says it should be LLM-first with tool-calling.

### D2: ActionResolver Is Brittle

The system prompt (lines 12-62) lists 17 ActionTypes and maps specific English phrases to actions. This is the same brittle intent classification the architecture explicitly rejects. If the user says "show me the first one" instead of "1", the hardcoded `isdigit()` check fails, and the LLM might or might not map this to SELECT_BRIEF_ITEM.

### D3: Tool Execution Is Tightly Coupled

`tool_registry.py` instantiates `DailyRunner` (line 113), `ApplicationLedger` (lines 320, 353, 372, 386, 434, 451) directly — no dependency injection, no interface. Each tool handler has its own error handling, its own DB access pattern, its own ID generation. No shared `ToolContext` or `ExecutionContext`.

### D4: Routing Is Duplicated

| Router | Where | What it routes |
|--------|-------|----------------|
| `action_resolver.py:67-83` | Hardcoded if/elif | Slash commands → ActionType |
| `action_resolver.py:86-94` | Hardcoded isdigit | Number → SELECT_BRIEF_ITEM |
| `action_resolver.py:96-118` | LLM classification | Natural language → ActionType |
| `supervisor_graph.py:intent_router` | State-based if/elif | UserJourneyState → handler |
| `command_router.py` | Method dispatch | Slash command → handler |
| `message_router.py` | State-based if/elif | UserJourneyState → handler (DUPLICATE of supervisor_graph) |

**SIX routing layers. Three of them handle slash commands.**

---

## E. TAL UX Parity Gaps

| TAL Capability | Current State | Gap |
|---------------|---------------|-----|
| **Live scanning feedback** | `start_scan()` calls `DailyRunner.run()` synchronously. User waits 60-120s with no feedback. `run_events` table exists but nothing streams to UI. | No async execution. No event streaming to terminal. No progress indicators. |
| **Fluid job selection** | `select_brief_item()` works via number input only. `isdigit()` check blocks natural selection. | "show me the Stripe one" fails. "the second job" fails. Only "2" works. |
| **Contextual followups** | active_job_id set on select_brief_item but not persisted. On next turn, context is lost if graph state not merged. | "why this job" fails if asked after any other message. |
| **Conversational continuity** | `add_messages` reducer works but ActionResolver prompt doesn't include history. | LLM never sees what it said 2 turns ago. |
| **Progressive disclosure** | `show_brief()` dumps all items at once. No "show more" or pagination. | 50-item brief is a wall of text. |
| **Momentum-oriented UX** | None. Scan completes, brief shows, user picks a number. No encouragement, no "you applied to 3 jobs this week", no streak tracking. | Zero momentum UX. |

---

## F. Technical Debt Map

### P0 Blockers — Cannot Ship Without

| # | What | Where | Why |
|---|------|-------|-----|
| P0-1 | `general_chat()` returns hardcoded string not LLM | `tool_registry.py:55-59` | Every unrecognized input gets the same dead response |
| P0-2 | `show_company_intel()` returns identical fake text for all companies | `tool_registry.py:378-392` | Actively misleading — users will trust fake intel |
| P0-3 | `prepare_application_pack()` doesn't invoke council graph | `tool_registry.py:397-420` | Pack ID generated with no content — broken feature |
| P0-4 | `show_profile()` returns dummy text, no DB lookup | `tool_registry.py:80-84` | Profile command is non-functional |
| P0-5 | `review_job()` uses broken private attribute access | `tool_registry.py:312-344` | Will crash at runtime |
| P0-6 | ActionResolver doesn't inject conversation history into LLM | `action_resolver.py:97-100` | Every turn is contextually amnesiac |
| P0-7 | artifact_context_updates not persisted to session | `tool_registry.py` + `supervisor_graph.py` | Context evaporates on next turn |
| P0-8 | `tests_router.py` imports dead `UserState` enum | `tests_router.py:6` | Tests are broken — can't verify anything |
| P0-9 | `start_scan()` runs synchronously — blocks chat for 60-120s | `tool_registry.py:122` | Terminal hangs during scan |

### P1 Instability — Breaks Under Load or Edge Cases

| # | What | Where |
|---|------|-------|
| P1-1 | 6 routing layers — slash commands handled in 3 different places | action_resolver, command_router, message_router, supervisor_graph |
| P1-2 | `ApplicationLedger` instantiated with `_sqlite_path` private attr access | `tool_registry.py:320` |
| P1-3 | `show_brief()` reads brief from DB but CommandRouter.brief() reads from filesystem | Two different brief sources |
| P1-4 | No `active_context` columns in sessions table | session_store.py |
| P1-5 | `isdigit()` check blocks natural job selection | action_resolver.py:87 |
| P1-6 | Slash command if/elif chain duplicates CommandRouter | action_resolver.py:67-83 |
| P1-7 | DB writes not atomic — `start_scan()` has multiple cursor.execute() without transaction | tool_registry.py:96-173 |

### P2 Cleanup — Technical Debt

| # | What | Where |
|---|------|-------|
| P2-1 | `session_store.py` performs side-effect migration on read | session_store.py:140-150 |
| P2-2 | `output/daily_briefs/` filesystem brief duplicates DB brief | DailyRunner + CommandRouter |
| P2-3 | `ledger.json` flat file vs `application_ledger` DB table | application_ledger.py |
| P2-4 | 17-item ActionType enum — architectural "enum explosion" | models.py:6-23 |
| P2-5 | `message_router.py` duplicates supervisor_graph.py routing | message_router.py |
| P2-6 | `THREE_LAYER_STATE_ARCHITECTURE.md §9` claims E2E verification that doesn't match code reality | Docs are aspirational fiction |

---

## Contradictions Between THREE_LAYER_STATE_ARCHITECTURE.md and Reality

| Doc Claim | Reality |
|-----------|---------|
| "Stripe / Vercel Mock Jobs: Completely deleted" | TRUE — only in tests.py ✅ |
| "latest_brief_123 & job_stripe: Destroyed" | TRUE ✅ |
| "would kick off background job canned text: Eradicated" | TRUE ✅ |
| "Unified CLI Shortcuts: Removed all direct command shortcuts or routing bypasses" | **FALSE** — action_resolver.py:67-83 still has hardcoded slash if/elif |
| "tool_registry.py MUST DIE. Replace with async sub-graphs" | **FALSE** — tool_registry.py still exists with fake stubs |
| "action_resolver.py MUST DIE. Replace with Tool Calling" | **FALSE** — action_resolver.py still has isdigit() bypass |
| "chat_cli.py MUST DIE (partially). Remove raw SQL. Delete all slash command logic." | **PARTIALLY FALSE** — slash commands still in chat_cli.py and action_resolver.py |
| "E2E Verification — 19 tests, OK" | 19 tests exist but tests_router.py imports dead enum |
| "Fully verified, stabilized, and verified E2E" | **FALSE** — 8 tool handlers return hardcoded fake data |
