# Data Persistence Audit — 3 Data Engineer Sub-Agent Report
**Date:** 2026-05-29
**Method:** 3 sub-agents, live Supabase queries via psycopg2, code path tracing

---

## EXECUTIVE SUMMARY

**Message persistence is COMPLETELY BROKEN for the API path.**
The tables exist but nothing writes to them. 8 systemic gaps identified.

---

## AGENT 1: Message Persistence Audit

### What We Found (DB Evidence)

| Table | Rows | For Real User (730d5bab) | Created Via |
|-------|------|--------------------------|-------------|
| careerloop.conversations | 2 rows | **0 rows** | CLI only (May 24) |
| careerloop.messages | 4 rows | **0 rows** | CLI only (May 24) |
| careerloop.sessions | 1 row | 1 row (stale, 08:55 UTC) | SessionStore |
| public.checkpoints | 73 rows | **0 rows** | CLI only (test user) |

### Root Cause (Code Path Tracing)

**POST /v1/chat/message** -> ChatService.message():

```
NEW_USER path:
  OnboardingFlow.handle_message()  <- NEVER writes to conversations/messages
  -> returns text reply
  -> session.save_session()       <- writes to sessions table ONLY

PROFILE_READY+ path:
  graph.invoke()                   <- LangGraph state (IN-MEMORY only)
  -> execute_action_node()        <- returns AIMessage in state dict
  -> ChatService returns reply    <- NEVER writes to conversations/messages
  -> No DB persistence of messages
```

**The careerloop.conversations and careerloop.messages tables are NEVER written to by any code path that runs from the API.** The 2 existing conversations were created by the CLI transport (May 24, abandoned code path).

### Where Data SHOULD Be Written

The messages table has these columns:
```sql
CREATE TABLE careerloop.messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES careerloop.conversations(id),
    user_id UUID REFERENCES careerloop.users(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    action_type TEXT,
    action_confidence REAL,
    artifact_context JSONB,
    response_envelope JSONB,
    tokens_used INTEGER,
    created_at TIMESTAMPTZ
);
```

This is a rich schema designed to store the full conversation history -- it is just never populated.

---

## AGENT 2: Session and Context Persistence Audit

### What We Found (Data Flow Tracing)

**Session write path:**
```
ChatService.message()
  -> SessionStore.get_session()     <- reads from careerloop.sessions
  -> SessionStore.save_session()    <- writes to careerloop.sessions
     Writes: state, current_job_id, onboarding_step, temp_profile_data,
             active_artifact_type, active_artifact_id, active_job_id,
             active_brief_id, active_pack_id, current_selection_index
```

**Root Cause G4:** The supervisor graph's execute_action_node() creates its OWN SessionStore instance:
```python
# supervisor_graph.py line 68-72
from careerloop.memory.connection import DatabaseManager
from careerloop.session.session_store import SessionStore
db = DatabaseManager(os.getenv("DATABASE_URL"))  # NEW instance each call!
store = SessionStore(db)
```

This means:
1. ChatService creates SessionStore(A) -> reads session -> passes to LangGraph
2. supervisor graph creates SessionStore(B) -> executes action -> updates session
3. ChatService re-reads session after graph.invoke() - line 82
4. But execute_action_node also creates a NEW DatabaseManager with a NEW pool

**LangGraph Checkpointer (PostgresSaver):**
- public.checkpoints table exists with 73 rows -- all from the CLI/test user
- API path does NOT pass a checkpointer to get_supervisor_graph()
- Line 218-219: builder.compile(checkpointer=checkpointer) -- checkpointer is None
- Messages accumulate in graph state dict but are NEVER checkpointed to DB

---

## AGENT 3: CV/Resume Processing and Hang Root Cause

### The "330-minute hang" -- Root Cause Analysis

**Code path when user pastes CV:**
```
POST /v1/chat/message (user state = NEW_USER or CV step)
  -> ChatService.message()
  -> OnboardingFlow.handle_message()
  -> _handle_waiting_cv(session, text, data)
  -> self.extraction_agent.extract(text)    <- line 118
  -> CVExtractionAgent.extract()
  -> _call_api(system_prompt, "CV Text:\n{truncated}")  <- line 287
  -> requests.post(timeout=30)              <- line 43
```

### Why It Hangs for 330 Minutes

| Issue | Impact | Evidence |
|-------|--------|----------|
| No HTTP timeout for onboarding | Onboarding path in ChatService does NOT use _invoke_with_timeout(). Only supervisor graph has it. | chat_service.py lines 29-52 |
| 30s timeout, 2 retries = 90s max | _call_api has 30s timeout with 2 retries. But if request gets stuck in TCP connect, timeout may not trigger properly. | llm_chat.py line 43 |
| No DB connection timeout | pool.getconn() has no timeout -- blocks forever if pool is exhausted. | connection.py |
| Frontend may send duplicate requests | If frontend fetch() has own timeout, it retries -- spawning MULTIPLE concurrent LLM calls. | Speculative |

**Most likely hang scenario:**
1. User pastes CV -> ChatService routes to OnboardingFlow
2. OnboardingFlow calls CVExtractionAgent.extract() -> DeepSeek API (~25s)
3. OnboardingAgent.process() called to validate -> another DeepSeek call (~25s)
4. HTTP connection held open for 50+ seconds
5. Frontend times out at 30s, retries -> another POST with same CV
6. Now there are 2 concurrent onboarding flows, both making DeepSeek calls
7. Each call opens a DB connection for session saves
8. Connection pool exhausted -> next requests block forever -> user waits forever

---

## COMPREHENSIVE GAP TABLE

| # | Gap | Severity | System | Root Cause |
|---|-----|----------|--------|------------|
| G1 | Messages never persisted | P0 | Chat API | No code writes to conversations/messages tables from the API path |
| G2 | No checkpointer in API path | P0 | LangGraph | get_supervisor_graph(checkpointer=None) -- graph state is in-memory only |
| G3 | No timeout on onboarding path | P0 | Chat Service | _invoke_with_timeout() only wraps supervisor graph, not onboarding flow |
| G4 | Duplicate SessionStore instances | P1 | Session | ChatService creates SessionStore(A), graph creates SessionStore(B) |
| G5 | No conversation history in LLM context | P1 | Supervisor Graph | messages array is empty on every new API call |
| G6 | Session active_context not written back | P1 | Session Store | ChatService does not save graph's updated context to sessions table |
| G7 | Frontend may retry on timeout | P1 | UX | Client-side timeout causes duplicate LLM calls |
| G8 | No DB connection timeout | P1 | Connection | pool.getconn() has no timeout |

---

## IMPLEMENTATION PLAN

### Phase 1: Fix Critical Path (P0 -- Do This NOW)

**Fix G1 + G6: Add message persistence + context saving to ChatService**

After getting the reply from onboarding or supervisor graph, write to careerloop.messages AND save session context back.

**Fix G3: Add timeout to onboarding path**

Wrap the onboarding flow call with the same _invoke_with_timeout() pattern:
```python
onboarding_result = _invoke_with_timeout(
    lambda: flow.handle_message(session, text),
    timeout=120
)
```

### Phase 2: Session Context Fix (P1)

**Fix G4: Pass SessionStore into graph context**

In chat_service.py, inject the store into the graph input:
```python
graph_input["_session_store"] = self.store
```

In supervisor_graph.py execute_action_node(), check for it:
```python
store = graph_input.get("_session_store") or SessionStore(db)
```

**Fix G6: Persist context after graph invoke**
```python
result = graph.invoke(graph_input, config=config)
updated = self.store.get_session(user_id)
```

This already happens at line 82 -- but the issue is that the graph creates its OWN store.

### Phase 3: LangGraph Checkpointer (P1)

Wire PostgresSaver checkpointer into the API path:
```python
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string(os.getenv("DATABASE_URL"))
```

Then load previous state on each call to populate the messages array.

---

## File Summary

| File | Changes Needed | Priority |
|------|---------------|----------|
| careerloop_api/services/chat_service.py | Add message persistence, onboarding timeout, session context save | P0 |
| careerloop/session/supervisor_graph.py | Accept passed SessionStore instead of creating new one | P1 |
| careerloop/session/session_store.py | Add save_messages() helper method | P1 |
