# Dev Blog — 2026-05-29: MVP REST API (careerloop_api/)

## What Was Done
- Built the `careerloop_api/` FastAPI package from the locked spec in `docs/engineering/API_ARCHITECTURE.md` — the first web-facing REST layer (previously only a Telegram webhook existed).
- Implemented all 7 MVP endpoint groups (9 routes) under `/v1`: auth/login, /me, /me/preferences, /briefs/latest, brief item select, /jobs/{id}, /jobs/{id}/save, /jobs/{id}/skip, /chat/message.
- Layered architecture: `routers → services → repositories → DatabaseManager`, with a shared `{ok,data,error,meta}` response envelope and a `get_current_user` bearer-token dependency.
- Wrote `e2e_api_test.py` (no pytest) — hits a live server against real Supabase + DeepSeek. **13/13 passing.**

## Key Decisions
- **Repository layer queries the LIVE v1 schema directly**, not via `repository_v2.py`. The live DB has `daily_briefs.id`/`daily_brief_items.recommendation_reason`, while repository_v2 writes v2 names (`brief_id`/`reason`) that don't exist yet — the persistence split from `ARCHITECTURE_AUDIT_2026-05-24.md`. Reading via repository_v2 would have returned wrong/empty data.
- **Zero-dependency HMAC token** for auth instead of adding PyJWT. No password is stored in the schema, so `/auth/login` authenticates by proven identity (email/user_id) and issues a signed token. Documented as dev/MVP pending Supabase JWT validation.
- **Job lookup accepts both UUID `job_id` and legacy text `id`** (brief items reference either). save/skip resolve to the canonical UUID and return `409` if a job is legacy-only.
- Mounted on **port 8001** to leave the Telegram webhook on 8000.

## Issues Encountered
- `build_supervisor_graph()` returns an *uncompiled* `StateGraph` — `.invoke()` fails with `AttributeError`. The Telegram webhook (`webhook_server.py::_route_to_supervisor`) has the same latent bug. Fixed in chat_service by using `get_supervisor_graph()` which compiles. **The webhook server likely has a live chat bug — flag for follow-up.**
- FastAPI/uvicorn were not installed in `.venv`; added them and pinned in `requirements.txt`.

## Files Changed
- `careerloop_api/` (new package): main.py, core/{config,security,envelope}.py, deps/{auth,db}.py, repositories/{users,briefs,jobs}_repo.py, services/{user,brief,job,chat,serializers}.py, routers/{auth,users,briefs,jobs,chat}.py, e2e_api_test.py, README.md
- `requirements.txt` — added fastapi, uvicorn[standard], httpx

## Next Session
- Wire the frontend against these endpoints (login → TAL list → job detail → chat).
- Fix the same uncompiled-graph bug in `webhook_server.py::_route_to_supervisor`.
- Add the deferred endpoints: `/scans` + SSE events, `/jobs/{id}/packs`, `/pipeline`.
- Reconcile the v1/v2 schema drift so `repository_v2.py` writes match live columns.
