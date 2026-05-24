# Chat Runtime V2 Architecture

## Overview
The V2 Chat Runtime modernizes CareerLoop's orchestration layer by transitioning from an intent-and-string-parsing model to an **Action-based** state machine modeled loosely on Google's TAL (Task and Actions Logic). 

Previously, `supervisor_graph.py` handled raw string outputs and massive if/else routing blocks. Slash commands lived completely outside the graph in `chat_cli.py`. The new architecture unifies all commands and free-text inputs through an `ActionResolver` and executes them via a `ToolRegistry`.

## Core Components

### 1. Action Model (`models.py`)
- **ActionType**: Enumeration of all valid user actions (e.g., `SHOW_BRIEF`, `SELECT_BRIEF_ITEM`, `PREPARE_APPLICATION_PACK`).
- **Action**: A standardized data payload containing the parsed action type, confidence, and LLM-extracted arguments.
- **ResponseEnvelope**: A structured response from the tool layer back to the client, capable of delivering text, cards, and mutating the session's active context.

### 2. Action Resolver (`action_resolver.py`)
Replaces the legacy `ChatIntentAgent`. It takes the user's raw text and active context, then outputs an `Action`. 
- **Hardcoded Rules**: Explicit slash commands (`/brief`) and contextual numbers ("1" while reviewing a brief) bypass LLM inference for speed and guaranteed deterministic behavior.
- **LLM Inference**: Natural language requests map to actions using the LLM when no rigid heuristic applies.

### 3. Tool Registry (`tool_registry.py`)
A dispatch router mapping `ActionType` to discrete execution functions.
Instead of monolithic graph nodes, every action maps to a discrete tool. Each tool returns a `ResponseEnvelope`.

### 4. Active Artifact Context (`session_store.py`)
To emulate mobile card-based UX, the session DB now tracks:
- `active_artifact_type` (e.g., "daily_brief", "job_card")
- `active_artifact_id`
- `active_job_id`
- `current_selection_index`

This allows users to say "why this job" or "1" and the ActionResolver immediately knows the context without doing expensive string searches through chat history.

### 5. Supervisor Graph (`supervisor_graph.py`)
The langgraph implementation has been reduced to just two main nodes:
1. `action_routing`: Runs the ActionResolver to determine intent.
2. `execute_action`: Runs the ToolRegistry to execute the action and mutate the context.

## State Machine Simplification
We dropped all transient background task states (e.g., `PACK_GENERATING`, `SCAN_RUNNING`) from the conversational `UserState`. State now exclusively tracks the long-running user journey (`IDLE`, `ONBOARDING`, `PROFILE_COMPLETE`, `REVIEWING_BRIEF`, `REVIEWING_JOB`, `REVIEWING_PACK`, `APPLIED`). Background tasks execute asynchronously via Actions and notify the user via cards.
