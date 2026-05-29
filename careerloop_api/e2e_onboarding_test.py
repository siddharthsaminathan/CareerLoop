"""E2E: brand-new user onboarding through the REST API (real DeepSeek, real Supabase).

NO pytest. Simulates a fresh Google OAuth user:
  1. Mint a Supabase JWT for a brand-new random UUID (no existing row)
  2. POST /v1/auth/me           → provisions careerloop.users (onboarding_complete=false)
  3. POST /v1/chat/message "hi" → NEW_USER → OnboardingFlow asks for CV
  4. POST /v1/chat/message <CV> → extracts fields, asks to confirm
  5. POST /v1/chat/message "yes"→ completes OR asks for missing fields
  6. (gap-fill if needed)       → PROFILE_READY
  7. Verify careerloop.users.onboarding_complete = true in the DB
  8. Clean up the test user

Run (server must be up with the real SUPABASE_JWT_SECRET):
  export SUPABASE_JWT_SECRET=$(grep SUPABASE_JWT_SECRET .env | cut -d= -f2-)
  .venv/bin/python careerloop_api/e2e_onboarding_test.py
"""

import os
import time
import uuid

import httpx
import jwt
import psycopg2
from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("API_BASE", "http://127.0.0.1:8001")
SECRET = os.environ["SUPABASE_JWT_SECRET"]
DB_URL = os.environ["DATABASE_URL"]

NEW_USER_ID = str(uuid.uuid4())
NEW_EMAIL = f"e2e-onboard-{NEW_USER_ID[:8]}@careerloop.test"

SAMPLE_CV = """
Priya Sharma
Senior Machine Learning Engineer — Bangalore, India
priya.sharma@example.com

SUMMARY
ML engineer with 6 years building production NLP and recommendation systems.
Led a team of 4 shipping LLM-based features at a fintech scale-up.

EXPERIENCE
Senior ML Engineer, FinScale (2021-present), Bangalore
- Built an LLM document-extraction pipeline processing 2M docs/month.
- Cut model inference cost 40% via quantization and batching.

ML Engineer, DataNova (2018-2021), Bangalore
- Built a recommendation engine lifting engagement 18%.

SKILLS
Python, PyTorch, LLMs, RAG, AWS, Kubernetes, SQL

EDUCATION
B.Tech Computer Science, NIT Trichy, 2018
"""


def mint(user_id):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id, "email": NEW_EMAIL, "role": "authenticated",
            "aud": "authenticated", "iat": now, "exp": now + 3600,
            "user_metadata": {"full_name": "Priya Sharma"},
            "app_metadata": {"provider": "google"},
        },
        SECRET, algorithm="HS256",
    )


def show(label, r):
    try:
        body = r.json()
    except Exception:
        body = r.text
    msg = ""
    if isinstance(body, dict):
        msg = (body.get("data") or {}).get("message", "") if body.get("ok") else str(body.get("error"))
    print(f"\n--- {label} [{r.status_code}] ---")
    print((msg or str(body))[:400])
    return body


def db_user_state(user_id):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT onboarding_complete, full_name FROM careerloop.users WHERE id=%s", (user_id,))
    row = cur.fetchone()
    cur.execute("SELECT state FROM careerloop.sessions WHERE user_id=%s", (user_id,))
    srow = cur.fetchone()
    conn.close()
    return {"onboarding_complete": row[0] if row else None,
            "full_name": row[1] if row else None,
            "session_state": srow[0] if srow else None}


def cleanup(user_id):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    for tbl in ("careerloop.sessions", "careerloop.users"):
        col = "user_id" if "sessions" in tbl else "id"
        try:
            cur.execute(f"DELETE FROM {tbl} WHERE {col}=%s", (user_id,))
        except Exception as e:
            print(f"cleanup {tbl}: {e}")
    conn.commit()
    conn.close()


def main():
    client = httpx.Client(base_url=BASE, timeout=180.0)
    token = mint(NEW_USER_ID)
    auth = {"Authorization": f"Bearer {token}"}
    passed = []

    print(f"New user: {NEW_USER_ID}")

    # 1. provision
    b = show("POST /auth/me (provision)", client.post("/v1/auth/me", headers=auth))
    prov_ok = b.get("ok") and b["data"]["id"] == NEW_USER_ID and b["data"]["onboarding_complete"] is False
    passed.append(("provision new user", prov_ok))

    st = db_user_state(NEW_USER_ID)
    print("DB state after provision:", st)
    passed.append(("user row created, onboarding_complete=false", st["onboarding_complete"] is False))

    # 2. first chat "hi" → onboarding welcome, asks for CV
    b = show("chat: 'hi'", client.post("/v1/chat/message", headers=auth, json={"text": "hi"}))
    msg = (b.get("data") or {}).get("message", "").lower()
    asks_cv = "cv" in msg or "resume" in msg
    state_new = (b.get("data") or {}).get("state") == "NEW_USER"
    passed.append(("first message routes to onboarding (asks for CV)", asks_cv and state_new))

    # 3. paste CV → extract + confirm
    b = show("chat: <CV paste>", client.post("/v1/chat/message", headers=auth, json={"text": SAMPLE_CV}))
    msg = (b.get("data") or {}).get("message", "").lower()
    confirms = "yes" in msg or "confirm" in msg or "correct" in msg or "extracted" in msg
    passed.append(("CV accepted → confirmation prompt", confirms))

    # 4. confirm "yes" → complete or gap-fill
    b = show("chat: 'yes'", client.post("/v1/chat/message", headers=auth, json={"text": "yes"}))
    msg = (b.get("data") or {}).get("message", "")
    state = (b.get("data") or {}).get("state")

    # 5. gap-fill if still NEW_USER
    if state == "NEW_USER":
        gap_answer = "Target roles: Senior ML Engineer. Cities: Bangalore, Remote. Salary: 40-55 LPA. Notice: 60 days. Mode: aggressive."
        b = show("chat: <gap-fill details>", client.post("/v1/chat/message", headers=auth, json={"text": gap_answer}))
        state = (b.get("data") or {}).get("state")
        # one more confirm if needed
        if state == "NEW_USER":
            b = show("chat: 'yes' (final)", client.post("/v1/chat/message", headers=auth, json={"text": "yes"}))
            state = (b.get("data") or {}).get("state")

    passed.append(("onboarding reaches PROFILE_READY", state == "PROFILE_READY"))

    # 6. verify DB
    final = db_user_state(NEW_USER_ID)
    print("\nFinal DB state:", final)
    passed.append(("DB onboarding_complete=true", final["onboarding_complete"] is True))
    passed.append(("DB session state PROFILE_READY", final["session_state"] == "PROFILE_READY"))

    # summary
    print("\n=== ONBOARDING E2E RESULTS ===")
    for name, ok in passed:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    n_pass = sum(1 for _, ok in passed if ok)
    print(f"\n{n_pass}/{len(passed)} passed")

    cleanup(NEW_USER_ID)
    print(f"Cleaned up test user {NEW_USER_ID[:8]}")


if __name__ == "__main__":
    main()
