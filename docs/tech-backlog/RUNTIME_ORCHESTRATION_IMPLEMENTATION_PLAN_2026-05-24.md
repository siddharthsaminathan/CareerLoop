# CareerLoop Final Runtime Architecture — Phase 2+3

> Part of: RUNTIME_ORCHESTRATION_AUDIT_2026-05-24.md

---

## PHASE 2: FINAL RUNTIME ARCHITECTURE

### 2.1 Core Principle

CareerLoop processes user input through a single, unified pipeline:

```
User Input → ActionResolver → ToolExecutor → StateUpdate → LLM Response Synthesis → User
```

No forks. No slash-command bypass. No hardcoded if/elif chains. Every input — slash command, natural language, number selection — resolves into an `Action`, executes through the same `ToolRegistry`, and returns a `ResponseEnvelope`. The LLM always synthesizes the final user-facing text.

### 2.2 Three-Layer State Model (Preserved)

**Layer 1 — User Journey State** (4 stable states)
```
NEW_USER → PROFILE_READY → APPLICATION_PENDING → INTERVIEW_ACTIVE
```
- Owned by: Orchestrator + application_ledger
- Mutated only on milestone transitions (CV uploaded, application submitted, interview scheduled)
- Never used to track conversational flow

**Layer 2 — Active Context** (conversational state)
```json
{
  "active_artifact_type": "daily_brief",   // daily_brief | job_card | application_pack | null
  "active_artifact_id": "uuid-...",
  "active_job_id": "loop-abc123",
  "active_brief_id": "uuid-...",
  "active_pack_id": "pack-...",
  "current_selection_index": 3,
  "last_rendered_items": [{"index": 1, "job_id": "loop-abc"}, ...]
}
```
- Owned by: Transport/UI layer
- Persisted to: `sessions.active_context` (JSONB column)
- Hydrated on every graph invocation from DB
- Updated by `ResponseEnvelope.artifact_context_updates` after every tool execution

**Layer 3 — Background Work State** (async execution)
```
background_runs table:
  run_id | user_id | run_type | status | started_at | completed_at
  
run_events table:
  event_id | run_id | event_type | message | timestamp
```
- Owned by: Background job queue
- UI subscribes to run_events for live streaming
- LLM sees active runs to answer "is my scan done?"

### 2.3 Unified Action Resolution

**Single entry point:** `ActionResolver.resolve()`

All inputs flow through one path:

```
Raw input
  │
  ▼
Slash command? → normalize to /brief, /scan, /pipeline, /status, /profile, /reset, /help
  │ (simple prefix check — no routing logic)
  ▼
Number input + active_brief? → SELECT_BRIEF_ITEM(index=N)
  │ (simple isdigit check with context guard — ONLY when active_brief is set)
  ▼
Everything else → LLM with full context injected:
  - System prompt (tool definitions as JSON schema)
  - User journey state
  - Active context (what is the user looking at?)
  - Background work (what is running?)
  - Last 5 conversation messages (history)
  - Current user message
  ▼
LLM returns: { "action_type": "...", "parsed_args": {...}, "confidence": 0.0-1.0 }
```

**Key changes from current:**
1. Slash commands resolved to ActionType via dict lookup, not if/elif chain
2. `isdigit()` check ONLY when `active_artifact_type == "daily_brief"` — already partially correct
3. LLM prompt includes conversation history, active context, and background work
4. System prompt uses tool-calling schema format (function definitions), not phrase-to-enum mapping

### 2.4 Tool Execution Architecture

All tools follow the same contract:

```python
def execute(self, action: Action, state: UserJourneyState, context: Dict) -> ResponseEnvelope
```

**Rules:**
- Tools return DATA in `ResponseEnvelope` — never user-facing text
- The `text` field contains structured data for the LLM to synthesize
- `response_type` signals the renderer: `text` | `list` | `card` | `document` | `error` | `stream`
- `cards` contains structured items for list rendering
- `artifact_context_updates` tells the session what changed
- `state_updates` tells the orchestrator about journey transitions

**Real implementations required for all 17 actions:**

| Handler | Real Implementation |
|---------|-------------------|
| `general_chat` | No tool call needed — LLM synthesizes directly from context |
| `show_help` | Return structured command list; LLM formats |
| `reset_session` | Clear session + active context; return confirmation data |
| `show_status` | Query DB for user journey + active context + background runs; return structured status |
| `show_profile` | Query `users` table for `master_cv_markdown` + `work_style_prefs`; return data blob |
| `start_scan` | ✅ ALREADY REAL — enqueue background_run, invoke DailyRunner, write to daily_briefs table |
| `show_brief` | ✅ ALREADY REAL — query daily_briefs + daily_brief_items from DB |
| `select_brief_item` | ✅ ALREADY REAL — query daily_brief_items by index from DB |
| `review_job` | Query `application_ledger` DB table for job details + fit_breakdown |
| `skip_job` | Update `application_ledger` status to SKIPPED |
| `save_job` | Update `application_ledger` status to SAVED |
| `show_company_intel` | Query `company_memory` DB table; fallback to `company_intel.py` lazy research |
| `show_people_to_reach` | Query `company_registry` for recruiter names; generate outreach suggestions |
| `prepare_application_pack` | **INVOKE RESUME COUNCIL GRAPH** — enqueue as background run, return pack_id |
| `edit_application_pack` | Re-invoke council with edit instruction; update pack |
| `mark_applied` | Update `application_ledger` status to APPLIED; advance journey to APPLICATION_PENDING |
| `show_pipeline` | Query `application_ledger` DB table with status aggregation |

### 2.5 Response Synthesis

After tool execution, the LLM receives:
- The tool's `ResponseEnvelope` (raw data)
- The conversation history
- The active context

The LLM synthesizes a natural response. No hardcoded text reaches the user.

```
Tool returns: { response_type: "list", cards: [...], text: "..." }
  ↓
LLM synthesizes: "Here's your daily brief for May 24. I found 3 strong matches..."
  ↓
User sees: Natural, contextual response
```

### 2.6 Orchestration Flow

```
┌─────────────────────────────────────────────────────┐
│                  TRANSPORT LAYER                     │
│  CLI, Telegram, WhatsApp, Web                       │
│  - Parses raw payload into UserEvent                 │
│  - Hydrates session from DB                          │
│  - Passes (messages, state, context, work) to Graph  │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│              LANGGRAPH SUPERVISOR                    │
│                                                      │
│  Node 1: action_resolution                           │
│    - ActionResolver.resolve(message, state, context) │
│    - Returns Action                                  │
│                                                      │
│  Node 2: action_execution                            │
│    - ToolRegistry.execute(action, state, context)    │
│    - Returns ResponseEnvelope                        │
│    - Merges artifact_context_updates into session    │
│    - Merges state_updates into journey               │
│                                                      │
│  Node 3: response_synthesis                          │
│    - LLM receives ResponseEnvelope + history          │
│    - Synthesizes natural user-facing text            │
│    - Returns assistant_response + AIMessage          │
│                                                      │
│  Edge: action_execution → response_synthesis (always)│
│  Edge: response_synthesis → END                       │
│  Edge: action_resolution → action_execution           │
└─────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│              TRANSPORT RESPONSE                       │
│  - Sends assistant_response to user                  │
│  - Persists session (state + context)                │
│  - Updates checkpoint (messages)                     │
└─────────────────────────────────────────────────────┘
```

### 2.7 Persistence Architecture

| Data | Store | Access Pattern |
|------|-------|---------------|
| User journey state | `sessions.state` (Postgres/SQLite) | Read on graph entry, write on state transition |
| Active context | `sessions.active_context` (JSONB) | Read on graph entry, merge after tool execution |
| Background runs | `background_runs` + `run_events` | Write by tools, read by UI + LLM |
| Daily briefs | `daily_briefs` + `daily_brief_items` | Write by start_scan, read by show_brief/select_brief_item |
| Application ledger | `application_ledger` DB table | All CRUD via repository, not flat file |
| Company intel | `company_memory` DB table | Read by show_company_intel |
| Conversation history | LangGraph checkpointer (`add_messages`) | Automatic via LangGraph |
| Output artifacts | File system (`output/`) | Cache/export only — never source of truth |
| Brief exports | `output/daily_briefs/{date}.md` | Write-through from DB for human readability — DB is canonical |

### 2.8 Event Streaming Strategy

```
start_scan():
  1. INSERT INTO background_runs (status=RUNNING)
  2. INSERT INTO run_events (message="Initializing scan...")
  3. For each scan stage:
     INSERT INTO run_events (message="Searching LinkedIn...")
     INSERT INTO run_events (message="✅ MATCH AI Engineer - BigRio")
     INSERT INTO run_events (message="❌ REJECT ML Engineer - San Jose")
  4. UPDATE background_runs SET status=COMPLETED
  5. INSERT INTO run_events (message="Scan complete: 24 matches")

UI polls: SELECT * FROM run_events WHERE run_id = ? ORDER BY timestamp
```

For terminal: inline progress spinner + event count
For Telegram: periodic status updates
For Web: WebSocket/SSE stream from run_events

### 2.9 Transport Abstraction

```python
class TransportAdapter(ABC):
    def receive(self, raw_payload) -> Optional[Dict]:
        """Parse → hydrate session → invoke graph → persist → send response"""
        
    def parse_payload(self, raw) -> UserEvent:
        """Platform-specific parsing"""
        
    def send_text(self, user_id, text) -> bool:
        """Platform-specific delivery"""
        
    def send_stream(self, user_id, events: Iterator[RunEvent]) -> bool:
        """Platform-specific streaming (terminal spinner, Telegram edits, Web SSE)"""
```

---

## PHASE 3: IMPLEMENTATION PLAN

### 3.1 Dependency Graph

```
Phase 3A: DB Schema + Persistence
  └─→ Phase 3B: Tool Registry (real implementations)
       └─→ Phase 3C: ActionResolver (context injection + history)
            └─→ Phase 3D: Supervisor Graph (3-node pipeline)
                 └─→ Phase 3E: Response Synthesis (LLM formatting)
                      └─→ Phase 3F: Transport + CLI cleanup
                           └─→ Phase 3G: Tests + Verification
```

### 3.2 File-by-File Migration Plan

#### Phase 3A: DB Schema + Persistence (1 day)

| File | Action | Details |
|------|--------|---------|
| `memory/connection.py` | MODIFY | Add `active_context` JSONB column to sessions table in `_init_sqlite_schema()` |
| `memory/supabase_schema.sql` | MODIFY | Add `active_context` JSONB column to sessions table |
| `session/session_store.py` | MODIFY | Add `get_active_context(user_id)` and `update_active_context(user_id, context)` methods. Remove side-effect migration in `get_session()` — move to explicit `migrate_session()` called once at startup. |
| `session/models.py` | MODIFY | Remove `debug_metadata` from ResponseEnvelope. Add `stream` response_type. |
| `application_ledger.py` | REFACTOR | Migrate from `ledger.json` flat file to `application_ledger` DB table. Keep JSON file as write-through cache. Add `get_by_id(job_id)`, `get_by_status(status)`, `transition(job_id, status)`. |

#### Phase 3B: Tool Registry Real Implementations (2 days)

| File | Action | Details |
|------|--------|---------|
| `session/tool_registry.py` | **REWRITE** | Replace `general_chat`, `show_help`, `show_profile`, `show_status`, `show_company_intel`, `show_people_to_reach`, `prepare_application_pack`, `edit_application_pack`, `review_job`, `mark_applied` with real DB-backed implementations. Remove all hardcoded strings. Return data, not text. Add `get_tool_schemas()` method returning OpenAI-compatible function definitions for the LLM. |

Real implementations:
- `general_chat` → return empty ResponseEnvelope (signal to supervisor: no tool needed, LLM handles directly)
- `show_help` → return structured list of available commands as cards
- `show_profile` → query `users.master_cv_markdown`, return as data
- `show_status` → query sessions + background_runs, return structured status
- `show_company_intel` → query `company_memory` table, fallback to `company_intel.py`
- `show_people_to_reach` → query `company_registry` for recruiter data
- `prepare_application_pack` → invoke Resume Council graph, enqueue as background run
- `review_job` → query `application_ledger` table by job_id
- `mark_applied` → update `application_ledger` status

#### Phase 3C: ActionResolver Redesign (1 day)

| File | Action | Details |
|------|--------|---------|
| `session/action_resolver.py` | **REWRITE** | Remove if/elif slash command chain — replace with dict lookup. Keep isdigit check ONLY within active_brief context. Inject conversation history into LLM prompt. Use tool-calling schema format in system prompt. Pass all 3 state layers to LLM. |

New resolve() flow:
```python
def resolve(self, message, user_id, journey_state, active_context, background_work, messages):
    # 1. Slash commands → dict lookup
    SLASH_MAP = {"/brief": "SHOW_BRIEF", "/scan": "START_SCAN", ...}
    if message.startswith("/"):
        cmd = message.split()[0]
        if cmd in SLASH_MAP:
            return Action(action_type=SLASH_MAP[cmd], ...)
    
    # 2. Number selection within active brief
    if message.strip().isdigit() and active_context.get("active_artifact_type") == "daily_brief":
        return Action(action_type="SELECT_BRIEF_ITEM", parsed_args={"index": int(message)})
    
    # 3. LLM with full context + tool schemas
    prompt = build_prompt(journey_state, active_context, background_work, messages, message)
    response = self._call_api(system_prompt_with_tool_schemas(), prompt)
    return parse_action(response)
```

#### Phase 3D: Supervisor Graph Simplification (1 day)

| File | Action | Details |
|------|--------|---------|
| `session/supervisor_graph.py` | **REWRITE** | Replace current `intent_router` + `pack_generating_node` with 3-node pipeline: `action_resolution` → `action_execution` → `response_synthesis`. Remove onboarding handler — move to tool_registry. Remove state-based if/elif tree — all states route through same 3 nodes. |

New graph:
```python
def action_resolution_node(state):
    action = resolver.resolve(
        message=state["messages"][-1].content,
        user_id=state["user_id"],
        journey_state=state["current_state"],
        active_context=hydrate_context(state),
        background_work=query_background_runs(state["user_id"]),
        messages=state.get("messages", [])[-10:],  # last 10 messages
    )
    return {"pending_action": action}

def action_execution_node(state):
    action = state["pending_action"]
    if action.action_type == "GENERAL_CHAT":
        return {"tool_response": None}  # signal: LLM handles directly
    
    response = tool_registry.execute(action, state["current_state"], state["active_context"])
    
    # Merge context updates into state
    context = state.get("active_context", {})
    context.update(response.artifact_context_updates)
    
    # Merge state updates
    new_journey = response.state_updates.get("state", state["current_state"])
    
    return {
        "tool_response": response,
        "active_context": context,
        "current_state": new_journey,
    }

def response_synthesis_node(state):
    tool_response = state.get("tool_response")
    messages = state.get("messages", [])
    
    if tool_response is None:
        # GENERAL_CHAT — LLM generates directly
        reply = chat_llm(messages)
    else:
        # Tool returned data — LLM synthesizes from data
        reply = synthesize_llm(tool_response, messages, state.get("active_context", {}))
    
    return {
        "assistant_response": reply,
        "messages": [AIMessage(content=reply)],
    }
```

#### Phase 3E: Response Synthesis (1 day)

| File | Action | Details |
|------|--------|---------|
| `session/response_synthesizer.py` | **CREATE** | LLM-powered response synthesis from tool output. Takes `ResponseEnvelope` + conversation history + active context → natural user-facing text. Replaces all hardcoded `ResponseEnvelope.text` strings. |

The synthesizer is a thin LLM prompt:
```
System: You are CareerLoop. Synthesize a natural, contextual response from the tool output.
User journey: {journey_state}
Active context: {active_context}
Tool output: {response_envelope}
Conversation: {history}

Respond conversationally. If the tool returned cards, present them naturally.
If it's an error, be empathetic. Never sound robotic.
```

#### Phase 3F: Transport + CLI Cleanup (1 day)

| File | Action | Details |
|------|--------|---------|
| `chat_cli.py` | **CLEANUP** | Remove `command_router.py` import — all routing now through graph. Keep slash command prefix check but delegate to graph (via transport.receive). Remove `print_help_panel()`, `print_status_card()`, `run_background_scan()`, `print_pipeline()` — all replaced by tool_registry handlers. |
| `session/command_router.py` | **DELETE** | Replaced by ActionResolver + ToolRegistry |
| `session/message_router.py` | **DELETE** | Dead code — duplicated by supervisor_graph |
| `transport/base.py` | MODIFY | Add `send_stream()` abstract method. Add active_context hydration in `receive()`. |
| `transport/terminal_chat.py` | MODIFY | Implement `send_stream()` as Rich Live display |

#### Phase 3G: Tests + Verification (1 day)

| File | Action | Details |
|------|--------|---------|
| `tests/test_chat_runtime.py` | MODIFY | Update from `UserState` (dead) to `UserJourneyState`. Add tests for: active_context persistence, background_runs, tool registry real implementations, response synthesis. Target: 30+ tests. |
| `session/tests_router.py` | **FIX or DELETE** | Currently imports dead `UserState`. Fix or delete. |

### 3.3 Sequencing Plan

**Week 1:**
- Day 1: Phase 3A (DB schema + persistence)
- Day 2-3: Phase 3B (Tool registry real implementations)
- Day 4: Phase 3C (ActionResolver redesign)
- Day 5: Phase 3D (Supervisor graph simplification)

**Week 2:**
- Day 1: Phase 3E (Response synthesis)
- Day 2: Phase 3F (Transport + CLI cleanup)
- Day 3-4: Phase 3G (Tests + verification)
- Day 5: E2E verification + commit

### 3.4 Regression Risks

| Risk | Mitigation |
|------|-----------|
| `UserState` → `UserJourneyState` rename breaks imports | Global find-replace before starting; verify all imports |
| `ledger.json` → DB migration loses data | Write migration script with verification; keep JSON as backup |
| Response synthesis quality degrades | Compare against TAL-style transcripts before shipping |
| `start_scan()` threading breaks terminal | Use subprocess or asyncio; test in both CLI and headless modes |
| Existing sessions with old state format break | Legacy map in states.py handles this; test with prod DB snapshot |

### 3.5 Rollback Strategy

All changes are in `careerloop/session/` and `careerloop/transport/` — no changes to discovery, scoring, council, or rendering. Rollback is:

```bash
git revert <commit-range>
```

Each phase commits independently. If Phase 3B is broken, revert only 3B — 3A stays.

### 3.6 Verification Gates

Before claiming completion:
1. `python -m pytest tests/test_chat_runtime.py` — 30+ tests, all passing
2. CLI smoke test: start → /status → "daily briefing" → select job → "company intel" → "prepare this"
3. No hardcoded strings in any `ResponseEnvelope.text` (grep for `text="`)
4. All tool handlers query DB (grep for `get_connection` in tool_registry.py)
5. `grep -rn "UserState" careerloop/session/` returns zero results (all migrated to UserJourneyState)
6. `grep -rn "command_router" careerloop/` returns zero imports in active code
7. `grep -rn "message_router" careerloop/` returns zero imports in active code
