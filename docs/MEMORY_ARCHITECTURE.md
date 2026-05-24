# CareerLoop Memory Architecture

> How CareerLoop remembers everything: user profile, preferences, past applications, interview outcomes, recruiter interactions, company intel, and strategic positioning. A 6-layer persistent memory model.

---

## 6-Layer Model

```
Layer 1: Profile Memory       (permanent, user-scoped, one row per user)
Layer 2: Positioning Memory   (per-track, user-scoped, multi-row)
Layer 3: Recruiter Memory     (global, company-scoped, reusable)
Layer 4: Interview Memory     (per-application, user-scoped, learning loop)
Layer 5: Company Memory       (global, company-scoped with user-private notes)
Layer 6: Strategic Memory     (user-scoped, time-decayed, event-driven)
```

---

## Layer 1: Profile Memory (Permanent, User-Scoped)

**Purpose:** Who the user is, what they want, and what's true about them.

### Tables

| Table | Contents | Key Columns |
|-------|----------|-------------|
| `public.users` | Identity + base profile | `id`, `email`, `full_name`, `master_cv_markdown`, `parsed_cv_data`, `employment_state`, `compensation_floor_lakhs`, `compensation_target_lakhs`, `remote_pref`, `search_posture` |
| `careerloop.user_preferences` | Structured targeting preferences | `target_roles` (JSONB), `target_cities` (JSONB), `salary_min`, `salary_max`, `notice_period`, `work_mode`, `avoid_companies` (JSONB), `avoid_role_types` (JSONB), `aggressiveness` |
| `careerloop.user_evidence` | Truth-grounded claims | `evidence_type` (project/work_achievement/skill/education/certification/link), `title`, `description`, `proof_url`, `source` (resume/linkedin/manual/chat), `confidence` |

### Lifecycle

- **Created:** User signup (Supabase Auth) + onboarding flow
- **Updated:** Whenever the user provides new info, uploads CV, or changes preferences in chat
- **Evicted:** Never. Profile is permanent.
- **Recovery:** If `careerloop.sessions` row is missing, `session_store.py` loads profile from `public.users` + `careerloop.user_preferences` to reconstruct state.

### Usage

- Used by every LLM call that needs user context (scoring, positioning, brief generation, outreach)
- `master_cv_markdown` is the canonical CV source. `parsed_cv_data` is the structured JSONB extraction.
- `user_evidence` feeds Truth Guard for claim validation during resume generation.

---

## Layer 2: Positioning Memory (Per-Track, User-Scoped)

**Purpose:** How the user positions themselves for different role tracks, and what has worked.

### Tables

| Table | Contents | Key Columns |
|-------|----------|-------------|
| `careerloop.strategic_tracks` | User's positioning tracks | `track_identity` (e.g., "AI PM", "Backend IC"), `positioning_strategy`, `resume_variant_id`, `outreach_style`, `success_metrics` (JSONB), `recruiter_response_patterns` (JSONB) |
| `careerloop.positioning_memory` | Per-track, per-company narrative memory | `company_normalized`, `generated_narrative`, `framing_strategy`, `successful_tone`, `rejected_tone`, `recruiter_positive_patterns` (JSONB), `converted` (0/1) |

### Lifecycle

- **Created:** When user defines a new track during onboarding or chat
- **Updated:** After each application, interview, or outcome event for that track
- **Evicted:** Only on explicit user deletion

### Usage

- S6 (Positioning Engine) reads `positioning_memory` to determine what narrative angle worked for similar companies
- After an interview, `interview-playbook` skill writes back what framing resonated
- `converted` flag marks narratives that led to offers — these get weighted higher in future positioning

---

## Layer 3: Recruiter Memory (Global, Company-Scoped)

**Purpose:** Who to reach at each company, and what messages were sent.

### Tables

| Table | Contents | Key Columns |
|-------|----------|-------------|
| `careerloop.people_to_reach` | Recruiters, hiring managers, potential referrers | `name`, `title`, `linkedin_url`, `source`, `relevance_reason`, `confidence`, `company_id` (FK) |
| `careerloop.outreach_messages` | Drafted and sent messages | `message_type` (recruiter_dm/referral_ask/followup/thank_you), `body`, `status` (drafted/sent/replied/ghosted), `person_id`, `job_id` |

### Lifecycle

- **Created:** Company intelligence phase discovers people; user drafts outreach
- **Updated:** When messages are sent, replied to, or ghosted
- **Evicted:** Outreach messages archived after 90 days. People records are permanent.

### Usage

- Company intel engine enriches company profiles with known recruiters
- Outreach message generation uses past successful templates (by `message_type` and `status = 'replied'`)
- `followups` table schedules ping messages based on `outreach_messages.status`

---

## Layer 4: Interview Memory (Per-Application, User-Scoped)

**Purpose:** What happened with each application — the full interview and outcome history.

### Tables

| Table | Contents | Key Columns |
|-------|----------|-------------|
| `careerloop.applications` | Every application action | `status` (prepared/applied/followup_due/recruiter_contacted/referral_requested/interview_scheduled/rejected/offer), `applied_at`, `apply_channel`, `notes` |
| `careerloop.outcome_events` | Learning loop events | `event_type` (reply_received/interview_scheduled/rejected/ghosted/offer_received/followup_worked/recruiter_replied), `payload` (JSONB), `occurred_at` |

### Lifecycle

- **Created:** `applications` when user applies; `outcome_events` when status changes
- **Updated:** Status transitions, new outcome events
- **Evicted:** Never. Both are permanent for learning loop.

### Usage

- `careerloop.application_ledger` (legacy, mirrors `ledger.json`) is also in this layer but being phased out in favor of `applications` + `outcome_events`
- Pattern analysis: after 2+ interviews, `interview-playbook` extracts patterns from `outcome_events` (what questions recur, what objections surface, what worked)
- `followups` table schedules ping messages based on application status and `outcome_events`

---

## Layer 5: Company Memory (Global with User-Private Notes)

**Purpose:** Everything CareerLoop knows about a company — shared across users, with per-user private additions.

### Tables

| Table | Contents | Key Columns |
|-------|----------|-------------|
| `careerloop.companies` | Global company profile | `name`, `normalized_name`, `domain`, `website`, `linkedin_url`, `industry`, `size`, `funding_stage`, `ats_provider`, `career_page_url`, `crawl_status` |
| `careerloop.company_memory` | Per-user private intel notes | `company_normalized`, `company_intelligence`, `compensation_analysis`, `hiring_urgency`, `recruiter_insights`, `glassdoor_synthesis`, `company_maturity`, `org_structure_patterns`, `startup_risk`, `work_culture_patterns`, `known_interview_loops` |

### Lifecycle

- **Created:** `companies` on first discovery. `company_memory` on first company intel fetch for a user.
- **Updated:** `companies` on re-crawl. `company_memory` on re-fetch or user-added notes.
- **Evicted:** `companies` never. `company_memory` never (permanent user notes).

### Usage

- S3 (Company Intelligence) writes to `company_memory` with structured intel: D1-D5 vectors, LinkedIn signals, Glassdoor synthesis
- `careerloop/company_intel.py` is the MECE research engine; `repository_v2.py` is the persistence layer
- `companies` table stores what's universally true; `company_memory` stores per-user synthesis and personal notes
- UNIQUE(user_id, company_normalized) ensures one note set per user per company

---

## Layer 6: Strategic Memory (User-Scoped, Time-Decayed)

**Purpose:** Ephemeral memory of what the user discussed, searched for, and engaged with recently. Drives conversational context.

### Tables

| Table | Contents | Key Columns |
|-------|----------|-------------|
| `careerloop.sessions` | Active runtime context | `state` (journey state), `active_artifact_type`, `active_artifact_id`, `active_job_id`, `active_brief_id`, `active_pack_id`, `current_selection_index`, `temp_profile_data` (JSONB) |
| `careerloop.event_timeline` | User-level event log | `event_type`, `reference_id`, `reference_type`, `details` (JSONB) |
| `careerloop.background_runs` | Async run tracking | `run_type` (scan/pack), `status` (QUEUED/RUNNING/COMPLETED/FAILED), `stats` (JSONB), `params` (JSONB) |
| `careerloop.run_events` | Live streaming events | `event_type`, `message`, `payload` (JSONB), `timestamp` |
| `backup_public_schema.conversations` | (Legacy/Emote) Chat sessions | `title`, `turn_count`, `last_activity` |
| `backup_public_schema.messages` | (Legacy/Emote) Chat messages | `user_message`, `shanthi_response`, `timestamp` |

### Lifecycle

- **Created:** Sessions on first chat. Background runs on scan/pack trigger. Run events during async execution.
- **Updated:** Sessions on every state change. Background runs on status transitions.
- **Evicted:** `run_events` deleted after 14 days. Conversations and messages: keep 90 days, then archive. Outcome events: permanent.

### Usage

- ActionResolver reads `sessions.active_context` (job_id, brief_id, pack_id) to resolve pronouns ("this one", "the second one", "prepare it")
- CLI streaming reads `run_events` to render live scan progress (MATCH/REJECT per job)
- Conversation history is managed by LangGraph `add_messages` reducer (in-memory during session) + persisted via `PostgresSaver` checkpointer

---

## Recall Hierarchy

When the LLM needs context about the user, it follows this hierarchy (ordered by recency and relevance):

```
1. Active Context (sessions)
   → What is the user looking at RIGHT NOW?
   → active_job_id, active_brief_id, active_pack_id, current_selection_index

2. Recent Messages (last 10 in conversation)
   → What did we just discuss?
   → LangGraph state messages array

3. Recent Memory Events (event_timeline, last 7 days)
   → What happened recently?
   → Status changes, briefs viewed, packs generated

4. Active Job Relationships (user_job_relationships, last 30 days)
   → What jobs did they engage with?
   → match_status = matched/interested/saved, ordered by updated_at

5. Applications + Outcomes
   → What happened with past applications?
   → Status, interview_stage, outcome_events

6. Profile + Preferences
   → Who is this person?
   → master_cv_markdown, user_preferences, user_evidence

7. Positioning Memory
   → What positioning worked before?
   → By track, by company type

8. Company Memory
   → What do we know about this company?
   → Global companies + per-user company_memory notes
```

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
| Conversations + Messages | 90 days | Archive to long-term storage. |
| `applications` | Permanent | Never delete. Core audit trail. |
| `outcome_events` | Permanent | Learning loop. Never delete. |
| `user_evidence` | Permanent | Truth claims. Never delete. |
| `user_preferences` | Permanent | One row per user. Never delete. |
| `daily_briefs` + items | Permanent | Historical brief archive. Never delete. |

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
