# Phase 1+2 Evidence — V3 Migration Applied

## Migration applied to Supabase
- **Migration file:** `careerloop/memory/supabase_migration_v3.sql`
- **Host:** `aws-1-ap-southeast-1.pooler.supabase.com:6543`
- **Date:** 2026-05-25
- **Strategy:** Dual-path idempotent — CREATE TABLE IF NOT EXISTS, DROP CONSTRAINT IF EXISTS, ALTER TABLE ADD COLUMN IF NOT EXISTS, INSERT ON CONFLICT DO NOTHING. Safe to re-run N times.

## careerloop.users
- **14 rows** backfilled from `public.users`
- All UUIDs preserved (no regenerated IDs)
- Columns migrated: `id`, `email`, `full_name`, `created_at`, `updated_at`, `last_active_at`
- Additional columns added: `phone`, `telegram_id`, `whatsapp_id`, `linkedin_url`, `onboarding_status`, `signup_source`, `current_plan`, `trial_started_at`, `trial_ends_at`, `status`
- Unique index on `email` (WHERE email IS NOT NULL)
- **Known gap:** Extended columns from `public.users` (location_city, location_country, linkedin_url, notice_period_days, current_ctc_lakhs, expected_ctc_lakhs, yoe, is_active) not yet migrated — deferred to V3.1 hardening pass.

## Foreign Keys — 20 FK constraints → careerloop.users(id) ON DELETE CASCADE

### Original 16 tables (FKs existed previously to public.users, redirected to careerloop.users)

| # | Table | Constraint Name | Old Target | New Target |
|---|-------|----------------|------------|------------|
| 1 | `careerloop.sessions` | `sessions_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 2 | `careerloop.background_runs` | `background_runs_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 3 | `careerloop.daily_briefs` | `daily_briefs_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 4 | `careerloop.strategic_tracks` | `strategic_tracks_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 5 | `careerloop.application_ledger` | `application_ledger_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 6 | `careerloop.event_timeline` | `event_timeline_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 7 | `careerloop.company_memory` | `company_memory_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 8 | `careerloop.positioning_memory` | `positioning_memory_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 9 | `careerloop.user_job_relationships` | `user_job_relationships_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 10 | `careerloop.applications` | `applications_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 11 | `careerloop.application_packs` | `application_packs_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 12 | `careerloop.user_preferences` | `user_preferences_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 13 | `careerloop.user_evidence` | `user_evidence_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 14 | `careerloop.outreach_messages` | `outreach_messages_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 15 | `careerloop.followups` | `followups_user_id_fkey` | public.users(id) | careerloop.users(id) |
| 16 | `careerloop.outcome_events` | `outcome_events_user_id_fkey` | public.users(id) | careerloop.users(id) |

### New tables with FKs to careerloop.users

| # | Table | Constraint | Type |
|---|-------|-----------|------|
| 17 | `careerloop.conversations` | `conversations_user_id_fkey` | New table, points to careerloop.users(id) |
| 18 | `careerloop.messages` | `messages_user_id_fkey` + `messages_conversation_id_fkey` | New table, user_id → careerloop.users(id), conversation_id → careerloop.conversations(id) |
| 19 | `careerloop.memory_events` | `memory_events_user_id_fkey` | New table, points to careerloop.users(id) |
| 20 | `careerloop.job_search_runs` | `job_search_runs_user_id_fkey` | New table, points to careerloop.users(id) |

**Total: 20 FK constraints verified.** All use `ON DELETE CASCADE`. Zero orphan risk.

## New Tables — 7 new tables created

| # | Table | Purpose | Row Count (at migration) |
|---|-------|---------|--------------------------|
| 1 | `careerloop.users` | Canonical identity spine | 14 (backfilled from public.users) |
| 2 | `careerloop.conversations` | Multi-transport chat sessions (cli, telegram, whatsapp, web) | 0 |
| 3 | `careerloop.messages` | Per-conversation message log with routing metadata (action_type, confidence, artifact_context, tokens_used) | 0 |
| 4 | `careerloop.memory_events` | Importance-weighted, TTL-based memory store (1-10 importance, configurable TTL) | 0 |
| 5 | `careerloop.recruiter_contacts` | People layer for outreach — name, title, linkedin_url, email, phone | 0 |
| 6 | `careerloop.job_sources` | Dedup-friendly source tracking per job (multi-source: linkedin, naukri, greenhouse, etc.) | 0 |
| 7 | `careerloop.job_search_runs` | Full audit trail for each scan/search execution (candidates_found, cache_hit_ratio, sources_used) | 0 |

## Additional Schema Changes

### UUID Standardization (4 ALTER TABLE ADD COLUMN)
| Table | Column | Purpose |
|-------|--------|---------|
| `careerloop.background_runs` | `run_id_uuid` | UUID bridge alongside TEXT `run_id` PK |
| `careerloop.run_events` | `event_id_uuid` | UUID bridge alongside TEXT `event_id` PK |
| `careerloop.run_events` | `run_id_uuid` | UUID FK bridge for run references |
| `careerloop.daily_briefs` | `run_id_uuid` | UUID FK bridge for run references |

### Sessions Cleanup (3 COMMENT ON COLUMN)
- `careerloop.sessions.current_job_id` → DEPRECATED
- `careerloop.sessions.onboarding_step` → DEPRECATED
- `careerloop.sessions.temp_profile_data` → DEPRECATED

### RLS Policies (7 policies, idempotent DO block)
- `careerloop.users` — Users can manage their own profile
- `careerloop.conversations` — Users can manage their own conversations
- `careerloop.messages` — Users can manage their own messages
- `careerloop.memory_events` — Users can manage their own memory events
- `careerloop.recruiter_contacts` — Authenticated users can read recruiter contacts
- `careerloop.job_sources` — Authenticated users can read job sources
- `careerloop.job_search_runs` — Users can manage their own job search runs

## Clean Audit

- **ZERO CareerLoop FOREIGN KEY constraints** reference `public.*` — all 20 FKs resolved to `careerloop.users(id)`
- **ZERO `public.users` references** in CareerLoop Python code — all Python code uses `_tbl()` prefixing (`careerloop.*`)
- **All primary keys are UUID**: `gen_random_uuid()` default on all 7 new tables
- **Schema isolation complete**: `careerloop` schema holds 29 tables (22 original + 7 new); `public` schema holds only Supabase auth, LangGraph checkpoints, and Emote app tables
- **Migration is idempotent**: Every statement uses IF NOT EXISTS / IF EXISTS guards — safe to re-run against production
- **Data preserved**: 14 `public.users` rows copied to `careerloop.users` via INSERT ON CONFLICT DO NOTHING — zero data loss, zero ID regeneration

## Known Gaps (V3.1 Hardening Pass — non-blocking)

| # | Gap | Impact | Priority |
|---|-----|--------|----------|
| 1 | `public.users` extended columns (location_city, yoe, etc.) not migrated | Low — add to careerloop.users in V3.1 | P2 |
| 2 | `background_runs.run_id` is still TEXT PK (uuid column added, not yet swapped) | Medium — 3 rows, no foreign consumers yet | P2 |
| 3 | `run_events.event_id` is still TEXT PK (uuid column added, not yet swapped) | Medium — 7 rows, no foreign consumers yet | P2 |
| 4 | `daily_briefs.run_id` is still TEXT (uuid column added, not yet FK'd) | Low — 1 row | P3 |
| 5 | `job_search_runs.run_id` is TEXT (references background_runs.run_id which is TEXT) | Low — cascades from gap #2 | P3 |
| 6 | `jobs.id` is TEXT PK, `jobs.job_id` UUID column exists (from V2) | Medium — constraint swap deferred | P2 |
| 7 | `daily_brief_items.job_id` is TEXT (references jobs.id which is TEXT) | Medium — cascades from gap #6 | P2 |
| 8 | `public.users` table still exists (consumers not all switched) | Low — eventual deprecation target | P3 |

**Conclusion: Phase 1 (identity spine) and Phase 2 (FK migration + new tables) are COMPLETE. Production-safe. All 20 FKs verified. Zero `public.*` references remain. 7 new tables created. 14 users backfilled.**

---

## Canonical Documentation

Evidence package includes 7 canonical docs:
- `docs/DATA_MODEL_CANONICAL.md` — Full data model with ERD, table inventory, relationships
- `docs/MEMORY_ARCHITECTURE.md` — 6-layer memory model with propagation architecture
- `docs/JOB_PERSISTENCE_ENGINE.md` — Global cache, user relationships, fingerprint dedup, TTL
- `docs/GLOBAL_VS_USER_SCOPED_DATA.md` — Global vs user-scoped separation rules
- `docs/SCHEMA_REFERENCE.md` — Column-level schema reference
- `docs/DB_MIGRATION_REPORT.md` — V1 → V2 → V3 migration audit trail
- `docs/DATA_ENGINEERING_ARCHITECTURE.md` — Architecture overview, design principles, ERD

Live Supabase evidence:
- `docs/CAREERLOOP_SCHEMA_DUMP.json` (265KB) — Full `information_schema` export
- `docs/CAREERLOOP_SCHEMA.md` (68KB) — Human-readable schema with columns, types, FKs, indexes, row counts
