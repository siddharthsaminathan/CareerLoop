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

-- 7. COMPANIES Table — employer graph (shared, not per-user)
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,                   -- normalized domain slug e.g. "razorpay"
    name TEXT NOT NULL,
    domain TEXT,                           -- razorpay.com
    city TEXT DEFAULT '',
    sector TEXT DEFAULT '',                -- MECE sector taxonomy (PRD §18)
    subsector TEXT DEFAULT '',
    ats_provider TEXT DEFAULT 'unknown',   -- greenhouse|lever|ashby|workday|custom|none|unknown
    career_page_url TEXT DEFAULT '',
    ats_url TEXT DEFAULT '',               -- direct ATS endpoint
    linkedin_url TEXT DEFAULT '',
    employee_estimate INTEGER DEFAULT 0,
    crawl_status TEXT DEFAULT 'pending',   -- pending|active|warm|cold|dead
    last_crawled_at TEXT,
    last_job_count INTEGER DEFAULT 0,
    source TEXT DEFAULT '',                -- how we discovered this company
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_companies_city ON companies(city);
CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector);
CREATE INDEX IF NOT EXISTS idx_companies_ats ON companies(ats_provider);
CREATE INDEX IF NOT EXISTS idx_companies_crawl ON companies(crawl_status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain) WHERE domain IS NOT NULL AND domain != '';

-- 8. COMPANY_SOURCES Table — crawl source registry per company
CREATE TABLE IF NOT EXISTS company_sources (
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,             -- greenhouse|lever|ashby|workday|career_page|linkedin
    crawl_url TEXT NOT NULL,
    last_crawled_at TEXT,
    last_job_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    PRIMARY KEY (company_id, source_type)
);

CREATE INDEX IF NOT EXISTS idx_company_sources_company ON company_sources(company_id);

-- 9. ROLE_KEYWORDS Table — LLM-generated keyword cache per role/function
CREATE TABLE IF NOT EXISTS role_keywords (
    role_name TEXT PRIMARY KEY,            -- normalized role/function name
    keywords TEXT NOT NULL,                -- JSON array of search keywords
    search_queries TEXT DEFAULT '[]',      -- JSON array of ready-to-use queries
    sector_hints TEXT DEFAULT '[]',        -- JSON array of likely sectors
    generated_at TEXT NOT NULL,
    usage_count INTEGER DEFAULT 1,
    last_used_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_role_keywords_last_used ON role_keywords(last_used_at);

-- 10. COMPANY_FUNCTIONS Table — function-probability per company
CREATE TABLE IF NOT EXISTS company_functions (
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    function TEXT NOT NULL,                -- normalized function slug
    probability REAL DEFAULT 0.5,          -- 0.0-1.0
    signal_source TEXT DEFAULT '',         -- sector_inference|employee_titles|tech_stack|historical_jobs
    updated_at TEXT NOT NULL,
    PRIMARY KEY (company_id, function)
);

CREATE INDEX IF NOT EXISTS idx_company_functions_function ON company_functions(function);
CREATE INDEX IF NOT EXISTS idx_company_functions_probability ON company_functions(probability);

-- 11. JOBS Table — canonical job storage with cross-source dedup linkage
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,                   -- canonical_id (sha256 fingerprint)
    company_id TEXT,                       -- nullable: not all jobs map cleanly to a company in registry
    canonical_id TEXT,                     -- self-ref: NULL if this row is canonical
    title TEXT NOT NULL,
    company_name TEXT NOT NULL,
    location TEXT DEFAULT '',
    source TEXT DEFAULT '',                -- greenhouse|lever|ashby|naukri|linkedin|company_portal|...
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
    scraped_at TEXT NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_canonical ON jobs(canonical_id);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
