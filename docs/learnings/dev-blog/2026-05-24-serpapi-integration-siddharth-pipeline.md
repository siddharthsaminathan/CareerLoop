# Dev Blog — 2026-05-24: SerpAPI Integration + Siddharth Full Pipeline Run

## What Was Done

- Added `SerpAPIDiscovery` class to `company_discovery.py` — real Google results via REST, 2-call hard cap, intent-based queries targeting funded AI companies
- Rewrote `careerloop/memory/connection.py` with SQLite dual-mode — PostgreSQL when `DATABASE_URL` set, SQLite fallback when absent; unblocks all local dev runs without Supabase
- Added `force_refresh` param to `OnDemandSearch.run()` — bypasses crawl cache for repeatable test runs
- Rewrote `run_siddharth.py` with `TeeOutput` (stdout + audit log), per-phase banners, 4 roles × 3 cities × 60 max
- Ran full v4 pipeline: 4 roles × Bangalore → 114 ranked jobs in ~40min
- Audited 114 jobs: top quality (Sarvam AI 73.1, Glean Greenhouse, Altimate.ai Ashby), 4 bad jobs leaking (HVAC×2, Intern, Mechanical — all <57 score, filtered by rank)

## Key Decisions

- **2-call SerpAPI cap**: User constraint — API credits are limited. Forced intent-based query construction (role-aware + funding-aware + anti-body-shop) to extract maximum signal from 2 calls instead of 6
- **SQLite fallback over Supabase requirement**: CTO's new `connection.py` required PostgreSQL unconditionally — broke all local runs. Dual-mode keeps prod using Supabase, dev using SQLite, callers unchanged
- **`force_refresh` over cache bypass**: Preserves caching for prod runs while enabling repeatable test pipelines

## Issues Encountered

- **Score compression**: JobSpy returns 500-char snippets → scorer has no meaningful signal → all jobs cluster 60-64. Ranking within that band is noise. Fix requires full JD fetch for JobSpy URLs before scoring
- **Mumbai/Remote ATS gap**: Company DB not seeded for those cities → 0 ATS portal coverage on city-specific searches. Boards filled the gap but ATS portals (Greenhouse/Lever/Ashby) were unreachable
- **4 bad jobs leaking**: HVAC, Mechanical, Intern roles still reach the ranked output at score <57. Current filter kills them by rank position, not by type. Title blocklist would be cleaner
- **Naukri via startpage rate-limiting**: `ConnectError` to `startpage.com` — non-critical, 5 other sources covered the gap

## Files Changed

- `careerloop/sources/company_discovery.py` — `SerpAPIDiscovery` class, `_build_queries` 2-call cap
- `careerloop/memory/connection.py` — full dual-mode rewrite (SQLite shim + PostgreSQL branch)
- `careerloop/on_demand.py` — `force_refresh` param, Phase A log message updated
- `run_siddharth.py` — complete rewrite with `TeeOutput`, phase banners, 3-city expansion
- `.env` — `SERPAPI_KEY` added
- `.env.example` — `SERPAPI_KEY` documented

## Next Session

- Fix score compression: fetch full JD text for JobSpy URLs before scoring → restore 0-100 score spread
- Seed Mumbai/Remote company DB via Phase A-only discovery run
- Add title blocklist to filter (HVAC/Mechanical/Hardware/Intern/Contract Staffing keywords) at Phase E, not Phase F
