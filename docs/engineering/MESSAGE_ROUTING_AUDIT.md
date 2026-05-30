# MESSAGE ROUTING FORENSIC TRACE

**Target User ID:** `730d5bab-2587-4507-a16a-70cd662d59c2`
**Conversation ID:** `f337f33a-6e80-442d-a9cd-20a44a9d2764`
**Message Content:** `"wtf"`
**Audit Date:** 2026-05-30

This document traces the exact message routing path from HTTP ingress to the database persistence layer, showing why the static *"Too short to be a full CV"* response was returned.

---

## 1. Trace Pipeline Map

```
Frontend HTTP Request
   ↓ [POST /v1/chat/message]
FastAPI Router (careerloop_api/routers/chat.py)
   ↓ [Inject Auth JWT & DB Pool Connection]
Chat Service (careerloop_api/services/chat_service.py)
   ↓ [Hydrate Session & Ensure Active Conversation ID]
Onboarding Flow Dispatcher (careerloop/onboarding/onboarding_flow.py)
   ↓ [Route message by step: STEP_WAITING_CV = 1]
Onboarding Handler (careerloop/onboarding/onboarding_flow.py::_handle_waiting_cv)
   ↓ [Evaluate Guards: len("wtf") < 80 characters]
Response Generator & Message Logger
   ↓ [Save assistant message & return JSON payload]
Frontend Ingress
```

---

## 2. In-Depth Trace Steps

### Step 1: Frontend Ingress
The user types `"wtf"` inside the conversational UI. The frontend application makes an asynchronous POST call:
* **Endpoint:** `POST /v1/chat/message`
* **Headers:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <Supabase_JWT>`
* **Request Payload:**
  ```json
  {
    "text": "wtf",
    "conversation_id": "f337f33a-6e80-442d-a9cd-20a44a9d2764"
  }
  ```

### Step 2: FastAPI Routing (`careerloop_api/routers/chat.py#L20-L22`)
* The request is intercepted by Uvicorn and handled by FastAPI.
* **`get_current_user` Dependency:** Validates the JWT signature against the `SUPABASE_JWT_SECRET` and extracts the user ID: `"730d5bab-2587-4507-a16a-70cd662d59c2"`.
* **`get_db` Dependency:** Acquires a PostgreSQL connection thread-safely from the `ThreadedConnectionPool`.
* Calls the service layer:
  ```python
  ChatService(db).message(user_id="730d5bab-2587-4507-a16a-70cd662d59c2", text="wtf")
  ```

### Step 3: Chat Service Layer (`careerloop_api/services/chat_service.py#L71-L129`)
1. **Hydrate Session:** Calls `self.store.get_session(user_id)`.
   - Hits `careerloop.sessions` for `user_id = '730d5bab-2587-4507-a16a-70cd662d59c2'`.
   - Hydrates `session.state = UserJourneyState.NEW_USER` and `session.onboarding_step = 1` (`STEP_WAITING_CV`).
2. **Ensure Conversation ID:** Calls `self._ensure_conversation(user_id)`.
   - Detects `temp_profile_data.get("_active_conversation_id")` is already `"f337f33a-6e80-442d-a9cd-20a44a9d2764"`. Returns this ID.
3. **Persist User Message:** Saves the user's message in the database `careerloop.messages`:
   ```python
   self.store.save_message(
       user_id="730d5bab-2587-4507-a16a-70cd662d59c2",
       conversation_id="f337f33a-6e80-442d-a9cd-20a44a9d2764",
       role="user",
       content="wtf"
   )
   ```
4. **Determine Routing Logic:** Because `session.state == UserJourneyState.NEW_USER`, it bypasses the main LangGraph supervisor graph and routes directly to the `OnboardingFlow` engine:
   ```python
   from careerloop.onboarding.onboarding_flow import OnboardingFlow
   flow = OnboardingFlow(self.store)
   reply, _new_state = _run_with_timeout(lambda: flow.handle_message(session, "wtf"))
   ```

### Step 4: Onboarding Engine Dispatcher (`careerloop/onboarding/onboarding_flow.py#L57-L81`)
1. Hydrates properties:
   - `state = session.state` (`UserJourneyState.NEW_USER`)
   - `step = session.onboarding_step` (`1` / `STEP_WAITING_CV`)
   - `data = session.temp_profile_data` (`{"_active_conversation_id": "f337f33a-6e80-442d-a9cd-20a44a9d2764"}`)
2. Checks step constants and routes to step handler:
   ```python
   if step == STEP_WAITING_CV:
       return self._handle_waiting_cv(session, "wtf", data)
   ```

### Step 5: Onboarding Guard Evaluation (`careerloop/onboarding/onboarding_flow.py#L106-L127`)
Inside `_handle_waiting_cv`:
1. **Conversational Commands Guard:** Checks if input is `"skip"`, `"no"`, or `"later"`. `"wtf"` is not, so it continues.
2. **Length Guard:** Evaluates input length:
   ```python
   if len(text.strip()) < 80: # len("wtf") == 3
   ```
   - Since `3 < 80`, the length guard evaluates to **True**.
   - It immediately exits early and formats the response string:
     ```python
     char_count = len("wtf".strip()) # 3
     return (
         f"I am currently waiting for your CV or resume text so I can build your professional profile.\n\n"
         f"The message you sent ({char_count} characters) is too short to be parsed as a full resume.\n\n"
         f"👉 Please paste your **complete CV or resume text** here (minimum 80 characters), or upload a PDF/DOCX file to proceed.",
         UserJourneyState.NEW_USER,
     )
     ```
   - Crucially, **no state updates are written to the session database.** `session.onboarding_step` remains `1` and `session.state` remains `NEW_USER`.

### Step 6: Response Generator (`careerloop_api/services/chat_service.py#L108-L129`)
1. The service receives `reply` and `UserJourneyState.NEW_USER`.
2. It persists the assistant's message in the database `careerloop.messages`:
   ```python
   self.store.save_message(
       user_id="730d5bab-2587-4507-a16a-70cd662d59c2",
       conversation_id="f337f33a-6e80-442d-a9cd-20a44a9d2764",
       role="assistant",
       content=reply
   )
   ```
3. Returns the formatted HTTP response JSON envelope:
   ```json
   {
     "message": "I am currently waiting for your CV or resume text...",
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

---

## 3. Rationale for Loop Lock

The CV validation error was selected because:
1. **The State Was Already STEP_WAITING_CV:** Due to a failed name-identification or LinkedIn search during Conversation #2, the user's persistent `onboarding_step` in `careerloop.sessions` was written as `1` (`STEP_WAITING_CV`).
2. **Onboarding State is User-Scoped, Not Conversation-Scoped:** When Conversation #1 was loaded, the database hydrated the user's step `1` from their previous session.
3. **No Conversational Escape Hatch:** The `STEP_WAITING_CV` handler has a strict guard rejecting any input shorter than 80 characters. Because this guard returns early without updating the step or clear-buffering the input, any conversational attempt (e.g., `"wtf"`, `"do you even know my name"`, `"who are you"`) triggers the same guard, looping indefinitely.
