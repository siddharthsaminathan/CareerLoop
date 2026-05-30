# FORENSIC RUNTIME TRACE: INDIVIDUAL TURN RESOLUTION

**Target User ID:** `730d5bab-2587-4507-a16a-70cd662d59c2`
**Target Conversation ID:** `f337f33a-6e80-442d-a9cd-20a44a9d2764`
**Input Message:** `"hello"`
**Audit Date:** 2026-05-30

This document reconstructs the actual runtime values and variables resolved by the CareerLoop API chat pipeline on a single incoming conversational turn, resolving the apparent contradiction between database representation and runtime behavior.

---

## The Apparent Contradiction Resolved

* **The Mismatch Premise:**
  The database shows the user session is in step `1` (which a developer might assume stands for "Step 1: Greet / Name Collection"). But the runtime behaves as if it is "Waiting for CV".
* **The Reality (No Contradiction):**
  In the onboarding codebase (`careerloop/onboarding/onboarding_flow.py` lines 18-24), step integer constants are defined as:
  - `STEP_IDLE = 0` (Greeting / Name collection)
  - `STEP_WAITING_CV = 1` (Waiting for CV)
  - `STEP_CONFIRMING = 2` (Extracted data confirmation)
  - `STEP_COLLECTING = 3` (Conversational Gap-fill)
  - `STEP_IDENTIFYING = 10` (LinkedIn lookup)
  - `STEP_PROFILE_CONFIRMATION = 11` (LinkedIn profile confirmation)

Therefore, **`onboarding_step = 1` in the database is literally the integer representation of the constant `STEP_WAITING_CV` (Waiting for CV).** Both the database and the runtime are in 100% perfect agreement.

---

## Actual Runtime Trace (Turn Sequence)

When the client sends the payload `{"text": "hello", "conversation_id": "f337f33a-6e80-442d-a9cd-20a44a9d2764"}`:

### 1. Load Session State (`careerloop.sessions`)
The chat service calls `self.store.get_session(user_id)`. The values returned from the PostgreSQL query are:
* **`user_id`**: `"730d5bab-2587-4507-a16a-70cd662d59c2"` (type: `str`)
* **`state`**: `"NEW_USER"` (type: `str` / mapping to `UserJourneyState.NEW_USER`)
* **`onboarding_step`**: `1` (type: `int` / mapping to constant `STEP_WAITING_CV = 1`)
* **`temp_profile_data`**: `{"_active_conversation_id": "f337f33a-6e80-442d-a9cd-20a44a9d2764"}` (type: `dict`)

### 2. Load Onboarding State (Constants)
The `OnboardingFlow` engine loads the mapping constants from memory:
* `STEP_IDLE = 0`
* `STEP_WAITING_CV = 1` (Matches `session.onboarding_step`!)
* `STEP_CONFIRMING = 2`
* `STEP_COLLECTING = 3`
* `STEP_IDENTIFYING = 10`
* `STEP_PROFILE_CONFIRMATION = 11`

### 3. Load Conversation State (`careerloop.conversations` & `careerloop.messages`)
* **Active Conversation:** `_ensure_conversation` reads `temp_profile_data` and returns `"f337f33a-6e80-442d-a9cd-20a44a9d2764"`.
* **User Message Logging:** The incoming message is written to `careerloop.messages`:
  ```sql
  INSERT INTO careerloop.messages (id, conversation_id, user_id, role, content, action_type)
  VALUES (gen_random_uuid(), 'f337f33a-6e80-442d-a9cd-20a44a9d2764', '730d5bab-2587-4507-a16a-70cd662d59c2', 'user', 'hello', null);
  ```

### 4. Routing Decision
The `ChatService::message` router checks the journey state:
* **Check:** `if session.state == UserJourneyState.NEW_USER:`
  - Value evaluated: `"NEW_USER" == "NEW_USER"` $ightarrow$ **True**.
* **Decision:** Routes execution directly to `OnboardingFlow(self.store).handle_message(session, "hello")`. The main LangGraph supervisor agent checkpointer is bypassed.

### 5. Selected Handler
Inside `OnboardingFlow::handle_message`:
* **Evaluation:**
  ```python
  if step == STEP_WAITING_CV: # step = 1, STEP_WAITING_CV = 1
      return self._handle_waiting_cv(session, text, data)
  ```
  - Value evaluated: `1 == 1` $ightarrow$ **True**.
* **Handler Dispatched:** `self._handle_waiting_cv(session, text="hello", data=data)`.

### 6. Selected Onboarding Step (Evaluating guards)
Inside `_handle_waiting_cv`:
* **Guard 1 (Conversational Commands):**
  - Code: `if text.strip().lower() in {"skip", "no", "later"}:`
  - Value evaluated: `"hello" in {"skip", "no", "later"}` $ightarrow$ **False**.
* **Guard 2 (CV Character Length Limit):**
  - Code: `if len(text.strip()) < 80:`
  - Value evaluated: `len("hello") = 5 < 80` $ightarrow$ **True**.
* **Execution:**
  - The guard intercepts the flow.
  - **No database mutations or transitions are executed.** `self._save(session)` is completely bypassed.
  - **No local variable changes are executed.** `session.onboarding_step` remains `1`.
  - The function returns the static error reply.

### 7. Response Generated
* **Formatted String Reply:**
  ```text
  "That looks too short to be a full CV. Please paste your complete resume text, or upload a PDF/DOCX file to proceed."
  ```
* **Assistant Message Logging:** The reply is written to `careerloop.messages` for conversation `"f337f33a-6e80-442d-a9cd-20a44a9d2764"`.
* **HTTP Envelope Output:**
  ```json
  {
    "message": "That looks too short to be a full CV. Please paste...",
    "response_type": "text",
    "cards": [],
    "actions": [],
    "active_context": {
      "active_artifact_type": null,
      "active_job_id": null,
      "active_brief_id": null,
      "active_pack_id": null
    },
    "state": "NEW_USER"
  }
  ```
* **Post-State DB Sync:** The row in `careerloop.sessions` is not written to, retaining its exact trapped state:
  `state = 'NEW_USER'`, `onboarding_step = 1`.

---

## Trace Summary Table

| Pipeline Phase | Component Coordinate | Variable Checked | Current Value | Execution Outcome |
|---|---|---|---|---|
| **Auth Spine** | FastAPI Auth Dependency | Bearer JWT Token | `730d5bab-2587-4507-a16a-70cd662d59c2` | Authenticated successfully |
| **State Hydration** | `SessionStore::get_session` | `user_id` in sessions | `state='NEW_USER'`, `onboarding_step=1` | Session hydrated successfully |
| **Pipeline Routing** | `ChatService::message` | `session.state` | `NEW_USER` | Routed to `OnboardingFlow` engine |
| **Step Routing** | `OnboardingFlow::handle_message` | `session.onboarding_step` | `1` (`STEP_WAITING_CV`) | Routed to `_handle_waiting_cv` |
| **Guard Evaluation** | `OnboardingFlow::_handle_waiting_cv` | `len(text)` | `len("hello") = 5` (< 80 characters) | Length guard evaluates to **True** |
| **Early Termination** | `OnboardingFlow::_handle_waiting_cv` | Early return string | `"That looks too short to be a full CV..."` | Returned warning; bypassed state saves |
