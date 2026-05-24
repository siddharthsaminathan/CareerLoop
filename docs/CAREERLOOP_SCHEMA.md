# CareerLoop Database Schema

Exported: 2026-05-25T01:10:16.413404

Host: aws-1-ap-southeast-1.pooler.supabase.com:6543


## Schema: `backup_public_schema`


### `backup_public_schema.conversation_logs` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | YES | — |
| `session_id` | uuid | YES | — |
| `google_id` | character varying | YES | — |
| `turn_number` | integer | YES | — |
| `user_input` | text | YES | — |
| `ai_response` | text | YES | — |
| `therapeutic_state` | text | YES | — |
| `state_confidence` | double precision | YES | — |
| `response_time_ms` | integer | YES | — |
| `metadata` | jsonb | YES | — |
| `created_at` | timestamp without time zone | YES | — |

### `backup_public_schema.conversations` (16 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `session_id` | uuid | YES | — |
| `google_id` | character varying | YES | — |
| `title` | character varying | YES | — |
| `created_at` | timestamp without time zone | YES | — |
| `last_activity` | timestamp without time zone | YES | — |
| `turn_count` | integer | YES | — |
| `is_active` | boolean | YES | — |
| `device_info` | jsonb | YES | — |

### `backup_public_schema.messages` (73 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | YES | — |
| `message_id` | character varying | YES | — |
| `session_id` | uuid | YES | — |
| `turn_number` | integer | YES | — |
| `user_message` | text | YES | — |
| `shanthi_response` | text | YES | — |
| `timestamp` | timestamp without time zone | YES | — |
| `input_tokens` | integer | YES | — |
| `output_tokens` | integer | YES | — |
| `processing_time_seconds` | numeric | YES | — |
| `metadata` | jsonb | YES | — |

### `backup_public_schema.session_devices` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | YES | — |
| `session_id` | uuid | YES | — |
| `device_id` | character varying | YES | — |
| `device_type` | character varying | YES | — |
| `browser` | character varying | YES | — |
| `os` | character varying | YES | — |
| `user_agent` | text | YES | — |
| `first_access` | timestamp without time zone | YES | — |
| `last_access` | timestamp without time zone | YES | — |
| `is_active` | boolean | YES | — |

### `backup_public_schema.sessions` (22 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `session_id` | character varying | YES | — |
| `model_type` | character varying | YES | — |
| `created_at` | timestamp without time zone | YES | — |
| `ended_at` | timestamp without time zone | YES | — |
| `user_agent` | text | YES | — |
| `ip_address` | character varying | YES | — |
| `is_test` | boolean | YES | — |

### `backup_public_schema.users` (12 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `google_id` | character varying | YES | — |
| `email` | character varying | YES | — |
| `name` | character varying | YES | — |
| `picture_url` | text | YES | — |
| `created_at` | timestamp without time zone | YES | — |
| `last_login` | timestamp without time zone | YES | — |
| `total_conversations` | integer | YES | — |
| `is_active` | boolean | YES | — |

## Schema: `careerloop`


### `careerloop.application_ledger` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | NO | — |
| `track_id` | uuid | YES | — |
| `job_fingerprint` | text | NO | — |
| `title` | text | NO | — |
| `company` | text | NO | — |
| `company_normalized` | text | NO | — |
| `location` | text | YES | ''::text |
| `work_mode` | text | YES | ''::text |
| `status` | text | NO | 'DISCOVERED'::text |
| `application_url` | text | YES | ''::text |
| `source` | text | YES | 'unknown'::text |
| `source_url` | text | YES | ''::text |
| `notes` | text | YES | ''::text |
| `recruiter_name` | text | YES | ''::text |
| `recruiter_contacted` | integer | YES | 0 |
| `follow_up_due_at` | timestamp with time zone | YES | — |
| `interview_stage` | text | YES | ''::text |
| `interview_outcomes` | jsonb | YES | '{}'::jsonb |
| `fit_score` | real | YES | — |
| `fit_breakdown` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `application_ledger_pkey`

**Foreign Keys (2):**
- `track_id` → `careerloop.strategic_tracks(id)` (`application_ledger_track_id_fkey`)
- `user_id` → `public.users(id)` (`application_ledger_user_id_fkey`)

### `careerloop.application_packs` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `pack_id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | NO | — |
| `job_id` | text | NO | — |
| `run_id` | uuid | NO | — |
| `resume_artifact_id` | text | YES | — |
| `cover_note` | text | YES | — |
| `recruiter_dm` | text | YES | — |
| `referral_dm` | text | YES | — |
| `screening_answers` | jsonb | YES | '{}'::jsonb |
| `company_intel_id` | text | YES | — |
| `status` | text | YES | 'draft'::text |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `application_packs_pkey`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`application_packs_user_id_fkey`)

### `careerloop.applications` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `application_id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | NO | — |
| `job_id` | text | NO | — |
| `status` | text | YES | 'prepared'::text |
| `application_pack_id` | uuid | YES | — |
| `applied_at` | timestamp with time zone | YES | — |
| `apply_channel` | text | YES | — |
| `notes` | text | YES | — |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `applications_pkey`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`applications_user_id_fkey`)

### `careerloop.background_runs` (3 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `run_id` | text | NO | — |
| `user_id` | uuid | NO | — |
| `run_type` | text | NO | — |
| `status` | text | YES | 'QUEUED'::text |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `started_at` | timestamp with time zone | YES | now() |
| `error_code` | text | YES | — |
| `error_summary` | text | YES | — |
| `params` | jsonb | YES | '{}'::jsonb |
| `stats` | jsonb | YES | '{}'::jsonb |
| `completed_at` | timestamp with time zone | YES | — |

**Indexes (1):**
- `background_runs_pkey`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`background_runs_user_id_fkey`)

### `careerloop.companies` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `domain_slug` | text | NO | — |
| `name` | text | NO | — |
| `domain` | text | YES | — |
| `city` | text | YES | ''::text |
| `sector` | text | YES | ''::text |
| `subsector` | text | YES | ''::text |
| `ats_provider` | text | YES | 'unknown'::text |
| `career_page_url` | text | YES | ''::text |
| `ats_url` | text | YES | ''::text |
| `linkedin_url` | text | YES | ''::text |
| `employee_estimate` | integer | YES | 0 |
| `crawl_status` | text | YES | 'pending'::text |
| `last_crawled_at` | timestamp with time zone | YES | — |
| `last_job_count` | integer | YES | 0 |
| `source` | text | YES | ''::text |
| `is_active` | integer | YES | 1 |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `normalized_name` | text | YES | — |
| `website` | text | YES | — |
| `logo_url` | text | YES | — |
| `industry` | text | YES | — |
| `size` | text | YES | — |
| `funding_stage` | text | YES | — |
| `raw_payload` | jsonb | YES | '{}'::jsonb |
| `first_seen_at` | timestamp with time zone | YES | now() |
| `last_updated_at` | timestamp with time zone | YES | now() |

**Indexes (2):**
- `companies_domain_slug_key`
- `companies_pkey`

### `careerloop.company_memory` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | NO | — |
| `company_normalized` | text | NO | — |
| `company_intelligence` | text | YES | ''::text |
| `compensation_analysis` | text | YES | ''::text |
| `hiring_urgency` | text | YES | ''::text |
| `recruiter_insights` | text | YES | ''::text |
| `glassdoor_synthesis` | text | YES | ''::text |
| `company_maturity` | text | YES | ''::text |
| `org_structure_patterns` | text | YES | ''::text |
| `startup_risk` | real | YES | 5.0 |
| `work_culture_patterns` | text | YES | ''::text |
| `known_interview_loops` | text | YES | ''::text |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (2):**
- `company_memory_pkey`
- `company_memory_user_id_company_normalized_key`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`company_memory_user_id_fkey`)

### `careerloop.daily_brief_items` (1 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `brief_id` | uuid | NO | — |
| `item_index` | integer | NO | — |
| `job_id` | text | NO | — |
| `title` | text | YES | — |
| `company` | text | YES | — |
| `location` | text | YES | — |
| `fit_score` | real | YES | — |
| `recommendation_reason` | text | YES | — |
| `risk_summary` | text | YES | — |
| `route_recommendation` | text | YES | — |

**Indexes (2):**
- `daily_brief_items_brief_id_item_index_key`
- `daily_brief_items_pkey`

**Foreign Keys (1):**
- `brief_id` → `careerloop.daily_briefs(id)` (`daily_brief_items_brief_id_fkey`)

### `careerloop.daily_briefs` (1 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | NO | — |
| `date_str` | text | NO | — |
| `run_id` | text | YES | — |
| `summary` | text | YES | — |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (2):**
- `daily_briefs_pkey`
- `daily_briefs_user_id_date_str_key`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`daily_briefs_user_id_fkey`)

### `careerloop.event_timeline` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | NO | — |
| `event_type` | text | NO | — |
| `reference_id` | text | YES | ''::text |
| `reference_type` | text | YES | ''::text |
| `details` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `event_timeline_pkey`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`event_timeline_user_id_fkey`)

### `careerloop.followups` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `followup_id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | NO | — |
| `application_id` | uuid | YES | — |
| `person_id` | uuid | YES | — |
| `due_at` | timestamp with time zone | YES | — |
| `status` | text | YES | 'pending'::text |
| `draft_message` | text | YES | — |
| `completed_at` | timestamp with time zone | YES | — |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `followups_pkey`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`followups_user_id_fkey`)

### `careerloop.job_candidates` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `candidate_id` | uuid | NO | gen_random_uuid() |
| `run_id` | uuid | NO | — |
| `source` | text | YES | — |
| `query` | text | YES | — |
| `raw_title` | text | YES | — |
| `raw_company` | text | YES | — |
| `raw_location` | text | YES | — |
| `raw_url` | text | YES | — |
| `raw_snippet` | text | YES | — |
| `raw_payload` | jsonb | YES | '{}'::jsonb |
| `extraction_status` | text | YES | 'pending'::text |
| `rejection_stage` | text | YES | — |
| `rejection_reason` | text | YES | — |
| `matched_job_id` | text | YES | — |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `job_candidates_pkey`

### `careerloop.jobs` (1 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | text | NO | — |
| `company_id` | uuid | YES | — |
| `canonical_id` | text | YES | — |
| `title` | text | NO | — |
| `company_name` | text | NO | — |
| `location` | text | YES | ''::text |
| `source` | text | YES | ''::text |
| `source_url` | text | YES | ''::text |
| `apply_url` | text | YES | ''::text |
| `role_summary` | text | YES | ''::text |
| `responsibilities` | text | YES | ''::text |
| `requirements` | text | YES | ''::text |
| `benefits` | text | YES | ''::text |
| `raw_jd_text` | text | YES | ''::text |
| `extraction_confidence` | real | YES | 1.0 |
| `posted_at` | text | YES | ''::text |
| `verified_active` | integer | YES | 0 |
| `scraped_at` | timestamp with time zone | NO | — |
| `created_at` | timestamp with time zone | YES | now() |
| `job_id` | uuid | YES | gen_random_uuid() |
| `normalized_title` | text | YES | — |
| `location_raw` | text | YES | — |
| `location_city` | text | YES | — |
| `location_country` | text | YES | — |
| `is_india_role` | boolean | YES | false |
| `work_mode` | text | YES | — |
| `salary_min` | numeric | YES | — |
| `salary_max` | numeric | YES | — |
| `salary_currency` | text | YES | 'INR'::text |
| `jd_text` | text | YES | — |
| `jd_hash` | text | YES | — |
| `content_fingerprint` | text | YES | — |
| `first_seen_at` | timestamp with time zone | YES | now() |
| `last_seen_at` | timestamp with time zone | YES | now() |
| `expires_at` | timestamp with time zone | YES | — |
| `status` | text | YES | 'active'::text |
| `raw_payload` | jsonb | YES | '{}'::jsonb |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (2):**
- `idx_jobs_fingerprint_unique`
- `jobs_pkey`

**Foreign Keys (1):**
- `company_id` → `careerloop.companies(id)` (`jobs_company_id_fkey`)

### `careerloop.outcome_events` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `outcome_id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | NO | — |
| `job_id` | text | YES | — |
| `application_id` | uuid | YES | — |
| `event_type` | text | YES | — |
| `payload` | jsonb | YES | '{}'::jsonb |
| `occurred_at` | timestamp with time zone | YES | now() |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `outcome_events_pkey`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`outcome_events_user_id_fkey`)

### `careerloop.outreach_messages` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `message_id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | NO | — |
| `person_id` | uuid | YES | — |
| `job_id` | text | YES | — |
| `application_id` | uuid | YES | — |
| `message_type` | text | YES | — |
| `body` | text | YES | — |
| `status` | text | YES | 'drafted'::text |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `outreach_messages_pkey`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`outreach_messages_user_id_fkey`)

### `careerloop.people_to_reach` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `person_id` | uuid | NO | gen_random_uuid() |
| `company_id` | uuid | YES | — |
| `job_id` | text | YES | — |
| `name` | text | YES | — |
| `title` | text | YES | — |
| `linkedin_url` | text | YES | — |
| `source` | text | YES | — |
| `relevance_reason` | text | YES | — |
| `confidence` | numeric | YES | 0.5 |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `people_to_reach_pkey`

### `careerloop.positioning_memory` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | NO | — |
| `track_id` | uuid | NO | — |
| `company_normalized` | text | NO | — |
| `generated_narrative` | text | NO | — |
| `framing_strategy` | text | YES | ''::text |
| `successful_tone` | text | YES | ''::text |
| `rejected_tone` | text | YES | ''::text |
| `recruiter_positive_patterns` | jsonb | YES | '{}'::jsonb |
| `converted` | integer | YES | 0 |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `positioning_memory_pkey`

**Foreign Keys (2):**
- `track_id` → `careerloop.strategic_tracks(id)` (`positioning_memory_track_id_fkey`)
- `user_id` → `public.users(id)` (`positioning_memory_user_id_fkey`)

### `careerloop.run_events` (7 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `event_id` | text | NO | — |
| `run_id` | text | NO | — |
| `message` | text | YES | — |
| `timestamp` | timestamp with time zone | YES | now() |
| `event_type` | text | YES | 'info'::text |
| `payload` | jsonb | YES | '{}'::jsonb |

**Indexes (1):**
- `run_events_pkey`

**Foreign Keys (1):**
- `run_id` → `careerloop.background_runs(run_id)` (`run_events_run_id_fkey`)

### `careerloop.sessions` (13 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `user_id` | uuid | NO | — |
| `state` | text | NO | 'IDLE'::text |
| `current_job_id` | text | YES | — |
| `onboarding_step` | integer | YES | 0 |
| `temp_profile_data` | jsonb | YES | — |
| `updated_at` | timestamp with time zone | YES | now() |
| `active_artifact_type` | text | YES | — |
| `active_artifact_id` | text | YES | — |
| `active_job_id` | text | YES | — |
| `active_brief_id` | text | YES | — |
| `active_pack_id` | text | YES | — |
| `current_selection_index` | integer | YES | — |

**Indexes (1):**
- `sessions_pkey`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`sessions_user_id_fkey`)

### `careerloop.strategic_tracks` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | NO | — |
| `track_identity` | text | NO | — |
| `positioning_strategy` | text | YES | ''::text |
| `resume_variant_id` | text | YES | ''::text |
| `outreach_style` | text | YES | ''::text |
| `success_metrics` | jsonb | YES | '{}'::jsonb |
| `recruiter_response_patterns` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `strategic_tracks_pkey`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`strategic_tracks_user_id_fkey`)

### `careerloop.user_evidence` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `evidence_id` | uuid | NO | gen_random_uuid() |
| `user_id` | uuid | NO | — |
| `evidence_type` | text | YES | — |
| `title` | text | YES | — |
| `description` | text | YES | — |
| `proof_url` | text | YES | — |
| `source` | text | YES | — |
| `confidence` | numeric | YES | 0.5 |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `user_evidence_pkey`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`user_evidence_user_id_fkey`)

### `careerloop.user_job_relationships` (2 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `user_id` | uuid | NO | — |
| `job_id` | text | NO | — |
| `fit_score` | numeric | YES | — |
| `fit_label` | text | YES | — |
| `match_status` | text | YES | 'matched'::text |
| `rejection_reason` | text | YES | — |
| `user_seen_at` | timestamp with time zone | YES | — |
| `shown_in_brief_id` | uuid | YES | — |
| `swiped_action` | text | YES | — |
| `interest_level` | text | YES | — |
| `route_recommendation` | text | YES | — |
| `personalization_payload` | jsonb | YES | '{}'::jsonb |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `user_job_relationships_pkey`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`user_job_relationships_user_id_fkey`)

### `careerloop.user_preferences` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `user_id` | uuid | NO | — |
| `target_roles` | jsonb | YES | '[]'::jsonb |
| `target_cities` | jsonb | YES | '[]'::jsonb |
| `salary_min` | numeric | YES | — |
| `salary_max` | numeric | YES | — |
| `notice_period` | text | YES | — |
| `work_mode` | text | YES | — |
| `avoid_companies` | jsonb | YES | '[]'::jsonb |
| `avoid_role_types` | jsonb | YES | '[]'::jsonb |
| `aggressiveness` | text | YES | — |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (1):**
- `user_preferences_pkey`

**Foreign Keys (1):**
- `user_id` → `public.users(id)` (`user_preferences_user_id_fkey`)

## Schema: `emote_app`


### `emote_app.banner_lines` (7 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | NO | nextval('emote_app.banner_lines_id_seq'::regclass) |
| `content` | text | NO | — |
| `date_added` | date | NO | CURRENT_DATE |
| `is_active` | boolean | NO | true |
| `date_stopped` | date | YES | — |

**Indexes (2):**
- `banner_lines_pkey`
- `idx_banner_lines_active`

### `emote_app.blog_images` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | NO | nextval('emote_app.blog_images_id_seq'::regclass) |
| `blog_post_id` | integer | YES | — |
| `storage_path` | character varying | NO | — |
| `public_url` | character varying | NO | — |
| `alt_text` | character varying | YES | — |
| `file_size_kb` | integer | YES | — |
| `mime_type` | character varying | YES | — |
| `uploaded_at` | timestamp with time zone | YES | now() |

**Indexes (2):**
- `blog_images_pkey`
- `idx_blog_images_post`

**Foreign Keys (1):**
- `blog_post_id` → `emote_app.blog_posts(id)` (`blog_images_blog_post_id_fkey`)

### `emote_app.blog_posts` (6 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | NO | nextval('emote_app.blog_posts_id_seq'::regclass) |
| `slug` | character varying | NO | — |
| `title` | character varying | NO | — |
| `excerpt` | character varying | YES | — |
| `markdown_body` | text | NO | — |
| `author_id` | character varying | NO | — |
| `author_name` | character varying | NO | — |
| `author_title` | character varying | YES | ''::character varying |
| `cover_image_url` | character varying | YES | — |
| `tags` | ARRAY | YES | '{}'::text[] |
| `meta_title` | character varying | YES | — |
| `meta_description` | character varying | YES | — |
| `meta_keywords` | ARRAY | YES | '{}'::text[] |
| `canonical_url` | character varying | YES | — |
| `og_image_url` | character varying | YES | — |
| `reading_time_minutes` | integer | YES | 5 |
| `word_count` | integer | YES | 0 |
| `status` | character varying | NO | 'draft'::character varying |
| `is_published` | boolean | YES | false |
| `published_at` | timestamp with time zone | YES | — |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `is_active` | boolean | YES | true |
| `youtube_url` | text | YES | — |
| `spotify_url` | text | YES | — |

**Indexes (4):**
- `blog_posts_pkey`
- `blog_posts_slug_key`
- `idx_blog_posts_author`
- `idx_blog_posts_published`

### `emote_app.checkpoint_blobs` (243 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `thread_id` | text | NO | — |
| `checkpoint_ns` | text | NO | ''::text |
| `channel` | text | NO | — |
| `version` | text | NO | — |
| `type` | text | NO | — |
| `blob` | bytea | YES | — |

**Indexes (2):**
- `checkpoint_blobs_pkey`
- `checkpoint_blobs_thread_id_idx`

### `emote_app.checkpoint_migrations` (10 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `v` | integer | NO | — |

**Indexes (1):**
- `checkpoint_migrations_pkey`

### `emote_app.checkpoint_writes` (467 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `thread_id` | text | NO | — |
| `checkpoint_ns` | text | NO | ''::text |
| `checkpoint_id` | text | NO | — |
| `task_id` | text | NO | — |
| `idx` | integer | NO | — |
| `channel` | text | NO | — |
| `type` | text | YES | — |
| `blob` | bytea | NO | — |
| `task_path` | text | NO | ''::text |

**Indexes (2):**
- `checkpoint_writes_pkey`
- `checkpoint_writes_thread_id_idx`

### `emote_app.checkpoints` (158 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `thread_id` | text | NO | — |
| `checkpoint_ns` | text | NO | ''::text |
| `checkpoint_id` | text | NO | — |
| `parent_checkpoint_id` | text | YES | — |
| `type` | text | YES | — |
| `checkpoint` | jsonb | NO | — |
| `metadata` | jsonb | NO | '{}'::jsonb |

**Indexes (2):**
- `checkpoints_pkey`
- `checkpoints_thread_id_idx`

### `emote_app.conversation_logs_json` (10289 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `session_id` | uuid | NO | — |
| `google_id` | character varying | NO | — |
| `log_data` | jsonb | NO | — |
| `created_at` | timestamp without time zone | YES | CURRENT_TIMESTAMP |

**Indexes (4):**
- `conversation_logs_json_pkey`
- `idx_conversation_logs_created_at`
- `idx_conversation_logs_google_id`
- `idx_conversation_logs_session_id`

### `emote_app.conversations` (1816 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `session_id` | uuid | NO | gen_random_uuid() |
| `google_id` | character varying | YES | — |
| `title` | character varying | YES | — |
| `created_at` | timestamp without time zone | YES | CURRENT_TIMESTAMP |
| `last_activity` | timestamp without time zone | YES | CURRENT_TIMESTAMP |
| `turn_count` | integer | YES | 0 |
| `is_active` | boolean | YES | true |
| `device_info` | jsonb | YES | '{}'::jsonb |
| `session_state` | jsonb | YES | — |
| `total_turns` | integer | YES | 0 |
| `deployment_version` | character varying | YES | — |
| `session_mode` | character varying | YES | 'classic'::character varying |
| `pattern_id` | character varying | YES | NULL::character varying |

**Indexes (6):**
- `conversations_pkey`
- `idx_conversations_created_at`
- `idx_conversations_google_id`
- `idx_conversations_last_activity`
- `idx_conversations_session_state`
- `idx_conversations_user_activity`

**Foreign Keys (1):**
- `google_id` → `emote_app.users(google_id)` (`conversations_google_id_fkey`)

### `emote_app.cookie_consents` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `google_id` | character varying | NO | — |
| `consent_type` | character varying | NO | — |
| `created_at` | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| `updated_at` | timestamp with time zone | YES | CURRENT_TIMESTAMP |

**Indexes (4):**
- `cookie_consents_google_id_key`
- `cookie_consents_pkey`
- `idx_cookie_consents_created_at`
- `idx_cookie_consents_google_id`

**Foreign Keys (1):**
- `google_id` → `emote_app.users(google_id)` (`cookie_consents_google_id_fkey`)

### `emote_app.crack_incidents` (30 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `incident_id` | character varying | NO | — |
| `title` | character varying | NO | — |
| `description` | text | YES | — |
| `severity` | character varying | YES | — |
| `source` | character varying | YES | — |
| `source_check_id` | character varying | YES | — |
| `status` | character varying | YES | 'detected'::character varying |
| `layer` | character varying | YES | — |
| `component` | character varying | YES | — |
| `fix_commit` | character varying | YES | — |
| `fix_version` | character varying | YES | — |
| `deployed_at` | timestamp with time zone | YES | — |
| `verified_at` | timestamp with time zone | YES | — |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `metadata` | jsonb | YES | — |

**Indexes (3):**
- `crack_incidents_incident_id_key`
- `crack_incidents_pkey`
- `idx_crack_incidents_status`

### `emote_app.crisis_resources` (38 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | NO | nextval('emote_app.crisis_resources_id_seq'::regclass) |
| `country_name` | text | NO | — |
| `country_code` | character | NO | — |
| `organization` | text | NO | — |
| `phone_number` | text | YES | — |
| `sms_number` | text | YES | — |
| `website_url` | text | YES | — |
| `available_hours` | text | YES | — |
| `services` | ARRAY | NO | '{}'::text[] |
| `languages` | ARRAY | NO | '{}'::text[] |
| `sort_order` | integer | NO | 0 |
| `is_active` | boolean | NO | true |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (3):**
- `crisis_resources_pkey`
- `idx_crisis_resources_country_code`
- `idx_crisis_resources_is_active`

### `emote_app.crisis_state` (49 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | NO | nextval('emote_app.crisis_state_id_seq'::regclass) |
| `session_id` | text | NO | — |
| `google_id` | text | NO | — |
| `status` | text | NO | 'not_in_crisis'::text |
| `current_level` | integer | NO | 0 |
| `highest_level` | integer | NO | 0 |
| `turns_in_crisis` | integer | NO | 0 |
| `turns_stable` | integer | NO | 0 |
| `state_data` | jsonb | NO | '{}'::jsonb |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (5):**
- `crisis_state_pkey`
- `crisis_state_session_id_key`
- `idx_crisis_state_google_id`
- `idx_crisis_state_session`
- `idx_crisis_state_status`

### `emote_app.dynamic_conversation_starters` (346 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | NO | nextval('emote_app.dynamic_conversation_starters_id_seq'::regclass) |
| `user_id` | text | NO | — |
| `session_id` | text | NO | — |
| `starters` | jsonb | NO | — |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (4):**
- `dynamic_conversation_starters_pkey`
- `dynamic_conversation_starters_user_id_session_id_key`
- `idx_dynamic_starters_session_id`
- `idx_dynamic_starters_user_id`

### `emote_app.email_nudges` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `google_id` | text | NO | — |
| `email` | text | NO | — |
| `sender_email` | text | NO | — |
| `cadence_type` | text | NO | — |
| `conversation_count_at_send` | integer | YES | 0 |
| `template_id` | text | NO | — |
| `theme_selection_signal` | text | YES | — |
| `subject` | text | NO | — |
| `resend_email_id` | text | YES | — |
| `open_tracked` | boolean | YES | false |
| `click_tracked` | boolean | YES | false |
| `sent_at` | timestamp with time zone | YES | now() |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (3):**
- `email_nudges_pkey`
- `idx_email_nudges_google_id`
- `idx_email_nudges_sent_at`

### `emote_app.entity_canonical` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `google_id` | character varying | NO | — |
| `canonical_name` | character varying | NO | — |
| `aliases` | jsonb | YES | '[]'::jsonb |
| `domain` | character varying | YES | — |
| `relationship_type` | character varying | YES | — |
| `last_seen` | timestamp without time zone | YES | CURRENT_TIMESTAMP |
| `mention_count` | integer | YES | 1 |
| `created_at` | timestamp without time zone | YES | CURRENT_TIMESTAMP |

**Indexes (3):**
- `entity_canonical_google_id_canonical_name_key`
- `entity_canonical_pkey`
- `idx_entity_canonical_google_id`

### `emote_app.feedback_logs` (104 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `feedback_id` | uuid | NO | gen_random_uuid() |
| `user_id` | character varying | NO | — |
| `session_id` | uuid | NO | — |
| `conversation_title` | text | YES | — |
| `feeling_before` | character varying | YES | — |
| `feeling_after` | character varying | YES | — |
| `understood_today` | character varying | YES | — |
| `useful_takeaway` | character varying | YES | — |
| `helpful_part` | text | YES | — |
| `frustrating_missing` | text | YES | — |
| `created_at` | timestamp with time zone | NO | now() |
| `updated_at` | timestamp with time zone | NO | now() |
| `conversation_depth` | character varying | YES | NULL::character varying |
| `would_return` | character varying | YES | NULL::character varying |

**Indexes (6):**
- `feedback_logs_pkey`
- `idx_feedback_logs_created`
- `idx_feedback_logs_created_at`
- `idx_feedback_logs_session`
- `idx_feedback_logs_session_id`
- `idx_feedback_logs_user_id`

**Foreign Keys (2):**
- `session_id` → `emote_app.conversations(session_id)` (`feedback_logs_session_id_fkey`)
- `user_id` → `emote_app.users(google_id)` (`feedback_logs_user_id_fkey`)

### `emote_app.guest_conversations` (10 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `session_id` | uuid | NO | — |
| `guest_id` | uuid | NO | — |
| `title` | character varying | YES | 'Guest Conversation'::character varying |
| `created_at` | timestamp without time zone | NO | now() |
| `last_activity` | timestamp without time zone | NO | now() |
| `turn_count` | integer | NO | 0 |
| `is_active` | boolean | NO | true |
| `total_turns` | integer | NO | 0 |

**Indexes (2):**
- `guest_conversations_pkey`
- `idx_guest_conversations_guest_id`

**Foreign Keys (1):**
- `guest_id` → `emote_app.guest_users(guest_id)` (`guest_conversations_guest_id_fkey`)

### `emote_app.guest_messages` (78 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | NO | nextval('emote_app.guest_messages_id_seq'::regclass) |
| `guest_id` | uuid | NO | — |
| `session_id` | uuid | NO | — |
| `role` | character varying | NO | — |
| `content` | text | NO | — |
| `timestamp` | timestamp with time zone | NO | now() |
| `turn_number` | integer | YES | — |

**Indexes (4):**
- `guest_messages_pkey`
- `idx_guest_messages_guest_id`
- `idx_guest_messages_session_id`
- `idx_guest_messages_timestamp`

**Foreign Keys (1):**
- `guest_id` → `emote_app.guest_users(guest_id)` (`guest_messages_guest_id_fkey`)

### `emote_app.guest_users` (13 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `guest_id` | uuid | NO | gen_random_uuid() |
| `created_at` | timestamp with time zone | NO | now() |
| `last_active_at` | timestamp with time zone | NO | now() |
| `ip_hash` | character varying | YES | — |
| `user_agent_hash` | character varying | YES | — |
| `converted_user_id` | character varying | YES | — |
| `session_id` | uuid | NO | gen_random_uuid() |
| `turns_used` | integer | NO | 0 |
| `status` | character varying | NO | 'active'::character varying |

**Indexes (6):**
- `guest_users_pkey`
- `idx_guest_users_converted_user_id`
- `idx_guest_users_created_at`
- `idx_guest_users_ip_hash`
- `idx_guest_users_session_id`
- `idx_guest_users_status`

### `emote_app.json_cache` (6376 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `content_hash` | character varying | NO | — |
| `content_text` | text | NO | — |
| `embedding_type` | character varying | NO | 'json_parsing'::character varying |
| `embedding_vector` | text | NO | — |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |
| `access_count` | integer | YES | 1 |
| `last_accessed` | timestamp with time zone | YES | now() |
| `user_id` | character varying | YES | — |
| `session_id` | uuid | YES | — |
| `turn_number` | integer | YES | — |
| `message_type` | character varying | YES | — |

**Indexes (8):**
- `idx_json_cache_access_count`
- `idx_json_cache_created_at`
- `idx_json_cache_embedding_type`
- `idx_json_cache_session_id`
- `idx_json_cache_user_id`
- `idx_json_cache_user_session`
- `idx_json_cache_user_turn`
- `json_cache_pkey`

### `emote_app.messages` (6396 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | NO | nextval('emote_app.messages_id_seq'::regclass) |
| `message_id` | character varying | YES | — |
| `session_id` | uuid | YES | gen_random_uuid() |
| `turn_number` | integer | NO | — |
| `user_message` | text | NO | — |
| `shanthi_response` | text | NO | — |
| `timestamp` | timestamp without time zone | YES | CURRENT_TIMESTAMP |
| `input_tokens` | integer | YES | 0 |
| `output_tokens` | integer | YES | 0 |
| `processing_time_seconds` | numeric | YES | 0.0 |
| `metadata` | jsonb | YES | '{}'::jsonb |
| `analysis_tokens` | jsonb | YES | '[]'::jsonb |

**Indexes (9):**
- `idx_messages_message_id`
- `idx_messages_session_id`
- `idx_messages_session_timestamp`
- `idx_messages_session_turn`
- `idx_messages_timestamp`
- `idx_messages_turn_number`
- `messages_message_id_key`
- `messages_pkey`
- `uq_messages_session_turn`

**Foreign Keys (1):**
- `session_id` → `emote_app.conversations(session_id)` (`messages_session_id_fkey`)

### `emote_app.ops_health_checks` (132 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `check_time` | timestamp with time zone | YES | now() |
| `check_id` | character varying | NO | — |
| `layer` | character varying | NO | — |
| `component` | character varying | YES | — |
| `status` | character varying | NO | — |
| `value` | numeric | YES | — |
| `threshold` | numeric | YES | — |
| `sample_size` | integer | YES | — |
| `severity` | character varying | YES | — |
| `details` | jsonb | YES | — |

**Indexes (3):**
- `idx_ops_health_check_id`
- `idx_ops_health_check_time`
- `ops_health_checks_pkey`

### `emote_app.pattern_corrections` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `pattern_id` | text | NO | — |
| `google_id` | text | NO | — |
| `field` | text | NO | — |
| `claim_text` | text | NO | — |
| `user_note` | text | YES | — |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (3):**
- `idx_pattern_corrections_created_at`
- `idx_pattern_corrections_pattern_id`
- `pattern_corrections_pkey`

**Foreign Keys (1):**
- `google_id` → `emote_app.users(google_id)` (`pattern_corrections_google_id_fkey`)

### `emote_app.pattern_feedback` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `pattern_id` | text | NO | — |
| `google_id` | text | NO | — |
| `feedback` | text | NO | — |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (3):**
- `idx_pattern_feedback_inaccurate`
- `pattern_feedback_pattern_id_google_id_key`
- `pattern_feedback_pkey`

**Foreign Keys (1):**
- `google_id` → `emote_app.users(google_id)` (`pattern_feedback_google_id_fkey`)

### `emote_app.pipeline_checkpoints` (29 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `pipeline_run_id` | uuid | NO | — |
| `session_id` | uuid | NO | — |
| `google_id` | character varying | NO | — |
| `step_name` | character varying | NO | — |
| `step_status` | character varying | NO | — |
| `error_message` | text | YES | — |
| `created_at` | timestamp without time zone | YES | now() |

**Indexes (3):**
- `idx_pipeline_checkpoints_run`
- `idx_pipeline_checkpoints_session`
- `pipeline_checkpoints_pkey`

### `emote_app.prompt_leak_incidents` (2096 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | NO | nextval('emote_app.prompt_leak_incidents_id_seq'::regclass) |
| `conversation_id` | text | YES | — |
| `google_id` | text | YES | — |
| `turn_number` | integer | YES | — |
| `raw_response` | text | NO | — |
| `cleaned_response` | text | NO | — |
| `leak_patterns` | ARRAY | NO | '{}'::text[] |
| `source` | text | NO | 'unknown'::text |
| `crisis_level` | text | YES | — |
| `model_used` | text | YES | — |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (3):**
- `idx_prompt_leak_created`
- `idx_prompt_leak_source`
- `prompt_leak_incidents_pkey`

### `emote_app.refresh_tokens` (952 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `user_id` | character varying | NO | — |
| `token_hash` | character varying | NO | — |
| `expires_at` | timestamp with time zone | NO | — |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (4):**
- `idx_rt_expires`
- `idx_rt_hash`
- `idx_rt_user`
- `refresh_tokens_pkey`

### `emote_app.registry_decision_log` (2 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `google_id` | character varying | NO | — |
| `session_id` | uuid | YES | — |
| `pipeline_run_id` | uuid | YES | — |
| `decision_type` | character varying | NO | — |
| `decision_data` | jsonb | NO | '{}'::jsonb |
| `created_at` | timestamp without time zone | YES | now() |

**Indexes (4):**
- `idx_registry_log_pipeline`
- `idx_registry_log_type`
- `idx_registry_log_user_created`
- `registry_decision_log_pkey`

### `emote_app.semantic_embeddings` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `user_id` | character varying | NO | — |
| `session_id` | uuid | NO | — |
| `content_hash` | character varying | NO | — |
| `content_text` | text | NO | — |
| `embedding_vector` | jsonb | NO | — |
| `embedding_type` | character varying | YES | 'general'::character varying |
| `created_at` | timestamp without time zone | YES | CURRENT_TIMESTAMP |
| `updated_at` | timestamp without time zone | YES | CURRENT_TIMESTAMP |

**Indexes (9):**
- `idx_semantic_embeddings_content_hash`
- `idx_semantic_embeddings_created_at`
- `idx_semantic_embeddings_session_id`
- `idx_semantic_embeddings_user_created`
- `idx_semantic_embeddings_user_id`
- `idx_semantic_embeddings_user_type`
- `idx_semantic_embeddings_vector_gin`
- `semantic_embeddings_content_hash_key`
- `semantic_embeddings_pkey`

### `emote_app.session_devices` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | NO | nextval('emote_app.session_devices_id_seq'::regclass) |
| `session_id` | uuid | YES | — |
| `device_id` | character varying | NO | — |
| `device_type` | character varying | YES | — |
| `browser` | character varying | YES | — |
| `os` | character varying | YES | — |
| `user_agent` | text | YES | — |
| `first_access` | timestamp without time zone | YES | CURRENT_TIMESTAMP |
| `last_access` | timestamp without time zone | YES | CURRENT_TIMESTAMP |
| `is_active` | boolean | YES | true |

**Indexes (3):**
- `idx_session_devices_device_id`
- `idx_session_devices_session_id`
- `session_devices_pkey`

**Foreign Keys (1):**
- `session_id` → `emote_app.conversations(session_id)` (`session_devices_session_id_fkey`)

### `emote_app.session_intelligence_snapshots` (776 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | NO | nextval('emote_app.session_intelligence_snapshots_id_seq'::regclass) |
| `session_id` | uuid | NO | — |
| `google_id` | character varying | NO | — |
| `sdf_final` | jsonb | YES | — |
| `rgi_final` | jsonb | YES | — |
| `snapshot_window` | jsonb | YES | — |
| `message_count` | integer | YES | 0 |
| `therapeutic_state` | character varying | YES | — |
| `state_confidence` | numeric | YES | — |
| `ended_reason` | character varying | YES | — |
| `created_at` | timestamp without time zone | YES | CURRENT_TIMESTAMP |

**Indexes (5):**
- `idx_session_snapshots_created_at`
- `idx_session_snapshots_google_id`
- `idx_session_snapshots_therapeutic_state`
- `session_intelligence_snapshots_pkey`
- `unique_session_snapshot`

**Foreign Keys (1):**
- `google_id` → `emote_app.users(google_id)` (`fk_google_id`)

### `emote_app.session_metrics` (10 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `session_id` | uuid | NO | — |
| `google_id` | character varying | NO | — |
| `total_turns` | integer | YES | 0 |
| `synthesis_count` | integer | YES | 0 |
| `closure_count` | integer | YES | 0 |
| `question_rate` | numeric | YES | 0.0 |
| `therapy_speak_percentage` | numeric | YES | 0.0 |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (3):**
- `idx_session_metrics_google_id`
- `idx_session_metrics_session_id`
- `session_metrics_pkey`

### `emote_app.session_scores` (516 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `session_id` | uuid | NO | — |
| `google_id` | character varying | NO | — |
| `avg_relevance` | numeric | YES | — |
| `avg_empathy` | numeric | YES | — |
| `avg_active_listening` | numeric | YES | — |
| `avg_goal_alignment` | numeric | YES | — |
| `avg_pacing` | numeric | YES | — |
| `avg_actionability` | numeric | YES | — |
| `avg_move_correctness` | numeric | YES | — |
| `overall_turn_score` | numeric | YES | — |
| `avg_ceo_alliance` | numeric | YES | — |
| `avg_ceo_goals` | numeric | YES | — |
| `avg_ceo_empathy` | numeric | YES | — |
| `avg_ceo_listening` | numeric | YES | — |
| `avg_ceo_genuineness` | numeric | YES | — |
| `avg_ceo_questions` | numeric | YES | — |
| `overall_ceo_score` | numeric | YES | — |
| `progression_score` | smallint | YES | — |
| `loop_detection_score` | smallint | YES | — |
| `resolution_score` | smallint | YES | — |
| `bridge_presence` | boolean | YES | — |
| `energy_shift` | smallint | YES | — |
| `goal_completion` | smallint | YES | — |
| `jtbd_detected` | character varying | YES | — |
| `jtbd_system` | character varying | YES | — |
| `jtbd_match` | boolean | YES | — |
| `jtbd_goal_completed` | boolean | YES | — |
| `jtbd_confidence` | numeric | YES | — |
| `did_return_next_session` | boolean | YES | — |
| `return_latency_hours` | numeric | YES | — |
| `deployment_version` | character varying | YES | — |
| `bug_flag` | boolean | YES | false |
| `bug_type` | character varying | YES | — |
| `incident_id` | character varying | YES | — |
| `evaluator_model` | character varying | YES | — |
| `evaluator_version` | character varying | YES | — |
| `turns_evaluated` | integer | YES | — |
| `total_turns` | integer | YES | — |
| `score_metadata` | jsonb | YES | — |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (3):**
- `idx_session_scores_google`
- `session_scores_pkey`
- `session_scores_session_id_key`

### `emote_app.session_store` (1 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `user_id` | text | NO | — |
| `state` | text | NO | — |
| `current_job_id` | text | YES | — |
| `onboarding_step` | integer | YES | 0 |
| `temp_profile_data` | text | YES | — |
| `updated_at` | timestamp without time zone | YES | CURRENT_TIMESTAMP |

**Indexes (1):**
- `session_store_pkey`

### `emote_app.session_summaries` (710 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `user_id` | text | NO | — |
| `session_id` | uuid | NO | — |
| `summary_text` | text | YES | — |
| `summary_data` | jsonb | YES | — |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (7):**
- `idx_session_summaries_created_at`
- `idx_session_summaries_session_id`
- `idx_session_summaries_unique_session`
- `idx_session_summaries_user_created`
- `idx_session_summaries_user_id`
- `idx_session_summaries_user_session`
- `session_summaries_pkey`

### `emote_app.sessions` (5679 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `session_id` | character varying | NO | — |
| `model_type` | character varying | NO | — |
| `created_at` | timestamp without time zone | YES | CURRENT_TIMESTAMP |
| `ended_at` | timestamp without time zone | YES | — |
| `user_agent` | text | YES | — |
| `ip_address` | character varying | YES | — |
| `is_test` | boolean | YES | false |

**Indexes (4):**
- `idx_sessions_created_at`
- `idx_sessions_ended_at`
- `idx_sessions_model_type`
- `sessions_pkey`

### `emote_app.things_to_remember` (2168 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `google_id` | character varying | YES | — |
| `content` | text | NO | — |
| `trigger_type` | character varying | YES | — |
| `trigger_date` | timestamp without time zone | YES | — |
| `delivery_window` | character varying | YES | — |
| `priority` | double precision | YES | 0.5 |
| `status` | character varying | YES | 'pending'::character varying |
| `connected_entity` | text | YES | — |
| `connected_domain` | text | YES | — |
| `source_session_id` | uuid | YES | — |
| `created_at` | timestamp without time zone | YES | now() |
| `resolved_at` | timestamp without time zone | YES | — |

**Indexes (4):**
- `idx_ttr_created_at`
- `idx_ttr_google_id_status`
- `idx_ttr_trigger_date`
- `things_to_remember_pkey`

**Foreign Keys (1):**
- `google_id` → `emote_app.users(google_id)` (`things_to_remember_google_id_fkey`)

### `emote_app.turn_scores` (4145 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `session_id` | uuid | NO | — |
| `google_id` | character varying | NO | — |
| `turn_number` | integer | NO | — |
| `log_entry_id` | uuid | YES | — |
| `relevance` | smallint | YES | — |
| `empathy` | smallint | YES | — |
| `active_listening` | smallint | YES | — |
| `goal_alignment` | smallint | YES | — |
| `pacing` | smallint | YES | — |
| `actionability` | smallint | YES | — |
| `move_correctness` | smallint | YES | — |
| `ceo_alliance` | smallint | YES | — |
| `ceo_goals` | smallint | YES | — |
| `ceo_empathy` | smallint | YES | — |
| `ceo_listening` | smallint | YES | — |
| `ceo_genuineness` | smallint | YES | — |
| `ceo_questions` | smallint | YES | — |
| `detected_mode` | character varying | YES | — |
| `detected_jtbd` | character varying | YES | — |
| `evaluator_model` | character varying | YES | — |
| `evaluator_version` | character varying | YES | — |
| `score_metadata` | jsonb | YES | — |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (3):**
- `idx_turn_scores_session`
- `turn_scores_pkey`
- `turn_scores_session_id_turn_number_key`

### `emote_app.user_behavior_summary` (514 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `google_id` | character varying | YES | — |
| `user_created_at` | timestamp without time zone | YES | — |
| `last_login` | timestamp without time zone | YES | — |
| `conversations` | bigint | YES | — |
| `user_turns` | bigint | YES | — |
| `avg_turns_per_conversation` | numeric | YES | — |
| `total_feedbacks` | bigint | YES | — |
| `feedback_rate_percent` | numeric | YES | — |

### `emote_app.user_context_submissions` (129 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `google_id` | character varying | NO | — |
| `session_id` | uuid | YES | — |
| `context_type` | character varying | NO | 'general'::character varying |
| `raw_length` | integer | YES | — |
| `extraction` | jsonb | NO | — |
| `prompt_section` | text | YES | — |
| `processing_time_ms` | double precision | YES | — |
| `kg_processed` | boolean | YES | false |
| `created_at` | timestamp with time zone | YES | now() |
| `processing_status` | character varying | NO | 'ready'::character varying |
| `processing_error` | text | YES | — |
| `source_surface` | character varying | NO | 'inline_paste'::character varying |
| `scope` | character varying | NO | 'session'::character varying |
| `request_id` | character varying | YES | — |
| `raw_text` | text | YES | — |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (6):**
- `idx_user_context_google_id`
- `idx_user_context_kg_unprocessed`
- `idx_user_context_processing_queue`
- `idx_user_context_ready_lookup`
- `idx_user_context_request_id`
- `user_context_submissions_pkey`

### `emote_app.user_embedding_stats` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `user_id` | character varying | YES | — |
| `total_embeddings` | bigint | YES | — |
| `unique_sessions` | bigint | YES | — |
| `embedding_types` | bigint | YES | — |
| `first_embedding` | timestamp without time zone | YES | — |
| `last_embedding` | timestamp without time zone | YES | — |
| `embedding_timespan` | interval | YES | — |

### `emote_app.user_emotional_profiles` (115 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `google_id` | text | NO | — |
| `profile_data` | jsonb | NO | '{}'::jsonb |
| `last_updated` | timestamp with time zone | YES | now() |
| `last_session_id` | uuid | YES | — |
| `version` | integer | YES | 1 |
| `created_at` | timestamp with time zone | YES | now() |
| `topic_registry` | jsonb | YES | '{}'::jsonb |
| `pre_generated_starters` | jsonb | YES | '[]'::jsonb |
| `pattern_profiles` | jsonb | YES | '{}'::jsonb |

**Indexes (3):**
- `idx_user_emotional_profiles_last_updated`
- `idx_user_profiles_registry_version`
- `user_emotional_profiles_pkey`

**Foreign Keys (1):**
- `google_id` → `emote_app.users(google_id)` (`user_emotional_profiles_google_id_fkey`)

### `emote_app.user_journey_view` (498 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `google_id` | character varying | YES | — |
| `email` | character varying | YES | — |
| `name` | character varying | YES | — |
| `signup_date` | timestamp without time zone | YES | — |
| `user_role` | character varying | YES | — |
| `total_sessions` | bigint | YES | — |
| `last_session_date` | timestamp without time zone | YES | — |
| `days_since_last_session` | numeric | YES | — |

### `emote_app.user_kg_turns` (633 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `google_id` | character varying | NO | — |
| `session_id` | uuid | NO | — |
| `turn_number` | integer | NO | — |
| `turn_data` | jsonb | NO | — |
| `created_at` | timestamp with time zone | YES | now() |

**Indexes (3):**
- `idx_user_kg_turns_google_id`
- `idx_user_kg_turns_google_session`
- `user_kg_turns_pkey`

### `emote_app.user_knowledge_graph` (72 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | gen_random_uuid() |
| `google_id` | character varying | NO | — |
| `kg_data` | jsonb | NO | '{}'::jsonb |
| `version` | integer | NO | 1 |
| `last_session_id` | uuid | YES | — |
| `sessions_processed` | ARRAY | YES | '{}'::text[] |
| `created_at` | timestamp without time zone | YES | now() |
| `updated_at` | timestamp without time zone | YES | now() |

**Indexes (3):**
- `idx_ukg_google_id`
- `uq_user_knowledge_graph_google_id`
- `user_knowledge_graph_pkey`

### `emote_app.user_summary_stats` (209 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `user_id` | text | YES | — |
| `total_summaries` | bigint | YES | — |
| `unique_sessions` | bigint | YES | — |
| `first_summary` | timestamp with time zone | YES | — |
| `last_summary` | timestamp with time zone | YES | — |
| `summary_timespan` | interval | YES | — |
| `avg_summary_length` | numeric | YES | — |

### `emote_app.users` (514 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `google_id` | character varying | NO | — |
| `email` | character varying | NO | — |
| `name` | character varying | YES | — |
| `picture_url` | text | YES | — |
| `created_at` | timestamp without time zone | YES | CURRENT_TIMESTAMP |
| `last_login` | timestamp without time zone | YES | CURRENT_TIMESTAMP |
| `total_conversations` | integer | YES | 0 |
| `is_active` | boolean | YES | true |
| `user_role` | character varying | NO | 'user'::character varying |
| `email_unsubscribed` | boolean | YES | false |
| `password_hash` | text | YES | — |
| `auth_provider` | character varying | YES | 'google'::character varying |

**Indexes (7):**
- `idx_users_auth_provider`
- `idx_users_email`
- `idx_users_email_lower`
- `idx_users_last_login`
- `idx_users_user_role`
- `users_email_key`
- `users_pkey`

## Schema: `graphql_public`


## Schema: `net`


### `net._http_response` (1 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | bigint | YES | — |
| `status_code` | integer | YES | — |
| `content_type` | text | YES | — |
| `headers` | jsonb | YES | — |
| `content` | text | YES | — |
| `timed_out` | boolean | YES | — |
| `error_msg` | text | YES | — |
| `created` | timestamp with time zone | NO | now() |

**Indexes (1):**
- `_http_response_created_idx`

### `net.http_request_queue` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | bigint | NO | nextval('net.http_request_queue_id_seq'::regclass) |
| `method` | text | NO | — |
| `url` | text | NO | — |
| `headers` | jsonb | YES | — |
| `body` | bytea | YES | — |
| `timeout_milliseconds` | integer | NO | — |

## Schema: `pg_temp_0`


## Schema: `pg_temp_1`


## Schema: `pg_temp_10`


## Schema: `pg_temp_11`


## Schema: `pg_temp_12`


## Schema: `pg_temp_13`


## Schema: `pg_temp_14`


## Schema: `pg_temp_15`


## Schema: `pg_temp_16`


## Schema: `pg_temp_17`


## Schema: `pg_temp_18`


## Schema: `pg_temp_19`


## Schema: `pg_temp_2`


## Schema: `pg_temp_20`


## Schema: `pg_temp_21`


## Schema: `pg_temp_22`


## Schema: `pg_temp_23`


## Schema: `pg_temp_24`


## Schema: `pg_temp_25`


## Schema: `pg_temp_26`


## Schema: `pg_temp_27`


## Schema: `pg_temp_28`


## Schema: `pg_temp_29`


## Schema: `pg_temp_3`


## Schema: `pg_temp_30`


## Schema: `pg_temp_31`


## Schema: `pg_temp_32`


## Schema: `pg_temp_33`


## Schema: `pg_temp_34`


## Schema: `pg_temp_35`


## Schema: `pg_temp_36`


## Schema: `pg_temp_37`


## Schema: `pg_temp_38`


## Schema: `pg_temp_39`


## Schema: `pg_temp_4`


## Schema: `pg_temp_40`


## Schema: `pg_temp_41`


## Schema: `pg_temp_42`


## Schema: `pg_temp_43`


## Schema: `pg_temp_44`


## Schema: `pg_temp_45`


## Schema: `pg_temp_46`


## Schema: `pg_temp_47`


## Schema: `pg_temp_48`


## Schema: `pg_temp_49`


## Schema: `pg_temp_5`


## Schema: `pg_temp_50`


## Schema: `pg_temp_51`


## Schema: `pg_temp_52`


## Schema: `pg_temp_53`


## Schema: `pg_temp_54`


## Schema: `pg_temp_55`


## Schema: `pg_temp_56`


## Schema: `pg_temp_57`


## Schema: `pg_temp_58`


## Schema: `pg_temp_59`


## Schema: `pg_temp_6`


## Schema: `pg_temp_7`


## Schema: `pg_temp_8`


## Schema: `pg_temp_9`


## Schema: `pg_toast_temp_0`


## Schema: `pg_toast_temp_1`


## Schema: `pg_toast_temp_10`


## Schema: `pg_toast_temp_11`


## Schema: `pg_toast_temp_12`


## Schema: `pg_toast_temp_13`


## Schema: `pg_toast_temp_14`


## Schema: `pg_toast_temp_15`


## Schema: `pg_toast_temp_16`


## Schema: `pg_toast_temp_17`


## Schema: `pg_toast_temp_18`


## Schema: `pg_toast_temp_19`


## Schema: `pg_toast_temp_2`


## Schema: `pg_toast_temp_20`


## Schema: `pg_toast_temp_21`


## Schema: `pg_toast_temp_22`


## Schema: `pg_toast_temp_23`


## Schema: `pg_toast_temp_24`


## Schema: `pg_toast_temp_25`


## Schema: `pg_toast_temp_26`


## Schema: `pg_toast_temp_27`


## Schema: `pg_toast_temp_28`


## Schema: `pg_toast_temp_29`


## Schema: `pg_toast_temp_3`


## Schema: `pg_toast_temp_30`


## Schema: `pg_toast_temp_31`


## Schema: `pg_toast_temp_32`


## Schema: `pg_toast_temp_33`


## Schema: `pg_toast_temp_34`


## Schema: `pg_toast_temp_35`


## Schema: `pg_toast_temp_36`


## Schema: `pg_toast_temp_37`


## Schema: `pg_toast_temp_38`


## Schema: `pg_toast_temp_39`


## Schema: `pg_toast_temp_4`


## Schema: `pg_toast_temp_40`


## Schema: `pg_toast_temp_41`


## Schema: `pg_toast_temp_42`


## Schema: `pg_toast_temp_43`


## Schema: `pg_toast_temp_44`


## Schema: `pg_toast_temp_45`


## Schema: `pg_toast_temp_46`


## Schema: `pg_toast_temp_47`


## Schema: `pg_toast_temp_48`


## Schema: `pg_toast_temp_49`


## Schema: `pg_toast_temp_5`


## Schema: `pg_toast_temp_50`


## Schema: `pg_toast_temp_51`


## Schema: `pg_toast_temp_52`


## Schema: `pg_toast_temp_53`


## Schema: `pg_toast_temp_54`


## Schema: `pg_toast_temp_55`


## Schema: `pg_toast_temp_56`


## Schema: `pg_toast_temp_57`


## Schema: `pg_toast_temp_58`


## Schema: `pg_toast_temp_59`


## Schema: `pg_toast_temp_6`


## Schema: `pg_toast_temp_7`


## Schema: `pg_toast_temp_8`


## Schema: `pg_toast_temp_9`


## Schema: `public`


### `public.checkpoint_blobs` (117 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `thread_id` | text | NO | — |
| `checkpoint_ns` | text | NO | ''::text |
| `channel` | text | NO | — |
| `version` | text | NO | — |
| `type` | text | NO | — |
| `blob` | bytea | YES | — |

**Indexes (2):**
- `checkpoint_blobs_pkey`
- `checkpoint_blobs_thread_id_idx`

### `public.checkpoint_migrations` (10 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `v` | integer | NO | — |

**Indexes (1):**
- `checkpoint_migrations_pkey`

### `public.checkpoint_writes` (229 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `thread_id` | text | NO | — |
| `checkpoint_ns` | text | NO | ''::text |
| `checkpoint_id` | text | NO | — |
| `task_id` | text | NO | — |
| `idx` | integer | NO | — |
| `channel` | text | NO | — |
| `type` | text | YES | — |
| `blob` | bytea | NO | — |
| `task_path` | text | NO | ''::text |

**Indexes (2):**
- `checkpoint_writes_pkey`
- `checkpoint_writes_thread_id_idx`

### `public.checkpoints` (73 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `thread_id` | text | NO | — |
| `checkpoint_ns` | text | NO | ''::text |
| `checkpoint_id` | text | NO | — |
| `parent_checkpoint_id` | text | YES | — |
| `type` | text | YES | — |
| `checkpoint` | jsonb | NO | — |
| `metadata` | jsonb | NO | '{}'::jsonb |

**Indexes (2):**
- `checkpoints_pkey`
- `checkpoints_thread_id_idx`

### `public.conversation_logs_json` (0 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `session_id` | uuid | NO | — |
| `google_id` | character varying | NO | — |
| `log_data` | jsonb | NO | — |
| `created_at` | timestamp without time zone | YES | CURRENT_TIMESTAMP |

**Indexes (1):**
- `conversation_logs_json_pkey`

### `public.emote_conversations` (10289 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | YES | — |
| `session_id` | uuid | YES | — |
| `google_id` | character varying | YES | — |
| `log_data` | jsonb | YES | — |
| `created_at` | timestamp without time zone | YES | — |

### `public.emote_starters` (346 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | integer | YES | — |
| `user_id` | text | YES | — |
| `session_id` | text | YES | — |
| `starters` | jsonb | YES | — |
| `created_at` | timestamp with time zone | YES | — |
| `updated_at` | timestamp with time zone | YES | — |

### `public.emote_users` (514 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `google_id` | character varying | YES | — |
| `email` | character varying | YES | — |
| `name` | character varying | YES | — |
| `picture_url` | text | YES | — |
| `created_at` | timestamp without time zone | YES | — |
| `last_login` | timestamp without time zone | YES | — |
| `total_conversations` | integer | YES | — |
| `is_active` | boolean | YES | — |

### `public.semantic_embeddings` (2 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | uuid_generate_v4() |
| `user_id` | character varying | NO | — |
| `session_id` | uuid | NO | — |
| `content_hash` | character varying | NO | — |
| `content_text` | text | NO | — |
| `embedding_vector` | jsonb | NO | — |
| `embedding_type` | character varying | YES | 'general'::character varying |
| `created_at` | timestamp without time zone | YES | CURRENT_TIMESTAMP |
| `updated_at` | timestamp without time zone | YES | CURRENT_TIMESTAMP |

**Indexes (9):**
- `idx_semantic_embeddings_content_hash`
- `idx_semantic_embeddings_created_at`
- `idx_semantic_embeddings_session_id`
- `idx_semantic_embeddings_user_created`
- `idx_semantic_embeddings_user_id`
- `idx_semantic_embeddings_user_type`
- `idx_semantic_embeddings_vector_gin`
- `semantic_embeddings_content_hash_key`
- `semantic_embeddings_pkey`

### `public.user_embedding_stats` (1 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `user_id` | character varying | YES | — |
| `total_embeddings` | bigint | YES | — |
| `unique_sessions` | bigint | YES | — |
| `embedding_types` | bigint | YES | — |
| `first_embedding` | timestamp without time zone | YES | — |
| `last_embedding` | timestamp without time zone | YES | — |
| `embedding_timespan` | interval | YES | — |

### `public.users` (14 rows)

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | uuid | NO | — |
| `email` | text | NO | — |
| `full_name` | text | YES | — |
| `master_cv_markdown` | text | YES | — |
| `parsed_cv_data` | jsonb | YES | — |
| `employment_state` | text | YES | 'employed_passive'::text |
| `urgency` | integer | YES | 5 |
| `burnout_level` | integer | YES | 5 |
| `preferred_environments` | jsonb | YES | '[]'::jsonb |
| `startup_tolerance` | integer | YES | 5 |
| `compensation_floor_lakhs` | real | YES | 0.0 |
| `compensation_target_lakhs` | real | YES | 0.0 |
| `work_style_prefs` | jsonb | YES | '{}'::jsonb |
| `emotional_constraints` | jsonb | YES | '{}'::jsonb |
| `interview_tolerance` | text | YES | 'standard'::text |
| `remote_pref` | text | YES | 'hybrid'::text |
| `search_posture` | text | YES | 'EXPLORE'::text |
| `created_at` | timestamp with time zone | YES | now() |
| `updated_at` | timestamp with time zone | YES | now() |

**Indexes (2):**
- `users_email_key`
- `users_pkey`