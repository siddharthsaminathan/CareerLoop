# ROOT CAUSE ANALYSIS: THE ONBOARDING LOOP TRAP

**Target User ID:** `730d5bab-2587-4507-a16a-70cd662d59c2`
**Audit Date:** 2026-05-30

This document summarizes the root cause of the infinite onboarding loop, explaining exactly why the system is behaving as it is.

---

## 1. The Core Bug: Absence of Escape Hatch in WAITING_CV

The actual bug does NOT live in Supabase, React, JWT tokens, or dual state containers. It is entirely a **logical state orchestration deadlock** in the backend onboarding flow:

### Bug A: Typo/NameError in Idle Handler
In `_handle_idle` of `careerloop/onboarding/onboarding_flow.py` line 91:
```python
greetings = {"hi", "hello", "hey", "/start", "start", "hi!", "hello!", "hey!", "yo", "yo!"}
if cleaned and len(cleaned) < 80 and cleaned.lower() not in greetings:
    session.onboarding_step = STEP_IDENTIFYING
    self._save(session)
    return self._handle_identifying(session, cleaned, {})
```
* **Fault:** `cleaned` is used on line 91 and 94, but **it is never defined inside `_handle_idle`**! It is a Python `NameError` crash path.
* **Why it didn't crash in some tests:** If `text` is passed and `text.strip()` was expected, other files may have bypassed it or it only crashed when a non-greeting name was sent under 80 characters.

### Bug B: The Lookup Misinterpretation
When the user sent `"hello"`, the step was `10` (`STEP_IDENTIFYING`) due to bootstrapping or prior test runs. The engine ran a LinkedIn lookup on `"hello"`. Since it yielded no match, it transitioned the user to `STEP_WAITING_CV` (1).

### Bug C: No Escape Hatch in CV Character Limit
In `_handle_waiting_cv` line 120-127:
```python
if len(text.strip()) < 80:
    char_count = len(text.strip())
    return (
        f"I am currently waiting for your CV...",
        UserJourneyState.NEW_USER,
    )
```
* **Fault:** If the user sends a message that is not a CV (e.g. `"wtf"`, `"do you know my name"` or greetings), and the length is less than 80 characters:
  1. The length guard catches the input.
  2. It returns the static CV warning.
  3. **It exits early without calling `self._save(session)`.**
  4. The onboarding step is never mutated, remaining permanently at `1`.
  5. The session state is never mutated, remaining permanently at `NEW_USER`.
  6. The user is locked in an infinite state loop.

---

## 2. Why Starting a New Chat Did Not Clear It

1. **Onboarding State is User-scoped:** `SessionStore::get_session` loads from `careerloop.sessions` using `user_id`, not `conversation_id`.
2. **Inherited State:** When a new conversation was opened, the chat service hydrated the same session showing `onboarding_step = 1`.
3. **No Bootstrapping Reset:** Since the step was already `1`, the new conversation's greeting `"hello"` bypassed the idle handler and went straight to `_handle_waiting_cv`. Since $L(	ext{"hello"}) = 5 < 80$, the loop locked immediately.
