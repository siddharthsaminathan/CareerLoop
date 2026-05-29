# Discovery Pipeline Status — 2026-05-19 (updated)

**Last updated:** 2026-05-19  
**Dry run outputs:** `test data/output/dry_run_varsha_20260518_19xx.md` (79 jobs), `test data/output/dry_run_hayagreev_20260518_1627.md` (59 jobs)  
**Target:** 150-200 ranked jobs per run | **Actual:** 39-79 jobs (up from 23)

---

## 1. End-to-End Flow (As-Built — 2026-05-19)

```
Resume / Profile (config/profile.yml + careerloop/profile_extended.yml OR profile_varsha.yml)
    ↓
RoleKeywordCache.get(role, city)
    ├── Cache hit: load keywords → re-derive city-specific queries
    └── Cache miss: token-based fallback (LLM fallback requires ANTHROPIC_API_KEY)
    ↓
OnDemandSearch.run(role, city, max_results=50, portal_companies=20)
    │
    ├── [LAYER 1] CompanyTargeting.top_n(function, city, n=20, min_function_probability=0.35)
    │       → for each ranked company:
    │           IF ats_provider not in (unknown, none, ""):
    │               ATSAdapter.fetch_jobs(id, name, provider, url)
    │                   ├── lever     → api.lever.co/v0/postings/{slug}?mode=json
    │                   ├── greenhouse → boards.greenhouse.io/embed/job_board/jobs?for={slug}
    │                   ├── ashby     → api.ashbyhq.com/posting-api/job-board/{slug}
    │                   └── workday/taleo/custom → log "no API adapter"
    │           ELIF career_page_url:
    │               [NEW] SpireAIAdapter.discover_workspace_id(career_page_url)
    │                   → GET io.spire2grow.com/ies/v1/p/workspaceId?domain={domain}
    │                   → IF workspace found: fetch all jobs via REST API (no scraping needed)
    │                   → ELSE: CareerPageCrawler.crawl(url) → JDSectionExtractor (Playwright fallback)
    │
    ├── [LAYER 2] Board Search (DDG + JobSpy)
    │       ├── SearchAdapter.search_queries(queries[:6]) → DDG → individual job URLs
    │       └── JobSpyAdapter.search_from_queries([{role, city}] × 2) → LinkedIn + Indeed
    │
    ↓
filter_india_jobs(all_jobs)
    ↓
Role relevance prefilter
    → role_tokens from search query
    → tf_head_tokens from profile.target_functions (domain-specific words only — "manager", "senior",
      "associate", "lead", "director", "specialist" etc. EXCLUDED as generic)
    → primary: title ∩ role_tokens → pass
    → secondary: title ∩ tf_head_tokens → pass (fashion/buying/merchandising domain words)
    → rejected_roles from profile.rejected_roles (YAML-driven, no hardcoding)
    ↓
deduplicate_canonical(relevant)
    ↓
IndiaFitEngine.score_jobs_batch(deduped)
    ↓
Top-N ranked output → test data/output/dry_run_{candidate}_{timestamp}.{md,json}
```

---

## 2. What Changed Since 2026-05-18

### 2.1 Spire AI Adapter — NEW

**File:** `careerloop/sources/spireai_adapter.py`

Spire AI (`spire2grow.com`) is a career portal platform used by Indian companies. Discovery is via a public REST endpoint — no scraping needed.

```
GET io.spire2grow.com/ies/v1/p/workspaceId?domain={career_page_domain}
→ returns workspace ID string (e.g. "MYNTRA-93as3")

GET io.spire2grow.com/ies/v1/p/requisition/_search
    Header: workspaceid: MYNTRA-93as3
→ returns paginated job listings (JSON)
```

**Result:** Myntra (`jobs.myntra.com`) → 14 jobs including "Principal Associate - Buying & Merchandising", "Lead Associate - Category Management (Women's Ethnic Wear)", etc.

**How it works in pipeline:** `_scrape_targeted_companies` now tries `discover_workspace_id(career_page_url)` for every company with `ats_provider=unknown/none`. If a workspace ID is found → fetch jobs via API. Otherwise → fall through to `CareerPageCrawler`.

**Companies confirmed using Spire AI:** Myntra only (as of this run). Other fashion companies (Nykaa, Fabindia, Ajio, etc.) return 404 from workspace lookup.

---

### 2.2 Career Page URLs Seeded for Fashion Companies

16 Indian fashion/retail companies now have `career_page_url` in the DB:

| Company | Career URL |
|---------|-----------|
| Myntra | https://jobs.myntra.com |
| Nykaa Fashion | https://careers.nykaa.com |
| Ajio | https://careers.ril.com |
| Fabindia | https://fabindia.com/in_en/careers |
| Arvind Fashions | https://www.arvindfashions.com/careers |
| Shoppers Stop | https://www.shoppersstop.com/careers |
| H&M India | https://career.hm.com/content/hmcareer/en_in.html |
| Bliss Club | https://blissclub.in/pages/career |
| Go Colors | https://gocolors.com/pages/careers |
| Snitch | https://snitch.co.in/pages/careers |
| Max Fashion | https://careers.maxfashion.in |
| Lifestyle Stores | https://www.lifestylestores.com/in/en/careers |
| Westside (Tata) | https://www.westside.com/pages/careers |
| Bewakoof | https://www.bewakoof.com/careers |
| Limeroad | https://www.limeroad.com/careers |
| Pantaloons | https://www.pantaloons.com/careers |

**Status of these URLs:** Most return 0 jobs because:
- They're Shopify storefronts (Bliss Club, Snitch) with no structured job listing markup
- JS-rendered SPAs (Fabindia, Arvind) — `CareerPageCrawler` requests fallback gets empty HTML
- Some 404/403 on static fetch

Only Myntra (Spire AI) actually contributes jobs from this layer.

---

### 2.3 Role Relevance Filter — Tightened

**Before:** `tf_head_tokens` included every word ≥4 chars from `target_functions` — including "manager", "senior", "associate", "lead".  
**After:** Extended stopword list excludes generic business titles:

```python
_generic = {"with", "and", "for", "the", ... ,
            "manager", "senior", "associate", "lead", "head", "director",
            "specialist", "analyst", "executive", "officer", "coordinator",
            "consultant", "principal"}
```

**Effect:** "Meesho Engineering Manager Backend" no longer passes role filter for "fashion buyer" search. "category" and "fashion" and "buying" remain as domain signals.

---

### 2.4 ATS Sector Mapping Fixed (from 2026-05-18 session)

- Paytm/fintech companies now correctly map to "Financial Services" → fn_prob(buying) = 0.02 → dropped from fashion buyer targeting
- Fashion & Retail, Apparel & Textiles sectors added to `SECTOR_FUNCTION_MATRIX`
- `_SECTOR_ALIASES` added to `FunctionProbabilityEngine` for canonical sector name matching

---

### 2.5 Lever Slug Bug Fixed (from 2026-05-18 session)

Regex `r"lever\.co/([a-z0-9_-]+)"` was extracting "v0" from `api.lever.co/v0/postings/meesho`. Fixed to `r"lever\.co/v0/postings/([a-z0-9_-]+)"`.

**Result:** Paytm (116 jobs), Meesho (45 jobs), CRED, Freshworks all fetching correctly.

---

## 3. Current Module Status

| Module | Status | Notes |
|--------|--------|-------|
| RoleKeywordCache | ✅ Working | Token-based fallback only (no LLM key) |
| CompanyTargeting | ✅ Working | fn_prob correctly excludes finance/tech for fashion roles |
| ATSAdapter (Lever) | ✅ Working | Meesho 45 jobs, Paytm 116 jobs (excluded for fashion) |
| ATSAdapter (Greenhouse) | ✅ Working | Ready when companies detected |
| ATSAdapter (Ashby) | ✅ Working | Sarvam AI etc. |
| ATSAdapter (Workday) | ❌ No adapter | Detected but 0 jobs fetched |
| SpireAI Adapter | ✅ NEW | Myntra 14 jobs |
| CareerPageCrawler | ⚠️ Partial | Only works for static HTML pages; JS-heavy pages return 0 |
| SearchAdapter (DDG) | ✅ Working | 15-20 URLs per run |
| JobSpyAdapter | ✅ Working | LinkedIn + Indeed, 20 results per query |
| IndiaFitEngine | ✅ Working | 15 dimensions, scores 47-67 range |
| Role relevance filter | ✅ Improved | Generic business words no longer pollute domain signals |
| India location filter | ✅ Working | |
| Deduplication | ✅ Working | |

---

## 4. Sources Breakdown — Varsha Dry Run (2026-05-19)

| Source | Jobs (fashion buyer / Bangalore) | Quality |
|--------|----------------------------------|---------|
| Lever (Meesho) | ~30 (after role filter) | Mixed — Meesho non-fashion roles still leak |
| SpireAI (Myntra) | 14 | ✅ High — actual buying/merchandising roles |
| JobSpy (Indeed+LinkedIn) | 28 | Medium |
| DDG search | ~17 URLs | Low (snippet only) |
| Company portals (static) | 0 | ❌ JS-heavy pages return nothing |
| **Total after filter+dedup** | **39** | |

---

## 5. Remaining Problems

### 5.1 Meesho Jobs Contaminating Fashion Results

Meesho (Lever, 45 jobs) ranks too highly for fashion buyer searches. Root cause:
- Meesho is Retail & Commerce → fn_prob(buying)=0.90 → correctly targeted
- But Meesho Lever board returns ALL functions (Engineering, HR, Finance, Sales, etc.)
- Role filter blocks some but "Design Manager", "Analytics Manager", "Portfolio Strategy" etc. pass through because they contain fashion-domain adjacent words
- **Fix needed:** After ATS fetch, score each job's title against the target function before including — not just at the prefilter stage

### 5.2 Fashion Company Portals = 0 Jobs

15/16 seeded fashion company career URLs return 0 jobs because:
- JS-rendered SPAs (React, Flutter, Angular) — `requests` gets empty shell
- `CareerPageCrawler` Playwright fallback has 20s timeout — slow and still often fails
- Companies like Bliss Club, Snitch use Shopify + basic "contact us" forms, no structured job listings
- **Fix:** Check if company uses Darwinbox / Keka / Greenhouse (not detected yet) via Playwright-rendered HTML signal scan

### 5.3 Workday 0 Jobs

BrowserStack, Uniphore detected as Workday but no jobs fetched. No Workday API adapter implemented. Workday requires authenticated sessions for their jobs API.

### 5.4 Score Range Too Compressed (47-67)

Without full JD text (description, skills, salary), 7/15 scoring dimensions default to neutral. Scores cluster. Real discrimination only possible with full JD.  
**Fix:** Activate ScrapeGraph (`SCRAPEGRAPH_API_KEY`) or Indeed direct scraper for full JD extraction.

### 5.5 Scoring Uses Wrong Profile for Dry Runs with patched ProfileManager

`target_roles` and `archetypes` in `IndiaFitEngine` are loaded from `config/profile.yml` (Hayagreev's base profile), even when running Varsha's dry run. This inflates `role_fit` scores for AI/tech roles when scoring against Varsha's fashion target. Not yet fixed.

---

## 6. What Works End-to-End

- ✅ Role → keywords (dynamic, no hardcoding)
- ✅ Keywords → company targeting (fn_prob from sector matrix)
- ✅ Company → ATS jobs (Lever/Greenhouse/Ashby)
- ✅ Company → Spire AI jobs (Myntra)
- ✅ Job boards (DDG + JobSpy LinkedIn/Indeed)
- ✅ India location filter
- ✅ Role relevance filter (profile-driven, no hardcoded lists)
- ✅ Dedup across sources
- ✅ 15-dimension scoring
- ✅ MD + JSON output

---

## 7. What Is NOT Working

- ❌ Fashion company portals (Bliss Club, Fabindia, Arvind, Nykaa etc.) → 0 jobs (JS-heavy)
- ❌ Workday adapter (BrowserStack, Uniphore detected but no jobs)
- ❌ LLM keywords (ANTHROPIC_API_KEY not set)
- ❌ ScrapeGraph JD extraction (SCRAPEGRAPH_API_KEY not set)
- ❌ Score discrimination (compressed 47-67 range due to missing JD text)
- ❌ Profile bleed: Varsha dry run uses Hayagreev's target_roles for scoring

---

## 8. Next Engineering Priorities

1. **Fix profile bleed** — `dry_run_varsha.py` should pass a fully overridden profile so `target_roles`/`archetypes` don't come from Hayagreev's `config/profile.yml`
2. **Post-ATS role filter** — after Lever/Greenhouse fetch, drop jobs whose title has 0 overlap with target_functions before adding to candidate pool
3. **Expand SpireAI discovery** — probe all company career URLs for Spire AI workspace → potential to find more companies using the platform
4. **Naukri integration** — Naukri.com has structured company pages with job listings; India's largest job board, not yet scraped
5. **Workday API adapter** — or Playwright-based Workday scraper
6. **Set env vars** — `ANTHROPIC_API_KEY` for LLM keywords, `SCRAPEGRAPH_API_KEY` for JD extraction
