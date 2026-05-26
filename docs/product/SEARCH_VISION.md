# CareerLoop Search System — Vision + Implementation Tracker

> **Living document.** Vision is locked. Implementation status updated each session.  
> Last updated: 2026-05-26  
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
[MISSING] Role Archetype Engine   ← generates must_have / avoid / company_type constraints
    ↓
Phase A — Employer Discovery      ← finds companies matching archetype
    ↓
Phase B — Job Board Retrieval     ← finds jobs directly (archetype-constrained queries)
    ↓
Phase C — ATS Portal Scrape       ← fetches jobs from company portals
    ↓
Phase D — JD Extraction           ← gets full job descriptions + structured semantic parse
    ↓
Phase E — Role Filtering          ← ontology filter + embedding filter
    ↓
Phase F — Scoring + Ranking       ← role archetype as hard gate, then 14-dim scoring
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

**Status: ❌ Not built. P0.**

---

### Phase A — Employer Discovery

**Score: 40/100**

**Goal:** Given role + city, find companies likely hiring for that role.  
**Sources:** SerpAPI (primary), Wellfound (Playwright/DDG fallback), Crunchbase (DDG), Inc42/YourStory (DDG), YC API.

**What's built:**

| Item | Status |
|------|--------|
| SerpAPI — 2-call cap, intent-based queries | ✅ Done |
| DDG fallback when no key | ✅ Done |
| Wellfound — Playwright scrape | ⚠️ Partial — opens browser per call |
| Crunchbase DDG — 2 queries | ✅ Done |
| Inc42/YourStory DDG — 3 queries | ✅ Done |
| YC API — India filter | ✅ Done |
| Company enrichment (ATS detection, upsert to DB) | ✅ Done |
| SQLite fallback | ✅ Done |

**Active Bugs:**

| Bug | Symptom | Root Cause |
|-----|---------|-----------|
| **B1 — Browser opens × 12** | Wellfound fires `sync_playwright()` per search. 12 searches = 12 Chromium instances | Playwright in Phase A is wrong architecture. Phase A should be API/HTTP only. |
| **B2 — Mumbai/Remote = 0 companies** | Phase A returns nothing for non-Bangalore cities | City name not found in DDG snippets for "Remote"; no query path for virtual-first companies |
| **B3 — All roles → same sector** | All 4 AI roles collapse to "Technology & Software" | `_infer_sector()` correct but too coarse. No role-archetype differentiation in SerpAPI queries. |
| **B4 — Queries too broad** | Finds "AI companies Bangalore" not "B2B AI SaaS product companies" | No company ontology. No role archetype constraint flowing into Phase A. |

**To Build (from chatgpt audit):**

| Item | Description | Priority |
|------|-------------|----------|
| **Company Identity Layer** | Tag every discovered company with: sector, industry, B2B/B2C, business_model, company_stage, market, keywords (LLM/automation/agents). This becomes the company ontology. | P0 |
| **Archetype-constrained discovery queries** | SerpAPI queries driven by Role Archetype Engine output — `preferred_company_types` constrains what Phase A searches for | P0 |
| **Remote India query path** | Separate query logic for Remote: `"fully remote AI product company India hiring"` — no city filter on snippets | P1 |
| **Remove Wellfound Playwright from Phase A** | Replace with DDG-only fallback. Playwright belongs in Phase C only. | P1 |

**RCA:** Phase A has no company identity model. Retrieves employers in a sector, not employers matching a role archetype. Contaminates everything downstream.

---

### Phase B — Job Board Retrieval

**Score: 55/100**

**Goal:** Direct job retrieval from boards in parallel, archetype-constrained.  
**Sources (6 parallel):** JobSpy (LinkedIn+Indeed), Naukri (XHR), Monster/Foundit, Glassdoor, Google Jobs (DDG→ATS URLs), DDG direct.

**What's built:**

| Source | Status | Jobs/run | Quality |
|--------|--------|----------|---------|
| JobSpy (LinkedIn+Indeed) | ✅ Working | ~40 | 🔴 desc=3c — unusable for scoring |
| Google Jobs (DDG→ATS URLs) | ✅ Working | ~30 | ✅ Best board source — real ATS job URLs |
| Glassdoor | ✅ Working | ~16 | ⚠️ Medium |
| Monster/Foundit | ✅ Working | ~25 | ⚠️ Medium |
| DDG direct | ✅ Working | ~13 | ⚠️ Low |
| Naukri XHR | 🔴 Dead | 0 | — |

**Active Bugs:**

| Bug | Symptom | Root Cause |
|-----|---------|-----------|
| **B5 — Naukri dead** | `ConnectError` to `startpage.com` every run | DDG routing through startpage; rate-limited |
| **B6 — JobSpy desc=3c** | JobSpy returns `description = "..."` for ~90% of results | JobSpy returns search page snippets only; no follow-up fetch to actual job URL |
| **B7 — Query expansion kills role precision** | "AI Product Engineer" expands to "AI engineer / ML engineer / backend AI" — loses archetype | No archetype-constrained query generation. Expansion purely keyword-based. |

**To Build (from chatgpt audit):**

| Item | Description | Priority |
|------|-------------|----------|
| **Archetype-constrained query expansion** | Before boards query, generate `{must_have, avoid, preferred_company_types}` from Role Archetype Engine. Queries become: `"AI product engineer B2B SaaS Bangalore"` not `"AI engineer Bangalore"` | P0 |
| **JobSpy full JD fetch** | After JobSpy returns job URLs, fetch each URL → parse full JD text → attach to job object before Phase F | P0 |
| **Naukri XHR fix** | Replace DDG backend with direct Naukri company search pages or Naukri XHR | P1 |

**RCA:** Role archetype is lost at query construction time. Board queries treat "AI Product Engineer" identically to "AI Engineer". No mechanism to constrain retrieved corpus to product-oriented roles.

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

**To Build (from chatgpt audit):**

| Item | Description | Priority |
|------|-------------|----------|
| **Job ontology classifier post-extraction** | After ATS extracts jobs, run a fast classifier: tag each job with `{function, market, business_model, role_archetype, seniority}`. This is the semantic tagging layer that Phase E + F need. | P1 |
| **Workday Playwright hardening** | Realistic browser profile, human-like delays, user-agent rotation | P2 |

**RCA:** Phase C itself is correct — best source quality in the pipeline (Sarvam AI Ashby = 5889c full JDs, scores 73). Problem is purely Phase A starving it of company inputs.

---

### Phase D — JD Extraction

**Score: 60/100**

**Goal:** Get full job description text for each job. Structured semantic parse where possible.  
**Method:** ScrapeGraph (Playwright+LLM) → Indeed JSON API → BeautifulSoup fallback.

**What's built:**

| Item | Status |
|------|--------|
| ScrapeGraph LLM extraction | ✅ Working — 2000-6000c for ATS jobs |
| BeautifulSoup fallback | ✅ Working |
| JobSpy/board URL follow-up fetch | ❌ Not built |
| `min_description_length` gate | ❌ Not built |

**Active Bugs:**

| Bug | Symptom | Root Cause |
|-----|---------|-----------|
| **B10 — 45% of jobs enter Phase F with <100c description** | Scorer gets title only; 7/14 dimensions default to neutral mid-range | No follow-up fetch for board job URLs; no hard reject gate on empty JDs |
| **B11 — Silent failures** | No log entry when extraction returns empty; jobs pass silently | Fallback chain exhausts with no `min_description_length` enforcement |

**To Build (from chatgpt audit):**

| Item | Description | Priority |
|------|-------------|----------|
| **Structured semantic parse layer** | After raw JD text extracted, run LLM pass to extract: `{role_type, company_market, customer_type, execution_style}`. Feeds Phase E ontology filter and Phase F archetype gate. | P1 |
| **Full JD fetch for board URLs** | For any job with `len(description) < 200`, fetch the apply_url, parse full page, re-attach description before Phase F | P0 |
| **Hard gate: reject desc < 200c** | Jobs that fail full JD fetch and still have <200c description → reject before Phase F, do not score | P0 |

**RCA:** Phase D has no hard gate. Empty JDs poison Phase F. Board sources (JobSpy/DDG) never return full JDs — Phase D must fetch them separately or reject.

---

### Phase E — Role Filtering

**Score: 65/100**

**Goal:** Remove jobs irrelevant to target role before scoring.  
**Method:** Embedding cosine similarity (all-MiniLM-L6-v2, threshold 0.40) + token overlap fallback.

**What's built:**

| Item | Status |
|------|--------|
| Embedding cosine filter (threshold 0.40) | ✅ Working |
| Anti-gatekeeping rules (rejects body shops, outsourcing) | ✅ Working |
| India city filter (3 choke points) | ✅ Working |
| Title blocklist | ❌ Not built |
| Ontology filter | ❌ Not built |

**Active Bugs:**

| Bug | Symptom | Root Cause |
|-----|---------|-----------|
| **B12 — role_fit=0 jobs score 52-58** | "Founding AI/LLM Integration Engineer" — role_fit=0, final_score=53.9 | `role_fit` is 1 of 14 scoring dimensions. Overridden by strong location/startup/source signals. Not a hard gate. |
| **B13 — Title leakers (HVAC, Mech, Intern)** | Wrong-domain roles survive embedding filter | "HVAC Product Engineer" has non-zero cosine similarity to "AI Product Engineer" (shared "Engineer" embedding). No title blocklist. |

**To Build (from chatgpt audit):**

| Item | Description | Priority |
|------|-------------|----------|
| **Ontology filter** | Before embedding filter, apply: if job's `role_archetype` tag (from Phase D classifier) is NOT in `must_have` archetypes AND IS in `avoid` list → hard reject. Embedding filter runs after. | P0 |
| **Title blocklist** | Hard reject titles matching: HVAC, Mechanical, Hardware, Intern, BPO, Data Entry, Civil, Non-Tech, SAP Basis. 10-minute build. | P0 |
| **role_fit as hard pre-filter** | `role_fit < 0.3` → reject before scoring. Not a scoring dimension — a gate. | P0 |

**RCA:** Embeddings alone are insufficient. "AI engineer" and "AI product engineer" embed closely but have completely different career intent. Ontology constraints needed before embedding similarity.

---

### Phase F — Scoring + Ranking

**Score: 45/100**

**Goal:** Rank surviving jobs 0-100 using 14-dimensional fit scoring.  
**Dimensions:** role_fit, salary, equity, location, company_stage, culture, work_mode, benefits, growth, source_quality + source-aware bonus (ATS +3.0, scraped +1.5, jobspy +1.0).

**What's built:**

| Item | Status |
|------|--------|
| 14-dim scorer | ✅ Built |
| Source-aware weighting | ✅ Built |
| Score spread for ATS jobs with full JDs | ✅ Working (52-73 range) |
| Score spread for board jobs with empty JDs | 🔴 Broken (all cluster 60-64) |
| role_fit as hard gate | ❌ Not built |

**Active Bugs:**

| Bug | Symptom | Root Cause |
|-----|---------|-----------|
| **B14 — Score compression (60-64 cluster)** | 70% of jobs score 60-64; ranking within that band is noise | Board jobs have desc=3c → 7/14 score dimensions default to neutral → all converge at same midpoint |
| **B15 — Score range 50-73 instead of 0-100** | No job scores <50 or >73 except outliers | Neutral defaults pull everything to center; only full-JD ATS jobs get real spread |
| **B16 — Role identity underweighted** | Wrong-domain jobs rank top-30 | role_fit is 1 of 14 equal dimensions; a job with role_fit=0 but strong location+source signals ranks mid-table |

**To Build (from chatgpt audit):**

| Item | Description | Priority |
|------|-------------|----------|
| **Role archetype as hard gating factor** | `role_fit < 0.3` → score capped at 30. No exceptions. If role is wrong, company quality/salary/etc. irrelevant. | P0 |
| **Score cap for missing JD** | If `len(description) < 200` AND full JD fetch failed → cap score at 40 regardless of other signals | P0 |
| **Multi-dimensional job identity tags in scoring** | Use Phase C/D ontology tags (`company_type`, `business_model`, `function`, `seniority`) as scoring inputs alongside raw text dimensions | P1 |

**RCA:** Scoring engine designed for full JDs. 70% of corpus (board sources) never had full JDs. Two independent fixes needed: (1) fetch full JD before scoring, (2) role archetype as hard gate — not a dimension.

---

### Phase G — Company Intelligence

**Score: 85/100**

**Goal:** Enrich shortlisted jobs with structured company research.  
**Status:** ✅ Built (1,419-line MECE implementation). Lazy-loaded per company on user interest signal. Not blocking pipeline.

This architecture is correct. Phase G should never be in the critical path.

---

## OVERALL PIPELINE SCORE: 61/100

| Phase | Score | Biggest Gap |
|-------|-------|-------------|
| A — Employer Discovery | 40/100 | No company ontology; Mumbai/Remote = 0; Playwright in wrong place |
| B — Job Boards | 55/100 | JobSpy desc=3c; Naukri dead; query expansion loses archetype |
| C — ATS Scrape | 80/100 | Works well; starved by Phase A; Workday unblocked |
| D — JD Extraction | 60/100 | No JD fetch for board URLs; no hard gate; silent failures |
| E — Role Filtering | 65/100 | role_fit=0 jobs survive; no ontology filter; title leakers |
| F — Scoring | 45/100 | Score compression; role identity not a gate |
| G — Company Intel | 85/100 | Built and correct |

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

| # | Bug | Phase | Impact | Fix |
|---|-----|-------|--------|-----|
| B1 | Wellfound Playwright in Phase A — browser opens × 12 | A | 🔴 High | Replace with DDG-only in Phase A |
| B2 | Mumbai/Remote = 0 companies | A | 🔴 High | Remote India query path; relax city check |
| B3 | Phase A queries too broad — no company ontology | A | 🔴 High | Build Role Archetype Engine; build Company Identity Layer |
| B4 | role_fit=0 jobs score 52-58 | E/F | 🔴 High | role_fit < 0.3 → hard reject in Phase E; cap at 30 in Phase F |
| B5 | JobSpy desc=3c → score compression | D/F | 🔴 High | Full JD fetch for all board URLs before Phase F |
| B6 | No hard gate on empty JDs | D | 🔴 High | `min_description_length=200` gate → reject or fetch before scoring |
| B7 | No ontology filter in Phase E | E | 🟡 Medium | Ontology filter before embedding filter |
| B8 | Title leakers (HVAC, Mech, Intern) | E | 🟡 Medium | Title blocklist — 30-minute fix |
| B9 | Query expansion loses role identity in Phase B | B | 🟡 Medium | Archetype-constrained query generation |
| B10 | Naukri dead — startpage rate limit | B | 🟡 Medium | Direct Naukri XHR or company page scrape |
| B11 | No job ontology tagging post Phase C extraction | C/D | 🟡 Medium | Job ontology classifier — tag function/market/archetype/seniority |
| B12 | Cache hits mask stale results | Pipeline | 🟡 Medium | `force_refresh` default for test runs; shorter TTL |
| B13 | Workday = 0 jobs | C | 🟢 Low | Playwright hardening + realistic headers |

---

## IMPLEMENTATION ROADMAP

### Sprint 1 — Fix scoring quality (B4 + B5 + B6) — 1 session
- `role_fit < 0.3` → hard reject in Phase E before scoring
- Full JD fetch for JobSpy/board URLs (fetch URL → parse → attach)
- `min_description_length=200` gate — reject empty JDs before Phase F
- **Expected:** score range expands to 0-100, top 10 all relevant jobs

### Sprint 2 — Fix role precision (B3 + B9) — 1-2 sessions
- Build Role Archetype Engine: role string → `{must_have, avoid, preferred_company_types}`
- Constrain Phase A SerpAPI queries with archetype
- Constrain Phase B query expansion with archetype
- **Expected:** "AI Product Engineer" stops returning infra/research/generic SWE

### Sprint 3 — Build Company Identity + Job Ontology tagging (B3 + B11) — 1-2 sessions
- Company Identity Layer: tag every company with sector/industry/B2B_B2C/stage/market
- Job ontology classifier: tag every job with function/archetype/seniority post-extraction
- Ontology filter in Phase E before embedding filter
- **Expected:** structural filtering replaces semantic guessing

### Sprint 4 — Fix discovery breadth (B1 + B2 + B10) — 1 session
- Remove Playwright from Wellfound in Phase A — DDG only
- Add Remote India query path
- Fix Naukri via direct XHR or company pages
- Title blocklist (HVAC/Mech/Intern/BPO)
- **Expected:** Mumbai + Remote return companies; no browser launches in Phase A

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
