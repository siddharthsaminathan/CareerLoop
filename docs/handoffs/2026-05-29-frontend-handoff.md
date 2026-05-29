# CareerLoop — Frontend Engineering Handoff
**Date:** 2026-05-29  
**Author:** Product Lead (Claude Code)  
**Scope:** Backend audit → minimal frontend build spec for Web v1

---

## Product Lead — Session Start

```
[product-lead] Last session: Sprint 5 — Phase E ontology gate, board query enrichment, Naukri API-first, SQLite local dev.
Aligned to: PRD §5 (Discovery Engine). Status: Discovery 85% → 88%.
Watch: API layer (careerloop_api/) is fully specced in docs but NOT implemented — zero FastAPI routes exist for the frontend yet.
```

---

## 1. Backend State — What Is and Is Not Built

### What exists today

| Layer | Status | Files |
|-------|--------|-------|
| Core pipeline (scan → score → brief) | ✅ Working | `careerloop/daily_runner.py`, `careerloop/on_demand.py` |
| DB schema (Supabase + SQLite) | ✅ Live | `careerloop/memory/supabase_migration_v2.sql` |
| Data repository | ✅ Working | `careerloop/memory/repository_v2.py` |
| Daily brief generation | ✅ Working (90%) | `careerloop/daily_runner.py` |
| Chat runtime (LangGraph supervisor) | ✅ Working | `careerloop/session/supervisor_graph.py` |
| Tool registry (show_brief, select_item) | ✅ Working | `careerloop/session/tool_registry.py` |
| Telegram webhook | ✅ Live | `careerloop/transport/webhook_server.py` |
| **REST API for frontend** | ❌ NOT BUILT | Specced at `docs/engineering/API_ARCHITECTURE.md` |

### The only live HTTP endpoints (right now)

```
POST /telegram/webhook   — Telegram bot receiver
GET  /health             — liveness check
```

That's it. The entire `careerloop_api/` package described in `docs/engineering/API_ARCHITECTURE.md` **does not exist yet** in the codebase. Zero routers, zero FastAPI app for web.

---

## 2. API Architecture Plan (from `docs/engineering/API_ARCHITECTURE.md`)

The design is already locked. Stack:

```
router → service → repository/runtime → Supabase (careerloop.*)
```

**Project structure to create:**

```
careerloop_api/
  main.py
  core/
    config.py          # DB_SCHEMA=careerloop, DATABASE_URL, DEEPSEEK_API_KEY
    security.py        # Supabase JWT validation
    errors.py          # CareerLoopError + handler
    logging.py         # reuse careerloop/logging_config.py
  deps/
    auth.py            # get_current_user → careerloop.users
    db.py              # get_db → psycopg2 connection pool
    user.py            # get_user_preferences, get_active_context
  routers/
    auth.py            # /auth/login
    users.py           # /me, /me/profile, /me/preferences, /me/resume
    chat.py            # /chat/message, /chat/sessions/current, /chat/messages
    scans.py           # /scans, /scans/{run_id}, /scans/{run_id}/events (SSE)
    briefs.py          # /briefs/latest, /briefs/{brief_id}/items, select
    jobs.py            # /jobs/{job_id}, save, skip
    applications.py    # /pipeline, /applications
    packs.py           # /jobs/{job_id}/packs, /packs/{pack_id}
    companies.py       # /companies/{company_id}
    memory.py          # /memory/profile
    webhooks.py        # /webhooks/telegram, /webhooks/whatsapp
  schemas/             # Pydantic models (one per domain)
  services/            # Business logic (wraps ToolRegistry + repos)
  repositories/        # DB access (reuse repository_v2 methods)
  workers/             # Background: scan_worker, pack_worker
  events/
    stream.py          # SSE for run_events
```

---

## 3. MVP API Endpoints — Build in This Order

These are the **7 endpoints** needed to power the first frontend. Everything else is deferred.

### Phase 1 — Identity (build first, blocks everything)

```
POST   /auth/login
       Body: { email, password }
       Returns: { access_token, user_id, expires_in }
       Source: Supabase auth

GET    /me
       Returns: { id, name, email, linkedin_url, onboarded_at }
       Source: careerloop.users

GET    /me/preferences
       Returns: { target_roles[], target_cities[], salary_min, salary_max, work_mode }
       Source: careerloop.user_preferences
```

### Phase 2 — Daily Brief / TAL (the core product UI)

```
GET    /briefs/latest
       Returns: BriefResponse {
         brief_id, date_str, summary,
         items: [BriefItem...]
       }
       Source: careerloop.daily_briefs + careerloop.daily_brief_items

POST   /briefs/{brief_id}/items/{item_index}/select
       Body: {} (empty)
       Returns: { job_id, active_artifact_type: "job_card" }
       Action: Sets active_job_id in careerloop.sessions

GET    /jobs/{job_id}
       Returns: JobDetail {
         id, title, company_name, location, work_mode,
         salary_min, salary_max, salary_currency,
         fit_score, recommendation_reason, risk_summary,
         route_recommendation, source_url, apply_url,
         status (active/expired), verified_active
       }
       Source: careerloop.jobs + careerloop.user_job_relationships
```

### Phase 3 — Chat (connects frontend to LangGraph)

```
POST   /chat/message
       Body: { text, conversation_id? }
       Returns: ResponseEnvelope {
         message: string,
         response_type: "text" | "list" | "card",
         cards: [],
         actions: [],
         active_context: { active_brief_id, active_job_id }
       }
       Source: supervisor_graph.py (already works, just needs HTTP wrapper)
```

### Standard Response Envelope (all endpoints use this)

```json
{
  "ok": true,
  "data": { ... },
  "error": null,
  "meta": {
    "request_id": "uuid",
    "timestamp": "2026-05-29T06:00:00Z"
  }
}
```

---

## 4. BriefItem Schema (the TAL job card)

This is the data model for each card in the TAL list. Source: `careerloop.daily_brief_items` joined with `careerloop.jobs`.

```typescript
interface BriefItem {
  item_index: number;          // ordinal (1, 2, 3…)
  job_id: string;              // FK to careerloop.jobs
  title: string;               // "Applied AI Engineer"
  company: string;             // "CheQ"
  location: string;            // "Bengaluru"
  fit_score: number;           // 0–100 (e.g. 78.0)
  recommendation_reason: string; // "Strong match on LLM stack and fintech domain"
  risk_summary: string;        // "Early-stage startup, Series A"
  route_recommendation: string; // "APPLY" | "RECRUITER" | "REFERRAL" | "SKIP"
}

interface JobDetail extends BriefItem {
  work_mode: string;           // "hybrid" | "remote" | "onsite"
  salary_min: number | null;   // e.g. 2200000 (annual INR)
  salary_max: number | null;
  salary_currency: string;     // "INR"
  source_url: string;          // original job post URL
  apply_url: string | null;    // direct ATS apply link
  verified_active: boolean;    // liveness checked
  status: "active" | "expired";
}
```

---

## 5. TAL — How to Render Job Cards (Frontend Spec)

Source: `docs/Tal Inspiration/tal_ux_inspiration.md` + `careerloop/whatsapp_ux.py`

### The List View (Today's Action List)

```
┌─────────────────────────────────────────────────┐
│           📊 CareerLoop — Today's Brief          │
│           Thursday, 29 May · 6 jobs              │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  [Company Logo]  Applied AI Engineer             │
│                  CheQ · Bengaluru · Hybrid       │
│                                                  │
│  🎯 78/100  ████████████░░░░  Strong Fit         │
│  💰 22–25 LPA  ·  Series A startup               │
│                                                  │
│  "Hiring for a core member to build LLM-based   │
│   financial advisory agents..."                  │
│                                                  │
│  [ ❌ Skip ]   [ 🧠 Inspect ]   [ ✅ Approve ]   │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  [Company Logo]  Senior ML Engineer              │
│                  Razorpay · Bengaluru · Remote   │
│                  ...                             │
└─────────────────────────────────────────────────┘
```

**Fit score color rules:**
- `>= 80` → Emerald green `#10B981`
- `60–79` → Amber `#F59E0B`
- `< 60` → Red `#EF4444` (don't show in TAL unless user asks)

**Route recommendation badge:**
- `APPLY` → 🟢 Direct Apply
- `RECRUITER` → 💬 DM Recruiter
- `REFERRAL` → 🤝 Find Referral
- `SKIP` → ⛔ Low Fit

### The Detail Card (on tap/click)

```
┌─────────────────────────────────────────────────┐
│  ← Back to Brief                                │
│                                                  │
│  [CheQ Logo]  Applied AI Engineer               │
│               CheQ · Bengaluru · Hybrid          │
│               22–25 LPA · Series A               │
│                                                  │
│  ┌──────────────────────┐                        │
│  │  Fit Score: 78/100   │  ████████████░░░░      │
│  └──────────────────────┘                        │
│                                                  │
│  Why it's a fit                                  │
│  Strong match on LLM stack and fintech domain.   │
│  Role directly maps to your AI product exp.      │
│                                                  │
│  Risks                                           │
│  ⚠️ Early-stage, could mean runway uncertainty   │
│                                                  │
│  Route                                           │
│  🟢 Direct Apply  →  [View Job Posting ↗]        │
│                                                  │
│  [ ❌ Skip ]              [ ✅ Approve & Pack ]   │
└─────────────────────────────────────────────────┘
```

### Swipe/Action States

| Action | What happens | API call |
|--------|-------------|---------|
| ✅ Approve | Move to `SHORTLISTED`, queue pack gen | `POST /jobs/{id}/save` then `POST /jobs/{id}/packs` |
| ❌ Skip | Move to `SKIPPED` | `POST /jobs/{id}/skip` |
| 🧠 Inspect | Open chat with job context | `POST /chat/message` with `"tell me about {company}"` |
| 🔗 View Job | Open `source_url` in new tab | Client-side only |

---

## 6. Minimal Frontend — Page-by-Page Plan

**Stack assumption:** Next.js (App Router) or any React framework. API base URL: `https://api.careerloop.in/v1` (or localhost:8001 in dev).

### Page 1 — Login
- Email + password form
- Calls `POST /auth/login`
- Stores JWT in httpOnly cookie or localStorage
- Redirect to `/brief` on success

### Page 2 — TAL / Daily Brief (THE CORE PAGE)
- Fetches `GET /briefs/latest`
- Renders list of `BriefItem` cards as described above
- Tap → navigate to `/jobs/{job_id}` detail
- Swipe right / Approve button → `POST /jobs/{id}/save`
- Swipe left / Skip → `POST /jobs/{id}/skip`
- Empty state: "No brief yet. Tap to run a scan."

### Page 3 — Job Detail
- Fetches `GET /jobs/{job_id}`
- Full detail card layout (described above)
- "Approve & Build Pack" → `POST /jobs/{id}/packs` → polling state
- "View Job Posting" → opens `source_url`

### Page 4 — Chat
- `POST /chat/message` with text
- Display `ResponseEnvelope.message` as assistant bubble
- If `response_type === "list"` → render cards inline in chat
- If `response_type === "card"` → render single job card inline
- Slash commands as quick-action chips: `/brief`, `/scan`, `/pipeline`

### Page 5 — Pipeline (defer to v2)
- `GET /pipeline` → list of all applications
- Status columns: Evaluated → Applied → Interview → Offer

---

## 7. What Needs to Be Built (Backend) Before Frontend Can Go Live

Priority order:

| # | Task | Effort | Blocks |
|---|------|--------|--------|
| 1 | Create `careerloop_api/` FastAPI app with `main.py` | 1h | Everything |
| 2 | Auth middleware — Supabase JWT validation | 2h | All protected routes |
| 3 | `GET /me` + `GET /me/preferences` | 1h | Profile display |
| 4 | `GET /briefs/latest` + `GET /briefs/{id}/items` | 1h | TAL page |
| 5 | `POST /briefs/{id}/items/{idx}/select` | 30m | TAL interaction |
| 6 | `GET /jobs/{job_id}` | 1h | Job detail page |
| 7 | `POST /jobs/{id}/save` + `POST /jobs/{id}/skip` | 30m | Swipe actions |
| 8 | `POST /chat/message` (wraps supervisor_graph) | 2h | Chat page |
| **Total** | | **~9h** | |

Everything needed is already in `repository_v2.py` and `tool_registry.py`. The API layer is a thin HTTP wrapper over existing logic.

---

## 8. Key Source Files (with evidence)

| What | File | Line ref |
|------|------|---------|
| API spec (full) | `docs/engineering/API_ARCHITECTURE.md` | entire file |
| TAL UX inspiration | `docs/Tal Inspiration/tal_ux_inspiration.md` | §3, §4 |
| Brief DB write | `careerloop/memory/repository_v2.py` | `create_brief()`, `create_brief_items()` |
| Brief DB read | `careerloop/session/tool_registry.py` | `show_brief()`, `select_brief_item()` |
| Job card formatter | `careerloop/whatsapp_ux.py` | `job_review_card()`, `job_detail_card()` |
| LangGraph supervisor | `careerloop/session/supervisor_graph.py` | `invoke_supervisor()` |
| Only live HTTP server | `careerloop/transport/webhook_server.py` | `POST /telegram/webhook` |
| DB schema | `docs/CAREERLOOP_SCHEMA.md` | full schema |
| daily_brief_items schema | `careerloop/memory/supabase_migration_v2.sql` | `careerloop.daily_brief_items` |

---

## 9. Local Dev Setup for Frontend Dev

```bash
# Start the backend (currently only Telegram webhook)
uvicorn careerloop.transport.webhook_server:app --host 0.0.0.0 --port 8000

# Once careerloop_api/ is built:
uvicorn careerloop_api.main:app --host 0.0.0.0 --port 8001 --reload

# Env vars needed
DATABASE_URL=postgresql://...
DEEPSEEK_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
```

For local SQLite dev (from Sprint 5):
```bash
USE_SQLITE=true python -m careerloop.session.supervisor_graph
```

---

## 10. Summary — What to Tell the Frontend Engineer

1. **The core product is the TAL (Today's Action List)** — a morning brief of 5–10 scored jobs rendered as swipeable cards. This is the first screen they should build after login.

2. **Job card data comes from `GET /briefs/latest`** which returns `items[]` with `title`, `company`, `location`, `fit_score`, `recommendation_reason`, `risk_summary`, `route_recommendation`. No extra fetching needed for the list view.

3. **The API doesn't exist yet** — the backend engineer needs to build `careerloop_api/` first (estimated ~9h). The spec is locked at `docs/engineering/API_ARCHITECTURE.md`. The data is all there in Supabase — just needs HTTP wrappers.

4. **Chat is the fallback for everything** — `POST /chat/message` can answer any question. "Why this job?", "company intel", "build my pack" — all go through the same endpoint.

5. **Fit score drives the visual** — `>= 80` green, `60–79` amber. Route badge (`APPLY`/`RECRUITER`/`REFERRAL`) tells the user their action.

6. **Build order:** Login → TAL list → Job detail → Chat. That's v1.
