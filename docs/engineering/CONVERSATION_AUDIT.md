# CONVERSATION STATE FORENSIC AUDIT

**Target User ID:** `730d5bab-2587-4507-a16a-70cd662d59c2`
**Audit Date:** 2026-05-30

This document audits the active conversations and history for Siddharth, analyzing whether the onboarding state and normal chat share a state container, and presenting database-backed proof.

---

## 1. Active Conversations Listing

Database query on `careerloop.conversations` resolves **four** unique conversation IDs for this user:

| Conversation ID | Transport | Status | Created At | Associated Message Types |
|---|---|---|---|---|
| **`f337f33a-6e80-442d-a9cd-20a44a9d2764`** | `cli` | `active` | 2026-05-30 10:24:40 | Onboarding CV-First Trap Messages (`wtf`, `do you even know my name`) |
| **`8105df4c-7dbf-4d99-bdc0-a5deb17d0e8e`** | `cli` | `active` | 2026-05-30 09:41:16 | Onboarding Lookup Transition (`hello` → SerpAPI Lookup Fails → `STEP_WAITING_CV`) |
| **`ab7798b6-46de-4d13-827a-6c5f928043de`** | `cli` | `active` | 2026-05-29 18:32:44 | Post-Onboarding General Greeting (`hello` → `PROFILE_READY` response) |
| **`8712ee6d-0145-443f-b388-9829f65261f3`** | `cli` | `active` | 2026-05-29 15:26:44 | Post-Onboarding Conversational Chat (General supervisor/graph execution) |

---

## 2. Conversational Message History Analysis

### Onboarding Conversations
* **`8105df4c-7dbf-4d99-bdc0-a5deb17d0e8e`** (Greeting Lookup failure):
  - **User:** `"hello"`
  - **Assistant:** `"I couldn't find a confident LinkedIn match for hello. No problem — please paste your CV/resume..."`
* **`f337f33a-6e80-442d-a9cd-20a44a9d2764`** (CV Lock Loop):
  - **User:** `"hello"` → **Assistant:** *"That looks too short to be a full CV..."* (Triggered because step was already 1)
  - **User:** `"do you even know my name"` → **Assistant:** *"That looks too short to be a full CV..."*
  - **User:** `"wtf"` → **Assistant:** *"That looks too short to be a full CV..."*

### Normal Chat Conversations (Historical - `PROFILE_READY` state)
* **`8712ee6d-0145-443f-b388-9829f65261f3`** (Active chat before the state reset):
  - **User:** `"Help"` → **Assistant:** Menu card rendered (*"Today's matches..."*).
  - **User:** `"hi"` → **Assistant:** *"Hey Siddharth! Welcome back..."*
  - **User:** `"bro you are working ha good bro..."` → **Assistant:** *"Haha, I appreciate you putting in the effort..."*
  - **User:** `"yes sir"` → **Assistant:** *"Haha, you're the boss!..."*

---

## 3. Proven State Container Sharing

### Finding
**Yes. Onboarding and general chat share the exact same physical and logical state container in the database.**

### Database Evidence
1. **The Session Table definition (`supabase_schema.sql#L40-L53`):**
   ```sql
   CREATE TABLE IF NOT EXISTS careerloop.sessions (
       user_id UUID PRIMARY KEY REFERENCES careerloop.users(id) ON DELETE CASCADE,
       state TEXT NOT NULL DEFAULT 'NEW_USER',
       current_job_id TEXT,
       onboarding_step INTEGER DEFAULT 0,
       temp_profile_data JSONB,
       ...
   );
   ```
   The primary key is strictly `user_id`. There is no `conversation_id` in this table. This means only one session state exists per user.

2. **Session Hydration Logic (`session_store.py#L149-L160`):**
   ```python
   def get_session(self, user_id: str) -> Session:
       ...
       cursor.execute(
           f"SELECT state, current_job_id, onboarding_step, temp_profile_data, ... "
           f"FROM {self._tbl('sessions')} WHERE user_id = %s",
           (user_id,)
       )
   ```
   The state container hydrates using the user's ID, bypassing the active HTTP `conversation_id`.

3. **Message Service Routing (`chat_service.py#L71-L89`):**
   ```python
   def message(self, user_id: str, text: str) -> dict:
       ...
       session = self.store.get_session(user_id) # Hydrates from same sessions table
       conv_id = self._ensure_conversation(user_id) # Resolves active conversation ID
       
       # Saves to conversation-scoped messages table
       self.store.save_message(user_id, conv_id, role="user", content=text) 
       
       if session.state == UserJourneyState.NEW_USER:
           # Routes to onboarding flow using same session state container
           flow = OnboardingFlow(self.store)
           ...
   ```

### Operational Consequences of Sharing

Because they share the same state container:
* **The Onboarding Engine Intercepts All Messages:** If `session.state` is `NEW_USER`, the chat service intercepts the message on line 88 and routes it directly to the onboarding flow. The LangGraph supervisor checkpointer and LLM agent pool are never invoked.
* **New Conversation IDs Do Not Reset State:** Starting a new chat assigns a new `conversation_id` in `careerloop.conversations` and logs messages under that ID in `careerloop.messages`. However, `self.store.get_session(user_id)` still retrieves the same user session showing `state = NEW_USER` and `onboarding_step = 1`.
* **Permanent Deadlock:** Any incoming message in the new conversation goes to `OnboardingFlow::handle_message` while `onboarding_step` is 1. If it's less than 80 characters, it triggers the validation error and stays in step 1, leaving the user locked in the loop across all past, present, and future conversations.
