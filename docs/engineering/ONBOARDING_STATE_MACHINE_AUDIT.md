# ONBOARDING STATE MACHINE AUDIT

**Audit Date:** 2026-05-30
**Scope:** Deep-dive analysis of state constants, dispatcher routing, and database mutations within the onboarding state machine.

---

## 1. Step Constant Definition & Mapping

In `careerloop/onboarding/onboarding_flow.py` (lines 18-24), the operational onboarding steps are represented by integer constants:

```python
STEP_IDLE         = 0   # First message — greet (LinkedIn-first if configured, else CV)
STEP_WAITING_CV   = 1   # Waiting for CV text or file
STEP_CONFIRMING   = 2   # Showing extracted summary — waiting for YES/correction
STEP_COLLECTING   = 3   # Conversational gap-fill for missing fields
# LinkedIn-first steps (active when SERPAPI_KEY is configured)
STEP_IDENTIFYING          = 10  # Waiting for the user's name to look up on LinkedIn
STEP_PROFILE_CONFIRMATION = 11  # Showing "Is this you?" card — waiting YES/NO
```

These steps map to physical values stored in `careerloop.sessions.onboarding_step` in PostgreSQL.

---

## 2. Onboarding Engine Dispatcher Route

Every chat message received by `ChatService` routes to the dispatcher inside `OnboardingFlow::handle_message` when `session.state == UserJourneyState.NEW_USER`:

```python
    def handle_message(self, session: Session, text: str) -> Tuple[str, UserJourneyState]:
        state  = session.state
        step   = session.onboarding_step
        data   = session.temp_profile_data or {}

        if state == UserJourneyState.PROFILE_READY:
            return self._already_complete(data), UserJourneyState.PROFILE_READY

        # Route by step
        if step == STEP_IDLE:
            return self._handle_idle(session, text)
        if step == STEP_WAITING_CV:
            return self._handle_waiting_cv(session, text, data)
        if step == STEP_CONFIRMING:
            return self._handle_confirming(session, text, data)
        if step == STEP_COLLECTING:
            return self._handle_collecting(session, text, data)

        # LinkedIn-first steps (active when SerpAPI configured)
        if step == STEP_IDENTIFYING:
            return self._handle_identifying(session, text, data)
        if step == STEP_PROFILE_CONFIRMATION:
            return self._handle_profile_confirmation(session, text, data)
```

---

## 3. Detailed Forensic Question Analysis

### Q1: Where is onboarding_step initially assigned?
* **File:** `careerloop/session/session_store.py`
* **Function:** `get_session` (lines 162-202)
* **Code Coordinates:**
  ```python
  if not row:
      profile_data = self._load_profile_data(user_id)
      default_state = UserJourneyState.NEW_USER
      temp_profile_data = profile_data or None
      ...
      default_session = Session(
          user_id=user_id,
          state=default_state,
          temp_profile_data=temp_profile_data,
      )
      self.save_session(default_session)
  ```
* **Explanation:** When a user is brand new (no session row exists in `careerloop.sessions`), a default `Session` object is instantiated. Because `onboarding_step` is not explicitly passed, it inherits the dataclass default parameter `onboarding_step: int = 0` (`STEP_IDLE`). It is then committed to PostgreSQL as `0` by `save_session(default_session)`.

### Q2: Why does a brand new user start in STEP_WAITING_CV instead of STEP_IDLE?
* **They don't.** On a fresh signup, a user correctly starts at `STEP_IDLE` (0).
* **The Siddharth Scenario:** Siddharth's session was in `STEP_WAITING_CV` (1) because he had **already completed a prior interaction** that advanced his step:
  1. The session initialized at `STEP_IDLE` (0).
  2. The user sent the first message `"hello"`.
  3. The dispatcher routed to `_handle_idle`, which set `onboarding_step = STEP_IDENTIFYING` (10) and prompted for his name.
  4. The user sent `"hello"` inside `STEP_IDENTIFYING` (10).
  5. `_handle_identifying` executed a LinkedIn SerpAPI lookup on the name `"hello"`, which failed.
  6. On lookup failure, the engine mutated `session.onboarding_step = STEP_WAITING_CV` (1) and saved it to PostgreSQL.

### Q3: What code path moves a user from STEP_IDLE to STEP_WAITING_CV?
There are two direct code paths:

* **Path A (LinkedIn Lookup Failure Graceful Fallback):**
  - `_handle_idle` line 96 $ightarrow$ updates step to `STEP_IDENTIFYING` (10).
  - `_handle_identifying` line 210 $ightarrow$ updates step to `STEP_WAITING_CV` (1) on SerpAPI lookup failure.
* **Path B (Manual Path Redirection):**
  - `_handle_profile_confirmation` line 290 $ightarrow$ updates step to `STEP_WAITING_CV` (1) if user rejects LinkedIn confirmation card (replies NO).
* **Path C (LinkedIn Confirmation Success):**
  - `_handle_profile_confirmation` line 262 $ightarrow$ updates step to `STEP_WAITING_CV` (1) if user confirms LinkedIn profile (replies YES).

### Q4: Did this specific user ever pass through STEP_IDLE?
* **Yes.** The message history trace in `USER_STATE_AUDIT.md` shows that Conversation `8105df4c-7dbf-4d99-bdc0-a5deb17d0e8e` (Conversation #2) received `"hello"` and returned `"I couldn't find a confident LinkedIn match for hello..."`.
* This proves that prior to this lookup failure, the user session was successfully initialized at `STEP_IDLE` (0) and advanced through `STEP_IDENTIFYING` (10) to `STEP_WAITING_CV` (1).

### Q5: Show the exact code responsible for: NEW_USER + STEP_WAITING_CV existing simultaneously.
In `chat_service.py` line 88:
```python
if session.state == UserJourneyState.NEW_USER:
    from careerloop.onboarding.onboarding_flow import OnboardingFlow
    flow = OnboardingFlow(self.store)
    reply, _new_state = _run_with_timeout(
        lambda: flow.handle_message(session, text),
        ...
```
In `onboarding_flow.py` line 57:
```python
def handle_message(self, session: Session, text: str) -> Tuple[str, UserJourneyState]:
    ...
    if step == STEP_WAITING_CV:
        return self._handle_waiting_cv(session, text, data)
```
In `onboarding_flow.py` line 120-127 (inside `_handle_waiting_cv`):
```python
    if len(text.strip()) < 80:
        char_count = len(text.strip())
        return (
            f"I am currently waiting for your CV or resume text...",
            UserJourneyState.NEW_USER,
        )
```
This demonstrates how `NEW_USER` journey state and `STEP_WAITING_CV` (1) step are carried together in the `Session` object.

---

## 4. Onboarding Flow Lifecycle Table

| Action Turn | Input Text | State Before | Step Before | Handler Executed | State After | Step After | Reply Prompt Generated |
|---|---|---|---|---|---|---|---|
| **0. Hydration** | None (First load) | `N/A` | `N/A` | `SessionStore::get_session` | `NEW_USER` | `0` (`STEP_IDLE`) | None (Initialized) |
| **1. Greeting** | `"hello"` | `NEW_USER` | `0` | `_handle_idle` | `NEW_USER` | `10` (`STEP_IDENTIFYING`) | *"Welcome to CareerLoop! What's your full name?"* |
| **2. Name Input** | `"Siddharth Saminathan"` | `NEW_USER` | `10` | `_handle_identifying` | `NEW_USER` | `11` (`STEP_PROFILE_CONFIRMATION`) | *"I found this profile — is this you? YES/NO"* |
| **3. Confirmation** | `"YES"` | `NEW_USER` | `11` | `_handle_profile_confirmation` | `NEW_USER` | `1` (`STEP_WAITING_CV`) | *"Great — pre-filled from LinkedIn! Now paste your CV..."* |
| **4. CV Upload** | `<800 lines of CV text>` | `NEW_USER` | `1` | `_handle_waiting_cv` | `NEW_USER` | `2` (`STEP_CONFIRMING`) | extracted profile confirmation checklist |
| **5. Finish** | `"YES"` | `NEW_USER` | `2` | `_handle_confirming` | `PROFILE_READY` | `0` (`STEP_IDLE`) | *"Your profile is complete! Welcome to CareerLoop!"* |
