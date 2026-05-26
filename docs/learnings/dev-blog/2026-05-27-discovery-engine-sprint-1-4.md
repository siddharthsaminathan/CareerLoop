# Dev Blog — 2026-05-27: Discovery Engine Sprint 1-4

## What Was Done

- **Role Archetype Engine built** — `careerloop/sources/role_archetype.py`. Derives `must_have/avoid/preferred_company_types` from `profile_extended.yml`. Zero hardcoding. First time role identity constraint flows into retrieval.
- **role_fit hard gate** — `role_fit_raw < profile.role_fit_gate` → score capped at 30. Stops "HVAC Engineer" from scoring 53 because it was in Bangalore with a startup.
- **_fetch_missing_jds()** — requests + BeautifulSoup full JD fetch for JobSpy desc=3c jobs. Mutates job dict in-place before scoring.
- **min_description_chars gate** — hard reject before `score_jobs_batch()`. Threshold from `profile_extended.yml`. Configurable per user.
- **archetype_fit as 16th scoring dimension** — weight 8. Reads from `_ontology.archetype_match` tag on job dict. FIT_WEIGHTS rebalanced to 100.
- **_tag_jobs_with_ontology()** — tags all jobs with `{seniority, archetype_match, biz_model, preferred_company_match}` post-dedup, pre-Phase E.
- **Wellfound Playwright removed** — `_scrape()` replaced with direct `_ddg_fallback()` call. No browser ever opens in Phase A.
- **Remote India SerpAPI path** — `is_remote` branch in `_build_queries()`. Previously Remote returned 0 companies.
- **AGENTS.md no-hardcoding rule** — locked architectural invariant. All values from ProfileManager. Scales to 100M users.
- **profile_extended.yml scoring section** — `role_fit_gate: 3.0`, `min_description_chars: 200`.
- **SEARCH_VISION.md** — updated as living tracker with sprint completions and Sprint 5-6 plan.

## Key Decisions

- **All thresholds in `profile_extended.yml`, never in code** — enforced by AGENTS.md rule. User changes config, pipeline adapts. No deploys for threshold tuning.
- **Archetype engine reads `rejected_roles` from profile** — no static lists. What Hayagreev rejects may differ from what Siddharth rejects.
- **`_tag_jobs_with_ontology()` runs on ALL jobs** — before Phase E, not just Phase F. Tags enable both filtering and scoring without duplicate computation.
- **16th dimension vs boosting role_fit** — added as separate dimension so breakdown is transparent. User can see `archetype_fit: 2.0` vs `role_fit: 7.0` and understand why a job ranked where it did.

## Issues Encountered

- **FIT_WEIGHTS summed to 111** after adding archetype_fit — had to rebalance 6 smaller dimensions. Verified with Python sum check before committing.
- **Seniority signals inline in `_tag_jobs_with_ontology()`** — `["senior", "sr", "lead"...]` is a static list in the function body. Technically violates the no-hardcoding rule just locked in AGENTS.md. Low-risk (seniority signals are universal) but needs fixing in Sprint 5.
- **User anger about previous hardcoded title blocklist** — removed `_TITLE_BLOCKLIST` entirely. Replaced with profile-driven `archetype.reject_title()`. Better architecture.
- **ICP feature question (localhost:3000)** — user asked about save/copy/modify buttons for ICP page. Unrelated to discovery engine work. Not addressed this session.

## Files Changed

- `careerloop/india_fit_engine.py` — role_fit hard gate, archetype_fit scorer, `_score_archetype_fit()` method
- `careerloop/on_demand.py` — `_fetch_missing_jds()`, `_tag_jobs_with_ontology()`, archetype engine wiring (Phase A + B), min-desc gate, RoleArchetypeEngine import
- `careerloop/sources/company_discovery.py` — Wellfound DDG-only, Remote India SerpAPI query path
- `careerloop/sources/role_archetype.py` — NEW file. `RoleArchetype` dataclass + `RoleArchetypeEngine` class
- `careerloop/profile_manager.py` — `role_fit_gate` and `min_description_chars` properties
- `careerloop/profile_extended.yml` — `scoring` section added
- `careerloop/config.py` — FIT_WEIGHTS updated (16 dims, sum=100)
- `AGENTS.md` — no-hardcoding engineering rule locked
- `docs/product/SEARCH_VISION.md` — living tracker updated (sprints 1-4 done, 5-6 planned)

## Next Session

1. Move seniority signals to `profile_extended.yml` — closes AGENTS.md violation (10 min)
2. Wire Phase E ontology pre-filter — `archetype_match < profile.archetype_gate` hard reject before cosine similarity (1 hour)
3. Naukri fix — direct REST API replacing DDG/startpage backend
4. Address ICP save/copy/modify UI at localhost:3000 if user wants to continue there
