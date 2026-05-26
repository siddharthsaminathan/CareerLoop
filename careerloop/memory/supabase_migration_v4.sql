-- CareerLoop Migration V4 — Multi-User Identity Columns
-- Run once against your Supabase database.
-- Safe to re-run (all statements are idempotent).

-- 1. Add Telegram identity columns to careerloop.users
ALTER TABLE careerloop.users
    ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT UNIQUE,
    ADD COLUMN IF NOT EXISTS phone_number TEXT,
    ADD COLUMN IF NOT EXISTS handle TEXT;

-- 2. Index for fast lookup by telegram_chat_id (the primary lookup path)
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_telegram_chat_id
    ON careerloop.users (telegram_chat_id)
    WHERE telegram_chat_id IS NOT NULL;

-- 3. Explicit profile columns — removes dependency on work_style_prefs JSONB blob
--    for the 5 required onboarding fields. JSONB blob stays as overflow.
ALTER TABLE careerloop.users
    ADD COLUMN IF NOT EXISTS target_roles TEXT,
    ADD COLUMN IF NOT EXISTS target_cities TEXT,
    ADD COLUMN IF NOT EXISTS salary_expectations TEXT,
    ADD COLUMN IF NOT EXISTS notice_period TEXT,
    ADD COLUMN IF NOT EXISTS career_mode TEXT DEFAULT 'explore';

-- 4. Onboarding status flag — lets the system know if profile is complete
--    without checking individual field nullability.
ALTER TABLE careerloop.users
    ADD COLUMN IF NOT EXISTS onboarding_complete BOOLEAN DEFAULT FALSE;

-- 5. Backfill onboarding_complete for existing users who have a CV
UPDATE careerloop.users
SET onboarding_complete = TRUE
WHERE master_cv_markdown IS NOT NULL
  AND LENGTH(master_cv_markdown) > 50
  AND onboarding_complete = FALSE;

-- 6. Backfill target_roles / target_cities / salary / notice from work_style_prefs JSONB
--    for existing users who have the data there.
UPDATE careerloop.users
SET
    target_roles     = COALESCE(target_roles,     work_style_prefs->>'target_roles'),
    target_cities    = COALESCE(target_cities,    work_style_prefs->>'target_cities'),
    salary_expectations = COALESCE(salary_expectations, work_style_prefs->>'salary_expectations'),
    notice_period    = COALESCE(notice_period,    work_style_prefs->>'notice_period'),
    career_mode      = COALESCE(career_mode,      work_style_prefs->>'aggressiveness', 'explore')
WHERE work_style_prefs IS NOT NULL
  AND work_style_prefs != '{}'::jsonb;
