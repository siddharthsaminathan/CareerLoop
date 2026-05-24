# CareerLoop Orchestration Refactor: Three-Layer State Architecture

This document serves as the canonical orchestration architecture for CareerLoop, pivoting the system from a rigid, stateless CLI into a dynamic, TAL-style (Task and Actions Logic) conversational operating system.

---

## 1. Root Cause Analysis

The current architecture fails because it attempts to model a complex conversational product as a one-dimensional state machine running inside a procedural loop. 

**Why one-dimensional state is broken:**
By shoving the user's onboarding progress (`PROFILE_COMPLETE`), what they are looking at (`REVIEWING_BRIEF`), and what the system is doing (`SCAN_RUNNING`) into a single `UserState` enum, the system constantly clobbers its own context. A user cannot ask a question about a company while an async scan is running without irreparably breaking the state machine.

**Why intent classification is brittle:**
The system forces complex natural language into predefined enums (e.g., `START_SCAN`, `SHOW_BRIEF`). The `action_resolver.py` uses rigid `if msg_lower.isdigit(): return Action(SELECT_BRIEF_ITEM)` logic that completely bypasses the LLM and hard-couples intent to arbitrary numbers. 

**Why the CLI feels robotic:**
The `tool_registry.py` returns hardcoded static strings (e.g., `"Profile context is active."`, `"Available commands: /brief"`). Hardcoded reply strings destroy conversational UX because the LLM is never allowed to synthesize a contextual, empathetic response based on the *actual* context.

**Spaghetti Routing in `supervisor_graph.py`:**
The LangGraph implementation acts as a god-object. It directly instantiates database connections, dictates UI updates via `artifact_context_updates`, and mixes the raw message history with `temp_profile_data`.

---

## 2. The New 3-Layer State Model

To solve this, state must be decoupled into three completely independent dimensions. 

### A. User Journey State
**Purpose:** Tracks where the user is in their overarching career workflow.
**Examples:** 
- `NEW_USER`
- `PROFILE_READY`
- `APPLICATION_PENDING`
- `INTERVIEW_ACTIVE`
**Mechanism:** Highly stable. Only changes when a major milestone is reached (e.g., CV uploaded, offer signed).

### B. Active Context State
**Purpose:** Tracks what the user is currently referring to conversationally. Enables contextual resolution (e.g., "1", "skip this", "prepare this").
**Examples:**
- `active_brief_id`
- `active_job_id`
- `active_company_id`
- `active_pack_id`
- `last_rendered_items` (array mapping indices to IDs)
- `selected_index`
**Mechanism:** Dynamic. Updated implicitly whenever the UI renders a new artifact to the screen.

### C. Background Work State
**Purpose:** Tracks asynchronous system operations so the UI can stream updates and the LLM knows what the system is currently processing.
**Examples:**
- `scan_run_id` | Status: `QUEUED`, `RUNNING`, `FAILED`, `COMPLETED`
- `pack_run_id` | Status: `GENERATING`, `PENDING_REVIEW`
- `company_research_status`
**Mechanism:** Ephemeral or persisted depending on the job. Changes rapidly.

---

## 3. State Ownership Rules

| Layer | Owner | Rules & Anti-Patterns |
|---|---|---|
| **User Journey** | Orchestrator / Ledger | Never updated by UI. Never used to track conversational flow. Mixing `REVIEWING_JOB` into this layer is strictly forbidden. |
| **Active Context** | UI / Transport Layer | Only the view layer mutates this. If the UI renders Job #3, it sets `active_job_id`. The execution layer *reads* this but *never* overwrites it directly. |
| **Background Work** | Async Queue / Run Table | Purely backend. The UI only subscribes to these streams. LLM intent routers must not block on these states. |

---

## 4. Conversational Resolution Engine

The rigid `ActionType` enum-to-function mapping will be replaced by a **Context-Aware Tool-Calling Paradigm**.

1. **The Resolver:** Instead of picking a label (`SHOW_BRIEF`), the LLM has access to a strict schema of tools (e.g., `FetchBrief(brief_id: Optional[str])`, `PrepareApplicationPack(job_id: str)`).
2. **Context Injection:** The resolver is injected with the `User Journey State`, the `Active Context`, and the `Background Work State`.
3. **Dynamic Routing:**
   - If User says: *"prepare this"*
   - System sees: `active_job_id = 'job_stripe'` in Context.
   - LLM infers: Call `PrepareApplicationPack(job_id='job_stripe')`.
4. **Natural Responses:** Tools return *data*, not strings. The LLM synthesizes the final response natively (e.g. `"I've queued up an application pack for Stripe..."`).

---

## 5. Persistence Architecture

All filesystem dependencies (e.g., `.last_brief_date`, `output/daily_briefs/*.md`) are strictly prohibited.

- **Permanent / User Scoped:** `users` table (auth, base profile).
- **Session / Artifact Scoped:** `active_context` stored natively in the DB (PostgreSQL) linked to the `user_id`. Artifacts like `daily_briefs` and `application_packs` get their own dedicated DB tables with versioning.
- **Event Scoped:** `background_runs` and `run_events` tables to stream logs to the UI without relying on local `.md` or `.log` files.

---

## 6. Live Streaming UX Architecture

Long-running tasks (Scanning, Pack Assembly) must stream real-time events to the UI.

- **Event Stream Model:** A Pub/Sub or Long-Polling architecture querying a `run_events` table.
- **Terminal/Mobile Rendering:** 
  ```text
  Searching LinkedIn...
  ✅ MATCH AI Engineer — BigRio
  ❌ REJECT ML Engineer — San Jose · outside target geography
  ✅ MATCH Fullstack AI Engineer — Moative
  ```
- **UX Goal:** The user must feel the momentum and filtering intelligence of the system, rather than a blank screen or a robotic `"Starting scan..."` message.

---

## 7. TAL-Style Conversational UX

CareerLoop will adopt Google's TAL (Task and Actions Logic) philosophy.

- **Contextual Actions:** Implicitly knowing what the user means without requiring them to restate it.
- **Lightweight Approvals:** Responding with "looks good" immediately moves the pipeline forward.
- **Why it feels alive:** The system separates the "Thinking" (Chat) from the "Doing" (Tools/Artifacts). Currently, CareerLoop forces both into a single synchronous loop, making it feel like a CLI script.

---

## 8. Migration Plan

- **Phase A:** Documentation rewrite only (This document).
- **Phase B:** State model refactor (Implement DB tables for Journey, Context, Work).
- **Phase C:** Persistence rewrite (Delete all `output/*.md` writes, move Briefs/Packs to SQL).
- **Phase D:** Tool registry migration (Replace ActionType enums with LLM Tool-Calling schema).
- **Phase E:** Streaming event system (Implement `run_events` publisher).
- **Phase F:** Transport integrations (Connect Telegram/WhatsApp webhooks).

---

## PART 2: CODEBASE AUDIT

The following files were deep-audited by autonomous sub-agents:

### `careerloop/session/states.py`
- **Responsibility:** Defines `UserState` enum.
- **Violations:** Mixes UX state (`REVIEWING_JOB`) with domain state (`PROFILE_COMPLETE`).
- **Verdict:** MUST REFACTOR. Split into 3 discrete enums/tables.

### `careerloop/session/supervisor_graph.py`
- **Responsibility:** LangGraph orchestration.
- **Violations:** God-object pollution. Directly instantiates DB. Dictates UI state (`artifact_context_updates`).
- **Verdict:** MUST REFACTOR. Extract DB dependencies. Stop manipulating UI state directly.

### `careerloop/whatsapp_ux.py`
- **Responsibility:** Formats text for low-cognitive load platforms.
- **Violations:** Weak dictionary contracts (`.get()`). Hardcodes state options (`1=best 2=all`).
- **Verdict:** MUST REFACTOR. Require Pydantic models. Remove hardcoded state menus.

### `careerloop/chat_cli.py`
- **Responsibility:** Terminal loop and transport payload execution.
- **Violations:** Bypasses domain layer with raw SQL queries. Acts as secondary intent router (`/scan`).
- **Verdict:** MUST DIE (partially). Remove raw SQL. Delete all slash command logic.

### `careerloop/llm_chat.py`
- **Responsibility:** Prompt wrappers for DeepSeek API.
- **Violations:** Forces LLM to output rigid JSON and natural text simultaneously, degrading tone.
- **Verdict:** MUST REFACTOR. Separate structured data extraction from natural language synthesis.

### `careerloop/session/session_store.py`
- **Responsibility:** DB persistence of sessions.
- **Violations:** Performs side-effects (mutating/repairing records) during `get_session()` read operations.
- **Verdict:** MUST REFACTOR. Move onboarding inference out to the orchestrator.

### `careerloop/session/action_resolver.py`
- **Responsibility:** Intent classifier.
- **Violations:** Contains `if msg_lower.isdigit():` which completely bypasses LLM intelligence.
- **Verdict:** MUST DIE. Replace with Tool Calling.

### `careerloop/session/tool_registry.py`
- **Responsibility:** Executes actions mapped to intents.
- **Violations:** Uses fake architecture / stubbed static string returns.
- **Verdict:** MUST DIE. Replace with async sub-graphs and tool execution nodes.

### `careerloop/daily_runner.py`
- **Responsibility:** Automated batch pipeline.
- **Violations:** Relies on `.last_brief_date` filesystem sentinels and `pipeline.md` regex parsing.
- **Verdict:** MUST REFACTOR. Move sentinels to DB.

---

## PART 3: ARCHITECTURE DIAGRAMS

### Three-Layer Orchestration Flow

```text
+-----------------------+
|  User Message / Input |
+-----------+-----------+
            |
            v
+-----------------------+
|   Transport Layer     | 
|   (Telegram/CLI)      |
+-----------+-----------+
            |
            v
+-------------------------------------------------+
|               Action Resolver                   |
|  Reads:                                         |
|  1. User Journey State: [PROFILE_READY]         |
|  2. Active Context: [active_brief: brief_2]     |
|  3. Work State: [scan_id_42: COMPLETED]         |
+-----------------------+-------------------------+
                        |
                        v
+-----------------------+-------------------------+
|                Tool Registry                    |
| Executes context-aware function:                |
| SHOW_LATEST_SCAN_RESULT()                       |
+-----------------------+-------------------------+
                        |
                        v
+-----------------------+-------------------------+
|          DB State / Persistence Layer           |
| Updates 3-Layer Tables / Fetches Data           |
+-----------------------+-------------------------+
                        |
                        v
+-----------------------+-------------------------+
|           Response / Transport                  |
| Renders `brief_2` to user naturally             |
+-------------------------------------------------+
```

### Persistence Entity Diagram

```text
USERS (Layer 1)
├── user_id (PK)
├── master_cv_markdown
└── journey_state (e.g. PROFILE_READY)

SESSIONS (Layer 2)
├── user_id (FK)
├── active_artifact_type (e.g. daily_brief)
├── active_artifact_id (e.g. brief_v2)
└── selected_index (e.g. 1)

BACKGROUND_RUNS (Layer 3)
├── run_id (PK)
├── user_id (FK)
├── type (e.g. SCAN)
└── status (e.g. RUNNING, COMPLETED)

RUN_EVENTS (Streaming Layer)
├── event_id
├── run_id (FK)
├── message (e.g. "✅ MATCH AI Engineer — BigRio")
└── timestamp
```

---

## 9. Current Status (2026-05-25)

### Completed
- V2 state migration: UserJourneyState (4 states) with legacy map for 30+ V1 states
- ActionResolver: LLM-based intent → Action routing with dict-based slash command shortcuts
- ToolRegistry: 17 handlers, 9 query real DB tables (daily_briefs, daily_brief_items, background_runs, run_events, users, company_memory, companies, application_ledger)
- Supervisor graph: 2-node pipeline (action_routing → execute_action → END)
- GENERAL_CHAT: Real DeepSeek LLM responses (no hardcoded text)
- Conversation history: add_messages reducer persists across turns
- E2E test script: e2e_runtime_test.py with real LLM calls

### In Progress
- Scan progress streaming via run_events to CLI
- Profile recovery from users table when sessions row is missing (Supabase/SQLite split)
- Onboarding flow: profile refinement vs scan intent distinction
- ActiveContext persistence across restarts

### Architecture Violations (known, being fixed)
- ~~Hardcoded tool responses~~ — FIXED (all 17 handlers query DB or delegate to LLM)
- ~~CommandRouter bypassing supervisor~~ — FIXED (deleted, all routing via ActionResolver)
- ~~GENERAL_CHAT echo~~ — FIXED (returns real LLM response)
- Scan runs synchronously blocking chat thread — P1 (streaming being added)
- Onboarding state not hydrated from users table on restart — P1 (profile recovery being added)
