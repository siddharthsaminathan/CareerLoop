# CareerLoop Data Engineering Architecture

> Canonical data model. Supabase PostgreSQL only. No SQLite.

## Design Principles

- **Global job data is reusable across users.** Same LinkedIn job seen by 5 users = 1 row in `jobs`.
- **User-specific relationship stored separately.** `user_job_relationships` tracks per-user fit, status, history.
- **DB is canonical.** Filesystem is cache/export only.
- **No scattered SQL.** All access through `careerloop/memory/repository_v2.py`.
- **Idempotent migrations.** `careerloop/memory/supabase_migration_v2.sql` can run multiple times safely.

## Entity-Relationship Diagram

```
users ──< user_job_relationships >── jobs ──< daily_brief_items >── daily_briefs
  │                                      │                              │
  ├── user_preferences                   ├── job_candidates              ├── background_runs
  ├── user_evidence                      └── companies                  └── run_events
  ├── applications ──< application_packs
  ├── outreach_messages >── people_to_reach
  ├── followups
  └── outcome_events
```

## Table Inventory

| Table | Purpose | Global/User |
|-------|---------|-------------|
| `jobs` | Global canonical job registry | Global |
| `companies` | Company profiles | Global |
| `job_candidates` | Raw discovery before dedupe | Run-scoped |
| `user_job_relationships` | Per-user fit/memory per job | User-scoped |
| `daily_briefs` | User-facing daily artifact | User-scoped |
| `daily_brief_items` | Numbered brief list items | User-scoped |
| `background_runs` | Async job tracking | User-scoped |
| `run_events` | Live streaming observability | Run-scoped |
| `applications` | Applied/acted jobs | User-scoped |
| `application_packs` | Generated execution bundles | User-scoped |
| `people_to_reach` | Recruiters/referrers | Global |
| `outreach_messages` | Sent messages | User-scoped |
| `followups` | Scheduled follow-ups | User-scoped |
| `user_evidence` | Truth-grounded claims | User-scoped |
| `user_preferences` | Structured career prefs | User-scoped |
| `outcome_events` | Learning loop | User-scoped |
| `users` | Auth + base profile | User-scoped |
| `sessions` | Runtime state + active_context | User-scoped |

## Cache Strategy

1. **Cache-first:** Check `jobs` table for recent active jobs matching role/city before external search.
2. **Cache-hit path:** Existing jobs → user fit scoring → user_job_relationships → daily_brief_items.
3. **Cache-miss path:** External search → job_candidates → dedupe → upsert into jobs → score → brief.

## TTL Rules

| Table | TTL | Action |
|-------|-----|--------|
| `jobs` | 30 days unseen → stale | Mark `status=expired` |
| `jobs` | 60 days unseen | Hard-delete or archive |
| `job_candidates` | 30 days | Archive/delete |
| `run_events` | 14 days | Delete, keep summary in `background_runs.stats` |
| `daily_briefs` | Permanent | Never delete |
| `application_packs` | Permanent | Never delete (user can request deletion) |

## Migration

Run: `careerloop/memory/supabase_migration_v2.sql`
All statements use `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN IF NOT EXISTS`.
Idempotent. Safe to re-run.

## Data Access

All access through `careerloop/memory/repository_v2.py`:
- `JobRepository` — Global job cache
- `DiscoveryRepository` — Background runs + run_events + candidates
- `UserJobRepository` — User-job personalization
- `BriefRepository` — Daily briefs + items
- `ApplicationRepository` — Applications + packs + followups
- `PeopleRepository` — People + outreach
- `EvidenceRepository` — Evidence + preferences + outcomes

## Status

**2026-05-25**: Schema designed, migration created, repository layer implemented. All tables are CREATE IF NOT EXISTS — production-safe to run against Supabase.
