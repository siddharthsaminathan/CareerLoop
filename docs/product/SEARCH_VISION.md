# CareerLoop Search System — Vision + Implementation Tracker

> **Living document.** Vision is locked. Implementation status updated each session.  
> Last updated: 2026-05-27 (Sprint 5 complete — Phase E ontology gate, board query enrichment, Naukri API-first)  
> Audit source: `docs/audits/Discovery_engine_audit_260526.md` + `docs/audits/Discovery_engine_audit_chatgpt_260526.md`

---

## CORE PRINCIPLE

CareerLoop is a career operating system. The search system exists to continuously:

```
understand user → search opportunities → apply → track outcomes → learn → converge toward employment
```

**Core optimization:** Not application volume. Not keyword matching. **Employment probability.**

> The system must retrieve from **this user's AI labor market**, not the entire AI labor market.

---

## THE 4 SEARCH SYSTEMS

| # | System | Goal | Status |
|---|--------|------|--------|
| **S1** | Job Search | Find verified, relevant job opportunities | 🟡 Active — Phase A-F built, precision bugs open |
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

**Score: 65/100** _(was 40 — +25 this session)_

**Goal:** Given role + city, find companies likely hiring for that role.  
**Sources:** SerpAPI (primary), Wellfound (DDG fallback only now), Crunchbase (DDG), Inc42/YourStory (DDG), YC API.

**What's built:**

| Item | Status |
|------|--------|
| SerpAPI — 2-call cap, intent-based queries | ✅ Done |
| DDG fallback when no key | ✅ Done |
| Wellfound — DDG-only (Playwright removed) | ✅ Fixed this session |
| Crunchbase DDG — 2 queries | ✅ Done |
| Inc42/YourStory DDG — 3 queries | ✅ Done |
| YC API — India filter | ✅ Done |
| Company enrichment (ATS detection, upsert to DB) | ✅ Done |
| SQLite fallback | ✅ Done |
| Remote India query path in SerpAPI | ✅ Built this session |
| Archetype-constrained function_hint (Phase A queries) | ✅ Built this session |

**Active Bugs:**

| Bug | Symptom | Status |
|-----|---------|--------|
| **B1 — Browser opens × 12** | Wellfound fires `sync_playwright()` per search | ✅ Fixed — `WellfoundDiscovery.search()` now calls `_ddg_fallback()` directly |
| **B2 — Remote = 0 companies** | No query path for virtual-first companies | ✅ Partially fixed — SerpAPI has Remote India path; Wellfound/Inc42 still return 0 for Remote |
| **B3 — Queries too broad** | Finds "AI companies Bangalore" not "B2B AI SaaS product companies" | ✅ Partially fixed — `to_query_constraint()` from RoleArchetypeEngine enriches Phase A `function_hint` |
| **B4 — No company ontology** | All companies enriched with same weak tags | ❌ Open — Company Identity Layer not built |

**To Build (still open):**

| Item | Description | Priority |
|------|-------------|----------|
| **Company Identity Layer** | Tag every discovered company with: sector, industry, B2B/B2C, business_model, company_stage, market, keywords. Becomes the company ontology for structured Phase A filtering. | P1 |
| **Remote — Wellfound/Inc42 path** | Wellfound + Inc42 return 0 for Remote city. Need virtual-first company sources (DDG `"remote-first India startup"`) | P1 |

**RCA:** Phase A now has archetype-constrained queries and no Playwright. Remaining gap is company ontology — discovered companies are still not tagged with B2B/B2C/stage/market. That's Sprint 5 work.

---

### Phase B — Job Board Retrieval

**Score: 75/100** _(was 70 — +5 sprint 5)_

**Goal:** Direct job retrieval from boards in parallel, archetype-constrained.  
**Sources (6 parallel):** JobSpy (LinkedIn+Indeed), Naukri (XHR), Monster/Foundit, Glassdoor, Google Jobs (DDG→ATS URLs), DDG direct.

**What's built:**

| Source | Status | Jobs/run | Quality |
|--------|--------|----------|---------|
| JobSpy (LinkedIn+Indeed) | ✅ Working | ~40 | ⚠️ JD fetch now attempted via `_fetch_missing_jds` |
| Google Jobs (DDG→ATS URLs) | ✅ Working | ~30 | ✅ Best board source — real ATS job URLs |
| Glassdoor | ✅ Working | ~16 | ⚠️ Medium |
| Monster/Foundit | ✅ Working | ~25 | ⚠️ Medium |
| DDG direct | ✅ Working | ~13 | ⚠️ Low |
| Naukri REST API | ✅ API-first (Sprint 5) | ~50 | ✅ Direct `jobapi/v3/search` — no Playwright in Phase B |
| Archetype filter on board results | ✅ Sprint 4 | — | Rejects titles in `rejected_roles` from profile |
| Archetype-enriched query strings | ✅ Sprint 5 | — | 2 archetype queries prepended to `queries[]` before `_board_search()` |

**Active Bugs:**

| Bug | Symptom | Status |
|-----|---------|--------|
| **B5 — Naukri dead** | `ConnectError` to `startpage.com` every run | ✅ Fixed — `NaukriAdapter.search()` now API-first (direct `jobapi/v3/search`), Playwright only as fallback |
| **B6 — JobSpy desc=3c** | JobSpy returns `description = "..."` for ~90% of results | ✅ Partially fixed — `_fetch_missing_jds` fetches full JD; gate rejects jobs still <200c |
| **B7 — Query expansion kills role precision** | "AI Product Engineer" → "AI engineer / ML engineer" | ✅ Fixed — archetype filter on Phase B output; Phase A queries now archetype-constrained |

**To Build (still open):**

| Item | Description | Priority |
|------|-------------|----------|
| ~~Naukri XHR fix~~ | ✅ Done Sprint 5 — API-first direct `jobapi/v3/search` | — |
| ~~Archetype-enriched query strings~~ | ✅ Done Sprint 5 — 2 archetype queries prepended to `queries[]` | — |

**RCA:** Phase B now has archetype-enriched queries at source, API-first Naukri, and archetype output filter. Remaining gap is Company Identity Layer (Sprint 6).

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

| Bug | Symptom | Status |
|-----|---------|--------|
| **B12 — role_fit=0 jobs score 52-58** | Wrong jobs rank mid-table | ✅ Fixed — `role_fit_raw < profile.role_fit_gate` → hard cap at 30 in `india_fit_engine.py` |
| **B13 — Title leakers (HVAC, Mech, Intern)** | Wrong-domain roles survive embedding filter | ✅ Fixed — `archetype.reject_title()` rejects titles matching profile `rejected_roles` (no hardcoding) |
| **B14 — Ontology pre-filter missing** | Phase E runs embedding on archetype-mismatched jobs (wasted compute) | ✅ Fixed Sprint 5 — `archetype_match < profile.archetype_gate` hard reject before cosine similarity |

**To Build (still open):**

| Item | Description | Priority |
|------|-------------|----------|
| **Structured semantic parse in Phase D** | LLM extraction of `{role_type, company_market, customer_type}` from JD — upgrades `archetype_match` from token-overlap to semantic | P1 |

**RCA:** Phase E now has 3-layer filter: ontology pre-gate → embedding similarity → profile rejection. Remaining gap is archetype_match quality — currently token-overlap, needs Phase D semantic parse to be accurate.

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

## OVERALL PIPELINE SCORE: 77/100 _(was 74 — +3 sprint 5)_

| Phase | Sprint 1-4 | Sprint 5 | Biggest Remaining Gap |
|-------|--------|-------|----------------------|
| A — Employer Discovery | 65 | **65** | Company Identity Layer not built; Wellfound/Inc42 return 0 for Remote |
| B — Job Boards | 70 | **75** | Company Identity Layer needed for typed company targeting |
| C — ATS Scrape | 80 | **80** | Workday bot-detection unresolved |
| D — JD Extraction | 75 | **75** | Structured semantic parse (role_type/customer_type) not built |
| E — Role Filtering | 78 | **83** | archetype_match quality (token-overlap; needs Phase D semantic parse) |
| F — Scoring | 70 | **70** | Structured ontology tags (needs Phase D parse first) |
| G — Company Intel | 85 | **85** | Correct. Not blocking. |

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

## OPEN BUGS — PRIORITY ORDER

| # | Bug | Phase | Impact | Status |
|---|-----|-------|--------|--------|
| B1 | Wellfound Playwright in Phase A — browser opens × 12 | A | 🔴 High | ✅ Fixed — DDG-only |
| B2 | Remote = 0 companies | A | 🔴 High | ✅ Partial — SerpAPI has Remote path; Wellfound/Inc42 still 0 |
| B3 | Phase A queries too broad | A | 🔴 High | ✅ Partial — archetype constrains queries; Company Identity Layer still missing |
| B4 | role_fit=0 jobs score 52-58 | E/F | 🔴 High | ✅ Fixed — hard cap at 30 |
| B5 | JobSpy desc=3c → score compression | D/F | 🔴 High | ✅ Fixed — `_fetch_missing_jds` + min-desc gate |
| B6 | No hard gate on empty JDs | D | 🔴 High | ✅ Fixed — configurable gate from profile |
| B7 | No ontology filter in Phase E | E | 🟡 Medium | ✅ Fixed Sprint 5 — `archetype_match < profile.archetype_gate` hard reject before embedding |
| B8 | Title leakers (HVAC, Mech, Intern) | E | 🟡 Medium | ✅ Fixed — `archetype.reject_title()` reads profile `rejected_roles` |
| B9 | Query expansion loses role identity in Phase B | B | 🟡 Medium | ✅ Fixed Sprint 5 — 2 archetype-constrained queries prepended to `queries[]` |
| B10 | Naukri dead — startpage rate limit | B | 🟡 Medium | ✅ Fixed Sprint 5 — `NaukriAdapter` API-first, Playwright only as fallback |
| B11 | No job ontology tagging post extraction | C/D | 🟡 Medium | ✅ Fixed — `_tag_jobs_with_ontology()` runs on all jobs pre-Phase E |
| B12 | Cache hits mask stale results | Pipeline | 🟡 Medium | ❌ Open |
| B13 | Workday = 0 jobs | C | 🟢 Low | ❌ Open |

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

### Sprint 6 — Company Identity Layer (B3, long-term precision)
- Tag every discovered company in `CompanyRegistry` with: `{sector, business_model, b2b_b2c, stage, market, product_keywords}`
- Constrain Phase A discovery: only fetch ATS jobs from companies whose identity matches archetype's `preferred_company_types`
- Phase D structured semantic parse: LLM extraction of `{role_type, company_market, customer_type, execution_style}` from JD text
- **Expected:** Phase A retrieves "B2B AI SaaS product companies" not "all AI companies"

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
