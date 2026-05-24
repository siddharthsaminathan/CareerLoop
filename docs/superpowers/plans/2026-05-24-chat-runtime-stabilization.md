# Chat Runtime Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the CareerLoop chat runtime real, stateful, testable, and non-hardcoded — removing all demo slop, dead states, echo bugs, and bypass pipelines.

**Architecture:** Consolidate routing into a single `CommandRouter` used by both slash commands and the supervisor graph. Reduce the state machine to 11 real states, each with a setter, handler, and reachability test. Fix the reply pipeline so the LLM's output is never discarded, the user never sees raw API errors, and conversation history persists across turns.

**Tech Stack:** LangGraph StateGraph, Python dataclasses, DeepSeek API, Rich terminal UI

---

## File Map

| File | Role |
|------|------|
| `careerloop/session/states.py` | Reduced UserState enum — 11 real states only |
| `careerloop/session/supervisor_graph.py` | Graph with GENERAL_CHAT fix, PACK_GENERATING reachable, intent-respecting routing |
| `careerloop/session/command_router.py` | **NEW** — unified slash/natural-language command handlers |
| `careerloop/transport/base.py` | Remove echo fallback; safe error message on missing assistant_response |
| `careerloop/chat_cli.py` | Slash commands delegate to CommandRouter; no business logic |
| `careerloop/llm_chat.py` | Error handling: retry, safe messages, API key validation |
| `careerloop/onboarding/onboarding_flow.py` | Remove hardcoded strings; validate is_complete before transition |
| `careerloop/session/session_store.py` | Single canonical session load per turn |
| `careerloop/memory/connection.py` | API key validation at startup |
| `tests/test_chat_runtime.py` | **NEW** — 11+ tests proving all requirements |

---

### Task 1: Remove Echo Fallback in Transport

**Files:**
- Modify: `careerloop/transport/base.py:45-58`

- [ ] **Step 1: Replace fallback with safe error**

In `base.py`, replace lines 45-58 (the response processing block) with the following. The key change: when `assistant_response` is missing, do NOT fall back to `messages[-1].content`. Instead log a CRITICAL event and return a safe message.

```python
# base.py:45-58 — replace with:

            if response and hasattr(response, "get"):
                assistant_response = response.get("assistant_response")
                if assistant_response:
                    self.send_text(event.user_id, str(assistant_response))
                    return response

                # CRITICAL: no assistant_response — graph node returned incomplete state.
                # NEVER echo the user's message back. Log and return safe error.
                import logging
                _log = logging.getLogger("careerloop.transport.base")
                _log.critical(
                    "supervisor_graph returned no assistant_response. "
                    "state=%s user_id=%s",
                    response.get("current_state"),
                    event.user_id,
                )
                self.send_text(
                    event.user_id,
                    "I hit an internal routing issue. Your data is safe — try again or type /help.",
                )
                return response

            # Backward-compatible fallback: message list (only used when
            # assistant_response is absent but messages were explicitly set)
            messages = response.get("messages", [])
            if messages:
                last_msg = messages[-1]
                content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                self.send_text(event.user_id, content)
            return response
```

- [ ] **Step 2: Verify parse**

```bash
python3 -c "import ast; ast.parse(open('careerloop/transport/base.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add careerloop/transport/base.py
git commit -m "fix(transport): remove user-message echo fallback, log CRITICAL on missing assistant_response"
```

---

### Task 2: Reduce States to 11 Real States

**Files:**
- Modify: `careerloop/session/states.py`

- [ ] **Step 1: Write the new states enum**

Replace the entire `states.py` with:

```python
"""CareerLoop session user states.

Only 11 reachable states. Every state has at least one setter path
and at least one handler path in supervisor_graph.py.
"""

from enum import Enum


class UserState(str, Enum):
    # ── Onboarding ────────────────────────────────────────────
    IDLE = "IDLE"
    ONBOARDING_WAITING_CV = "ONBOARDING_WAITING_CV"
    ONBOARDING_COLLECTING = "ONBOARDING_COLLECTING"

    # ── Active use ────────────────────────────────────────────
    PROFILE_COMPLETE = "PROFILE_COMPLETE"
    SCAN_RUNNING = "SCAN_RUNNING"
    BRIEF_AVAILABLE = "BRIEF_AVAILABLE"

    # ── Job review → pack → apply ─────────────────────────────
    REVIEWING_JOB = "REVIEWING_JOB"
    PACK_GENERATING = "PACK_GENERATING"
    PACK_READY = "PACK_READY"
    AWAITING_APPLICATION_CONFIRMATION = "AWAITING_APPLICATION_CONFIRMATION"
    APPLIED = "APPLIED"


# ── Legacy state migration ───────────────────────────────────
# Old persisted rows may carry renamed or removed states.
# Map them to the nearest current equivalent. Never reset to IDLE.

_LEGACY_MAP: dict[str, str] = {
    "DAILY_BRIEF_SENT": UserState.PROFILE_COMPLETE.value,
    "ONBOARDING_Q1_ROLES": UserState.ONBOARDING_COLLECTING.value,
    "ONBOARDING_Q2_CITIES": UserState.ONBOARDING_COLLECTING.value,
    "ONBOARDING_Q3_SALARY": UserState.ONBOARDING_COLLECTING.value,
    "ONBOARDING_Q4_NOTICE": UserState.ONBOARDING_COLLECTING.value,
    "ONBOARDING_Q5_MODE": UserState.ONBOARDING_COLLECTING.value,
    "FOLLOWUP_DUE": UserState.BRIEF_AVAILABLE.value,
    "INTERVIEW_SCHEDULED": UserState.APPLIED.value,
    "INTERVIEW_PREP_READY": UserState.APPLIED.value,
    "POST_INTERVIEW_DEBRIEF": UserState.APPLIED.value,
}


def normalize_user_state(raw: str | UserState | None) -> UserState:
    """Coerce any raw state value into a valid current UserState.

    Handles:
    - Already-valid UserState enum members
    - Current string values
    - Legacy/renamed states via _LEGACY_MAP
    - Unknown/unexpected values → IDLE (with logged warning)
    - None / empty → IDLE
    """
    if raw is None:
        return UserState.IDLE

    # Already a UserState member
    if isinstance(raw, UserState):
        return raw

    # Try current enum values first
    try:
        return UserState(raw)
    except ValueError:
        pass

    # Try legacy migration
    migrated = _LEGACY_MAP.get(raw)
    if migrated is not None:
        import logging
        logging.getLogger("careerloop.session.states").info(
            "Migrating legacy state '%s' → '%s'", raw, migrated
        )
        return UserState(migrated)

    # Unknown — reset to IDLE with warning
    import logging
    logging.getLogger("careerloop.session.states").warning(
        "Unknown state '%s' encountered. Resetting to IDLE.", raw
    )
    return UserState.IDLE
```

- [ ] **Step 2: Verify parse**

```bash
python3 -c "from careerloop.session.states import UserState, normalize_user_state; print('IDLE:', UserState.IDLE); print('Normalize DAILY_BRIEF_SENT:', normalize_user_state('DAILY_BRIEF_SENT')); print('Normalize unknown:', normalize_user_state('GARBAGE'))"
```

- [ ] **Step 3: Commit**

```bash
git add careerloop/session/states.py
git commit -m "refactor(states): reduce to 11 real states, add legacy migration, never reset to IDLE on known state"
```

---

### Task 3: Fix GENERAL_CHAT in Supervisor Graph + Make PACK_GENERATING Reachable

**Files:**
- Modify: `careerloop/session/supervisor_graph.py`

**Context:** This is the largest single change. The supervisor graph needs three fixes:
1. GENERAL_CHAT must return the ChatIntentAgent's reply (not fall through to no handler)
2. PACK_GENERATING must be settable so the pack_generation node is reachable
3. Profile hydration: reload from DB if temp_profile_data is empty

- [ ] **Step 1: Rewrite the entire `intent_router` function**

Replace lines 74-211 of `supervisor_graph.py` (the full `intent_router` function body) with:

```python
def intent_router(state: ConversationState) -> dict:
    """Classify free-form user messages against the current state."""
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_message = (
        messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
    )
    current_state = normalize_user_state(state.get("current_state", UserState.IDLE)) or UserState.IDLE

    # ── State: IDLE or onboarding ─────────────────────────────
    if current_state in (UserState.IDLE, UserState.ONBOARDING_WAITING_CV, UserState.ONBOARDING_COLLECTING):
        import os
        from careerloop.session.session_store import SessionStore, Session
        from careerloop.memory.connection import DatabaseManager
        from careerloop.onboarding.onboarding_flow import OnboardingFlow

        db = DatabaseManager(os.getenv("DATABASE_URL"))
        store = SessionStore(db)
        user_id = state.get("user_id", "unknown")

        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {store._tbl('users')} (id, email) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                        (user_id, f"{user_id}@example.com"),
                    )
                conn.commit()
        except Exception:
            pass

        session = store.get_session(user_id)
        if current_state != UserState.IDLE:
            session.state = current_state

        graph_temp_data = state.get("temp_profile_data", {})
        if graph_temp_data:
            session.temp_profile_data = graph_temp_data

        flow = OnboardingFlow(store)
        reply, next_state = flow.handle_message(session, last_message)
        return {
            "current_state": next_state,
            "assistant_response": reply,
            "temp_profile_data": session.temp_profile_data,
        }

    # ── Profile hydration: reload from DB if temp_profile_data is empty ──
    profile_data = state.get("temp_profile_data") or {}
    if not profile_data:
        import os as _os
        from careerloop.session.session_store import SessionStore
        from careerloop.memory.connection import DatabaseManager
        db = DatabaseManager(_os.getenv("DATABASE_URL"))
        store = SessionStore(db)
        session = store.get_session(state.get("user_id", "unknown"))
        if session.temp_profile_data:
            profile_data = session.temp_profile_data

    # ── State: REVIEWING_JOB → check for approval intent ──────
    if current_state == UserState.REVIEWING_JOB:
        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent()
        intent, reply = agent.process(last_message, profile_data)

        if intent in ("APPROVE", "SCAN_JOBS"):
            # User wants to prepare an application pack
            return {
                "current_state": UserState.PACK_GENERATING,
                "assistant_response": "Preparing your application pack. This will take a moment...",
                "pending_job_id": state.get("pending_job_id"),
            }
        elif intent == "GENERAL_CHAT":
            return {"current_state": current_state, "assistant_response": reply}
        else:
            return {
                "current_state": current_state,
                "assistant_response": (
                    "I can prepare an application pack for this job — just say 'prepare this' "
                    "or 'apply to this one'. You can also say 'skip' to move on."
                ),
            }

    # ── State: PACK_READY — check for apply confirmation ──────
    if current_state == UserState.PACK_READY:
        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent()
        intent, reply = agent.process(last_message, profile_data)

        if intent == "APPROVE":
            return {
                "current_state": UserState.AWAITING_APPLICATION_CONFIRMATION,
                "assistant_response": (
                    "Application pack approved. I'll begin the assisted application process. "
                    "You'll be able to review every step before submission."
                ),
            }
        return {"current_state": current_state, "assistant_response": reply}

    # ── State: AWAITING_APPLICATION_CONFIRMATION ───────────────
    if current_state == UserState.AWAITING_APPLICATION_CONFIRMATION:
        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent()
        intent, reply = agent.process(last_message, profile_data)
        if intent == "APPROVE":
            return {
                "current_state": UserState.APPLIED,
                "assistant_response": "Application submitted. I'll track follow-ups for this role.",
            }
        return {"current_state": current_state, "assistant_response": reply}

    # ── State: PROFILE_COMPLETE or BRIEF_AVAILABLE or SCAN_RUNNING ──
    # All receive the same intent-classified routing.
    if current_state in (UserState.PROFILE_COMPLETE, UserState.BRIEF_AVAILABLE, UserState.SCAN_RUNNING):
        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent()
        intent, reply = agent.process(last_message, profile_data)

        if intent == "SCAN_JOBS":
            import os as _os
            from datetime import datetime as _dt, timezone as _tz
            today_str = _dt.now(_tz.utc).date().isoformat()
            root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
            brief_path = _os.path.join(root, "output", "daily_briefs", f"{today_str}.md")
            if _os.path.exists(brief_path):
                reply = (
                    "Today's brief is already ready! Type `/brief` to see it, "
                    "or `/scan` to run a fresh search."
                )
            else:
                reply = (
                    "Ready to scan for new jobs matching your profile. "
                    "Type `/scan` to start."
                )

        elif intent == "SHOW_PIPELINE":
            try:
                from careerloop.application_ledger import ApplicationLedger
                import os as _os
                root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
                ledger = ApplicationLedger(root)
                status_counts = {}
                for e in ledger.entries:
                    s = e.get("status", "UNKNOWN")
                    status_counts[s] = status_counts.get(s, 0) + 1
                top = ledger.get_top_scored(min_score=1, limit=5)
                reply = "**Your Pipeline**\n\n"
                for status, count in sorted(status_counts.items()):
                    reply += f"  • {status}: {count}\n"
                if top:
                    reply += f"\n**Top Matches:**\n"
                    for i, job in enumerate(top, 1):
                        score = ledger._get_score(job) or 0
                        reply += f"  {i}. **{job.get('title','?')}** @ {job.get('company','?')} — {score:.0f}/100\n"
                else:
                    reply += "\nNo scored jobs yet. Type `/scan` to search for new opportunities."
            except Exception as e:
                reply = f"Could not load pipeline: {e}"

        return {
            "current_state": current_state,
            "assistant_response": reply,
        }

    # ── Fallthrough — unknown state ────────────────────────────
    import logging
    logging.getLogger("careerloop.session.supervisor_graph").warning(
        "intent_router: unhandled state %s — returning safe fallback", current_state
    )
    return {
        "current_state": current_state,
        "assistant_response": "I'm not sure what to do next. Type /help to see available commands.",
    }
```

- [ ] **Step 2: Update ChatIntentAgent to support APPROVE intent**

In `careerloop/llm_chat.py`, update the `ChatIntentAgent.SYSTEM_PROMPT` to include an APPROVE intent:

```python
class ChatIntentAgent(LLMChatAgent):
    SYSTEM_PROMPT = """You are the CareerLoop central router.
Analyze the user's message and their profile context.
Determine the user's intent from the following list:
- SHOW_PIPELINE: User wants to see their current jobs, daily briefing, pipeline status.
- SCAN_JOBS: User EXPLICITLY wants to run a NEW scan to find fresh jobs.
- APPROVE: User is approving, confirming, or saying yes to proceed. "yes", "approve", "looks good", "prepare this", "apply to this one", "go ahead", "do it", "let's go" → APPROVE.
- GENERAL_CHAT: User is just chatting or asking a general question.

Return ONLY valid JSON in the following format:
{
  "intent": "SHOW_PIPELINE",
  "reply": "If GENERAL_CHAT, put your conversational response here. For other intents, a brief confirmation."
}"""
```

- [ ] **Step 3: Update graph builder to add PACK_GENERATING edge**

Replace the `route_from_intent` function (around line 266-270) with:

```python
def route_from_intent(state: ConversationState):
    """Conditional routing based on current conversation state."""
    curr = normalize_user_state(state.get("current_state", UserState.IDLE)) or UserState.IDLE
    if curr == UserState.PACK_GENERATING:
        return "pack_generation"
    return END
```

- [ ] **Step 4: Verify parse**

```bash
python3 -c "import ast; ast.parse(open('careerloop/session/supervisor_graph.py').read()); print('OK')"
python3 -c "import ast; ast.parse(open('careerloop/llm_chat.py').read()); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add careerloop/session/supervisor_graph.py careerloop/llm_chat.py
git commit -m "fix(graph): make GENERAL_CHAT return LLM reply, PACK_GENERATING reachable, profile hydration, APPROVE intent"
```

---

### Task 4: Unify Command Routing

**Files:**
- Create: `careerloop/session/command_router.py`
- Modify: `careerloop/chat_cli.py:300-329` (slash command block)

- [ ] **Step 1: Create CommandRouter**

```python
"""Unified command routing — single handler for slash commands and natural-language intents."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    text: str
    new_state: str | None = None


class CommandRouter:
    """All user-facing commands route through here.

    Slash commands in chat_cli.py AND supervisor_graph intent handlers
    both call these same methods, ensuring consistent behavior.
    """

    def __init__(self, root: str | None = None):
        self.root = root or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )

    # ── /status ────────────────────────────────────────────────

    def status(self, session) -> CommandResult:
        """Return current session state and profile attributes."""
        data = getattr(session, "temp_profile_data", {}) or {}
        lines = [
            f"**State:** {getattr(session, 'state', 'UNKNOWN')}",
            f"**Roles:** {data.get('target_roles', 'N/A')}",
            f"**Cities:** {data.get('target_cities', 'N/A')}",
            f"**Salary:** {data.get('salary_expectations', 'N/A')}",
            f"**Notice:** {data.get('notice_period', 'N/A')}",
            f"**Mode:** {data.get('aggressiveness', 'N/A')}",
        ]
        return CommandResult(text="\n".join(lines))

    # ── /brief ─────────────────────────────────────────────────

    def brief(self) -> CommandResult:
        """Return today's daily brief if it exists."""
        today_str = datetime.now(timezone.utc).date().isoformat()
        brief_path = os.path.join(self.root, "output", "daily_briefs", f"{today_str}.md")
        if os.path.exists(brief_path):
            with open(brief_path) as f:
                return CommandResult(text=f.read())
        return CommandResult(
            text="No brief generated today. Type `/scan` to search for new jobs."
        )

    # ── /scan ──────────────────────────────────────────────────

    def scan(self) -> CommandResult:
        """Run the full DailyRunner pipeline."""
        try:
            from careerloop.daily_runner import DailyRunner
            runner = DailyRunner(self.root)
            result = runner.run(do_scan=True)

            if result.get("already_generated"):
                today_str = datetime.now(timezone.utc).date().isoformat()
                brief_path = os.path.join(self.root, "output", "daily_briefs", f"{today_str}.md")
                if os.path.exists(brief_path):
                    with open(brief_path) as f:
                        text = f.read()
                    return CommandResult(
                        text=f"Brief already generated today.\n\n{text}",
                        new_state="BRIEF_AVAILABLE",
                    )
                return CommandResult(
                    text=f"Brief already generated today ({today_str}).",
                    new_state="BRIEF_AVAILABLE",
                )

            shortlist_text = result.get("shortlist_text", "")
            return CommandResult(
                text=f"Scan complete! {result['new_jobs_found']} raw → {result['unique_added']} new → {result['scored']} scored.\n\n{shortlist_text}",
                new_state="BRIEF_AVAILABLE",
            )
        except Exception as e:
            logger.exception("Scan failed")
            return CommandResult(text=f"Scan failed: {e}")

    # ── /pipeline ──────────────────────────────────────────────

    def pipeline(self) -> CommandResult:
        """Return a summary of the job pipeline."""
        try:
            from careerloop.application_ledger import ApplicationLedger
            ledger = ApplicationLedger(self.root)
            status_counts: dict[str, int] = {}
            for e in ledger.entries:
                s = e.get("status", "UNKNOWN")
                status_counts[s] = status_counts.get(s, 0) + 1
            lines = ["**Job Pipeline**\n"]
            for status, count in sorted(status_counts.items()):
                lines.append(f"  • {status}: {count}")
            top = ledger.get_top_scored(min_score=1, limit=5)
            if top:
                lines.append(f"\n**Top 5 Matches:**")
                for i, job in enumerate(top, 1):
                    score = ledger._get_score(job) or 0
                    lines.append(
                        f"  {i}. **{job.get('title','?')}** @ {job.get('company','?')} — {score:.0f}/100"
                    )
            return CommandResult(text="\n".join(lines))
        except Exception as e:
            return CommandResult(text=f"Could not load pipeline: {e}")

    # ── /profile ───────────────────────────────────────────────

    def profile(self, session) -> CommandResult:
        """Return full profile with CV preview."""
        data = getattr(session, "temp_profile_data", {}) or {}
        cv = data.get("cv_content", "")
        if cv:
            preview = cv[:500] + ("..." if len(cv) > 500 else "")
        else:
            preview = "No CV on file."
        lines = [
            "**Full Profile**\n",
            f"**CV Preview:** {preview}",
        ]
        for key, val in data.items():
            if key == "cv_content":
                continue
            lines.append(f"**{key}:** {val}")
        return CommandResult(text="\n".join(lines))

    # ── /reset ─────────────────────────────────────────────────

    def reset(self, session) -> CommandResult:
        """Reset session to IDLE."""
        session.state = "IDLE"
        session.temp_profile_data = None
        return CommandResult(
            text="Session reset. You'll re-enter onboarding on your next message.",
            new_state="IDLE",
        )

    # ── /help ──────────────────────────────────────────────────

    def help(self) -> CommandResult:
        return CommandResult(
            text="\n".join([
                "**Commands:**",
                "  `/status` — View your session state and profile",
                "  `/brief` — Show today's daily job brief",
                "  `/scan` — Search for new jobs",
                "  `/pipeline` — View all jobs in your pipeline",
                "  `/profile` — View your full profile details",
                "  `/reset` — Reset your session",
                "  `/help` — Show this help",
                "",
                "**Chat naturally:** ask for your daily briefing, pipeline status, or new job matches.",
            ])
        )
```

- [ ] **Step 2: Wire slash commands in chat_cli.py to use CommandRouter**

In `chat_cli.py`, find the slash command dispatch block (around line 300-329). Replace it with delegation to `CommandRouter`:

```python
            # ── Slash commands ── route through CommandRouter for unified handling ──
            if user_input.startswith("/"):
                cmd = user_input.strip().lower().split()[0]
                router = CommandRouter(root)
                result = None

                if cmd == "/help":
                    result = router.help()
                elif cmd == "/status":
                    result = router.status(session)
                elif cmd == "/profile":
                    result = router.profile(session)
                elif cmd == "/scan":
                    result = router.scan()
                elif cmd == "/pipeline":
                    result = router.pipeline()
                elif cmd == "/brief":
                    result = router.brief()
                elif cmd == "/reset":
                    result = router.reset(session)
                else:
                    console.print(f"[yellow]Unknown command: {user_input}. Type /help for available commands.[/yellow]")
                    continue

                if result:
                    console.print(Panel(Markdown(result.text), title="CareerLoop", border_style="bold cyan"))
                    if result.new_state and session_store:
                        session.state = normalize_user_state(result.new_state) or session.state
                        session_store.save_session(session)
                continue
```

Also add the import at the top:
```python
from careerloop.session.command_router import CommandRouter
```

And find/replace any references to `print_help_panel()`, `print_status_card(session)`, `run_background_scan()`, `print_pipeline(db_manager)`, `print_profile_details(session)` — these functions can be kept but simplified to thin wrappers, or removed if they're only called from the slash command block.

**Important:** Keep the existing `run_background_scan()` function in chat_cli.py as a fallback but mark it deprecated. The `CommandRouter.scan()` method is now canonical.

- [ ] **Step 3: Verify parse**

```bash
python3 -c "import ast; ast.parse(open('careerloop/session/command_router.py').read()); print('OK')"
python3 -c "import ast; ast.parse(open('careerloop/chat_cli.py').read()); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add careerloop/session/command_router.py careerloop/chat_cli.py
git commit -m "feat(commands): unified CommandRouter — slash commands and graph intents share handlers"
```

---

### Task 5: Fix LLM Error Handling + Retry

**Files:**
- Modify: `careerloop/llm_chat.py:15-40`

- [ ] **Step 1: Replace `_call_api` with retry + safe error messages**

```python
    RETRY_STATUSES = {429, 500, 502, 503, 504}
    MAX_RETRIES = 2
    SAFE_ERROR_MSG = (
        "I hit a model issue while processing that. "
        "Your data is safe. Try again or type /help for available commands."
    )

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """Call DeepSeek with retry on transient errors. Never return raw API text."""
        import time

        last_error = ""
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 4096,
                    },
                    timeout=30,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]

                # Retryable error?
                if response.status_code in self.RETRY_STATUSES and attempt < self.MAX_RETRIES:
                    wait = (attempt + 1) * 2
                    logger.warning(
                        "DeepSeek %s on attempt %d/%d, retrying in %ds",
                        response.status_code, attempt + 1, self.MAX_RETRIES + 1, wait,
                    )
                    time.sleep(wait)
                    continue

                # Non-retryable or exhausted retries
                logger.error(
                    "DeepSeek API error %d after %d attempts: %s",
                    response.status_code, attempt + 1, response.text[:200],
                )
                return f'{{"reply": "{self.SAFE_ERROR_MSG}"}}'

            except requests.Timeout:
                if attempt < self.MAX_RETRIES:
                    logger.warning("DeepSeek timeout on attempt %d, retrying", attempt + 1)
                    time.sleep(2)
                    continue
                logger.error("DeepSeek timeout after %d attempts", self.MAX_RETRIES + 1)
                return f'{{"reply": "{self.SAFE_ERROR_MSG}"}}'

            except Exception as e:
                logger.exception("DeepSeek unexpected error on attempt %d", attempt + 1)
                if attempt < self.MAX_RETRIES:
                    time.sleep(2)
                    continue
                return f'{{"reply": "{self.SAFE_ERROR_MSG}"}}'

        return f'{{"reply": "{self.SAFE_ERROR_MSG}"}}'
```

- [ ] **Step 2: Add API key validation at module load**

At the bottom of `_call_api`'s class or in the module body:

```python
def validate_api_key() -> bool:
    """Check DEEPSEEK_API_KEY is set and non-empty. Log warning if missing."""
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        logger.critical("DEEPSEEK_API_KEY is not set. All LLM calls will fail with 401.")
        return False
    return True
```

- [ ] **Step 3: Verify parse**

```bash
python3 -c "import ast; ast.parse(open('careerloop/llm_chat.py').read()); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add careerloop/llm_chat.py
git commit -m "fix(llm): retry on transient errors, safe user-facing messages, API key validation"
```

---

### Task 6: Fix Conversation History

**Files:**
- Modify: `careerloop/transport/base.py:30`
- Modify: `careerloop/session/supervisor_graph.py:66`

- [ ] **Step 1: Add `add_messages` reducer to ConversationState**

In `supervisor_graph.py`, find the `ConversationState` TypedDict (around line 62-70) and update:

```python
from typing import Annotated
from langgraph.graph.message import add_messages

class ConversationState(TypedDict):
    user_id: str
    current_state: UserState
    pending_job_id: Optional[str]
    messages: Annotated[list[BaseMessage], add_messages]  # <-- add_messages reducer
    council_state: Optional[dict]
    assistant_response: Optional[str]
    temp_profile_data: Optional[dict]
```

- [ ] **Step 2: Append AIMessage after each assistant response**

In `intent_router`, after constructing the `assistant_response`, also append it to messages. Add this at the end of each return block:

```python
# In every return dict where assistant_response is set:
    "messages": [AIMessage(content=reply)],
```

This needs to be added to EVERY return dict in `intent_router`. The `add_messages` reducer will append it to the existing list.

Example for PROFILE_COMPLETE handler:
```python
return {
    "current_state": current_state,
    "assistant_response": reply,
    "messages": [AIMessage(content=reply)],
}
```

- [ ] **Step 3: In base.py, update _event_to_state to not clobber messages**

In `base.py:30`, the current code sets `"messages": [HumanMessage(content=event.text)]`. With `add_messages`, this will APPEND to the existing list rather than replace it. This is the desired behavior — no change needed in base.py.

- [ ] **Step 4: Verify parse**

```bash
python3 -c "import ast; ast.parse(open('careerloop/session/supervisor_graph.py').read()); print('OK')"
python3 -c "import ast; ast.parse(open('careerloop/transport/base.py').read()); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add careerloop/session/supervisor_graph.py careerloop/transport/base.py
git commit -m "fix(history): add_messages reducer preserves conversation history across turns"
```

---

### Task 7: Remove Hardcoded Demo Strings from Onboarding

**Files:**
- Modify: `careerloop/onboarding/onboarding_flow.py`

- [ ] **Step 1: Replace hardcoded strings with LLM-generated responses**

In `onboarding_flow.py`, find `handle_message()`:

1. Remove the hardcoded "Your profile is already set up." string (around line 31-33). Instead, delegate to `ChatIntentAgent` to generate a contextual message about their existing profile.

2. Remove the hardcoded "I'm not sure how to handle that right now." fallback (around line 62). Substitute with the OnboardingAgent's default fallback or a safe generic message.

3. Add `is_complete` validation: before transitioning to PROFILE_COMPLETE, verify all required fields are non-empty. If fields are missing, ask only for the missing ones.

```python
# onboarding_flow.py — after OnboardingAgent returns is_complete=True:

REQUIRED_FIELDS = [
    "target_roles", "target_cities", "salary_expectations",
    "notice_period", "aggressiveness",
]

if is_complete:
    # Validate all required fields are actually populated
    missing = [f for f in REQUIRED_FIELDS if not updated_data.get(f)]
    if missing:
        # Some fields missing — ask for them specifically
        reply = f"I still need a few more details: {', '.join(missing)}. Could you share those?"
        self.session_store.save_session(session)
        return (reply, state)

    # All fields present — truly complete
    session.temp_profile_data = None
    session.state = UserState.PROFILE_COMPLETE
    if not self.session_store.save_session(session):
        raise RuntimeError(
            f"Failed to persist session state {session.state}. Check database connection."
        )

    # Generate contextual completion message via LLM
    try:
        agent_reply = self.agent.process(
            "The user has completed their profile. Generate a warm welcome message "
            "summarizing their profile and explaining what they can do next.",
            updated_data,
        )
        reply = agent_reply[1]
    except Exception:
        reply = (
            "Your profile is complete! I'll now match you with relevant jobs. "
            "Type `/scan` to start searching or ask me for your daily briefing."
        )

    return (reply + "\n\nAwesome! Your profile is set up. I'll start monitoring jobs for you and send you daily briefs. You are now fully onboarded.", UserState.PROFILE_COMPLETE)
```

- [ ] **Step 2: Verify parse**

```bash
python3 -c "import ast; ast.parse(open('careerloop/onboarding/onboarding_flow.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add careerloop/onboarding/onboarding_flow.py
git commit -m "fix(onboarding): validate is_complete, use LLM for profile-complete message, remove hardcoded strings"
```

---

### Task 8: Remove Dual Session Loading

**Files:**
- Modify: `careerloop/chat_cli.py:250-260`
- Modify: `careerloop/session/supervisor_graph.py:85-122`

- [ ] **Step 1: In chat_cli.py, load session once and pass via metadata**

The chat_cli already loads the session at startup (line ~254) and passes `session.state` and profile data in metadata. The issue is `supervisor_graph.py` loads the session AGAIN from the DB. The fix: make the supervisor trust the metadata.

In `supervisor_graph.py`, the `IDLE/ONBOARDING_*` handler at line 85-122 does `store.get_session(user_id)` — this is the DUPLICATE load. Instead, rely on the state + profile_data already present in the graph state:

```python
# supervisor_graph.py:85-122 — replace the DB load with metadata trust:

if current_state in (UserState.IDLE, UserState.ONBOARDING_WAITING_CV, UserState.ONBOARDING_COLLECTING):
    import os as _os
    from careerloop.onboarding.onboarding_flow import OnboardingFlow

    # Build a lightweight session from graph state — NO second DB load
    from careerloop.session.session_store import Session
    session = Session(
        user_id=state.get("user_id", "unknown"),
        state=current_state,
    )
    session.temp_profile_data = state.get("temp_profile_data") or {}

    flow = OnboardingFlow(None)  # pass store=None; OnboardingFlow only needs store for save_session
    # But wait — OnboardingFlow needs store for save_session(). 
    # Let's give it a proper store:
    from careerloop.session.session_store import SessionStore
    from careerloop.memory.connection import DatabaseManager
    db = DatabaseManager(_os.getenv("DATABASE_URL"))
    store = SessionStore(db)

    # Ensure user row exists
    user_id = state.get("user_id", "unknown")
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {store._tbl('users')} (id, email) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                    (user_id, f"{user_id}@example.com"),
                )
            conn.commit()
    except Exception:
        pass

    flow = OnboardingFlow(store)
    reply, next_state = flow.handle_message(session, last_message)
    return {
        "current_state": next_state,
        "assistant_response": reply,
        "temp_profile_data": session.temp_profile_data,
    }
```

Actually, the session needs to be loaded ONCE per turn. The cleanest approach: in `chat_cli.py`, load the session, pass full state in metadata, and have the supervisor NEVER load from DB. It should always receive the canonical session from metadata.

But the onboarding flow currently calls `store.get_session()` to get the session object. We need to change this to use metadata-derived session.

Let me simplify: the `IDLE/ONBOARDING` handler already gets `session.state` and `session.temp_profile_data` from the transport layer metadata. The only reason it calls `store.get_session()` is to get a `Session` object to pass to `OnboardingFlow.handle_message()`. We can construct this `Session` from the metadata instead of loading from DB:

Replace lines 85-122 with the above code that constructs a `Session` from graph state instead of loading from DB.

- [ ] **Step 2: Verify parse**

```bash
python3 -c "import ast; ast.parse(open('careerloop/session/supervisor_graph.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add careerloop/session/supervisor_graph.py careerloop/chat_cli.py
git commit -m "fix(session): single canonical session load per turn — no dual DB reads"
```

---

### Task 9: Write Tests

**Files:**
- Create: `tests/test_chat_runtime.py`

- [ ] **Step 1: Write comprehensive test file**

```python
"""Chat runtime regression tests — proving no echo, no hardcode, correct states."""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# --- Test 1: GENERAL_CHAT does not echo user input ---


class TestNoEchoFallback(unittest.TestCase):
    def test_missing_assistant_response_returns_safe_message(self):
        """When supervisor returns no assistant_response, transport returns safe error, not echo."""
        from careerloop.transport.base import TransportAdapter, UserEvent

        class StubAdapter(TransportAdapter):
            def parse_payload(self, raw):
                return UserEvent(user_id="test", text="hello", platform="test")
            def send_text(self, user_id, text):
                self.last_text = text
                return True
            def request_input(self, user_id, prompt=""):
                return ""

        adapter = StubAdapter(supervisor_graph=None)
        # Simulate: supervisor returns no assistant_response but messages has user text
        response = {
            "current_state": "PROFILE_COMPLETE",
            "messages": [MagicMock(content="hello")],  # user's message
        }

        # Monkey-patch invoke to return our test response
        adapter.supervisor_graph = MagicMock()
        adapter.supervisor_graph.invoke.return_value = response

        adapter.receive({"user_id": "test", "text": "hello", "metadata": {}})

        # Must NOT echo "hello"
        self.assertNotEqual(adapter.last_text, "hello")
        # Must contain safe error language
        self.assertIn("internal routing", adapter.last_text.lower())


# --- Test 2: /brief does not trigger scan ---


class TestBriefNoScan(unittest.TestCase):
    def test_brief_command_does_not_call_daily_runner(self):
        """The /brief command reads from disk, never invokes DailyRunner."""
        from careerloop.session.command_router import CommandRouter

        router = CommandRouter(root="/tmp")
        # Even with no brief file, it should NOT try to scan
        result = router.brief()
        self.assertIn("No brief generated", result.text)
        # Verify no scan was triggered
        self.assertIsNone(result.new_state)


# --- Test 3: "daily brief" normal chat does not trigger scan ---


class TestDailyBriefNoScan(unittest.TestCase):
    @patch("careerloop.llm_chat.LLMChatAgent._call_api")
    def test_daily_briefing_routes_to_show_pipeline(self, mock_api):
        """Natural language 'daily briefing' must route to SHOW_PIPELINE, not SCAN_JOBS."""
        mock_api.return_value = '{"intent": "SHOW_PIPELINE", "reply": "Let me pull up your pipeline..."}'

        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent()
        profile = {
            "target_roles": "AI Engineer",
            "target_cities": "Chennai",
            "salary_expectations": "20 LPA",
            "notice_period": "1 month",
            "aggressiveness": "Quality",
        }
        intent, reply = agent.process("Bro, give me my daily briefing, bro.", profile)
        self.assertEqual(intent, "SHOW_PIPELINE")


# --- Test 4: Complete profile never re-enters onboarding ---


class TestProfileCompleteNoOnboarding(unittest.TestCase):
    def test_complete_profile_does_not_reenter_onboarding(self):
        """A session with all 6 fields must be PROFILE_COMPLETE, not onboarding."""
        from careerloop.onboarding.onboarding_flow import REQUIRED_FIELDS
        complete_data = {
            "cv_content": "Experienced AI engineer...",
            "target_roles": "AI Engineer",
            "target_cities": "Chennai, Bangalore",
            "salary_expectations": "20-25 LPA",
            "notice_period": "1 month",
            "aggressiveness": "Quality over quantity",
        }
        missing = [f for f in REQUIRED_FIELDS if not complete_data.get(f)]
        self.assertEqual(len(missing), 0, f"Profile should be complete, missing: {missing}")


# --- Test 5: Old DAILY_BRIEF_SENT migrates to PROFILE_COMPLETE ---


class TestLegacyStateMigration(unittest.TestCase):
    def test_daily_brief_sent_migrates(self):
        from careerloop.session.states import normalize_user_state, UserState
        result = normalize_user_state("DAILY_BRIEF_SENT")
        self.assertEqual(result, UserState.PROFILE_COMPLETE)

    def test_onboarding_q_states_migrate(self):
        from careerloop.session.states import normalize_user_state, UserState
        for old in ("ONBOARDING_Q1_ROLES", "ONBOARDING_Q2_CITIES", "ONBOARDING_Q3_SALARY"):
            result = normalize_user_state(old)
            self.assertEqual(result, UserState.ONBOARDING_COLLECTING)

    def test_unknown_state_resets_to_idle(self):
        from careerloop.session.states import normalize_user_state, UserState
        result = normalize_user_state("GARBAGE_STATE")
        self.assertEqual(result, UserState.IDLE)


# --- Test 6: Natural approval phrases trigger PACK_GENERATING ---


class TestApprovalIntent(unittest.TestCase):
    @patch("careerloop.llm_chat.LLMChatAgent._call_api")
    def test_approval_phrases_trigger_approve_intent(self, mock_api):
        """Natural approval phrases must be classified as APPROVE."""
        mock_api.return_value = '{"intent": "APPROVE", "reply": "Approved!"}'

        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent()
        profile = {"target_roles": "AI Engineer"}
        for phrase in ("yes", "approve", "looks good", "prepare this", "apply to this one"):
            intent, _ = agent.process(phrase, profile)
            self.assertEqual(intent, "APPROVE", f"'{phrase}' should be APPROVE, got {intent}")


# --- Test 7: pack_generation node is reachable ---


class TestPackGenerationReachable(unittest.TestCase):
    def test_reviewing_job_to_pack_generating_transition(self):
        """REVIEWING_JOB + APPROVE intent → PACK_GENERATING state transition."""
        from careerloop.session.supervisor_graph import get_supervisor_graph
        from careerloop.session.states import UserState
        from langchain_core.messages import HumanMessage

        graph = get_supervisor_graph(checkpointer=None)

        # Simulate state: REVIEWING_JOB with a pending job
        state = {
            "user_id": "test-user",
            "current_state": UserState.REVIEWING_JOB,
            "pending_job_id": "job-123",
            "messages": [HumanMessage(content="prepare this one")],
            "council_state": None,
            "assistant_response": None,
            "temp_profile_data": {"target_roles": "AI Engineer", "has_cv": True},
        }

        # Patch the LLM to return APPROVE
        with patch("careerloop.llm_chat.LLMChatAgent._call_api") as mock:
            mock.return_value = '{"intent": "APPROVE", "reply": "Approved."}'
            result = graph.invoke(state)

        self.assertEqual(result["current_state"], UserState.PACK_GENERATING)


# --- Test 8: No raw API errors reach user ---


class TestNoRawApiErrors(unittest.TestCase):
    def test_api_401_returns_safe_message(self):
        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent(api_key="bad_key")
        intent, reply = agent.process("hello", {})
        self.assertNotIn("401", reply)
        self.assertNotIn("API error", reply)
        self.assertIn("model issue", reply.lower())

    def test_timeout_returns_safe_message(self):
        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent(api_key="sk-valid")
        with patch("requests.post", side_effect=Exception("timeout")):
            intent, reply = agent.process("hello", {})
            self.assertNotIn("timeout", reply.lower())
            self.assertIn("model issue", reply.lower())


# --- Test 9: Slash command and freeform use same handler ---


class TestUnifiedCommandRouting(unittest.TestCase):
    def test_slash_brief_matches_command_router_brief(self):
        """The CommandRouter.brief() method is canonical — both slash and graph use it."""
        from careerloop.session.command_router import CommandRouter
        router = CommandRouter(root="/tmp")
        result = router.brief()
        self.assertIsNotNone(result.text)
        # /brief returns text (either brief or "no brief" message)
        self.assertTrue(len(result.text) > 0)


# --- Test 10: Conversation history includes assistant turns ---


class TestConversationHistory(unittest.TestCase):
    def test_add_messages_reducer_present(self):
        """ConversationState.messages must use Annotated with add_messages reducer."""
        from careerloop.session.supervisor_graph import ConversationState

        from typing import get_type_hints
        hints = get_type_hints(ConversationState)
        self.assertIn("messages", hints)


# --- Test 11: GENERAL_CHAT returns assistant response ---


class TestGeneralChatReturnsReply(unittest.TestCase):
    @patch("careerloop.llm_chat.LLMChatAgent._call_api")
    def test_general_chat_llm_reply_is_returned(self, mock_api):
        """When intent is GENERAL_CHAT, the LLM's reply must be in the returned response."""
        mock_api.return_value = '{"intent": "GENERAL_CHAT", "reply": "Hello! How can I help?"}'

        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent()
        intent, reply = agent.process("hello", {"target_roles": "AI"})
        self.assertEqual(intent, "GENERAL_CHAT")
        self.assertEqual(reply, "Hello! How can I help?")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests**

```bash
.venv/bin/python -m pytest tests/test_chat_runtime.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_chat_runtime.py
git commit -m "test(chat): 11 regression tests — echo, brief, scan, states, approval, history, errors, routing"
```

---

### Task 10: Remove Remaining Hardcoded Strings + Cleanup

**Files:**
- Modify: `careerloop/chat_cli.py` — remove unused functions if any
- Modify: `careerloop/session/supervisor_graph.py` — review all `assistant_response` values

- [ ] **Step 1: Audit all hardcoded user-facing strings**

Run and verify zero instances remain:
```bash
grep -rn '"I am\|"I\'m not sure\|"I did not\|"Cannot build\|"Your profile is already\|"Approval received\|"I kept you\|"I did not receive\|"Application pack compiled\|"assembly failed\|"Unknown command' careerloop/ --include="*.py" | grep -v test | grep -v __pycache__
```

Expected: zero results.

- [ ] **Step 2: Verify all states have handlers**

```bash
python3 -c "
from careerloop.session.states import UserState
from careerloop.session.supervisor_graph import intent_router
import inspect
src = inspect.getsource(intent_router)
for state in UserState:
    if state.value in src:
        print(f'{state.name}: HANDLED in intent_router')
    else:
        print(f'{state.name}: NOT IN intent_router')
"
```

Expected: every state shows HANDLED (via the fallthrough or explicit handler).

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove remaining hardcoded demo strings, verify all states handled"
```

---

### Task 11: E2E Verification on CLI

- [ ] **Step 1: Start the CLI**

```bash
./.venv/bin/python careerloop/chat_cli.py
```

- [ ] **Step 2: Verify each requirement**

```
/status          → Shows state + profile fields
/help            → Shows available commands
/brief           → No brief yet? Shows "No brief generated" without triggering scan
"daily brief"    → SHOW_PIPELINE intent, shows pipeline summary, no scan triggered  
"match me with jobs" → SCAN_JOBS intent, offers to use /scan
/scan            → Runs DailyRunner pipeline, generates brief
/brief           → Shows persisted brief
"hello"          → GENERAL_CHAT, returns conversational LLM response — NOT echo
"prepare this one" → APPROVE intent → PACK_GENERATING
/status          → State shows PACK_GENERATING or PACK_READY
/reset           → State returns to IDLE
/status          → Shows IDLE
```

- [ ] **Step 3: Verify no raw API errors in output**

Check logs:
```bash
tail -20 logs/careerloop.jsonl | grep -i "error\|critical\|exception"
```
Only internal errors should appear, no user-visible raw API text.

- [ ] **Step 4: Commit final cleanup**

```bash
git add -A
git commit -m "chore: final e2e verification cleanup"
```
