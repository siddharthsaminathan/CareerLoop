# CareerLoop User Journey Validation — May 29, 2026

**Test Account:** siddharth.swami99@gmail.com (user_id: 730d5bab)  
**Method:** Live DB queries + code path tracing. No mock data.

---

## USER JOURNEY: Scan → Brief → Inspect → Approve → Pack

---

### 1. SCAN

| Step | Status | What Happens |
|------|--------|-------------|
| **Frontend action** | ✅ | User clicks "Run a Scan" or types `/scan` in chat |
| **API endpoint** | ✅ | `POST /v1/scans` → `ScanService.initiate_scan()` |
| **Backend** | ✅ | Daemon thread runs `DailyRunner.run(do_scan=True)`. Scrapes 52 sources, finds 11 new jobs, appends 3. Emits SSE events. |
| **DB writes** | ⚠️ PARTIAL | Writes to `careerloop.daily_briefs` + `careerloop.daily_brief_items` + `careerloop.background_runs` + `careerloop.run_events`. Does NOT write to `careerloop.jobs`. |
| **User sees** | ⚠️ Brief with 6 items. All scores = 70.0 (identical — scoring is broken). Items reference phantom job_ids not in `careerloop.jobs`. |

### 2. BRIEF

| Step | Status | What Happens |
|------|--------|-------------|
| **Frontend action** | ✅ | Navigate to `/brief` or `/briefs/latest?offset=0` |
| **API endpoint** | ✅ | `GET /v1/briefs/latest` → `BriefService.latest()` |
| **Backend** | ✅ | `BriefsRepo.get_latest_brief()` returns brief + 6 items |
| **DB reads** | ✅ | `careerloop.daily_briefs` + `careerloop.daily_brief_items` |
| **User sees** | ⚠️ 6 job cards: Intercom (2 duplicates), N26 (2 duplicates), HelloFresh (2 duplicates). All scores = 70.0. No summary text (NULL). |

### 3. INSPECT (click job card)

| Step | Status | What Happens |
|------|--------|-------------|
| **Frontend action** | ✅ | Click job card → `navigate(/jobs/{jobId})` |
| **API endpoint** | ✅ | `GET /v1/jobs/{job_id}` |
| **Backend** | ❌ | `GET /v1/jobs/{job_id}` returns **404** because `careerloop.jobs` doesn't have the job. The job_id comes from `daily_brief_items` which references phantom jobs that were never persisted to the jobs cache. |

**INSPECT — What data is displayed today?**

| Item | Status | Evidence |
|------|--------|----------|
| JD | ❌ FAIL | Job not in cache. API returns 404. |
| Match reasoning | ❌ FAIL | No data available. All scores = 70.0 (broken). |
| Recruiter suggestions | ❌ FAIL | `show_people_to_reach()` exists but needs a company name from a real job. |
| Outreach templates | ❌ FAIL | Package generation not wired. No templates surfaced. |
| Company intelligence | ❌ FAIL | `show_company_intel()` only reads from `company_memory` cache. No live intel for brief items. |

### 4. APPROVE

| Step | Status | What Happens |
|------|--------|-------------|
| **Frontend action** | ✅ | Click "Approve" on job card |
| **API endpoint** | ✅ | `POST /v1/jobs/{job_id}/save` |
| **Backend** | ❓ | Calls `JobService.save_job()`. Need to verify what happens with a non-existent job_id. |
| **DB writes** | ❌ | `careerloop.user_job_relationships` has **ZERO rows** for this user. Either save_job silently fails for phantom job_ids, or the endpoint was never hit. |

**APPROVE — What happens today?**
- User clicks Approve. API returns 200. But nothing is persisted because the job_id doesn't exist in `careerloop.jobs`. Silent failure.

**What should happen?**
- Approve should persist to `careerloop.user_job_relationships` with match_status='saved'.
- The brief item's status should update.
- The job should be marked for application pack generation.
- The next step (pack generation) should use the saved relationship.

**What is missing?**
1. Jobs not persisted to cache during scan
2. Silent failure — user thinks it worked but nothing was saved
3. No feedback loop — user can't see which jobs they've approved

### 5. GENERATE PACK

| Step | Status | What Happens |
|------|--------|-------------|
| **Frontend action** | ✅ | User types "prepare pack for this job" in chat |
| **API endpoint** | ✅ | `POST /v1/chat/message` → supervisor graph → ActionResolver → `PREPARE_APPLICATION_PACK` |
| **Backend** | ⚠️ NOW FIXED | `tool_registry.prepare_application_pack()` — daemon thread calls `PackageAssembler.assemble_package()` |
| **DB writes** | ⚠️ NEW (today) | Writes to `careerloop.application_packs` + `careerloop.run_events` |
| **User sees** | ⚠️ | "Generating your application pack..." status card. Pack generates but: |
|   | ❌ | Resume needs `master_cv_markdown` — user has has_cv=False |
|   | ❌ | Cover note is generic (no JD-based tailoring because job not in cache) |
|   | ❌ | Recruiter outreach is placeholder |
|   | ❌ | Screening answers are empty |

---

## ROOT CAUSE ANALYSIS (RCA)

### RCA-1: Jobs Not Persisted to Cache During Scan (CRITICAL)

**File:** `careerloop/daily_runner.py`  
**Bug:** `DailyRunner.run()` generates brief items with job data from the scan, but never writes those jobs to `careerloop.jobs`. The brief_items table has foreign keys (job_id) that reference phantom rows.

**Impact:** Every downstream action (inspect, approve, pack generation) fails because the job doesn't exist in the primary jobs cache.

**Fix needed:** After scan completes, before writing brief_items, ensure every job is inserted into `careerloop.jobs` with `ON CONFLICT DO UPDATE`.

### RCA-2: All Fit Scores = 70.0 (BROKEN SCORING)

**Evidence:** 6 brief items, all score = 70.0. This is a placeholder/fallback value.

**Impact:** User can't distinguish between good and bad matches. The core value prop (scored, ranked brief) is broken.

**Fix needed:** Investigate `india_fit_llm.py:score_batch()` — the 70.0 might be a default return when scoring fails.

### RCA-3: Duplicate Brief Items

**Evidence:** Intercom appears twice (jobs 7bd33322 and 6dd9229f), N26 appears twice, HelloFresh appears twice. 6 items = 3 unique jobs × 2 duplicates.

**Impact:** User sees duplicate cards. looks broken.

**Fix needed:** Deduplication in brief_items insertion is failing. The duplicate check in `daily_runner.py` needs to group by company+title, not just URL.

### RCA-4: NO CV Content (has_cv=False)

**Evidence:** `master_cv_markdown` is NULL for user 730d5bab despite `onboarding_complete=True`.

**Impact:** Application packs generate with empty resume. Resume edits have nothing to edit. The revenue-critical deliverable (tailored resume) is impossible.

**Fix needed:** Onboarding needs to require CV text before completing. LinkedIn-only onboarding sets PROFILE_READY without storing any CV.

---

## WHAT'S ACTUALLY WORKING (9 things)

1. ✅ Auth — JWT token → user_id → session. Works correctly.
2. ✅ Chat message send + persistence — messages stored in `careerloop.messages`
3. ✅ Chat history restore — `GET /v1/chat/history` returns messages on login
4. ✅ Scan launch — background thread runs, scrapes sources
5. ✅ Brief generation — daily_briefs + daily_brief_items populated
6. ✅ Brief retrieval — GET /v1/briefs/latest with offset pagination
7. ✅ Session recovery — onboarding_complete flag check works
8. ✅ PackageAssembler.assemble_package() — wired into tool_registry (today)
9. ✅ Resume editing — surgical DeepSeek edit wired into tool_registry (today)

## WHAT'S BROKEN (7 things blocking revenue)

1. ❌ Jobs not cached during scan — all brief item references are orphaned
2. ❌ All fit scores = 70.0 — scoring engine returning defaults
3. ❌ Brief item duplicates — same job appears twice
4. ❌ has_cv=False — onboarding produced PROFILE_READY with no CV
5. ❌ User-jobs relationships empty — APPROVE writes nothing
6. ❌ Application packs table = 0 rows — pack generation just fixed today, never tested
7. ❌ Brief summary = NULL — no executive summary text for frontend
