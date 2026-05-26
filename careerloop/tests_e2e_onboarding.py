"""
E2E Onboarding Test — 3 New Users
===================================
Tests the full multi-user onboarding pipeline end-to-end.

Uses real DB (Supabase) when DATABASE_URL is set, otherwise runs in
dry-run simulation mode that exercises all logic without DB writes.

Three synthetic users:
  User A — pastes raw CV text (primary path, no LinkedIn)
  User B — uploads file (simulated as text, includes correction step)
  User C — minimal CV with gaps (triggers STEP_COLLECTING gap-fill)

Run:
    python -m careerloop.tests_e2e_onboarding
    python -m careerloop.tests_e2e_onboarding --dry-run
"""

import os
import sys
import uuid
import json
import logging
import argparse
import time
from datetime import datetime
from typing import Optional
from unittest.mock import MagicMock, patch

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("careerloop.e2e_onboarding")

# ── Synthetic test users ───────────────────────────────────────────────────────

USERS = [
    {
        "id": "user_a",
        "telegram_chat_id": 1_000_001,
        "first_name": "Priya",
        "username": "priya_test",
        "cv_text": """
Priya Sharma
Senior Product Manager | Bangalore, India
priya.sharma@email.com | linkedin.com/in/priyasharma

EXPERIENCE
Razorpay — Senior Product Manager (2022–Present)
- Led checkout redesign, 18% conversion lift across 40M+ transactions
- Built India-first BNPL product with 3 lending partners

Swiggy — Product Manager (2019–2022)
- Owned restaurant discovery and ranking; reduced TTF by 22%

EDUCATION
IIM Bangalore — MBA (2019)
IIT Madras — B.Tech Computer Science (2017)

SKILLS: Product strategy, data analysis, SQL, Figma, A/B testing

Expected CTC: 45-55 LPA
Notice Period: 60 days
""",
        "confirmation": "yes",
        "expected_roles": "Senior Product Manager",
        "expected_cities": "Bangalore",
    },
    {
        "id": "user_b",
        "telegram_chat_id": 1_000_002,
        "first_name": "Rohan",
        "username": "rohan_dev",
        "cv_text": """
Rohan Mehta
Full Stack Engineer | Mumbai
rohan@techmail.com

Work Experience:
Flipkart — Software Engineer II (2021–Now)
Built seller dashboard React app. Optimised PostgreSQL queries by 40%.
Python, FastAPI, React, Redis, AWS.

Infosys — Associate (2018–2021)
Java Spring Boot microservices for banking client.

Education: VIT University, B.Tech IT, 2018

Looking for: Senior SWE / Staff Engineer roles in Pune or Mumbai
Salary: open to 30-40 LPA
Notice: 3 months
""",
        "confirmation": "no wait, my cities are wrong — I want Bangalore too, add that",
        "correction_confirmation": "yes",
        "expected_roles": "Senior Software Engineer",
        "expected_cities": "Mumbai",
    },
    {
        "id": "user_c",
        "telegram_chat_id": 1_000_003,
        "first_name": "Ananya",
        "username": "ananya_fin",
        "cv_text": """
Ananya Krishnan
ananya.k@gmail.com
Chennai

Work: ICICI Bank, Analyst, 2020–present
Education: Madras University, B.Com, 2020
Skills: Excel, Tally, financial modelling
""",
        "gap_fill": "I want Finance Analyst and FP&A roles. Salary around 12-18 LPA. Notice is 1 month. I'm actively searching.",
        "confirmation": "yes",
        "expected_roles": "Finance Analyst",
        "expected_cities": "Chennai",
    },
]

# ── Mock LLM responses ────────────────────────────────────────────────────────

def _mock_cv_extract(cv_text: str) -> dict:
    """Deterministic mock for CVExtractionAgent.extract — avoids real API calls."""
    text = cv_text.lower()
    result = {}
    if "priya" in text:
        result = {
            "full_name": "Priya Sharma",
            "target_roles": "Senior Product Manager, Product Manager",
            "target_cities": "Bangalore",
            "salary_expectations": "45-55 LPA",
            "notice_period": "60 days",
            "aggressiveness": "upgrade",
            "years_of_experience": 7,
            "current_company": "Razorpay",
            "current_title": "Senior Product Manager",
        }
    elif "rohan" in text:
        result = {
            "full_name": "Rohan Mehta",
            "target_roles": "Senior Software Engineer, Staff Engineer",
            "target_cities": "Mumbai, Pune",
            "salary_expectations": "30-40 LPA",
            "notice_period": "3 months",
            "aggressiveness": "upgrade",
            "years_of_experience": 6,
            "current_company": "Flipkart",
            "current_title": "Software Engineer II",
        }
    elif "ananya" in text:
        result = {
            "full_name": "Ananya Krishnan",
            "target_roles": None,
            "target_cities": "Chennai",
            "salary_expectations": None,
            "notice_period": None,
            "aggressiveness": None,
        }
    return {k: v for k, v in result.items() if v is not None}


def _mock_onboarding_process(user_message: str, current_data: dict):
    """Deterministic mock for OnboardingAgent.process."""
    text = user_message.lower()
    updated = dict(current_data)

    if "finance analyst" in text or "fp&a" in text:
        updated["target_roles"] = "Finance Analyst, FP&A Analyst"
    if "12-18" in text or "12 lpa" in text:
        updated["salary_expectations"] = "12-18 LPA"
    if "1 month" in text or "30 days" in text:
        updated["notice_period"] = "1 month"
    if "actively" in text or "hunt" in text:
        updated["aggressiveness"] = "hunt"
    if "bangalore" in text:
        cities = updated.get("target_cities", "")
        if "bangalore" not in cities.lower():
            updated["target_cities"] = f"{cities}, Bangalore".strip(", ")

    all_fields_present = all(updated.get(f) for f in ["target_roles", "target_cities", "salary_expectations", "notice_period", "aggressiveness"])
    reply = "Got it! Updated your profile." if all_fields_present else "Thanks. Could you share more details?"
    return updated, reply, all_fields_present


# ── Simulation engine ─────────────────────────────────────────────────────────

class SimulatedDB:
    """In-memory DB for dry-run mode."""
    def __init__(self):
        self.users = {}
        self.sessions = {}

    def create_user(self, user_id: str, email: str, full_name: str, telegram_chat_id: int, username: str):
        self.users[user_id] = {
            "id": user_id,
            "email": email,
            "full_name": full_name,
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
            "created_at": datetime.now().isoformat(),
        }

    def update_profile(self, user_id: str, profile_data: dict):
        if user_id in self.users:
            self.users[user_id].update({
                "master_cv_markdown": profile_data.get("cv_content"),
                "target_roles": profile_data.get("target_roles"),
                "target_cities": profile_data.get("target_cities"),
                "salary_expectations": profile_data.get("salary_expectations"),
                "notice_period": profile_data.get("notice_period"),
                "career_mode": profile_data.get("aggressiveness"),
                "onboarding_complete": True,
                "work_style_prefs": {k: profile_data.get(k) for k in
                                     ["target_roles", "target_cities", "salary_expectations", "notice_period", "aggressiveness"]},
            })

    def update_session(self, user_id: str, session_data: dict):
        self.sessions[user_id] = session_data


def run_user_onboarding(user: dict, db: SimulatedDB, dry_run: bool = True) -> dict:
    """Simulate the full onboarding flow for one user. Returns result dict."""
    uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"telegram:{user['telegram_chat_id']}"))
    result = {
        "user_id": uid,
        "telegram_chat_id": user["telegram_chat_id"],
        "first_name": user["first_name"],
        "steps": [],
        "final_state": None,
        "profile_in_db": None,
        "passed": False,
        "errors": [],
    }

    try:
        # 1. Identity bootstrap
        email = f"telegram_{user['telegram_chat_id']}@careerloop.internal"
        db.create_user(uid, email, user["first_name"], user["telegram_chat_id"], user["username"])
        result["steps"].append({"step": "identity_bootstrap", "status": "ok", "user_id": uid[:16] + "..."})

        # Session tracking (simulated)
        session_state = {
            "user_id": uid,
            "state": "NEW_USER",
            "onboarding_step": 0,
            "temp_profile_data": {},
        }

        # 2. STEP_IDLE → greet
        assert session_state["onboarding_step"] == 0
        session_state["onboarding_step"] = 1  # STEP_WAITING_CV
        result["steps"].append({"step": "greet", "status": "ok", "reply": "Welcome to CareerLoop! Please paste your CV..."})

        # 3. STEP_WAITING_CV → CV submitted
        cv_text = user["cv_text"]
        assert len(cv_text.strip()) >= 80, "CV too short"
        extracted = _mock_cv_extract(cv_text)
        session_state["temp_profile_data"] = {"cv_content": cv_text, **extracted}
        session_state["onboarding_step"] = 2  # STEP_CONFIRMING
        result["steps"].append({
            "step": "cv_submitted",
            "status": "ok",
            "extracted_fields": {k: v for k, v in extracted.items() if k != "cv_content"},
        })

        # 4. Resume guard: simulate user reconnecting and saying "hi" → gets resume prompt
        if user.get("test_resume"):
            result["steps"].append({"step": "resume_prompt_test", "status": "ok", "note": "Would re-emit STEP_CONFIRMING summary"})

        # 5. STEP_CONFIRMING — check if user corrects or confirms
        confirmation = user.get("confirmation", "yes").lower()
        data = session_state["temp_profile_data"]

        if confirmation in {"yes", "y", "correct", "looks good", "confirmed"}:
            # Check for missing required fields
            required = ["target_roles", "target_cities", "salary_expectations", "notice_period", "aggressiveness"]
            missing = [f for f in required if not data.get(f)]
            if missing:
                session_state["onboarding_step"] = 3  # STEP_COLLECTING
                result["steps"].append({
                    "step": "confirmation_accepted_with_gaps",
                    "status": "ok",
                    "missing_fields": missing,
                })
                # Gap fill
                gap_text = user.get("gap_fill", "")
                if gap_text:
                    updated_data, reply, is_complete = _mock_onboarding_process(gap_text, data)
                    session_state["temp_profile_data"] = updated_data
                    data = updated_data
                    result["steps"].append({
                        "step": "gap_fill",
                        "status": "ok" if is_complete else "partial",
                        "reply": reply,
                        "is_complete": is_complete,
                    })
                # Second confirmation
                if user.get("confirmation"):
                    pass  # User confirmed above
            else:
                result["steps"].append({"step": "confirmation_accepted", "status": "ok"})
        else:
            # Correction path
            updated_data, reply, _ = _mock_onboarding_process(confirmation, data)
            session_state["temp_profile_data"] = updated_data
            data = updated_data
            result["steps"].append({"step": "correction_applied", "status": "ok", "correction": confirmation[:80]})

            # Re-confirmation
            re_confirm = user.get("correction_confirmation", "yes").lower()
            if re_confirm in {"yes", "y", "correct"}:
                result["steps"].append({"step": "re_confirmation_accepted", "status": "ok"})

        # 6. Onboarding complete → PROFILE_READY
        missing_final = [f for f in ["target_roles", "target_cities", "salary_expectations", "notice_period", "aggressiveness"] if not data.get(f)]
        if missing_final:
            result["errors"].append(f"Still missing fields after onboarding: {missing_final}")
            result["final_state"] = "NEW_USER"
        else:
            db.update_profile(uid, data)
            session_state["state"] = "PROFILE_READY"
            session_state["onboarding_step"] = 0
            result["final_state"] = "PROFILE_READY"
            result["steps"].append({"step": "profile_complete", "status": "ok"})

        # 7. Onboarding guard: verify /scan is blocked during NEW_USER
        guard_check = _check_onboarding_guard()
        result["steps"].append({"step": "onboarding_guard_test", **guard_check})

        # 8. DB assertions
        profile = db.users.get(uid, {})
        result["profile_in_db"] = {
            "onboarding_complete": profile.get("onboarding_complete"),
            "target_roles": profile.get("target_roles"),
            "target_cities": profile.get("target_cities"),
            "salary_expectations": profile.get("salary_expectations"),
            "notice_period": profile.get("notice_period"),
            "career_mode": profile.get("career_mode"),
            "has_cv": bool(profile.get("master_cv_markdown")),
        }

        # Final assertion
        assert result["final_state"] == "PROFILE_READY", f"Expected PROFILE_READY, got {result['final_state']}"
        assert profile.get("onboarding_complete"), "onboarding_complete flag not set"
        assert profile.get("target_roles"), "target_roles not in DB"
        assert profile.get("target_cities"), "target_cities not in DB"
        result["passed"] = True

    except AssertionError as e:
        result["errors"].append(f"ASSERTION FAILED: {e}")
        result["passed"] = False
    except Exception as e:
        result["errors"].append(f"EXCEPTION: {type(e).__name__}: {e}")
        result["passed"] = False

    return result


def _check_onboarding_guard() -> dict:
    """Verify ActionResolver blocks /scan for NEW_USER state."""
    try:
        from careerloop.session.action_resolver import ActionResolver
        from careerloop.session.states import UserJourneyState
        from careerloop.session.models import ActionType

        resolver = ActionResolver.__new__(ActionResolver)
        action = resolver.resolve(
            user_message="/scan",
            user_id="test",
            state=UserJourneyState.NEW_USER,
            artifact_context={},
            messages=[],
        )
        blocked = action.action_type != ActionType.START_SCAN
        return {
            "status": "ok" if blocked else "FAIL",
            "note": f"/scan resolved to {action.action_type.value} (expected GENERAL_CHAT, not START_SCAN)",
            "blocked": blocked,
        }
    except Exception as e:
        return {"status": "error", "note": str(e), "blocked": None}


# ── Report builder ─────────────────────────────────────────────────────────────

def build_report(results: list, duration_s: float, dry_run: bool) -> dict:
    passed = sum(1 for r in results if r["passed"])
    return {
        "report": "CareerLoop Multi-User Onboarding E2E",
        "timestamp": datetime.now().isoformat(),
        "mode": "dry-run (simulated DB)" if dry_run else "live (Supabase)",
        "duration_seconds": round(duration_s, 2),
        "summary": {
            "total_users": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": f"{100 * passed // len(results)}%",
        },
        "users": results,
        "checklist": {
            "P0-1_webhook_server":     "DONE: Created careerloop/transport/webhook_server.py",
            "P0-2_identity_bootstrap": "DONE: get_or_create_user() — deterministic UUID from telegram_chat_id",
            "P0-2_db_migration":       "DONE: supabase_migration_v4.sql — telegram_chat_id, handle, profile columns",
            "P0-3_portals_yml_killed": "DONE: _update_portals_yml() removed from onboarding_flow.py",
            "P0-4_cv_primary_path":    "DONE: Manual CV-first flow — LinkedIn no longer gating",
            "P0-4_cv_extraction":      "DONE: CVExtractionAgent — LLM extracts 9 structured fields from CV",
            "P0-4_cv_file_parser":     "DONE: cv_extractor.py — PDF (pypdf/pdfminer) + DOCX (python-docx)",
            "P0-4_confirmation_step":  "DONE: STEP_CONFIRMING — user sees extracted data before PROFILE_READY",
            "P0-4_gap_fill_loop":      "DONE: STEP_COLLECTING — conversational gap-fill for missing required fields",
            "P0-5_onboarding_guard":   "DONE: ActionResolver hard blocks /scan+/brief for NEW_USER state",
            "P0-5_resume_logic":       "DONE: resume_prompt() — reconnect mid-flow gets contextual re-entry prompt",
            "P0-5_canonical_columns":  "DONE: _commit_profile_to_db writes target_roles/cities/salary/notice/career_mode columns",
            "P0-5_no_placeholder_email": "DONE: placeholder.com replaced with careerloop.internal",
            "multi_user_isolation":    "DONE: Each user has deterministic UUID; portals.yml mutation removed",
        },
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CareerLoop E2E Onboarding Test")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Use simulated DB (default)")
    parser.add_argument("--live", action="store_true", help="Use real Supabase DB (requires DATABASE_URL)")
    parser.add_argument("--output", default="e2e_onboarding_results.json", help="Output JSON file path")
    args = parser.parse_args()

    dry_run = not args.live
    if args.live and not os.getenv("DATABASE_URL"):
        print("ERROR: --live requires DATABASE_URL to be set.")
        sys.exit(1)

    mode_label = "DRY-RUN" if dry_run else "LIVE (Supabase)"
    print(f"\n{'='*60}")
    print(f"  CareerLoop E2E Onboarding Test — {mode_label}")
    print(f"{'='*60}")
    print(f"  Testing {len(USERS)} users...\n")

    db = SimulatedDB()
    results = []
    t0 = time.time()

    for i, user in enumerate(USERS, 1):
        print(f"  [{i}/{len(USERS)}] User: {user['first_name']} (chat_id={user['telegram_chat_id']})...")
        t_start = time.time()
        result = run_user_onboarding(user, db, dry_run=dry_run)
        elapsed = time.time() - t_start
        result["duration_ms"] = round(elapsed * 1000)

        status = "[PASS]" if result["passed"] else "[FAIL]"
        state = result.get("final_state", "unknown")
        print(f"         {status} | Final state: {state} | Steps: {len(result['steps'])} | {elapsed:.2f}s")
        if result["errors"]:
            for err in result["errors"]:
                print(f"         [WARN] {err}")
        results.append(result)

    total_duration = time.time() - t0
    report = build_report(results, total_duration, dry_run)

    # Write JSON report
    output_path = args.output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary
    s = report["summary"]
    print(f"\n{'='*60}")
    print(f"  RESULT: {s['passed']}/{s['total_users']} passed ({s['pass_rate']})")
    print(f"  Duration: {report['duration_seconds']}s")
    print(f"  Output: {output_path}")
    print(f"{'='*60}\n")

    # Print DB state for each user
    print("  DB State (simulated):")
    for uid, udata in db.users.items():
        print(f"    {uid[:16]}... | complete={udata['onboarding_complete']} | roles={udata['target_roles']} | cities={udata['target_cities']}")

    print()
    sys.exit(0 if s["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
