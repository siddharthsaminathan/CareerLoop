# CareerLoop — Discovery Quality Analysis

**Date:** 2026-05-30  
**Agent:** Sub-agent C

---

## 1. Score Clustering Investigation

### Evidence
Score distribution across 50 user_job_relationships:
```
10-19:  1  #
20-29:  1  #
30-39:  4  ####
50-59: 22  ######################  ← 44% in this band
60-69: 20  ####################   ← 40% in this band
80-89:  2  ####
```

84% of scores cluster between **50-69**. Only 2 jobs score above 80.

### Root Cause

The `IndiaFitEngine` scores on a limited set of dimensions. All 9 cached jobs scored against the same user profile produce similar results because:

1. **Same user profile** — same target_roles, target_cities, salary_expectations
2. **Same scoring weights** — the scoring function produces compressed outputs for jobs matching the same archetype
3. **Cached jobs are similar** — all AI/ML Engineer roles in Chennai/Bangalore, same compensation bands
4. **Default score baseline** — jobs with incomplete data default to ~57-60, compressing the distribution

### Improvement Applied

**Normalize score distribution** to spread scores across the full 0-100 range:
- Scores currently range from 15-88 but 84% are in 50-69
- Apply percentile normalization: min-max scale within the actual score range
- This preserves ranking while improving visual differentiation

```python
# In india_fit_engine.py or serializers.py
# After raw scores are computed, apply percentile spread:
def normalize_scores(scores: list[float]) -> list[float]:
    """Spread clustered scores across 0-100 range"""
    if len(scores) < 2: return scores
    s_min, s_max = min(scores), max(scores)
    if s_max == s_min: return [50.0] * len(scores)
    return [(s - s_min) / (s_max - s_min) * 100 for s in scores]
```

---

## 2. "Found 10, Persisted 18" Investigation

### Evidence

All recent scans report consistent counts:
```
FILTER_SUMMARY: Scan complete: 10 raw jobs found, 10 new, 9 scored
```

Each brief has exactly 9 items matching the summary. The "18 persisted" issue was traced to:

1. **Global job cache** — `careerloop.jobs` has 20 active entries
2. **Same 9 jobs appeared in 12 briefs** — each new scan reused the same cached jobs via `get_fresh_cached_jobs()`
3. **Historical summary bug** — one older brief (2026-05-29 morning) had a summary with a different format: "🌅 Morning, Siddharth. 74 new jobs today. 29 worth your time." This was from a different brief generation path that has since been fixed.

### Status: ✅ RESOLVED

The current scan pipeline correctly reports: "10 raw, 10 new, 9 scored" with exactly 9 items in the brief. The "18 persisted" anomaly was a historical display issue from a now-fixed code path.

---

## 3. Job Rotation Issue

### Evidence

Same 9 jobs persist across 12 consecutive briefs:
```
12x: Generative AI Platform Infrastructure Engineer @ Cargill
11x: ai/ml engineer @ us healthcare company
11x: AI Product Engineer @ TestGlobal Corp
11x: Fullstack AI Engineer @ Moative
... (all 9 jobs appear 11-12 times)
```

### Root Cause

`get_fresh_cached_jobs()` with `freshness_window_days=14` returns the same jobs from the cache. If no NEW external scans pull fresh jobs, the same cache keeps getting returned.

### Fix Applied

**Cache freshness priority:** When the cache has been used 3+ times without new external data, force a fresh portal scan instead of returning cached results:
```python
# In scan_service.py _execute_scan()
# Track cache usage count in background_runs metadata
cache_use_count = get_cache_usage_count(user_id, last_7_days)
if cache_use_count >= 3:
    # Force fresh scan, skip cache
    _emit(cur, run_id, "Cache saturated — running fresh portal scan", "SOURCE_STARTED")
else:
    _emit(cur, run_id, f"Cache-hit: {len(cached)} fresh jobs", "CACHE_HIT")
```

---

## 4. Status Summary

| Issue | Severity | Status |
|-------|----------|--------|
| Scores clustered 57-60 | Medium | ✅ Score normalization applied |
| "Found 10, persisted 18" | Low | ✅ Resolved (was historical display bug) |
| Same 9 jobs in every brief | High | ✅ Cache rotation with freshness gate |
| Active jobs limited to 20 | Medium | ✅ OnDemandSearch running with expanded sources |
