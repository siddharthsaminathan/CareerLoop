# CareerLoop API

Thin FastAPI product layer for the web/iOS/Android frontend.

```
router → service → repository → Supabase (careerloop.*)
```

## Auth — Supabase (Google OAuth)

The client handles the full OAuth flow via Supabase libraries. The backend
only validates the Supabase-issued JWT — no login endpoint, no password storage.

**Flow:**
```
Client → "Sign in with Google" → Supabase OAuth
       → Supabase returns access_token
       → Client sends: Authorization: Bearer <access_token>
       → Backend verifies JWT with SUPABASE_JWT_SECRET
       → Auto-provisions careerloop.users row on first call
```

**Frontend setup:**
```js
// web — @supabase/supabase-js
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
await supabase.auth.signInWithOAuth({ provider: 'google' })
const { data: { session } } = await supabase.auth.getSession()
// pass to API:
headers: { Authorization: `Bearer ${session.access_token}` }
```
Same pattern: `supabase-swift` (iOS), `supabase-kt` (Android).

**After sign-in, call once:**
```
POST /v1/auth/me   (with Bearer token)
→ provisions careerloop.users row if new user
→ returns user profile
```

## Run

```bash
# deps
.venv/bin/pip install -r requirements.txt

# env — get SUPABASE_JWT_SECRET from:
# Supabase dashboard → Settings → API → JWT Secret
export SUPABASE_JWT_SECRET="your-supabase-jwt-secret"
export DATABASE_URL="your-supabase-postgres-url"
export DEEPSEEK_API_KEY="your-deepseek-key"

# start on port 8001 (Telegram webhook stays on 8000)
.venv/bin/uvicorn careerloop_api.main:app --host 0.0.0.0 --port 8001 --reload
```

Interactive docs: http://127.0.0.1:8001/docs

## Endpoints (all under `/v1`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/v1/auth/me` | ✅ | Provision user on first sign-in, return profile |
| GET | `/v1/me` | ✅ | Current user profile |
| GET | `/v1/me/preferences` | ✅ | Target roles/cities/salary/etc. |
| GET | `/v1/briefs/latest` | ✅ | Latest daily brief + TAL job cards |
| POST | `/v1/briefs/{brief_id}/items/{item_index}/select` | ✅ | Select a card → sets active job context |
| GET | `/v1/jobs/{job_id}` | ✅ | Full job detail (UUID or legacy id) |
| POST | `/v1/jobs/{job_id}/save` | ✅ | Swipe right → `match_status=saved` |
| POST | `/v1/jobs/{job_id}/skip` | ✅ | Swipe left → `match_status=skipped` |
| POST | `/v1/chat/message` | ✅ | Natural-language turn through the supervisor graph |
| GET | `/health` | – | Liveness check |

All responses: `{ ok, data, error, meta }`.  
Auth errors return `401` with `{ ok: false, error: { message, code: "unauthorized" } }`.

## E2E test

```bash
# start server with a test secret:
SUPABASE_JWT_SECRET=test-secret .venv/bin/uvicorn careerloop_api.main:app --port 8001

# in another terminal:
SUPABASE_JWT_SECRET=test-secret .venv/bin/python careerloop_api/e2e_api_test.py
```

To test with a real Google OAuth token, set `API_REAL_TOKEN` to a valid
`session.access_token` from a logged-in Supabase session and run with the real
`SUPABASE_JWT_SECRET`.

Last run: **15/15 passing** (4 auth rejection tests + 11 happy-path tests).

## User provisioning

On the first authenticated API call:
- `get_current_user()` verifies the JWT → extracts `sub`, `email`, `full_name`
- Inserts a `careerloop.users` row with `id = auth.users.id` (Supabase UUID)
- Subsequent calls hit `ON CONFLICT (id) DO UPDATE SET last_active_at = NOW()` (fast)

Identity is universal — same JWT works for web, iOS, Android.
