# CareerLoop — Backend → Frontend Handoff (Consolidated)
**Date:** 2026-05-29
**Author:** Backend (Claude)
**Status:** API live, auth via Supabase, onboarding E2E proven, Tal job cards enriched
**Verified:** 15/15 API E2E + 7/7 new-user onboarding E2E (real Supabase + real DeepSeek)
**Architect Verdict:** `docs/learnings/2026-05-29_SENIOR_ARCHITECT_VERDICT.md` — 7.8/10 overall. P0 thread safety and P1 connection pooling identified as pre-multi-user blockers.

This is the single doc for everyone working on the first web frontend. It covers:
1. Auth (Supabase Google OAuth) — universal across web/iOS/Android
2. The 7 MVP API endpoints — full contract
3. Tal-inspired job card rendering — what the API now returns
4. New-user onboarding flow (CV-first live, LinkedIn-first ready)
5. How to run the server + test

---

## 1. Auth — Supabase, Universal, Every User Handled

**Yes — every user is handled automatically.** There is no custom login. The flow:

```
Client (web/iOS/Android)
  → Supabase "Sign in with Google"
  → Supabase issues a JWT (signed with SUPABASE_JWT_SECRET)
  → Client sends:  Authorization: Bearer <access_token>   on every request
Backend
  → Verifies the JWT (careerloop_api/core/security.py)
  → On first call, auto-provisions a careerloop.users row
    (id = Supabase auth.users UUID)   [careerloop_api/deps/auth.py:_provision_user]
  → Every endpoint receives a clean user_id
```

- **No per-user setup needed.** A brand-new Google user → provisioned on first call → lands in `NEW_USER` state → routed into onboarding. Verified E2E.
- **Same token works for web, iOS, Android** — auth is transport-agnostic.
- Identity contract: `careerloop.users.id == auth.users.id`. Telegram users live in a separate pool (uuid5-derived); not used for web.

**Frontend setup:**
```js
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
await supabase.auth.signInWithOAuth({ provider: 'google' })
const { data: { session } } = await supabase.auth.getSession()
// after sign-in, call once:
//   POST /v1/auth/me   Authorization: Bearer <session.access_token>
// then use the same bearer token on every call.
```

**You must:** enable Google in Supabase (Authentication → Providers → Google) and add redirect URLs. The backend env needs `SUPABASE_JWT_SECRET` (already set in `.env`).

---

## 2. The 7 MVP Endpoints — Full Contract

Base URL: `http://127.0.0.1:8001` (dev). All under `/v1`. All return the envelope:
```json
{ "ok": true, "data": {…}, "error": null, "meta": { "request_id": "…", "timestamp": "…" } }
```
Errors: `{ "ok": false, "data": null, "error": { "message": "…", "code": "…" } }` with HTTP 401/404/409/500.
All endpoints except `/health` require `Authorization: Bearer <token>`.

### (1) POST `/v1/auth/me` — provision + profile
Call once right after OAuth. Creates the user row if new.
```json
→ { "id": "uuid", "email": "…", "full_name": "…", "onboarding_complete": false,
    "career_mode": "explore", "has_cv": false, "linkedin_url": null, … }
```

### (2) GET `/v1/me` — current profile
Same shape as above.

### (3) GET `/v1/me/preferences`
```json
→ { "target_roles": [...], "target_cities": [...], "salary_expectations": "…",
    "notice_period": "…", "work_mode": "…", "aggressiveness": "…", "source": "…" }
```

### (4) GET `/v1/briefs/latest` — the TAL list
Returns the latest daily brief and its job cards (TAL items):
```json
→ {
  "brief_id": "uuid", "date_str": "2026-05-24", "summary": "…",
  "created_at": "…", "item_count": 5,
  "items": [ <BriefItem>, … ]   // see §3 for BriefItem shape
}
```
404 `no_brief` if the user has no brief yet (show an empty state + "run scan").

### (5) POST `/v1/briefs/{brief_id}/items/{item_index}/select`
Marks a card as the active job (sets session context). `item_index` is 1-based.
```json
→ { "job_id": "loop-0122", "active_artifact_type": "job_card",
    "active_brief_id": "uuid", "selected_index": 1, "card": <BriefItem> }
```

### (6) GET `/v1/jobs/{job_id}` — full job detail
`job_id` accepts the canonical UUID **or** the legacy text id (`loop-0122`).
```json
→ <JobDetail>   // see §3
```
404 `job_not_found` if unknown.

### (7a) POST `/v1/jobs/{job_id}/save` — swipe right
```json
→ { "job_id": "uuid", "match_status": "saved", "swiped_action": "right" }
```
### (7b) POST `/v1/jobs/{job_id}/skip` — swipe left
```json
→ { "job_id": "uuid", "match_status": "skipped", "swiped_action": "left" }
```
Both persist to `careerloop.user_job_relationships`. Return `409 job_not_canonical`
if the job has no UUID yet (legacy-only rows).

### (bonus) POST `/v1/chat/message` — natural language
```json
← { "text": "show my brief", "conversation_id": null }
→ { "message": "…", "response_type": "text|card|list",
    "cards": [...], "actions": [...],
    "active_context": { "active_job_id": "…", "active_brief_id": "…" },
    "state": "NEW_USER|PROFILE_READY|…" }
```
*Frontend Note (2026-05-29):* The frontend has been successfully updated to accurately read `response.data.message` (instead of `text` or `content`). It also now renders this field as full Markdown using `react-markdown` to support bolding and headers.

For `NEW_USER`, this drives onboarding (see §4). For `PROFILE_READY+`, it runs the
LangGraph supervisor (real LLM). Use this as the universal fallback for anything
without a dedicated endpoint ("why this job", "company intel", etc.).

---

## 3. Tal-Inspired Job Cards — What the API Now Returns

The job card data is modeled on `docs/Tal Inspiration/tal_ux_inspiration.md`
(logo, title, company, location, fit score + color, salary, description, route).

### BriefItem (the TAL swipe card) — from `/v1/briefs/latest`
```ts
interface BriefItem {
  item_index: number;            // 1-based ordinal
  job_id: string;                // UUID or legacy "loop-0122"
  title: string;                 // "AI Engineer"
  company: string;               // "BigRio"
  logo_url: string | null;       // company logo (see logo strategy below)
  location: string;              // "Chennai"
  work_mode: string | null;      // remote | hybrid | onsite
  salary_min: number | null;     // annual, INR
  salary_max: number | null;
  salary_currency: string;       // "INR"
  description: string | null;    // ≤280-char snippet
  fit_score: number | null;      // 0–100, e.g. 69.3
  fit_tier: "strong"|"good"|"weak"|null;  // ≥80 strong(green), 60–79 good(amber), <60 weak(red)
  recommendation_reason: string | null;   // "Why it's a fit"
  risk_summary: string | null;
  route_recommendation: string | null;    // APPLY | RECRUITER | REFERRAL | SKIP (free text)
  apply_url: string | null;
}
```

### JobDetail — from `/v1/jobs/{job_id}`
All of BriefItem's job fields plus: `legacy_id`, `location_city`, `source`,
`source_url`, `role_summary`, `description` (longer, ≤1200 chars), `is_india_role`,
`verified_active`, `status`, `posted_at`, and (if a relationship exists)
`match_status`, `fit_score`, `fit_tier`, `route_recommendation`.

### Color rules for the frontend (from `fit_tier`)
| tier | score | color |
|------|-------|-------|
| `strong` | ≥80 | Emerald `#10B981` |
| `good` | 60–79 | Amber `#F59E0B` |
| `weak` | <60 | Red `#EF4444` |

### Logo strategy (implemented in `serializers.company_logo`)
The frontend just renders `logo_url` — the backend always provides something:
1. `companies.logo_url` if backfilled (currently NULL in DB — see gap below)
2. else Clearbit logo from the company's own domain/website
3. else an initials avatar (`ui-avatars.com`) generated from the company name — **always renders**

So cards never show a broken image. Example today:
`https://ui-avatars.com/api/?name=BigRio&background=0D8ABC&color=fff&bold=true&size=128`

### Known data gaps (not blockers — cards still render)
- `companies.logo_url`, `domain`, `website` are NULL for all current companies → real
  logos require a backfill job (Clearbit enrichment or crawler fix). Until then, the
  initials-avatar fallback renders.
- `salary_min/max` and `jd_text`/`role_summary` are empty for the 5 real scraped jobs
  (the scraper doesn't populate them yet) → `salary_*` and `description` will be null
  for those. Seeded test jobs have descriptions.

---

## 4. New-User Onboarding Flow

Driven entirely through `POST /v1/chat/message` while the user is `NEW_USER`.
The frontend just renders messages + (optionally) the identity card, and posts replies.

### CV-first (LIVE today — proven 7/7 E2E)
```
1. POST /auth/me                          → user provisioned, state=NEW_USER
2. POST /chat/message "hi"                → "Welcome… paste your CV/resume"
3. POST /chat/message "<CV text>"         → real LLM extracts roles/cities → confirm card
4. POST /chat/message "yes"               → fills gaps OR completes
5. POST /chat/message "<missing details>" → state flips to PROFILE_READY
```
On completion: `careerloop.users.onboarding_complete = true`, session → `PROFILE_READY`.

### LinkedIn-first (BUILT, dormant until you add a key)
Implemented via **SerpAPI Google search** (`careerloop/sources/identity_provider.py`)
— the same `SERPAPI_KEY` already used for company discovery. No paid per-profile API.
When `SERPAPI_KEY` is set in `.env`, onboarding becomes:
```
1. POST /chat/message "hi"                  → "What's your full name?"
2. POST /chat/message "Priya Sharma"        → Google search (site:linkedin.com/in)
                                              → NAME-MATCH FILTER verifies it's them
                                              → "Is this you?" + identity card in cards[]
3. POST /chat/message "yes"                 → profile pre-filled, asks for CV (or "skip")
4. → gap-fill → PROFILE_READY
```
**Name-match filter (the safeguard):** we only present a candidate when the result's
profile name actually matches what the user typed (first name must match + ≥60% token
overlap). A non-match falls back to CV rather than claiming a stranger is them.

Because Google returns only public title/snippet (not full profile data), the card
shows name + headline + company + URL; the CV step then captures detailed proof points.

When `chat/message` returns `response_type: "card"` with `cards[0].type ==
"identity_confirmation"`, render the Tal-style "Is this you?" card:
`{ full_name, headline, current_company, location, linkedin_url, avatar_url }`.

**To activate:** add `SERPAPI_KEY=...` to `.env` and restart. With no key, it falls
back to CV-first automatically (no mock data — the old hardcoded scraper was removed).

---

## 5. Run + Test

```bash
# install deps
.venv/bin/pip install -r requirements.txt

# env already has DATABASE_URL, DEEPSEEK_API_KEY, SUPABASE_JWT_SECRET
# (optional) add SERPAPI_KEY to enable LinkedIn-first onboarding

# start the API (port 8001; Telegram webhook stays on 8000)
set -a; . ./.env; set +a
.venv/bin/uvicorn careerloop_api.main:app --host 0.0.0.0 --port 8001 --reload
```
Interactive docs: http://127.0.0.1:8001/docs

```bash
# E2E tests (server must be running, same secret):
export SUPABASE_JWT_SECRET=$(grep SUPABASE_JWT_SECRET .env | cut -d= -f2-)
.venv/bin/python careerloop_api/e2e_api_test.py          # 15/15 — all endpoints + auth
.venv/bin/python careerloop_api/e2e_onboarding_test.py   # 7/7  — new-user onboarding
```

### Minting a test token (frontend-free)
The E2E scripts mint Supabase-shaped JWTs with the real secret. The frontend uses
real Google OAuth tokens — no minting needed.

---

## 6. Frontend Build Order (recommended)
1. **Auth** — Supabase Google sign-in → `POST /auth/me`
2. **Onboarding** — chat loop for `NEW_USER` (CV-first; identity card if LinkedIn on)
3. **TAL list** — `GET /briefs/latest` → render BriefItem cards (logo, fit_tier color, route)
4. **Job detail** — `GET /jobs/{id}` + save/skip buttons
5. **Chat** — `POST /chat/message` for everything else

---

## 7. File Map (backend)
| Concern | File |
|---------|------|
| App entry + routers | `careerloop_api/main.py` |
| Supabase JWT verify | `careerloop_api/core/security.py` |
| Auth dep + provisioning | `careerloop_api/deps/auth.py` |
| Response envelope | `careerloop_api/core/envelope.py` |
| Routers | `careerloop_api/routers/{auth,users,briefs,jobs,chat}.py` |
| Services | `careerloop_api/services/{user,brief,job,chat}_service.py` |
| Card serialization (logo/desc/tier) | `careerloop_api/services/serializers.py` |
| Repositories (live-schema SQL) | `careerloop_api/repositories/{users,briefs,jobs}_repo.py` |
| LinkedIn identity (SerpAPI + name filter) | `careerloop/sources/identity_provider.py` |
| Onboarding orchestrator | `careerloop/onboarding/onboarding_flow.py` |
| E2E tests | `careerloop_api/e2e_api_test.py`, `careerloop_api/e2e_onboarding_test.py` |
