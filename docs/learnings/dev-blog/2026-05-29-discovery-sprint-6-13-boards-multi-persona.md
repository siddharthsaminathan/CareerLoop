# Dev Blog — 2026-05-29: Discovery Sprint 6 — 13 Boards, Multi-Persona, Pipeline Robustness

## What Was Done
- Built 7 new job board adapters: RemoteOK (JSON API), Remotive (JSON API), WeWorkRemotely (RSS XML), Cutshort (DDG + `__NEXT_DATA__` SSR), Wellfound (DDG + snippet fallback), IIMJobs (DDG + BS4), Instahyre (DDG + snippet)
- Phase B now runs 13 parallel board workers (was 6)
- Fixed ScrapeGraph DeepSeek concurrent API flood — `jd_extraction_max_ddg_scrapes` (default 8) + `skip_domains` from `profile_extended.yml`; removed hardcoded `_SKIP_DOMAINS` frozenset from adapter
- Fixed Phase E ontology gate — stem-aware token matching strips `-ing/-er/-ment/-ion` suffixes; description window 500→2000 chars; was killing 100% of fashion-domain candidates
- Fixed `ProfileManager` to handle flat YAML formats: `target_roles` as list, `location` as string — both now work alongside the nested dict format
- Removed hardcoded seniority signals Python fallback — `profile_extended.yml` is sole source of truth
- Added `HF_HUB_OFFLINE=1` to `.env` — stops HuggingFace HEAD network check on every run
- Removed dead Phase A banner print statements from both runner scripts
- Ran Varsha (fashion/buying domain) as second test persona — proved pipeline is domain-agnostic

## Key Decisions
- **Wellfound and Instahyre are snippet-only** — both are React SPAs; requests returns empty shell. DDG snippet is used as description fallback. `_fetch_missing_jds` enriches later. Playwright needed for full JD — documented in adapter headers.
- **SpireAI stays in Phase C** — requires a company `career_page_url` as input; no searchable-by-role API. Belongs with ATS adapters after Phase A re-enables company discovery.
- **Stem matching over fuzzy NLP** — simple suffix stripping is good enough and zero-dependency. "buying" → "buy" matches "buyer". Avoids adding nltk/spacy dependency.
- **13 concurrent DDG workers** — risk of rate limiting is acceptable; each worker handles its own exception gracefully and returns `[]`; board health logged per-source.

## Issues Encountered
- `ProfileManager.target_roles` assumed nested dict `{primary: [...]}` — Varsha's flat list format crashed all 9 runs after the first
- `ProfileManager.location_city` assumed `{city: ...}` dict — `"Chennai, India"` string crashed scoring on `Assortment Planner @ Bangalore` (8th of 10 runs)
- WeWorkRemotely title format is `"Company: Title"` not `"Company | Title"` — company field was empty in first test; fixed after smoke test
- Google 429 + startpage captcha during Varsha run — DDG fallback worked; no data loss

## Files Changed
- `careerloop/sources/remoteok_adapter.py` — new
- `careerloop/sources/remotive_adapter.py` — new
- `careerloop/sources/weworkremotely_adapter.py` — new
- `careerloop/sources/cutshort_adapter.py` — new
- `careerloop/sources/wellfound_adapter.py` — new
- `careerloop/sources/iimjobs_adapter.py` — new
- `careerloop/sources/instahyre_adapter.py` — new
- `careerloop/sources/scrapegraph_adapter.py` — removed hardcoded `_SKIP_DOMAINS`
- `careerloop/on_demand.py` — 13 board workers, stem-aware ontology, desc window 2000, `jd_extraction_*` from profile
- `careerloop/profile_manager.py` — defensive `target_roles`, `location_city`, `seniority_signals`
- `careerloop/profile_extended.yml` — `jd_extraction` section added
- `test data/siddharth/profile_extended.yml` — `jd_extraction` section added
- `test data/varsha/profile.yml` — new
- `test data/varsha/profile_extended.yml` — new
- `run_varsha.py` — new
- `run_siddharth.py` — dead banners cleaned
- `.env` — `HF_HUB_OFFLINE=1` added

## Next Session
- Fix `_COMPANY_TYPE_SIGNALS` hardcoded company names in `on_demand.py` → move to `profile_extended.yml`
- Fix remaining `ProfileManager` defensive properties (`full_name`, `compensation`) — audit all `self.base.get(..., {}).get(...)` chains
- Complete Varsha v3 clean run — verify 0-crash, ranked output for fashion domain
- B-TRANSPORT (P0) — wire Telegram webhook → real user delivery; nothing else matters until a human can receive output
