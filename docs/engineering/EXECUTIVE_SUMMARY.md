# CAREERLOOP FORENSIC ONBOARDING AUDIT: EXECUTIVE SUMMARY

**Target User:** Siddharth Saminathan ([siddharth.swami99@gmail.com](mailto:siddharth.swami99@gmail.com))
**System User ID:** `730d5bab-2587-4507-a16a-70cd662d59c2`
**Audit Date:** 2026-05-30
**Lead Engineer:** Principle Backend Reliability Engineer

This document concludes the forensic audit of the onboarding system, state machine, and routing services. It compiles all observations, proves the root cause of the CV collection loop trap, and outlines the minimal, surgical backend fixes required.

---

## 1. Summary of Forensic Findings

We have generated and verified the following forensic audit reports inside the repository workspace:
1. [docs/engineering/USER_STATE_AUDIT.md](file:///Users/siddharthsaminathan/projects/CareerLoop/docs/engineering/USER_STATE_AUDIT.md) — exact live PostgreSQL/Supabase database tables, columns, and message logs for Siddharth.
2. [docs/engineering/ONBOARDING_STATE_MACHINE.md](file:///Users/siddharthsaminathan/projects/CareerLoop/docs/engineering/ONBOARDING_STATE_MACHINE.md) — states, entry/exit guards, mutations, and source code locations.
3. [docs/engineering/MESSAGE_ROUTING_AUDIT.md](file:///Users/siddharthsaminathan/projects/CareerLoop/docs/engineering/MESSAGE_ROUTING_AUDIT.md) — step-by-step routing trace for input `"wtf"` from HTTP ingress to database log.
4. [docs/engineering/CV_LOOP_ROOT_CAUSE.md](file:///Users/siddharthsaminathan/projects/CareerLoop/docs/engineering/CV_LOOP_ROOT_CAUSE.md) — mathematical/logical proof of the loop lock.
5. [docs/engineering/CONVERSATION_AUDIT.md](file:///Users/siddharthsaminathan/projects/CareerLoop/docs/engineering/CONVERSATION_AUDIT.md) — conversation history listings and proof of shared state containers.
6. [docs/engineering/JOURNEY_RECONSTRUCTION.md](file:///Users/siddharthsaminathan/projects/CareerLoop/docs/engineering/JOURNEY_RECONSTRUCTION.md) — chronological step reconstruction of Siddharth's account.
7. [docs/engineering/SYSTEM_ORCHESTRATION.md](file:///Users/siddharthsaminathan/projects/CareerLoop/docs/engineering/SYSTEM_ORCHESTRATION.md) — complete system architecture Mermaid diagram and state ownership.

---

## 2. Answers to the 8 Core Questions

### Q1: Why is onboarding stuck?
Onboarding is stuck because the user's persistent session in `careerloop.sessions` is locked in `state = NEW_USER` and `onboarding_step = 1` (`STEP_WAITING_CV`). While in this step, any incoming conversational message (e.g. greetings, questions like *"do you even know my name"*, or frustration like *"wtf"*) that is under 80 characters in length triggers a strict character length validation guard. This guard returns a static resume paste warning and exits early *without* updating the step or saving a new state, trapping the session in this handler indefinitely.

### Q2: Is DB state corrupted?
**No. The database state is not corrupted.**
The schema, foreign keys, indexes, and row values are relationally and syntactically 100% correct. The sessions and messages tables contain precisely the values that the backend code instructed them to write. The issue is a logical state orchestration defect, not DB corruption.

### Q3: Is conversation state corrupted?
**No. The conversation state is not corrupted.**
The chat history successfully persists each user turn and assistant reply in sequence, tied to the correct `conversation_id` and `user_id`. The logs retrieved from the live database match the UI logs perfectly.

### Q4: Is onboarding state corrupted?
**No, the onboarding state is not physically corrupted, but it is logically trapped.**
The user's session step was mutated to `1` (`STEP_WAITING_CV`) during a previous lookup sequence in Conversation `8105df4c-7dbf-4d99-bdc0-a5deb17d0e8e`. Because the first message was the greeting `"hello"` when the step was `10` (`STEP_IDENTIFYING`), the engine executed a LinkedIn lookup on the string `"hello"`. The search yielded no match, which successfully and permanently mutated the persistent database step to `1`.

### Q5: Is the frontend causing it?
**No. The frontend is not causing this.**
The React application behaves exactly as designed: it authenticates the user, retrieves the JWT, and posts the text to `/v1/chat/message` along with the active `conversation_id`, then renders the resulting string. It has no control over journey routing, state hydration, or guard evaluations.

### Q6: Is the backend causing it?
**Yes. The backend is 100% responsible for this lock due to two logical oversights:**
1. **User-scoped Onboarding State Persistence:** On onboarding initialization, state is hydrated from `careerloop.sessions` using the `user_id`. When a user starts a new conversation (generating a new `conversation_id`), the backend does *not* reset their onboarding progress to `0` (`STEP_IDLE`). The new conversation inherits the trapped step `1` from their previous session.
2. **Missing Conversational Escape Hatch & Stateless Exit:** The `STEP_WAITING_CV` handler in `onboarding_flow.py` contains a length guard that rejects any message under 80 characters. Because there is no check for general conversational greetings or commands, and because the guard exits early without updating the step, it established the loop lock.

### Q7: What is the exact root cause?
The exact root cause is the **absence of a conversational fallback inside the `STEP_WAITING_CV` length guard, combined with user-scoped onboarding session persistence.**
A prior failed LinkedIn lookup on the greeting `"hello"` permanently saved the user's `onboarding_step` as `1` in PostgreSQL. When the user initiated a new conversation, the chat service hydrated step `1`. Any subsequent greeting or question sent by the user fell under 80 characters, evaluating the length guard to True, returning the CV warning, and exiting without saving, locking the session.
*(Secondary Bug: A latent Python `NameError` exists in `_handle_idle` line 91, where the variable `cleaned` is referenced before definition, which crashes the engine if a new user session enters state 0).*

### Q8: What are the minimum fixes required?
Only **three minimal, high-impact edits** are required in `careerloop/onboarding/onboarding_flow.py` to restore state consistency:

1. **Fix NameError in `_handle_idle`:**
   Add `cleaned = text.strip()` at the start of `_handle_idle` so the variable is bound.
2. **Add a Conversational Escape Hatch inside `_handle_waiting_cv`:**
   Before throwing the length validation error, check if the user is sending standard conversational words (greetings, name checks, etc.). If so, respond in conversational language explaining that we are setting up their profile and prompt for a CV, or allow them to exit/reset by typing `"skip"`.
3. **Implement a `"reset"` Command in the Router Dispatcher:**
   Add a conversational command (e.g. `"reset"`, `"start over"`) to `OnboardingFlow::handle_message` that manually resets `session.onboarding_step = STEP_IDLE` (0) and saves the session, giving the user a guaranteed manual escape hatch.

---

## 3. Recommended Code Patches (For Implementation Phase)

For safety, the following patches should be applied to `careerloop/onboarding/onboarding_flow.py` when implementation is re-enabled:

### Patch A: Fix NameError in `_handle_idle`
```python
    def _handle_idle(self, session: Session, text: str = "") -> Tuple[str, UserJourneyState]:
        cleaned = text.strip()  # Fix NameError by binding 'cleaned'
        conv_id = (session.temp_profile_data or {}).get("_active_conversation_id")
        ...
```

### Patch B: Reset Command in `handle_message`
```python
    def handle_message(self, session: Session, text: str) -> Tuple[str, UserJourneyState]:
        ...
        cleaned = text.strip().lower()
        if cleaned in {"reset", "restart", "start over"}:
            session.onboarding_step = STEP_IDLE
            session.temp_profile_data = {}
            self._save(session)
            return "Onboarding has been reset! What's your full name to get started?", UserJourneyState.NEW_USER
        ...
```

### Patch C: Escape Hatch in `_handle_waiting_cv`
```python
        if len(text.strip()) < 80:
            char_count = len(text.strip())
            # Add conversational greetings escape to prevent cold loops
            greetings = {"hi", "hello", "hey", "who are you", "what is this", "what is my name", "do you know my name", "wtf"}
            if text.strip().lower() in greetings:
                return (
                    "I am still waiting for your resume to get your profile set up! Please paste your complete CV text here "
                    "so I can analyze your target roles, or type **skip** to proceed using only your LinkedIn data.",
                    UserJourneyState.NEW_USER
                )
            ...
```

No code changes have been staged or committed, keeping this turn 100% read-only as requested. The audit is complete.
