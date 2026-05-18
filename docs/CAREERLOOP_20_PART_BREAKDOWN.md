# CAREERLOOP — 20-PART ARCHITECTURE BREAKDOWN
## India AI Job Discovery & Application Pipeline
### v1 Audit + v2 Vision | May 17, 2026

---

## PART 1 — WHAT WE BUILT (v1 SCOPE)

CareerLoop is a **fork of santifer/Career-Ops** (open-source AI job search pipeline) with a **hyper-localized India layer** added on top. The parent project provides job board scanning, ATS-optimized CV generation, and pipeline tracking. We built:

1. **India Job Discovery Engine** — multi-source job hunting locked to Tier-1 Indian cities
2. **14-Dimension India Fit Engine** — heuristic scoring without LLM calls
3. **India Lock Geographic Filter** — rejects international jobs
4. **LangGraph Resume Council** — 7-stage DeepSeek pipeline for application packs
5. **Application Ledger** — persistent job tracking with 13-status lifecycle
6. **Search Page Rejection Filter** — blocks non-job URLs (Naukri search pages, blogs, career advice)

---

## PART 2 — CURRENT ARCHITECTURE (FULL STACK)

```
CONFIG LAYER
  profile.yml + profile_extended.yml → user identity, target roles, salary floor
  cv.md → master resume

DISCOVERY LAYER (careerloop/discovery.py)
  RoleStrategyGenerator → generates search queries from profile
  SearchAdapter (DuckDuckGo) → site-scoped queries → candidate URLs
  JobSpyAdapter → multi-board (LinkedIn, Indeed, Glassdoor)
  ScrapeGraphAdapter → deep extraction (Playwright rendering, HTML→JSON)
  india_filter.py → geographic hardening (India-only)

VERIFICATION LAYER (careerloop/verification.py)
  JobVerifier → checks posting liveness, URL reachability
  apply_route.py → merge cross-source duplicates, resolve apply route

SCORING LAYER (careerloop/india_fit_engine.py)
  14 dimensions, 0-100, heuristic (no LLM)
  Role fit + Skill fit + Salary + Location + Work mode + Company stability + Brand value + ...

LEDGER LAYER (careerloop/application_ledger.py)
  Persistent job tracking (ledger.json)
  13 statuses: DISCOVERED → SHORTLISTED → SENT_TO_USER → APPROVED → APPLIED → ...

COUNCIL LAYER (careerloop/council/)
  LangGraph state machine → 7 DeepSeek stages
  Company Intel → Role Decode → User Truth → Fit/Gap → Positioning → Resume Plan → Application Pack

MEMORY LAYER (careerloop/memory/)
  SQLite persistence (careerloop.db)
  6 tables: users, strategic_tracks, application_ledger, company_memory, positioning_memory, event_timeline

OUTPUT LAYER (careerloop/shortlist_formatter.py)
  WhatsApp-style daily shortlist
  Top 5 jobs with fit score + breakdown
```

---

## PART 3 — SOURCE ADAPTERS (WHAT EXISTS)

| Adapter | File | Status | What It Does |
|---------|------|--------|-------------|
| SearchAdapter | sources/search_adapter.py | ✅ LIVE | DuckDuckGo free search → candidate job URLs |
| ScrapeGraphAdapter | sources/scrapegraph_adapter.py | ✅ LIVE | Deep extraction via Playwright rendering + HTML→JSON |
| JobSpyAdapter | sources/jobspy_adapter.py | ✅ LIVE | Multi-board search (LinkedIn, Indeed, Glassdoor) |

**Job board URL patterns allowed (search_adapter.py):**
LinkedIn view pages, Naukri listings, Cutshort, Instahyre, Wellfound, Hirist, IIMJobs, Foundit, WorkIndia, Apna, Shine

**What does NOT exist:**
- ❌ Direct company career page scraper (Anthropic, OpenAI, Stripe, etc.)
- ❌ Greenhouse/Ashby/Lever API adapter (exists in parent repo but blocked for India)
- ❌ Company talent pool builder (no company database)
- ❌ Dynamic keyword generator from LLM

---

## PART 4 — INDIA FIT ENGINE DIMENSIONS

14 weighted dimensions, heuristic scoring (NO LLM calls per job):

| Dimension | Weight | Scoring Method |
|-----------|--------|---------------|
| role_fit | 15 | Title match vs target roles + archetypes |
| skill_fit | 15 | Keyword match vs confirmed skills |
| salary_fit | 10 | Extracted salary vs ₹25L floor |
| location_fit | 10 | City match vs preferences |
| work_mode_fit | 8 | Remote/hybrid/onsite match |
| notice_period_fit | 5 | Notice period alignment |
| company_stability | 7 | Lookup table (Google=10, startup=5) |
| startup_risk | 5 | Inverted — lower is better |
| brand_value | 6 | Career resume value lookup |
| commute_risk | 4 | Distance from preferred city |
| assignment_burden | 3 | Role complexity |
| interview_difficulty | 3 | Inverted — easier is better |
| response_likelihood | 5 | Company response probability |
| career_trajectory | 4 | Career growth potential |

**Current scores:** 141 jobs, avg 62.8/100. 33 GO (70+), 101 MAYBE, 7 SKIP.

---

## PART 5 — SEARCH PAGE REJECTION FILTER (TODAY'S FIX)

Added `_reject_if_not_job()` to India Fit Engine with 17 regex patterns:

**Catches:**
- Naukri search results (`naukri.com/ai-engineer-jobs-in-chennai`)
- LinkedIn job search pages (`/jobs/ai-engineer-jobs`)
- Cutshort category pages (`cutshort.io/jobs/`)
- Foundit/Instahyre/Hirist category listings
- Blog posts, career advice articles, interview prep
- "Highest paying jobs" listicles
- "How to become" career guides

**Result:** 47 of 141 jobs rejected as search pages. 65 real jobs scored.

---

## PART 6 — LANGGRAPH RESUME COUNCIL (v1.0)

7-stage DeepSeek pipeline. ~$0.02 per run. 90 seconds.

| Stage | Input | Output | LLM |
|-------|-------|--------|-----|
| S1: Company Intelligence | JD text | Company snapshot, culture, red flags | DeepSeek |
| S2: Role Decode | JD text | Must-have skills, hidden expectations, Day 1 plan | DeepSeek |
| S3: User Truth Check | CV + JD | Confirmed skills, weak claims, gaps, fit score | DeepSeek |
| S4: Fit/Gap Analysis | S1+S2+S3 | Overall fit, recruiter objections, application stance | DeepSeek |
| S5: Positioning Strategy | S4 + CV | Positioning angle, lead story, headline, narrative | DeepSeek |
| S6: Resume Plan | CV + S5 | Bullet rewrites, skills to add/remove, risky claims | DeepSeek |
| S7: Application Pack | S5 + profile | Cover note, recruiter DM, follow-up, quality score | DeepSeek |

**Tested on:** Nicobar AI Product Engineer role. Fit: 85/100. Quality: 88/100. Tech fit: 90/100.

---

## PART 7 — WHAT'S MISSING (v1 GAPS)

| Gap | Severity | Phase 2 Doc Reference |
|-----|----------|----------------------|
| Section Writers (auto-assemble resume) | HIGH | PHASE_2_RESUME_COUNCIL.md |
| Truth Guard (independent verification) | HIGH | PHASE_2_RESUME_COUNCIL.md |
| HR Reader (10-second recruiter scan) | MEDIUM | PHASE_2_RESUME_COUNCIL.md |
| Humanizer (dedicated AI-strip pass) | MEDIUM | PHASE_2_RESUME_COUNCIL.md |
| Final Assembler (auto PDF/docx) | HIGH | PHASE_2_RESUME_COUNCIL.md |
| Score persistence (ledger update) | CRITICAL | Fixed today |
| Company career page scraper | HIGH | NOT IN ANY DOC |
| Dynamic keyword generator | HIGH | NOT IN ANY DOC |
| Top-N company targeting | HIGH | NOT IN ANY DOC |
| On-demand search trigger | MEDIUM | NOT IN ANY DOC |

---

## PART 8 — THE VISION: v2 COMPANY-PORTAL ARCHITECTURE

**Problem:** Job boards only show ~30% of available AI jobs. Companies like Anthropic, OpenAI, Stripe, Supabase post on their own career pages — never on Naukri or LinkedIn. We're missing 70% of the market.

**Solution:** Add a Company Portal layer to the discovery pipeline:

```
┌─────────────────────────────────────────────────────────┐
│              v2 DISCOVERY ARCHITECTURE                    │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  LAYER 1: JOB BOARDS (existing)                           │
│    DuckDuckGo → Naukri/LinkedIn/Cutshort/Instahyre       │
│                                                           │
│  LAYER 2: COMPANY PORTALS (NEW)                           │
│    Company DB → Career Page URLs → ScrapeGraphAI Extract  │
│    → India Filter → Verify Active → Score                 │
│                                                           │
│  LAYER 3: DYNAMIC KEYWORDS (NEW)                          │
│    User Role → LLM call → Keywords → Store in DB          │
│    Next search: DB lookup → no LLM cost                   │
│                                                           │
│  LAYER 4: TOP-N TARGETING (NEW)                           │
│    Score all companies in sector → Rank → Top 30/50       │
│    Scrape their career pages → Build job pool             │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## PART 9 — COMPANY DATABASE DESIGN

**What we need:** A database of AI/tech companies in India, organized by Tier-1 city.

**Schema:**
```sql
CREATE TABLE companies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    career_page_url TEXT,         -- e.g., anthropic.com/careers
    greenhouse_url TEXT,          -- if using Greenhouse ATS
    lever_url TEXT,               -- if using Lever ATS
    ashby_url TEXT,               -- if using Ashby ATS
    city TEXT,                    -- Chennai/Bangalore/Mumbai/Delhi/Hyderabad/Pune
    sector TEXT,                  -- AI/ML, SaaS, Fintech, Healthtech, etc.
    employee_count INTEGER,
    funding_stage TEXT,           -- Seed/Series A/B/C/Public
    last_scraped_at TIMESTAMP,
    job_count INTEGER,
    is_active BOOLEAN
);
```

**Seeding strategy:**
- LinkedIn company search: "AI companies in Chennai"
- Crunchbase/TC funding lists filtered for India
- YC companies with India presence
- Wellfound/Instahyre company directories

---

## PART 10 — DYNAMIC KEYWORD GENERATOR

**Current problem:** Keywords are hardcoded in the fit engine (`ai_signals = ["ai", "llm", "ml", "agent"...]`). If someone searches for "fashion buyer" or "supply chain analyst," the system has no keywords.

**Solution:** LLM-powered keyword cache:

```
User searches "fashion buyer job Chennai"
    → Check DB: keywords for "fashion buyer" exist?
    → NO → Call DeepSeek: "Generate 20 search keywords for 'fashion buyer' roles in India"
    → Store in DB: {role: "fashion buyer", keywords: [...], generated_at: ...}
    → Use keywords for search
    → Cache hit next time: 0 LLM cost

User searches "AI engineer" again
    → Check DB: keywords exist
    → YES → Use cached keywords
    → 0 LLM cost
```

**Schema:**
```sql
CREATE TABLE role_keywords (
    role_name TEXT PRIMARY KEY,
    keywords TEXT NOT NULL,       -- JSON array
    search_queries TEXT,          -- JSON array of ready-to-use search strings
    generated_at TIMESTAMP,
    usage_count INTEGER DEFAULT 1,
    last_used_at TIMESTAMP
);
```

---

## PART 11 — TOP-N COMPANY TARGETING

**Concept:** Instead of scraping ALL companies, start with the top 30 AI/tech companies per city. If user doesn't find anything, expand to next 30.

**Algorithm:**
1. Fetch all companies in city X, sector "AI/ML"
2. Score each company: (brand_value × 2) + company_stability + funding_maturity
3. Sort descending → Top 30
4. For each company: check if career page has new jobs since last scrape
5. If yes → ScrapeGraphAI extract → India Filter → Score → Ledger
6. Present to user
7. If user says "show more" → expand to next 30

**Scoring weights for company ranking:**
```
company_rank = (BRAND_VALUE_SIGNALS[name] × 2) 
             + COMPANY_STABILITY_SIGNALS[name]
             + funding_score(funding_stage)
```

---

## PART 12 — ON-DEMAND SEARCH ARCHITECTURE

**Current:** Cron-based daily runner (passive, batch).

**v2: On-demand triggers:**
1. User types: "Find AI Product Engineer jobs in Chennai"
2. System checks DB: when was last search for this role+city?
3. If < 6 hours → return cached results
4. If > 6 hours → trigger fresh search:
   - Dynamic keywords → DuckDuckGo → ScrapeGraphAI → Score → Ledger
5. Return top 10 jobs immediately
6. Continue background scoring for remaining jobs

**User experience:**
```
User: "Find me AI product jobs in Bangalore"
System: "Searching... Found 8 new jobs. Top 3:
  1. Anthropic — Applied AI Engineer (92/100)
  2. Stripe — ML Platform Engineer (88/100)  
  3. Supabase — AI Product Engineer (85/100)
  Scoring 5 more in background. Full results in 2 minutes."
```

---

## PART 13 — FILES INVENTORY

### Core Pipeline (careerloop/)
```
discovery.py          (21KB) — Discovery engine: search → extract → filter → verify
india_fit_engine.py   (21KB) — 14-dimension heuristic scoring
india_fit_llm.py      (9KB)  — LLM-based scoring alternative
india_filter.py       (6KB)  — Geographic hardening
daily_runner.py       (11KB) — Daily pipeline orchestrator
application_ledger.py (9KB)  — Job persistence + status lifecycle
shortlist_formatter.py (7KB) — WhatsApp-style output
profile_manager.py    (6KB)  — User profile + preferences
verification.py       (6KB)  — Job liveness verification
apply_route.py        (6KB)  — Cross-source dedup + apply routing
role_strategy.py      (10KB) — Role-specific search strategy
models.py             (13KB) — Data contracts + type definitions
config.py             (5KB)  — Weights, signals, city maps
audit.py              (5KB)  — Pipeline health checks
```

### Council (careerloop/council/)
```
graph.py        (16KB) — LangGraph state machine
stages.py       (12KB) — Deterministic fallbacks
llm.py          (3KB)  — DeepSeek client
models.py       (4KB)  — Typed contracts
context.py      (2KB)  — Job context builder
orchestrator.py (3KB)  — One-job runner
```

### Sources (careerloop/sources/)
```
search_adapter.py      (9KB) — DuckDuckGo search
scrapegraph_adapter.py (3KB) — Deep extraction
jobspy_adapter.py      (2KB) — Multi-board search
```

### Memory (careerloop/memory/)
```
models.py      — SQLAlchemy models
connection.py  — SQLite connection
repository.py  — CRUD operations
retrieval.py   — Query layer
```

### Docs
```
PHASE_1_PIPELINE.md            — Discovery engine spec
PHASE_2_RESUME_COUNCIL.md       — Council vision (full pipeline)
PHASE_2_IMPLEMENTATION_PLAN.md  — Council implementation plan
ARCHITECTURE.md                 — System overview
CAREERLOOP_V1_LOCK.md           — v1 lock + validation
daily-dev-blog-2026-05-14.md    — May 14 dev log
```

---

## PART 14 — WHAT WE SCORE WELL

✅ **Strengths:**
- Multi-source discovery (DDG + JobSpy + ScrapeGraphAI)
- Heuristic scoring is fast (no LLM cost per job)
- India-only geographic lock
- LangGraph Council produces real application packs
- 14 dimensions cover most fit signals
- Search page rejection filter added today
- Memory layer with SQLite persistence
- Profile customization (salary floor, city preferences, role targets)

---

## PART 15 — WHAT WE SCORE POORLY

❌ **Weaknesses:**
- Only seeing ~30% of available jobs (job boards only)
- Keywords hardcoded — can't handle non-AI roles without code changes
- No company career page scraping
- No company database
- Ledger scores not persisted (fixed today)
- Council missing 5 of 12 planned stages
- No on-demand search trigger
- Formatter only shows top 5
- No multi-user support (single profile)
- No WhatsApp delivery (planned, not built)

---

## PART 16 — v2 ROADMAP (PRIORITY ORDER)

### P0 — This Week
1. **Company career page scraper** — target Anthropic, OpenAI, Stripe, Supabase career pages directly
2. **Score persistence fix** — ✅ DONE today (daily_runner now saves scores)
3. **Search page rejection** — ✅ DONE today (_reject_if_not_job added)

### P1 — Next Week
4. **Dynamic keyword generator** — LLM → keyword cache → search
5. **Top-30 company targeting** — rank → scrape → pool
6. **Full shortlist display** — show all jobs, not just top 5

### P2 — This Month
7. **On-demand search trigger** — user types query, system hunts
8. **Company database seeding** — top 100 AI companies in Tier-1 cities
9. **Council v1.1** — Section Writers + Humanizer + Truth Guard

### P3 — Next Month
10. **Multi-user profiles** — girlfriend's instance, paid users
11. **WhatsApp delivery** — daily shortlist via WhatsApp
12. **Monetization** — $9/mo individual, $29/mo pro

---

## PART 17 — INFRASTRUCTURE GAPS

| Gap | Impact | Fix |
|-----|--------|-----|
| No rate limiting on DDG | Can get blocked | Add exponential backoff |
| ScrapeGraphAI costs unknown | Could be expensive | Track API costs |
| No CI/CD | Manual deploys | GitHub Actions |
| No monitoring | Silent failures | Add health check endpoint |
| No backup | Data loss risk | Git backup or S3 sync |
| Single machine | No scale | Docker + Fly.io deploy |

---

## PART 18 — METRICS & NORTH STAR

**Current:**
- 141 jobs discovered
- 33 GO (70+), 101 MAYBE, 7 SKIP
- 47 rejected as search pages
- ~$0.02 per Resume Council run
- 0 applications submitted (pipeline not connected to apply)

**Target (v2):**
- 500+ jobs discovered (with company portals)
- 100+ GO jobs
- <$0.05 per full pipeline run
- On-demand search < 60 seconds
- 1 application per day throughput

**North Star Metric:** Applications submitted per week.

---

## PART 19 — FILE ORGANIZATION (CURRENT)

```
~/Projects/CareerLoop/
├── careerloop/           ← All core Python modules
├── config/               ← profile.yml, models.yml
├── cv.md                 ← Master resume
├── docs/                 ← Vision docs, phase plans
├── output/               ← Council outputs, test runs
│   └── test-runs/nicobar/ ← Nicobar application pack
├── reports/              ← Daily shortlists
├── data/                 ← Pipeline inbox, imports
├── modes/                ← Claude Code slash commands
├── templates/            ← CV templates (HTML, LaTeX)
├── dashboard/            ← Go TUI dashboard
├── batch/                ← Batch processing scripts
├── examples/             ← Example CV + config
├── .claude/              ← Claude Code skills
├── .opencode/            ← OpenCode slash commands
├── .gemini/              ← Gemini CLI commands
└── run_council.py        ← Council CLI runner
```

---

## PART 20 — HANDOFF SUMMARY

**What we built:** A hyper-localized India AI job discovery pipeline on top of open-source Career-Ops. Multi-source search → geographic filtering → 14-dimension scoring → LangGraph Resume Council → application pack generation.

**What we fixed today:** Search page rejection filter (47 jobs caught), score persistence, ledger export.

**What's next:** Company career page scraping (70% of jobs are invisible to us), dynamic keyword generation (LLM-powered, cached), top-N company targeting.

**The vision:** CareerLoop becomes the "Google for India AI jobs" — search once, get every relevant job across every source (job boards + company portals), scored against your profile, with ready-to-send application packs. On-demand, not batch. Smart, not spammy.

**Repository:** github.com/siddharthsaminathan/CareerLoop

---

*v2 vision drafted May 17, 2026. v1 locked + validated.*
