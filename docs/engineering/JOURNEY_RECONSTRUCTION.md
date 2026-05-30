# USER JOURNEY RECONSTRUCTION

**Target User:** Siddharth Saminathan ([siddharth.swami99@gmail.com](mailto:siddharth.swami99@gmail.com))
**System User ID:** `730d5bab-2587-4507-a16a-70cd662d59c2`
**Audit Date:** 2026-05-30

This document reconstructs the chronological journey of Siddharth, tracing his interactions from registration and successful onboarding, through the state reset, to the lock loop.

---

## Chronological Journey Map

```
2026-05-29 15:26:44 (Successful Onboarding & Chat)
  Login via Google Auth
   ↓
  Resolve/Create user row in careerloop.users
   ↓
  Complete Onboarding → State = PROFILE_READY
   ↓
  Active conversational chat inside Conversation 8712ee6d-0145-443f-b388-9829f65261f3
   ↓
  User reconnects later in Conversation ab7798b6-46de-4d13-827a-6c5f928043de (greetings work)

2026-05-30 09:41:16 (The State Reset & Lookup Failure)
  User row onboarding_complete is reset to False (or truncated via test)
   ↓
  User reconnects in Conversation 8105df4c-7dbf-4d99-bdc0-a5deb17d0e8e
   ↓
  Session state hydrated as NEW_USER, step = 10 (STEP_IDENTIFYING)
   ↓
  User sends "hello"
   ↓
  Routed to _handle_identifying → SerpAPI searches "hello" on LinkedIn (fails)
   ↓
  Onboarding step mutated to 1 (STEP_WAITING_CV) and saved in database

2026-05-30 10:24:40 (The Double-Lock CV Loop)
  User reconnects in new Conversation f337f33a-6e80-442d-a9cd-20a44a9d2764
   ↓
  User sends greeting "hello"
   ↓
  Session hydrated as NEW_USER, step = 1 (STEP_WAITING_CV)
   ↓
  Routed directly to _handle_waiting_cv
   ↓
  len("hello") = 5 < 80 chars → early exit with "Too short to be a full CV"
   ↓
  User sends "do you even know my name" (len = 24 < 80) → "Too short..."
   ↓
  User sends "wtf" (len = 3 < 80) → "Too short..." (Locked in loop)
```

---

## In-Depth Phase Breakdown

### Phase 1: Successful Onboarding & Active Chat (2026-05-29)
1. **Login:** Siddharth logs in. Google Auth returns his email and sets the canonical user ID `730d5bab-2587-4507-a16a-70cd662d59c2`.
2. **Onboarding Complete:** The user goes through the onboarding flow. They paste a valid CV and confirm all profile fields.
3. **Database Commits:** The system executes `_complete_onboarding` which updates `careerloop.users`:
   - `onboarding_complete = TRUE`
   - `onboarding_status = 'complete'`
   - `master_cv_markdown` is stashed.
   - `state` in `careerloop.sessions` becomes `PROFILE_READY` (step 0).
4. **General Chat:** Conversation `8712ee6d-0145-443f-b388-9829f65261f3` is opened. Siddharth tests the bot:
   - User: `"Help"` → Bot renders active matches menu.
   - User: `"hi"` → Bot: *"Hey Siddharth! Welcome back."*
   - User: `"bro you are working..."` → Bot: *"Haha, appreciate you testing me out..."*
5. **Re-entry Greeting:** User opens Conversation `ab7798b6-46de-4d13-827a-6c5f928043de`:
   - User: `"hello"` → Bot: *"Hey there! Ready to dive back in?"* (Greetings work because session state is `PROFILE_READY`).

---

### Phase 2: State Reset & LinkedIn Lookup Failure (2026-05-30 09:41:16)
1. **The Reset:** A background event (e.g. database schema migrations, test suites executing, or system administrative cleaning) truncates/resets the user spine:
   - `onboarding_complete` is set to `False`.
   - `onboarding_status` is reset to `'new'`.
   - `master_cv_markdown` is deleted.
2. **The Re-connection:** Siddharth connects and starts a new conversation (`8105df4c-7dbf-4d99-bdc0-a5deb17d0e8e`).
3. **Hydration:** The session hydrates as `state = NEW_USER` and `onboarding_step = 10` (`STEP_IDENTIFYING`).
4. **The Search Failure:** Siddharth sends a greeting: `"hello"`.
   - Because `onboarding_step` is 10, `"hello"` is routed directly to `_handle_identifying`.
   - The engine interprets `"hello"` as the user's name and runs a SerpAPI LinkedIn search on the search query `"hello"`.
   - The search yields no confident match.
   - The engine exits:
     - Mutates `session.onboarding_step = STEP_WAITING_CV` (1).
     - **Database Write:** Calls `self._save(session)` which saves `onboarding_step = 1` in `careerloop.sessions`.
     - Returns: *"I couldn't find a confident LinkedIn match for hello. No problem — please paste your CV/resume..."*.

---

### Phase 3: The Infinite CV Lock Loop (2026-05-30 10:24:40)
1. **The New Conversation:** Siddharth opens a new chat container (`f337f33a-6e80-442d-a9cd-20a44a9d2764`).
2. **Hydration:** The chat service hydrates his session from `careerloop.sessions`:
   - `state = UserJourneyState.NEW_USER`
   - `onboarding_step = 1` (`STEP_WAITING_CV`)
3. **The First Message:** Siddharth sends a simple greeting: `"hello"`.
   - Because `onboarding_step` is 1, the dispatcher routes `"hello"` directly to `_handle_waiting_cv`.
   - The character length guard evaluates: `len("hello".strip()) = 5 < 80`.
   - It exits early, returning: *"That looks too short to be a full CV..."*.
   - **Critical Fault:** It exits without saving or mutating the step, leaving `onboarding_step = 1` in the database.
4. **The Loop Lock:**
   - Siddharth, confused by the CV warning, asks: `"do you even know my name"` ($L = 24 < 80$).
   - The dispatcher routes again to `_handle_waiting_cv`. The length guard returns True, returning *"That looks too short..."*.
   - Siddharth types `"wtf"` ($L = 3 < 80$).
   - It routes again to `_handle_waiting_cv`, length guard returns True, returning *"That looks too short..."*.
   - The loop lock is established and will repeat indefinitely.
