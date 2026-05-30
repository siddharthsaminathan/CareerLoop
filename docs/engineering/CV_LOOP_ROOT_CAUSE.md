# CV UPLOAD LOOP ROOT CAUSE ANALYSIS

**Target User ID:** `730d5bab-2587-4507-a16a-70cd662d59c2`
**Active Step in DB:** `1` (`STEP_WAITING_CV`)
**Audit Date:** 2026-05-30

This document evaluates the six potential causes of the persistent CV collection loop and mathematically proves which one is the true root cause.

---

## 1. Analysis of Proposed Causes

| Cause Option | Description | Audit Status | Evidence / Analysis |
|---|---|---|---|
| **A. State never changes** | The state machine logic does not transition the state on short messages. | **TRUE (CORE CAUSE)** | Inside `_handle_waiting_cv`, inputs under 80 characters trigger an early exit returning `UserJourneyState.NEW_USER` and step `1` directly without calling `self._save(session)`. |
| **B. Reload restores old state** | Database persistence is failing, or reloading forces a roll-back to cached state. | **FALSE** | Database writes are successful and read back cleanly from PostgreSQL on startup. The issue persists across multiple active conversation IDs because the state is *correctly* persisted in the DB as `onboarding_step = 1`. |
| **C. Frontend sends wrong session** | The client passes a mismatched session header, bypassing authentication boundaries. | **FALSE** | The frontend makes requests using the correct Supabase JWT, resolving to Siddharth's canonical system user ID `730d5bab-2587-4507-a16a-70cd662d59c2`. |
| **D. Conversation ID mismatch** | State is bound to Conversation ID, and starting a new conversation isolates it from the session state. | **FALSE** | The onboarding state machine is bound strictly to `user_id` inside `careerloop.sessions`, making it independent of `conversation_id`. Regardless of conversation context, it hydrates the same user session. |
| **E. Onboarding bootstrap bug** | The initial bootstrapping logic sets the user to `STEP_WAITING_CV` on registration. | **FALSE** | The database defaults `onboarding_step` to `0` (`STEP_IDLE`). The transition to `STEP_WAITING_CV` (1) occurred dynamically due to a prior interaction. |
| **F. DB already contains partial onboarding** | The persistent session store contains `onboarding_step = 1` from a prior failed lookup. | **TRUE (CORE CAUSE)** | The user's previous conversation (`8105df4c-7dbf-4d99-bdc0-a5deb17d0e8e`) processed the greeting `"hello"` as a candidate name. The SerpAPI lookup yielded no match, which successfully and permanently mutated the step to `1` (`STEP_WAITING_CV`). |

---

## 2. The Formal Logical Proof

Let $S$ represent the state tuple $(\text{state}, \text{step})$ of the onboarding session, where:
- $\text{state} \in \{ \text{NEW\_USER}, \text{PROFILE\_READY} \}$
- $\text{step} \in \{ 0 \text{ (IDLE)}, 1 \text{ (WAITING\_CV)}, 2 \text{ (CONFIRMING)}, 3 \text{ (COLLECTING)}, 10 \text{ (IDENTIFYING)} \}$

Let $I$ represent the user input string, and $L(I) = \text{len}(I\text{.strip()})$ represent its length.

### Theorem
*If the session state is $S_t = (\text{NEW\_USER}, 1)$, then any subsequent message $I$ with length $L(I) < 80$ that does not belong to the command set $C = \{ \text{"skip"}, \text{"no"}, \text{"later"} \}$ will result in a state transition $S_{t+1} = S_t$. This locks the session in an infinite loop.*

### Mathematical Proof

1. **Hydration Phase:**
   When a user sends message $I$, `ChatService::message` hydrates the session from `careerloop.sessions` for the authenticated `user_id`.
   $$\text{Since } S_t = (\text{NEW\_USER}, 1) \implies \text{step} = 1$$

2. **Dispatcher Routing:**
   `OnboardingFlow::handle_message` executes the step router:
   $$\text{Since } \text{step} = 1 \implies \text{Route to } \text{OnboardingFlow::\_handle\_waiting\_cv}(session, I, data)$$

3. **Guard Evaluation inside `_handle_waiting_cv`:**
   - **Guard 1 (Conversational Commands):**
     $$\text{Check if } I\text{.lower().strip()} \in C$$
     $$\text{Since } I \notin C \implies \text{Guard 1 evaluates to False. Execution continues.}$$
   - **Guard 2 (CV Character Length Limit):**
     $$\text{Check if } L(I) < 80$$
     $$\text{Since } L(I) < 80 \implies \text{Guard 2 evaluates to True.}$$

4. **Early Termination:**
   When Guard 2 is True, the code executes the following early exit:
   ```python
   return (
       f"I am currently waiting for your CV...",
       UserJourneyState.NEW_USER,
   )
   ```
   During this branch:
   - **No session database write occurs:** The `self._save(session)` routine is completely bypassed.
   - **No step modification occurs:** The variable `session.onboarding_step` remains `1`.
   - **No state modification occurs:** The variable `session.state` remains `NEW_USER`.

5. **Post-Evaluation State:**
   The session remains unchanged in memory and PostgreSQL:
   $$S_{t+1} = (\text{NEW\_USER}, 1) = S_t$$

6. **Inductive Step:**
   For any message sequence $\{I_1, I_2, \dots, I_n\}$ where $\forall k, L(I_k) < 80$ and $I_k \notin C$:
   $$S_{t+n} = S_{t+n-1} = \dots = S_t = (\text{NEW\_USER}, 1)$$
   The user is locked in an infinite state loop. $\blacksquare$

---

## 3. The Double-Lock Scenario (Why Starting a New Chat Doesn't Help)

When the user opens a new chat tab or reboots the CLI:
1. The client generates a new active `conversation_id = "f337f33a-6e80-442d-a9cd-20a44a9d2764"`.
2. The user sends a greeting like `"hello"` ($L(I) = 5 < 80$).
3. **Hydration from the canonical spine:** `ChatService::message` fetches from `careerloop.sessions` using the authenticated `user_id`. It hydrates `onboarding_step = 1`, not `0` (step is stored per user, not per conversation).
4. Because the step is already `1`, the greeting `"hello"` does **not** get routed to `_handle_idle` to say *"Welcome to CareerLoop! What's your name?"*.
5. Instead, `"hello"` is passed directly to `_handle_waiting_cv`.
6. Since $L(\text{"hello"}) = 5 < 80$, the length guard evaluates to True, and the assistant responds with: *"That looks too short to be a full CV..."*.
7. The user is confused because a simple greeting triggered a CV error, responds with `"wtf"` or `"do you even know my name"`, both of which are under 80 characters, locking them in the loop.
