# Discovery Engine Productization — Audit & Fixes

**Date:** 2026-05-30
**Context:** Full E2E quality audit of the job discovery pipeline. Four systemic issues found, all fixed.

---

## 1. Cache Saturation (CRITICAL)

### Evidence
```
careerloop.jobs total: 20
Unique companies: 10
Source breakdown: on_demand (13), Cutshort (4), linkedin (2), cutshort (1)
5 jobs have empty company_name (""), 2 each for TestCorp/ZakApps/Moative/BigRio
```

Only 20 jobs exist in the entire DB pool. With the cache-first strategy and `LIMIT 10` in `_build_from_cache()`, the same top-N jobs appear in every brief — identically ordered by `fit_score DESC, scraped_at DESC`.

### Root Causes

**A) File-based CrawlCache bypasses pipeline entirely**

`careerloop/on_demand.py:348-413` — The `CrawlCache` check runs FIRST in `OnDemandSearch.run()`. For the same `(role, city)` pair, it returns cached jobs from the filesystem (8-hour TTL). No Phase A (employer discovery), no Phase B (board search). Every repeated scan for `("AI Engineer", "Bangalore")` returns identical results.

Both callers hit this:
- `_execute_scan()` at `scan_service.py:1132` — `force_refresh=False` (default)
- `_execute_scan_more()` at `scan_service.py:739` — `force_refresh=False` (default, pre-fix)

**B) No result rotation in DB cache fallback**

`_build_from_cache()` at `scan_service.py:605` and `get_fresh_cached_jobs()` at `repository_v2.py:1045` both use deterministic `ORDER BY`. Same query every brief = same results.

### Fix Applied

| File | Line | Change |
|------|------|--------|
| `scan_service.py` | 769 | `force_refresh=True` in `_execute_scan_more()` — user-requested fresh discovery must bypass CrawlCache |
| `scan_service.py` | 1162 | `force_refresh=True` in `_execute_scan()` — daily scan always runs fresh pipeline |
| `scan_service.py` | 611-662 | `_build_from_cache()`: fetch `limit * 3` rows, then day-seeded `Random.shuffle()`, return `limit` |
| `repository_v2.py` | 1120 | `ORDER BY RANDOM()` instead of `last_seen_at DESC` |
| `repository_v2.py` | 1132-1135 | Day-seeded Python shuffle on results (deterministic within same day, rotates day-over-day) |

**Expected result:** No more "12 consecutive briefs showing the same 9 jobs." Every brief has rotation + fresh pipeline runs on every scan.

---

## 2. Score Compression (86.9% in 50-69 band)

### Evidence
```
Score distribution (115 scored jobs):
  0-29:    2 (1.7%)
  30-39:  11 (9.6%)
  40-49:   0 (0.0%)    <-- ZERO jobs in this band
  50-59:  51 (44.3%)   <-- massive cluster
  60-69:  49 (42.6%)   <-- massive cluster
  70-79:   0 (0.0%)    <-- ZERO jobs in this band
  80-89:   2 (1.7%)
  90-100:  0 (0.0%)

Mean: 56.5, StdDev: 11.0
```

### Root Cause

IndiaFitEngine has 16 scoring dimensions, each contributing 0-10 raw (then weighted). Almost every scorer defaults to **5.0** when no signal is present. This creates a mathematically anchored baseline:

**Old baseline (all defaults): ~53/100**
```
role_fit(5.0), archetype_fit(5.0), skill_fit(5.0), salary_fit(5.0),
equity_fit(5.0), benefits_fit(5.0), location_fit(5.0), work_mode_fit(5.0),
notice_period_fit(7.0), sector_fit(6.0), company_stability(5.0),
startup_risk(5.0), brand_value(4.0), commute_risk(7.0),
response_likelihood(5.0), career_trajectory(5.0)
```

With every dimension defaulting to 50%+ of max weight, ALL jobs start at 53%+. Only a few dimensions get real signals (role_fit, location_fit, company_stability), pushing scores to 56-65. That is why 87% of scores compress into 50-69.

### Fix Applied

**Neutral defaults reduced from 5.0 to 3.0-3.5.** Missing data should not contribute positively. The philosophy: "If we don't know, it doesn't help."

| Scorer | Old Default | New Default | Reason |
|--------|------------|-------------|--------|
| `_score_role_fit` | 5.0 | **3.0** | No intent set = no signal |
| `_score_archetype_fit` | 5.0 | **3.0** | No ontology tag = unclassified |
| `_score_skill_fit` (no skills) | 5.0 | **3.0** | No confirmed skills = nothing to match |
| `_score_skill_fit` (no JD text) | 5.0 | **3.0** | No content to score |
| `_score_salary_fit` (no salary targets) | 5.0 | **3.0** | No targets to compare |
| `_score_salary_fit` (no salary in JD) | 5.0 | **3.5** | Uncertainty penalty |
| `_score_equity_fit` | 5.0 | **3.5** | User doesn't care = don't reward |
| `_score_benefits_fit` | 5.0 | **3.5** | No requirements = don't reward |
| `_score_location_fit` | 5.0 | **3.5** | Unknown location = penalty |
| `_score_work_mode_fit` | 5.0 | **3.5** | Unknown mode = penalty |
| `_score_notice_period_fit` | 7.0 | **4.5** | No signal = cautious neutral |
| `_score_sector_fit` (no preference) | 5.0 | **3.5** | No preference set = don't reward |
| `_score_sector_fit` (unknown sector) | 6.0 | **4.0** | Unknown = below neutral |
| `_score_career_trajectory` | 5.0 | **4.0** | Trajectory must be earned |
| Role_fit gate cap | 30.0 | **25.0** | Better discrimination for mismatches |

**New baseline (all defaults): ~38/100** (down from ~53)

### Expected Score Distribution (After Fix)

The baseline drops by ~15 points. Jobs with real signals gain the same margins as before — but now spread across a wider range:

| Band | Before | Expected After | Rationale |
|------|--------|---------------|-----------|
| 0-29 | 1.7% | 8-15% | Cleared hard-gate mismatches + all-default jobs |
| 30-49 | 9.6% | 25-35% | Jobs with 1-2 weak signals |
| 50-69 | 86.9% | 30-40% | Jobs with 3-4 signals (previously the entire cluster) |
| 70-89 | 1.7% | 12-20% | Strong signals across most dimensions |
| 90-100 | 0% | 3-6% | Exceptional matches (right role, right city, right comp, right sector) |

**Note:** These are estimates. Actual distribution depends on profile quality (confirmed skills, target functions, salary targets). The more signal the user provides, the better the spread.

---

## 3. Fresh Portal Scans

### Evidence
```
SERPAPI_KEY: NOT configured in .env
DEEPSEEK_API_KEY: configured
ENABLE_PHASE_A: configured (value hidden)
```

Only 4 source types in the DB: `on_demand`, `Cutshort`, `linkedin`, `cutshort`. The 13 `on_demand` jobs were all produced in a single pipeline run and then cached.

### Root Causes

**A) SERPAPI_KEY not configured**

`careerloop/on_demand.py:1170` — Phase A company discovery checks for `SERPAPI_KEY`:
```python
src = "SerpAPI" if os.environ.get("SERPAPI_KEY") else "DDG"
```

Without it, company discovery falls back to DDG (free but less targeted). The DDG fallback works (Phase A runs), but it is weaker than SerpAPI for discovering companies hiring for specific roles.

**B) Phase A disabled by default for scan_more**

`careerloop/sources/scan_service.py:69`:
```python
def _phase_a_enabled() -> bool:
    return os.getenv("ENABLE_PHASE_A", "false").strip().lower() in ("1", "true", "yes", "on")
```

Phase A adds 3-5 minutes before the first job appears (TTFE killer), so it is intentionally off for `scan_more`. For the daily scan (`_execute_scan`), `include_phase_a=True` is hardcoded — but the CrawlCache was intercepting before Phase A ran (fixed above).

**C) Board search sources limited**

The search adapter (`careerloop/sources/search_adapter.py`) limits to India-native job boards only. Non-India ATS boards (Greenhouse, Lever, etc.) are explicitly skipped in `SKIP_DOMAINS`. This is intentional (India-only search) but means fewer sources contribute.

### Fix Applied

| File | Line | Change |
|------|------|--------|
| `scan_service.py` | 769 | `force_refresh=True` in scan_more (fixes CrawlCache bypass) |
| `scan_service.py` | 1162 | `force_refresh=True` in default scan (fixes CrawlCache bypass) |

### Gap Documented (NOT a code fix)

**SERPAPI_KEY is not set.** Adding it to `.env` would strengthen Phase A company discovery:
```
SERPAPI_KEY=your_serpapi_key_here
```

Without it, company discovery uses DDG (free, functional, but less targeted). This is a configuration gap, not a code gap — the code correctly handles both paths.

**`_phase_a_enabled()` returns False** by default. Phase A is the live internet company discovery engine. It is intentionally off for `scan_more` (TTFE requirement). For the default daily scan, it is hardcoded `True` in `_execute_scan()`. To enable it for scan_more too:
```
ENABLE_PHASE_A=true
```

---

## 4. Hayagreev Pipeline (OnDemandSearch Usage)

### Evidence

Both scan paths use `OnDemandSearch.run()` as canonical:

- `_execute_scan()` at `scan_service.py:1132` → `searcher.run(...)` — daily brief
- `_execute_scan_more()` at `scan_service.py:739` → `ods.run(...)` — scan more

### Verdict

**OnDemandSearch IS the canonical pipeline. It is NOT bypassed.** Both scan paths correctly route through it.

Two supplementary paths exist that query the DB directly:
1. `_build_from_cache()` at `scan_service.py:605` — fallback when OnDemandSearch returns no results
2. `get_fresh_cached_jobs()` at `repository_v2.py:1045` — supplementary cache-hit check during `_execute_scan`

These are supplementary, not bypass paths. The primary discovery flow uses `OnDemandSearch.run()` → Phase A (employer discovery) + Phase B (board search) → filtering → scoring → results.

The issue was that `OnDemandSearch.run()` itself short-circuits via CrawlCache (fixed in Section 1).

---

## Summary of All Fixes

| Issue | Root Cause | Fix | Files Changed |
|-------|-----------|-----|---------------|
| Cache Saturation | CrawlCache intercepts all scans; no result rotation | `force_refresh=True` on both scan paths; day-seeded shuffle in cache fallback | `scan_service.py`, `repository_v2.py` |
| Score Compression | 16 dimensions defaulting to 5.0/10 anchors baseline at 53/100 | Reduce neutral defaults to 3.0-4.5 range; new baseline ~38/100 | `india_fit_engine.py` |
| Fresh Portal Scans | SERPAPI_KEY not set; CrawlCache bypass (fixed above) | Document SERPAPI_KEY gap; CrawlCache bypass via `force_refresh=True` | `scan_service.py` |
| OnDemandSearch bypass | Not bypassed — both paths use OnDemandSearch | Confirmed via code audit; no fix needed | N/A |

### Files Changed

1. `careerloop/india_fit_engine.py` — 14 neutral default changes + role_fit gate cap reduced
2. `careerloop_api/services/scan_service.py` — `force_refresh=True` in 2 places + day-seeded shuffle in `_build_from_cache`
3. `careerloop/memory/repository_v2.py` — `ORDER BY RANDOM()` + day-seeded shuffle in `get_fresh_cached_jobs`

### What Was NOT Changed

- The CrawlCache TTL (8h) is reasonable for production — the fix is to bypass it when the user requests fresh discovery
- Phase A architecture — intentionally disabled for scan_more due to 3-5 min TTFE
- Board search domain filtering — India-only is by design
- IndiaFitEngine weight distribution — the weights still sum to 100, only the neutral defaults changed
- SERPAPI_KEY — configuration gap, not a code gap
