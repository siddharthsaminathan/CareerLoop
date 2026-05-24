# CareerLoop API Architecture

> Thin FastAPI product layer. Core logic in services/runtime/repos. Not another brain.

## Design Principle

```
router → service → repository/runtime → Supabase (careerloop.*)
```

Never:
- router → raw SQL everywhere
- router → Resume Council directly
- router → DailyRunner directly
- router → giant orchestration file

---

## Project Structure

```text
careerloop_api/
  main.py
  core/
    config.py          # DB_SCHEMA=careerloop, DATABASE_URL, DEEPSEEK_API_KEY
    security.py        # Supabase JWT validation
    errors.py          # CareerLoopError, error handler
    logging.py         # Reuse careerloop/logging_config.py
  deps/
    auth.py            # get_current_user → careerloop.users
    db.py              # get_db → psycopg2 connection pool
    user.py            # get_user_preferences, get_active_context
  routers/
    auth.py            # /auth/login
    users.py           # /me, /me/profile, /me/preferences, /me/resume
    chat.py            # /chat/message, /chat/sessions/current, /chat/messages
    scans.py           # /scans, /scans/{run_id}, /scans/{run_id}/events, /scans/latest
    briefs.py          # /briefs/latest, /briefs/{brief_id}, /briefs/{brief_id}/items
    jobs.py            # /jobs, /jobs/{job_id}, /jobs/{job_id}/save, /jobs/{job_id}/skip
    applications.py    # /pipeline, /applications, /applications/{id}
    packs.py           # /jobs/{job_id}/packs, /packs/{pack_id}
    pipeline.py        # /pipeline (status, stats)
    companies.py       # /companies/{company_id}, /companies/{company_id}/research
    memory.py          # /memory/profile, /memory/events, /memory/outcomes
    webhooks.py        # /webhooks/telegram, /webhooks/whatsapp, /webhooks/gmail
  schemas/
    common.py          # ResponseEnvelope, ActionRequest, Pagination
    users.py           # UserProfile, UserPreferences, ResumeUpload
    chat.py            # ChatMessage, ChatResponse
    scans.py           # ScanRequest, ScanStatus, RunEvent
    briefs.py          # BriefResponse, BriefItem, SelectItemRequest
    jobs.py            # JobCard, JobDetail, CompanyInfo
    applications.py    # ApplicationCreate, PipelineStatus
    packs.py           # PackCreate, PackStatus, PackRegenerate
    pipeline.py        # PipelineStats, PipelineFilter
    companies.py       # CompanyProfile, CompanyResearch
    memory.py          # MemoryEvent, OutcomeEvent
  services/
    chat_service.py    # Wraps supervisor_graph: ActionResolver → ToolRegistry → ResponseEnvelope
    scan_service.py    # Wraps ToolRegistry.start_scan() + polls run_events
    brief_service.py   # Wraps BriefRepository
    job_service.py     # Wraps JobRepository + UserJobRepository
    application_service.py  # Wraps ApplicationRepository
    pack_service.py    # Wraps ApplicationRepository.create_pack
    company_service.py # Wraps companies + company_memory queries
    memory_service.py  # Wraps EvidenceRepository + memory_events
  repositories/
    users_repo.py      # careerloop.users CRUD
    sessions_repo.py   # careerloop.sessions CRUD
    jobs_repo.py       # careerloop.jobs upsert + search (reuses repository_v2)
    briefs_repo.py     # careerloop.daily_briefs + daily_brief_items
    runs_repo.py       # careerloop.background_runs + run_events
    applications_repo.py  # careerloop.applications + application_packs
    memory_repo.py     # careerloop.memory_events + outcome_events
  workers/
    scan_worker.py     # Background scan via DailyRunner
    pack_worker.py     # Background pack generation via Resume Council
    company_worker.py  # Background company research
  events/
    stream.py          # SSE/WebSocket for live run_events streaming
    run_events.py      # Poll careerloop.run_events by run_id
```

---

## API Domains

### Auth / User

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Supabase email/password → JWT |
| GET | `/me` | Current user from `careerloop.users` |
| PATCH | `/me/profile` | Update name, linkedin_url, phone |
| GET | `/me/preferences` | `careerloop.user_preferences` |
| PATCH | `/me/preferences` | Update target_roles, target_cities, salary, etc. |
| POST | `/me/resume` | Upload CV → extracts to `careerloop.user_evidence` |

### Chat Runtime

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat/message` | Send message → ActionResolver → ToolRegistry → response |
| GET | `/chat/sessions/current` | Active session from `careerloop.sessions` |
| GET | `/chat/messages` | Messages for conversation_id from `careerloop.messages` |

**POST /chat/message payload:**
```json
{
  "text": "find me new jobs",
  "transport": "web",
  "conversation_id": "uuid"
}
```

**Response:**
```json
{
  "message": "Scanning now...",
  "response_type": "text",
  "cards": [],
  "actions": [],
  "active_context": {
    "active_brief_id": null,
    "active_job_id": null
  }
}
```

### Scans

| Method | Path | Description |
|--------|------|-------------|
| POST | `/scans` | Start new scan (creates background_run, returns run_id) |
| GET | `/scans/{run_id}` | Scan status from `careerloop.background_runs` |
| GET | `/scans/{run_id}/events` | Stream `careerloop.run_events` for this scan |
| GET | `/scans/latest` | Latest scan for current user |

**POST /scans payload:**
```json
{
  "force": false,
  "mode": "quality",
  "target_roles": ["AI Product Engineer"],
  "target_cities": ["Chennai", "Bangalore"]
}
```

### Briefs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/briefs/latest` | Latest brief from `careerloop.daily_briefs` |
| GET | `/briefs/{brief_id}` | Brief detail |
| GET | `/briefs/{brief_id}/items` | Brief items from `careerloop.daily_brief_items` |
| POST | `/briefs/{brief_id}/items/{item_index}/select` | Select item → sets active_job_id in sessions |

### Jobs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/jobs` | List jobs (paginated, filtered) |
| GET | `/jobs/{job_id}` | Job detail from `careerloop.jobs` + `careerloop.user_job_relationships` |
| POST | `/jobs/{job_id}/save` | Set match_status=saved |
| POST | `/jobs/{job_id}/skip` | Set match_status=skipped |
| GET | `/jobs/{job_id}/company` | Company from `careerloop.companies` |
| GET | `/jobs/{job_id}/people` | Recruiters from `careerloop.recruiter_contacts` |

### Application Packs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/jobs/{job_id}/packs` | Create pack (creates background_run for pack_generation) |
| GET | `/packs/{pack_id}` | Pack status + contents |
| PATCH | `/packs/{pack_id}` | Update cover_note, recruiter_dm, referral_dm |
| POST | `/packs/{pack_id}/regenerate-section` | Re-run council for specific section |
| POST | `/packs/{pack_id}/approve` | Approve pack → mark ready for application |

### Applications / Pipeline

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pipeline` | All applications from `careerloop.applications` |
| POST | `/applications` | Create application |
| PATCH | `/applications/{application_id}` | Update status/notes |
| POST | `/applications/{application_id}/mark-applied` | Set status=applied, applied_at=NOW() |
| POST | `/applications/{application_id}/followups` | Create `careerloop.followups` row |

### Companies

| Method | Path | Description |
|--------|------|-------------|
| GET | `/companies/{company_id}` | Company profile |
| POST | `/companies/{company_id}/research` | Trigger deep research (creates background_run) |
| GET | `/companies/{company_id}/memory` | `careerloop.company_memory` |

### Memory

| Method | Path | Description |
|--------|------|-------------|
| GET | `/memory/profile` | `careerloop.user_evidence` + `careerloop.user_preferences` |
| GET | `/memory/events` | `careerloop.memory_events` (paginated) |
| POST | `/memory/events` | Create memory_event |
| GET | `/memory/outcomes` | `careerloop.outcome_events` |

### Webhooks

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhooks/telegram` | Telegram bot webhook |
| POST | `/webhooks/whatsapp` | WhatsApp Cloud API webhook |
| POST | `/webhooks/gmail` | Gmail push notification |
| POST | `/webhooks/calendar` | Google Calendar push notification |

---

## MVP Build Order

```
1. /me + /me/preferences
2. /chat/message
3. /scans + /scans/{run_id}/events
4. /briefs/latest + select item
5. /jobs/{job_id}
6. /jobs/{job_id}/packs
7. /pipeline
```

Enough for frontend + Telegram/WhatsApp webhook integrations later.

---

## Key Rules

- **Thin routers.** Routers parse HTTP, validate schemas, call services, return JSON. No business logic.
- **Services own logic.** Services call ToolRegistry, repositories, DailyRunner. One service per domain.
- **Repositories own SQL.** All DB access through repository classes. No raw SQL in routers or services.
- **careerloop schema only.** All tables in `careerloop.*`. `public.users` only for Supabase auth JWT validation.
- **ResponseEnvelope everywhere.** Every endpoint returns the same envelope shape for consistency.
- **Streaming via Server-Sent Events.** `/scans/{run_id}/events` returns SSE stream of `careerloop.run_events`.
- **Webhooks are thin adapters.** Parse platform-specific payload → normalize to UserEvent → push through supervisor_graph.
