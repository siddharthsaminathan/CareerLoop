"""
CareerLoop Concurrency and Load Testing Harness
Fires 5 parallel scan request threads at POST /v1/scans to verify the atomic active scan lock.
"""

import os
import sys
import time
import uuid
import json
import jwt
import httpx
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Configuration
API_BASE = "http://127.0.0.1:8001"
SUPABASE_JWT_SECRET = "y2vSuE7DzrrPVLAawfvlWv150RCBVwCsvr6HFfwaSLldtyPFp8Pvs6Motf/pzePpX8oDIUyuc2V07ExrP56drQ=="
DATABASE_URL = "postgresql://postgres.iephtlrikgfgakcojwhu:FS48TIvMiumRin8a@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"

# Ensure clean imports
sys.path.insert(0, "/Users/siddharthsaminathan/projects/CareerLoop")

def mint_jwt(user_id: str, email: str, name: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "iat": now,
        "exp": now + 3600,
        "user_metadata": {"full_name": name, "email": email},
        "app_metadata": {"provider": "google"},
    }
    return jwt.encode(payload, SUPABASE_JWT_SECRET, algorithm="HS256")

def db_execute(sql, params=None):
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            conn.commit()
            return cur.rowcount
    finally:
        conn.close()

def main():
    print("======================================================================")
    print("        CAREERLOOP CONCURRENT SCAN LOAD TESTING & HARDENING HARNESS   ")
    print("======================================================================")

    # 1. Generate new test user and token
    test_user_id = str(uuid.uuid4())
    test_email = f"load.test.{uuid.uuid4().hex[:6]}@example.com"
    test_name = "Scan LoadTest User"
    
    print(f"[*] Provisioning synthetic user:")
    print(f"    User ID: {test_user_id}")
    print(f"    Email:   {test_email}")

    token = mint_jwt(test_user_id, test_email, test_name)
    headers = {"Authorization": f"Bearer {token}"}

    client = httpx.Client(base_url=API_BASE, timeout=10.0)

    # Step A: Register the user via /v1/auth/me to populate careerloop.users
    r = client.post("/v1/auth/me", headers=headers)
    if r.status_code != 200:
        print(f"[FAIL] User registration failed: {r.status_code} - {r.text}")
        sys.exit(1)
    print("[✓] User created via POST /v1/auth/me")

    # Step B: Set target_roles and onboarding status directly in the database
    updated = db_execute(
        """
        UPDATE careerloop.users 
        SET target_roles = '["AI Engineer"]', target_cities = '["Bangalore"]', onboarding_complete = true 
        WHERE id = %s
        """,
        (test_user_id,)
    )
    if updated == 0:
        print("[FAIL] Database update for user record did not modify any rows.")
        sys.exit(1)
    print("[✓] User profile configured in careerloop.users (onboarding_complete=true)")

    # 2. Prepare concurrent threads
    num_threads = 5
    barrier = threading.Barrier(num_threads)
    results = []
    results_lock = threading.Lock()

    def worker_thread(thread_idx):
        # Build independent client per thread to avoid socket sharing or multiplexing bottlenecks
        with httpx.Client(base_url=API_BASE, timeout=10.0) as thread_client:
            # Synchronize all threads at the barrier before firing
            barrier.wait()
            
            t_start = time.time()
            try:
                response = thread_client.post(
                    "/v1/scans",
                    headers=headers,
                    json={"mode": "default"}
                )
                t_end = time.time()
                
                res_data = {
                    "thread_idx": thread_idx,
                    "status_code": response.status_code,
                    "latency_ms": round((t_end - t_start) * 1000, 2),
                    "body": response.json(),
                    "start_time": t_start
                }
            except Exception as e:
                t_end = time.time()
                res_data = {
                    "thread_idx": thread_idx,
                    "status_code": None,
                    "latency_ms": round((t_end - t_start) * 1000, 2),
                    "error": str(e),
                    "start_time": t_start
                }
            
            with results_lock:
                results.append(res_data)

    print(f"\n[*] Launching {num_threads} concurrent POST /v1/scans requests...")
    threads = []
    for idx in range(num_threads):
        t = threading.Thread(target=worker_thread, args=(idx,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print("\n========================= LOAD TEST RESULTS ==========================")
    # Sort by start time to see request sequence
    results.sort(key=lambda x: x["start_time"])
    
    success_count = 0
    conflict_count = 0
    other_count = 0
    
    for r in results:
        t_idx = r["thread_idx"]
        status = r.get("status_code")
        latency = r.get("latency_ms")
        
        if status == 200:
            success_count += 1
            run_id = r["body"].get("data", {}).get("run_id")
            print(f"[SUCCESS] Thread #{t_idx}: HTTP 200 OK | Latency: {latency}ms | Run ID: {run_id}")
        elif status == 409:
            conflict_count += 1
            err_code = r["body"].get("error", {}).get("code")
            err_msg = r["body"].get("error", {}).get("message")
            print(f"[BLOCKED] Thread #{t_idx}: HTTP 409 Conflict | Latency: {latency}ms | Code: {err_code} | Msg: {err_msg}")
        else:
            other_count += 1
            err_detail = r.get("error") or json.dumps(r.get("body"))
            print(f"[UNKNOWN] Thread #{t_idx}: HTTP {status} | Latency: {latency}ms | Info: {err_detail}")

    print("\n============================= SUMMARY ================================")
    print(f"Total Requests  : {num_threads}")
    print(f"Successful (200): {success_count}")
    print(f"Conflicts  (409): {conflict_count}")
    print(f"Other/Failed    : {other_count}")
    print("======================================================================")

    # Write results output file inside repository workspace for the report
    output_log_path = "/Users/siddharthsaminathan/projects/CareerLoop/docs/engineering/load_test_results.json"
    os.makedirs(os.path.dirname(output_log_path), exist_ok=True)
    with open(output_log_path, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "test_user_id": test_user_id,
            "requests": results,
            "summary": {
                "total": num_threads,
                "success": success_count,
                "conflict": conflict_count,
                "other": other_count
            }
        }, f, indent=2)
    print(f"[✓] Raw test results saved to {output_log_path}")

    # Assert correctness
    if success_count == 1 and conflict_count == (num_threads - 1):
        print("\n[PASS] Concurrency lock verified successfully! Exactly 1 trigger accepted and 4 blocked.")
        sys.exit(0)
    else:
        print("\n[FAIL] Concurrency lock failed verification. Unexpected success/conflict distribution.")
        sys.exit(1)

if __name__ == "__main__":
    main()
