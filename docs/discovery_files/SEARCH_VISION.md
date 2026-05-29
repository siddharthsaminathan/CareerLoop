# CareerLoop Search System — Vision + Implementation Tracker

> **Living document.** Vision is locked. Implementation status updated each session.  
> Last updated: 2026-05-28 (Sprint 6 — Phase A DETACHED. Primary pipeline = Phase B→G. All Phase A root causes documented below.)  
> Audit sources: `docs/audits/Discovery_engine_audit_260526.md` · `docs/audits/Discovery_engine_audit_chatgpt_260526.md` · `docs/discovery_files/PHASE_A_detachment.md` · v3 live run audit `test data/output/siddharth/audit_20260528_*.log`

---

## CORE PRINCIPLE

CareerLoop is a career operating system. The search system exists to continuously:

```
understand user → search opportunities → apply → track outcomes → learn → converge toward employment
```

**Core optimization:** Not application volume. Not keyword matching. **Employment probability.**

> The system must retrieve from **this user's AI labor market**, not the entire AI labor market.

---

## ⚠️ SPRINT 6 ARCHITECTURAL DECISION: PHASE A DETACHED

**Decision date:** 2026-05-28  
**Decision:** Phase A (Employer Discovery) is **detached from the primary pipeline** until Company Identity Layer is built.

**Reason:** Phase A is returning 0–1 jobs per city while adding 300–400 seconds of latency. Phase B–G already delivers a functioning retrieval pipeline. Phase A in its current state is an experimental discovery layer masquerading as a production dependency.

**Evidence from v3 run (2026-05-28):**
- Bangalore / AI Product Engineer: Phase A = 1 job, Phase B = 133 jobs
- Chennai / AI Product Engineer: Phase A = 0 jobs, Phase B = 129 jobs
- Phase A enriched 80 companies per city but ZERO returned India-relevant jobs for the target role

**Current primary pipeline (active):**
```
Phase B — Job Board Retrieval     ← 6 parallel sources, 100–150 jobs/run
Phase C — ATS Portal Scrape       ← 14 adapters (dependent on Phase A companies; returns 0 without Phase A)
Phase D — JD Extraction           ← ScrapeGraph → IndeedScraper → BeautifulSoup fallback
Phase E — Role Filtering          ← 3-layer: ontology gate → embedding cosine → profile rejection
Phase F — Scoring + Ranking       ← 16-dim fit engine, role_fit hard gate
Phase G — Company Intel           ← lazy, per-interest enrichment
```

**Phase A future track (async, non-blocking):**
- Rebuild as background Company Intelligence Registry
- Async enrichment of companies discovered from Phase B results
- Not a primary retrieval path; a company enrichment layer
- Blocked on: Company Identity Layer (sector, B2B/B2C, stage, market tags per company)

---

## THE 4 SEARCH SYSTEMS

| # | System | Goal | Status |
|---|--------|------|--------|
| **S1** | Job Search | Find verified, relevant job opportunities | 🟡 Active — Phase B→G pipeline running. Phase A detached. |
| **S2** | Recruiter Search | Find recruiters connected to role + company + geo | ⚫ Not started |
| **S3** | Referral Search | Find employees likely to provide referrals | ⚫ Not started |
| **S4** | Cold Connection Search | Find warm outreach paths via alumni, mutuals, org network | ⚫ Not started |

S2–S4 blocked on: S1 must reach ≥80% before starting.

---

## SEARCH SYSTEM 1 — JOB SEARCH ENGINE

### Architecture

```
Career Intent Vector (role + city + profile)
    ↓
Role Archetype Engine              ← generates must_have / avoid / company_type constraints (✅ built)
    ↓
Phase A — Employer Discovery      ← finds companies matching archetype
    ↓
Phase B — Job Board Retrieval     ← archetype-enriched queries + parallel 6 sources
    ↓
Phase C — ATS Portal Scrape       ← fetches jobs from company portals (14 adapters)
    ↓
Phase D — JD Extraction           ← full JD fetch + min-desc gate
    ↓
Phase E — Role Filtering          ← ontology pre-filter → embedding filter
    ↓
Phase F — Scoring + Ranking       ← 16-dim, role_fit hard gate, archetype_fit dim
    ↓
Phase G — Company Intel           ← enriches shortlisted jobs (lazy, per-interest)
```

---

### THE MISSING LAYER — Role Archetype Engine

**This is the singular fix that unblocks Phase A, B, E, F.**

Input: `"AI Product Engineer"`  
Output:
```json
{
  "must_have": ["product", "platform", "customer-facing", "cross-functional", "applied AI"],
  "avoid": ["research ML", "pure backend", "hardware", "generic SWE", "infra only"],
  "preferred_company_types": ["B2B AI SaaS", "AI product startup", "platform company"],
  "reject_company_types": ["body shop", "IT outsourcing", "staffing", "hardware OEM"]
}
```

This vector constrains: Phase A discovery queries → Phase B query expansion → Phase E ontology filter → Phase F hard gate.

**Status: ✅ Built + fully wired. `careerloop/sources/role_archetype.py` — `RoleArchetypeEngine`. Derives must_have/avoid/preferred_company_types from `profile_extended.yml` (zero hardcoding). Wired into: Phase A `_discover_and_rank()` function_hint, Phase B archetype-enriched query prepend + title reject filter, Phase E ontology pre-filter gate.**

---

### Phase A — Employer Discovery

**Score: 20/100** _(revised down from 65 after v3 empirical evidence — system is broken in production)_

**Status: 🔴 DETACHED — Not in primary pipeline. Rebuilding as async Company Intelligence Registry.**

**Goal:** Given role + city, find companies likely hiring for that role.  
**Files:** `careerloop/sources/company_discovery.py`, `careerloop/on_demand.py:_discover_and_rank()`, `careerloop/on_demand.py:_scrape_targeted_companies()`

---

#### PHASE A ROOT CAUSE ANALYSIS (from v3 audit 2026-05-28 + PHASE_A_detachment.md)

**RC-1 — BAD QUERY CONSTRUCTION (function_hint is LLM soup)**

The archetype `to_query_constraint()` returns a phrase like:
```
"ai product engineer applied product engineering AI product startup"
```
This phrase is embedded as a quoted literal in the SerpAPI query:
```
well-funded AI startup Bangalore India hiring "ai product engineer applied product engineering AI product startup" 2025
```
No webpage contains this exact phrase. Result: SerpAPI query 1 returns **0 results every single run**.  
Fix needed: Use only `role` + `archetype.function_type` (2-3 words max) in Phase A queries. Never embed the full constraint as a quoted phrase.

**RC-2 — NO EMPLOYER VALIDATION LAYER**

Every discovered URL is treated as a real employer. From v3 run:
- `productbased.in` — a blog, not a company → enriched as employer
- `builtin.com` — a job aggregator, not a company → detected as Greenhouse, fetched jobs
- `wellfound.com/company/augmedix` — a Wellfound listing page → detected as SmartRecruiters (false positive — Wellfound uses SmartRecruiters under the hood) → 0 India jobs
- `internshala.com` — an internship platform, not an employer → enriched as employer

None of these are actual companies hiring Siddharth.  
Fix needed: Employer validation gate before enrichment — check if domain resolves to a real company (not a blog/aggregator/platform). Gate on: has careers page, ATS exists with >0 active jobs.

**RC-3 — YC SOURCE POLLUTES WITH US COMPANIES**

`YCDiscovery.search()` uses `https://api.ycombinator.com/v0.1/companies?country=India` but returns 100 companies that are predominantly US-headquartered (Airbnb, DoorDash, Coinbase, Dropbox, GitLab, Amplitude, PagerDuty, Oklo, Instacart, etc.). These companies have no India AI product engineer roles.  
Fix needed: YC source should filter by `city` (not just India) OR be removed from Phase A entirely until Company Identity Layer can tag which YC companies actively hire in India.

**RC-4 — PHASE A HAS NO MEMORY (rediscovery every run)**

Every `run()` call fires SerpAPI → Wellfound → Crunchbase → Inc42 → YC for the same city+sector. The `CompanyRegistry` DB exists but `targeting.top_n()` is called AFTER live discovery, not instead of it. Discovered companies are cached but the discovery queries run again anyway.  
Fix needed: Cache-first strategy — check `CompanyRegistry` for city+sector+role before firing live sources. Only run live discovery if cached companies are stale (>7 days) or count is below threshold.

**RC-5 — ENTITY CONTAMINATION (blogs, aggregators, listing pages treated as employers)**

From v3 logs, companies enriched include:
- `"100+ Product Company Jobs in Bangalore"` — a blog post title, not a company
- `"Top 12 Product Based Companies in Chennai"` — another article  
- `"Best Tech Jobs & Startup Jobs in Bangalore 2026"` — an aggregator page
- `"Tech & Startup Jobs in Bengaluru"` — another aggregator

These have zero ATS jobs but consume enrichment budget. Root cause: SerpAPI returns search result titles as company names — the title extraction regex is naive.  
Fix needed: Company name validation — reject any "company" whose name looks like a search result title (contains numbers, "jobs", "companies", "startups", "list", "top N").

---

#### WHAT'S BUILT (valid, will be reused in future Phase A rebuild)

| Item | Status |
|------|--------|
| SerpAPI integration — 2-call cap | ✅ Done — query construction broken, but adapter works |
| DDG fallback when no key | ✅ Done |
| Wellfound — DDG-only (Playwright removed) | ✅ Fixed Sprint 4 |
| Crunchbase DDG — 2 queries | ✅ Done |
| Inc42/YourStory DDG — 3 queries | ✅ Done |
| YC API — India filter | ✅ Done — but pollutes with US companies |
| Company enrichment (ATS detection, upsert to DB) | ✅ Done — enrichment logic correct, input is garbage |
| SQLite fallback | ✅ Done |
| CompanyRegistry DB upsert | ✅ Done |
| Archetype-constrained function_hint | ✅ Built Sprint 5 — broken query construction though |

---

#### FUTURE PHASE A REBUILD PLAN (Sprint 7+, async track)

| Item | Description | Priority |
|------|-------------|----------|
| **Fix query construction** | SerpAPI queries use `role` + `archetype.function_type` (2-3 words) only. No quoted phrases. No full archetype constraint. | P0 |
| **Employer validation gate** | Before enrichment: check domain is a real company (not blog/aggregator). Gate on: domain ≠ known aggregators, name doesn't look like a search title. | P0 |
| **Fix YC source** | YC filter by `city` field or remove until Company Identity Layer tags India hiring activity. | P1 |
| **Cache-first discovery** | Check `CompanyRegistry.list_by_city_sector()` first. Only run live if stale or count < threshold. | P1 |
| **Company Identity Layer** | Tag every company with: `{sector, business_model, b2b_b2c, stage, market, product_keywords}`. Gate Phase A output on archetype `preferred_company_types` match. | P1 |
| **Make Phase A async** | Run Phase A in background thread after Phase B returns results. Enriches company registry for future runs. Does not block user-facing results. | P2 |

**Phase A code paths to disable (detachment):**
- `on_demand.py:_discover_and_rank()` — skip via `include_phase_a=False` flag on `run()`
- `on_demand.py:_scrape_targeted_companies()` — skip same way
- Phase A contributes 0–1 jobs per city; Phase B contributes 100–150. Detachment has zero user-facing cost.

---

### Phase B — Job Board Retrieval

**Score: 72/100** _(revised — Naukri dead, Google rate-limiting observed in long runs)_

**Status: ✅ PRIMARY PIPELINE — all results come from here.**

**Goal:** Direct job retrieval from boards in parallel, archetype-constrained.  
**Sources (6 parallel):** JobSpy (LinkedIn+Indeed), Naukri (XHR API), Monster/Foundit, Glassdoor, Google Jobs (DDG→ATS URLs), DDG direct.

**Observed board health (v3 run 2026-05-28):**

| Source | Bangalore AI PE | Chennai AI PE | Notes |
|--------|----------------|---------------|-------|
| JobSpy (LinkedIn+Indeed) | 40 | 40 | ✅ Consistent, best volume |
| GoogleJobs | 30 | 30 | ✅ Good quality |
| Glassdoor | 30 | 23 | ✅ Works |
| Monster/Foundit | 23 | 36 | ✅ Works |
| DDG direct | 23 | 19 | ⚠️ Variable |
| Naukri API | **0** | **0** | 🔴 Returns 406 every run |

**Active Bugs:**

| Bug | Symptom | Root Cause | Status |
|-----|---------|-----------|--------|
| **B-NEW-1 — Naukri 406** | `NaukriAdapter` returns HTTP 406 every run → 0 jobs | API endpoint may have changed or requires updated headers/cookies. Current headers: `appid: 109`, `systemid: Naukri`. Naukri API may be rate-limiting or requires session cookie. | 🔴 Open |
| **B-NEW-2 — Google CAPTCHA in long runs** | `google.com/sorry/index` 429 appears after ~5th search in same run | Google rate-limits the search IP after repeated queries. Observed in Applied AI Engineer @ Chennai searches (last 3 queries returning 429). | 🟡 Open |
| **B-NEW-3 — DDG `_source_type=search` leaks thin jobs** | DDG returns URL snippets (not full JDs) for some results — these pass min-desc gate if snippet ≥200c but contain no real JD | `_run_ddg_search()` appends raw snippet as description when scraper fails. Snippet is the search result body, not the JD. | 🟡 Open |
| **B6 — JobSpy desc=3c** | JobSpy returns `description = "..."` for ~90% of results | Fixed by `_fetch_missing_jds` + min-desc gate. Still some thin JDs getting through cutshort.io links. | ✅ Partially fixed |

**What's built:**

| Source | Status | Jobs/run | Quality |
|--------|--------|----------|---------|
| JobSpy (LinkedIn+Indeed) | ✅ Working | ~40 | ⚠️ JD fetch attempted via `_fetch_missing_jds` |
| Google Jobs (DDG→ATS URLs) | ✅ Working | ~30 | ✅ Best quality — real ATS job URLs |
| Glassdoor | ✅ Working | ~23–30 | ⚠️ Medium |
| Monster/Foundit | ✅ Working | ~23–36 | ⚠️ Medium |
| DDG direct | ✅ Working | ~19–23 | ⚠️ Low — snippet quality |
| Naukri REST API | ❌ DEAD — 406 | 0 | 🔴 Needs header/auth fix |
| Archetype title filter on board results | ✅ Sprint 4 | — | Rejects titles matching profile `rejected_roles` |
| Archetype-enriched query strings | ✅ Sprint 5 | — | 2 archetype queries prepended to `queries[]` |
| Per-source health logging | ✅ Sprint 6 | — | `[Phase B] per-source: ...` visible in audit log |

**To Fix (priority order):**

| Item | Description | Priority |
|------|-------------|----------|
| **Naukri 406 root cause** | Investigate current Naukri API requirements. Try: updated `User-Agent`, session cookies from browser, test `appid`/`systemid` values. If API blocked, implement DDG fallback for Naukri (`"role" site:naukri.com city`). | P1 |
| **Google CAPTCHA mitigation** | Add random delays (2–4s) between DDG searches. Rotate User-Agent strings from a pool (read from profile config, not hardcoded). Respect rate limits by spacing parallel queries. | P2 |
| **DDG snippet source tagging** | Tag DDG results with `_jd_quality: snippet` when scraper fails. Downweight these in Phase F (source quality dimension). | P2 |

---

### Phase C — ATS Portal Scrape

**Score: 80/100**

**Goal:** Fetch jobs from company career portals using 14 ATS adapters.  
**Adapters:** Greenhouse, Lever, Ashby, Workday, SmartRecruiters, SAP SuccessFactors, Taleo, iCIMS, TalentRecruit, Darwinbox, Workable, Teamtailor, Recruitee, BambooHR.

**What's built:**

| Item | Status |
|------|--------|
| 14 ATS adapters | ✅ Done |
| ATS fingerprint engine (13/13 signatures) | ✅ Done |
| L1 — Network/XHR interception | ✅ Done |
| L2 — Rendered DOM extraction | ✅ Done |
| L3 — Agentic navigation (scroll/click/paginate) | ✅ Done |
| SpireAI adapter (Myntra confirmed) | ✅ Done |
| ATS endpoint cache (7-day TTL) | ✅ Done |
| Workday adapter | ⚠️ Detected, not scraped |

**Active Bugs:**

| Bug | Symptom | Root Cause |
|-----|---------|-----------|
| **B8 — Mumbai/Remote = 0 ATS jobs** | Phase C returns nothing for non-Bangalore cities | Phase C has zero companies to scrape because Phase A returned 0 for those cities. Phase C is correct; Phase A is broken. |
| **B9 — Workday = 0 jobs** | BrowserStack, Uniphore detected, 0 jobs fetched | Workday bot-detects headless Playwright; needs realistic browser profile + user-agent rotation |

**To Build (still open):**

| Item | Description | Priority |
|------|-------------|----------|
| **Workday Playwright hardening** | Realistic browser profile, human-like delays, user-agent rotation | P2 |

**What was built this session:** Job ontology classifier is now `_tag_jobs_with_ontology()` in `on_demand.py` — tags every job with `{seniority, archetype_match, biz_model, preferred_company_match}` before Phase E. Called on all jobs post-dedup.

**RCA:** Phase C itself is correct — best source quality in the pipeline (Sarvam AI Ashby = 5889c full JDs, scores 73). Remaining gap is Workday (bot-detection).

---

### Phase D — JD Extraction

**Score: 75/100** _(was 60 — +15 this session)_

**Goal:** Get full job description text for each job. Structured semantic parse where possible.  
**Method:** ScrapeGraph (Playwright+LLM) → Indeed JSON API → BeautifulSoup fallback.

**What's built:**

| Item | Status |
|------|--------|
| ScrapeGraph LLM extraction | ✅ Working — 2000-6000c for ATS jobs |
| BeautifulSoup fallback | ✅ Working |
| JobSpy/board URL follow-up fetch | ✅ Built this session — `_fetch_missing_jds()` in `on_demand.py` |
| `min_description_chars` gate (configurable) | ✅ Built this session — `profile_extended.yml scoring.min_description_chars` |

**Active Bugs:**

| Bug | Symptom | Status |
|-----|---------|--------|
| **B10 — 45% of jobs enter Phase F with <100c** | Scorer gets title only | ✅ Fixed — `_fetch_missing_jds` attempts fetch; gate rejects if still thin |
| **B11 — Silent failures** | Jobs pass Phase F with empty JD silently | ✅ Fixed — hard gate before `score_jobs_batch()` with logged drop count |

**To Build (still open):**

| Item | Description | Priority |
|------|-------------|----------|
| **Structured semantic parse layer** | After raw JD text extracted, run LLM pass: `{role_type, company_market, customer_type, execution_style}`. Feeds Phase E ontology filter. | P1 |

**RCA:** JD gate now enforced. Remaining gap is semantic structure — raw JD text is attached but not parsed into typed fields. Next Phase D upgrade.

---

### Phase E — Role Filtering

**Score: 83/100** _(was 78 — +5 sprint 5)_

**Goal:** Remove jobs irrelevant to target role before scoring.  
**Method:** Embedding cosine similarity (all-MiniLM-L6-v2, threshold 0.40) + token overlap fallback.

**What's built:**

| Item | Status |
|------|--------|
| Embedding cosine filter (threshold 0.40) | ✅ Working |
| Anti-gatekeeping rules (rejects body shops, outsourcing) | ✅ Working |
| India city filter (3 choke points) | ✅ Working |
| Archetype title reject (via `archetype.reject_title()`) | ✅ Built this session — reads `rejected_roles` from profile |
| Ontology tags on jobs (seniority, archetype_match, biz_model) | ✅ Sprint 3 — `_tag_jobs_with_ontology()` |
| Ontology pre-filter (archetype_match gate before embedding) | ✅ Sprint 5 — `archetype_match < profile.archetype_gate` hard reject in `on_demand.py` before `_role_filter.filter_jobs()` |

**Active Bugs:**

| Bug | Symptom | Root Cause | Status |
|-----|---------|-----------|--------|
| **B12 — role_fit=0 jobs score 52-58** | Wrong jobs rank mid-table | Fixed. | ✅ Fixed |
| **B13 — Title leakers (HVAC, Mech, Intern)** | Wrong-domain roles survive embedding filter | Fixed. | ✅ Fixed |
| **B14 — Ontology pre-filter missing** | Phase E runs embedding on archetype-mismatched jobs | Fixed Sprint 5. | ✅ Fixed |
| **B-NEW-4 — SQLite cursor context manager crash** | `india_fit_engine.py`: `company_memory_lookup` and `company_registry_lookup` fail with `'sqlite3.Cursor' object does not support the context manager protocol` for every company. Falls back to defaults silently. | `_SQLiteConn.cursor()` returns a raw `sqlite3.Cursor` object. Somewhere in `india_fit_engine.py`, it's used in a `with conn.cursor() as cur:` context manager, which is not supported on SQLite cursors. | 🔴 Open — `careerloop/india_fit_engine.py` |
| **B-NEW-5 — Ontology gate dropping 82%** | `archetype_match < 0.2` drops 84/102 jobs in Bangalore AI PE run | Token-overlap match against `must_have` tokens from LLM archetype. Tokens like `'applied AI'`, `'customer-facing'`, `'cross-functional'` don't appear verbatim in most JD text — they're semantic signals, not exact strings. The 82% dropout CORRECTLY removes garbage jobs but may also remove valid jobs with good semantic fit but low token overlap. | 🟡 Monitoring — gate threshold in `profile_extended.yml scoring.archetype_gate`. Not hardcoded. |

**To Build (still open):**

| Item | Description | Priority |
|------|-------------|----------|
| **Fix SQLite cursor context manager** | Find `with conn.cursor() as cur:` in `india_fit_engine.py`. Replace with `cur = conn.cursor(); cur.execute(...)`. SQLite cursors don't support `__enter__/__exit__`. | P0 |
| **Structured semantic parse in Phase D** | LLM extraction of `{role_type, company_market, customer_type}` from JD text — upgrades `archetype_match` from token-overlap to semantic similarity. | P1 |

**Ontology gate observation (v3 run):**  
82% dropout (102→18) for `AI Product Engineer @ Bangalore` is functioning as intended — the 84 dropped jobs were from Glassdoor/Monster with thin descriptions and no product/AI/LLM signals. The 18 that passed had at least 2/8 must_have tokens present. Gate is correctly filtering. However, if must_have tokens are too abstract (e.g. `"customer-facing"` never appears verbatim), valid jobs may be dropped. Phase D structured parse will fix this by operating on semantic fields, not raw text overlap.

---

### Phase F — Scoring + Ranking

**Score: 70/100** _(was 45 — +25 this session)_

**Goal:** Rank surviving jobs 0-100 using 16-dimensional fit scoring.  
**Dimensions:** role_fit, archetype_fit (NEW), skill_fit, salary, equity, location, company_stage, culture, work_mode, benefits, growth, source_quality + source-aware bonus (ATS +3.0, scraped +1.5, jobspy +1.0).

**What's built:**

| Item | Status |
|------|--------|
| 16-dim scorer (was 15) | ✅ Built — `archetype_fit` added this session |
| Source-aware weighting | ✅ Built |
| FIT_WEIGHTS sum = 100 (rebalanced) | ✅ Fixed this session |
| Score spread for ATS jobs with full JDs | ✅ Working |
| Board job score compression fixed (JD fetch gate) | ✅ Fixed this session |
| role_fit as hard gate | ✅ Built this session — `role_fit_raw < profile.role_fit_gate` → cap at 30 |
| archetype_fit dimension (reads from ontology tags) | ✅ Built this session |

**Active Bugs:**

| Bug | Symptom | Status |
|-----|---------|--------|
| **B14 — Score compression (60-64 cluster)** | Board jobs all cluster at midpoint | ✅ Fixed — min-desc gate removes no-JD jobs; `_fetch_missing_jds` populates JD before scoring |
| **B15 — Score range 50-73** | No real spread | ✅ Partially fixed — role_fit hard gate pushes wrong-domain jobs to ≤30; desc gate removes noise |
| **B16 — Role identity underweighted** | Wrong-domain jobs rank mid-table | ✅ Fixed — role_fit hard gate + archetype_fit as dedicated dimension (weight 8) |

**To Build (still open):**

| Item | Description | Priority |
|------|-------------|----------|
| **Score cap for missing JD** | If JD fetch failed AND `len(description) < min_desc` → score cap at 40 (currently they're rejected; may want a softer cap option) | P2 |
| **Structured ontology tags in scoring** | `archetype_fit` currently uses token-overlap. Once Phase D structured parse is built, upgrade to use `{role_type, company_market, customer_type}` fields | P1 |

**RCA:** Scoring engine now has a hard role gate and a dedicated archetype dimension. JD fetch + gate breaks the 60-64 compression cluster. Real score spread will emerge on next live run.

---

### Phase G — Company Intelligence

**Score: 85/100**

**Goal:** Enrich shortlisted jobs with structured company research.  
**Status:** ✅ Built (1,419-line MECE implementation). Lazy-loaded per company on user interest signal. Not blocking pipeline.

This architecture is correct. Phase G should never be in the critical path.

---

## OVERALL PIPELINE SCORE: 72/100 _(revised 2026-05-28 — Phase A score corrected after empirical evidence)_

| Phase | Sprint 5 | Sprint 6 | Biggest Remaining Gap |
|-------|--------|-------|----------------------|
| A — Employer Discovery | 65 | **20** 🔴 | **DETACHED** — entity contamination, bad query construction, YC pollution, no employer validation |
| B — Job Boards | 75 | **72** | Naukri dead (406), Google CAPTCHA on long runs |
| C — ATS Scrape | 80 | **80** | Phase A detached → C only gets jobs when Phase A active. Standalone C inactive. |
| D — JD Extraction | 75 | **75** | Structured semantic parse (role_type/customer_type) not built |
| E — Role Filtering | 83 | **83** | SQLite cursor bug in `india_fit_engine.py`; archetype_match quality (token-overlap) |
| F — Scoring | 70 | **70** | Structured ontology tags (needs Phase D parse first) |
| G — Company Intel | 85 | **85** | Correct. Not blocking. |

**Phase B→G pipeline score: 76/100** (this is the active pipeline).

---

## THE REAL ROOT CAUSE

> **"Semantic intent drift between user archetype and retrieval archetype."**

Current system: `"AI" + "product" + "engineer"` → keyword retrieval.  
Required system: `what TYPE of company` + `what TYPE of function` + `what TYPE of role` + `what TYPE of market` → identity-constrained retrieval.

The 4-layer model needed (from chatgpt audit):
1. **Company Identity** — sector, industry, B2B/B2C, stage, market, keywords per company
2. **Functional Ontology** — every role tagged to a function (Product, Engineering, Data, Sales, etc.)
3. **Role Archetype** — `{role_family, specialization, market_focus, customer_type, execution_type}` per role
4. **Job Tagging** — every job automatically tagged with company_type + business_model + function + archetype + seniority

Without this, embeddings and cosine similarity are too weak — "AI engineer" and "AI product engineer" embed closely but have completely different career intent.

---

## OPEN BUGS — PRIORITY ORDER (Phase B→G pipeline)

| # | Bug | Phase | Impact | Status |
|---|-----|-------|--------|--------|
| **B-NEW-4** | SQLite cursor context manager crash — `india_fit_engine.py` `company_memory_lookup` / `company_registry_lookup` fail on every company | E/F | 🔴 High — scoring engine uses defaults for every company, company signals not applied | ❌ Open — `careerloop/india_fit_engine.py` |
| **B-NEW-1** | Naukri 406 — API returns HTTP 406, 0 jobs every run | B | 🔴 High — Naukri is biggest Indian job board, losing ~50 jobs/run | ❌ Open — `careerloop/sources/naukri_adapter.py` |
| **B-NEW-2** | Google CAPTCHA (429) on long runs — later DDG searches hit Google CAPTCHA | B | 🟡 Medium — affects 3rd+ searches in same run, DDG fallback still works | ❌ Open — need inter-search delay |
| **B-NEW-3** | DDG snippet leaks — search result snippets treated as JDs | B/D | 🟡 Medium — thin content, misleads scorer | ❌ Open — `on_demand.py:_board_search` |
| **B12** | Cache hits mask stale results | Pipeline | 🟡 Medium | ❌ Open |
| **B13** | Workday = 0 jobs | C | 🟢 Low | ❌ Open |

**Previously fixed (archived):**
B1 (Wellfound Playwright) ✅ · B2 (Remote 0 companies) ✅ partial · B3 (Phase A queries) → **DETACHED** · B4 (role_fit=0 score) ✅ · B5 (JobSpy 3c) ✅ · B6 (empty JD gate) ✅ · B7 (ontology filter) ✅ · B8 (title leakers) ✅ · B9 (query expansion) ✅ · B10 (Naukri Playwright) ✅ (but API now 406) · B11 (ontology tagging) ✅

---

## IMPLEMENTATION ROADMAP

### ✅ Sprint 1 — Fix scoring quality (B4 + B5 + B6) — DONE 2026-05-26
- ✅ `role_fit < profile.role_fit_gate` → hard cap at 30 in `india_fit_engine.py`
- ✅ `_fetch_missing_jds()` — full JD fetch for thin-description jobs (requests + BS4)
- ✅ `min_description_chars` gate — configurable from `profile_extended.yml`, not hardcoded
- **Result:** score range now separates wrong-domain jobs (≤30) from real matches (50-80)

### ✅ Sprint 2 — Fix role precision (B3 + B9) — DONE 2026-05-26
- ✅ `RoleArchetypeEngine` — `careerloop/sources/role_archetype.py` — all config-driven
- ✅ Phase A `_discover_and_rank()` uses `archetype.to_query_constraint()` as function_hint
- ✅ Phase B board output filtered via `archetype.reject_title()` → reads `rejected_roles`
- **Result:** "AI Product Engineer" now rejects titles in profile's rejected_roles list

### ✅ Sprint 3 — Job Ontology tagging (B11) — DONE 2026-05-26
- ✅ `_tag_jobs_with_ontology()` — tags all jobs with `{seniority, archetype_match, biz_model, preferred_company_match}`
- ✅ `archetype_fit` added as 16th scoring dimension (weight 8) in `config.py`
- ✅ FIT_WEIGHTS rebalanced to sum exactly 100
- **Result:** ontology signals now flow into Phase F score; seniority mismatch now visible in breakdown

### ✅ Sprint 4 — Discovery breadth (B1 + B2) — DONE 2026-05-26
- ✅ Wellfound: `_scrape()` → `_ddg_fallback()` directly; no Playwright in Phase A
- ✅ SerpAPI `_build_queries()`: Remote India path when city is remote/pan-india/anywhere
- ✅ AGENTS.md: no-hardcoding rule locked for all future sessions
- **Result:** no browser launches in Phase A; Remote city now returns SerpAPI results

### ✅ Sprint 5 — Close remaining gaps (B7 + B9 + B10) — DONE 2026-05-27
- ✅ Phase E ontology gate: `archetype_match < profile.archetype_gate` hard reject before `_role_filter.filter_jobs()` in `on_demand.py`
- ✅ Phase B query enrichment: 2 archetype-constrained queries prepended to `queries[]` before `_board_search()` call
- ✅ Naukri fix: `NaukriAdapter.search()` now API-first (direct `jobapi/v3/search`), Playwright only as last-resort fallback
- **Result:** Phase E catches archetype-mismatch survivors before expensive embedding; Phase B board queries constrained at source

### ✅ Sprint 6 — Phase A detachment + observability + root cause documentation — DONE 2026-05-28
- ✅ Added full observability: `logging.basicConfig` wired to stdout/audit log — all module-level `logger.info` calls now visible
- ✅ Phase A root causes documented (5 RCs) in `SEARCH_VISION.md` from v3 live run
- ✅ Phase B per-source health displayed immediately in audit output
- ✅ Phase A detached via `include_phase_a=False` flag in `on_demand.run()`
- ✅ `[A:src]` / `[B:src]` phase attribution on every ranked job in final table
- **Result:** v3 run shows Phase B→G pipeline producing 7 ranked jobs for Bangalore/AI Product Engineer with full traceability

### Sprint 7 — Fix Phase B pipeline bugs (active sprint)
- [ ] **Fix SQLite cursor bug** in `india_fit_engine.py` — `with conn.cursor() as cur:` → `cur = conn.cursor()` (B-NEW-4)
- [ ] **Fix Naukri 406** — investigate updated API headers/auth; add DDG Naukri fallback (`site:naukri.com role city`) (B-NEW-1)
- [ ] **Fix Google CAPTCHA** — add inter-search delays from profile config, not hardcoded (B-NEW-2)
- [ ] **DDG snippet quality** — tag `_jd_quality: snippet` when scraper fails; downweight in Phase F (B-NEW-3)
- **Expected:** 50+ more jobs/run from Naukri; company scoring signals active (SQLite fix); cleaner Phase F scoring

### Sprint 8 — Phase D structured parse
- Phase D LLM extraction: `{role_type, company_market, customer_type, execution_style}` from raw JD text
- Upgrades `archetype_match` from token-overlap (current) to semantic field comparison
- Structured tags flow into Phase E ontology gate + Phase F archetype_fit dimension

### Sprint 9 — Phase A rebuild (async Company Intelligence Registry)
- Fix all 5 Phase A root causes (see Phase A section above)
- Rebuild as background enrichment layer, not primary retrieval
- Company Identity Layer: tag every company from Phase B results with sector/B2B-B2C/stage/market
- Cache-first discovery: check `CompanyRegistry` before live queries

---

## SEARCH SYSTEM 2 — RECRUITER SEARCH

**Status: ⚫ Not started. Unblocks after Sprint 1-2.**

Input: `(role, company, city)` → Output: `{recruiter_name, linkedin, email, role}`  
Sources: LinkedIn DDG `site:linkedin.com`, company directories, email pattern extraction.

---

## SEARCH SYSTEM 3 — REFERRAL SEARCH

**Status: ⚫ Not started.**

Input: `(role, company)` → Output: `{employee_name, linkedin, department, seniority, warm_path}`  
Sources: LinkedIn `site:` DDG, alumni database, same-function employees.

---

## SEARCH SYSTEM 4 — COLD CONNECTION SEARCH

**Status: ⚫ Not started.**

Input: `(company, user_profile)` → Output: outreach targets via mutual connections, alumni, org network.

---

## FEEDBACK LOOP ENGINE

**Status: ⚫ Not started. Long-term moat.**

Tracks: applications → interviews → rejections → resume versions → outreach versions → search reweighting.  
System learns which company types, role archetypes, and query patterns produce interviews. Reweights accordingly.
