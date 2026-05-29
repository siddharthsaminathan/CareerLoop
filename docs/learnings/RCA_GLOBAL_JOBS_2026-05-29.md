# RCA: Global Jobs + Uniform 70.0 Scores — May 29, 2026

**User:** siddharth.swami99@gmail.com (Chennai, Bangalore, Bengaluru, Remote)

---

## EXECUTIVE SUMMARY

**Root Cause:** The `scan_more` path (`_execute_scan_more`) has zero location filtering. It scrapes ALL companies globally, matches by title keyword only, and writes directly to `daily_brief_items` with a hardcoded score of 70.0. The location filter (`_is_india_location`) exists in `ats_adapter.py` and `daily_runner.py` but is never called from the `scan_more` code path.

---

## THE CHAIN

```
User clicks "Scan More"
  → scan_service.py:initiate_scan(mode="scan_more")
    → _execute_scan_more() (line 388)
      → spawns node scan.mjs (line 436)
        → scan.mjs fetches ALL jobs from Greenhouse/Lever/Ashby
        → NO India location filter in Node.js code
      → collects all SCAN_EVENTs regardless of location
      → _matches_targets(title, target_roles) checks ONLY title keywords
        → "product" from "AI Product Engineer" matches "AI Products" in Intercom (Dublin)
        → "engineer" matches "Forward Deployed Engineer" at ElevenLabs (Singapore)
        → NEVER checks if location is India
      → _append_to_brief() writes to daily_brief_items with HARDCODED score=70.0
      → User sees: Intercom/Dublin, N26/Berlin, HelloFresh/NYC, ElevenLabs/SF, Mistral/Paris...
```

---

## 3 GAPS — 1 PATH

| # | File | Lines | What's Missing | Severity |
|---|------|-------|---------------|----------|
| **GAP-1** | `scan.mjs` | 296-328 | Node.js scanner has ZERO India location filter. Emits every job from every ATS globally. | 🔴 P0 |
| **GAP-2** | `scan_service.py:_execute_scan_more` | 481-516 | `_matches_targets()` checks only title keywords. Adds job to brief regardless of location. | 🔴 P0 |
| **GAP-3** | `scan_service.py:_load_targets_and_seen` | 542-574 | Reads `target_roles` from DB but NEVER reads `target_cities`. User's city preferences ("Chennai, Bangalore, Bengaluru, Remote") are stored but never applied. | 🔴 P0 |

---

## SCORE REGRESSION — 70.0

| Source | File | Line | Value |
|--------|------|------|-------|
| `_append_to_brief()` hardcoded | `scan_service.py` | 573 (fixed in 9b27679) | `70.0` |
| `_build_from_cache()` default | `scan_service.py` | 367 | `65.0` |
| `_compute_title_match_score()` keyword overlap | `scan_service.py` | ~610 | 50.0–85.0 |

**Result:** All 12 brief items for this user have score=70.0 because:
1. `scan_more` path used the hardcoded 70.0 before our fix
2. `_build_from_cache()` uses a JOIN that returns NULL (UUID vs text type mismatch), so default 65.0 was also never used
3. Real LLM scoring (`india_fit_llm.py:score_batch()`) exists but is never called from API scan paths — only from `DailyRunner.run()` which is gated by a sentinel file

---

## DUPLICATE BRIEF ITEMS

Items 1-3 and 4-6 are duplicates (Intercom ×2, N26 ×2, HelloFresh ×2). 

**Root cause:** `_execute_scan` does DELETE all brief_items then INSERT. Two concurrent scans (evidence: 15:20, 17:13, 17:36, 17:48 all have paired runs) race. Both DELETE, both INSERT — everything appears twice.

---

## NON-INDIA JOBS IN CACHE PATH

`_build_from_cache()` (line 343-356) queries `careerloop.jobs` with NO `is_india_role=true` or location WHERE clause. If the jobs cache had non-India entries, they would appear in the brief too. Currently only 7 Indian test jobs are cached, so this gap hasn't surfaced yet.

---

## WHAT ALREADY WORKS

| Path | Location Filter | Score | Status |
|------|----------------|-------|--------|
| `_execute_scan` → `DailyRunner.run()` | ✅ `filter_india_jobs()` (daily_runner:128) + `_india_guard()` (daily_runner:267) | ✅ Real heuristics (variance) | Works correctly |
| `_execute_scan_more` → `scan.mjs` | ❌ No filter anywhere | ❌ Hardcoded 70.0 | BROKEN |
| `_build_from_cache` → SQL query | ❌ No location WHERE clause | ❌ Default 65.0 | BROKEN for non-India |

---

## FIXES NEEDED (2 changes)

### Fix 1: Location filter in `_execute_scan_more`

File: `careerloop_api/services/scan_service.py`, after line ~481

Add India location check before `_append_to_brief()`:
```python
loc = ev.get("location", "")
if loc and not _is_india_location(loc):
    continue  # Skip non-India jobs in scan_more
```

### Fix 2: Location filter in `_build_from_cache`

File: `careerloop_api/services/scan_service.py`, line ~343

Add to SQL WHERE clause:
```sql
AND (j.is_india_role = true OR j.location ILIKE '%india%' OR j.location ILIKE '%bangalore%' OR j.location ILIKE '%chennai%' ...)
```

---

## COMPARISON: Good Path vs Broken Path

| | Default Scan (`_execute_scan`) | Scan More (`_execute_scan_more`) |
|---|-------------------------------|--------------------------------|
| Discovery | `DailyRunner.run()` → portals + ATS | `node scan.mjs` |
| Location filter? | ✅ `filter_india_jobs()` + `_india_guard()` | ❌ NONE |
| City filter from user profile? | ✅ Via `ProfileManager` | ❌ `target_cities` never read |
| Scoring | Real heuristics + IndiaFitEngine | Hardcoded 70.0 → keyword overlap (after fix) |
| Dedup | ✅ `is_duplicate()` | ❌ CONCURRENT RACE CONDITION |
| Jobs persisted to cache? | ❌ P0-1 gap (fixed today) | ❌ P0-1 gap (fixed today) |

**The default scan path is architecturally sound.** The `scan_more` path was bolted on later and inherited zero filtering, zero scoring, zero dedup from the main pipeline.
