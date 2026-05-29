"""E2E test for the CareerLoop API.

NO pytest (project policy). Tests two modes:

Mode A — Supabase JWT test (default)
  Mints a local test JWT signed with the TEST_JWT_SECRET env var (or a hardcoded
  test value), starts the server with that same secret, verifies all 9 routes.
  Does NOT need a real Supabase project — just checks the full request lifecycle.

Mode B — Real Supabase JWT
  Set SUPABASE_JWT_SECRET in .env to your real Supabase JWT secret, and set
  API_REAL_TOKEN to a valid Supabase access_token from a logged-in session.
  Tests that a real Google OAuth token is accepted end-to-end.

Run:
  # start server first:
  SUPABASE_JWT_SECRET=test-secret .venv/bin/uvicorn careerloop_api.main:app --port 8001
  # then:
  .venv/bin/python careerloop_api/e2e_api_test.py

Results → careerloop_api/e2e_api_results.json
"""

import json
import os
import time
import uuid

import httpx
import jwt

BASE = os.getenv("API_BASE", "http://127.0.0.1:8001")
TEST_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "test-secret")

# Supabase UUID for the test user — must match an existing careerloop.users row
# if you want /briefs/latest to return real data.
TEST_USER_ID = os.getenv("API_TEST_USER", "9c512f87-1f5b-5e58-bf23-778d97e6e0a7")
REAL_TOKEN = os.getenv("API_REAL_TOKEN", "")  # optional: a real Supabase access_token

results = []


def record(name, passed, detail):
    results.append({"test": name, "passed": passed, "detail": detail})
    flag = "PASS" if passed else "FAIL"
    print(f"[{flag}] {name} — {detail}")


def mint_test_token(user_id: str, secret: str, email: str = "test@careerloop.ai",
                    full_name: str = "Test User", expired: bool = False) -> str:
    """Mint a Supabase-shaped JWT for testing, signed with the given secret."""
    now = int(time.time())
    exp = now - 60 if expired else now + 3600
    payload = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "iat": now,
        "exp": exp,
        "user_metadata": {"full_name": full_name},
        "app_metadata": {"provider": "google"},
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def main():
    client = httpx.Client(base_url=BASE, timeout=120.0)

    # 0. health
    r = client.get("/health")
    record("health", r.status_code == 200 and r.json().get("status") == "ok",
           f"{r.status_code} {r.text[:80]}")

    # ── Auth rejection tests ──────────────────────────────────────────────────

    # 1. no token → 401
    r = client.get("/v1/me")
    record("no_token_401", r.status_code == 401, f"{r.status_code} (expected 401)")

    # 2. garbage token → 401
    r = client.get("/v1/me", headers={"Authorization": "Bearer not.a.jwt"})
    record("bad_token_401", r.status_code == 401, f"{r.status_code} (expected 401)")

    # 3. expired token → 401
    expired_tok = mint_test_token(TEST_USER_ID, TEST_JWT_SECRET, expired=True)
    r = client.get("/v1/me", headers={"Authorization": f"Bearer {expired_tok}"})
    record("expired_token_401", r.status_code == 401, f"{r.status_code} (expected 401)")

    # 4. wrong role → 401
    anon_payload = {
        "sub": str(uuid.uuid4()), "role": "anon", "aud": "authenticated",
        "iat": int(time.time()), "exp": int(time.time()) + 3600,
    }
    anon_tok = jwt.encode(anon_payload, TEST_JWT_SECRET, algorithm="HS256")
    r = client.get("/v1/me", headers={"Authorization": f"Bearer {anon_tok}"})
    record("anon_role_401", r.status_code == 401, f"{r.status_code} (expected 401, role=anon)")

    # ── Valid token tests ──────────────────────────────────────────────────────

    token = REAL_TOKEN or mint_test_token(TEST_USER_ID, TEST_JWT_SECRET)
    auth = {"Authorization": f"Bearer {token}"}

    # 5. POST /auth/me — provision + return profile
    r = client.post("/v1/auth/me", headers=auth)
    d = r.json().get("data", {}) if r.status_code == 200 else {}
    record("POST /auth/me", r.status_code == 200 and "id" in d,
           f"{r.status_code} id={d.get('id','?')[:8]} name={d.get('full_name')}")

    # 6. GET /me
    r = client.get("/v1/me", headers=auth)
    d = r.json().get("data", {}) if r.status_code == 200 else {}
    record("GET /me", r.status_code == 200 and d.get("id") == TEST_USER_ID,
           f"{r.status_code} id_match={d.get('id') == TEST_USER_ID}")

    # 7. GET /me/preferences
    r = client.get("/v1/me/preferences", headers=auth)
    record("GET /me/preferences", r.status_code == 200,
           f"{r.status_code} keys={list((r.json().get('data') or {}).keys())}")

    # 8. GET /briefs/latest
    r = client.get("/v1/briefs/latest", headers=auth)
    brief = r.json().get("data", {}) if r.status_code == 200 else {}
    items = brief.get("items", [])
    record("GET /briefs/latest", r.status_code == 200 and "brief_id" in brief,
           f"{r.status_code} brief={brief.get('brief_id','?')[:8]} items={len(items)}")
    brief_id = brief.get("brief_id")
    first_index = items[0]["item_index"] if items else None

    # 9. POST select item
    if brief_id and first_index is not None:
        r = client.post(f"/v1/briefs/{brief_id}/items/{first_index}/select", headers=auth)
        sd = r.json().get("data", {}) if r.status_code == 200 else {}
        record("POST select item", r.status_code == 200 and sd.get("active_artifact_type") == "job_card",
               f"{r.status_code} job_id={sd.get('job_id')}")
        selected_job = sd.get("job_id")
    else:
        record("POST select item", False, "no brief/item to select")
        selected_job = None

    # 10. GET /jobs/{id}
    if selected_job:
        r = client.get(f"/v1/jobs/{selected_job}", headers=auth)
        jd = r.json().get("data", {}) if r.status_code == 200 else {}
        record("GET /jobs/{id}", r.status_code == 200,
               f"{r.status_code} title={jd.get('title','?')[:40]}")
    else:
        record("GET /jobs/{id}", False, "no job selected")

    # 11. save + skip
    if selected_job:
        r = client.post(f"/v1/jobs/{selected_job}/save", headers=auth)
        record("POST /jobs/{id}/save", r.status_code in (200, 409),
               f"{r.status_code} {r.json().get('data') or r.json().get('error')}")
        r = client.post(f"/v1/jobs/{selected_job}/skip", headers=auth)
        record("POST /jobs/{id}/skip", r.status_code in (200, 409),
               f"{r.status_code} {r.json().get('data') or r.json().get('error')}")

    # 12. job not found → 404
    r = client.get("/v1/jobs/does-not-exist-xyz", headers=auth)
    record("GET /jobs/{id} 404", r.status_code == 404, f"{r.status_code} (expected 404)")

    # 13. chat/message (real LLM — slow)
    try:
        r = client.post("/v1/chat/message", headers=auth, json={"text": "what can you help me with?"})
        cd = r.json().get("data", {}) if r.status_code == 200 else {}
        msg = cd.get("message", "")
        no_echo = msg.strip().lower() != "what can you help me with?"
        record("POST /chat/message", r.status_code == 200 and bool(msg) and no_echo,
               f"{r.status_code} reply={msg[:60]!r}")
    except Exception as e:
        record("POST /chat/message", False, f"exception: {e}")

    # ── Summary ───────────────────────────────────────────────────────────────
    out = os.path.join(os.path.dirname(__file__), "e2e_api_results.json")
    passed = sum(1 for x in results if x["passed"])
    summary = {
        "total": len(results), "passed": passed, "failed": len(results) - passed,
        "results": results,
    }
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n=== {passed}/{len(results)} passed === → {out}")


if __name__ == "__main__":
    main()
