-- ============================================================================
-- CareerLoop Data Engineering V3 Migration — Canonical Identity Spine
-- ============================================================================
-- Purpose:    Establish careerloop.users as the single identity spine and
--             migrate ALL foreign keys from public.users → careerloop.users.
--             Add missing domain tables (conversations, messages, memory_events,
--             recruiter_contacts, job_sources, job_search_runs).
--             Standardize UUID columns on transition paths.
--
-- Strategy:   Dual-path idempotent.
--   Path A (clean install):   CREATE TABLE IF NOT EXISTS — ignored if exists.
--   Path B (existing DB):     DROP CONSTRAINT IF EXISTS → recreate FK.
--                              ALTER TABLE ADD COLUMN IF NOT EXISTS.
--                              INSERT ... ON CONFLICT DO NOTHING.
-- No destructive drops except FK recreation (same constraint, new target).
-- Safe to run N times. Supabase PostgreSQL only.
--
-- Pre-requisites: V1 (supabase_schema.sql) + V2 (supabase_migration_v2.sql)
--                 must already be applied.
--
-- Total changes:
--   1 new table      (careerloop.users)
--   1 data copy      (public.users → careerloop.users)
--   16 FK migrations (public.users → careerloop.users)
--   3 ALTER TABLE    (UUID column additions for run_id/event_id)
--   3 COMMENTs       (sessions deprecation markers)
--   4 CREATE TABLE   (conversations, messages, memory_events, recruiter_contacts)
--   2 CREATE TABLE   (job_sources, job_search_runs)
--   9 RLS policies   (idempotent DO block)
-- ============================================================================

-- ############################################################################
-- SECTION 1: CREATE careerloop.users — CANONICAL IDENTITY SPINE
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT,
    phone TEXT,
    telegram_id TEXT,
    whatsapp_id TEXT,
    linkedin_url TEXT,
    full_name TEXT,
    onboarding_status TEXT DEFAULT 'new',
    signup_source TEXT DEFAULT 'cli',
    current_plan TEXT DEFAULT 'free',
    trial_started_at TIMESTAMPTZ,
    trial_ends_at TIMESTAMPTZ,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_careerloop_users_email
    ON careerloop.users(email) WHERE email IS NOT NULL;

-- NOTE: public.users has additional columns added in V2 (location_city,
-- location_country, linkedin_url, notice_period_days, current_ctc_lakhs,
-- expected_ctc_lakhs, yoe, is_active) that are not yet migrated to
-- careerloop.users. These stay in public.users as legacy columns.
-- Future V3.1 migration will add them to careerloop.users and copy data.

-- ############################################################################
-- SECTION 2: COPY EXISTING public.users DATA INTO careerloop.users
-- ############################################################################
INSERT INTO careerloop.users (id, email, full_name, created_at, updated_at, last_active_at)
SELECT id, email, full_name, created_at, updated_at, NOW()
FROM public.users
ON CONFLICT (id) DO NOTHING;

-- ############################################################################
-- SECTION 3: FK MIGRATION — Drop FKs to public.users, recreate to careerloop.users
-- ############################################################################
-- For each CareerLoop table with REFERENCES public.users(id), we:
--   1. DROP the old FK (IF EXISTS — safe on fresh installs)
--   2. ADD the new FK pointing to careerloop.users(id) ON DELETE CASCADE
--
-- Constraint names follow PostgreSQL auto-generation convention:
--   {tablename}_{columnname}_fkey
-- For inline constraints defined without explicit names in CREATE TABLE.
-- The IF EXISTS clause makes these safe on clean installs where the table
-- was created with V3's careerloop.users reference from the start.

-- 3a. sessions (supabase_schema.sql: user_id is PK + FK)
ALTER TABLE careerloop.sessions DROP CONSTRAINT IF EXISTS sessions_user_id_fkey;
ALTER TABLE careerloop.sessions
    ADD CONSTRAINT sessions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3b. background_runs (supabase_schema.sql)
ALTER TABLE careerloop.background_runs DROP CONSTRAINT IF EXISTS background_runs_user_id_fkey;
ALTER TABLE careerloop.background_runs
    ADD CONSTRAINT background_runs_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3c. daily_briefs (supabase_schema.sql v1 definition; V2 CREATE is a no-op)
ALTER TABLE careerloop.daily_briefs DROP CONSTRAINT IF EXISTS daily_briefs_user_id_fkey;
ALTER TABLE careerloop.daily_briefs
    ADD CONSTRAINT daily_briefs_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3d. strategic_tracks (supabase_schema.sql)
ALTER TABLE careerloop.strategic_tracks DROP CONSTRAINT IF EXISTS strategic_tracks_user_id_fkey;
ALTER TABLE careerloop.strategic_tracks
    ADD CONSTRAINT strategic_tracks_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3e. application_ledger (supabase_schema.sql)
ALTER TABLE careerloop.application_ledger DROP CONSTRAINT IF EXISTS application_ledger_user_id_fkey;
ALTER TABLE careerloop.application_ledger
    ADD CONSTRAINT application_ledger_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3f. event_timeline (supabase_schema.sql)
ALTER TABLE careerloop.event_timeline DROP CONSTRAINT IF EXISTS event_timeline_user_id_fkey;
ALTER TABLE careerloop.event_timeline
    ADD CONSTRAINT event_timeline_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3g. company_memory (supabase_schema.sql)
ALTER TABLE careerloop.company_memory DROP CONSTRAINT IF EXISTS company_memory_user_id_fkey;
ALTER TABLE careerloop.company_memory
    ADD CONSTRAINT company_memory_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3h. positioning_memory (supabase_schema.sql)
ALTER TABLE careerloop.positioning_memory DROP CONSTRAINT IF EXISTS positioning_memory_user_id_fkey;
ALTER TABLE careerloop.positioning_memory
    ADD CONSTRAINT positioning_memory_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3i. user_job_relationships (V2 migration)
ALTER TABLE careerloop.user_job_relationships DROP CONSTRAINT IF EXISTS user_job_relationships_user_id_fkey;
ALTER TABLE careerloop.user_job_relationships
    ADD CONSTRAINT user_job_relationships_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3j. applications (V2 migration)
ALTER TABLE careerloop.applications DROP CONSTRAINT IF EXISTS applications_user_id_fkey;
ALTER TABLE careerloop.applications
    ADD CONSTRAINT applications_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3k. application_packs (V2 migration)
ALTER TABLE careerloop.application_packs DROP CONSTRAINT IF EXISTS application_packs_user_id_fkey;
ALTER TABLE careerloop.application_packs
    ADD CONSTRAINT application_packs_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3l. user_preferences (V2 migration — user_id is PK + FK)
-- Drop only the FK; the PK constraint (user_preferences_pkey) stays intact.
ALTER TABLE careerloop.user_preferences DROP CONSTRAINT IF EXISTS user_preferences_user_id_fkey;
ALTER TABLE careerloop.user_preferences
    ADD CONSTRAINT user_preferences_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3m. user_evidence (V2 migration)
ALTER TABLE careerloop.user_evidence DROP CONSTRAINT IF EXISTS user_evidence_user_id_fkey;
ALTER TABLE careerloop.user_evidence
    ADD CONSTRAINT user_evidence_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3n. outreach_messages (V2 migration)
ALTER TABLE careerloop.outreach_messages DROP CONSTRAINT IF EXISTS outreach_messages_user_id_fkey;
ALTER TABLE careerloop.outreach_messages
    ADD CONSTRAINT outreach_messages_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3o. followups (V2 migration)
ALTER TABLE careerloop.followups DROP CONSTRAINT IF EXISTS followups_user_id_fkey;
ALTER TABLE careerloop.followups
    ADD CONSTRAINT followups_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- 3p. outcome_events (V2 migration)
ALTER TABLE careerloop.outcome_events DROP CONSTRAINT IF EXISTS outcome_events_user_id_fkey;
ALTER TABLE careerloop.outcome_events
    ADD CONSTRAINT outcome_events_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES careerloop.users(id) ON DELETE CASCADE;

-- ############################################################################
-- SECTION 4: STANDARDIZE UUID COLUMNS
-- ############################################################################
-- Add UUID equivalents alongside existing TEXT ID columns. These are
-- transitional bridges — new code writes both; old TEXT columns remain
-- for backward compatibility. A future V3.1 hardening pass will backfill
-- and swap PKs from TEXT→UUID.

-- 4a. background_runs.run_id: currently TEXT PK → add UUID column
ALTER TABLE careerloop.background_runs ADD COLUMN IF NOT EXISTS run_id_uuid UUID DEFAULT gen_random_uuid();

-- 4b. run_events.event_id: currently TEXT PK → add UUID column
ALTER TABLE careerloop.run_events ADD COLUMN IF NOT EXISTS event_id_uuid UUID DEFAULT gen_random_uuid();

-- 4c. run_events.run_id: currently TEXT → add UUID column
ALTER TABLE careerloop.run_events ADD COLUMN IF NOT EXISTS run_id_uuid UUID;

-- 4d. daily_briefs.run_id: currently TEXT → add UUID column
ALTER TABLE careerloop.daily_briefs ADD COLUMN IF NOT EXISTS run_id_uuid UUID;

-- NOTE: sessions.user_id is already UUID. jobs.job_id is already UUID (V2).
--       No changes needed for those.

-- ############################################################################
-- SECTION 5: CLEAN UP sessions TABLE — DEPRECATION MARKERS
-- ############################################################################
-- These columns exist but should NOT be used for identity or memory.
-- We keep them for backward compatibility and mark them as deprecated.

COMMENT ON COLUMN careerloop.sessions.current_job_id
    IS 'DEPRECATED: use active_job_id in active_context instead';

COMMENT ON COLUMN careerloop.sessions.onboarding_step
    IS 'DEPRECATED: onboarding tracked via careerloop.users.onboarding_status';

COMMENT ON COLUMN careerloop.sessions.temp_profile_data
    IS 'DEPRECATED: profile data lives in careerloop.users + careerloop.user_preferences';

-- ############################################################################
-- SECTION 6: CREATE MISSING DOMAIN TABLES
-- ############################################################################

-- 6a. Conversations — multi-transport chat sessions
CREATE TABLE IF NOT EXISTS careerloop.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES careerloop.users(id) ON DELETE CASCADE,
    transport TEXT NOT NULL DEFAULT 'cli',  -- cli, telegram, whatsapp, web
    external_chat_id TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conv_user ON careerloop.conversations(user_id);

-- 6b. Messages — per-conversation message log with routing metadata
CREATE TABLE IF NOT EXISTS careerloop.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES careerloop.conversations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES careerloop.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system','tool')),
    content TEXT NOT NULL,
    action_type TEXT,
    action_confidence REAL,
    artifact_context JSONB DEFAULT '{}',
    response_envelope JSONB DEFAULT '{}',
    tokens_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_msg_conv ON careerloop.messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_msg_user ON careerloop.messages(user_id, created_at);

-- 6c. Memory events — importance-weighted, TTL-based memory store
CREATE TABLE IF NOT EXISTS careerloop.memory_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES careerloop.users(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    summary TEXT,
    payload JSONB DEFAULT '{}',
    importance INTEGER DEFAULT 1 CHECK (importance BETWEEN 1 AND 10),
    ttl_days INTEGER,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mem_user ON careerloop.memory_events(user_id, event_type);
CREATE INDEX IF NOT EXISTS idx_mem_expires ON careerloop.memory_events(expires_at)
    WHERE expires_at IS NOT NULL;

-- 6d. Recruiter contacts — people layer for outreach
CREATE TABLE IF NOT EXISTS careerloop.recruiter_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES careerloop.companies(id),
    name TEXT NOT NULL,
    title TEXT,
    linkedin_url TEXT,
    email TEXT,
    phone TEXT,
    source TEXT,
    notes TEXT,
    last_contacted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recruiter_company ON careerloop.recruiter_contacts(company_id);

-- ############################################################################
-- SECTION 7: JOB PERSISTENCE ENGINE TABLES
-- ############################################################################

-- 7a. Job sources — dedup-friendly source tracking per job
CREATE TABLE IF NOT EXISTS careerloop.job_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL,
    source TEXT NOT NULL,  -- linkedin, naukri, greenhouse, ashby, lever, etc.
    source_job_id TEXT,
    source_url TEXT,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jsource_job ON careerloop.job_sources(job_id);

-- 7b. Job search runs — audit trail for each scan/search execution
-- NOTE: run_id is TEXT to match careerloop.background_runs.run_id (TEXT PK).
--       After the UUID backfill in V3.1, this column should be migrated to
--       UUID referencing careerloop.background_runs.run_id_uuid.
CREATE TABLE IF NOT EXISTS careerloop.job_search_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES careerloop.users(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL,
    query_params JSONB DEFAULT '{}',
    candidates_found INTEGER DEFAULT 0,
    after_dedup INTEGER DEFAULT 0,
    after_geo_filter INTEGER DEFAULT 0,
    after_role_filter INTEGER DEFAULT 0,
    scored INTEGER DEFAULT 0,
    shortlisted INTEGER DEFAULT 0,
    cache_hit_ratio REAL DEFAULT 0,
    sources_used JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jsearch_user ON careerloop.job_search_runs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_jsearch_run ON careerloop.job_search_runs(run_id);

-- ############################################################################
-- SECTION 8: RLS POLICIES FOR NEW TABLES
-- ############################################################################
-- Idempotent DO block — checks pg_policies before creating each policy.

DO $$
BEGIN
    -- careerloop.users
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own profile' AND schemaname = 'careerloop' AND tablename = 'users') THEN
        ALTER TABLE careerloop.users ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own profile"
            ON careerloop.users FOR ALL USING (auth.uid() = id);
    END IF;

    -- careerloop.conversations
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own conversations') THEN
        ALTER TABLE careerloop.conversations ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own conversations"
            ON careerloop.conversations FOR ALL USING (auth.uid() = user_id);
    END IF;

    -- careerloop.messages
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own messages') THEN
        ALTER TABLE careerloop.messages ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own messages"
            ON careerloop.messages FOR ALL USING (auth.uid() = user_id);
    END IF;

    -- careerloop.memory_events
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own memory events') THEN
        ALTER TABLE careerloop.memory_events ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own memory events"
            ON careerloop.memory_events FOR ALL USING (auth.uid() = user_id);
    END IF;

    -- careerloop.recruiter_contacts
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Authenticated users can read recruiter contacts') THEN
        ALTER TABLE careerloop.recruiter_contacts ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Authenticated users can read recruiter contacts"
            ON careerloop.recruiter_contacts FOR SELECT USING (auth.role() = 'authenticated');
    END IF;

    -- careerloop.job_sources
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Authenticated users can read job sources') THEN
        ALTER TABLE careerloop.job_sources ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Authenticated users can read job sources"
            ON careerloop.job_sources FOR SELECT USING (auth.role() = 'authenticated');
    END IF;

    -- careerloop.job_search_runs
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own job search runs') THEN
        ALTER TABLE careerloop.job_search_runs ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own job search runs"
            ON careerloop.job_search_runs FOR ALL USING (auth.uid() = user_id);
    END IF;
END $$;

-- ############################################################################
-- MIGRATION COMPLETE
-- ############################################################################
-- Summary of changes:
--   Section 1:  careerloop.users created (canonical identity spine, 18 cols)
--   Section 2:  public.users → careerloop.users data copy (ON CONFLICT safe)
--   Section 3:  16 FK constraints migrated (public.users → careerloop.users)
--   Section 4:  4 ALTER TABLE ADD COLUMN IF NOT EXISTS (UUID bridge columns)
--   Section 5:  3 COMMENT ON COLUMN (sessions deprecation markers)
--   Section 6:  4 CREATE TABLE (conversations, messages, memory_events,
--               recruiter_contacts)
--   Section 7:  2 CREATE TABLE (job_sources, job_search_runs)
--   Section 8:  7 RLS policies (idempotent DO block)
--
-- Tables now referencing careerloop.users (all 16 migrated):
--   sessions, background_runs, daily_briefs, strategic_tracks,
--   application_ledger, event_timeline, company_memory, positioning_memory,
--   user_job_relationships, applications, application_packs, user_preferences,
--   user_evidence, outreach_messages, followups, outcome_events
--
-- New tables in careerloop schema (all reference careerloop.users):
--   conversations, messages, memory_events, job_search_runs
--
-- Known gaps requiring follow-up (V3.1 hardening):
--   1. public.users extended columns (location_city, location_country,
--      linkedin_url, notice_period_days, current_ctc_lakhs, expected_ctc_lakhs,
--      yoe, is_active) → migrate to careerloop.users
--   2. background_runs.run_id (TEXT PK → UUID PK) backfill + swap
--   3. run_events.event_id (TEXT PK → UUID PK) backfill + swap
--   4. daily_briefs.run_id (TEXT → UUID) backfill + swap FK
--   5. job_search_runs.run_id (TEXT → UUID FK) after #2 completes
--   6. jobs.id (TEXT PK) → jobs.job_id (UUID PK) constraint swap (from V2)
--   7. daily_brief_items.job_id (TEXT → UUID FK) backfill (from V2)
--   8. public.users table — eventually deprecate after all consumers
--      switch to careerloop.users
--
-- Revert strategy (if needed):
--   Reverse Section 3 FKs back to public.users, drop careerloop.users.
--   Sections 1, 4, 5, 6, 7, 8 are additive and safe to leave.
-- ============================================================================
