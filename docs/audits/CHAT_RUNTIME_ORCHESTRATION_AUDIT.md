# CHAT_RUNTIME_ORCHESTRATION_AUDIT

## A. User Message Flow Trace
User Message → `chat_cli.py` (CLI loop)
- **Slash Commands** (`/scan`, `/brief`, etc.) bypass the orchestrator graph entirely and hit `CommandRouter`.
- **Free text** routes to `TerminalChatAdapter` → `supervisor_graph.py` (`get_supervisor_graph`) → `intent_router` (State evaluation + LLM intent classification) → State transitions or specific node triggers (`deep_research`, `pack_generation`) → Assistant Response is returned to the transport.

## B. State Catalog (`careerloop/session/states.py`)
11 reachable states categorized as:
- **USER JOURNEY:**
  - `IDLE`
  - `ONBOARDING_IDENTIFYING`
  - `ONBOARDING_PROFILE_CONFIRMATION`
  - `ONBOARDING_WAITING_CV`
  - `ONBOARDING_COLLECTING`
  - `PROFILE_COMPLETE`
  - `REVIEWING_JOB`
  - `AWAITING_APPLICATION_CONFIRMATION`
  - `APPLIED`
- **BACKGROUND JOB:**
  - `SCAN_RUNNING`
  - `RESEARCHING_COMPANY`
  - `PACK_GENERATING`
- **ARTIFACT:**
  - `BRIEF_AVAILABLE`
  - `PACK_READY`

*(Legacy states like `DAILY_BRIEF_SENT` are mapped to these).*

## C. The "Reply 1" Regression Analysis
**Root Cause:**
- When a daily brief is outputted, the user is prompted to "Reply 1". 
- When the user types "1", the `ChatIntentAgent` classifies the intent based on a brittle system prompt. Because "1" does not clearly map to an action in its rigid prompt (`SHOW_PIPELINE`, `SCAN_JOBS`, `APPROVE`, `GENERAL_CHAT`, etc.), the intent routing is completely broken.
- Inside `_handle_active_state` (which fires for `BRIEF_AVAILABLE`), if the intent classifier hallucinates or hits `SHOW_PIPELINE`, it executes a massive hardcoded `if/else` block that generates the string `"**Your Pipeline**\n\n"`.
- It then appends the absolute disk path to the response: `reply += f"\n\nToday's brief is available at: {brief_path}"`, leaking the local user file path to the UI and completely dropping the context that the user was trying to review a job.
- The router lacks any concept of "selecting a job context from a brief".

## D. Hardcoded AI Slop & Logic Inventory
- **`careerloop/session/supervisor_graph.py`**:
  - `reply = "Your daily brief is already generated for today! However, if you would like to force a fresh scan of all boards right now, just type \`/scan\` or say 'force scan' to proceed."`
  - `reply = "Ready to scan for new jobs matching your profile... Tip: \`/scan\` runs ~156 board queries and takes 60-120 seconds."`
  - `reply = "**Your Pipeline**\n\n"` (with hardcoded status iteration).
  - `reply = "I didn't receive a message. How can I help?"`
  - `reply = "Approved! Generating your application pack now..."`
  - `reply = "Your application pack is being generated. This may take a moment..."`
  - `reply = "I'm not sure what to do next. Type /help for available commands or /scan to search for new opportunities."`
- **`careerloop/llm_chat.py`**:
  - `SAFE_ERROR_MSG = "I hit a model issue while processing that. Your data is safe. Try again or type /help for available commands."`

## E. Persistence Layer Issues
- **Disk-Only Artifacts:** The daily briefs are persisted on the local filesystem (`output/daily_briefs/YYYY-MM-DD.md`) instead of a database. Checking `os.path.exists(brief_path)` throughout `supervisor_graph.py` makes it undeployable to remote environments.
- **State Split-Brain:** Profile data lives partially in `public.users` (Postgres) and partially in graph state (`temp_profile_data`), causing double loads and synchronization risks.

## F. Orchestration & Architectural Deficit
- **Graph Bypass:** The CLI routes slash commands directly, breaking out of the state machine.
- **Pile of If-Else:** `intent_router` inside `supervisor_graph.py` is a massive `if-elif` chain (lines 235-427) rather than a dynamic agent tool registry.
- **Brittle Intents:** The `ChatIntentAgent` uses explicit keyword routing (`"yes", "approve", "looks good" -> APPROVE`) which forces the LLM to output rigid classification labels instead of dynamically executing tool calls.

## G. Recommended Architecture (Planning)
- **Unified Graph Routing:** All input (slash commands + text) must hit the LangGraph supervisor.
- **Tool Calling (TAL-like):** Move away from intent string classification. Provide tools (`review_job(job_id)`, `show_pipeline()`, `start_scan()`) and let the model invoke them naturally.
- **Database Persistence:** Move the brief artifacts to the database to remove filesystem dependency and path leaks.
- **Remove Slop:** Standardize tool-driven conversational UX without hardcoded strings.
