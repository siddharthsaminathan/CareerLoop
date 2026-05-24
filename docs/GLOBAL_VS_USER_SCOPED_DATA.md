# Global vs User-Scoped Data

> Canonical reference for deciding whether a column, row, or table belongs to the global layer or the user-scoped layer. All agents must consult this before writing schema changes.

---

## Principle

**Global data is reusable across users. User-scoped data is per-user. Never duplicate global rows per user.**

When the same LinkedIn job is seen by 5 users, there must be exactly 1 row in `careerloop.jobs` — not 5. The user-specific layer (`careerloop.user_job_relationships`) stores each user's individual relationship to that one global row.

This is the core architectural invariant of CareerLoop's data model. Violating it creates data duplication, stale scores, and cross-user signal pollution.

---

## Global Tables

Tables where one row serves all users. These are read by all authenticated users, writable only by the system (service role).

| Table | Why Global | Dedup Key | Row Lifetime |
|-------|-----------|-----------|--------------|
| `careerloop.jobs` | Same LinkedIn job seen by N users = 1 row. Score once, cache once. | `content_fingerprint` (SHA256 of title+company+city) | Expire after 60 days unseen |
| `careerloop.companies` | Company profile (name, domain, ATS provider, industry) reused across all jobs at that company. | `domain` or `normalized_name` | Permanent |
| `careerloop.people_to_reach` | Recruiter/hiring-manager contact info is company-level. Discovered once, used by all users targeting that company. | (company_id, linkedin_url) | Permanent |

### Global table access rules

- **Read:** Any authenticated user can SELECT. RLS policy: `auth.role() = 'authenticated'`.
- **Write:** Only the service role (bypasses RLS). Application code uses the service-role connection.
- **Never:** Store user-specific data (fit scores, user notes, apply status) in global tables. Use the relationship layer.

---

## User-Scoped Tables

Tables where each row belongs to exactly one user. All have `user_id UUID REFERENCES public.users(id)` and RLS policy `auth.uid() = user_id`.

| Table | Why User-Scoped | FK Chain | Row Lifetime |
|-------|----------------|----------|--------------|
| `careerloop.sessions` | Runtime state (journey state, active context, onboarding step) is per-user by definition. | user_id → public.users | Permanent (one row per user) |
| `careerloop.daily_briefs` | Daily job brief is a per-user artifact. Different users get different briefs from the same global job pool. | user_id → public.users; run_id → background_runs | Permanent |
| `careerloop.daily_brief_items` | Items within a user's brief. Belongs to user via brief_id FK chain. | brief_id → daily_briefs (which has user_id) | Permanent |
| `careerloop.user_job_relationships` | How THIS user relates to THIS global job (matched/rejected/saved/skipped/applied). The bridge table between global jobs and user-scoped actions. | user_id → public.users; job_id → jobs | Permanent |
| `careerloop.applications` | The user's application action on a specific job. Tracks status: prepared → applied → interview → offer/rejected. | user_id → public.users; job_id → jobs | Permanent (audit trail) |
| `careerloop.application_packs` | Generated execution bundle (tailored CV + cover letter + recruiter DM) for a specific user+job combination. | user_id → public.users; job_id → jobs; run_id → background_runs | Permanent |
| `careerloop.outreach_messages` | Messages the user sent (or drafted) to recruiters/referrers. | user_id → public.users; person_id → people_to_reach; job_id → jobs | 90 days after last update |
| `careerloop.followups` | User's scheduled follow-up actions. | user_id → public.users; application_id → applications | 90 days after completion |
| `careerloop.user_preferences` | User's career targeting: roles, cities, salary range, work mode, avoid-list. | user_id PK+FK → public.users | Permanent (one row per user) |
| `careerloop.user_evidence` | Truth-grounded claims (projects, achievements, skills, certs) extracted from user's CV or added manually. | user_id → public.users | Permanent |
| `careerloop.outcome_events` | Learning loop: interview scheduled, offer received, rejected, ghosted. Permanent record for pattern analysis. | user_id → public.users; job_id → jobs; application_id → applications | Permanent (learning loop) |
| `careerloop.strategic_tracks` | User's positioning tracks (e.g., "AI PM track", "Backend IC track"). Each track has its own resume variant, outreach style, success metrics. | user_id → public.users | Permanent |
| `careerloop.positioning_memory` | Per-track, per-company narrative memory. What framing worked or failed for this user at this company. | user_id → public.users; track_id → strategic_tracks | Permanent |
| `careerloop.company_memory` | User's private company intelligence notes and synthesis. UNIQUE(user_id, company_normalized) — one note set per user per company. | user_id → public.users | Permanent |
| `careerloop.application_ledger` | Legacy application tracker (mirror of ledger.json). One entry per user per job. | user_id → public.users; track_id → strategic_tracks | Permanent |
| `careerloop.event_timeline` | User's personal event log (status changes, milestones, reminders). | user_id → public.users | Permanent |
| `careerloop.background_runs` | Async job runs initiated by the user (scans, pack generation). | user_id → public.users | Permanent (audit trail) |

---

## Run-Scoped Tables (Hybrid)

These tables are scoped to a specific background run, which in turn is user-scoped. They are ephemeral — cleaned up after the run completes or after a TTL.

| Table | Scope | FK Chain | Cleanup |
|-------|-------|----------|---------|
| `careerloop.job_candidates` | Run | run_id → background_runs (which has user_id) | Archive after 30 days |
| `careerloop.run_events` | Run | run_id → background_runs | Delete after 14 days; summary kept in background_runs.stats |

---

## Anti-Patterns

These are forbidden. If you find one in the codebase, it is a bug.

### Do Not Duplicate Global Rows Per User

```
# WRONG: Creating a new jobs row every time a user discovers the same job
INSERT INTO careerloop.jobs (title, company_name, ...)
VALUES ('AI Engineer', 'Stripe', ...)  -- Creates duplicate row
```

```
# RIGHT: Check fingerprint first, then insert or update
INSERT INTO careerloop.jobs (...) VALUES (...)
ON CONFLICT (content_fingerprint) DO UPDATE SET last_seen_at = NOW()
```

### Do Not Store User-Specific Data in Global Tables

```
# WRONG: Adding fit_score column to jobs table
ALTER TABLE careerloop.jobs ADD COLUMN fit_score_for_siddharth REAL;
```

```
# RIGHT: Store in user_job_relationships
INSERT INTO careerloop.user_job_relationships (user_id, job_id, fit_score)
VALUES ('siddharth-uuid', 'job-uuid', 73.5)
```

### Do Not Query User-Scoped Tables Without user_id Filter

```
# WRONG: Cross-user query
SELECT * FROM careerloop.applications WHERE status = 'applied';
```

```
# RIGHT: Always filter by user_id
SELECT * FROM careerloop.applications WHERE user_id = %s AND status = 'applied';
```

### Do Not Create Per-User Company Rows

```
# WRONG: Duplicating company profile per user
INSERT INTO careerloop.companies (name, user_id) ...
```

```
# RIGHT: One global company row; user-specific notes go in company_memory
INSERT INTO careerloop.company_memory (user_id, company_normalized, company_intelligence) ...
```

### Do Not Store Fit Scores in the Jobs Table

Fit scores are per-user, not per-job. A job that is a 73/100 for Siddharth might be a 45/100 for Varsha. Store the score in `user_job_relationships.fit_score`, never in `jobs`.

---

## Query Patterns

### Finding all jobs a user matched today (cache-hit path)

```sql
SELECT j.*, r.fit_score, r.match_status
FROM careerloop.jobs j
JOIN careerloop.user_job_relationships r ON r.job_id = j.job_id
WHERE r.user_id = %s
  AND r.match_status = 'matched'
  AND j.last_seen_at >= NOW() - INTERVAL '7 days'
  AND j.status = 'active'
ORDER BY r.fit_score DESC NULLS LAST;
```

### Finding fresh global jobs without user relationships (cache-miss path)

```sql
SELECT j.*
FROM careerloop.jobs j
WHERE j.status = 'active'
  AND j.last_seen_at >= NOW() - INTERVAL '7 days'
  AND NOT EXISTS (
      SELECT 1 FROM careerloop.user_job_relationships r
      WHERE r.job_id = j.job_id AND r.user_id = %s
  )
ORDER BY j.last_seen_at DESC
LIMIT 50;
```

### Getting a user's daily brief with all items

```sql
SELECT b.*, i.item_index, i.fit_score, i.title, i.company, i.location,
       i.recommendation_reason, i.route_recommendation
FROM careerloop.daily_briefs b
JOIN careerloop.daily_brief_items i ON i.brief_id = b.id
WHERE b.user_id = %s
  AND b.date_str = %s
ORDER BY i.item_index ASC;
```

---

## Schema Decision Tree

When adding a new table or column, ask:

1. **Does this data change per user?** If yes, it goes in a user-scoped table with `user_id FK`. If no, it belongs in a global table.

2. **Could two users ever have different values for the same entity?** If yes, user-scoped. If no, global.

3. **Is this a user's action, preference, or learning?** If yes, user-scoped. Always.

4. **Is this a fact about the external world (a job posting, a company, a person)?** If yes, global.

5. **Is this ephemeral (tied to a specific run)?** If yes, run-scoped with `run_id FK` to `background_runs`.

If you cannot answer, default to user-scoped. It is easier to deduplicate and promote user-scoped data to global later than to unwind global data pollution.
