# Dev Blog — 2026-05-30: Product Hardening — Auth, Discovery Pipeline & Core Loop Stability

## What Was Done

### Onboarding Loop — Fixed
- `_handle_waiting_cv()` had a hardcoded greetings set (`{"hello", "hi", "wtf", ...}`) that returned the exact same string every time without saving state. Loop persisted forever.
- **Fix:** Replaced hardcoded trap with `onboarding_agent.process()` — LLM generates contextual replies, saves state, and advances the flow.
- `_ensure_conversation()` race condition fixed — the in-memory session object was stale when `OnboardingFlow._save()` ran, overwriting the conv_id with every onboarding step. Now synced immediately after `_ensure_conversation` returns.

### ActionResolver — SHOW_PROFILE vs GENERAL_CHAT Routing
- All profile queries ("What roles am I targeting?", "Do you have my profile?") were routing to `SHOW_PROFILE` which dumped the full CV card.
- **Fix:** Updated ActionResolver system prompt — full document requests → `SHOW_PROFILE`, specific field questions → `GENERAL_CHAT`. The GENERAL_CHAT handler already had profile context and calls DeepSeek to synthesise a direct answer.
- Verified: "What roles am I targeting?" → "AI Product Engineer, Systems Architect, AI Engineer, Data Engineer — Chennai." No CV dump.

### Discovery Pipeline — 2 Jobs → 7 Jobs
- Root cause traced from live `run_events` DB: 114 raw → 62 killed by India filter → 52 → **48 killed by ontology gate** → 4 → 2 final.
- Ontology gate used LLM-generated `must_have` tokens (`["product", "applied AI", "customer-facing", "cross-functional"]`) — PM jargon never appearing in AI/ML/Data Engineer JDs. Data Engineer = 0.0, ML Engineer = 0.0, Systems Architect = 0.0 → hard-rejected at 92% rate.
- **Fix:** Added target-function escape hatch in `_tag_jobs_with_ontology()`. Full phrase match in title → 1.0. Distinctive word (ai/data/ml/systems) + job noun (engineer/manager) → 1.0. Generic-only → no credit. Sales Manager, Mechanical Engineer still reject at 0.0.
- Also gated `remoteok`, `remotive`, `weworkremotely` behind `city == "remote"` — these US/EU boards produced 60 raw jobs that all died on India filter. Wasted bandwidth removed.
- Result: 7 jobs in brief, 0 false positives.

### JWT Auth — full_name Overwrite Bug
- `_provision_user()` used `full_name or email` in the `ON CONFLICT DO UPDATE` path. When a restored session JWT carries no `user_metadata` (Supabase strips it), `full_name = ""` → `full_name or email` = email → COALESCE overwrote "Siddharth Saminathan" with "siddharth.swami99@gmail.com" every 5-minute TTL cycle.
- **Fix:** Separated INSERT and UPDATE parameters. UPDATE now uses raw `full_name` (not `full_name or email`). `COALESCE(NULLIF(full_name, ''), existing)` correctly returns NULL when JWT carries no name → existing name preserved.
- Verified: 3 sequential `/auth/me` calls with empty `user_metadata` → `full_name = 'Siddharth Saminathan'` each time.

### Supabase PKCE Deadlock — Root Cause of "Taking Longer Than Expected"
- `getHeaders()` in `api.ts` called `supabase.auth.getSession()` to get the Bearer token.
- During OAuth callback (`/brief?code=...`), `onAuthStateChange(SIGNED_IN)` fires, which calls `loadUserProfile()` → `api.getMe()` → `getHeaders()` → `supabase.auth.getSession()`.
- `getSession()` internally waits for the PKCE code exchange to complete — but the exchange is what triggered `onAuthStateChange` in the first place. **Classic deadlock.** Both `POST /v1/auth/me` and `GET /v1/briefs/latest` hung for 15 seconds until AbortController killed them.
- **Fix:** Added `api.setToken(token)` / `api._cachedToken` to `ApiClient`. Token is cached the instant `onAuthStateChange` provides it. `getHeaders()` uses `_cachedToken` first, falls back to `getSession()` only when no cache. Cleared on `SIGNED_OUT`.
- Verified: Console now shows `"Profile response: { ok: true, data: { full_name: 'Siddharth Saminathan' } }"` immediately after OAuth.

### Inspect Page — Blank Screen Fixed
- `RouteBadge` did `config[route].bg` where `route` was `undefined` → uncaught crash → React unmounted the tree → blank screen.
- `serializers.job_detail()` never emitted `recommendation_reason`, `risk_summary`, or `company` (returned `company_name` not `company`). No `user_job_relationships` row existed for unsaved jobs.
- **Fix:** `jobs_repo.get_brief_enrichment()` pulls fit data from `daily_brief_items`. Serializer always emits `company`, non-null `route_recommendation` (fallback: `"APPLY"`). `RouteBadge` null-safe with APPLY fallback.

### BriefPage — Auth Gate
- `BriefPage.loadBrief()` fired before session established on OAuth callback. No token → 401 → 15s timeout.
- **Fix:** `useEffect` now gates on `isAuthenticated` from auth context. Brief only fetches after session is confirmed.

### Verified End State
- 5-message onboarding E2E: 5 different contextual responses, state advances NEW_USER → PROFILE_READY
- CV stored: 5,475 chars in `master_cv_markdown`
- Single `conversation_id` persists across all messages
- 7 jobs in brief (was 2), correct roles, no false positives
- Profile queries answer directly from context, no CV dump
- Auth survives refresh: `full_name` stays correct across multiple TTL cycles

---

## Key Decisions

- **`isAuthenticated = !!session` only** — profile load is enrichment, not auth. Decoupling prevents flaky `/auth/me` from ejecting authenticated users on every refresh.
- **Escape hatch pattern for ontology gate** — instead of tuning `must_have` (fragile, LLM-generated), added a direct title-match override. Target functions are config-driven from `profile_extended.yml`.
- **Token cache in ApiClient, not React state** — React state updates are async and batched. The token cache is synchronous and available immediately. Bypasses the PKCE deadlock at the source.
- **GENERAL_CHAT for field questions, SHOW_PROFILE for document requests** — LLM synthesises focused answers using profile context; no raw CV dump for conversational queries.

---

## Issues Encountered

- Vite HMR reset `AuthProvider` state mid-session during live edits — caused "User / user@example.com" in profile until server was restarted + incognito tab opened.
- Two separate user rows in DB: `siddharth.swami99@gmail.com` (730d5bab) and `siddharthsaminathan99@gmail.com` (b9d04dd0). Debugging was done on the wrong account for one cycle.
- `company_registry_lookup` fails for all companies — passes slug as UUID, triggers SQL type error. Non-blocking (falls back to defaults) but noisy in logs. Needs fix.
- SSE streaming visible but quality still insufficient — events too infrequent, no per-job match/reject visibility during scan. User wants to see discovery happen live.
- Job scores still 45-60 for top matches — ontology gate fixed the quantity problem, but the scoring calibration needs tuning for AI/ML roles in India.
- Dark mode UI needs complete redesign — current dark palette is poor contrast, unpolished.

---

## Files Changed

**Backend:**
- `careerloop/onboarding/onboarding_flow.py` — greetings trap removed, LLM contextual response
- `careerloop_api/services/chat_service.py` — conv_id race condition fixed
- `careerloop/session/action_resolver.py` — SHOW_PROFILE vs GENERAL_CHAT routing improved
- `careerloop/on_demand.py` — ontology gate escape hatch, US remote boards gated
- `careerloop/profile_extended.yml` — `target_functions` expanded, `archetype_gate: 0.15`
- `careerloop_api/deps/auth.py` — `full_name` overwrite bug fixed in `_provision_user()`
- `careerloop_api/repositories/jobs_repo.py` — `get_brief_enrichment()` added
- `careerloop_api/services/job_service.py` — passes enrichment to serializer
- `careerloop_api/services/serializers.py` — `job_detail()` always emits `company`, enrichment fields
- `scripts/sse_scan.sh` — SSE terminal script for live scan streaming

**Frontend (`Career Loop Front End/src/`):**
- `lib/auth.tsx` — `isAuthenticated = !!session`, `onAuthStateChange` only clears on SIGNED_OUT, `api.setToken()` called immediately
- `lib/api.ts` — `_cachedToken` + `setToken()` bypasses PKCE deadlock
- `lib/supabase.ts` — explicit `persistSession: true`, `storage: window.localStorage`
- `pages/BriefPage.tsx` — `isAuthenticated` gate added to `loadBrief` useEffect
- `components/product/RouteBadge.tsx` — null-safe, fallback to APPLY
- `components/product/FitScoreBar.tsx` — null/NaN guard

---

### Frontend Rendering Fixes — Afternoon Session

After the backend agent completed product hardening, a separate frontend pass addressed rendering issues:

#### Profile Rendering (Raw N/A Lists Gone)
- `ProfilePage.tsx` fetches `GET /v1/me/preferences` on mount. Shows Profile Summary Card with Personal Info + Career Profile sections.
- `displayValue()` and `displayList()` utility functions in `types.ts` replace null/undefined/"N/A"/"—" with graceful "Not provided yet" fallbacks.
- `ChatBubble.tsx` profile cards now use `displayValue()` instead of raw `|| "—"`.

#### Scan Artifact Stale Closure (Progress Rollback)
- Lock timeout created a JS closure on `data`. When 1000ms timer fired, it wrote old progress back, overwriting live updates.
- Fix: `dataRef = useRef(data)` updated every render. Timeout reads `dataRef.current` instead of closure `data`.

#### Scan Card Centered → Chat Bubble (Layout)
- ScanArtifact had `mx-auto` → floating centered card. Removed. ChatBubble wraps it in avatar + left-aligned container.

#### CV Extraction Silently Fails (DeepSeek API Key Invalid)
- `sk-5e3258fcab4febcb14d30ef0cc3ff6c` returns 401. Error swallowed by `_call_api()` into fake-success JSON.
- Fix: Rotated key in `.env`. Added `_parse_error` sentinel so onboarding tells user "I had trouble parsing your CV."

#### Chat Persistence Broken (`_active_conversation_id` Destroyed)
- Messages persist in DB (22 rows, 5 conversations). Link to find them destroyed at two sites: `_complete_onboarding()` popped the key, `_handle_idle()` erased the dict.
- Fix: Removed both destruction sites. conv_id survives through onboarding.

#### Saved Jobs Reappearing in Brief
- Same job in both `saved` AND `matched` status. Fix: filter `top_jobs` before brief_items insertion.

#### Duplicate Scan Elimination + 5-Thread Load Test
- `_active_scans_lock` mutex + `_worker_semaphore` (max 3). Proven: 1/5 accepted (200), 4/5 blocked (409) with same run_id.

#### Brief Lifecycle Verified (Clean MECE)
- Zero endpoint mixing, zero leaked logic. Brief = READ ONLY. Copilot = ACT.


## Open Issues for Next Session

### P0
- **SSE streaming UX** — events arrive but frontend renders single card. Backend emits 49 events for 9 jobs; user sees 0%→7%→100% with no per-role visibility.
- **`company_registry_lookup` SQL error** — slug as UUID, noisy logs.

### P1
- **Job score calibration** — top matches 45-60. Default baselines reduced from 5.0→3.0-3.5 but actual distribution not verified post-fix.
- **Dark mode redesign** — poor contrast, unpolished.
- **Scan transparency** — user sees only progress bar during 60s+ Phase A. Needs per-source visibility.

### P2
- Fly.io deployment (Dockerfile + GitHub Actions)
- PostgresSaver checkpointer hardening
- Multi-worker readiness (Redis session cache)
- Score explainability (Role Fit, Location Fit, Skills Fit breakdowns via API)
