# ONBOARDING STATE STABILIZATION: INTEGRATION FIX PLAN

This document outlines the step-by-step, surgical code modifications required inside `careerloop/onboarding/onboarding_flow.py` to restore E2E reliability and resolve the loop lock.

> [!IMPORTANT]
> **NO IMPLEMENTATION IS APPLIED YET.**
> This document serves as a verified blueprints guide.

---

## Part 1: Required Surgical Code Changes

### 1. Fix the NameError in `_handle_idle`
* **File:** `careerloop/onboarding/onboarding_flow.py`
* **Coordinate:** Line 86 (start of `_handle_idle`)
* **Patch:** Define the `cleaned` variable safely from the incoming `text` parameter.

```diff
     def _handle_idle(self, session: Session, text: str = "") -> Tuple[str, UserJourneyState]:
+        cleaned = text.strip()
         conv_id = (session.temp_profile_data or {}).get("_active_conversation_id")
```

---

### 2. Implement a Conversational Escape Hatch in `_handle_waiting_cv`
* **File:** `careerloop/onboarding/onboarding_flow.py`
* **Coordinate:** Line 120 (start of character limit guard)
* **Patch:** Check for standard greetings or conversational phrases *before* throwing the resume paste error. If detected, respond with conversational guidance rather than a strict formatting error.

```diff
         if len(text.strip()) < 80:
             char_count = len(text.strip())
+            # Conversational greetings filter
+            greetings = {"hi", "hello", "hey", "who are you", "what is this", "what is my name", "do you know my name", "wtf"}
+            if text.strip().lower() in greetings:
+                return (
+                    "I am still waiting for your resume to get your profile set up! Please paste your complete CV text here "
+                    "so I can analyze your target roles, or type **skip** to proceed using only your LinkedIn data.",
+                    UserJourneyState.NEW_USER
+                )
             return (
                 f"I am currently waiting for your CV or resume text so I can build your professional profile.

"
```

---

### 3. Implement a Universal Reset Command
* **File:** `careerloop/onboarding/onboarding_flow.py`
* **Coordinate:** Line 57 (start of `handle_message` router dispatcher)
* **Patch:** If a user types `"reset"` or `"restart"`, clear their onboarding session state to `STEP_IDLE` (0) and clear `temp_profile_data` to give them a guaranteed conversational manual escape hatch.

```diff
     def handle_message(self, session: Session, text: str) -> Tuple[str, UserJourneyState]:
         state  = session.state
         step   = session.onboarding_step
         data   = session.temp_profile_data or {}
 
+        # Universal restart command to escape any stuck step
+        cleaned = text.strip().lower()
+        if cleaned in {"reset", "restart", "start over"}:
+            session.onboarding_step = STEP_IDLE
+            session.temp_profile_data = {}
+            self._save(session)
+            return (
+                "Onboarding has been reset! What's your full name to get started?",
+                UserJourneyState.NEW_USER
+            )
+
         if state == UserJourneyState.PROFILE_READY:
```

---

## Part 2: E2E Functional Validation Plan

Once the patches are applied, we will execute functional verification:
1. **Direct Session Reset Check:** Issue a `reset` message in chat and assert the DB state resets to `0` (`STEP_IDLE`).
2. **Greeting Resilience Check:** Send `"hello"` as a brand new user and assert it successfully returns: *"What's your full name?"* instead of the CV validation error.
3. **LinkedIn Graceful Fallback Check:** Send a greeting, receive name prompt, answer `"hello"` (interpret name), and assert it responds with the SerpAPI fallback error message.
4. **CV Extraction Integrity Check:** Paste Priya's E2E resume text and assert the step successfully advances to `STEP_CONFIRMING` (2) with complete profile stashes.
