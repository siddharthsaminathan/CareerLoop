-- Discovery Funnel Observability (2026-05-29)
-- Tracks every stage of the job discovery pipeline per scan run

CREATE TABLE IF NOT EXISTS careerloop.scan_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          TEXT NOT NULL REFERENCES careerloop.background_runs(run_id),
    user_id         UUID NOT NULL,
    stage           TEXT NOT NULL,  -- 'discovered','deduped','location_filter','role_filter','scored','threshold','briefed'
    count_in        INTEGER NOT NULL DEFAULT 0,
    count_out       INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, stage)
);

CREATE TABLE IF NOT EXISTS careerloop.scan_rejection_reasons (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          TEXT NOT NULL REFERENCES careerloop.background_runs(run_id),
    user_id         UUID NOT NULL,
    job_title       TEXT,
    company_name    TEXT,
    source_url      TEXT,
    rejection_stage TEXT NOT NULL,  -- 'LOCATION','ROLE','SALARY','COMPANY_CAP','FIT_SCORE','DUPLICATE'
    rejection_reason TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scan_metrics_run ON careerloop.scan_metrics(run_id);
CREATE INDEX IF NOT EXISTS idx_scan_rejections_run ON careerloop.scan_rejection_reasons(run_id);
CREATE INDEX IF NOT EXISTS idx_scan_rejections_user ON careerloop.scan_rejection_reasons(user_id);
