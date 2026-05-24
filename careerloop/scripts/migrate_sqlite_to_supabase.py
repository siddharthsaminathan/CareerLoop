#!/usr/bin/env python3
"""
CareerLoop Database Migration Script
Migrates the existing SQLite embedded database to Supabase PostgreSQL safely.
Does not alter the source SQLite database.
"""

import os
import sys
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import uuid
import json
from datetime import datetime

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://iephtlrikgfgakcojwhu.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Requires service_role key to bypass RLS during migration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL environment variable is required.")
    print("Set it before running: export DATABASE_URL='postgresql://...'")
    sys.exit(1)

SQLITE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "careerloop.db"))

NAMESPACE_CAREERLOOP = uuid.UUID('12345678-1234-5678-1234-567812345678')

def make_uuid(string_id: str) -> str:
    """Consistently hashes an old string ID to a valid UUID."""
    if not string_id:
        return None
    try:
        # Check if it's already a valid UUID
        val = uuid.UUID(string_id)
        return str(val)
    except ValueError:
        return str(uuid.uuid5(NAMESPACE_CAREERLOOP, string_id))

def get_sqlite_conn():
    if not os.path.exists(SQLITE_PATH):
        print(f"Error: SQLite DB not found at {SQLITE_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_pg_conn():
    return psycopg2.connect(DATABASE_URL)

def migrate_users(sqlite_conn, pg_conn):
    print("Migrating users...")
    cur_sqlite = sqlite_conn.cursor()
    cur_sqlite.execute("SELECT * FROM users")
    users = cur_sqlite.fetchall()

    pg_cur = pg_conn.cursor()
    
    # Notice: In Supabase, users must exist in auth.users first. 
    # For this script, we assume either we create proxy auth.users or the user will re-register.
    # To bypass auth.users constraint for migration testing, one might need to insert directly to auth.users if superuser.
    # We will log a warning.
    print(f"  Found {len(users)} users. NOTE: Supabase requires these users to exist in auth.users.")
    
    rows = []
    for u in users:
        new_id = make_uuid(u['id'])
        rows.append((
            new_id,
            f"migrated_{new_id}@careerloop.local", # placeholder email
            "Migrated User",
            u['employment_state'],
            u['urgency'],
            u['burnout_level'],
            u['preferred_environments'] or '[]',
            u['startup_tolerance'],
            u['compensation_floor_lakhs'],
            u['compensation_target_lakhs'],
            u['work_style_prefs'] or '{}',
            u['emotional_constraints'] or '{}',
            u['interview_tolerance'],
            u['remote_pref'],
            u['search_posture'],
            u['created_at'],
            u['updated_at']
        ))

    if not rows:
        return

    query = """
    INSERT INTO public.users (
        id, email, full_name, employment_state, urgency, burnout_level, 
        preferred_environments, startup_tolerance, compensation_floor_lakhs, 
        compensation_target_lakhs, work_style_prefs, emotional_constraints, 
        interview_tolerance, remote_pref, search_posture, created_at, updated_at
    ) VALUES %s ON CONFLICT (id) DO NOTHING
    """
    try:
        execute_values(pg_cur, query, rows)
        pg_conn.commit()
        print(f"  Migrated {len(rows)} users.")
    except Exception as e:
        pg_conn.rollback()
        print(f"  Failed migrating users: {e}")

def migrate_session_store(sqlite_conn, pg_conn):
    print("Migrating session_store...")
    cur_sqlite = sqlite_conn.cursor()
    
    # Try fetching session_store if it exists
    try:
        cur_sqlite.execute("SELECT * FROM session_store")
        sessions = cur_sqlite.fetchall()
    except sqlite3.OperationalError:
        print("  session_store table not found in SQLite. Skipping.")
        return

    pg_cur = pg_conn.cursor()
    rows = []
    for s in sessions:
        new_id = make_uuid(s['user_id'])
        rows.append((
            new_id,
            s['state'],
            s['current_job_id'],
            s['onboarding_step'],
            s['temp_profile_data'] or '{}',
            s['updated_at'] or datetime.now().isoformat()
        ))

    if not rows:
        return

    query = """
    INSERT INTO public.sessions (
        user_id, state, current_job_id, onboarding_step, temp_profile_data, updated_at
    ) VALUES %s ON CONFLICT (user_id) DO NOTHING
    """
    try:
        execute_values(pg_cur, query, rows)
        pg_conn.commit()
        print(f"  Migrated {len(rows)} sessions.")
    except Exception as e:
        pg_conn.rollback()
        print(f"  Failed migrating sessions: {e}")

def main():
    print("Starting database migration to Supabase...")
    sqlite_conn = get_sqlite_conn()
    try:
        pg_conn = get_pg_conn()
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        sys.exit(1)

    migrate_users(sqlite_conn, pg_conn)
    migrate_session_store(sqlite_conn, pg_conn)
    
    # Additional tables (application_ledger, strategic_tracks, etc.) can be added following the same pattern.
    
    sqlite_conn.close()
    pg_conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    main()
