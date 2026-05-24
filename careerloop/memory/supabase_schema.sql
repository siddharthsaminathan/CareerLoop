-- CareerLoop Universal Persistent Career Memory Layer Schema
-- PostgreSQL + Supabase Native Implementation with Row Level Security

-- NOTE: We assume `auth.users` exists as part of Supabase's native auth schema.
-- This schema extends `auth.users` for our multi-tenant application.

-- 1. USERS Table
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    
    -- Core Profile
    master_cv_markdown TEXT,
    parsed_cv_data JSONB,
    
    -- State & Preferences
    employment_state TEXT DEFAULT 'employed_passive',
    urgency INTEGER DEFAULT 5,
    burnout_level INTEGER DEFAULT 5,
    preferred_environments JSONB DEFAULT '[]'::jsonb,
    startup_tolerance INTEGER DEFAULT 5,
    compensation_floor_lakhs REAL DEFAULT 0.0,
    compensation_target_lakhs REAL DEFAULT 0.0,
    work_style_prefs JSONB DEFAULT '{}'::jsonb,
    emotional_constraints JSONB DEFAULT '{}'::jsonb,
    interview_tolerance TEXT DEFAULT 'standard',
    remote_pref TEXT DEFAULT 'hybrid',
    search_posture TEXT DEFAULT 'EXPLORE',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage their own profile" 
    ON public.users FOR ALL USING (auth.uid() = id);

-- 2. SESSIONS Table (Replaces local session_store)
CREATE TABLE IF NOT EXISTS careerloop.sessions (
    user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    state TEXT NOT NULL DEFAULT 'NEW_USER',
    current_job_id TEXT,
    onboarding_step INTEGER DEFAULT 0,
    temp_profile_data JSONB,
    active_artifact_type TEXT,
    active_artifact_id TEXT,
    active_job_id TEXT,
    active_brief_id TEXT,
    active_pack_id TEXT,
    current_selection_index INTEGER,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE careerloop.sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage their own session" 
    ON careerloop.sessions FOR ALL USING (auth.uid() = user_id);

-- 2a. DAILY_BRIEFS Tables
CREATE TABLE IF NOT EXISTS careerloop.daily_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    date_str TEXT NOT NULL,
    run_id TEXT,
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, date_str)
);

ALTER TABLE careerloop.daily_briefs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage their own daily briefs" 
    ON careerloop.daily_briefs FOR ALL USING (auth.uid() = user_id);

CREATE TABLE IF NOT EXISTS careerloop.daily_brief_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_id UUID NOT NULL REFERENCES careerloop.daily_briefs(id) ON DELETE CASCADE,
    item_index INTEGER NOT NULL,
    job_id TEXT NOT NULL,
    title TEXT,
    company TEXT,
    location TEXT,
    fit_score REAL,
    recommendation_reason TEXT,
    risk_summary TEXT,
    route_recommendation TEXT,
    UNIQUE(brief_id, item_index)
);

ALTER TABLE careerloop.daily_brief_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage their own daily brief items" 
    ON careerloop.daily_brief_items FOR ALL USING (
        EXISTS (
            SELECT 1 FROM careerloop.daily_briefs b 
            WHERE b.id = careerloop.daily_brief_items.brief_id AND b.user_id = auth.uid()
        )
    );

-- 3. STRATEGIC_TRACKS Table
CREATE TABLE IF NOT EXISTS careerloop.strategic_tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    track_identity TEXT NOT NULL,
    positioning_strategy TEXT DEFAULT '',
    resume_variant_id TEXT DEFAULT '',
    outreach_style TEXT DEFAULT '',
    success_metrics JSONB DEFAULT '{}'::jsonb,
    recruiter_response_patterns JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE careerloop.strategic_tracks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage their own tracks" 
    ON careerloop.strategic_tracks FOR ALL USING (auth.uid() = user_id);

-- 4. APPLICATION_LEDGER Table
CREATE TABLE IF NOT EXISTS careerloop.application_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    track_id UUID REFERENCES careerloop.strategic_tracks(id) ON DELETE SET NULL,
    job_fingerprint TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    company_normalized TEXT NOT NULL,
    location TEXT DEFAULT '',
    work_mode TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'DISCOVERED',
    application_url TEXT DEFAULT '',
    source TEXT DEFAULT 'unknown',
    source_url TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    recruiter_name TEXT DEFAULT '',
    recruiter_contacted INTEGER DEFAULT 0,
    follow_up_due_at TIMESTAMPTZ,
    interview_stage TEXT DEFAULT '',
    interview_outcomes JSONB DEFAULT '{}'::jsonb,
    fit_score REAL,
    fit_breakdown JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE careerloop.application_ledger ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage their own applications" 
    ON careerloop.application_ledger FOR ALL USING (auth.uid() = user_id);

-- 5. EVENT_TIMELINE Table
CREATE TABLE IF NOT EXISTS careerloop.event_timeline (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    reference_id TEXT DEFAULT '',
    reference_type TEXT DEFAULT '',
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE careerloop.event_timeline ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage their own events" 
    ON careerloop.event_timeline FOR ALL USING (auth.uid() = user_id);

-- 6. COMPANY_MEMORY Table (Per-user private company intelligence)
CREATE TABLE IF NOT EXISTS careerloop.company_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    company_normalized TEXT NOT NULL,
    company_intelligence TEXT DEFAULT '',
    compensation_analysis TEXT DEFAULT '',
    hiring_urgency TEXT DEFAULT '',
    recruiter_insights TEXT DEFAULT '',
    glassdoor_synthesis TEXT DEFAULT '',
    company_maturity TEXT DEFAULT '',
    org_structure_patterns TEXT DEFAULT '',
    startup_risk REAL DEFAULT 5.0,
    work_culture_patterns TEXT DEFAULT '',
    known_interview_loops TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, company_normalized)
);

ALTER TABLE careerloop.company_memory ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage their own company memory" 
    ON careerloop.company_memory FOR ALL USING (auth.uid() = user_id);

-- 7. POSITIONING_MEMORY Table
CREATE TABLE IF NOT EXISTS careerloop.positioning_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    track_id UUID NOT NULL REFERENCES careerloop.strategic_tracks(id) ON DELETE CASCADE,
    company_normalized TEXT NOT NULL,
    generated_narrative TEXT NOT NULL,
    framing_strategy TEXT DEFAULT '',
    successful_tone TEXT DEFAULT '',
    rejected_tone TEXT DEFAULT '',
    recruiter_positive_patterns JSONB DEFAULT '{}'::jsonb,
    converted INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE careerloop.positioning_memory ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage their own positioning memory" 
    ON careerloop.positioning_memory FOR ALL USING (auth.uid() = user_id);

-- 8. GLOBAL TABLES (COMPANIES, JOBS)
-- These are system-level tracking tables, readable by all authenticated users
-- but writable only by the system/admin role.

CREATE TABLE IF NOT EXISTS careerloop.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    domain TEXT,
    city TEXT DEFAULT '',
    sector TEXT DEFAULT '',
    subsector TEXT DEFAULT '',
    ats_provider TEXT DEFAULT 'unknown',
    career_page_url TEXT DEFAULT '',
    ats_url TEXT DEFAULT '',
    linkedin_url TEXT DEFAULT '',
    employee_estimate INTEGER DEFAULT 0,
    crawl_status TEXT DEFAULT 'pending',
    last_crawled_at TIMESTAMPTZ,
    last_job_count INTEGER DEFAULT 0,
    source TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE careerloop.companies ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read global companies" 
    ON careerloop.companies FOR SELECT USING (auth.role() = 'authenticated');
-- Writable only by service role (handled automatically bypassing RLS)

CREATE TABLE IF NOT EXISTS careerloop.jobs (
    id TEXT PRIMARY KEY, -- sha256 fingerprint
    company_id UUID REFERENCES careerloop.companies(id) ON DELETE SET NULL,
    canonical_id TEXT,
    title TEXT NOT NULL,
    company_name TEXT NOT NULL,
    location TEXT DEFAULT '',
    source TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    apply_url TEXT DEFAULT '',
    role_summary TEXT DEFAULT '',
    responsibilities TEXT DEFAULT '',
    requirements TEXT DEFAULT '',
    benefits TEXT DEFAULT '',
    raw_jd_text TEXT DEFAULT '',
    extraction_confidence REAL DEFAULT 1.0,
    posted_at TEXT DEFAULT '',
    verified_active INTEGER DEFAULT 0,
    scraped_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE careerloop.jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read global jobs" 
    ON careerloop.jobs FOR SELECT USING (auth.role() = 'authenticated');

-- 9. BACKGROUND_RUNS Table (Layer 3 State)
CREATE TABLE IF NOT EXISTS careerloop.background_runs (
    run_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    run_type TEXT NOT NULL,
    status TEXT DEFAULT 'QUEUED',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE careerloop.background_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own background runs" 
    ON careerloop.background_runs FOR SELECT USING (auth.uid() = user_id);

-- 10. RUN_EVENTS Table
CREATE TABLE IF NOT EXISTS careerloop.run_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES careerloop.background_runs(run_id) ON DELETE CASCADE,
    message TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE careerloop.run_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view events for their runs" 
    ON careerloop.run_events FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM careerloop.background_runs r
            WHERE r.run_id = careerloop.run_events.run_id AND r.user_id = auth.uid()
        )
    );
