# Discovery Engine Audit — 2026-05-26

> Evidence-based audit from live pipeline run + code inspection.  
> Data source: `siddharth_bangalore_full_run_20260523_2317.json` + `audit_20260523_2343.log`  
> Implementation tracker: `docs/product/SEARCH_VISION.md`

---

## TL;DR

Infrastructure is mostly correct. The bottleneck is **semantic precision**, not scraping.

The system retrieves from the **AI labor market**. It should retrieve from **this user's AI labor market**.

Root cause: **role identity lost at retrieval time** — Phase A company discovery and Phase B query expansion both ignore role archetype. Everything downstream inherits contaminated input.

---

## Live Run Stats (2026-05-23 full run)

| Role | City | Jobs ranked | Elapsed | Cache hit? |
|------|------|-------------|---------|------------|
| AI Product Engineer | Bangalore | 29 | 0s | ✅ Cache hit — stale data |
| Full Stack AI Engineer | Bangalore | 17 | 0s | ✅ Cache hit — stale data |
| Applied AI Engineer | Bangalore | 34 | 620s | Live run |
| Founding AI Engineer | Bangalore | 34 | 454s | Live run |
| Any role | Mumbai | 0 | — | Phase A returned 0 companies |
| Any role | Remote | 0 | — | Phase A returned 0 companies |

**SerpAPI calls across all 3 runs this session: ~30 calls (not 59).**  
The 59 figure came from multiple pipeline runs across the day (v1–v5). Each full run = 12 discover() calls × 2 queries = 24 SerpAPI calls. Code is correct. Multiple invocations is the cause.

---

## Job Quality — Live Runs Only

### Applied AI Engineer @ Bangalore (34 jobs, 620s)

**Score range:** 52–73. **Avg:** 61.5

| # | Score | Title | Company | Source | Desc |
|---|-------|-------|---------|--------|------|
| 1 | 73 | Forward Deployed Software Engineer | Sarvam AI | ashby | 5889c ✅ |
| 2 | 71 | Applied AI Principal/Staff Engineer | Best Tech Jobs | greenhouse | 0c ❌ |
| 3 | 69 | Applied AI Engineer - AI Labs | i2e Consulting | scrapegraph | 3113c ✅ |
| 4 | 69 | ML Engineer (Data), Foundational Models | Sarvam AI | ashby | 4587c ✅ |
| 5 | 67 | Applied AI Engineer | SpotDraft | scrapegraph | 4466c ✅ |

Source breakdown: ashby×3, greenhouse×1, scrapegraph×8, foundit×6, glassdoor×1, jobspy×8, google_jobs×6  
Empty desc (<100c): 9/34 jobs

**Verdict: Good run.** Sarvam AI, SpotDraft, Contrails AI, neuroGrid are all legit targets.

### Founding AI Engineer @ Bangalore (34 jobs, 454s)

**Score range:** 52–73. **Avg:** 62.2

| # | Score | Title | Company | Source | Desc |
|---|-------|-------|---------|--------|------|
| 1 | 73 | Forward Deployed Software Engineer | Sarvam AI | ashby | 5889c ✅ |
| 2 | 73 | Backend Engineer, API Team | Sarvam AI | ashby | 3366c ✅ |
| 3 | 72 | Backend Engineer, Chanakya | Sarvam AI | ashby | 3932c ✅ |
| 4 | 70 | Founding AI Engineer | Knowl | scrapegraph | 3029c ✅ |
| 5 | 68 | Founding AI Engineer | NeoSapien | scrapegraph | 3455c ✅ |

Empty desc (<100c): 16/34 jobs

**Verdict: Good top-10. Sarvam AI dominates top 3 (same ATS, different roles). Knowl, NeoSapien, Figr, Prodigal all correct targets.**

### Cache Runs (AI Product + Full Stack AI)

**These are stale.** Pipeline never ran. Data from a previous crawl.

Full Stack AI: 82% jobspy with desc=3c. Sarvam AI appears at rank 2 but with 3-char description — same job, wrong source, no data.

---

## Phase-by-Phase Evidence

### Phase A — Company Discovery

**Evidence from audit log:**
```
sector=Technology & Software — Phase A via SerpAPI+Wellfound+Crunchbase+Inc42+YC...
```
All 12 searches collapsed to same sector. SerpAPI fired 2 queries per search (correct). Wellfound triggered Playwright (browser opened) per search.

**Key finding:** Phase A returned 210 companies for Applied AI @ Bangalore and 0 companies for Mumbai/Remote. The company DB is only populated for Bangalore. This is not a seeding problem — Phase A's queries don't find companies for non-physical cities because DDG/SerpAPI snippets don't mention "Remote" in company context.

### Phase B — Job Boards

**Evidence from board health note:**
```
board health: ddg:35 | glassdoor:30 | google_jobs:30 | jobspy:40 | monster:25 | naukri:20
```

Naukri returned 20 despite the startpage error — it partially succeeded. Google Jobs (DDG→ATS URLs) is a standout: finds real Greenhouse/Lever/Ashby job links by DDG-searching ATS domains directly. This is the highest-quality board source.

JobSpy returns 40 results per search but desc=3c for nearly all. These pollute Phase F.

### Phase C — ATS Portal Scrape

Working correctly for Bangalore. The 3 Ashby jobs from Sarvam AI (scores 72-73) came from Phase C. Greenhouse job came from Phase C. These are the best results in the entire dataset.

Phase C is the **highest-quality source**. The goal should be to maximize Phase C coverage, not Phase A breadth.

### Phase D — JD Extraction

ATS jobs (ashby, greenhouse): 3000-6000c descriptions. ✅  
Scrapegraph jobs: 900-4500c descriptions. ✅  
JobSpy jobs: 3c descriptions. 🔴  
Foundit jobs: 0-500c descriptions. ⚠️

Silent failures: no log entry when extraction returns empty. Jobs enter Phase F regardless.

### Phase E — Role Filtering

Applied filter dropped: 168 → 114 relevant (54 rejected), then city filter 114 → 55, then company cap → 34.

**Problem found:** Jobs with `role_fit=0` still score 52-58. A "Founding AI/LLM Integration Engineer" with zero role fit scored 53.9 because location/startup/source signals were strong. This is catastrophic — the filter passed it, and the scorer promoted it.

### Phase F — Scoring

Score range confirms the analysis:
- ATS jobs (full JD): score 67-73
- Scrapegraph jobs (partial JD): score 64-69
- JobSpy jobs (no JD): score 60-64 (all at same level — pure noise)
- Bad-domain jobs: score 52-56

The 60-64 band contains both real jobs and garbage. No way to distinguish from score alone.

---

## The Real Root Cause

```
semantic intent drift between user archetype and retrieval archetype
```

**Current system:**
- `"AI Product Engineer"` → query: `"well-funded AI startup Bangalore India hiring 'AI Product Engineer' 2025"`
- This finds: AI companies. ANY AI company.
- Then ATS fetches ALL jobs from that company.
- Role filter tries to clean up.

**Problem:** The role filter is doing company-level work. It shouldn't have to. Company discovery should already target companies that hire product-oriented AI roles, not all AI companies.

**What needs to change:**
1. Phase A needs: `"B2B AI SaaS product company"` not `"AI company"`
2. Phase B needs: `must_have=[product, platform, customer]` constraints on query expansion
3. Phase E needs: `role_fit < 0.3` = hard reject, not a scored dimension
4. Phase F needs: `len(description) < 200` = hard reject before scoring

**These are the 4 fixes. Nothing else is broken.**

---

## What Is Working Well

| Component | Quality |
|-----------|---------|
| ATS adapters (14) | Strong — Greenhouse, Lever, Ashby all fetch correctly |
| L1 network interception | Strong — intercepts XHR/fetch, detects hidden APIs |
| L2 DOM extraction | Good |
| Sarvam AI via Ashby | Best result in corpus — proves the ATS pipeline works |
| Google Jobs DDG adapter | Best board source — finds real ATS URLs |
| India location filter | Working at 3 choke points |
| Deduplication | Working |
| SQLite dual-mode DB | Working — unblocks local dev |
| SerpAPI 2-call cap | Working — 24 calls per full run (not 59) |

---

## Priority Fix List

1. **`role_fit < 0.3` → hard reject** before scoring — stops garbage jobs from ranking
2. **Full JD fetch for JobSpy URLs** — fetch actual job page, parse description — fixes score compression
3. **Role Archetype Engine** — pre-retrieval constraint layer — `{must_have, avoid, preferred_company_types}` — fixes Phase A + B query quality
4. **`min_description_length=200` gate** in Phase D → reject before Phase F
5. **Title blocklist** in Phase E — HVAC, Mechanical, Hardware, Intern, BPO — 10-minute fix
6. **Remote/Mumbai Phase A path** — "Remote India AI startup" query; city check relaxed for Remote

See full tracker: `docs/product/SEARCH_VISION.md`
