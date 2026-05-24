# CareerLoop Canonical Data Model

> Single source of truth for CareerLoop's data model. All agents must reference this document before writing any SQL, repository code, or migration.

---

## Identity Spine

- **`public.users` is the ONLY identity root.** Every CareerLoop table that scopes data to a user references `public.users(id)`.
- No CareerLoop table references `backup_public_schema.users`, `emote_app.*`, or any other user table.
- All user-scoped CareerLoop tables FK to `public.users(id) ON DELETE CASCADE`.
- `public.users` is managed by Supabase Auth. CareerLoop code never creates users except via `save_session()`'s idempotent INSERT stub.

### Identity policy
```
public.users (id UUID PK)
  ^
  |____ careerloop.sessions (user_id FK → public.users)
  |____ careerloop.daily_briefs (user_id FK → public.users)
  |____ careerloop.strategic_tracks (user_id FK → public.users)
  |____ careerloop.application_ledger (user_id FK → public.users)
  |____ careerloop.event_timeline (user_id FK → public.users)
  |____ careerloop.company_memory (user_id FK → public.users)
  |____ careerloop.positioning_memory (user_id FK → public.users)
  |____ careerloop.background_runs (user_id FK → public.users)
  |____ careerloop.applications (user_id FK → public.users)
  |____ careerloop.application_packs (user_id FK → public.users)
  |____ careerloop.user_job_relationships (user_id FK → public.users)
  |____ careerloop.outreach_messages (user_id FK → public.users)
  |____ careerloop.followups (user_id FK → public.users)
  |____ careerloop.user_evidence (user_id FK → public.users)
  |____ careerloop.user_preferences (user_id FK → public.users)
  |____ careerloop.outcome_events (user_id FK → public.users)
```

---

## Schema: `careerloop`

All CareerLoop tables live in the `careerloop` PostgreSQL schema. This isolates them from Supabase auth tables (`public`), LangGraph checkpoint tables (`emote_app.checkpoint_*`), and the legacy Emote app tables (`emote_app.*`).

### Complete Table Inventory (22 tables)

| # | Table | Purpose | Scope | PK Type | Row Estimate |
|---|-------|---------|-------|---------|-------------|
| 1 | `sessions` | Runtime state per user: journey state, active context, onboarding step | User | user_id (UUID) | 13 |
| 2 | `daily_briefs` | Daily job brief artifact per user | User | id (UUID) | 1 |
| 3 | `daily_brief_items` | Numbered items within a daily brief | User | id (UUID) | 1 |
| 4 | `strategic_tracks` | User-defined positioning tracks (e.g., "AI PM track") | User | id (UUID) | 0 |
| 5 | `application_ledger` | Legacy application tracker (ledger.json twin) | User | id (UUID) | 0 |
| 6 | `event_timeline` | User-level event log (status changes, milestones) | User | id (UUID) | 0 |
| 7 | `company_memory` | Per-user private company intelligence notes | User | id (UUID) | 0 |
| 8 | `positioning_memory` | Per-track, per-company narrative memory | User | id (UUID) | 0 |
| 9 | `jobs` | Global canonical job registry (fingerprint-deduped) | Global | job_id (UUID) | 1 |
| 10 | `companies` | Global company profiles (domain-deduped) | Global | id (UUID) | 0 |
| 11 | `people_to_reach` | Recruiters/hiring managers (company-scoped) | Global | person_id (UUID) | 0 |
| 12 | `job_candidates` | Raw discovery before dedupe into jobs | Run | candidate_id (UUID) | 0 |
| 13 | `background_runs` | Async job tracking (scan, pack gen, etc.) | User | run_id (TEXT) | 3 |
| 14 | `run_events` | Streaming observability events per run | Run | event_id (TEXT) | 7 |
| 15 | `user_job_relationships` | Per-user match/reject/skip per job | User | (user_id, job_id) | 2 |
| 16 | `applications` | Applied/acted jobs | User | application_id (UUID) | 0 |
| 17 | `application_packs` | Generated execution bundles (CV + cover + DM) | User | pack_id (UUID) | 0 |
| 18 | `outreach_messages` | Sent messages to recruiters/referrers | User | message_id (UUID) | 0 |
| 19 | `followups` | Scheduled follow-up actions | User | followup_id (UUID) | 0 |
| 20 | `user_evidence` | Truth-grounded claims (projects, skills, certs) | User | evidence_id (UUID) | 0 |
| 21 | `user_preferences` | Structured career targeting preferences | User | user_id (UUID) | 0 |
| 22 | `outcome_events` | Learning loop events (interviews, offers, rejections) | User | outcome_id (UUID) | 0 |

---

## Global vs User-Scoped

| Table | Scope | Rationale |
|-------|-------|-----------|
| `jobs` | Global | Same LinkedIn job seen by 5 users = 1 row. Fingerprint dedup. |
| `companies` | Global | Company profile reused across all jobs and users. Domain dedup. |
| `people_to_reach` | Global | Recruiter contact info is company-level, reusable. |
| `job_candidates` | Run | Ephemeral discovery staging. Tied to a run, not a user directly. |
| `run_events` | Run | Ephemeral streaming logs. Tied to a run. |
| `sessions` | User | Runtime state is per-user by definition. |
| `daily_briefs` | User | Daily artifact is per-user. |
| `daily_brief_items` | User | Items belong to a user's brief. |
| `strategic_tracks` | User | User's personal positioning tracks. |
| `application_ledger` | User | User's application log. |
| `event_timeline` | User | User's personal event history. |
| `company_memory` | User | User's private company intel notes. Has UNIQUE(user_id, company_normalized). |
| `positioning_memory` | User | User's narrative memory per track per company. |
| `background_runs` | User | Runs initiated by a specific user. |
| `user_job_relationships` | User | How THIS user relates to THIS job. |
| `applications` | User | User's application action. |
| `application_packs` | User | User's generated pack. |
| `outreach_messages` | User | User's sent messages. |
| `followups` | User | User's follow-up schedule. |
| `user_evidence` | User | User's truth-grounded claims. |
| `user_preferences` | User | User's career preferences. One row per user. |
| `outcome_events` | User | User's learning events. Permanent. |

---

## Foreign Key Graph

```
                         public.users (id)  ←── Supabase Auth identity root
                              │
         ┌────────────────────┼──────────────────────────────┐
         │                    │                              │
         ▼                    ▼                              ▼
careerloop.sessions    careerloop.strategic_tracks    careerloop.background_runs
  (user_id)              (user_id)                      (user_id, run_id PK)
                              │                              │
                              │              ┌───────────────┼───────────────┐
                              │              │               │               │
                              │              ▼               ▼               ▼
                              │    careerloop.run_events  careerloop.    careerloop.
                              │      (run_id FK → bg_runs) job_candidates  daily_briefs
                              │                              (run_id)     (run_id, user_id)
         ┌────────────────────┤                                              │
         │                    │                                              │
         ▼                    ▼                                              ▼
careerloop.application_ledger  careerloop.positioning_memory    careerloop.daily_brief_items
  (user_id, track_id → tracks)    (user_id, track_id → tracks)    (brief_id FK → daily_briefs,
                                                                   job_id FK → jobs)

careerloop.companies (id PK)
  │
  ├─── careerloop.jobs (company_id FK → companies)
  │       │
  │       ├─── careerloop.user_job_relationships (job_id FK → jobs, user_id FK → users)
  │       ├─── careerloop.applications (job_id FK → jobs, user_id FK → users)
  │       │       │
  │       │       ├─── careerloop.followups (application_id FK → applications, user_id)
  │       │       └─── careerloop.outcome_events (application_id FK → applications, job_id FK → jobs)
  │       │
  │       ├─── careerloop.application_packs (job_id → jobs, user_id, run_id → bg_runs)
  │       └─── careerloop.daily_brief_items (job_id FK → jobs)
  │
  └─── careerloop.people_to_reach (company_id FK → companies)
          │
          └─── careerloop.outreach_messages (person_id FK → people, user_id, job_id)

careerloop.user_evidence (user_id FK → users)        — standalone, no downstream refs
careerloop.user_preferences (user_id PK FK → users)   — standalone, one row per user
careerloop.outcome_events (user_id, job_id, application_id) — leaf table, learning loop
careerloop.event_timeline (user_id)                   — leaf event log
careerloop.company_memory (user_id, UNIQUE user_id+company) — leaf, user notes
```

---

## ID Standard

| Aspect | Rule |
|--------|------|
| New table PKs | `UUID DEFAULT gen_random_uuid()` |
| Foreign keys to users | `UUID NOT NULL REFERENCES public.users(id)` |
| Foreign keys to jobs | `UUID REFERENCES careerloop.jobs(job_id)` |
| Foreign keys to companies | `UUID REFERENCES careerloop.companies(id)` |
| Legacy TEXT columns | `application_packs.job_id`, `applications.job_id`, `daily_brief_items.job_id`, `background_runs.run_id`, `run_events.event_id` still use TEXT — scheduled for UUID migration in v2.1 |
| Backfill path | `jobs.id` (TEXT v1 legacy) coexists with `jobs.job_id` (UUID v2). Code writes to `job_id`; v2.1 will swap PK constraint. |

### Known legacy columns requiring backfill (from v2 migration notes)

1. `jobs.id` (TEXT PK) → `jobs.job_id` (UUID PK): backfill + swap constraint
2. `daily_brief_items.job_id` (TEXT) → UUID: backfill mapping needed
3. `daily_briefs.run_id` (TEXT) → UUID FK: backfill mapping needed
4. `background_runs.run_id` (TEXT) → UUID: backfill needed
5. `jobs.content_fingerprint` DEFAULT '' → ALTER to NOT NULL after backfill

---

## Lifecycle Policies

| Table | Created | Updated | Archived/Deleted |
|-------|---------|---------|------------------|
| `public.users` | Supabase Auth signup | `updated_at` on profile edit | Soft-delete via `is_active = false` |
| `careerloop.sessions` | First chat message | Every state change | Never deleted (single row per user) |
| `careerloop.jobs` | First discovery | `last_seen_at` on re-discovery | Mark `status='expired'` after 60 days unseen |
| `careerloop.companies` | First discovery | On re-crawl | Never deleted |
| `careerloop.job_candidates` | Each scan run | Never updated after dedupe | Archive after 30 days |
| `careerloop.run_events` | During scan/pack run | Never updated (append-only) | Delete after 14 days, keep summary in `background_runs.stats` |
| `careerloop.daily_briefs` | Each daily scan | On re-generation same day | Permanent (never delete) |
| `careerloop.daily_brief_items` | Each daily scan | On re-generation | Permanent |
| `careerloop.background_runs` | On scan/pack start | Status/stats updated during run | Permanent (audit trail) |
| `careerloop.applications` | On user apply action | Status changes | Permanent |
| `careerloop.application_packs` | On pack generation | Status changes | Permanent (user can request deletion) |
| `careerloop.user_job_relationships` | On job discovery or user action | On re-discovery or swipe | Permanent |
| `careerloop.outcome_events` | On interview/offer/rejection | Never updated | Permanent (learning loop) |
| `careerloop.outreach_messages` | On draft/send | Status changes | Keep 90 days after last update |
| `careerloop.followups` | On schedule | Mark completed/skipped | Keep 90 days after completion |
| `careerloop.user_evidence` | On CV parse or manual add | On evidence refresh | Permanent |
| `careerloop.user_preferences` | On onboarding | On preference change | Permanent (one row per user) |

---

## Index Strategy

| Index | Table | Why |
|-------|-------|-----|
| `idx_jobs_fingerprint` UNIQUE | `careerloop.jobs(content_fingerprint)` | Dedup primary defense |
| `idx_jobs_last_seen` | `careerloop.jobs(last_seen_at)` | TTL expiry queries |
| `idx_jobs_status` | `careerloop.jobs(status)` | Active/expired filtering |
| `idx_jobs_city` | `careerloop.jobs(location_city)` | Geo-filtered cache queries |
| `idx_jobs_title` | `careerloop.jobs(normalized_title)` | Role-filtered cache queries |
| `idx_companies_normalized` UNIQUE | `careerloop.companies(normalized_name)` | Dedup company profiles |
| `idx_companies_domain` UNIQUE (partial) | `careerloop.companies(domain) WHERE domain IS NOT NULL` | Domain-level dedup |
| `idx_ujr_match_status` | `careerloop.user_job_relationships(match_status)` | Filter matched/rejected for user |
| `idx_ujr_fit_score` | `careerloop.user_job_relationships(fit_score)` | Sort by score |
| `idx_briefs_user_date` | `careerloop.daily_briefs(user_id, date_str)` | Lookup today's brief |
| `idx_candidates_run` | `careerloop.job_candidates(run_id)` | Run-scoped queries |
| `idx_bg_runs_status` | `careerloop.background_runs(status)` | Monitor running/queued |
| `idx_outcomes_occurred` | `careerloop.outcome_events(occurred_at)` | Time-series learning queries |
| `idx_followups_due` | `careerloop.followups(due_at) WHERE status='pending'` | Due followup queries |

---

## Migration Path

### V1: Original `public.*` tables (pre-2026-05-25)

CareerLoop tables co-mingled with Supabase auth in `public` schema. Tables: `users`, `sessions`, `daily_briefs`, `daily_brief_items`, `strategic_tracks`, `application_ledger`, `event_timeline`, `company_memory`, `positioning_memory`, `companies`, `jobs`, `background_runs`, `run_events`. Mix of TEXT and UUID PKs. No content fingerprinting.

### V2: `careerloop.*` schema isolation (commit 68cbb43, 2026-05-25)

All CareerLoop tables moved to `careerloop` schema. `public` now holds only Supabase auth (`users`), LangGraph checkpoints, and Emote app tables. SQLite fallback code removed. `connection.py` hard-fails if DATABASE_URL absent. Schema dump exported: `docs/CAREERLOOP_SCHEMA.md` + `docs/CAREERLOOP_SCHEMA_DUMP.json`.

### V3: `careerloop.users` identity spine + repository layer (CURRENT)

22 tables in `careerloop` schema. All FKs standardized to reference `public.users(id)`. Repository layer: `careerloop/memory/repository_v2.py` (1040 lines, 7 classes, 32 methods). Centralized data access. `careerloop/memory/supabase_migration_v2.sql` adds V2 columns, indexes, RLS policies, and new tables (`job_candidates`, `user_job_relationships`, `applications`, `application_packs`, `people_to_reach`, `outreach_messages`, `followups`, `user_evidence`, `user_preferences`, `outcome_events`). Idempotent; safe to re-run.

### Next: V3.1 hardening

1. Backfill TEXT→UUID PKs on `jobs`, `background_runs`, `daily_brief_items`
2. Enforce FK constraints currently deferred (job_id TEXT → UUID)
3. Run `jobs.content_fingerprint` NOT NULL backfill
4. Remove dead v1 columns (original `jobs.id` TEXT, `companies.domain_slug`, etc.)

---

## Data Access Rules

1. **All DB access through `careerloop/memory/repository_v2.py`**. No raw SQL in session code, chat code, or tool handlers.
2. **Write-path functions** use `ON CONFLICT ... DO UPDATE` for idempotency.
3. **Read-path functions** return `Optional[dict]` or `List[dict]` — never raw cursors.
4. **All SQL is parameterized** with `%s` placeholders and RealDictCursor.
5. **RLS enforces per-user isolation** on all user-scoped tables. Global tables allow `SELECT` for any authenticated user; writes bypass RLS (service role).

### Repository classes

| Class | Tables | Purpose |
|-------|--------|---------|
| `JobRepository` | `jobs`, `companies` | Global job cache ops |
| `DiscoveryRepository` | `background_runs`, `run_events`, `job_candidates` | Raw discovery pipeline |
| `UserJobRepository` | `user_job_relationships` | Per-user job personalization |
| `BriefRepository` | `daily_briefs`, `daily_brief_items` | Daily brief lifecycle |
| `ApplicationRepository` | `applications`, `application_packs`, `followups` | Apply + pack + follow-up |
| `PeopleRepository` | `people_to_reach`, `outreach_messages` | Recruiter + outreach |
| `EvidenceRepository` | `user_evidence`, `user_preferences`, `outcome_events` | Evidence + prefs + learning |
