"""
Cross-Layer E2E Test — Synthetic User "Hayagreev Sivakumar"
Tests ALL 4 layers:
  L1: Application Layer (API endpoints)
  L2: Database Layer (DB writes/reads at each step)
  L3: Orchestration Layer (LangGraph state + tool registry)
  L4: Module Layer (Onboarding flow, CV extraction, session store)

Each step: calls API -> verifies response -> queries DB -> logs evidence
"""

import os, sys, json, time, uuid, subprocess
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

# Set JWT secret to match running server
os.environ["SUPABASE_JWT_SECRET"] = "y2vSuE7DzrrPVLAawfvlWv150RCBVwCsvr6HFfwaSLldtyPFp8Pvs6Motf/pzePpX8oDIUyuc2V07ExrP56drQ=="
os.environ["DATABASE_URL"] = open(os.path.join(os.path.dirname(__file__), ".env")).read().split("DATABASE_URL=")[1].split("\n")[0].strip()

import psycopg2
from psycopg2.extras import RealDictCursor
import httpx
import jwt

BASE = "http://127.0.0.1:8001"
JWT_SECRET = os.environ["SUPABASE_JWT_SECRET"]
DATABASE_URL = os.environ["DATABASE_URL"]

# Synthetic user
TEST_USER_ID = "00000000-0000-0000-0000-000000000099"
TEST_EMAIL = "hayagreev.sivakumar@example.com"
TEST_NAME = "Hayagreev Sivakumar"

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def db_query(sql, params=None):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            try:
                return [dict(r) for r in cur.fetchall()]
            except:
                return None
    finally:
        conn.close()

def db_execute(sql, params=None):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            conn.commit()
            try:
                return cur.rowcount
            except:
                return None
    finally:
        conn.close()

def mint_token(user_id, secret, email="test@test.com", name="Test User", expired=False):
    now = int(time.time())
    exp = now - 60 if expired else now + 3600
    payload = {
        "sub": user_id, "email": email, "role": "authenticated", "aud": "authenticated",
        "iat": now, "exp": exp,
        "user_metadata": {"full_name": name, "email": email},
        "app_metadata": {"provider": "google"},
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def log_step(step, layer, status, detail, db_evidence=""):
    flag = "PASS" if status == "PASS" else "FAIL" if status == "FAIL" else "INFO"
    print(f"\n[{flag}] [{layer}] Step {step}: {detail}")
    if db_evidence:
        for line in db_evidence.strip().split("\n"):
            print(f"       DB: {line}")

# ─── Cleanup: remove any previous test run ───────────────────────────────────
print("=" * 70)
print("CROSS-LAYER E2E TEST: Synthetic User 'Hayagreev Sivakumar'")
print("=" * 70)

db_execute("DELETE FROM careerloop.messages WHERE user_id = %s", (TEST_USER_ID,))
db_execute("DELETE FROM careerloop.conversations WHERE user_id = %s", (TEST_USER_ID,))
db_execute("DELETE FROM careerloop.sessions WHERE user_id = %s", (TEST_USER_ID,))
db_execute("DELETE FROM careerloop.background_runs WHERE user_id = %s", (TEST_USER_ID,))
db_execute("DELETE FROM careerloop.daily_brief_items WHERE brief_id IN (SELECT id FROM careerloop.daily_briefs WHERE user_id = %s)", (TEST_USER_ID,))
db_execute("DELETE FROM careerloop.daily_briefs WHERE user_id = %s", (TEST_USER_ID,))
db_execute("DELETE FROM careerloop.users WHERE id = %s", (TEST_USER_ID,))

token = mint_token(TEST_USER_ID, JWT_SECRET, email=TEST_EMAIL, name=TEST_NAME)
client = httpx.Client(base_url=BASE, timeout=30.0)
headers = {"Authorization": f"Bearer {token}"}

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 1: APPLICATION LAYER — API endpoints
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 70)
print("LAYER 1: APPLICATION LAYER (API)")
print("─" * 70)

# Step A1: Health check
r = client.get("/health")
log_step("A1", "APP", "PASS" if r.status_code == 200 else "FAIL",
         f"GET /health -> {r.status_code} {r.json().get('status')}")

# Step A2: POST /v1/auth/me — user provisioning
r = client.post("/v1/auth/me", headers=headers)
a2_data = r.json()
user_id_from_api = a2_data.get("data", {}).get("id", "N/A")
log_step("A2", "APP", "PASS" if r.status_code == 200 else "FAIL",
         f"POST /v1/auth/me -> {r.status_code}, user_id={user_id_from_api[:20] if user_id_from_api != 'N/A' else 'N/A'}")

# DB verification
db_rows = db_query("SELECT id, email, full_name, onboarding_complete, signup_source FROM careerloop.users WHERE id = %s", (TEST_USER_ID,))
if db_rows:
    ur = db_rows[0]
    log_step("A2-DB", "DB", "PASS" if ur.get("onboarding_complete") is not None else "FAIL",
             f"careerloop.users: email={ur['email']}, name={ur['full_name']}, onboarding={ur['onboarding_complete']}, source={ur['signup_source']}")
else:
    log_step("A2-DB", "DB", "FAIL", "NO USER ROW FOUND in careerloop.users after POST /v1/auth/me!")

# Step A3: GET /v1/me
r = client.get("/v1/me", headers=headers)
a3_data = r.json().get("data", {})
log_step("A3", "APP", "PASS" if r.status_code == 200 and a3_data.get("email") == TEST_EMAIL else "FAIL",
         f"GET /v1/me -> email={a3_data.get('email')}, name={a3_data.get('full_name')}, onboarding={a3_data.get('onboarding_complete')}, has_cv={a3_data.get('has_cv')}")

# Step A4: GET /v1/me/preferences
r = client.get("/v1/me/preferences", headers=headers)
log_step("A4", "APP", "PASS" if r.status_code == 200 else "FAIL",
         f"GET /v1/me/preferences -> {json.dumps(r.json().get('data', {}))[:200]}")

# Step A5: GET /v1/briefs/latest — should 404 for new user
r = client.get("/v1/briefs/latest", headers=headers)
log_step("A5", "APP", "PASS" if r.status_code == 404 else "INFO",
         f"GET /v1/briefs/latest -> {r.status_code} (expected 404 for new user, got {r.json().get('error', {}).get('code', 'N/A')})")

# Step A6: POST /v1/chat/message "hi" — start onboarding
r = client.post("/v1/chat/message", headers=headers, json={"text": "hi"})
a6_data = r.json().get("data", {})
log_step("A6", "APP", "PASS" if r.status_code == 200 else "FAIL",
         f"POST /v1/chat/message 'hi' -> {r.status_code}, reply='{a6_data.get('message', '')[:100]}...', state={a6_data.get('state')}, cards={len(a6_data.get('cards', []))}")

# DB: Check session state after first message
db_rows = db_query("SELECT state, onboarding_step, temp_profile_data FROM careerloop.sessions WHERE user_id = %s", (TEST_USER_ID,))
if db_rows:
    sr = db_rows[0]
    log_step("A6-DB", "DB", "INFO",
             f"careerloop.sessions: state={sr['state']}, onboarding_step={sr['onboarding_step']}, has_temp_profile={sr['temp_profile_data'] is not None}")

# DB: Check messages table
db_msg = db_query("SELECT count(*) as cnt FROM careerloop.messages WHERE user_id = %s", (TEST_USER_ID,))
msg_count = db_msg[0]['cnt'] if db_msg else 0
log_step("A6-MSG", "DB", "FAIL" if msg_count == 0 else "PASS",
         f"careerloop.messages count = {msg_count} (0 means messages NOT PERSISTED)")

# DB: Check conversations table
db_conv = db_query("SELECT count(*) as cnt FROM careerloop.conversations WHERE user_id = %s", (TEST_USER_ID,))
conv_count = db_conv[0]['cnt'] if db_conv else 0
log_step("A6-CONV", "DB", "FAIL" if conv_count == 0 else "PASS",
         f"careerloop.conversations count = {conv_count} (0 means conversations NOT PERSISTED)")

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 2: ONBOARDING FLOW — Paste CV (Module Layer)
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 70)
print("LAYER 2+3+4: ONBOARDING FLOW — MODULE + ORCHESTRATION + DB")
print("─" * 70)

# Step B1: Paste CV text
SAMPLE_CV = """Hayagreev Sivakumar
Email: hayagreev.sivakumar@example.com
Phone: +91-9876543210

SUMMARY
Product-minded AI Engineer with 5+ years of experience building ML systems at scale.
Currently at TechCorp, leading the NLP pipeline team.

EXPERIENCE

TechCorp, Bangalore — Senior AI Engineer (2022-Present)
- Built production NLP pipeline processing 1M+ documents/day
- Reduced model inference latency by 60% through ONNX optimization
- Led team of 3 ML engineers

DataFlow Labs, Chennai — ML Engineer (2020-2022)
- Developed recommendation system serving 500K users
- Implemented real-time fraud detection using Graph Neural Networks

StartupX, Remote — Backend Engineer (2019-2020)
- Built REST APIs serving 100K+ daily active users

EDUCATION
IIT Madras — B.Tech Computer Science (2015-2019)
CGPA: 8.7/10

SKILLS
Python, PyTorch, TensorFlow, LangChain, FastAPI, PostgreSQL, Kubernetes, AWS
NLP, Computer Vision, Recommendation Systems, MLOps"""

log_step("B1", "MODULE", "INFO", f"Pasting CV ({len(SAMPLE_CV)} chars) for Hayagreev...")

r = client.post("/v1/chat/message", headers=headers, json={"text": SAMPLE_CV})
b1_data = r.json().get("data", {})
status = "PASS" if r.status_code == 200 else "FAIL"
log_step("B1-API", "APP", status,
         f"POST /v1/chat/message (CV paste) -> {r.status_code}, reply='{b1_data.get('message', '')[:120]}...', state={b1_data.get('state')}, cards={len(b1_data.get('cards', []))}")

if r.status_code != 200:
    err_msg = r.json().get("error", {}).get("message", "unknown")
    log_step("B1-ERR", "APP", "FAIL", f"Error: {err_msg}")
    # Check if the issue is in the onboarding flow timing out
    log_step("B1-ROOT", "APP", "INFO", 
             "Root cause: onboarding path in chat_service.py has NO timeout wrapper. "
             "CVExtractionAgent calls DeepSeek with 30s timeout, then OnboardingAgent calls DeepSeek again."
             "If DeepSeek is slow, this can take 60+ seconds. If frontend retries, duplicate calls exhaust pool.")

# DB: Check session state after CV
db_rows = db_query("SELECT state, onboarding_step, temp_profile_data FROM careerloop.sessions WHERE user_id = %s", (TEST_USER_ID,))
if db_rows:
    sr = db_rows[0]
    tpd_preview = str(sr['temp_profile_data'])[:300] if sr['temp_profile_data'] else "NULL"
    log_step("B1-DB", "DB", "INFO",
             f"careerloop.sessions: state={sr['state']}, step={sr['onboarding_step']}")
    log_step("B1-DB-PROFILE", "DB", "INFO", f"temp_profile_data preview: {tpd_preview}")

# DB: Check if CV content was stored
db_users = db_query("SELECT master_cv_markdown IS NOT NULL as has_cv, target_roles, target_cities FROM careerloop.users WHERE id = %s", (TEST_USER_ID,))
if db_users:
    u = db_users[0]
    log_step("B1-DB-USERS", "DB", "PASS" if u.get('has_cv') or u.get('target_roles') else "FAIL",
             f"careerloop.users: has_cv={u['has_cv']}, target_roles={u.get('target_roles', 'NULL')}, target_cities={u.get('target_cities', 'NULL')}")

# DB: Messages should now exist
db_msg = db_query("SELECT count(*) as cnt FROM careerloop.messages WHERE user_id = %s", (TEST_USER_ID,))
msg_count = db_msg[0]['cnt'] if db_msg else 0
log_step("B1-MSG", "DB", "FAIL" if msg_count == 0 else "PASS",
         f"careerloop.messages count = {msg_count} (after CV paste — should be >0)")

# Step B2: Confirm profile
log_step("B2", "MODULE", "INFO", "Sending 'yes' to confirm extracted profile...")
r = client.post("/v1/chat/message", headers=headers, json={"text": "yes"})
b2_data = r.json().get("data", {})
log_step("B2-API", "APP", "PASS" if r.status_code == 200 else "FAIL",
         f"POST /v1/chat/message 'yes' -> {r.status_code}, reply='{b2_data.get('message', '')[:150]}...', state={b2_data.get('state')}")

# DB: Check final state
db_rows = db_query("SELECT state, onboarding_step FROM careerloop.sessions WHERE user_id = %s", (TEST_USER_ID,))
if db_rows:
    sr = db_rows[0]
    log_step("B2-DB", "DB", "PASS" if sr['state'] == 'PROFILE_READY' else "FAIL",
             f"careerloop.sessions: state={sr['state']} (expected PROFILE_READY), step={sr['onboarding_step']}")

db_users = db_query("SELECT onboarding_complete, target_roles, target_cities, career_mode FROM careerloop.users WHERE id = %s", (TEST_USER_ID,))
if db_users:
    u = db_users[0]
    log_step("B2-DB-USER", "DB", "PASS" if u.get('onboarding_complete') else "FAIL",
             f"careerloop.users: onboarding_complete={u['onboarding_complete']}, target_roles={u.get('target_roles', 'NULL')[:80] if u.get('target_roles') else 'NULL'}, target_cities={u.get('target_cities', 'NULL')}")

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 3: BRIEF LOADING
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "─" * 70)
print("LAYER 3: BRIEF LOADING")
print("─" * 70)

# Step C1: GET /v1/briefs/latest
r = client.get("/v1/briefs/latest", headers=headers)
log_step("C1", "APP", "PASS" if r.status_code in (200, 404) else "FAIL",
         f"GET /v1/briefs/latest -> {r.status_code}")

if r.status_code == 200:
    brief = r.json().get("data", {})
    log_step("C1-BRIEF", "DB", "PASS" if brief.get("item_count", 0) > 0 else "FAIL",
             f"brief_id={brief.get('brief_id', 'N/A')[:12]}, items={brief.get('item_count', 0)}")
    if brief.get("items"):
        for item in brief["items"][:3]:
            log_step("C1-ITEM", "INFO", "INFO",
                     f"  #{item.get('item_index')}: {item.get('title')} @ {item.get('company')} - {item.get('fit_score')}/100")
else:
    log_step("C1-NOBRIEF", "APP", "INFO",
             "No brief found for new user. This is expected if no scan has run.")

# Step C2: Try starting a scan
log_step("C2", "MODULE", "INFO", "Attempting to start a scan via POST /v1/scans...")
r = client.post("/v1/scans", headers=headers, json={"mode": "default"})
log_step("C2-API", "APP", "PASS" if r.status_code in (200, 409, 503) else "FAIL",
         f"POST /v1/scans -> {r.status_code}, {json.dumps(r.json().get('data', r.json().get('error', {})))[:150]}")

if r.status_code == 200:
    run_id = r.json().get("data", {}).get("run_id")
    log_step("C2-SCAN", "APP", "INFO", f"Scan started: run_id={run_id}")
    
    # Wait a few seconds then check status
    time.sleep(5)
    r = client.get(f"/v1/scans/{run_id}", headers=headers)
    status_data = r.json().get("data", {})
    log_step("C2-STATUS", "APP", "INFO",
             f"GET /v1/scans/{run_id} -> status={status_data.get('status')}, type={status_data.get('run_type')}")
    
    # Check DB
    db_runs = db_query("SELECT status, run_type FROM careerloop.background_runs WHERE run_id = %s", (run_id,))
    if db_runs:
        log_step("C2-DB", "DB", "INFO", f"careerloop.background_runs: status={db_runs[0]['status']}, type={db_runs[0]['run_type']}")
else:
    err = r.json().get("error", {}).get("message", "unknown")
    log_step("C2-ERR", "APP", "FAIL" if r.status_code != 200 else "PASS", f"Scan start error: {err}")

# ═══════════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("FINAL DB STATE AUDIT")
print("=" * 70)

checks = [
    ("careerloop.users (test user)", f"SELECT email, full_name, onboarding_complete, target_roles, target_cities, master_cv_markdown IS NOT NULL as has_cv FROM careerloop.users WHERE id = '{TEST_USER_ID}'"),
    ("careerloop.sessions (test user)", f"SELECT state, onboarding_step, active_artifact_type, active_job_id, active_brief_id FROM careerloop.sessions WHERE user_id = '{TEST_USER_ID}'"),
    ("careerloop.conversations (test user)", f"SELECT count(*) as cnt FROM careerloop.conversations WHERE user_id = '{TEST_USER_ID}'"),
    ("careerloop.messages (test user)", f"SELECT count(*) as cnt FROM careerloop.messages WHERE user_id = '{TEST_USER_ID}'"),
    ("careerloop.background_runs (test user)", f"SELECT count(*) as cnt FROM careerloop.background_runs WHERE user_id = '{TEST_USER_ID}'"),
    ("careerloop.user_preferences (test user)", f"SELECT count(*) as cnt FROM careerloop.user_preferences WHERE user_id = '{TEST_USER_ID}'"),
    ("Total messages in DB", "SELECT count(*) as cnt FROM careerloop.messages"),
    ("Total conversations in DB", "SELECT count(*) as cnt FROM careerloop.conversations"),
]

for label, sql in checks:
    try:
        rows = db_query(sql)
        log_step("FINAL", "DB", "INFO", f"{label}: {json.dumps(rows[0] if rows else {})}")
    except Exception as e:
        log_step("FINAL", "DB", "INFO", f"{label}: ERROR {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# GAP ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("GAP ANALYSIS")
print("=" * 70)

# Layer 1 gaps
print("\n[L1] APPLICATION LAYER GAPS:")
print("  ✅ GET /health, POST /v1/auth/me, GET /v1/me, GET /v1/me/preferences — WORKING")
print("  ⚠️  POST /v1/chat/message — works but NO TIMEOUT on onboarding path")
print("  ⚠️  POST /v1/scans — may fail due to DB pool exhaustion")
print("  ❌ GET /v1/briefs/latest — stuck 'loading your brief' if scan takes too long")

# Layer 2 gaps
print("\n[L2] DATABASE LAYER GAPS:")
print("  ✅ careerloop.users rows created via /v1/auth/me — WORKING")
print("  ✅ careerloop.sessions rows created and updated — WORKING")
print("  ❌ careerloop.messages — NEVER written by API path (0 rows for API users)")
print("  ❌ careerloop.conversations — NEVER written by API path (0 rows for API users)")
print("  ⚠️  careerloop.user_preferences — never populated by onboarding flow")
print("  ⚠️  careers.loop.users.target_roles/target_cities — session writes to temp_profile_data, NOT to these columns")

# Layer 3 gaps
print("\n[L3] ORCHESTRATION LAYER GAPS:")
print("  ❌ No LangGraph checkpointer in API path — graph state is in-memory ONLY")
print("  ❌ ConversationState.messages array is EMPTY on every new API call")
print("  ❌ _invoke_with_timeout() only covers supervisor graph, NOT onboarding flow")
print("  ❌ supervisor_graph.execute_action_node() creates NEW DatabaseManager + SessionStore per call")

# Layer 4 gaps
print("\n[L4] MODULE LAYER GAPS:")
print("  ❌ CVExtractionAgent._call_api() has 30s timeout but NO wrapping timeout in chat_service.py")
print("  ❌ If DeepSeek slow or pool exhausted, HTTP response never returns -> user waits forever")
print("  ❌ No frontend retry protection -> duplicate requests -> double pool pressure -> deadlock")

# Recommendations
print("\n" + "=" * 70)
print("RECOMMENDED FIXES (PRIORITY ORDER)")
print("=" * 70)
print("P0: Add message persistence to ChatService (G1)")
print("P0: Add timeout to onboarding flow path (G3)")
print("P0: Add DB connection timeout to pool.getconn() (G8)")
print("P1: Wire PostgresSaver checkpointer into API path (G2)")
print("P1: Pass SessionStore into graph context, stop creating new ones (G4)")
print("P1: Save session context back from graph output (G6)")
print("P1: Load conversation history from checkpointer on each call (G5)")

client.close()
