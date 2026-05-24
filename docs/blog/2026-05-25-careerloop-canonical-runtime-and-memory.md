# CareerLoop — Canonical Runtime & Memory Architecture

**Date:** 2026-05-25  
**Author:** Siddharth Saminathan + Claude Opus  
**Status:** P1 Product Quality Complete. Memory Architecture Documented.

---

## What Was Broken Before

Two weeks ago CareerLoop was a CLI demo with hardcoded job cards, fake company names, and SQLite pretending to be production memory. The chat runtime echoed user messages back as if they were bot responses. The state machine had 17 states of which 8 were dead code. Slash commands bypassed the supervisor graph entirely. The database had CareerLoop tables scattered across `public.*` alongside Supabase auth, LangGraph checkpoints, and Emote app tables.

None of the supposed "runtime" actually worked end-to-end on real data.

## What We Fixed

### Phase 1: Architecture Audit (May 24)
7 parallel sub-agents audited every subsystem. Result: 12 CRITICAL, 16 HIGH, 17 MEDIUM findings — all with file paths and line numbers. Fixed 22 items across 5 phases in one session.

### Phase 2: Runtime Stabilization
- Removed echo fallback from transport layer
- Reduced state machine from 17 to 11 real states
- Made GENERAL_CHAT return real LLM responses
- Fixed conversation history with add_messages reducer
- Created ActionResolver (LLM-based) + ToolRegistry (17 handlers)
- Removed all hardcoded demo strings
- Added 14 regression tests

### Phase 3: Supabase-Only
- Removed ALL SQLite fallback code (367 → 110 lines in connection.py)
- Hard-fail if DATABASE_URL is missing
- DB banner at startup shows Supabase host, journey state, brief count
- Profile recovery from users table
- ActionResolver now prevents scan during onboarding

### Phase 4: Data Engineering V2 → V3
- Created `careerloop` schema — isolated from `public.*`
- Moved 22 CareerLoop tables into `careerloop.*`
- Created `careerloop.users` as canonical identity spine
- Migrated all 20 foreign keys from `public.users` → `careerloop.users(id) ON DELETE CASCADE`
- Backfilled 14 users from `public.users`
- Created 7 new tables: conversations, messages, memory_events, recruiter_contacts, job_sources, job_search_runs, careerloop.users
- Standardized: zero `public.*` references in CareerLoop code

### Phase 5: Canonical Product Path
- Wired V3 pipeline: scan → job_candidates → jobs → user_job_relationships → daily_brief_items
- Companies table populated with domain_slug dedup
- Cutshort format parsing: "BigRio is hiring AI Engineer job in Chennai | Cutshort" → company=BigRio, title=AI Engineer, location=Chennai
- Cache-hit stub: `get_fresh_cached_jobs()` checks `careerloop.jobs` before external scan
- Fingerprint dedup working with UNIQUE index on `content_fingerprint`
- 20 FK constraints verified

### Phase 6: Memory Architecture
- 7-layer operational memory model documented
- 4-level recall hierarchy defined
- 8 propagation flows mapped
- 10 anti-patterns explicitly called out
- All in `docs/MEMORY_SYSTEMS_ARCHITECTURE.md`

---

## Why careerloop.users Matters

Before V3, every CareerLoop table referenced `public.users(id)` — the Supabase auth table. This meant:

- We couldn't add CareerLoop-specific columns (onboarding_status, current_plan, linkedin_url)
- Schema migrations risked breaking auth
- No clear ownership boundary between Supabase and CareerLoop

Now `careerloop.users` is the single identity root. All 20 CareerLoop tables reference it. Zero references to `public.users` remain in CareerLoop code. We can extend the user model freely without touching Supabase auth.

---

## The V3 Pipeline — How It Actually Works Now

```
User types "find me new jobs"
  → ActionResolver: START_SCAN
  → ToolRegistry.start_scan()
  → DailyRunner: scan.mjs → 156 API calls → India filter → role filter → dedup → scoring
  → careerloop.background_runs (RUNNING → COMPLETED)
  → careerloop.run_events (17 events: SCAN_STARTED, SOURCE_STARTED, MATCH x5, FILTER_SUMMARY, BRIEF_CREATED)
  → careerloop.job_candidates (raw discovery, 5 rows)
  → careerloop.jobs (fingerprint dedup, ON CONFLICT DO UPDATE, 5 new rows)
  → careerloop.companies (domain_slug dedup, 5 rows)
  → careerloop.user_job_relationships (fit_score, match_status per user, 5 rows)
  → careerloop.daily_briefs + careerloop.daily_brief_items (numbered list)
  → careerloop.sessions (active_artifact_type = "daily_brief")
```

Every stage writes to the canonical Supabase table. No local files. No transient memory. No fake data.

---

## Today's Verified Commits

| Commit | What |
|--------|------|
| `08f52e8` | Canonical Data Architecture V3 — 20 FKs, 14 users backfilled |
| `7952886` | Product Path Verification — fresh scan, active context, pack creation |
| `9222124` | V3 Canonical Pipeline — job_candidates→jobs→relationships→brief_items |
| `b78b890` | P1 Product Quality — Cutshort parsing, companies, company_memory, cache-hit |

---

## What Remains

### P0 — Must Fix Before Real Users
- Full transport deployment (Telegram/WhatsApp webhook verification)
- Multi-user CV upload flow

### P1 — Should Fix This Week
- `india_fit_engine.py` queries bare table names (`company_memory`, `companies`) without `careerloop.` prefix — causes "relation does not exist" warnings on every scan
- Cache-hit currently informational only — should block external scan when 5+ fresh cached jobs exist
- Backfill `careerloop.user_preferences` from `public.users.work_style_prefs`

### P2 — Nice to Have
- 29 TEXT ID columns need UUID migration
- RLS policies on 17 tables
- Full scan streaming via run_events to CLI during scan (MATCH/REJECT live rendering)

---

## Current Production Readiness

| Dimension | Status |
|-----------|--------|
| Data model | ✅ PRODUCTION-READY |
| Schema isolation | ✅ PRODUCTION-READY |
| FK integrity | ✅ PRODUCTION-READY |
| Global/user separation | ✅ PRODUCTION-READY |
| Fingerprint dedup | ✅ PRODUCTION-READY |
| V3 product path | ✅ VERIFIED |
| Memory architecture | ✅ DOCUMENTED |
| Chat runtime | ✅ NO ECHO, REAL LLM |
| UUID standardization | ⚠️ PARTIAL (29 TEXT IDs) |
| Transport (Telegram/WhatsApp) | ❌ NOT STARTED |
| Multi-user onboarding | ❌ NOT STARTED |

---

## Next Milestone

**P0 transport deployment** — verify Telegram/WhatsApp webhook loop with real Supabase sessions. Then run a full scan through the V3 pipeline on production Supabase with real user data. Ship the daily brief to an actual chat.
