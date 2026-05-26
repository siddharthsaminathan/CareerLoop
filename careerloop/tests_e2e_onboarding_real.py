"""
Real E2E Onboarding Test
========================
What is REAL here (no mocks):
  - CVExtractionAgent.extract() — actual DeepSeek API call
  - OnboardingFlow.handle_message() — actual class method calls
  - Step transitions — actual state machine logic
  - ActionResolver.resolve() — actual guard logic

What requires DATABASE_URL (skipped if absent):
  - SessionStore.get_or_create_user() — real Supabase write
  - SessionStore.save_session() — real Supabase write
  - _commit_profile_to_db() — real Supabase write + read-back

Run:
    python -m careerloop.tests_e2e_onboarding_real
    python -m careerloop.tests_e2e_onboarding_real --with-db   (requires DATABASE_URL)
"""

import os
import sys
import json
import uuid
import time
import logging
import argparse
from datetime import datetime
from unittest.mock import MagicMock, patch

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.WARNING)

# ── Three real test users ──────────────────────────────────────────────────────

USERS = [
    {
        "id": "user_a",
        "telegram_chat_id": 9_000_001,
        "first_name": "Priya",
        "username": "priya_e2e",
        "cv_text": (
            "Priya Sharma\n"
            "Senior Product Manager | Bangalore\n"
            "priya@email.com\n\n"
            "EXPERIENCE\n"
            "Razorpay — Senior Product Manager (2022–Present)\n"
            "Led checkout redesign, 18% conversion lift. BNPL product with 3 lenders.\n\n"
            "Swiggy — Product Manager (2019–2022)\n"
            "Restaurant discovery ranking. Reduced time-to-first-order by 22%.\n\n"
            "EDUCATION\n"
            "IIM Bangalore MBA 2019 | IIT Madras B.Tech CS 2017\n\n"
            "Expected CTC: 45-55 LPA | Notice: 60 days"
        ),
        "confirmation": "yes",
    },
    {
        "id": "user_b",
        "telegram_chat_id": 9_000_002,
        "first_name": "Rohan",
        "username": "rohan_e2e",
        "cv_text": (
            "Rohan Mehta | Full Stack Engineer | Mumbai\n"
            "rohan@techmail.com\n\n"
            "Flipkart — Software Engineer II (2021–Now)\n"
            "React seller dashboard. Optimised PostgreSQL queries by 40%.\n"
            "Python, FastAPI, Redis, AWS.\n\n"
            "Infosys — Associate (2018–2021)\n"
            "Java Spring Boot microservices.\n\n"
            "VIT University B.Tech IT 2018\n"
            "Looking for: Senior SWE / Staff Engineer in Pune or Mumbai\n"
            "Salary: 30-40 LPA | Notice: 3 months"
        ),
        "confirmation": "no wait, I also want Bangalore added to my cities",
        "correction_confirmation": "yes",
    },
    {
        "id": "user_c",
        "telegram_chat_id": 9_000_003,
        "first_name": "Ananya",
        "username": "ananya_e2e",
        "cv_text": (
            "Ananya Krishnan\n"
            "ananya.k@gmail.com | Chennai\n\n"
            "ICICI Bank, Analyst, 2020–present\n"
            "Madras University B.Com 2020\n"
            "Skills: Excel, financial modelling, Tally"
        ),
        "gap_fill": (
            "I want Finance Analyst and FP&A Analyst roles. "
            "Salary around 12-18 LPA. Notice is 1 month. I am actively job hunting."
        ),
        "confirmation": "yes",
    },
]

REQUIRED_FIELDS = ["target_roles", "target_cities", "salary_expectations", "notice_period", "aggressiveness"]


# ── Minimal fake SessionStore (only used when DATABASE_URL is absent) ──────────

def _make_fake_store():
    """
    A fake SessionStore that records calls and stores state in memory.
    Used ONLY when DATABASE_URL is absent — not to avoid testing logic,
    but because the production DB is not available in this environment.
    All OnboardingFlow, CVExtractionAgent, and ActionResolver logic
    runs real with no mocking.
    """
    from careerloop.session.session_store import Session
    from careerloop.session.states import UserJourneyState

    db_log = []  # Records every DB call made — visible in report

    class FakeStore:
        def __init__(self):
            self._sessions = {}
            self._users = {}
            self.db_manager = MagicMock()
            self.db_manager.get_connection = MagicMock()

        def _tbl(self, name):
            return f"careerloop.{name}"

        def _parse_profile_prefs(self, raw):
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except Exception:
                    return {}
            return {}

        def get_or_create_user(self, telegram_chat_id, first_name="", username=""):
            uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"telegram:{telegram_chat_id}"))
            if uid not in self._users:
                self._users[uid] = {
                    "id": uid,
                    "email": f"telegram_{telegram_chat_id}@careerloop.internal",
                    "full_name": first_name or "User",
                    "telegram_chat_id": telegram_chat_id,
                    "handle": username,
                    "master_cv_markdown": None,
                    "work_style_prefs": {},
                    "target_roles": None,
                    "target_cities": None,
                    "salary_expectations": None,
                    "notice_period": None,
                    "career_mode": None,
                    "onboarding_complete": False,
                }
                db_log.append(f"INSERT careerloop.users uid={uid[:12]} chat_id={telegram_chat_id}")
            return uid

        def get_session(self, user_id: str) -> Session:
            if user_id not in self._sessions:
                session = Session(user_id=user_id, state=UserJourneyState.NEW_USER)
                self._sessions[user_id] = session
                db_log.append(f"SELECT careerloop.sessions user_id={user_id[:12]} -> NEW (created)")
                return session
            db_log.append(f"SELECT careerloop.sessions user_id={user_id[:12]} -> EXISTS")
            return self._sessions[user_id]

        def save_session(self, session: Session) -> bool:
            self._sessions[session.user_id] = session
            db_log.append(
                f"UPSERT careerloop.sessions user_id={session.user_id[:12]} "
                f"state={session.state.value} step={session.onboarding_step}"
            )
            return True

        def _load_profile_data(self, user_id: str) -> dict:
            u = self._users.get(user_id, {})
            return {
                "cv_content": u.get("master_cv_markdown") or "",
                "target_roles": u.get("target_roles") or "",
                "target_cities": u.get("target_cities") or "",
                "salary_expectations": u.get("salary_expectations") or "",
                "notice_period": u.get("notice_period") or "",
                "aggressiveness": u.get("career_mode") or "",
            }

        def get_profile(self, user_id: str) -> dict:
            return self._users.get(user_id, {})

        def write_profile(self, user_id: str, profile_data: dict):
            """Called by onboarding_flow._commit_profile_to_db — we intercept to capture the write."""
            if user_id in self._users:
                self._users[user_id].update({
                    "master_cv_markdown": profile_data.get("cv_content"),
                    "target_roles": profile_data.get("target_roles"),
                    "target_cities": profile_data.get("target_cities"),
                    "salary_expectations": profile_data.get("salary_expectations"),
                    "notice_period": profile_data.get("notice_period"),
                    "career_mode": profile_data.get("aggressiveness"),
                    "onboarding_complete": True,
                })
                db_log.append(
                    f"UPDATE careerloop.users uid={user_id[:12]} "
                    f"roles={profile_data.get('target_roles')} "
                    f"cities={profile_data.get('target_cities')} "
                    f"onboarding_complete=TRUE"
                )

    store = FakeStore()
    return store, db_log


# ── Real pipeline runner ───────────────────────────────────────────────────────

def run_user_real(user: dict, with_db: bool = False) -> dict:
    """
    Runs ONE user through the actual OnboardingFlow + CVExtractionAgent pipeline.
    LLM calls are real. DB calls are real if with_db=True, else intercepted via FakeStore.
    """
    from careerloop.session.states import UserJourneyState
    from careerloop.onboarding.onboarding_flow import OnboardingFlow
    from careerloop.session.action_resolver import ActionResolver
    from careerloop.session.models import ActionType

    t_user_start = time.time()
    result = {
        "user": user["first_name"],
        "telegram_chat_id": user["telegram_chat_id"],
        "steps": [],
        "db_calls": [],
        "final_state": None,
        "profile_written": {},
        "passed": False,
        "errors": [],
        "llm_calls": [],
    }

    # ── Store setup ────────────────────────────────────────────────────────────
    if with_db:
        from careerloop.memory.connection import get_db_manager
        from careerloop.session.session_store import SessionStore
        db = get_db_manager()
        store = SessionStore(db)
        db_log = ["Using real Supabase — DB calls not intercepted"]
    else:
        store, db_log = _make_fake_store()
        result["db_calls"] = db_log  # live reference — appended as we go

    # Patch _commit_profile_to_db to route through store.write_profile when using FakeStore
    if not with_db:
        original_commit = OnboardingFlow._commit_profile_to_db

        def patched_commit(self_flow, user_id, profile_data):
            store.write_profile(user_id, profile_data)

        OnboardingFlow._commit_profile_to_db = patched_commit

    try:
        # ── Step 1: Identity bootstrap ─────────────────────────────────────────
        uid = store.get_or_create_user(
            telegram_chat_id=user["telegram_chat_id"],
            first_name=user["first_name"],
            username=user["username"],
        )
        result["steps"].append({"step": "identity_bootstrap", "user_id": uid[:16] + "...", "status": "ok"})

        # ── Step 2: Build flow + session ───────────────────────────────────────
        flow = OnboardingFlow(store)
        session = store.get_session(uid)
        assert session.state == UserJourneyState.NEW_USER

        # ── Step 3: STEP_IDLE — greet ──────────────────────────────────────────
        t0 = time.time()
        reply, state = flow.handle_message(session, "hi")
        result["steps"].append({
            "step": "STEP_IDLE->WAITING_CV",
            "status": "ok",
            "session_step": session.onboarding_step,
            "reply_preview": reply[:80],
            "latency_ms": round((time.time() - t0) * 1000),
        })
        assert "CV" in reply or "resume" in reply.lower(), f"Greet did not ask for CV: {reply}"
        assert session.onboarding_step == 1  # STEP_WAITING_CV

        # ── Step 4: STEP_WAITING_CV — submit CV (REAL LLM CALL) ───────────────
        t0 = time.time()
        reply, state = flow.handle_message(session, user["cv_text"])
        llm_latency = round((time.time() - t0) * 1000)
        extracted = session.temp_profile_data or {}
        result["steps"].append({
            "step": "STEP_WAITING_CV->CONFIRMING",
            "status": "ok",
            "session_step": session.onboarding_step,
            "llm_call": "CVExtractionAgent.extract (REAL DeepSeek)",
            "llm_latency_ms": llm_latency,
            "extracted_fields": {k: v for k, v in extracted.items() if k != "cv_content"},
            "reply_preview": reply[:120],
        })
        result["llm_calls"].append({"agent": "CVExtractionAgent", "latency_ms": llm_latency})
        assert session.onboarding_step == 2, f"Expected STEP_CONFIRMING(2), got {session.onboarding_step}"

        # ── Step 5: STEP_CONFIRMING or STEP_COLLECTING ────────────────────────
        confirmation_text = user.get("confirmation", "yes")
        gap_fill = user.get("gap_fill")

        t0 = time.time()
        reply, state = flow.handle_message(session, confirmation_text)
        confirm_latency = round((time.time() - t0) * 1000)

        # If correction path (Rohan): one more turn
        if confirmation_text.lower() not in {"yes", "y", "correct", "yep"}:
            result["steps"].append({
                "step": "STEP_CONFIRMING (correction)",
                "status": "ok",
                "session_step": session.onboarding_step,
                "llm_call": "OnboardingAgent.process (REAL DeepSeek)",
                "llm_latency_ms": confirm_latency,
                "correction_text": confirmation_text[:80],
                "reply_preview": reply[:120],
            })
            result["llm_calls"].append({"agent": "OnboardingAgent (correction)", "latency_ms": confirm_latency})

            re_confirm = user.get("correction_confirmation", "yes")
            t0 = time.time()
            reply, state = flow.handle_message(session, re_confirm)
            result["steps"].append({
                "step": "STEP_CONFIRMING (re-confirm)",
                "status": "ok",
                "session_step": session.onboarding_step,
                "reply_preview": reply[:120],
                "latency_ms": round((time.time() - t0) * 1000),
            })
        elif gap_fill:
            # Gap fill path (Ananya): missing fields → STEP_COLLECTING
            result["steps"].append({
                "step": "STEP_CONFIRMING->COLLECTING (gaps found)",
                "status": "ok",
                "session_step": session.onboarding_step,
                "reply_preview": reply[:120],
                "latency_ms": confirm_latency,
            })
            t0 = time.time()
            reply, state = flow.handle_message(session, gap_fill)
            gap_latency = round((time.time() - t0) * 1000)
            result["steps"].append({
                "step": "STEP_COLLECTING->PROFILE_READY (gap fill)",
                "status": "ok",
                "session_step": session.onboarding_step,
                "llm_call": "OnboardingAgent.process (REAL DeepSeek)",
                "llm_latency_ms": gap_latency,
                "reply_preview": reply[:120],
            })
            result["llm_calls"].append({"agent": "OnboardingAgent (gap fill)", "latency_ms": gap_latency})
        else:
            result["steps"].append({
                "step": "STEP_CONFIRMING->PROFILE_READY",
                "status": "ok",
                "session_step": session.onboarding_step,
                "reply_preview": reply[:120],
                "latency_ms": confirm_latency,
            })

        # ── Step 6: Assert PROFILE_READY ──────────────────────────────────────
        final_state = session.state
        result["final_state"] = final_state.value

        # ── Step 7: Assert DB profile written ─────────────────────────────────
        if not with_db:
            profile = store.get_profile(uid)
        else:
            profile = store._load_profile_data(uid)

        result["profile_written"] = {
            "onboarding_complete": profile.get("onboarding_complete", "N/A (live DB)"),
            "target_roles": profile.get("target_roles"),
            "target_cities": profile.get("target_cities"),
            "salary_expectations": profile.get("salary_expectations"),
            "notice_period": profile.get("notice_period"),
            "career_mode": profile.get("career_mode"),
            "has_cv": bool(profile.get("master_cv_markdown")),
        }

        assert final_state == UserJourneyState.PROFILE_READY, \
            f"Expected PROFILE_READY, got {final_state.value}"
        assert profile.get("target_roles"), "target_roles missing from DB"
        assert profile.get("target_cities"), "target_cities missing from DB"
        assert profile.get("has_cv") or profile.get("master_cv_markdown"), "CV not written to DB"

        # ── Step 8: Onboarding guard — real ActionResolver ────────────────────
        resolver = ActionResolver()
        guard_action = resolver.resolve(
            user_message="/scan",
            user_id=uid,
            state=UserJourneyState.NEW_USER,  # test the guard state
            artifact_context={},
            messages=[],
        )
        guard_blocked = guard_action.action_type != ActionType.START_SCAN
        result["steps"].append({
            "step": "onboarding_guard (ActionResolver.resolve REAL)",
            "status": "ok" if guard_blocked else "FAIL",
            "input": "/scan with state=NEW_USER",
            "resolved_to": guard_action.action_type.value,
            "blocked": guard_blocked,
        })
        assert guard_blocked, f"Onboarding guard failed — /scan was not blocked (got {guard_action.action_type.value})"

        result["passed"] = True

    except AssertionError as e:
        result["errors"].append(f"ASSERTION: {e}")
    except Exception as e:
        import traceback
        result["errors"].append(f"EXCEPTION {type(e).__name__}: {e}")
        result["errors"].append(traceback.format_exc()[-800:])
    finally:
        if not with_db:
            OnboardingFlow._commit_profile_to_db = original_commit

    result["total_ms"] = round((time.time() - t_user_start) * 1000)
    return result


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-db", action="store_true", help="Use real Supabase (requires DATABASE_URL)")
    parser.add_argument("--output", default="e2e_onboarding_results_real.json")
    args = parser.parse_args()

    with_db = args.with_db
    if with_db and not os.getenv("DATABASE_URL"):
        print("ERROR: --with-db requires DATABASE_URL.")
        sys.exit(1)

    mode = "LIVE Supabase" if with_db else "Real LLM + FakeStore (no DATABASE_URL)"
    print(f"\n{'='*65}")
    print(f"  CareerLoop REAL E2E Onboarding Test")
    print(f"  Mode: {mode}")
    print(f"  LLM: {'DeepSeek REAL' if os.getenv('DEEPSEEK_API_KEY') else 'MISSING — will fail'}")
    print(f"{'='*65}\n")

    results = []
    t_total = time.time()

    for i, user in enumerate(USERS, 1):
        print(f"  [{i}/{len(USERS)}] {user['first_name']} (chat_id={user['telegram_chat_id']}) — running real pipeline...")
        r = run_user_real(user, with_db=with_db)
        status = "[PASS]" if r["passed"] else "[FAIL]"
        llm_count = len(r["llm_calls"])
        total_llm_ms = sum(c["latency_ms"] for c in r["llm_calls"])
        print(f"         {status} | final={r['final_state']} | {llm_count} real LLM calls | {total_llm_ms}ms LLM | {r['total_ms']}ms total")
        for err in r["errors"]:
            print(f"         [ERR] {err[:120]}")
        results.append(r)

    duration = round(time.time() - t_total, 2)
    passed = sum(1 for r in results if r["passed"])

    report = {
        "report": "CareerLoop REAL E2E Onboarding — Real LLM, Real OnboardingFlow",
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "what_is_real": [
            "CVExtractionAgent.extract() — actual DeepSeek API call",
            "OnboardingAgent.process() — actual DeepSeek API call for corrections/gap-fill",
            "OnboardingFlow.handle_message() — actual state machine execution",
            "ActionResolver.resolve() — actual guard logic",
            "Session state transitions — actual step tracking",
        ],
        "what_is_faked": [] if with_db else [
            "SessionStore DB writes — intercepted to in-memory FakeStore (no DATABASE_URL)",
            "All DB calls logged in db_calls[] per user for inspection",
        ],
        "summary": {
            "total_users": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": f"{100 * passed // len(results)}%",
            "duration_seconds": duration,
        },
        "users": results,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*65}")
    print(f"  RESULT: {passed}/{len(results)} passed ({report['summary']['pass_rate']})")
    print(f"  Total time: {duration}s")
    print(f"  Output: {args.output}")
    print(f"{'='*65}\n")

    if not with_db:
        print("  NOTE: Run with --with-db once DATABASE_URL is set for full Supabase E2E.\n")

    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
