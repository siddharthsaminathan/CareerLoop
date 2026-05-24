# Job Persistence Engine

> How CareerLoop discovers, deduplicates, stores, scores, and personalizes jobs across the global cache and per-user relationship layer.

---

## Architecture

```
External Sources (14 ATS + 6 boards)
         │
         ▼
  careerloop.job_candidates  ←── Raw discovery staging (per run, ephemeral)
         │
         │ SHA256 fingerprint dedup
         ▼
  careerloop.jobs            ←── Global canonical job registry (one row per job)
         │
         │ Per-user fit scoring
         ▼
  careerloop.user_job_relationships  ←── Per-user match/reject/apply status
         │
         │ Brief assembly
         ▼
  careerloop.daily_briefs + daily_brief_items  ←── User-facing daily artifact
```

---

## Tables

### `careerloop.jobs` — Global Canonical Job Registry

The single source of truth for every job discovered. One row per unique job, identified by content fingerprint.

| Column | Purpose |
|--------|---------|
| `job_id` (UUID PK) | Unique identifier (v2); `id` (TEXT) is v1 legacy |
| `content_fingerprint` (TEXT, UNIQUE) | SHA256(normalized_title + company_name + location_city) |
| `source` | Discovery source: `linkedin`, `greenhouse`, `lever`, `ashby`, `jobspy`, `ddg`, etc. |
| `title`, `normalized_title` | Raw and normalized job title |
| `company_name`, `company_id` | Company reference (TEXT for dedup; UUID FK to companies) |
| `location_raw`, `location_city`, `location_country` | Geo fields |
| `is_india_role` (BOOLEAN) | True if location is in India |
| `work_mode` | `remote`, `hybrid`, `onsite` |
| `jd_text` | Full job description text |
| `jd_hash` | SHA256 of jd_text for change detection |
| `apply_url` | Direct application link |
| `canonical_url` | Permanent URL (ATS portal URL, not tracking redirect) |
| `salary_min`, `salary_max`, `salary_currency` | Compensation (when available) |
| `first_seen_at` | First discovery timestamp |
| `last_seen_at` | Most recent re-discovery timestamp |
| `expires_at` | Posting expiration (when available from ATS) |
| `status` | `active`, `expired`, `unknown` |
| `raw_payload` (JSONB) | Full source response for debugging |

### `careerloop.job_candidates` — Raw Discovery Staging

Ephemeral table for each scan run. Stores raw hits before dedup and scoring.

| Column | Purpose |
|--------|---------|
| `candidate_id` (UUID PK) | Unique candidate row |
| `run_id` (UUID FK) | Background run that discovered this |
| `source`, `query` | What source and query produced this hit |
| `raw_title`, `raw_company`, `raw_location`, `raw_url`, `raw_snippet` | Raw fields before normalization |
| `raw_payload` (JSONB) | Full source response |
| `extraction_status` | `pending` / `extracted` / `rejected` |
| `rejection_stage` | Which filter stage rejected it |
| `rejection_reason` | Why it was rejected |
| `matched_job_id` (UUID FK) | Link to canonical job after dedup |

### `careerloop.job_search_runs` — (Pending, not yet implemented)

Per-scan analytics. Currently stats are stored in `background_runs.stats` JSONB.

### `careerloop.user_job_relationships` — Per-User Personalization

The bridge between global jobs and user actions. One row per (user, job) pair.

| Column | Purpose |
|--------|---------|
| `user_id` (UUID FK) | User |
| `job_id` (UUID FK) | Job |
| `fit_score` (NUMERIC) | User-specific match score |
| `fit_label` | `strong_match`, `possible`, `weak` |
| `match_status` | `matched`, `rejected`, `maybe`, `saved`, `skipped`, `interested`, `applied` |
| `rejection_reason` | Why rejected (e.g., `outside_geo`, `wrong_role`, `low_score`) |
| `route_recommendation` | `direct_apply`, `recruiter_first`, `referral_first`, `skip` |
| `user_seen_at` | When user first saw this job |
| `swiped_action` | User's swipe/action (UI layer) |
| `interest_level` | Explicit interest marker |
| `shown_in_brief_id` | Which brief introduced this job to the user |
| `personalization_payload` (JSONB) | User-specific scoring details |

---

## Cache Strategy

### Cache-First Flow

```
1. Check careerloop.jobs for active India jobs matching role + city
   ↓
2. If cache has >= 10 fresh matches (last_seen < 7 days, status = 'active')
   → Use cache-first. Score existing jobs without external API calls.
   ↓
3. If cache is thin (< 5 fresh matches)
   → Trigger external search (ATS portals + job boards)
   ↓
4. All discovered jobs → careerloop.job_candidates
   → Geo filter (India only)
   → Role filter (title + normalized_title matching)
   → Dedupe via content_fingerprint
   → UPSERT into careerloop.jobs
   ↓
5. All matched jobs → create/update careerloop.user_job_relationships rows
```

### Cache Query (Finding Fresh Active Jobs)

```sql
SELECT job_id, title, company_name, location_city, normalized_title,
       jd_text, source, last_seen_at
FROM careerloop.jobs
WHERE status = 'active'
  AND is_india_role = true
  AND last_seen_at >= NOW() - INTERVAL '7 days'
  AND (location_city = ANY(%s) OR location_city IS NULL)
ORDER BY last_seen_at DESC;
```

---

## TTL Policy

| Age | Status | Behavior |
|-----|--------|----------|
| 0-7 days | Active (fresh) | Shown in brief, used for scoring |
| 7-30 days | Active (stale) | Still shown but marked as stale |
| 30-60 days | Active (stale) | Still queryable, not shown in brief |
| > 60 days unseen | Expired | `status = 'expired'` set by `JobRepository.expire_stale_jobs()` |
| apply_url returns 404 | Expired (dead) | Immediately set `status = 'expired'` |

**TTL enforcement:** `JobRepository.expire_stale_jobs(days=60)` should be called daily by the background scheduler or daily runner.

---

## Dedup Strategy

### Content Fingerprint

```
content_fingerprint = SHA256(normalized_title + company_name + location_city)
```

- `normalized_title`: lowercase, stripped of special chars, first meaningful words (e.g., "senior backend engineer" from "Senior Backend Engineer - Platform Team")
- `company_name`: lowercase, stripped of legal suffixes (Pvt Ltd, Inc, Corp, GmbH)
- `location_city`: lowercase, first city extracted from location string

### Dedup on Insert

```sql
INSERT INTO careerloop.jobs (job_id, content_fingerprint, ...)
VALUES (%s, %s, ...)
ON CONFLICT (content_fingerprint) DO UPDATE SET
    title          = EXCLUDED.title,
    company_name   = EXCLUDED.company_name,
    jd_text        = EXCLUDED.jd_text,
    apply_url      = EXCLUDED.apply_url,
    last_seen_at   = NOW(),
    updated_at     = NOW();
```

### Why UNIQUE on content_fingerprint

- Prevents duplicate rows for the same job discovered through different sources (e.g., LinkedIn + Greenhouse + Google Jobs all showing the same Stripe role).
- The `ON CONFLICT DO UPDATE` ensures `last_seen_at` is refreshed on re-discovery, keeping the cache warm for jobs still being posted.

### Pre-Dedup Filtering (before writing to job_candidates)

Candidates are rejected before ever reaching the dedup layer if:

1. **Not India:** `is_india_role = false` (location not in India)
2. **Wrong role:** title mismatch against user's target roles and normalized role blacklist
3. **Bad company:** company name matches known body-shop/consultancy blacklist
4. **Dead link:** apply_url returns 404 or connection error

---

## User-Job Lifecycle

```
 discovered ──→ viewed ──→ shortlisted ──→ applied ──→ interview ──→ offer
     │              │           │               │            │
     │              │           │               │            └── rejected
     │              │           │               │
     │              │           │               └── rejected ──→ (learning loop)
     │              │           │
     │              │           └── skipped (fit_score < threshold or user passed)
     │              │
     │              └── passed (user saw brief item, no action)
     │
     └── rejected (geo filter, role filter, company filter)
```

Each state transition is recorded in `user_job_relationships.match_status`:

| match_status | Meaning |
|-------------|---------|
| `matched` | Job passed all filters, scored, and shown to user |
| `interested` | User explicitly marked interest (clicked item, said "looks good") |
| `maybe` | User is uncertain — save for later |
| `saved` | User bookmarked for future reference |
| `skipped` | User explicitly passed |
| `rejected` | System or user rejected (with rejection_reason) |
| `applied` | User applied to this job |

---

## Fit Scoring Integration

When a job is matched to a user:

1. **India Fit Engine (cheap, all jobs):** Geo + title + company fast filter. Rejects non-India, wrong role, bad company. Pass-through jobs get a base score.
2. **Full scoring (lazy, top-N only):** OpenAI/DeepSeek call for ~10 best-fit jobs. Produces 0-100 score with detailed breakdown.
3. **Score stored in `user_job_relationships.fit_score`** — not in the jobs table. Same job can have different scores for different users.
4. **Route recommendation** computed after scoring: `direct_apply` (high score + easy apply), `recruiter_first` (high score + need intro), `referral_first` (need warm connection), `skip` (below threshold).

---

## Source-Aware Weighting

When the same job is discovered through multiple sources, the source weight affects display ordering (not scoring):

| Source Type | Weight | Reasoning |
|-------------|--------|-----------|
| ATS direct (Greenhouse, Lever, Ashby, etc.) | +3.0 | Verified, often still open |
| Company career page scrape | +1.5 | Direct from employer, high confidence |
| JobSpy (LinkedIn + Indeed aggregate) | +1.0 | Broad coverage, variable freshness |
| Google Jobs / DDG / generic | +0.0 | Lower confidence, aggregate |

---

## Operations

### Daily: Cache Warm-Up

Run by `DailyRunner` or background scheduler:

1. `JobRepository.expire_stale_jobs(days=60)` — mark old jobs expired
2. Check active job count per user's target cities
3. If thin, trigger external search
4. Score new matches → populate `user_job_relationships`
5. Assemble daily brief

### Weekly: Candidate Cleanup

1. Delete `job_candidates` rows older than 30 days
2. Delete `run_events` rows older than 14 days
3. Archive stats into `background_runs.stats` before deletion

### On-Demand: User Scans

1. User initiates scan via chat or command
2. `background_runs` row created with `status = 'QUEUED'`
3. 6 board sources run in parallel via `ThreadPoolExecutor`
4. Live events streamed to `run_events` for CLI rendering
5. Results flow through candidate → dedup → jobs → relationships pipeline

---

## Known Gaps

1. **`job_search_runs` table not yet created.** Per-scan analytics currently live in `background_runs.stats` JSONB.
2. **TEXT→UUID backfill pending for jobs.id and daily_brief_items.job_id.** Scheduled for v2.1.
3. **No expiry date extraction from ATS metadata.** `expires_at` column exists but is rarely populated from source data.
4. **No stale-job re-verification.** Jobs older than 7 days are not re-checked for liveness. A `check-liveness.mjs` script exists but is not wired into the automated cache pipeline.
