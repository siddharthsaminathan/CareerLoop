#!/usr/bin/env python3
"""
CareerLoop E2E Stress Test — Real LLM Pipeline
===============================================
Runs 2 test users through full pipeline with real DeepSeek calls.
Saves complete state-transition log to e2e_test_results.json.
"""

import os, sys, json, uuid, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
# Supabase required — verify DATABASE_URL is set
if not os.getenv("DATABASE_URL"):
    print("ERROR: DATABASE_URL must be set for Supabase E2E test.")
    sys.exit(1)
from dotenv import load_dotenv
load_dotenv()

from careerloop.session.supervisor_graph import get_supervisor_graph
from careerloop.session.states import UserJourneyState
from langchain_core.messages import HumanMessage, AIMessage

TEST_USER_1 = str(uuid.uuid4())
TEST_USER_2 = "9c512f87-1f5b-5e58-bf23-778d97e6e0a7"

OUTPUT_FILE = Path(__file__).parent / "e2e_test_results.json"
results = {"test_run": datetime.now(timezone.utc).isoformat(), "model": "deepseek-chat", "sessions": {}}


def run_session(user_id: str, user_name: str, messages: list[dict], label: str):
    graph = get_supervisor_graph(checkpointer=None)
    history = []
    turns = []

    for i, turn in enumerate(messages):
        user_msg = turn["msg"]
        history.append(HumanMessage(content=user_msg))

        state = {
            "user_id": user_id,
            "current_state": UserJourneyState.NEW_USER if i == 0 else UserJourneyState.PROFILE_READY,
            "messages": list(history),
            "artifact_context": {},
        }

        t0 = time.monotonic()
        result = graph.invoke(state)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        action = result.get("action_taken")
        reply = result.get("assistant_response", "")
        envelope = result.get("response_envelope")

        turn_data = {
            "turn": i + 1,
            "user_input": user_msg,
            "resolved_action": action.action_type.value if action else "NONE",
            "confidence": action.confidence if action else 0,
            "state_after": str(result.get("current_state", "?")),
            "response_type": envelope.response_type if envelope else "?",
            "cards_count": len(envelope.cards) if envelope and envelope.cards else 0,
            "assistant_response": reply[:600],
            "response_length": len(reply),
            "elapsed_ms": elapsed_ms,
        }
        turns.append(turn_data)

        if reply:
            history.append(AIMessage(content=reply))

        action_name = action.action_type.value if action else "???"
        preview = reply[:120].replace("\n", " ")
        print(f"  [{i+1:2d}/{len(messages)}] {action_name:25s} | {preview}")

    # Behavior checks
    chat_turns = [t for t in turns if t["resolved_action"] == "GENERAL_CHAT"]
    slash_turns = [t for t in turns if t["user_input"].startswith("/")]
    mid_turns = turns[len(turns)//2:]

    results["sessions"][label] = {
        "user_name": user_name,
        "total_turns": len(turns),
        "turns": turns,
        "behavior_checks": {
            "general_chat_no_echo": all(t["user_input"] not in t["assistant_response"] for t in chat_turns),
            "slash_confidence_1.0": all(t["confidence"] == 1.0 for t in slash_turns),
            "state_stable_mid_session": all("NEW_USER" not in str(t["state_after"]) for t in mid_turns),
        },
    }


# ═══════════════════════════════════════════════════════════════
#  SESSION 1: Shayagreev Shivkumar — New User Onboarding
# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("  SESSION 1: Shayagreev Shivkumar (New User)")
print("=" * 60)

run_session(TEST_USER_1, "Shayagreev Shivkumar", [
    {"msg": "Hi, I'm Shayagreev Shivkumar. I'm an ML engineer with 5 years experience."},
    {"msg": "I want ML Engineer or Applied AI Engineer roles in Bangalore, Chennai, Mumbai."},
    {"msg": "Salary: 30-40 LPA. Notice: 1 month. I'm selective — quality over quantity."},
    {"msg": "/status"},
    {"msg": "do you have any jobs for me?"},
    {"msg": "ok thanks, I'll come back later for a scan"},
], "shayagreev_onboarding")


# ═══════════════════════════════════════════════════════════════
#  SESSION 2: Siddharth Saminathan — Active User
# ═══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("  SESSION 2: Siddharth Saminathan (Active)")
print("=" * 60)

run_session(TEST_USER_2, "Siddharth Saminathan", [
    {"msg": "/status"},
    {"msg": "give me my daily briefing"},
    {"msg": "match me with new jobs — find me something fresh"},
    {"msg": "/help"},
    {"msg": "what's in my pipeline right now?"},
    {"msg": "tell me about the company for my top match"},
    {"msg": "who should I reach out to there?"},
    {"msg": "prepare an application pack for this"},
    {"msg": "skip this one"},
    {"msg": "thanks, that's enough for today"},
], "siddharth_active")


# ═══════════════════════════════════════════════════════════════
#  Save
# ═══════════════════════════════════════════════════════════════
results["summary"] = {
    "total_sessions": len(results["sessions"]),
    "total_turns": sum(s["total_turns"] for s in results["sessions"].values()),
}

with open(OUTPUT_FILE, "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print()
print("=" * 60)
print(f"  SAVED: {OUTPUT_FILE}")
print(f"  Sessions: {results['summary']['total_sessions']} | Turns: {results['summary']['total_turns']}")
print("=" * 60)
