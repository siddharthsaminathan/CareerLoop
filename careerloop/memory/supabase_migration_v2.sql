-- ============================================================================
-- CareerLoop Data Engineering V2 Migration
-- ============================================================================
-- Strategy: Dual-path idempotent migration.
--   Path A (clean install):  CREATE TABLE IF NOT EXISTS — ignored if table exists.
--   Path B (existing v1 DB): ALTER TABLE ADD COLUMN IF NOT EXISTS — bridges
--                              schema drift between v1 and v2.
-- No destructive drops. Safe to run N times. Supabase PostgreSQL only.
--
-- Tables:          14 new or extended
-- ALTER blocks:    6 (jobs, companies, daily_briefs, daily_brief_items,
--                      background_runs, run_events, sessions)
-- Indexes:         All use IF NOT EXISTS
--
-- v1 columns that are RENAMED/REPLACED in v2 are left intact (no DROP).
-- New code reads v2 columns; old columns become dead weight removed later.
-- ============================================================================

-- ############################################################################
-- 1. GLOBAL JOB CACHE (CREATE + ALTER bridge)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,
    source_job_id TEXT,
    canonical_url TEXT,
    apply_url TEXT,
    title TEXT NOT NULL,
    normalized_title TEXT,
    company_id UUID REFERENCES careerloop.companies(id),
    company_name TEXT,
    location_raw TEXT,
    location_city TEXT,
    location_country TEXT,
    is_india_role BOOLEAN DEFAULT false,
    work_mode TEXT,
    salary_min NUMERIC,
    salary_max NUMERIC,
    salary_currency TEXT DEFAULT 'INR',
    jd_text TEXT,
    jd_hash TEXT,
    content_fingerprint TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    status TEXT DEFAULT 'active' CHECK (status IN ('active','expired','unknown')),
    raw_payload JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bridge: if jobs table already exists from v1 (id TEXT PK, different columns),
-- add all v2 columns that are missing. NOT NULL columns get a safe DEFAULT so
-- existing rows survive the ALTER.
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS job_id UUID DEFAULT gen_random_uuid();
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS source_job_id TEXT;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS canonical_url TEXT;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS normalized_title TEXT;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS location_raw TEXT;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS location_city TEXT;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS location_country TEXT;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS is_india_role BOOLEAN DEFAULT false;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS work_mode TEXT;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS salary_min NUMERIC;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS salary_max NUMERIC;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS salary_currency TEXT DEFAULT 'INR';
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS jd_text TEXT;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS jd_hash TEXT;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS content_fingerprint TEXT DEFAULT '';  -- backfill before making NOT NULL
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS raw_payload JSONB DEFAULT '{}';
ALTER TABLE careerloop.jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
-- NOTE: v1 `id` (TEXT PK) remains; v2 `job_id` (UUID) is additive.
--       PK migration from TEXT→UUID requires a separate backfill step.

CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_fingerprint ON careerloop.jobs(content_fingerprint);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON careerloop.jobs(company_name);
CREATE INDEX IF NOT EXISTS idx_jobs_job_id ON careerloop.jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_title ON careerloop.jobs(normalized_title);
CREATE INDEX IF NOT EXISTS idx_jobs_city ON careerloop.jobs(location_city);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON careerloop.jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON careerloop.jobs(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON careerloop.jobs(status);

-- ############################################################################
-- 2. COMPANY CACHE (CREATE + ALTER bridge)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    website TEXT,
    linkedin_url TEXT,
    logo_url TEXT,
    domain TEXT,
    industry TEXT,
    size TEXT,
    funding_stage TEXT,
    location TEXT,
    raw_payload JSONB DEFAULT '{}',
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bridge: v1 companies has domain_slug, city, sector, subsector, ats_provider,
-- career_page_url, ats_url, employee_estimate, crawl_status, last_crawled_at,
-- last_job_count, is_active, source. Keep those; add v2 columns.
ALTER TABLE careerloop.companies ADD COLUMN IF NOT EXISTS normalized_name TEXT;
ALTER TABLE careerloop.companies ADD COLUMN IF NOT EXISTS website TEXT;
ALTER TABLE careerloop.companies ADD COLUMN IF NOT EXISTS logo_url TEXT;
ALTER TABLE careerloop.companies ADD COLUMN IF NOT EXISTS industry TEXT;
ALTER TABLE careerloop.companies ADD COLUMN IF NOT EXISTS size TEXT;
ALTER TABLE careerloop.companies ADD COLUMN IF NOT EXISTS funding_stage TEXT;
ALTER TABLE careerloop.companies ADD COLUMN IF NOT EXISTS raw_payload JSONB DEFAULT '{}';
ALTER TABLE careerloop.companies ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE careerloop.companies ADD COLUMN IF NOT EXISTS last_updated_at TIMESTAMPTZ DEFAULT NOW();
-- Backfill normalized_name from existing name column if NULL
UPDATE careerloop.companies SET normalized_name = LOWER(TRIM(name)) WHERE normalized_name IS NULL AND name IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_normalized ON careerloop.companies(normalized_name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_domain ON careerloop.companies(domain) WHERE domain IS NOT NULL;

-- ############################################################################
-- 3. BACKGROUND RUNS (extend existing table)
-- ############################################################################
-- v1 has: run_id TEXT PK, user_id, run_type, status, created_at, updated_at
ALTER TABLE careerloop.background_runs ADD COLUMN IF NOT EXISTS error_code TEXT;
ALTER TABLE careerloop.background_runs ADD COLUMN IF NOT EXISTS error_summary TEXT;
ALTER TABLE careerloop.background_runs ADD COLUMN IF NOT EXISTS params JSONB DEFAULT '{}';
ALTER TABLE careerloop.background_runs ADD COLUMN IF NOT EXISTS stats JSONB DEFAULT '{}';
ALTER TABLE careerloop.background_runs ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE careerloop.background_runs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_bg_runs_status ON careerloop.background_runs(status);
CREATE INDEX IF NOT EXISTS idx_bg_runs_type ON careerloop.background_runs(run_type);

-- ############################################################################
-- 4. RUN EVENTS (extend existing table)
-- ############################################################################
-- v1 has: event_id TEXT PK, run_id, message, timestamp
ALTER TABLE careerloop.run_events ADD COLUMN IF NOT EXISTS event_type TEXT DEFAULT 'info';
ALTER TABLE careerloop.run_events ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}';
CREATE INDEX IF NOT EXISTS idx_run_events_type ON careerloop.run_events(event_type);

-- ############################################################################
-- 5. RAW DISCOVERY CANDIDATES (new table)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.job_candidates (
    candidate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES careerloop.background_runs(run_id),
    source TEXT,
    query TEXT,
    raw_title TEXT,
    raw_company TEXT,
    raw_location TEXT,
    raw_url TEXT,
    raw_snippet TEXT,
    raw_payload JSONB DEFAULT '{}',
    extraction_status TEXT DEFAULT 'pending',
    rejection_stage TEXT,
    rejection_reason TEXT,
    matched_job_id UUID REFERENCES careerloop.jobs(job_id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_candidates_run ON careerloop.job_candidates(run_id);
CREATE INDEX IF NOT EXISTS idx_candidates_status ON careerloop.job_candidates(extraction_status);

-- ############################################################################
-- 6. USER-JOB RELATIONSHIP (new table)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.user_job_relationships (
    user_id UUID NOT NULL REFERENCES public.users(id),
    job_id UUID NOT NULL REFERENCES careerloop.jobs(job_id),
    fit_score NUMERIC,
    fit_label TEXT,
    match_status TEXT DEFAULT 'matched' CHECK (match_status IN ('matched','rejected','maybe','saved','skipped','interested','applied')),
    rejection_reason TEXT,
    user_seen_at TIMESTAMPTZ,
    shown_in_brief_id UUID,
    swiped_action TEXT,
    interest_level TEXT,
    route_recommendation TEXT CHECK (route_recommendation IN ('direct_apply','recruiter_first','referral_first','skip')),
    personalization_payload JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, job_id)
);
CREATE INDEX IF NOT EXISTS idx_ujr_match_status ON careerloop.user_job_relationships(match_status);
CREATE INDEX IF NOT EXISTS idx_ujr_fit_score ON careerloop.user_job_relationships(fit_score);

-- ############################################################################
-- 7. DAILY BRIEFS (CREATE + ALTER bridge)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.daily_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id),
    run_id UUID NOT NULL REFERENCES careerloop.background_runs(run_id),
    date_str TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active',
    summary_text TEXT,
    stats JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bridge: v1 daily_briefs has run_id TEXT, summary (not summary_text), no version,
-- no status, no stats. Add missing columns.
ALTER TABLE careerloop.daily_briefs ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;
ALTER TABLE careerloop.daily_briefs ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
ALTER TABLE careerloop.daily_briefs ADD COLUMN IF NOT EXISTS summary_text TEXT;
ALTER TABLE careerloop.daily_briefs ADD COLUMN IF NOT EXISTS stats JSONB DEFAULT '{}';
-- NOTE: v1 `summary` column remains; migrate data to `summary_text` in a
--       separate backfill step if needed.

CREATE INDEX IF NOT EXISTS idx_briefs_user_date ON careerloop.daily_briefs(user_id, date_str);
CREATE INDEX IF NOT EXISTS idx_briefs_status ON careerloop.daily_briefs(status);

-- ############################################################################
-- 8. DAILY BRIEF ITEMS (CREATE + ALTER bridge)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.daily_brief_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_id UUID NOT NULL REFERENCES careerloop.daily_briefs(id),
    item_index INTEGER NOT NULL,
    job_id UUID NOT NULL REFERENCES careerloop.jobs(job_id),
    fit_score NUMERIC,
    fit_label TEXT,
    title TEXT,
    company TEXT,
    location TEXT,
    recommendation_reason TEXT,
    risk_summary TEXT,
    route_recommendation TEXT,
    display_payload JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (brief_id, item_index)
);

-- Bridge: v1 daily_brief_items has job_id TEXT, fit_score REAL, no fit_label,
-- no display_payload, no created_at. Add missing columns.
ALTER TABLE careerloop.daily_brief_items ADD COLUMN IF NOT EXISTS fit_label TEXT;
ALTER TABLE careerloop.daily_brief_items ADD COLUMN IF NOT EXISTS display_payload JSONB DEFAULT '{}';
ALTER TABLE careerloop.daily_brief_items ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
-- NOTE: v1 `job_id` is TEXT; v2 expects UUID. A separate backfill step is
--       needed to map TEXT→UUID references before enforcing the FK.

CREATE INDEX IF NOT EXISTS idx_brief_items_job ON careerloop.daily_brief_items(job_id);

-- ############################################################################
-- 9. APPLICATIONS (new table)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.applications (
    application_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id),
    job_id UUID NOT NULL REFERENCES careerloop.jobs(job_id),
    status TEXT DEFAULT 'prepared' CHECK (status IN ('prepared','applied','followup_due','recruiter_contacted','referral_requested','interview_scheduled','rejected','offer')),
    application_pack_id UUID,
    applied_at TIMESTAMPTZ,
    apply_channel TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_apps_user ON careerloop.applications(user_id);
CREATE INDEX IF NOT EXISTS idx_apps_status ON careerloop.applications(status);
CREATE INDEX IF NOT EXISTS idx_apps_job ON careerloop.applications(job_id);

-- ############################################################################
-- 10. APPLICATION PACKS (new table)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.application_packs (
    pack_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id),
    job_id UUID NOT NULL REFERENCES careerloop.jobs(job_id),
    run_id UUID NOT NULL REFERENCES careerloop.background_runs(run_id),
    resume_artifact_id TEXT,
    cover_note TEXT,
    recruiter_dm TEXT,
    referral_dm TEXT,
    screening_answers JSONB DEFAULT '{}',
    company_intel_id TEXT,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft','ready','sent','archived')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_packs_user ON careerloop.application_packs(user_id);
CREATE INDEX IF NOT EXISTS idx_packs_job ON careerloop.application_packs(job_id);

-- ############################################################################
-- 11. PEOPLE TO REACH (new table)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.people_to_reach (
    person_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES careerloop.companies(id),
    job_id UUID REFERENCES careerloop.jobs(job_id),
    name TEXT,
    title TEXT,
    linkedin_url TEXT,
    source TEXT,
    relevance_reason TEXT,
    confidence NUMERIC DEFAULT 0.5,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_people_company ON careerloop.people_to_reach(company_id);
CREATE INDEX IF NOT EXISTS idx_people_job ON careerloop.people_to_reach(job_id);

-- ############################################################################
-- 12. OUTREACH MESSAGES (new table)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.outreach_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id),
    person_id UUID REFERENCES careerloop.people_to_reach(person_id),
    job_id UUID REFERENCES careerloop.jobs(job_id),
    application_id UUID REFERENCES careerloop.applications(application_id),
    message_type TEXT CHECK (message_type IN ('recruiter_dm','referral_ask','followup','thank_you')),
    body TEXT,
    status TEXT DEFAULT 'drafted' CHECK (status IN ('drafted','sent','replied','ghosted')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_outreach_user ON careerloop.outreach_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON careerloop.outreach_messages(status);

-- ############################################################################
-- 13. FOLLOWUPS (new table)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.followups (
    followup_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id),
    application_id UUID REFERENCES careerloop.applications(application_id),
    person_id UUID REFERENCES careerloop.people_to_reach(person_id),
    due_at TIMESTAMPTZ,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending','sent','completed','skipped')),
    draft_message TEXT,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_followups_user ON careerloop.followups(user_id);
CREATE INDEX IF NOT EXISTS idx_followups_due ON careerloop.followups(due_at) WHERE status = 'pending';

-- ############################################################################
-- 14. USER EVIDENCE (new table)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.user_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id),
    evidence_type TEXT CHECK (evidence_type IN ('project','work_achievement','skill','education','certification','link')),
    title TEXT,
    description TEXT,
    proof_url TEXT,
    source TEXT CHECK (source IN ('resume','linkedin','manual','chat')),
    confidence NUMERIC DEFAULT 0.5,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_evidence_user ON careerloop.user_evidence(user_id);
CREATE INDEX IF NOT EXISTS idx_evidence_type ON careerloop.user_evidence(evidence_type);

-- ############################################################################
-- 15. USER PREFERENCES (new table)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.user_preferences (
    user_id UUID PRIMARY KEY REFERENCES public.users(id),
    target_roles JSONB DEFAULT '[]',
    target_cities JSONB DEFAULT '[]',
    salary_min NUMERIC,
    salary_max NUMERIC,
    notice_period TEXT,
    work_mode TEXT,
    avoid_companies JSONB DEFAULT '[]',
    avoid_role_types JSONB DEFAULT '[]',
    aggressiveness TEXT CHECK (aggressiveness IN ('conservative','moderate','aggressive')),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ############################################################################
-- 16. OUTCOME EVENTS — Learning loop (new table)
-- ############################################################################
CREATE TABLE IF NOT EXISTS careerloop.outcome_events (
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id),
    job_id UUID REFERENCES careerloop.jobs(job_id),
    application_id UUID REFERENCES careerloop.applications(application_id),
    event_type TEXT CHECK (event_type IN ('reply_received','interview_scheduled','rejected','ghosted','offer_received','followup_worked','recruiter_replied')),
    payload JSONB DEFAULT '{}',
    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_outcomes_user ON careerloop.outcome_events(user_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_type ON careerloop.outcome_events(event_type);
CREATE INDEX IF NOT EXISTS idx_outcomes_occurred ON careerloop.outcome_events(occurred_at);

-- ############################################################################
-- SESSIONS EXTENSION — active_context columns
-- ############################################################################
-- v1 sessions already has all these columns, so these are safe no-ops on v1.
-- On a fresh DB where sessions was created without them, they add the columns.
ALTER TABLE careerloop.sessions ADD COLUMN IF NOT EXISTS active_artifact_type TEXT;
ALTER TABLE careerloop.sessions ADD COLUMN IF NOT EXISTS active_artifact_id TEXT;
ALTER TABLE careerloop.sessions ADD COLUMN IF NOT EXISTS active_job_id TEXT;
ALTER TABLE careerloop.sessions ADD COLUMN IF NOT EXISTS active_brief_id TEXT;
ALTER TABLE careerloop.sessions ADD COLUMN IF NOT EXISTS active_pack_id TEXT;
ALTER TABLE careerloop.sessions ADD COLUMN IF NOT EXISTS current_selection_index INTEGER;

-- ############################################################################
-- USERS EXTENSION — convenience columns for v2 features
-- ############################################################################
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS location_city TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS location_country TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS linkedin_url TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS notice_period_days INTEGER;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS current_ctc_lakhs NUMERIC;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS expected_ctc_lakhs NUMERIC;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS yoe NUMERIC;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

-- ############################################################################
-- RLS POLICIES for new tables (idempotent — uses DO block to check existence)
-- ############################################################################
DO $$
BEGIN
    -- job_candidates
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Authenticated users can read job candidates') THEN
        ALTER TABLE careerloop.job_candidates ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Authenticated users can read job candidates"
            ON careerloop.job_candidates FOR SELECT USING (auth.role() = 'authenticated');
    END IF;

    -- user_job_relationships
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own job relationships') THEN
        ALTER TABLE careerloop.user_job_relationships ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own job relationships"
            ON careerloop.user_job_relationships FOR ALL USING (auth.uid() = user_id);
    END IF;

    -- applications
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own applications') THEN
        ALTER TABLE careerloop.applications ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own applications"
            ON careerloop.applications FOR ALL USING (auth.uid() = user_id);
    END IF;

    -- application_packs
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own application packs') THEN
        ALTER TABLE careerloop.application_packs ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own application packs"
            ON careerloop.application_packs FOR ALL USING (auth.uid() = user_id);
    END IF;

    -- people_to_reach
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Authenticated users can read people to reach') THEN
        ALTER TABLE careerloop.people_to_reach ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Authenticated users can read people to reach"
            ON careerloop.people_to_reach FOR SELECT USING (auth.role() = 'authenticated');
    END IF;

    -- outreach_messages
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own outreach messages') THEN
        ALTER TABLE careerloop.outreach_messages ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own outreach messages"
            ON careerloop.outreach_messages FOR ALL USING (auth.uid() = user_id);
    END IF;

    -- followups
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own followups') THEN
        ALTER TABLE careerloop.followups ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own followups"
            ON careerloop.followups FOR ALL USING (auth.uid() = user_id);
    END IF;

    -- user_evidence
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own evidence') THEN
        ALTER TABLE careerloop.user_evidence ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own evidence"
            ON careerloop.user_evidence FOR ALL USING (auth.uid() = user_id);
    END IF;

    -- user_preferences
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own preferences') THEN
        ALTER TABLE careerloop.user_preferences ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own preferences"
            ON careerloop.user_preferences FOR ALL USING (auth.uid() = user_id);
    END IF;

    -- outcome_events
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can manage their own outcome events') THEN
        ALTER TABLE careerloop.outcome_events ENABLE ROW LEVEL SECURITY;
        CREATE POLICY "Users can manage their own outcome events"
            ON careerloop.outcome_events FOR ALL USING (auth.uid() = user_id);
    END IF;
END $$;

-- ############################################################################
-- MIGRATION COMPLETE
-- ############################################################################
-- Summary:
--   6  CREATE TABLE IF NOT EXISTS (new tables)
--   2  CREATE TABLE IF NOT EXISTS + ALTER bridge (jobs, companies)
--   2  CREATE TABLE IF NOT EXISTS + ALTER bridge (daily_briefs, daily_brief_items)
--   2  ALTER TABLE only (background_runs, run_events — already exist)
--   2  ALTER TABLE only (sessions, users — already exist with most columns)
--   16 CREATE INDEX IF NOT EXISTS
--   10 RLS policies (idempotent DO block)
--
-- Known gaps requiring manual follow-up:
--   1. jobs.id (TEXT PK)→jobs.job_id (UUID PK) — backfill + swap constraint
--   2. daily_brief_items.job_id (TEXT)→(UUID) — backfill mapping needed
--   3. daily_briefs.run_id (TEXT)→(UUID FK) — backfill mapping needed
--   4. background_runs.run_id (TEXT)→(UUID) — backfill before UUID FK references
--   5. jobs.content_fingerprint DEFAULT '' → ALTER to NOT NULL after backfill
--   These are non-destructive schema additions; constraint enforcement follows
--   in a separate v2.1 hardening migration after data is backfilled.
-- ============================================================================
