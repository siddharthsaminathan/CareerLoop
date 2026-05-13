-- CareerLoop Universal Persistent Career Memory Layer Schema
-- Enforces long-term state continuity using local SQLite.

-- Enable foreign key support natively
PRAGMA foreign_keys = ON;

-- 1. USERS Table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    employment_state TEXT DEFAULT 'employed_passive',
    urgency INTEGER DEFAULT 5,
    burnout_level INTEGER DEFAULT 5,
    preferred_environments TEXT DEFAULT '[]',
    startup_tolerance INTEGER DEFAULT 5,
    compensation_floor_lakhs REAL DEFAULT 0.0,
    compensation_target_lakhs REAL DEFAULT 0.0,
    work_style_prefs TEXT DEFAULT '{}',
    emotional_constraints TEXT DEFAULT '{}',
    interview_tolerance TEXT DEFAULT 'standard',
    remote_pref TEXT DEFAULT 'hybrid',
    search_posture TEXT DEFAULT 'EXPLORE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 2. STRATEGIC_TRACKS Table
CREATE TABLE IF NOT EXISTS strategic_tracks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    track_identity TEXT NOT NULL,
    positioning_strategy TEXT DEFAULT '',
    resume_variant_id TEXT DEFAULT '',
    outreach_style TEXT DEFAULT '',
    success_metrics TEXT DEFAULT '{}',
    recruiter_response_patterns TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_strategic_tracks_user ON strategic_tracks(user_id);

-- 3. APPLICATION_LEDGER Table
CREATE TABLE IF NOT EXISTS application_ledger (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    track_id TEXT,
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
    follow_up_due_at TEXT,
    interview_stage TEXT DEFAULT '',
    interview_outcomes TEXT DEFAULT '{}',
    fit_score REAL DEFAULT NULL,
    fit_breakdown TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (track_id) REFERENCES strategic_tracks (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ledger_user ON application_ledger(user_id);
CREATE INDEX IF NOT EXISTS idx_ledger_track ON application_ledger(track_id);
CREATE INDEX IF NOT EXISTS idx_ledger_fingerprint ON application_ledger(job_fingerprint);
CREATE INDEX IF NOT EXISTS idx_ledger_status ON application_ledger(status);
CREATE INDEX IF NOT EXISTS idx_ledger_company ON application_ledger(company_normalized);

-- 4. COMPANY_MEMORY Table
CREATE TABLE IF NOT EXISTS company_memory (
    id TEXT PRIMARY KEY,
    company_normalized TEXT UNIQUE NOT NULL,
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
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_company_memory_normalized ON company_memory(company_normalized);

-- 5. POSITIONING_MEMORY Table
CREATE TABLE IF NOT EXISTS positioning_memory (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    track_id TEXT NOT NULL,
    company_normalized TEXT NOT NULL,
    generated_narrative TEXT NOT NULL,
    framing_strategy TEXT DEFAULT '',
    successful_tone TEXT DEFAULT '',
    rejected_tone TEXT DEFAULT '',
    recruiter_positive_patterns TEXT DEFAULT '{}',
    converted INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (track_id) REFERENCES strategic_tracks (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_positioning_user ON positioning_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_positioning_track ON positioning_memory(track_id);
CREATE INDEX IF NOT EXISTS idx_positioning_company ON positioning_memory(company_normalized);

-- 6. EVENT_TIMELINE Table
CREATE TABLE IF NOT EXISTS event_timeline (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    reference_id TEXT DEFAULT '',
    reference_type TEXT DEFAULT '',
    details TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_events_user ON event_timeline(user_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON event_timeline(event_type);
CREATE INDEX IF NOT EXISTS idx_events_reference ON event_timeline(reference_id, reference_type);
