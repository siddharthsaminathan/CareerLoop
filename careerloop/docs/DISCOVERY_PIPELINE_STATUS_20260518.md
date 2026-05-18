# Discovery Pipeline Status — 2026-05-18

**Author:** Hayagreev Sivakumar (dry run subject) + Claude (doc author)  
**Dry run output:** `test data/output/dry_run_hayagreev_20260518_1254.md`  
**Target:** 150-200 ranked jobs per run | **Actual:** 23 jobs

---

## 1. End-to-End Flow (As-Built)

```
Resume (test data/hayagreev_resume_0426.md)
    ↓
ProfileManager (config/profile.yml + careerloop/profile_extended.yml)
    ↓
RoleKeywordCache.get(role, city)
    ├── Cache hit: load keywords → re-derive city-specific queries (never use cached queries)
    └── Cache miss: token-based fallback (LLM fallback requires ANTHROPIC_API_KEY)
    ↓
OnDemandSearch.run(role, city, max_results=50, portal_companies=20)
    │
    ├── [LAYER 1] CompanyTargeting.top_n(function, city, n=20)
    │       → ranks companies by fn_prob×40 + ats×15 + crawl×10 + employee×15 + brand×10 + velocity×10
    │       → for each company:
    │           IF ats_provider not in (unknown, none, ""):
    │               ATSAdapter.fetch_jobs(id, name, provider, url)
    │                   ├── greenhouse → boards.greenhouse.io JSON API
    │                   ├── lever → api.lever.co/v0/postings JSON API
    │                   ├── ashby → api.ashbyhq.com/posting-api/job-board (posting-api) or
    │                   │           {slug}.ashbyhq.com/api/non-user-facing/job-board (legacy)
    │                   └── workday/custom/none → log "no API adapter, use career page crawler"
    │           ELIF career_page_url:
    │               CareerPageCrawler.crawl(url) → up to 10 JD URLs
    │               JDSectionExtractor.extract(url) → structured JD (confidence ≥ 0.6)
    │
    ├── [LAYER 2] Board Search (if include_boards=True and queries available)
    │       ├── SearchAdapter.search_queries(queries[:6])
    │       │       └── DDG DDGS (duckduckgo_search package) → individual job URLs
    │       │           (ScrapeGraphAdapter.available=False → no full JD extraction)
    │       │           → raw title + snippet only
    │       └── JobSpyAdapter.search_from_queries([{role, city, query}] × 2)
    │               → indeed.com + linkedin.com scrape
    │
    ↓
filter_india_jobs(all_jobs) — location string filter for India/TN/KA etc.
    ↓
Role relevance prefilter
    → role_signal = role_tokens | target_fn_tokens | {product, ai, ml, engineer, manager, pm, technical}
    → HARD_REJECT: hr, legal, finance, accounting, logistics, transport, social media, talent, recruiter, etc.
    → drop jobs with zero title overlap
    ↓
deduplicate_canonical(relevant)
    → sha256(normalize(company)|normalize(title)|city[:30])[:16]
    → priority: company_portal=1 > greenhouse/lever/ashby=2 > workday=3 > naukri=4 > linkedin=5
    ↓
IndiaFitEngine.score_jobs_batch(deduped)
    → 15 dimensions: title_fit, skill_fit, seniority_fit, work_mode_fit, ctc_fit, company_size_fit,
      sector_fit, startup_risk_fit, location_fit, growth_signal, jd_clarity, ai_ml_relevance,
      pedigree_bonus, ats_quality, description_depth
    → score = weighted sum → 0-100
    ↓
Top-N ranked output → test data/output/dry_run_hayagreev_{timestamp}.{md,json}
```

---

## 2. Module-by-Module Audit

### 2.1 RoleKeywordCache (`careerloop/role_keywords.py`)

| Status | Working |
|--------|---------|
| Cache hit/miss | ✅ Works |
| Token-based keyword fallback | ✅ Works (narrow) |
| City-specific query derivation | ✅ Fixed (was storing city-embedded queries in cache, causing Bangalore to get Chennai queries) |
| LLM-generated keywords (CouncilLLMClient) | ⚠️ Requires `ANTHROPIC_API_KEY` in env — not set in this run |

**Bottleneck:** Token-based fallback produces generic queries like `"ai product engineer Chennai site:linkedin.com"`. LLM path generates richer, role-aware expansions (e.g., "AI/ML product manager fintech", "technical PM LLM startup"). LLM keywords would likely 2-3× the candidate yield.

**Fix:** Set `ANTHROPIC_API_KEY` in `.env` or env before running.

---

### 2.2 CompanyTargeting (`careerloop/company_targeting.py`)

| Status | Working |
|--------|---------|
| DB load | ✅ Works |
| Scoring formula | ✅ Works |
| fn_prob computation | ✅ Works (from company sector + role heuristic) |
| City filter | ✅ Works |

**Observation:** fn_prob drives 40% of ranking. Companies with `ats_provider="none"` get `ats×15=0` (no ATS bonus). Since 34/42 companies are `"none"`, ATS bonus barely differentiates — effectively company size and brand dominate.

---

### 2.3 ATS Detection (`careerloop/detect_ats_pass.py`)

**Run result (2026-05-18):**

| Company | City | Detected ATS | URL |
|---------|------|-------------|-----|
| Meesho | Bangalore | lever | `api.lever.co/v0/postings/meesho` |
| CRED | Bangalore | lever | `api.lever.co/v0/postings/cred.club` |
| Freshworks | Chennai | lever | `api.lever.co/v0/postings/freshworks` *(slug issue — see §4.3)* |
| Paytm | Bangalore | lever | `api.lever.co/v0/postings/paytm` |
| Sarvam AI | Bangalore | ashby | `api.ashbyhq.com/posting-api/job-board/sarvam-ai` |
| BrowserStack | Bangalore | workday | `browserstack.wd1.myworkdayjobs.com/...` |
| Uniphore | Chennai | workday | `uniphore.wd1.myworkdayjobs.com/...` |
| **34 others** | both | **none** | — |

**34/42 = "none":** Their ATS is one of:
- Workday with non-standard subdomain (not `{slug}.wd1.myworkdayjobs.com`)
- SAP SuccessFactors (not probed via API)
- iCIMS / Taleo / SmartRecruiters (SmartRecruiters excluded — returns 200 for any slug = false positive)
- JavaScript-rendered career pages (HTML regex can't extract ATS signals from JS bundles)
- Custom in-house portals (TCS iBegin, Infosys career portal, etc.)

**SmartRecruiters note:** Explicitly excluded from `ATS_PROBES` because it returns HTTP 200 for any slug, making it impossible to validate existence. Previous version had all 38 companies "detected" as SmartRecruiters — all false positives.

---

### 2.4 ATSAdapter (`careerloop/sources/ats_adapter.py`)

| Provider | Status | Notes |
|----------|--------|-------|
| Greenhouse | ✅ | Boards API → JSON list of jobs with full description |
| Lever | ✅ | `postings?mode=json` → full JD text in description field |
| Ashby | ✅ | posting-api (new) + non-user-facing (legacy) both supported. `descriptionPlain` inline. |
| Workday | ⚠️ | Detected but no API adapter — falls through to career page crawler |
| SmartRecruiters | — | Not probed (false-positive risk) |
| iCIMS/Taleo/SuccessFactors | — | No adapters implemented |
| none/custom | — | Falls through to career page crawler |

**Upstream implication:** Only 5/42 companies (Meesho, CRED, Freshworks, Paytm, Sarvam AI) produce structured JD data via ATS adapters. BrowserStack and Uniphore are Workday = no API adapter = career page crawler fallback.

---

### 2.5 Company Portal Scraper (`careerloop/sources/company_portal_scraper.py`)

| Component | Status |
|-----------|--------|
| CareerPageCrawler | ✅ Functional |
| JDSectionExtractor | ✅ Functional (confidence threshold: 0.6) |

**Efficiency analysis (from dry run — portal layer):**

Crawl results observed for `ats_provider="none"` companies:
- Cognizant career page: ~4 URLs extracted
- Accenture India: ~4 URLs extracted  
- Ola Electric: ~7 URLs extracted
- Most others: 0-2 URLs (JS-heavy, require Playwright render)

**Root cause for low portal yield:**
1. `requests`-based crawler cannot execute JavaScript — modern career pages (Workday, SAP SF, custom React SPAs) render job listings entirely in JS
2. JDSectionExtractor confidence threshold (0.6) drops jobs where the HTML structure is ambiguous
3. Only 10 URLs extracted per company even if more exist

**Downstream implication:** Portal layer contributes near-zero jobs for most companies. Actual portal contributions in dry run: estimated <5 jobs total.

---

### 2.6 Job Board Scraper (`careerloop/sources/search_adapter.py` + `jobspy_adapter.py`)

#### SearchAdapter (DDG)

| Metric | Value |
|--------|-------|
| Queries fired | Up to 6 per (role × city) |
| Source | DuckDuckGo (`duckduckgo_search` package) |
| URL type filter | Only `URLType.INDIVIDUAL_JOB` pass through |
| JD extraction | None (ScrapeGraph disabled) |
| Output per query | ~3-8 individual job URLs (highly variable) |

**Efficiency:** DDG returns a mix of job board aggregate pages (linkedin.com/jobs/search, naukri.com/...) and individual listings. URL classifier filters aggregates. Individual job pages pass through but with only snippet text (20-50 words) — no full JD → scoring is title + snippet only.

**Import fix applied:** DDG package import uses try/except:
```python
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
```

#### JobSpyAdapter

| Metric | Value |
|--------|-------|
| Sources scraped | indeed.com + linkedin.com |
| Queries | 2 per (role × city) |
| Role/city passing | ✅ Fixed (was passing empty strings) |
| Description length | Full HTML stripped text (~200-800 words) |

**Before fix:** `{"query": q, "city": "", "site": ""}` → `role=""`, `city=""` → `JobSpy.scrape_jobs(site_name=["indeed", "linkedin"], search_term="", location="India")` → generic India results (random roles)

**After fix:** `{"role": role, "city": city or "India", "query": q}` → targeted results

**Efficiency:** JobSpy is the primary source of result volume in the dry run. 15-20 of the 23 final jobs came from JobSpy (Indeed + LinkedIn). Full descriptions available when JobSpy extracts them → better scoring.

---

### 2.7 ScrapeGraphAdapter (`careerloop/sources/scrapegraph_adapter.py`)

| Status | ❌ Inactive |
|--------|------------|
| `available` | `False` |
| Reason | `SCRAPEGRAPH_API_KEY` not set |
| Impact | SearchAdapter falls through to raw snippet-only mode |

**What it would do if active:** For each individual job URL from DDG, ScrapeGraph would extract structured JSON:
```json
{
  "title": "...", "company": "...", "location": "...",
  "description": "...(full text)...", "skills": [...],
  "salary": "...", "work_mode": "remote/hybrid/onsite"
}
```

**Downstream impact of absence:**
- DDG-sourced jobs have ~30-word snippets only
- `skill_fit`, `ctc_fit`, `work_mode_fit`, `description_depth` dimensions all default to neutral (0.5) → scores compressed into 44-62 range
- Full JD would spread scores 30-90 → much better discrimination

**Fix:** Set `SCRAPEGRAPH_API_KEY=<key>` in env. ScrapeGraph is a paid API (~$0.001/page).

---

### 2.8 IndiaFitEngine (`careerloop/india_fit_engine.py`)

| Status | ✅ Functional |
|--------|--------------|
| Dimensions | 15 (all active) |
| Score range observed | 44.7 – 61.7 |
| Profile source | `careerloop/profile_extended.yml` |

**Score compression cause:** Without full JD text, 7 of 15 dimensions default to neutral:
- `skill_fit` (0.5) — no skills list in JD → can't match against profile skills
- `work_mode_fit` (0.5) — mode not specified in snippet
- `ctc_fit` (0.5) — salary not in snippet
- `description_depth` (0.2) — short snippets score low
- `ai_ml_relevance` (0.5) — can't detect ML stack from title alone
- `jd_clarity` (0.3) — snippets are unclear
- `growth_signal` (0.5) — no company growth signals in snippet

**Active dimensions (scoring correctly):**
- `title_fit` — working well (title matching to target roles)
- `seniority_fit` — working (APM/PM/Sr PM level detection)
- `location_fit` — working (Chennai/Bangalore match)
- `company_size_fit` — working (employee_estimate in DB)
- `sector_fit` — working (company sector vs profile sector_preferences)
- `startup_risk_fit` — working (startup_tolerance vs employee_estimate)
- `pedigree_bonus` — working (Tier-1 company recognition)
- `ats_quality` — working (ATS provider bonus)

---

### 2.9 Role Relevance Prefilter (`careerloop/on_demand.py`)

| Status | ✅ Working |
|--------|-----------|
| Hard rejects | hr, legal, finance, accounting, logistics, transport, social media, copywriter, talent, recruiter, sales, business development, executive assistant, security engineer |
| Role signal | role_tokens ∪ target_fn_tokens ∪ {product, ai, ml, engineer, manager, pm, technical} |

**Before filter:** Meesho Lever board returned ~42 jobs (all functions). Pipeline ingested HR, Logistics, Social Media roles.  
**After filter:** Only relevant titles pass. Dry run notes confirm `role filter: 12 → 5 relevant` (AI PE/Chennai), `10 → 6 relevant` (AI PE/Bangalore).

**Edge case known:** "Quality Engineer" and "Design Automation Engineer" passed filter (contain "engineer") but are hardware/manufacturing roles, not AI product engineering. Filter is title-token-based only — cannot understand job function semantics. Symptom: ranks 44-53 scores for these jobs.

---

### 2.10 Deduplication (`careerloop/apply_route.py`)

| Status | ✅ Working |
|--------|-----------|
| Algorithm | sha256(normalize(company)∥normalize(title)∥city[:30])[:16] |
| Source priority | company_portal=1, greenhouse/lever/ashby=2, workday=3, naukri=4, linkedin=5 |

**Observed dedup rate:** 
- AI PE / Chennai: 33 raw → 4 after dedup (88% dedup rate — same jobs appearing on multiple boards)
- AI PE / Bangalore: 15 raw → 6 (60%)
- AI PM / Chennai: 33 raw → 6 (82%)
- AI PM / Bangalore: 11 raw → 7 (36%)

High dedup rates confirm: job board aggregators cross-post same listings heavily.

---

## 3. Job Board Scraper Efficiency Summary

| Source | Jobs contributed | JD quality | Notes |
|--------|-----------------|------------|-------|
| JobSpy (Indeed) | ~12 | Medium (HTML stripped) | Best volume source |
| JobSpy (LinkedIn) | ~6 | Medium | Requires JS execution sometimes |
| DDG + snippets | ~5 | Poor (30-word snippet) | ScrapeGraph would upgrade to full JD |
| ATS direct (Lever/Greenhouse/Ashby) | ~3 | High (full JSON) | Only 5 companies have working ATS |
| Company portal crawler | ~0-2 | Medium (when works) | JS-heavy pages = zero yield |
| **Total** | **~23-28** | Mixed | Target: 150-200 |

---

## 4. Bottlenecks and RCA

### 4.1 Primary: 34/42 Companies Have No Working ATS → Portal Crawler Fails on JS Pages

**Cause:** Most Indian tech companies (TCS, Infosys, Wipro, Razorpay, PhonePe, Flipkart, Amazon India, Google India, etc.) use:
- JavaScript-rendered career pages (React SPA, Workday embedded widget)
- Non-standard Workday subdomains (not `{slug}.wd1.myworkdayjobs.com`)
- SAP SuccessFactors (no public API)
- Custom portals (TCS iBegin, Infosys BPM portal)

**Current behavior:** `requests.get(career_page_url)` → gets empty HTML shell → regex finds nothing → `ats_provider="none"` → career page crawler also gets empty shell → 0 URLs extracted.

**Fix path:**
1. Add Playwright-based career page renderer to `detect_ats_pass.py` — renders JS, re-runs HTML signal scan
2. Add Workday scraper: probe `{slug}.wd5.myworkdayjobs.com` variants (not just wd1)
3. Add SAP SuccessFactors detection: look for `successfactors.com` or `sap.com/careers` in rendered HTML

**Estimated uplift:** +15-20 companies with working ATS → +50-80 additional structured jobs per run

---

### 4.2 Primary: ScrapeGraph Inactive → DDG Results Are Snippet-Only

**Cause:** `SCRAPEGRAPH_API_KEY` not set.

**Impact:** Every DDG result is a job URL with a 30-word title + snippet. No skill list, no salary, no work mode → 7/15 scoring dimensions default to neutral.

**Fix:** Set `SCRAPEGRAPH_API_KEY` in `.env`. Estimated cost: ~$0.10-0.30 per dry run (100-300 pages × $0.001).

**Alternative without ScrapeGraph:** Implement a free HTML extractor for known job board URL patterns:
- `in.indeed.com/viewjob?jk=` → scrape with `requests` + `BeautifulSoup` (no JS needed for Indeed India)
- `linkedin.com/jobs/view/` → requires cookie/auth, limited viability

---

### 4.3 Secondary: Freshworks Lever Slug Detection Bug

**Symptom:** `detect_ats_pass.py` log showed slug "v0" being extracted for Freshworks. However `_probe_api()` derives slug from domain, not URL: `freshworks.com` → `freshworks`. The `_probe_html()` path's HTML signal extraction regex may be triggering for a different URL pattern. Not fully reproduced.

**Impact:** If Freshworks Lever URL stored as `api.lever.co/v0/postings/v0`, the ATS fetch returns 404 → 0 jobs from Freshworks.

**Fix:** Add test: after detect_ats_pass run, query DB for Freshworks ATS URL, verify slug is "freshworks" not "v0". If wrong, run `detect_ats_pass --force --city Chennai` and inspect HTML signal log.

---

### 4.4 Secondary: Company DB Too Small (42 companies for 2 cities)

**Target from PRD:** 100+ companies per Tier-1 city.  
**Current:** 15 Chennai + 27 Bangalore = 42 total.

**Missing categories:**
- Chennai: Cognizant BFS, Fintech startups (Kyndryl, Tvisha, Indium), mid-size AI startups
- Bangalore: Healthtech (Practo, MediBuddy), Edtech (Byju's, Unacademy, upGrad), SaaS (Druva, Icertis, Mindtickle), gaming/media, mid-tier IT services

**Fix:** Expand `seed_companies.py` to 150+ companies. ATS detection pass then auto-discovers ATS for new entrants.

---

### 4.5 Minor: LLM Keywords Not Active

**Cause:** `ANTHROPIC_API_KEY` not set in env at run time → CouncilLLMClient falls back to token-based keyword generation.

**Token-based queries (actual, for "AI product engineer", Chennai):**
```
ai product engineer Chennai site:linkedin.com
ai product engineer Chennai site:naukri.com
product engineer Chennai AI ML jobs
```

**LLM-generated queries (expected, if active):**
```
AI product manager ML platform Chennai startup
technical product manager LLM inference India
AI/ML product engineer RLHF RAG Chennai
product manager generative AI B2B SaaS Bangalore
```

**Impact:** ~30% fewer relevant results, narrower role coverage.

**Fix:** Set `ANTHROPIC_API_KEY` in env. Keyword cache populated on first run, amortized across reruns.

---

## 5. Dry Run Output Analysis

**File:** `test data/output/dry_run_hayagreev_20260518_1254.md`

### Quality Assessment

| Combo | Raw → Dedup | Score Range | Quality Verdict |
|-------|-------------|-------------|----------------|
| AI PE / Chennai | 33 → 4 | 45-50.5 | ❌ Hardware QA/Mfg roles dominating (role filter too broad for "engineer") |
| AI PE / Bangalore | 15 → 6 | 44-53.7 | ❌ QA/NPI/Verification engineers — not AI PE |
| AI PM / Chennai | 33 → 6 | 44-61.7 | ✅ Revolut, Intellect Design, enGen, Amazon PM — genuine matches |
| AI PM / Bangalore | 11 → 7 | 45-59.1 | ✅ Nykaa PM, ShareChat APM, DigiCert PM, Google PM — genuine matches |

**AI Product Manager results are good.** Role signal is strong: "product manager" is specific, HARD_REJECT filters hardware roles correctly.

**AI Product Engineer results are poor.** "Engineer" is too generic — QA engineers, manufacturing engineers, verification engineers all pass the title filter. Needs a tighter prefilter: require at least one of {ai, ml, product, llm, platform, backend} in title when role contains "engineer".

---

### Genuine Matches (Human Assessment)

**Likely worth pursuing:**
1. Google — Product Manager, Payment Platform (Bangalore) — 57.9
2. Nykaa — Product Manager II - Personalisation (Bangalore) — 59.1
3. Amazon — Senior Product Manager, Retail Business Services (Chennai) — 56.7
4. Revolut — Operations Manager (Product) (Chennai) — 61.7
5. ShareChat — Associate Product Manager (Bangalore) — 59.1
6. Intellect Design Arena — Product Manager (Chennai) — 61.7

**False positives:**
- Cisco Quality Engineer NPI — hardware manufacturing
- Flipkart Design Automation Engineer — chip design automation
- Intel IP Verification Engineer — semiconductor verification
- Nokia Manufacturing CI Engineer — manufacturing ops

---

## 6. Path to 150-200 Jobs

| Action | Estimated Yield Increase | Effort |
|--------|------------------------|--------|
| Set `ANTHROPIC_API_KEY` → LLM keywords | +15-30 jobs | 1 min (env var) |
| Set `SCRAPEGRAPH_API_KEY` → full JD from DDG | +0 jobs (better quality only) | 1 min (env var) |
| Add Playwright to `detect_ats_pass.py` | +50-80 jobs (from JS-heavy companies) | Medium (2-4 hrs) |
| Expand company DB to 150 companies | +30-50 jobs | Low (1 hr) |
| Workday wd3/wd5 subdomain probing | +10-20 jobs | Low (30 min) |
| Add SAP SuccessFactors detection | +5-10 jobs | Low (1 hr) |
| Tighten "AI Product Engineer" role filter | 0 new jobs, -5 false positives | Low (15 min) |
| Indeed India direct scraper (no ScrapeGraph needed) | +20-40 jobs with full JD | Medium (2 hrs) |

**Realistic path:** LLM keywords + 150 companies + Playwright ATS detection → ~80-120 jobs per run. Full ScrapeGraph + Indeed direct scraper → 150-200.

---

## 7. What Is Working

- ✅ End-to-end pipeline runs without crashing
- ✅ Real job links with URLs in output (not mocks)
- ✅ India location filter (TN/KA/IN city codes)
- ✅ Role relevance prefilter (prevents full company job dumps)
- ✅ City-aware search queries (Bangalore gets Bangalore queries)
- ✅ ATS detection is dynamic (no hardcoded slugs)
- ✅ Lever/Greenhouse/Ashby adapters return full JD JSON
- ✅ JobSpy (Indeed + LinkedIn) working with correct role+city targeting
- ✅ Deduplication across sources
- ✅ 15-dimension scoring with profile-aware weights
- ✅ MD + JSON output to test data/output/
- ✅ DB-backed company registry (SQLite)
- ✅ Seeded 42 companies with clean identity data (no hardcoded ATS)

---

## 8. What Is Not Working

- ❌ 34/42 companies have no working ATS → portal layer contributes near-zero jobs
- ❌ ScrapeGraph inactive (`SCRAPEGRAPH_API_KEY` not set) → DDG results are snippet-only
- ❌ LLM keywords inactive (`ANTHROPIC_API_KEY` not set at run time) → narrow token-based queries
- ❌ JS-heavy career pages yield 0 from HTML scraper (Workday, SAP SF, React SPAs)
- ❌ "AI Product Engineer" role filter too broad → hardware QA/verification jobs pass through
- ❌ Company DB too small (42 vs 150+ target)
- ❌ Workday adapter not implemented (BrowserStack, Uniphore detected but no jobs fetched)
- ❌ Freshworks Lever slug possibly incorrect (needs verification)
- ❌ No SmartRecruiters adapter (false-positive risk prevents adding)
- ❌ DeepSeek LLM provider not integrated in CouncilLLMClient (pending)

---

## 9. Upstream/Downstream Implications

### If ATS detection improves (Playwright rendering):
- Upstream: detect_ats_pass.py runs longer (10-30s per company vs 2s)
- Downstream: ATSAdapter gets real provider+url → structured JD for 30+ more companies → skill_fit/work_mode_fit/ctc_fit score correctly → score range spreads from 44-62 to 30-90 → ranking becomes meaningful

### If ScrapeGraph activates:
- Downstream: all DDG-sourced URLs get full JD extraction → same scoring improvement as above
- Cost: ~$0.10-0.30/run

### If company DB expands to 150:
- Upstream: detect_ats_pass.py needs one more detection pass after seeding
- Downstream: CompanyTargeting.top_n has more candidates → better fn_prob distribution → portal layer more targeted

### If "AI Product Engineer" title filter tightens:
- Downstream: false positives drop → precision improves → user trust in results increases
- Risk: may over-filter legitimate AI infra / platform engineering roles

### If DeepSeek integrates in CouncilLLMClient:
- Upstream: RoleKeywordCache can use DeepSeek as LLM fallback (cheaper than Anthropic per token)
- Downstream: Better keywords → better DDG queries → more relevant candidates

---

## 10. Next Engineering Priorities (Ordered)

1. **Set env vars** — `ANTHROPIC_API_KEY` for LLM keywords, `SCRAPEGRAPH_API_KEY` for JD extraction  
   *Impact: highest ROI per minute of work*

2. **Tighten AI PE role filter** — require {ai, ml, product, llm, platform} in title when role is "product engineer"  
   *Impact: eliminates hardware false positives immediately*

3. **Expand company DB** — add 50-100 companies to seed_companies.py (healthtech, edtech, SaaS, gaming)  
   *Impact: more portal candidates, more ATS hits*

4. **Workday wd3/wd5 probing** — add to ATS_PROBES in detect_ats_pass.py  
   *Impact: BrowserStack, Uniphore, possibly 5-10 more companies*

5. **Playwright ATS detection** — render JS career pages, re-run HTML signal scan  
   *Impact: biggest yield increase but most engineering effort*

6. **DeepSeek in CouncilLLMClient** — OpenAI-compatible, `api.deepseek.com`, model `deepseek-v4-pro`  
   *Impact: cheaper LLM fallback for keyword generation*

7. **Indeed India direct scraper** — `requests` + `BeautifulSoup` for `in.indeed.com/viewjob?jk=` URLs  
   *Impact: free full JD extraction for Indeed results without ScrapeGraph*
