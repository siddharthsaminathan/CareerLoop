#!/usr/bin/env python3
"""
CareerLoop E2E smoke test:
- Supabase/Postgres reachability
- session table read/write
- onboarding router state transition
- supervisor graph routing via transport adapter
- PostgresSaver checkpointer setup
"""

import os
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import psycopg2
from dotenv import load_dotenv

from careerloop.memory.checkpointer import get_checkpointer
from careerloop.session.message_router import MessageRouter
from careerloop.session.session_store import SessionStore
from careerloop.session.states import UserState
from careerloop.session.supervisor_graph import get_supervisor_graph
from careerloop.transport.base import TransportAdapter, UserEvent


def _ok(msg: str) -> None:
    print(f"[PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}")


def _must(condition: bool, pass_msg: str, fail_msg: str) -> None:
    if condition:
        _ok(pass_msg)
    else:
        _fail(fail_msg)
        raise RuntimeError(fail_msg)


def _load_env() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    load_dotenv(os.path.join(root, ".env"))


def _test_db_connectivity() -> None:
    db_url = os.getenv("DATABASE_URL")
    _must(bool(db_url), "DATABASE_URL is present.", "DATABASE_URL is missing.")

    conn = psycopg2.connect(db_url, connect_timeout=8)
    cur = conn.cursor()
    cur.execute("select 1;")
    row = cur.fetchone()
    _must(row and row[0] == 1, "Postgres query returned 1.", "Postgres query failed.")
    cur.execute("select to_regclass('public.sessions');")
    reg = cur.fetchone()
    _must(reg and reg[0] == "sessions", "public.sessions table exists.", "public.sessions table missing.")
    conn.close()


def _stable_uuid_for_email(email: str) -> str:
    namespace = uuid.UUID("12345678-1234-5678-1234-567812345678")
    return str(uuid.uuid5(namespace, email))


def _upsert_user_row(user_id: str, email: str) -> None:
    db_url = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(db_url, connect_timeout=8)
    cur = conn.cursor()
    cur.execute(
        """
        insert into public.users (id, email, full_name)
        values (%s, %s, %s)
        on conflict (id) do nothing
        """,
        (user_id, email, email.split("@")[0]),
    )
    conn.commit()
    conn.close()
    _ok("User upsert succeeded.")


@dataclass
class CaptureTransport(TransportAdapter):
    supervisor_graph: Any = None

    def __post_init__(self) -> None:
        self.sent = []

    def parse_payload(self, raw_payload: Dict[str, Any]) -> Optional[UserEvent]:
        return UserEvent(
            user_id=raw_payload["user_id"],
            text=raw_payload.get("text", ""),
            platform="smoke",
            metadata=raw_payload.get("metadata", {}),
        )

    def send_text(self, user_id: str, text: str) -> bool:
        self.sent.append((user_id, text))
        return True

    def request_input(self, user_id: str, prompt_text: str = "") -> str:
        return ""


def _patch_onboarding_agent(router: MessageRouter) -> None:
    def fake_process(user_message: str, current_data: Dict[str, Any]):
        # Deterministic onboarding completion in one user message.
        updated = dict(current_data)
        updated.update(
            {
                "cv_content": "Senior engineer with platform and AI delivery experience.",
                "target_roles": "AI Product Engineer, Applied AI Engineer",
                "target_cities": "Bangalore, Remote",
                "salary_expectations": "50-70 LPA",
                "notice_period": "Immediate",
                "aggressiveness": "Highly selective",
            }
        )
        reply = "Captured profile details. Finalizing setup."
        return updated, reply, True

    router.onboarding.agent.process = fake_process


def _test_router_and_session(user_id: str) -> None:
    session_store = SessionStore()
    transport = CaptureTransport()
    router = MessageRouter(session_store, transport)
    _patch_onboarding_agent(router)

    # Step 1: user lands in IDLE, first message starts onboarding.
    router.handle_incoming(user_id, "")
    s1 = session_store.get_session(user_id)
    _must(
        s1.state == UserState.ONBOARDING_WAITING_CV,
        "Session moved IDLE -> ONBOARDING_WAITING_CV.",
        f"Unexpected state after kickoff: {s1.state}",
    )

    # Step 2: user provides one message, fake onboarding agent completes profile.
    router.handle_incoming(user_id, "Here is my profile data")
    s2 = session_store.get_session(user_id)
    _must(
        s2.state == UserState.PROFILE_COMPLETE,
        "Session moved ONBOARDING -> PROFILE_COMPLETE.",
        f"Unexpected state after onboarding completion: {s2.state}",
    )
    _must(
        s2.temp_profile_data is None,
        "Temporary onboarding profile data was cleared.",
        "Temporary onboarding profile data was not cleared.",
    )
    _must(len(transport.sent) >= 2, "Router produced chat responses.", "Router produced no chat responses.")


def _test_supervisor_transport_contract(user_id: str) -> None:
    graph = get_supervisor_graph()
    transport = CaptureTransport(supervisor_graph=graph)

    # Route a simple message through receive() and ensure assistant text comes back.
    transport.receive({"user_id": user_id, "text": "hello"})
    _must(len(transport.sent) >= 1, "Supervisor returned an assistant response.", "Supervisor returned no response.")
    _must(
        "Welcome to CareerLoop" in transport.sent[-1][1],
        "Supervisor produced onboarding guidance.",
        f"Unexpected supervisor response: {transport.sent[-1][1]}",
    )

    # Validate safe behavior for pack request without council input.
    transport.receive(
        {
            "user_id": user_id,
            "text": "please build pack",
            "metadata": {"current_state": UserState.IDLE},
        }
    )
    _must(
        any(
            ("Preparing your application pack" in msg)
            or ("Cannot build a pack yet" in msg)
            for _, msg in transport.sent
        ),
        "Supervisor handled pack intent safely (acknowledged or blocked on missing council input).",
        "Supervisor did not acknowledge or safely block pack intent.",
    )


def _test_checkpointer() -> None:
    with get_checkpointer() as cp:
        _must(cp is not None, "PostgresSaver checkpointer setup succeeded.", "PostgresSaver setup failed.")


def main() -> int:
    try:
        _load_env()
        print("Running CareerLoop end-to-end smoke test...")

        _test_db_connectivity()

        run_tag = uuid.uuid4().hex[:8]
        email = f"smoke.test.{run_tag}@careerloop.ai"
        user_id = _stable_uuid_for_email(email)
        _upsert_user_row(user_id, email)
        _ok(f"Stable login UUID generated: {user_id}")

        _test_router_and_session(user_id)
        _test_supervisor_transport_contract(user_id)
        _test_checkpointer()

        print("\n[PASS] E2E smoke test completed successfully.")
        return 0
    except Exception as e:
        _fail(f"E2E smoke test failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
