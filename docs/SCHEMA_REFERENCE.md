# CareerLoop Schema Reference Card

> Quick-reference card for agents. For full details, see `DATA_MODEL_CANONICAL.md`.

---

## Quick Lookup

| Question | Answer |
|----------|--------|
| Total tables | 22 in `careerloop.*` + 1 in `public.users` (identity) |
| Identity root | `public.users(id)` — Supabase Auth |
| Schema | `careerloop` (isolated from Supabase auth and Emote app) |
| PK standard | New tables: `UUID DEFAULT gen_random_uuid()`. Legacy TEXT PKs on `jobs.id`, `background_runs.run_id`, `run_events.event_id` |
| FK standard | All user FKs: `UUID REFERENCES public.users(id)`. All job FKs: `UUID REFERENCES careerloop.jobs(job_id)` |
| Dedup | `jobs.content_fingerprint` UNIQUE (SHA256 of title+company+city) |
| RLS | User-scoped tables: `auth.uid() = user_id`. Global tables: `auth.role() = 'authenticated'` SELECT only |
| Repository | All access through `careerloop/memory/repository_v2.py` (7 classes, 32 methods) |
| Migration | `careerloop/memory/supabase_migration_v2.sql` — idempotent, safe to re-run |

---

## Table Directory

### User Identity & Profile
```
public.users                         — Auth + master CV + profile
careerloop.user_preferences          — Targeting (roles, cities, salary, work mode)
careerloop.user_evidence             — Truth claims (projects, skills, certs)
```

### Session & Runtime
```
careerloop.sessions                  — Journey state + active context
careerloop.background_runs           — Async runs (scan, pack gen)
careerloop.run_events                — Streaming observability events
careerloop.event_timeline            — User-level event log
```

### Global Job Cache
```
careerloop.jobs                      — Canonical job registry (fingerprint-deduped)
careerloop.companies                 — Company profiles (domain-deduped)
careerloop.job_candidates            — Raw discovery staging (ephemeral)
```

### User-Job Bridge
```
careerloop.user_job_relationships    — Per-user match/reject/save per job
careerloop.daily_briefs              — Daily job brief per user
careerloop.daily_brief_items         — Numbered items within a brief
```

### Application Engine
```
careerloop.applications              — Applied jobs + status tracking
careerloop.application_packs         — Generated bundles (CV + cover + DM)
careerloop.application_ledger        — Legacy tracker (ledger.json mirror)
```

### People & Outreach
```
careerloop.people_to_reach           — Recruiters, hiring managers
careerloop.outreach_messages         — Drafted/sent messages
careerloop.followups                 — Scheduled follow-up actions
```

### Positioning & Strategy
```
careerloop.strategic_tracks          — User positioning tracks
careerloop.positioning_memory        — Per-track per-company narrative memory
```

### Company Intelligence
```
careerloop.company_memory            — Per-user private company intel
```

### Learning Loop
```
careerloop.outcome_events            — Interview/offer/rejection events
```

---

## Foreign Key Summary

```
public.users(id)
  ├── careerloop.sessions(user_id)
  ├── careerloop.strategic_tracks(user_id)
  │     └── careerloop.positioning_memory(track_id) + (user_id)
  ├── careerloop.application_ledger(user_id, track_id → strategic_tracks)
  ├── careerloop.event_timeline(user_id)
  ├── careerloop.company_memory(user_id)
  ├── careerloop.background_runs(user_id)
  │     ├── careerloop.run_events(run_id)
  │     ├── careerloop.job_candidates(run_id)
  │     └── careerloop.daily_briefs(run_id) + (user_id)
  │           └── careerloop.daily_brief_items(brief_id, job_id → jobs)
  ├── careerloop.applications(user_id, job_id → jobs)
  │     └── careerloop.followups(application_id, user_id)
  ├── careerloop.application_packs(user_id, job_id → jobs, run_id → bg_runs)
  ├── careerloop.user_job_relationships(user_id, job_id → jobs)
  ├── careerloop.outreach_messages(user_id, person_id → people, job_id → jobs)
  ├── careerloop.user_evidence(user_id)
  ├── careerloop.user_preferences(user_id PK+FK)
  └── careerloop.outcome_events(user_id, job_id → jobs, application_id → apps)

careerloop.companies(id)
  ├── careerloop.jobs(company_id)
  └── careerloop.people_to_reach(company_id)
```

---

## Common Queries

### 1. Get user session with profile

```sql
SELECT s.state, s.active_job_id, s.active_brief_id, s.active_pack_id,
       s.current_selection_index,
       u.master_cv_markdown, u.full_name, u.email
FROM careerloop.sessions s
JOIN public.users u ON u.id = s.user_id
WHERE s.user_id = %s;
```

### 2. Get today's brief with all items

```sql
SELECT b.id AS brief_id, b.date_str, b.summary_text, b.stats,
       i.item_index, i.fit_score, i.title, i.company, i.location,
       i.recommendation_reason, i.risk_summary, i.route_recommendation
FROM careerloop.daily_briefs b
JOIN careerloop.daily_brief_items i ON i.brief_id = b.id
WHERE b.user_id = %s AND b.date_str = to_char(CURRENT_DATE, 'YYYY-MM-DD')
ORDER BY i.item_index ASC;
```

### 3. Find fresh active jobs for a user's cities (cache-first)

```sql
SELECT j.job_id, j.normalized_title, j.company_name, j.location_city,
       j.source, j.apply_url, j.last_seen_at, j.jd_text
FROM careerloop.jobs j
WHERE j.status = 'active'
  AND j.is_india_role = true
  AND j.last_seen_at >= NOW() - INTERVAL '7 days'
  AND (j.location_city = ANY(%s) OR j.location_city IS NULL)
  AND NOT EXISTS (
      SELECT 1 FROM careerloop.user_job_relationships r
      WHERE r.job_id = j.job_id AND r.user_id = %s
  )
ORDER BY j.last_seen_at DESC
LIMIT 50;
```

### 4. Get user's matched jobs with relationships

```sql
SELECT j.job_id, j.title, j.company_name, j.location_city, j.source,
       j.apply_url, j.last_seen_at, r.fit_score, r.match_status,
       r.route_recommendation, r.user_seen_at
FROM careerloop.user_job_relationships r
JOIN careerloop.jobs j ON j.job_id = r.job_id
WHERE r.user_id = %s
  AND r.match_status IN ('matched', 'interested', 'saved')
ORDER BY r.fit_score DESC NULLS LAST
LIMIT 50;
```

### 5. Get run events for live streaming

```sql
SELECT event_id, event_type, message, payload, timestamp
FROM careerloop.run_events
WHERE run_id = %s
ORDER BY timestamp ASC
LIMIT 100;
```

---

## Index Quick Reference

| Index Name | Table | Columns | Type |
|-----------|-------|---------|------|
| `idx_jobs_fingerprint` | `jobs` | `content_fingerprint` | UNIQUE |
| `idx_jobs_last_seen` | `jobs` | `last_seen_at` | BTREE |
| `idx_jobs_status` | `jobs` | `status` | BTREE |
| `idx_jobs_city` | `jobs` | `location_city` | BTREE |
| `idx_jobs_title` | `jobs` | `normalized_title` | BTREE |
| `idx_jobs_source` | `jobs` | `source` | BTREE |
| `idx_jobs_company` | `jobs` | `company_name` | BTREE |
| `idx_jobs_job_id` | `jobs` | `job_id` | BTREE |
| `idx_companies_normalized` | `companies` | `normalized_name` | UNIQUE |
| `idx_companies_domain` | `companies` | `domain` WHERE NOT NULL | UNIQUE (partial) |
| `idx_ujr_match_status` | `user_job_relationships` | `match_status` | BTREE |
| `idx_ujr_fit_score` | `user_job_relationships` | `fit_score` | BTREE |
| `idx_briefs_user_date` | `daily_briefs` | `user_id, date_str` | BTREE |
| `idx_briefs_status` | `daily_briefs` | `status` | BTREE |
| `idx_brief_items_job` | `daily_brief_items` | `job_id` | BTREE |
| `idx_candidates_run` | `job_candidates` | `run_id` | BTREE |
| `idx_candidates_status` | `job_candidates` | `extraction_status` | BTREE |
| `idx_bg_runs_status` | `background_runs` | `status` | BTREE |
| `idx_bg_runs_type` | `background_runs` | `run_type` | BTREE |
| `idx_run_events_type` | `run_events` | `event_type` | BTREE |
| `idx_apps_user` | `applications` | `user_id` | BTREE |
| `idx_apps_status` | `applications` | `status` | BTREE |
| `idx_apps_job` | `applications` | `job_id` | BTREE |
| `idx_packs_user` | `application_packs` | `user_id` | BTREE |
| `idx_packs_job` | `application_packs` | `job_id` | BTREE |
| `idx_people_company` | `people_to_reach` | `company_id` | BTREE |
| `idx_people_job` | `people_to_reach` | `job_id` | BTREE |
| `idx_outreach_user` | `outreach_messages` | `user_id` | BTREE |
| `idx_outreach_status` | `outreach_messages` | `status` | BTREE |
| `idx_followups_user` | `followups` | `user_id` | BTREE |
| `idx_followups_due` | `followups` | `due_at` WHERE status='pending' | BTREE (partial) |
| `idx_evidence_user` | `user_evidence` | `user_id` | BTREE |
| `idx_evidence_type` | `user_evidence` | `evidence_type` | BTREE |
| `idx_outcomes_user` | `outcome_events` | `user_id` | BTREE |
| `idx_outcomes_type` | `outcome_events` | `event_type` | BTREE |
| `idx_outcomes_occurred` | `outcome_events` | `occurred_at` | BTREE |

---

## Check Constraint Reference

| Table | Column | Valid Values |
|-------|--------|-------------|
| `jobs` | `status` | `active`, `expired`, `unknown` |
| `user_job_relationships` | `match_status` | `matched`, `rejected`, `maybe`, `saved`, `skipped`, `interested`, `applied` |
| `user_job_relationships` | `route_recommendation` | `direct_apply`, `recruiter_first`, `referral_first`, `skip` |
| `applications` | `status` | `prepared`, `applied`, `followup_due`, `recruiter_contacted`, `referral_requested`, `interview_scheduled`, `rejected`, `offer` |
| `application_packs` | `status` | `draft`, `ready`, `sent`, `archived` |
| `outreach_messages` | `message_type` | `recruiter_dm`, `referral_ask`, `followup`, `thank_you` |
| `outreach_messages` | `status` | `drafted`, `sent`, `replied`, `ghosted` |
| `followups` | `status` | `pending`, `sent`, `completed`, `skipped` |
| `user_evidence` | `evidence_type` | `project`, `work_achievement`, `skill`, `education`, `certification`, `link` |
| `user_evidence` | `source` | `resume`, `linkedin`, `manual`, `chat` |
| `user_preferences` | `aggressiveness` | `conservative`, `moderate`, `aggressive` |
| `outcome_events` | `event_type` | `reply_received`, `interview_scheduled`, `rejected`, `ghosted`, `offer_received`, `followup_worked`, `recruiter_replied` |

---

## Repository Class Map

| Class | Tables | File |
|-------|--------|------|
| `JobRepository` | `jobs`, `companies` | `careerloop/memory/repository_v2.py` |
| `DiscoveryRepository` | `background_runs`, `run_events`, `job_candidates` | same |
| `UserJobRepository` | `user_job_relationships` | same |
| `BriefRepository` | `daily_briefs`, `daily_brief_items` | same |
| `ApplicationRepository` | `applications`, `application_packs`, `followups` | same |
| `PeopleRepository` | `people_to_reach`, `outreach_messages` | same |
| `EvidenceRepository` | `user_evidence`, `user_preferences`, `outcome_events` | same |

---

## Migration Files

| File | Purpose | Safe to Re-run? |
|------|---------|----------------|
| `careerloop/memory/supabase_schema.sql` | V1 base schema (users, sessions, daily_briefs, companies, jobs, etc.) | Yes (CREATE IF NOT EXISTS) |
| `careerloop/memory/supabase_migration_v2.sql` | V2 additions (new tables, new columns, indexes, RLS) | Yes (idempotent ALTER ADD IF NOT EXISTS + DO block for RLS) |

---

## Key Architecture Rules

1. **Never query `careerloop.*` tables without `user_id` filter** on user-scoped tables.
2. **Never store user-specific data in global tables** (`jobs`, `companies`, `people_to_reach`).
3. **Never duplicate global rows per user** — use the relationship layer.
4. **All writes go through `repository_v2.py`** — no raw SQL in session/chat/tool code.
5. **All SQL is parameterized** — `%s` placeholders with `RealDictCursor`.
6. **RLS is always enabled** on all tables. Writes use service role connection.
7. **`careerloop.application_ledger` is legacy** — prefer `applications` + `outcome_events` for new code.
8. **Filesystem is cache/export only** — all state decisions live in PostgreSQL.
