# CareerLoop Memory Systems Architecture

> Canonical. Supabase PostgreSQL. careerloop schema only. No local filesystem memory.

## Core Principle

CareerLoop memory is NOT chat history. CareerLoop memory is **operational memory** that helps the system:
- remember who the user is
- remember what the user wants
- remember what the user can truthfully claim
- remember what jobs were found
- remember how the user reacted
- remember what actions were taken
- remember what outcomes happened
- improve future search, positioning, outreach, follow-up, and interview prep

---

## 1. Identity Memory

**Purpose:** Who the user is. The canonical identity spine for ALL CareerLoop data.

**Tables:** `careerloop.users`

**Stores:**
- `id` (UUID PK), `email`, `phone`
- `telegram_id`, `whatsapp_id`
- `linkedin_url`
- `full_name`
- `onboarding_status` (new, profile_ready, complete)
- `signup_source` (cli, telegram, web)
- `current_plan` (free, trial, pro)
- `trial_started_at`, `trial_ends_at`
- `status` (active, inactive, paused)
- `last_active_at`

**Lifecycle:** Created at signup (or first CLI message via `save_session()` idempotent INSERT). Updated on profile changes. Permanent.

**Access:** SessionStore, ActionResolver, ToolRegistry, repository_v2.py

**Identity policy:** Every CareerLoop table FK chains to `careerloop.users(id) ON DELETE CASCADE`. There are 16 tables with this FK. `public.users` (Supabase Auth) is the legacy identity root — all FKs were migrated to `careerloop.users` in V3 (supabase_migration_v3.sql, Section 3).

**Actual row count:** 17

---

## 2. Career Preference Memory

**Purpose:** What the user is optimizing for. Structured targeting preferences.

**Tables:** `careerloop.user_preferences`

**Stores:**
- `user_id` (UUID PK + FK to careerloop.users)
- `target_roles` (JSONB) — e.g., `["AI Product Manager", "Head of Applied AI"]`
- `target_cities` (JSONB) — e.g., `["Bangalore", "Remote"]`
- `salary_min`, `salary_max` (NUMERIC)
- `notice_period` (TEXT)
- `work_mode` (TEXT) — remote, hybrid, onsite
- `avoid_companies` (JSONB) — companies to exclude
- `avoid_role_types` (JSONB) — role types to skip
- `aggressiveness` (TEXT) — conservative, moderate, aggressive

**Lifecycle:** Set during onboarding. Updated when user refines preferences. Used by scan/filter/scoring. One row per user (PK is user_id).

**Access:** ToolRegistry.show_profile, start_scan, DailyRunner profile loading, EvidenceRepository

**Actual row count:** 0

---

## 3. Evidence Memory

**Purpose:** What the user can truthfully claim. Ground-truth for all generated content.

**Tables:** `careerloop.user_evidence`

**Stores:**
- `evidence_id` (UUID PK)
- `user_id` (UUID FK to careerloop.users)
- `evidence_type` (CHECK: project, work_achievement, skill, education, certification, link)
- `title`, `description`, `proof_url`
- `source` (CHECK: resume, linkedin, manual, chat)
- `confidence` (NUMERIC 0-1)

**Used by:** Resume Council, positioning engine, application packs, interview prep, truth validation

**Lifecycle:** Extracted at onboarding from CV/LinkedIn. Augmented over time from chat and interview feedback. Permanent.

**Rule:** Resume Council must never invent unsupported claims. Every claim in a generated resume must trace to a `user_evidence` row with `confidence > 0.5`.

**Actual row count:** 0

---

## 4. Opportunity Memory

**Purpose:** What the market contains. The global job and company registry.

**Tables:**
- `careerloop.jobs` — Global canonical job registry (fingerprint dedup). V2 schema with `job_id` UUID, `content_fingerprint` TEXT UNIQUE, 30+ columns including `normalized_title`, `location_city`, `location_country`, `is_india_role`, `work_mode`, `salary_min/max`, `jd_text`, `status` (active/expired/unknown), `raw_payload` JSONB.
- `careerloop.companies` — Global company profiles. `normalized_name` UNIQUE, `domain` UNIQUE (partial), `industry`, `size`, `funding_stage`, plus V1 legacy columns (`domain_slug`, `ats_provider`, `career_page_url`, `crawl_status`).
- `careerloop.job_sources` — Per-job source tracking (linkedin, naukri, greenhouse, ashby, lever). Dedup-friendly. `job_id + source + source_job_id`.
- `careerloop.job_candidates` — Raw discovery before dedup into jobs. Tied to a `run_id` (FK to background_runs). Ephemeral staging.
- `careerloop.job_search_runs` — Audit trail per scan/search execution. `query_params`, `candidates_found`, `after_dedup`, `after_geo_filter`, `after_role_filter`, `scored`, `shortlisted`, `cache_hit_ratio`, `sources_used`.

**Rules:**
- **Global, not user-scoped.** Same LinkedIn job seen by 5 users = 1 row in `jobs`.
- **Fingerprint dedup.** `content_fingerprint` UNIQUE index. `ON CONFLICT (content_fingerprint) DO UPDATE`.
- **TTL.** Active 7d, stale 30d, expired 60d. Soft-delete (`status = 'expired'`).
- **Never duplicate jobs per user.** User-specific state lives in `user_job_relationships`.
- **Job sources are global.** `job_sources` tracks which platform(s) a job was seen on — reused across users.

**Actual row counts:** jobs=3, companies=0, job_sources=0, job_candidates=0, job_search_runs=0

---

## 5. User-Opportunity Memory

**Purpose:** How one user relates to one job. The bridge between global opportunity and personal action.

**Tables:** `careerloop.user_job_relationships`

**Stores:**
- `user_id`, `job_id` (composite PK)
- `fit_score` (NUMERIC), `fit_label` (TEXT)
- `match_status` (CHECK: matched, rejected, maybe, saved, skipped, interested, applied)
- `rejection_reason` (TEXT)
- `user_seen_at` (TIMESTAMPTZ)
- `shown_in_brief_id` (UUID)
- `swiped_action` (TEXT), `interest_level` (TEXT)
- `route_recommendation` (CHECK: direct_apply, recruiter_first, referral_first, skip)
- `personalization_payload` (JSONB)

**Lifecycle state machine:**
```
discovered (job_candidates) → matched (user_job_relationships) → shown_in_brief → selected → applied → interview → offer
                                                                     ↘ skipped
                                                            ↘ rejected
```

**Rule:** This is where personalization lives. Same job can be `matched(88/100)` for user A and `rejected(15/100)` for user B.

**Actual row count:** 6

---

## 6. Execution Memory

**Purpose:** What actions actually happened. The tangible ROI layer — every application, pack, message, and follow-up.

**Tables:**
- `careerloop.application_packs` — Generated resume + cover + outreach bundles. `resume_artifact_id`, `cover_note`, `recruiter_dm`, `referral_dm`, `screening_answers` (JSONB), `company_intel_id`, `status` (draft/ready/sent/archived). FK to `jobs`, `background_runs`.
- `careerloop.applications` — Submitted applications with status tracking. `status` (prepared/applied/followup_due/recruiter_contacted/referral_requested/interview_scheduled/rejected/offer), `applied_at`, `apply_channel`. FK to `jobs`.
- `careerloop.outreach_messages` — Sent recruiter DMs, referral asks. `message_type` (recruiter_dm/referral_ask/followup/thank_you), `body`, `status` (drafted/sent/replied/ghosted). FK to `people_to_reach`, `jobs`, `applications`.
- `careerloop.followups` — Scheduled follow-ups. `due_at`, `status` (pending/sent/completed/skipped), `draft_message`. FK to `applications`, `people_to_reach`.
- `careerloop.people_to_reach` — Recruiters/hiring managers. `name`, `title`, `linkedin_url`, `source`, `relevance_reason`, `confidence`. FK to `companies`, `jobs`. Global-scoped.
- `careerloop.recruiter_contacts` — Extended people directory. `name`, `title`, `linkedin_url`, `email`, `phone`, `source`, `notes`, `last_contacted_at`. FK to `companies`. Global-scoped.

**Lifecycle:**
```
prepare_pack → approve → apply → followup_due → recruiter_contacted
                                              → interview_scheduled
                                              → rejected | offer
```

**Legacy table:** `careerloop.application_ledger` mirrors the old `ledger.json` format. Being phased out in favor of `applications` + `application_packs` + `outcome_events`.

**Actual row counts:** application_packs=0, applications=0, outreach_messages=0, followups=0, people_to_reach=0, recruiter_contacts=0

---

## 7. Learning Memory

**Purpose:** What CareerLoop learns from outcomes. Improves future recommendations.

**Tables:**
- `careerloop.outcome_events` — Structured outcome signals. `event_type` (reply_received, interview_scheduled, rejected, ghosted, offer_received, followup_worked, recruiter_replied), `payload` (JSONB), `occurred_at`. FK to `jobs`, `applications`.
- `careerloop.memory_events` — Importance-weighted, time-decayed memory store. `event_type`, `summary`, `payload` (JSONB), `importance` (INTEGER 1-10), `ttl_days` (INTEGER), `expires_at` (TIMESTAMPTZ).
- `careerloop.positioning_memory` — Per-track, per-company narrative memory. What framing angles worked or didn't. `generated_narrative`, `framing_strategy`, `successful_tone`, `rejected_tone`, `recruiter_positive_patterns` (JSONB), `converted` (0/1). FK to `strategic_tracks`.
- `careerloop.company_memory` — Per-user private company intel notes. `company_intelligence`, `compensation_analysis`, `hiring_urgency`, `recruiter_insights`, `glassdoor_synthesis`, `company_maturity`, `org_structure_patterns`, `startup_risk`, `work_culture_patterns`, `known_interview_loops`. UNIQUE(user_id, company_normalized).

**Lifecycle:**
- `outcome_events`: permanent (learning loop, never deleted)
- `memory_events`: importance-based TTL — importance 1-3 = 7d, 4-6 = 30d, 7-8 = 90d, 9-10 = permanent (no expires_at)
- `positioning_memory`: permanent per track per company
- `company_memory`: permanent per user per company

**Actual row counts:** outcome_events=0, memory_events=2, positioning_memory=0, company_memory=0

---

## 8. Conversation Memory

**Purpose:** Multi-transport chat session and message history. Persists the full conversation log across sessions and transports.

**Tables:**
- `careerloop.conversations` — Per-transport chat sessions. `transport` (cli/telegram/whatsapp/web), `external_chat_id`, `status` (active/archived). FK to `careerloop.users`.
- `careerloop.messages` — Per-conversation message log with routing metadata. `role` (user/assistant/system/tool), `content`, `action_type`, `action_confidence`, `artifact_context` (JSONB), `response_envelope` (JSONB), `tokens_used`. FK to `conversations`, `careerloop.users`.

**Lifecycle:** Conversations created on first message per transport. Messages append-only. LangGraph `add_messages` reducer manages in-memory conversation state during active session; messages table provides permanent cross-session persistence.

**Actual row counts:** conversations=2, messages=4

---

## Runtime State Memory

**Purpose:** Active runtime context — what the user is looking at right now and what the system is doing.

**Tables:**
- `careerloop.sessions` — Runtime state per user. `state` (UserJourneyState), `active_artifact_type`, `active_artifact_id`, `active_job_id`, `active_brief_id`, `active_pack_id`, `current_selection_index`, `temp_profile_data` (JSONB). One row per user (user_id PK, FK to careerloop.users).
- `careerloop.background_runs` — Async job tracking. `run_type` (scan/pack), `status` (QUEUED/RUNNING/COMPLETED/FAILED), `params` (JSONB), `stats` (JSONB), `error_code`, `error_summary`, `started_at`, `completed_at`. FK to `careerloop.users`.
- `careerloop.run_events` — Streaming observability events. `event_type`, `message`, `payload` (JSONB), `timestamp`. FK to `background_runs`. Ephemeral: deleted after 14 days, summary kept in `background_runs.stats`.
- `careerloop.event_timeline` — User-level event log. `event_type`, `reference_id`, `reference_type`, `details` (JSONB). Permanent per-user audit trail.
- `careerloop.strategic_tracks` — User's positioning tracks. `track_identity` (e.g., "AI PM", "Backend IC"), `positioning_strategy`, `resume_variant_id`, `outreach_style`, `success_metrics` (JSONB), `recruiter_response_patterns` (JSONB). FK to `careerloop.users`.

**Actual row counts:** sessions=13, background_runs=3, run_events=7, event_timeline=0, strategic_tracks=0

---

## Recall Hierarchy

### Level 1: Active Context Recall (deterministic, instant)
`careerloop.sessions.active_artifact_type`, `active_job_id`, `active_brief_id`, `active_pack_id`, `current_selection_index`

Used when user says "this", "that", "it", "1", "prepare this", "skip it".

### Level 2: Structured Relational Recall (DB query, <10ms)
User profile, preferences, recent jobs, pipeline status, applications, follow-ups, briefs.

Used for /status, /pipeline, /brief, "show my jobs", "what's my pipeline".

### Level 3: Event Timeline Recall (DB query, <50ms)
Scans, selections, applications, follow-ups, interviews, rejections — chronological via `event_timeline`, `background_runs`, `outcome_events`.

Used for "what happened last time", "show me my scan history".

### Level 4: Semantic Recall (future, vector search)
Interview vents, nuanced preferences, long career explanations, "I hate companies like X", user narrative patterns.

**Not implemented yet.** Documented as V4 architecture. `memory_events` table with importance-weighting is the structural foundation.

---

## Memory Propagation Flows

### A. Onboarding -> Identity + Preference + Evidence Memory
```
User input → OnboardingAgent → careerloop.users (name, email, linkedin_url, onboarding_status)
                             → careerloop.user_preferences (target_roles, target_cities, salary)
                             → careerloop.user_evidence (CV claims, work achievements)
```

### B. Scan -> Opportunity + User-Opportunity Memory
```
scan.mjs / start_scan → background_runs (QUEUED → RUNNING) →
  run_events (streaming MATCH/REJECT per candidate) →
  careerloop.job_candidates (raw discovery) →
  careerloop.jobs (fingerprint dedup, global, ON CONFLICT DO UPDATE) →
  careerloop.job_sources (per-source tracking) →
  careerloop.job_search_runs (audit trail with cache_hit_ratio) →
  careerloop.user_job_relationships (fit_score, match_status per user)
```

### C. Brief -> Artifact Memory + Active Context
```
DailyRunner shortlist →
  careerloop.daily_briefs (run_id, date_str, stats) →
  careerloop.daily_brief_items (item_index, job_id FK, fit_score, route_recommendation) →
  careerloop.sessions.active_artifact_type = "daily_brief"
  careerloop.sessions.active_brief_id = brief_id
```

### D. Job Selection -> Active Context + User-Opportunity Memory
```
User: "1" →
  careerloop.sessions.active_job_id = selected_job_id
  careerloop.sessions.active_artifact_type = "job_card"
  careerloop.user_job_relationships (match_status = "interested", user_seen_at = NOW())
```

### E. Prepare Pack -> Execution Memory + Evidence Memory
```
User: "prepare this" →
  careerloop.background_runs (pack_generation, QUEUED) →
  careerloop.application_packs (pack_id, resume_artifact_id, cover_note, recruiter_dm) →
  Reads careerloop.user_evidence for truth claims
```

### F. Apply -> Applications + Followups + Outcomes
```
User: "I applied" →
  careerloop.applications (status = "applied", applied_at) →
  careerloop.followups (due_at = NOW() + 5 days) →
  careerloop.user_job_relationships (match_status = "applied")
```

### G. Interview Debrief -> Learning Memory
```
User vents about interview →
  careerloop.outcome_events (event_type = "interview_scheduled") →
  careerloop.memory_events (interview feedback, importance = 8) →
  careerloop.positioning_memory (what narrative worked)
```

### H. Rejection / Ghosting -> Outcome Events + Strategy Adaptation
```
Application status = "rejected" →
  careerloop.outcome_events (event_type = "rejected", payload = {reason}) →
  careerloop.user_job_relationships (match_status = "rejected") →
  Future scoring adjusts: lower weight on similar companies/roles
```

### I. Chat Conversation -> Conversation Memory
```
Every message exchange →
  careerloop.conversations (one per transport per user) →
  careerloop.messages (role, content, action_type, artifact_context, tokens_used) →
  LangGraph in-memory state via add_messages reducer (active session only)
```

---

## Anti-Patterns (DO NOT)

| Anti-Pattern | Why |
|-------------|-----|
| Store all memory as raw chat text | Unstructured, unqueryable, expensive. Use messages table for persistence, memory_events for structured recall. |
| Put global job data inside user tables | Duplication, inconsistency, no cache reuse. Jobs are global; relationships are per-user. |
| Duplicate jobs per user | Breaks global dedup, wastes storage. Use `content_fingerprint` UNIQUE index. |
| Store scan logs as product truth | `run_events` are observability only — not canonical. `jobs` + `user_job_relationships` are truth. |
| Use sessions as long-term memory | Sessions are runtime state — not audit history. Expire stale context; persist facts to domain tables. |
| Use embeddings for simple relational facts | SQL queries are faster, cheaper, more reliable. Embeddings are for V4 semantic recall only. |
| Let Resume Council invent unsupported claims | Every claim must trace to `user_evidence` with confidence > 0.5. |
| Delete jobs because one user skipped them | Jobs are global — other users may want them. Use `status = 'expired'` for TTL cleanup only. |
| Make daily briefs from transient scan objects | Brief items must reference `careerloop.jobs.job_id` via FK. |
| Use local disk as memory | `.last_brief_date`, `output/*.md`, `ledger.json` are cache/export only. All truth in PostgreSQL. |
| Query user-scoped tables without user_id filter | Cross-user data leak. Every query that touches user data must filter by `user_id`. |
| Store fit scores in the jobs table | Fit scores are per-user. A 73/100 for Siddharth might be a 45/100 for Varsha. Store in `user_job_relationships.fit_score`. |
| Create per-user company rows in companies table | Company profile is global. Per-user notes go in `company_memory` with UNIQUE(user_id, company_normalized). |
| Reference `public.users` in new FKs | All FKs must reference `careerloop.users(id)` — the canonical identity spine since V3. |
| Skip the repository layer | All DB access through `repository_v2.py`. No raw SQL in session code, chat code, or tool handlers. |

---

## Schema Summary

| Layer | Table | Scope | PK Type | Row Count |
|-------|-------|-------|---------|-----------|
| Identity | `careerloop.users` | User | UUID | 17 |
| Runtime | `careerloop.sessions` | User | UUID (user_id) | 13 |
| Runtime | `careerloop.background_runs` | User | TEXT (run_id) | 3 |
| Runtime | `careerloop.run_events` | Run | TEXT (event_id) | 7 |
| Runtime | `careerloop.event_timeline` | User | UUID | 0 |
| Runtime | `careerloop.strategic_tracks` | User | UUID | 0 |
| Preference | `careerloop.user_preferences` | User | UUID (user_id) | 0 |
| Evidence | `careerloop.user_evidence` | User | UUID | 0 |
| Opportunity | `careerloop.jobs` | Global | UUID (job_id) | 3 |
| Opportunity | `careerloop.companies` | Global | UUID | 0 |
| Opportunity | `careerloop.job_sources` | Global | UUID | 0 |
| Opportunity | `careerloop.job_candidates` | Run | UUID | 0 |
| Opportunity | `careerloop.job_search_runs` | User | UUID | 0 |
| User-Opportunity | `careerloop.user_job_relationships` | User | Composite (user_id, job_id) | 6 |
| Execution | `careerloop.application_packs` | User | UUID | 0 |
| Execution | `careerloop.applications` | User | UUID | 0 |
| Execution | `careerloop.application_ledger` | User | UUID | 0 |
| Execution | `careerloop.outreach_messages` | User | UUID | 0 |
| Execution | `careerloop.followups` | User | UUID | 0 |
| Execution | `careerloop.people_to_reach` | Global | UUID | 0 |
| Execution | `careerloop.recruiter_contacts` | Global | UUID | 0 |
| Learning | `careerloop.outcome_events` | User | UUID | 0 |
| Learning | `careerloop.memory_events` | User | UUID | 2 |
| Learning | `careerloop.positioning_memory` | User | UUID | 0 |
| Learning | `careerloop.company_memory` | User | UUID | 0 |
| Conversation | `careerloop.conversations` | User | UUID | 2 |
| Conversation | `careerloop.messages` | User | UUID | 4 |
| Artifact | `careerloop.daily_briefs` | User | UUID | 1 |
| Artifact | `careerloop.daily_brief_items` | User | UUID | 1 |

**Total:** 29 tables, 59 rows (3 global, 56 user-scoped)

---

## Foreign Key Graph

```
careerloop.users (id UUID PK)  ←── CANONICAL IDENTITY SPINE (V3)
    │
    ├── careerloop.sessions (user_id FK)
    ├── careerloop.user_preferences (user_id PK+FK)
    ├── careerloop.user_evidence (user_id FK)
    ├── careerloop.strategic_tracks (user_id FK)
    │       └── careerloop.positioning_memory (track_id FK)
    ├── careerloop.company_memory (user_id FK, UNIQUE user_id+company_normalized)
    ├── careerloop.background_runs (user_id FK)
    │       ├── careerloop.run_events (run_id FK)
    │       ├── careerloop.job_candidates (run_id FK)
    │       ├── careerloop.job_search_runs (run_id TEXT)
    │       └── careerloop.daily_briefs (run_id, user_id FK)
    │               └── careerloop.daily_brief_items (brief_id FK, job_id FK → jobs)
    ├── careerloop.user_job_relationships (user_id FK, job_id FK → jobs)
    ├── careerloop.applications (user_id FK, job_id FK → jobs)
    │       ├── careerloop.followups (application_id FK)
    │       └── careerloop.outcome_events (application_id FK, job_id FK)
    ├── careerloop.application_packs (user_id FK, job_id FK → jobs, run_id FK)
    ├── careerloop.outreach_messages (user_id FK, person_id FK, job_id FK)
    ├── careerloop.application_ledger (user_id FK, track_id FK → strategic_tracks)
    ├── careerloop.event_timeline (user_id FK)
    ├── careerloop.outcome_events (user_id FK)
    ├── careerloop.memory_events (user_id FK)
    ├── careerloop.conversations (user_id FK)
    │       └── careerloop.messages (conversation_id FK, user_id FK)
    └── careerloop.followups (user_id FK)

careerloop.companies (id UUID PK)  ←── GLOBAL
    ├── careerloop.jobs (company_id FK)
    │       ├── careerloop.job_sources (job_id FK)
    │       ├── careerloop.user_job_relationships (job_id FK)
    │       ├── careerloop.applications (job_id FK)
    │       ├── careerloop.application_packs (job_id FK)
    │       ├── careerloop.outreach_messages (job_id FK)
    │       └── careerloop.outcome_events (job_id FK)
    ├── careerloop.people_to_reach (company_id FK)
    │       └── careerloop.outreach_messages (person_id FK)
    └── careerloop.recruiter_contacts (company_id FK)
```

20 FK constraints chain to `careerloop.users(id)`. 6 tables reference `careerloop.companies(id)`. 7 tables reference `careerloop.jobs(job_id)`.

---

## ID Standard

| Aspect | Rule |
|--------|------|
| New table PKs | `UUID DEFAULT gen_random_uuid()` |
| Foreign keys to users | `UUID NOT NULL REFERENCES careerloop.users(id) ON DELETE CASCADE` |
| Foreign keys to jobs | `UUID REFERENCES careerloop.jobs(job_id)` |
| Foreign keys to companies | `UUID REFERENCES careerloop.companies(id)` |
| Legacy TEXT columns | `background_runs.run_id` (TEXT PK), `run_events.event_id` (TEXT PK), `jobs.id` (TEXT, legacy from V1) -- UUID bridge columns added in V3 (`run_id_uuid`, `event_id_uuid`). V3.1 will backfill and swap PK constraints. |
| V1→V2→V3 path | `jobs.id` (TEXT v1) coexists with `jobs.job_id` (UUID v2). V3 added `careerloop.users` as identity spine. V3.1 will enforce all TEXT→UUID constraints. |

---

## Expiration and Archival Policy

| Data | TTL | Action |
|------|-----|--------|
| `run_events` | 14 days | Hard delete. Keep summary in `background_runs.stats`. |
| `job_candidates` | 30 days | Archive/delete. Raw candidates are staging only. |
| `jobs` (unseen) | 60 days | Mark `status = 'expired'`. Keep row for dedup reference. |
| `jobs` (dead link) | Immediate | Mark `status = 'expired'` when apply_url returns 404. |
| `outreach_messages` | 90 days after last update | Archive. Keep templates from `status = 'replied'` messages. |
| `followups` | 90 days after completion | Archive. |
| `memory_events` | Configurable by importance | importance 1-3 = 7d, 4-6 = 30d, 7-8 = 90d, 9-10 = permanent. |
| `conversations` + `messages` | Permanent (active), 90d (archived) | Archive conversations with `status = 'archived'`. |
| `applications` | Permanent | Never delete. Core audit trail. |
| `outcome_events` | Permanent | Learning loop. Never delete. |
| `user_evidence` | Permanent | Truth claims. Never delete. |
| `user_preferences` | Permanent | One row per user. Never delete. |
| `daily_briefs` + items | Permanent | Historical brief archive. Never delete. |
| `sessions` | Permanent | One row per user. Never delete. |
| `companies` | Permanent | Global registry. Never delete. |

---

## Filesystem Memory (Legacy, Being Phased Out)

CareerLoop originally relied heavily on filesystem state. The architecture audit (2026-05-24) identified these as critical persistence bugs. Migration status:

| File | Status | Replacement |
|------|--------|-------------|
| `careerloop/.last_brief_date` | Deprecated, still created | `careerloop.daily_briefs.date_str` |
| `output/daily_briefs/*.md` | Deprecated, still created | `careerloop.daily_briefs` + `daily_brief_items` |
| `careerloop/ledger.json` | Legacy, still active | `careerloop.application_ledger` + `careerloop.applications` |
| `data/pipeline.md` | Legacy, still read | `careerloop.job_candidates` |
| `data/scan-history.tsv` | Legacy | `careerloop.jobs.content_fingerprint` UNIQUE index |
| `output/council/*/` | Mixed. Packs on filesystem. | `careerloop.application_packs` (DB) + filesystem for PDF artifacts |

**Rule:** All state decisions (what happened, what was scored, what was applied to) MUST live in PostgreSQL. Filesystem is cache/export only.

---

## Data Access Rules

1. **All DB access through `careerloop/memory/repository_v2.py`** (1040 lines, 7 classes, 32 methods). No raw SQL in session code, chat code, or tool handlers.
2. **Write-path functions** use `ON CONFLICT ... DO UPDATE` for idempotency.
3. **Read-path functions** return `Optional[dict]` or `List[dict]` — never raw cursors.
4. **All SQL is parameterized** with `%s` placeholders and RealDictCursor.
5. **RLS enforces per-user isolation** on user-scoped tables. Global tables allow `SELECT` for any authenticated user; writes bypass RLS (service role).

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

---

## Current Status (2026-05-25)

### Implemented
- 29 tables across 7 memory layers + conversation + runtime state
- Identity spine: `careerloop.users` with 16 FK constraints (V3 migration complete)
- Global job dedup via `content_fingerprint` UNIQUE index working
- User-opportunity bridge via `user_job_relationships` composite PK
- Daily brief pipeline: `jobs → user_job_relationships → daily_briefs → daily_brief_items`
- Active Context recall working in sessions (active_job_id, active_brief_id, active_pack_id)
- Scan, brief, selection, pack flows writing to correct memory tables
- Conversation persistence via `conversations` + `messages` tables
- Memory events store with importance-weighted TTL foundation
- `repository_v2.py` centralized data access layer (7 classes)

### Not Yet Implemented
- Semantic recall layer (V4 — vector search on memory_events, messages)
- Evidence extraction pipeline from chat/CV (user_evidence table exists, extraction logic not built)
- Learning loop from outcome_events -> scoring adaptation (tables exist, feedback loop not wired)
- Memory_events TTL expiration cron (expires_at column exists, no cleanup job)
- Cache-hit full blocking of external scan (job_search_runs.cache_hit_ratio tracked, not yet used as gate)
- RLS policies on all tables (10 tables with RLS, 17 still missing RLS+policies)

### Remaining Blockers
- `india_fit_engine.py` queries bare table names (company_memory, companies) without `careerloop.` schema prefix — P1
- 29 TEXT ID columns need UUID migration — P2 (V3 added UUID bridge columns; V3.1 hardening needed for constraint swap)
- RLS policies on 17 tables — P2
- Full transport deployment (Telegram/WhatsApp) — P0
- `public.users` legacy columns (location_city, linkedin_url, notice_period_days, current_ctc_lakhs, etc.) → migrate to `careerloop.users` — P2
