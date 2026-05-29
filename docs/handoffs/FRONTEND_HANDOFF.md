# CareerLoop — Frontend Integration Handoff
**Date:** 2026-05-29  
**Backend status:** Live at `http://localhost:8001` · 15/15 E2E passing  
**Auth:** Supabase Google OAuth (universal — web, iOS, Android)

---

## 0. Quick Start

```bash
# Clone and run the backend
git clone <repo>
cd CareerLoop
.venv/bin/pip install -r requirements.txt

# Copy env and fill in (DATABASE_URL + SUPABASE_JWT_SECRET already set)
cp .env.example .env
# Add: SERPAPI_KEY=<your key>  ← enables LinkedIn-first onboarding

# Start API (port 8001)
set -a; . ./.env; set +a
.venv/bin/uvicorn careerloop_api.main:app --host 0.0.0.0 --port 8001 --reload
```

Interactive docs: **http://localhost:8001/docs**

---

## 1. Auth — Supabase Google OAuth

**The backend does not have a login form.** The client (web/iOS/Android) handles OAuth entirely via Supabase libraries. The backend just validates the Supabase JWT on every request.

### Frontend setup (web — `@supabase/supabase-js`)

```js
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://iephtlrikgfgakcojwhu.supabase.co',   // your Supabase project URL
  '<SUPABASE_ANON_KEY>'                           // from Supabase dashboard → Settings → API
)

// 1. Trigger Google sign-in
await supabase.auth.signInWithOAuth({ provider: 'google' })

// 2. After redirect, get the session
const { data: { session } } = await supabase.auth.getSession()

// 3. Every API call uses this as the bearer token
const headers = { Authorization: `Bearer ${session.access_token}` }
```

### After sign-in — call once to register the user

```
POST /v1/auth/me
Authorization: Bearer <session.access_token>
```

This creates the `careerloop.users` row if new (idempotent — safe to call on every app launch). Returns the user profile.

**You need to enable Google OAuth in Supabase:**
Supabase dashboard → Authentication → Providers → Google → add Google Client ID + Secret, then add your app domain to Redirect URLs.

### What happens automatically
- Brand-new user → `careerloop.users` row created (`onboarding_complete: false`)
- User is in `NEW_USER` state → first `/v1/chat/message` routes them to onboarding
- After onboarding completes → `onboarding_complete: true`, state = `PROFILE_READY`
- Existing user → `last_active_at` updated, same token works

---

## 2. All Endpoints — Full Contract

**Base URL:** `http://localhost:8001/v1`  
**Auth:** `Authorization: Bearer <supabase_access_token>` on every request  
**Response envelope (all endpoints):**
```json
{
  "ok": true,
  "data": { ... },
  "error": null,
  "meta": { "request_id": "uuid", "timestamp": "ISO8601" }
}
```
**Error response:**
```json
{
  "ok": false,
  "data": null,
  "error": { "message": "Human readable", "code": "snake_case_code" },
  "meta": { ... }
}
```

---

### POST `/v1/auth/me` — Register / get profile

Call once after OAuth. Creates user row on first call.

**Response `data`:**
```json
{
  "id": "9c512f87-1f5b-5e58-bf23-778d97e6e0a7",
  "email": "user@gmail.com",
  "full_name": "Priya Sharma",
  "linkedin_url": null,
  "onboarding_complete": false,
  "career_mode": "explore",
  "has_cv": false,
  "created_at": "2026-05-29T07:36:52Z",
  "last_active_at": "2026-05-29T07:36:52Z"
}
```

---

### GET `/v1/me` — Current user profile

Same shape as `/auth/me`. Use to check `onboarding_complete` on app load.

---

### GET `/v1/me/preferences` — Job preferences

```json
{
  "target_roles": ["Senior ML Engineer", "AI Product Engineer"],
  "target_cities": ["Bangalore", "Remote"],
  "salary_expectations": "40-55 LPA",
  "notice_period": "60 days",
  "work_mode": null,
  "aggressiveness": "aggressive",
  "source": "users_fallback"
}
```
Fields are null/empty until onboarding completes.

---

### GET `/v1/briefs/latest` — Today's job list (the TAL)

Returns the latest daily brief with all job cards.

**Response `data`:**
```json
{
  "brief_id": "11994aae-f39d-4506-8275-26e7a42bc176",
  "date_str": "2026-05-24",
  "summary": "6 strong matches today.",
  "created_at": "2026-05-24T04:00:00Z",
  "item_count": 5,
  "items": [ <BriefItem>, ... ]
}
```

**BriefItem shape:**
```json
{
  "item_index": 1,
  "job_id": "loop-0122",
  "title": "AI Engineer",
  "company": "BigRio",
  "logo_url": "https://ui-avatars.com/api/?name=BigRio&background=0D8ABC&color=fff&bold=true&size=128",
  "location": "Chennai",
  "work_mode": null,
  "salary_min": null,
  "salary_max": null,
  "salary_currency": "INR",
  "description": "Building LLM-based products for...",
  "fit_score": 69.3,
  "fit_tier": "good",
  "recommendation_reason": "Strong match on LLM stack and fintech domain.",
  "risk_summary": "Early-stage startup, Series A.",
  "route_recommendation": "APPLY",
  "apply_url": "https://cutshort.io/job/..."
}
```

**`fit_tier` → color:**
| `fit_tier` | Score | Color |
|---|---|---|
| `"strong"` | ≥80 | Emerald `#10B981` |
| `"good"` | 60–79 | Amber `#F59E0B` |
| `"weak"` | <60 | Red `#EF4444` |

**Logo:** Always non-null. Priority: real logo URL → Clearbit domain logo → initials avatar (always renders, never broken).

**404 error code `no_brief`** if user has no brief yet — show empty state + "Run a scan".

---

### POST `/v1/scans` — Start a scan (ASYNC — returns immediately)

Do NOT use `/chat/message` with `/scan` — that blocks for 60s. Use this instead.

**Two modes:**
```json
POST /v1/scans  {}                      → default: cache-first daily brief (fast)
POST /v1/scans  {"mode": "scan_more"}   → FRESH discovery across job portals, streamed
                                          live, deduped against the brief, no cache
```
**The "Scan More" button MUST send `{"mode":"scan_more"}`.** It scans ~real companies
live (Palantir, Mistral, Spotify…), streams each as it's hit, evaluates each role
against the user's target roles (match/skip), and appends net-new matches to the brief.

**Response `data`:**
```json
{ "run_id": "a094e1121424", "status": "RUNNING", "mode": "scan_more" }
```

**scan_more SSE event types (render as a live feed):**
| event_type | render as |
|---|---|
| `SCAN_STARTED` | "Hunting for fresh roles…" |
| `SOURCE_SCANNING` | "🔍 Scanned Anthropic — 386 roles" (rolls in live, one per company) |
| `JOB_FOUND` | "Found: {title} @ {company}" |
| `JOB_EVALUATED` | "✓ {title} — matches" / "✗ {title} — skipped" |
| `FILTER_SUMMARY` | "Scanned 40 companies · 9 roles seen · 3 new matches added" |
| `BRIEF_CREATED` | done — reload `GET /v1/briefs/latest` to show new cards |
| `DONE` | close the EventSource |

Verified live: 40 companies stream over ~45s with real time gaps. Proof: `logs/scan_more_proof.txt`.

After getting the `run_id`, open an EventSource to `/v1/scans/{run_id}/events` to stream progress.

---

### GET `/v1/scans/{run_id}/events` — Real-time scan progress (SSE)

Server-Sent Events stream. Each event has `event_type` and `message`. Stream closes with a `DONE` event when the scan finishes.

```js
// CORRECT way to trigger a scan + show progress
async function startScan(token) {
  // 1. Start scan — returns run_id instantly
  const res = await fetch('/v1/scans', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` }
  })
  const { data: { run_id } } = await res.json()

  // 2. Open SSE stream
  // NOTE: EventSource doesn't support custom headers natively.
  // Use fetchEventSource from @microsoft/fetch-event-source instead:
  import { fetchEventSource } from '@microsoft/fetch-event-source'
  fetchEventSource(`/v1/scans/${run_id}/events`, {
    headers: { Authorization: `Bearer ${token}` },
    onmessage(e) {
      const evt = JSON.parse(e.data)

      if (evt.event_type === 'DONE') {
        // 3. Scan complete — fetch the brief
        fetchBrief()
        return
      }

      // Render each event as a progress row in the UI
      renderScanEvent(evt)  // see event types below
    }
  })
}

// Event types and how to render them:
// QUEUED           → "Initializing..."
// SCAN_STARTED     → "🔍 Starting job discovery"
// SOURCE_STARTED   → "📡 Searching job portals..."
// CACHE_HIT        → "📦 Found 7 recent jobs in cache"
// CANDIDATE_MATCHED→ "✅ MATCH #1 — AI Engineer @ BigRio (Chennai) — 69/100"
// FILTER_SUMMARY   → "📊 Scan complete: 15 raw, 7 new, 7 scored"
// BRIEF_CREATED    → "✨ Brief ready — loading your matches..."
// DONE             → close stream, call GET /v1/briefs/latest
```

---

### GET `/v1/scans/{run_id}` — Scan status

```json
{ "run_id": "...", "status": "RUNNING|COMPLETED|FAILED", "started_at": "..." }
```

---

### POST `/v1/briefs/{brief_id}/items/{item_index}/select` — Tap a card

`item_index` is 1-based (1, 2, 3…). Sets this job as the active context.

**Response `data`:**
```json
{
  "job_id": "loop-0122",
  "active_artifact_type": "job_card",
  "active_brief_id": "11994aae-...",
  "selected_index": 1,
  "card": <BriefItem>
}
```

---

### GET `/v1/jobs/{job_id}` — Full job detail

`job_id` accepts the UUID **or** the legacy text id (`loop-0122`).

**Response `data`** — all BriefItem fields plus:
```json
{
  "job_id": "3d10a92f-b6af-4e6f-b15e-3e39c2cfe77e",
  "legacy_id": "loop-0122",
  "title": "AI Engineer",
  "company_name": "BigRio",
  "logo_url": "...",
  "location": "Chennai",
  "location_city": "Chennai",
  "work_mode": null,
  "salary_min": null,
  "salary_max": null,
  "salary_currency": "INR",
  "source": "cutshort",
  "source_url": "",
  "apply_url": "https://cutshort.io/...",
  "role_summary": null,
  "description": "Build AI-powered...",
  "is_india_role": true,
  "verified_active": false,
  "status": "active",
  "posted_at": null,
  "match_status": "skipped",
  "fit_score": 69.3,
  "fit_tier": "good",
  "route_recommendation": null
}
```

**404** `job_not_found` if unknown.

---

### POST `/v1/jobs/{job_id}/save` — Swipe right / Approve

```json
→ { "job_id": "uuid", "match_status": "saved", "swiped_action": "right" }
```
Writes to `careerloop.user_job_relationships`. **409** `job_not_canonical` for legacy-only text ids.

---

### POST `/v1/jobs/{job_id}/skip` — Swipe left / Skip

```json
→ { "job_id": "uuid", "match_status": "skipped", "swiped_action": "left" }
```

---

### POST `/v1/chat/message` — Chat (drives onboarding + all intents)

**Request:**
```json
{ "text": "show my brief", "conversation_id": null }
```

**Response `data`:**
```json
{
  "message": "Here are your 5 matches for today...",
  "response_type": "text",
  "cards": [],
  "actions": [],
  "active_context": {
    "active_artifact_type": null,
    "active_job_id": null,
    "active_brief_id": null,
    "active_pack_id": null
  },
  "state": "PROFILE_READY"
}
```

*Frontend Note (2026-05-29):* The frontend maps this response using `res.data.message` and renders the text via `react-markdown` to ensure all formatting is perfectly displayed in the chat bubbles.

`response_type` values:
- `"text"` — plain message, render in chat bubble
- `"list"` — `cards[]` contains job cards (same BriefItem shape), render inline
- `"card"` — `cards[0]` is a single card

**During onboarding** (`state: "NEW_USER"`), `response_type` can be `"card"` with:
```json
"cards": [{
  "type": "identity_confirmation",
  "full_name": "Priya Sharma",
  "headline": "Senior ML Engineer at FinScale",
  "current_company": "FinScale",
  "location": "Bangalore",
  "linkedin_url": "https://linkedin.com/in/priya-sharma",
  "avatar_url": ""
}]
```
Render this as the Tal-style "Is this you?" card with Yes / No buttons.

---

## 3. Onboarding Flow (chat-driven)

Route all chat for `state == "NEW_USER"` users through the chat UI.

### CV-first (active today — no SERPAPI_KEY needed)
```
App open → POST /auth/me → onboarding_complete: false
→ show chat
→ user types anything
→ POST /chat/message → "Paste your CV"
→ user pastes CV
→ POST /chat/message "<cv text>" → confirmation card
→ user says "yes"
→ POST /chat/message "yes" → gap-fill or complete
→ state = PROFILE_READY → show TAL
```

### LinkedIn-first (activates when SERPAPI_KEY is set)
```
App open → POST /auth/me → show chat
→ user types anything
→ POST /chat/message → "What's your full name?"
→ user types name
→ POST /chat/message "Priya Sharma"
→ backend Google-searches LinkedIn, filters by name match
→ response_type: "card", cards[0].type: "identity_confirmation"
→ render "Is this you?" card → user taps Yes
→ POST /chat/message "yes"
→ "Pre-filled! Now paste your CV or skip"
→ user pastes CV or says "skip"
→ gap-fill → state = PROFILE_READY → show TAL
```

---

## 4. Page-by-Page Build Order

### Page 1 — Login
- Supabase Google OAuth button
- On success → `POST /v1/auth/me` → check `onboarding_complete`
- `false` → go to onboarding chat
- `true` → go to TAL

### Page 2 — Onboarding Chat
- Full-screen chat UI
- Route all messages through `POST /v1/chat/message`
- Watch `state` in response: `NEW_USER` → stay in chat; `PROFILE_READY` → navigate to TAL
- If `response_type == "card"` and `cards[0].type == "identity_confirmation"` → render the "Is this you?" identity card with Yes/No buttons

### Page 3 — TAL (Today's Action List) ← core product UI
- `GET /v1/briefs/latest` → render each `items[]` entry as a swipeable card
- Empty state (404) → "No brief yet" + "Run a scan" CTA (sends `POST /v1/chat/message` with text `"/scan"`)
- Card tap → `POST /v1/briefs/{brief_id}/items/{item_index}/select` → navigate to Job Detail
- Swipe right → `POST /v1/jobs/{job_id}/save`
- Swipe left → `POST /v1/jobs/{job_id}/skip`

### Page 4 — Job Detail
- `GET /v1/jobs/{job_id}`
- Show logo, title, company, location, fit score (colored by `fit_tier`)
- Show description, salary (if present), route badge
- "Apply" button → open `apply_url` in new tab
- "Approve & Build Pack" → `POST /v1/jobs/{job_id}/save`
- "Skip" → `POST /v1/jobs/{job_id}/skip`

### Page 5 — Chat (universal fallback)
- `POST /v1/chat/message` for everything: "why this job", "company intel", "scan for new jobs", etc.
- If `response_type == "list"`, render cards inline in the chat bubble

---

## 5. Supabase Env Values (for the frontend)

```
NEXT_PUBLIC_SUPABASE_URL=https://iephtlrikgfgakcojwhu.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<get from Supabase dashboard → Settings → API → anon public>
NEXT_PUBLIC_API_BASE=http://localhost:8001
```

---

## 6. Backend File Map (for reference)

| Concern | File |
|---|---|
| App entry | `careerloop_api/main.py` |
| JWT verify (Supabase) | `careerloop_api/core/security.py` |
| Auth dep + user provisioning | `careerloop_api/deps/auth.py` |
| Routers | `careerloop_api/routers/{auth,users,briefs,jobs,chat}.py` |
| Job card serialization | `careerloop_api/services/serializers.py` |
| DB repos (live schema) | `careerloop_api/repositories/` |
| Onboarding orchestrator | `careerloop/onboarding/onboarding_flow.py` |
| LinkedIn identity (SerpAPI) | `careerloop/sources/identity_provider.py` |
| E2E tests | `careerloop_api/e2e_api_test.py`, `e2e_onboarding_test.py` |
