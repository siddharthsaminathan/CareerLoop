# Career-Ops — Complete System Breakdown & Enhancement Roadmap

**Author:** Siddharth Saminathan (CTO, Emote)  
**Date:** May 12, 2026  
**Status:** Living document — update as the system evolves

---

## Table of Contents

1. [What Career-Ops Actually Is](#1-what-career-ops-actually-is)
2. [Architecture Deep Dive — How It Works](#2-architecture-deep-dive--how-it-works)
3. [The Scanner — 3 Methods Explained](#3-the-scanner--3-methods-explained)
4. [The Evaluation Engine — A-F Scoring Framework](#4-the-evaluation-engine--a-f-scoring-framework)
5. [CV Generation & Personalization](#5-cv-generation--personalization)
6. [Interview Prep & Story Bank](#6-interview-prep--story-bank)
7. [Pipeline Integrity & Tracker System](#7-pipeline-integrity--tracker-system)
8. [Current India Configuration — What's Working & What's Broken](#8-current-india-configuration--whats-working--whats-broken)
9. [Scrapegraph-ai — Capabilities & Integration Plan](#9-scrapegraph-ai--capabilities--integration-plan)
10. [The Auto-Apply Problem — What's Possible & What's Dangerous](#10-the-auto-apply-problem--whats-possible--whats-dangerous)
11. [Gap Analysis — What Career-Ops Cannot Do Today](#11-gap-analysis--what-career-ops-cannot-do-today)
12. [Enhancement Roadmap — Phase 1 (This Week)](#12-enhancement-roadmap--phase-1-this-week)
13. [Enhancement Roadmap — Phase 2 (Month 1)](#13-enhancement-roadmap--phase-2-month-1)
14. [Enhancement Roadmap — Phase 3 (Month 2-3)](#14-enhancement-roadmap--phase-3-month-2-3)
15. [Decision Log & Open Questions](#15-decision-log--open-questions)

---

## 1. What Career-Ops Actually Is

### Origin

Career-Ops was built by Santiago Fernández (santifer.io) to evaluate 740+ job offers, generate 100+ tailored CVs, and land a Head of Applied AI role. It's an **AI-powered job search command center** that runs inside Claude Code, OpenCode, or Gemini CLI — it's NOT a standalone app. It's a set of markdown files, scripts, and slash commands that turn an AI coding agent into a personalized job search assistant.

### Core Philosophy

> "Companies use AI to filter candidates. I just gave candidates AI to choose companies."

The system is designed for **quality over quantity**. It strongly recommends against applying to anything scoring below 4.0/5. A well-targeted application to 5 companies beats a generic blast to 50.

### What It Replaces

| Manual Process | Career-Ops Equivalent |
|---|---|
| Checking 10 job boards daily | `/career-ops scan` — one command, 55+ companies |
| Reading JDs and comparing to your resume | A-F evaluation — automated match scoring |
| Rewriting your CV for each application | `/career-ops pdf` — tailored ATS-optimized CV per job |
| Tracking applications in a spreadsheet | `data/applications.md` with integrity checks |
| Googling "salary for X role at Y company" | Block D — comp research with WebSearch |
| Preparing interview stories from scratch | Story Bank — accumulates STAR+R across evaluations |
| Following up manually | Follow-up cadence calculator |

### Stack

| Component | Technology |
|---|---|
| AI Agent | Claude Code / OpenCode / Gemini CLI |
| Scraper (API mode) | Node.js (.mjs), native fetch, zero-token |
| Scraper (browser mode) | Playwright (Chromium) |
| Scraper (search mode) | Claude WebSearch tool |
| Configuration | YAML (portals.yml, profile.yml) |
| Data storage | Markdown files (pipeline.md, applications.md) |
| CV templates | HTML + CSS, rendered to PDF via Playwright |
| Evaluation framework | Markdown modes (oferta.md, _shared.md, etc.) |
| PDF generation | Playwright HTML → PDF |
| LaTeX CV | pdflatex (optional) |

---

## 2. Architecture Deep Dive — How It Works

### Directory Structure (Your Instance)

```
/Users/siddharthsaminathan/projects/career-ops/
├── CLAUDE.md                  # Loaded by Claude Code on startup
├── cv.md                      # YOUR canonical CV (markdown)
├── config/
│   └── profile.yml            # YOUR details, target roles, comp, narrative
├── portals.yml                # 55+ companies + search queries (India-optimized)
├── modes/                     # Evaluation templates (A-F scoring logic)
│   ├── _shared.md             # System rules, scoring weights, archetypes
│   ├── _profile.md            # YOUR custom archetypes/narrative (never overwritten)
│   ├── oferta.md              # Single offer evaluation (A-G blocks)
│   ├── ofertas.md             # Multi-offer comparison
│   ├── pipeline.md            # Process pending URLs
│   ├── scan.md                # Scanner instructions
│   ├── pdf.md                 # CV generation instructions
│   ├── batch.md               # Batch processing with sub-agents
│   ├── contacto.md            # LinkedIn outreach
│   ├── deep.md                # Company deep research
│   ├── interview-prep.md      # Interview preparation
│   ├── apply.md               # Live application assistant
│   ├── training.md            # Course/cert evaluation
│   ├── project.md             # Portfolio project evaluation
│   ├── tracker.md             # Application status overview
│   ├── patterns.md            # Rejection pattern analysis
│   └── followup.md            # Follow-up cadence
├── data/
│   ├── pipeline.md            # Inbox of unevaluated job URLs
│   ├── applications.md        # Master tracker (all applications)
│   ├── scan-history.tsv       # Dedup history (URLs already seen)
│   └── follow-ups.md          # Follow-up tracker
├── reports/                   # Evaluation reports (001-slug-YYYY-MM-DD.md)
├── output/                    # Generated PDFs
├── interview-prep/
│   └── story-bank.md          # Accumulated STAR+R stories
├── batch/
│   └── tracker-additions/     # TSV files for merge-tracker
├── templates/
│   ├── cv-template.html       # HTML CV template
│   ├── cv-template.tex        # LaTeX CV template
│   └── portals.example.yml    # Reference portals config
├── scan.mjs                   # Zero-token API scanner (standalone)
├── check-liveness.mjs         # Playwright job liveness checker
├── generate-pdf.mjs           # HTML → PDF CV generator
├── generate-latex.mjs         # LaTeX CV compiler
├── verify-pipeline.mjs        # Pipeline health checks (63+ rules)
├── merge-tracker.mjs          # Batch → master tracker merge
├── dedup-tracker.mjs          # Duplicate detection
├── normalize-statuses.mjs     # Canonical status enforcement
├── analyze-patterns.mjs       # Rejection pattern analysis
├── followup-cadence.mjs       # Follow-up timing calculator
└── update-system.mjs          # Self-update checker
```

### Data Flow — End to End

```
┌─────────────────────────────────────────────────────────────────┐
│                        JOB DISCOVERY                            │
│                                                                 │
│  /career-ops scan                                               │
│  ├── node scan.mjs (API mode)                                   │
│  │   └── portals.yml → detect API → fetch JSON → title filter   │
│  ├── WebSearch queries (Claude mode)                            │
│  │   └── LinkedIn India, Naukri, Cutshort, Instahyre searches   │
│  └── Playwright browser (career pages without APIs)             │
│                                                                 │
│  Output → data/pipeline.md (checkbox list of URLs)              │
│         → data/scan-history.tsv (dedup record)                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                      JOB EVALUATION                             │
│                                                                 │
│  /career-ops pipeline (or paste single URL)                     │
│  ├── Reads cv.md + config/profile.yml + modes/_profile.md       │
│  ├── Verifies job liveness (Playwright)                         │
│  ├── Classifies into archetype (AI Platform, Agentic, FDE, SA)  │
│  ├── Runs A-F evaluation against YOUR resume                    │
│  │   A: Role Summary (archetype, domain, seniority, TL;DR)      │
│  │   B: CV Match (requirement → CV line mapping, gaps)          │
│  │   C: Level Strategy (downlevel plan, senior sell)            │
│  │   D: Comp Research (WebSearch: Glassdoor, Levels.fyi)        │
│  │   E: Personalization Plan (CV + LinkedIn changes)            │
│  │   F: Interview Prep (STAR+R stories, story bank)             │
│  │   G: Legitimacy Check (ghost posting detection)              │
│  └── Generates report → reports/###-company-YYYY-MM-DD.md       │
│                                                                 │
│  Score interpretation:                                          │
│    4.5+ → Strong match, apply immediately                       │
│    4.0-4.4 → Good match, worth applying                         │
│    3.5-3.9 → Decent, apply only if specific reason              │
│    <3.5 → Recommend against applying                            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                     APPLICATION PREP                             │
│                                                                 │
│  /career-ops pdf → Generates tailored ATS-optimized CV          │
│  /career-ops latex → Exports as LaTeX for Overleaf              │
│  /career-ops contacto → LinkedIn outreach (find contacts)       │
│  /career-ops apply → Live application form assistant            │
│  /career-ops interview-prep → Company-specific intel            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                      TRACKING & LEARNING                         │
│                                                                 │
│  data/applications.md — Master tracker with statuses            │
│  /career-ops tracker — Visual pipeline overview                 │
│  /career-ops compare — Rank multiple offers                     │
│  /career-ops patterns — Analyze rejection patterns              │
│  /career-ops followup — Cadence calculator                      │
│                                                                 │
│  Integrity scripts:                                             │
│    verify-pipeline.mjs    — 63+ health checks                   │
│    merge-tracker.mjs      — Batch → master merge                │
│    dedup-tracker.mjs      — Remove duplicates                   │
│    normalize-statuses.mjs — Enforce canonical states            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. The Scanner — 3 Methods Explained

### Method 1: Direct API (`node scan.mjs`)

**How it works:**
1. Reads `portals.yml` → `tracked_companies` section
2. For each company, detects the ATS from `careers_url` pattern:
   - `jobs.ashbyhq.com/{slug}` → `api.ashbyhq.com/posting-api/job-board/{slug}`
   - `job-boards.greenhouse.io/{slug}` → `boards-api.greenhouse.io/v1/boards/{slug}/jobs`
   - `jobs.lever.co/{slug}` → `api.lever.co/v0/postings/{slug}`
3. Fetches JSON (10 concurrent, 10s timeout)
4. Applies title filter from `portals.yml` (positive/negative keywords)
5. Deduplicates against `scan-history.tsv` + `pipeline.md` + `applications.md`
6. Writes new URLs to `pipeline.md`

**Cost:** Zero LLM tokens. Pure HTTP + JSON parsing.

**Speed:** 55 companies in ~8-12 seconds.

**Limitation:** ONLY works for Greenhouse, Ashby, and Lever. No other ATS platforms supported.

### Method 2: WebSearch (Claude Code required)

**How it works:**
1. The `search_queries` section in `portals.yml` has Google search queries
2. Claude Code's WebSearch tool executes them
3. Results are parsed for job titles + URLs
4. New URLs are added to `pipeline.md`

**Cost:** WebSearch tool calls (included in Claude Code).

**Limitation:** Results can be stale. Search engines index job pages with delays. Some job boards block search indexing.

**Current India queries configured:**
```yaml
- LinkedIn India — AI/LLM Engineer
- LinkedIn India — Agentic AI
- LinkedIn India — Platform/Backend AI
- LinkedIn India — Founding/Product Engineer
- LinkedIn India — Senior AI roles
- Naukri — AI Engineer
- Naukri — Python AI Backend
- Cutshort — AI/ML roles
- Instahyre — AI roles
- Wellfound — AI Engineer India
- RemoteOK, Himalayas, YC Jobs (global remote)
- Cross-ATS: Greenhouse/Lever/Ashby India jobs
```

### Method 3: Playwright Browser (Claude Code required)

**How it works:**
1. Companies in `portals.yml` with `scan_method: playwright` or `scan_method: websearch`
2. Claude Code opens the career page in Playwright
3. Reads the rendered page for job listings
4. Extracts titles, URLs, locations

**Cost:** Claude Code browser tool calls.

**Limitation:** Slower (browser rendering). Each page takes 2-5 seconds. Works on any website including SPAs (React, Angular).

### Which Method Runs When

| Command | What runs |
|---|---|
| `node scan.mjs` | Method 1 only (API) |
| `/career-ops scan` (inside Claude) | Methods 1 + 2 + 3 |
| `node scan.mjs --company Stripe` | Method 1, single company |
| `node scan.mjs --dry-run` | Method 1, preview only, no writes |

### Why 37 Indian Companies Return 404

The scanner auto-detects the API from URL patterns. If a company changes its ATS provider or URL structure, detection fails. Examples:

| Company | URL in portals.yml | Status | Likely Issue |
|---------|-------------------|--------|-------------|
| Razorpay | `jobs.lever.co/razorpay` | 404 | Moved off Lever |
| Flipkart | `boards.greenhouse.io/flipkart` | 404 | URL changed or Greenhouse board renamed |
| Swiggy | `jobs.lever.co/swiggy` | 404 | Moved off Lever |
| Freshworks | `boards.greenhouse.io/freshworks` | 404 | URL changed |

These URLs were educated guesses when I built the India portals.yml. They need verification — some companies may have moved to different ATS platforms or changed their board slugs. Each URL needs to be opened in a browser to find the correct current careers page.

---

## 4. The Evaluation Engine — A-F Scoring Framework

### How It Works

When you paste a job URL or run `/career-ops pipeline`, the system:

1. **Fetches the JD** — via WebFetch or Playwright
2. **Reads your CV** — from `cv.md` (canonical source)
3. **Reads your profile** — from `config/profile.yml` (target roles, comp, narrative)
4. **Reads your custom archetypes** — from `modes/_profile.md`
5. **Classifies the role** — into archetype (see below)
6. **Runs A-G evaluation** — generates a numbered report in `reports/`

### The 6 Archetypes

| Archetype | Key JD Signals | Siddharth's Fit |
|---|---|---|
| **AI Platform / LLMOps** | "observability", "evals", "pipelines", "monitoring" | Secondary — your infra/obs experience |
| **Agentic / Automation** | "agent", "HITL", "orchestration", "multi-agent" | PRIMARY — Emote + Omnex exactly this |
| **Forward Deployed** | "customer", "deployment", "solutions", "integration" | Adjacent — founder experience |
| **Solutions Architect** | "architecture", "pre-sales", "enterprise", "technical advisor" | Adjacent — Anthropic Applied AI Architect |
| **Product Manager (AI)** | "product", "roadmap", "discovery", "stakeholder" | Secondary — Emote product ownership |
| **Transformation / RevOps** | "change management", "adoption", "automation", "GTM" | Adjacent — Omnex enterprise digitalization |

### The A-G Blocks

**Block A — Role Summary:** Archetype detection, domain, seniority, remote policy, TL;DR in 1 sentence.

**Block B — CV Match:** Every JD requirement mapped to specific lines in your CV. Gaps identified with mitigation strategy for each:
1. Is it a hard blocker or nice-to-have?
2. Can you demonstrate adjacent experience?
3. Is there a portfolio project that covers it?
4. Concrete mitigation plan (cover letter phrase, quick project, etc.)

**Block C — Level Strategy:**
- Level detected in JD vs your natural level
- Plan to "sell senior without lying" — specific phrases, achievements to highlight
- Plan if downleveled — accept if comp is fair, negotiate 6-month review, clear promo criteria

**Block D — Comp Research:** WebSearch for current salaries (Glassdoor, Levels.fyi, Blind). Table with data and sources. Market demand trend.

**Block E — Personalization Plan:** Top 5 CV changes + Top 5 LinkedIn changes to maximize match. Table format: current state → proposed change → why.

**Block F — Interview Prep:** 6-10 STAR+R stories mapped to JD requirements. STAR = Situation, Task, Action, Result. +R = Reflection (what you learned). Stories accumulate in `interview-prep/story-bank.md`.

**Block G — Legitimacy Check (Posting is Real?):**

| Tier | Meaning |
|---|---|
| **High Confidence** | Real, active opening |
| **Proceed with Caution** | Mixed signals |
| **Suspicious** | Multiple ghost indicators |

Signals checked:
- Posting age (under 30d = good, 60d+ = concerning)
- Apply button active on page
- Tech specificity in JD (generic = suspicious)
- Requirements realism
- Recent layoff news
- Reposting patterns (same role 2+ times in 90 days)
- Role-company fit

---

## 5. CV Generation & Personalization

### How It Works

`/career-ops pdf` generates an ATS-optimized CV tailored to a specific job:

1. Reads your canonical CV from `cv.md`
2. Reads the job evaluation report (A-F blocks)
3. Reads the personalization plan (Block E)
4. Applies the 5 recommended changes
5. Generates HTML using `templates/cv-template.html`
6. Renders to PDF via Playwright (Chromium headless)

### Design

The default template uses Space Grotesk + DM Sans fonts, ATS-optimized layout (single column, no tables, no images, standard section headings). Customizable via `templates/cv-template.html`.

### LaTeX Option

`/career-ops latex` exports as `.tex` for Overleaf. Better typography for academic/research roles.

### Key Rule

**The system NEVER submits without you reviewing.** It generates the PDF, drafts the cover letter, fills the form — but STOPS before clicking Submit. You always have the final call.

---

## 6. Interview Prep & Story Bank

### How It Works

Every evaluation generates STAR+R stories (Block F). These accumulate in `interview-prep/story-bank.md`. Over time, you build 5-10 master stories that can be adapted to any behavioral question.

### Story Bank Structure

Each story has:
- **Situation** — context, company, role
- **Task** — what needed to be done
- **Action** — what YOU specifically did
- **Result** — measurable outcome
- **Reflection** — what you learned, what you'd do differently

The **Reflection** column is what signals seniority — junior candidates describe what happened, senior candidates extract lessons.

### Company-Specific Intel

`/career-ops interview-prep` generates `interview-prep/{company}-{role}.md` with:
- Company mission, recent news, product launches
- Interview process (from Glassdoor/Blind/Reddit)
- Key people (hiring manager, team lead if findable)
- Technical stack
- Culture signals
- Questions to ask them

---

## 7. Pipeline Integrity & Tracker System

### Master Tracker

`data/applications.md` — a markdown table with all applications:

```
| # | Date | Company | Role | Score | Status | PDF | Report | Notes |
|---|------|---------|------|-------|--------|-----|--------|-------|
| 1 | 2026-05-12 | Anthropic | Applied AI Engineer | 4.6/5 | Evaluated | ❌ | [1](reports/001-anthropic-2026-05-12.md) | Bangalore |
```

### Canonical States

| State | Meaning |
|---|---|
| `Evaluated` | Report completed, pending decision |
| `Applied` | Application sent |
| `Responded` | Company responded |
| `Interview` | In interview process |
| `Offer` | Offer received |
| `Rejected` | Rejected by company |
| `Discarded` | Discarded by you, or offer closed |
| `SKIP` | Doesn't fit, don't apply |

### Integrity Scripts

| Script | What it does |
|---|---|
| `verify-pipeline.mjs` | 63+ health checks — missing reports, invalid statuses, broken links |
| `merge-tracker.mjs` | Merges batch evaluation results into master tracker (handles column swaps) |
| `dedup-tracker.mjs` | Detects duplicate company+role entries |
| `normalize-statuses.mjs` | Enforces canonical status names |

### TSV Convention

After batch evaluations, results are written as TSV files in `batch/tracker-additions/`:
```
001\t2026-05-12\tAnthropic\tApplied AI Engineer\tEvaluated\t4.6/5\t❌\t[1](reports/001-anthropic-2026-05-12.md)\tBangalore
```

`merge-tracker.mjs` handles the merge into the master table. Never manually add rows to applications.md — always use the merge script.

---

## 8. Current India Configuration — What's Working & What's Broken

### Working Companies (API hits succeed)

| # | Company | ATS | India Roles Found (Latest Scan) |
|---|---|---|---|
| 1 | Anthropic | Greenhouse | Applied AI Engineer (Bangalore), Applied AI Architect (Mumbai) |
| 2 | Stripe | Greenhouse | Software Engineer Data & AI, Staff Engineer (Bengaluru) |
| 3 | GitLab | Greenhouse | AI Engineer, Staff Backend, Senior Backend (Remote India) |
| 4 | Twilio | Greenhouse | Staff ML Engineer, Senior Engineer Security (Remote India) |
| 5 | Cloudflare | Greenhouse | Senior Strategic Solutions Engineer (Bengaluru, Delhi NCR) |
| 6 | MongoDB | Greenhouse | Staff Engineer, Senior Staff Engineer (Gurugram) |
| 7 | Zapier | Ashby | Software Engineer (India) |
| 8 | Meesho | Lever | Engineering Manager (Bangalore) |
| 9 | CRED | Lever | ML Engineer (Hyderabad) |
| 10 | Datadog | Greenhouse | Global roles (Paris, NY, Madrid — no India yet) |
| 11 | Vercel | Greenhouse | Global remote roles |
| 12 | n8n | Ashby | Remote Europe roles |
| 13 | LangChain | Ashby | US/EU deployed engineer roles |
| 14 | Supabase | Ashby | Remote global roles |
| 15 | Clay Labs | Ashby | NYC-based roles |
| 16 | Anthropic | Greenhouse | Multiple Applied AI roles globally |
| 17 | Resend | Ashby | Americas remote |
| 18 | Atlassian | Lever | Global roles (need to verify India) |

### Broken Companies (404 — need URL fixes)

| Company | Current URL | Likely Fix Needed |
|---|---|---|
| Razorpay | `jobs.lever.co/razorpay` | May have moved to Greenhouse or custom careers page |
| Flipkart | `boards.greenhouse.io/flipkart` | Board slug may have changed |
| Swiggy | `jobs.lever.co/swiggy` | May have moved to custom ATS |
| PhonePe | `jobs.lever.co/phonepe` | Verify correct Lever slug |
| Zomato | `jobs.lever.co/zomato` | Verify correct Lever slug |
| Groww | `jobs.lever.co/groww` | Verify correct Lever slug |
| Zepto | `jobs.lever.co/zepto` | Verify correct Lever slug |
| Meesho | `jobs.lever.co/meesho` | API works but only 3 roles found |
| Nykaa | `jobs.lever.co/nykaa` | Verify correct Lever slug |
| Freshworks | `boards.greenhouse.io/freshworks` | Board slug may have changed |
| Myntra | `boards.greenhouse.io/myntra` | Board slug may have changed |
| Postman | `jobs.lever.co/postman` | May have moved ATS |
| BrowserStack | `jobs.lever.co/browserstack` | Verify correct Lever slug |
| Chargebee | `jobs.lever.co/chargebee` | Verify correct Lever slug |
| Hasura | `jobs.lever.co/hasura` | Verify correct Lever slug |
| CleverTap | `jobs.lever.co/clevertap` | Verify correct Lever slug |
| CRED | `jobs.lever.co/cred` | API works (found ML Engineer role) |
| Ola | `jobs.lever.co/ola` | Verify correct Lever slug |
| Ola Electric | `jobs.lever.co/olaelectric` | Verify correct Lever slug |
| Ather Energy | `jobs.lever.co/atherenergy` | Verify correct Lever slug |
| Unacademy | `jobs.lever.co/unacademy` | Verify correct Lever slug |
| Vedantu | `jobs.lever.co/vedantu` | Verify correct Lever slug |
| Practo | `jobs.lever.co/practo` | Verify correct Lever slug |
| Cult.fit | `jobs.lever.co/curefit` | Verify correct Lever slug |
| Fractal Analytics | `jobs.lever.co/fractal` | Verify correct Lever slug |
| Mad Street Den | `jobs.lever.co/madstreetden` | Verify correct Lever slug |
| Uber | `boards.greenhouse.io/uber` | Board slug may have changed |
| Shopify | `boards.greenhouse.io/shopify` | Board slug may have changed |
| Coinbase | `boards.greenhouse.io/coinbase` | Board slug may have changed |
| Elastic | `jobs.lever.co/elastic` | Verify correct Lever slug |
| Red Hat | `boards.greenhouse.io/redhat` | Board slug may have changed |
| Snowflake | `boards.greenhouse.io/snowflake` | Board slug may have changed |
| ThoughtWorks | `jobs.lever.co/thoughtworks` | Verify correct Lever slug |
| Sprinklr | `boards.greenhouse.io/sprinklr` | Board slug may have changed |
| Kovai.co | `jobs.lever.co/kovai` | Verify correct Lever slug |
| CoinDCX | `jobs.lever.co/coindcx` | Verify correct Lever slug |
| slice | `jobs.lever.co/slice` | Verify correct Lever slug |

### Total India Job Pipeline (May 12 scan)

- 55 companies scanned via API
- 2,704 total jobs found
- 1,986 filtered out (title mismatch — not AI/engineering)
- 641 duplicates skipped (already in pipeline/history)
- 77 new jobs added
- ~7 India-specific roles in today's batch

---

## 9. Scrapegraph-ai — Capabilities & Integration Plan

### What It Is

Scrapegraph-ai is a Python library (v2.1.1, MIT) that uses LLMs to extract structured data from any website. Instead of writing CSS selectors or XPaths, you describe what you want in natural language.

### Key Features

| Feature | Description |
|---|---|
| **SmartScraperGraph** | Single-page scraper — give URL + prompt, get structured JSON |
| **SearchGraph** | Searches the web + scrapes results |
| **Multi-page scraping** | Follows pagination, scrapes lists |
| **LLM-agnostic** | Works with OpenAI, DeepSeek, Ollama, Anthropic, Mistral |
| **Playwright integration** | Renders JavaScript-heavy pages |
| **Markdown/XML/JSON input** | Also scrapes local files |
| **Proxy support** | Rotating proxies to avoid rate limiting |

### How It Compares to Career-Ops Scanner

| Dimension | Career-Ops scan.mjs | Scrapegraph-ai |
|---|---|---|
| **Method** | Direct JSON API calls | LLM parses rendered HTML |
| **Cost per company** | $0 (zero tokens) | ~$0.01-0.05 (LLM API call) |
| **Speed per company** | ~0.2 seconds | ~3-10 seconds |
| **Coverage** | Only Greenhouse/Ashby/Lever | ANY website |
| **Data quality** | 100% structured, no errors | LLM can miss fields, hallucinate |
| **Setup** | YAML config | Python code |
| **Rate limiting** | No issue (official APIs) | Need proxy rotation for some sites |
| **Reliability** | Deterministic | Probabilistic (LLM-dependent) |

### Proposed Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNIFIED SCANNER (Phase 2)                     │
│                                                                 │
│  portals.yml                                                     │
│  ├── tracked_companies (with API) → node scan.mjs (free)        │
│  ├── tracked_companies (no API)   → scrapegraph-ai (LLM)        │
│  └── search_queries               → WebSearch + scrapegraph-ai  │
│                                                                 │
│  New: companies without Greenhouse/Ashby/Lever                   │
│  ├── LinkedIn India job search results                          │
│  ├── Naukri.com search results                                  │
│  ├── Cutshort.io profiles                                       │
│  ├── Instahyre listings                                         │
│  ├── Company career pages (custom ATS)                          │
│  └── Wellfound / AngelList India                                │
└─────────────────────────────────────────────────────────────────┘
```

### Scrapegraph-ai Config for DeepSeek (Your API Key)

```python
from scrapegraphai.graphs import SmartScraperGraph

graph_config = {
    "llm": {
        "api_key": "sk-0c977935506f4da58884fc25a8a539af",
        "model": "deepseek/deepseek-chat",  # OpenAI-compatible
        "base_url": "https://api.deepseek.com/v1",
        "model_tokens": 8192,
        "format": "json",
    },
    "verbose": True,
    "headless": True,
}

# Example: Scrape LinkedIn India job search results
smart_scraper = SmartScraperGraph(
    prompt="""
    Extract all job listings from this page. For each job, return:
    - title: the job title
    - company: the company name
    - location: the job location
    - url: the job detail URL
    - posted_date: when it was posted (if visible)
    """,
    source="https://www.linkedin.com/jobs/search/?keywords=AI%20Engineer&location=India",
    config=graph_config
)

result = smart_scraper.run()
# Returns structured JSON with all job listings
```

### What Scrapegraph-ai UNLOCKS for Career-Ops

| New Capability | How |
|---|---|
| **LinkedIn India scraping** | Scrape search results pages, extract job listings |
| **Naukri.com scraping** | Parse Naukri job listings into structured data |
| **Company career pages** | Any company with a custom careers page (not Greenhouse/Lever) |
| **Cutshort, Instahyre, Wellfound** | All the Indian job platforms without APIs |
| **Job description extraction** | Given any job URL, extract clean JD text |
| **Application form detection** | Identify form fields for auto-fill (Phase 3) |
| **Ghost posting detection** | Check if job still appears on company site vs aggregator |

### Cost Estimate for Full India Scan

If we add 30 Indian companies via scrapegraph-ai:
- 30 companies × $0.02 avg LLM cost = ~$0.60 per daily scan
- Monthly: ~$18 in DeepSeek API costs
- Compare to: $0 for the current API-only scanner

---

## 10. The Auto-Apply Problem — What's Possible & What's Dangerous

### What "Auto-Apply" Actually Means

There's a spectrum:

```
Level 1: Auto-fill forms
  └── Fill name, email, phone, LinkedIn, portfolio URL
      └── LOW RISK — same data every time, no LLM needed

Level 2: Auto-tailor CV + cover letter
  └── Generate tailored PDF per job, draft cover letter
      └── MEDIUM RISK — requires human review before sending

Level 3: Auto-submit application
  └── Fill form + attach PDF + click Submit
      └── HIGH RISK — can't take back a submitted application

Level 4: Auto-apply to all matching jobs
  └── Scan → Evaluate → Generate → Submit with no human in loop
      └── DANGEROUS — violates Career-Ops ethical principles
```

### Career-Ops Current Stance

From `CLAUDE.md`:

> **NEVER submit an application without the user reviewing it first.** Fill forms, draft answers, generate PDFs — but always STOP before clicking Submit/Send/Apply. The user makes the final call.

> **Strongly discourage low-fit applications.** If a score is below 4.0/5, explicitly recommend against applying.

> **Quality over speed.** A well-targeted application to 5 companies beats a generic blast to 50.

### What We CAN Automate (Safe)

| Automation | How | Risk |
|---|---|---|
| **Auto-fill personal info** | Playwright fills name/email/phone/location fields | None |
| **Auto-attach CV PDF** | Upload tailored PDF generated by `/career-ops pdf` | None |
| **Auto-draft cover letter** | LLM generates from Block E personalization plan | Low (human reviews) |
| **Auto-answer "standard" questions** | Pre-written answers for "Are you authorized to work in X?" etc. | Low |
| **Auto-detect form fields** | Scrapegraph-ai or Playwright identifies form structure | None |
| **One-click submit** | After human review, single click to submit | Low (deliberate action) |

### What We SHOULD NOT Automate

| Automation | Why Not |
|---|---|
| **Auto-submit without review** | Can't unsend. Bad application is worse than no application. |
| **Auto-apply to low-score jobs** | Wastes recruiter's time, damages your reputation |
| **Auto-apply to mass-recruiters** | TCS/Infosys/Wipro — you explicitly blocked these |
| **Auto-answer behavioral questions** | "Tell me about a time when..." — needs your real stories |
| **Auto-negotiate salary** | Needs your judgment, priorities, competing offers |

### Proposed "Guided Apply" Flow (Level 2.5)

```
1. You run /career-ops scan → 77 new jobs found
2. You run /career-ops pipeline → 7 India jobs evaluated
3. You pick 3 jobs scored 4.0+ and say "prepare these"
4. System generates:
   ├── Tailored CV PDF (per job)
   ├── Cover letter draft
   ├── Pre-filled application form (name, email, links)
   └── Answers to standard questions
5. You review each one → make edits → say "apply"
6. System submits via Playwright ONE AT A TIME
7. Status updated to "Applied" in tracker
```

This gives you speed (no retyping same info 50 times) without sacrificing judgment (you review every application).

---

## 11. Gap Analysis — What Career-Ops Cannot Do Today

### Critical Gaps

| # | Gap | Impact | Proposed Solution |
|---|---|---|---|
| 1 | **37 Indian company URLs broken** | Losing 67% of Indian startup coverage | Manually verify each URL, update portals.yml |
| 2 | **No LinkedIn India direct scraping** | Missing the #1 job board in India | Scrapegraph-ai integration |
| 3 | **No Naukri/Cutshort/Instahyre support** | Missing India-specific platforms | Scrapegraph-ai or dedicated scrapers |
| 4 | **No non-ATS company scanning** | Any company without Greenhouse/Ashby/Lever is invisible | Scrapegraph-ai + Playwright fallback |
| 5 | **WebSearch queries not running** | LinkedIn/Naukri queries only run inside Claude, never tested | Run full `/career-ops scan` inside Claude |
| 6 | **No auto-apply capability** | Manual submission for every application | Playwright-based guided apply (Level 2.5) |
| 7 | **Profile not customized for girlfriend** | Her instance has US/EU defaults | Need her resume + preferences |
| 8 | **No email/push notifications for new jobs** | Must manually check | Cron + Resend integration |
| 9 | **Scan history grows unbounded** | Dedup gets slower over time | Periodic history cleanup |
| 10 | **No comp data for Indian market** | Block D uses Glassdoor/Levels.fyi (US-focused) | Add Indian salary sources (AmbitionBox, Glassdoor India) |

### Nice-to-Have Gaps

| # | Gap | Impact |
|---|---|---|
| 11 | No LinkedIn profile optimization | Missing out on recruiter inbound |
| 12 | No networking automation | LinkedIn outreach is manual |
| 13 | No application analytics | Can't see which CV versions convert best |
| 14 | No interview feedback loop | Can't learn from rejections automatically |
| 15 | No multi-language support for India | Hindi/Tamil job listings missed |

---

## 12. Enhancement Roadmap — Phase 1 (This Week)

### Goal: Fix the broken pipeline + run full India scan

#### Task 1.1: Fix broken Indian company URLs (2 hours)

For each of the 37 broken companies:
1. Open the company's actual careers page in a browser
2. Identify their current ATS (Greenhouse, Lever, Ashby, Workday, or custom)
3. If Greenhouse/Lever/Ashby → update the URL in portals.yml
4. If custom ATS → mark as `scan_method: websearch` with a search query
5. If they don't hire in India → disable with `enabled: false`

```bash
# To verify a URL: open in browser, check if it redirects
# For Greenhouse: check if /api endpoint works
curl -s "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs" | jq '.jobs | length'

# For Lever: check the JSON endpoint
curl -s "https://api.lever.co/v0/postings/{slug}" | jq 'length'

# For Ashby: check the API
curl -s "https://api.ashbyhq.com/posting-api/job-board/{slug}" | jq '.jobs | length'
```

#### Task 1.2: Run full `/career-ops scan` inside Claude (30 min)

This will execute ALL three methods (API + WebSearch + Playwright), including the LinkedIn India and Naukri queries I added:

```bash
cd /Users/siddharthsaminathan/projects/career-ops
claude
# Then type: /career-ops scan
```

#### Task 1.3: Install and test Scrapegraph-ai (1 hour)

```bash
cd /Users/siddharthsaminathan/projects/career-ops
source .venv/bin/activate  # or create a new venv
pip install scrapegraphai
playwright install  # if not already done
```

Test script:
```python
# test_scrapegraph.py
from scrapegraphai.graphs import SmartScraperGraph

config = {
    "llm": {
        "api_key": "sk-0c977935506f4da58884fc25a8a539af",
        "model": "deepseek/deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "format": "json",
    },
    "headless": True,
}

# Test: scrape a Lever job page (should work well)
scraper = SmartScraperGraph(
    prompt="Extract: job title, company name, location, requirements list, responsibilities list",
    source="https://jobs.lever.co/cred",  # CRED careers page
    config=config
)
result = scraper.run()
print(result)
```

#### Task 1.4: Create `scrape_india.py` — India-specific scraper (3 hours)

A Python script that uses Scrapegraph-ai to scrape:
- LinkedIn India job search results (for your target roles)
- Naukri.com search results
- Any company career page without an API

Output: TSV files compatible with career-ops pipeline format.

#### Task 1.5: Evaluate top 10 India jobs and generate CVs (1 hour)

After scan + scrape, pick the top 10 highest-scoring India jobs and:
- Run full A-F evaluation
- Generate tailored CV PDFs
- Add to application tracker

---

## 13. Enhancement Roadmap — Phase 2 (Month 1)

### Goal: Productionize the India pipeline + add guided apply

#### Task 2.1: Automated daily scan with notifications

- Cron job: `0 7 * * * cd /path/to/career-ops && node scan.mjs`
- Email digest via Resend: "X new India jobs today"
- Top 3 matches highlighted with scores

#### Task 2.2: Scrapegraph-ai integration into scan pipeline

- Add new section to `portals.yml`: `scraped_companies`
- `scrape-india.py` reads this section, scrapes via Scrapegraph-ai
- Output unified with API scanner results in `pipeline.md`

#### Task 2.3: LinkedIn India dedicated connector

- Research LinkedIn's public job search pages (no auth needed for basic search)
- Build Scrapegraph-ai prompt specifically for LinkedIn job cards
- Test with: "AI Engineer India", "LLM Engineer Bangalore", "Applied AI remote"
- Add 10 LinkedIn search queries to portals.yml

#### Task 2.4: Naukri + Cutshort connectors

- Same approach as LinkedIn — Scrapegraph-ai prompts for each platform
- Naukri: prioritize Bangalore, Chennai, Remote
- Cutshort: prioritize AI/ML, Python, FastAPI roles

#### Task 2.5: Guided Apply prototype (Level 2)

- New mode: `apply.md` (already exists, needs India customization)
- Playwright script that:
  1. Opens the job application URL
  2. Fills known fields (name, email, phone, location, LinkedIn, GitHub, portfolio)
  3. Uploads the tailored CV PDF
  4. Pastes cover letter (if text field exists)
  5. STOPS before submit — shows you the filled form for review
- Triggered by: `/career-ops apply {job-number}`

#### Task 2.6: Fix girlfriend's instance

- Get her resume → format into `cv.md`
- Get her target roles, comp range, location preferences
- Customize `portals.yml` for her profile (more established companies, finance if she wants to stay in that domain)
- Run initial scan for her

---

## 14. Enhancement Roadmap — Phase 3 (Month 2-3)

### Goal: Full automation + analytics

#### Task 3.1: One-Click Apply

After human review:
1. You click "approve" in the guided apply flow
2. System submits the application
3. Status auto-updated to "Applied" in tracker
4. Confirmation screenshot saved

#### Task 3.2: Application Analytics Dashboard

- Which CV versions are getting responses?
- Which job sources yield the best matches?
- Time-to-response tracking
- Conversion funnel: Scan → Evaluate → Apply → Interview → Offer

#### Task 3.3: Interview Feedback Loop

After each interview:
1. System asks: "How did it go? What questions did they ask?"
2. Your answers update the Story Bank with real interview data
3. Future interview preps get better because they learn from your actual interviews

#### Task 3.4: LinkedIn Profile Optimizer

- Scrapes your current LinkedIn profile
- Compares against target roles
- Suggests specific changes to headline, about section, experience bullets
- Generates optimized version you can copy-paste

#### Task 3.5: Networking Automation

- `/career-ops contacto` already finds contacts at target companies
- Phase 3 adds: automated connection requests, follow-up messages
- NOT spam — personalized messages based on company research (Block A)

#### Task 3.6: Multi-Language Support for India

- Add Hindi/Tamil job listing search queries
- Handle Indian company career pages that are in mixed English/local language

---

## 15. Decision Log & Open Questions

### Decisions Made

| # | Decision | Date | Rationale |
|---|---|---|---|
| 1 | Use Career-Ops as primary job search system | May 11 | 30K+ stars, AGPL, works with Claude Code, covers evaluation + CV + tracking |
| 2 | Self-host (not Postiz cloud) | May 11 | Free, full control, custom portals.yml |
| 3 | Optimize for India market | May 11 | Deep custom portals.yml, Indian companies, INR comp |
| 4 | Use DeepSeek API as LLM backend | May 11 | Already have key, OpenAI-compatible, cost-effective |
| 5 | Two separate instances (self + girlfriend) | May 11 | Different CVs, target roles, company preferences |
| 6 | Block mass-recruiters (TCS, Infosys, Wipro, etc.) | May 11 | These companies don't match your profile |
| 7 | Scrapegraph-ai as supplement, not replacement | May 12 | Best of both: free API scanner + LLM scraper for non-API sites |

### Open Questions

| # | Question | Status |
|---|---|---|
| 1 | What's your girlfriend's name, CV, and target roles? | Waiting on you |
| 2 | Should we add Workday ATS support? (Many Indian MNCs use Workday) | Needs research — Workday has no public API |
| 3 | Should we scan for remote global roles that hire in India timezone? | Some companies don't list "India" but are timezone-agnostic |
| 4 | Do you want to auto-apply or always review first? | See §10 — recommend Level 2.5 (fill + stop, you review) |
| 5 | Should we integrate with your existing Claude Code proxy or use Direct DeepSeek? | Career-ops uses Claude Code for evaluations, DeepSeek for scraping |
| 6 | Daily scan or weekly scan? | Daily recommended — jobs fill fast in India |
| 7 | Should the girlfriend's instance use the SAME DeepSeek API key? | Yes — same key, separate instance, separate portals.yml |

---

## Appendix A: Quick Reference — Commands

```bash
# Launch career-ops
cd /Users/siddharthsaminathan/projects/career-ops
claude

# Inside Claude:
/career-ops scan              # Full scan (API + WebSearch + Playwright)
/career-ops pipeline          # Evaluate all new jobs in pipeline
/career-ops pdf               # Generate tailored CV for a job
/career-ops compare           # Rank multiple offers
/career-ops tracker           # View application status
/career-ops batch             # Parallel evaluate 10+ jobs
/career-ops contacto          # LinkedIn outreach
/career-ops deep              # Company research
/career-ops interview-prep    # Interview preparation

# Outside Claude (terminal):
node scan.mjs                 # API-only scan (fast, free)
node scan.mjs --dry-run       # Preview without saving
node scan.mjs --company CRED  # Scan single company
npm run doctor                # Check setup health
node check-liveness.mjs <url> # Verify a job posting is still active
node verify-pipeline.mjs      # 63+ health checks on tracker
```

## Appendix B: Quick Reference — Files

| File | What to edit |
|---|---|
| `cv.md` | Your CV — update when you change jobs or add achievements |
| `config/profile.yml` | Your details, target salary, location preferences |
| `portals.yml` | Companies to scan, search queries, title filters |
| `modes/_profile.md` | Custom archetypes, narrative, negotiation preferences |
| `data/pipeline.md` | Auto-populated by scanner — don't edit manually |
| `data/applications.md` | Your application tracker — update status, don't add rows manually |

## Appendix C: Instance Locations

| Person | Path | Status |
|---|---|---|
| **Siddharth** | `/Users/siddharthsaminathan/projects/career-ops/` | Active, India-optimized |
| **Girlfriend** | `/Users/siddharthsaminathan/projects/career-ops-gf/` | Setup complete, waiting for resume |

---

*Document generated May 12, 2026 · Career-Ops v1.3.0 (update v1.7.0 available) · [Career-Ops GitHub](https://github.com/santifer/career-ops) · [Scrapegraph-ai GitHub](https://github.com/VinciGit00/Scrapegraph-ai)*
