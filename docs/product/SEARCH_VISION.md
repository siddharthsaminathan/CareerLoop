# CareerLoop Search System — Vision + End-to-End Implementation Plan

## CORE PRINCIPLE

CareerLoop is NOT:

* a job board
* an ATS scraper
* a resume generator

CareerLoop IS:
a closed-loop career transition operating system.

The system continuously:

1. understands the user
2. searches opportunities
3. applies
4. tracks outcomes
5. learns from feedback
6. converges toward employment

The search system is NOT static.

It is:
adaptive search optimization.

---

## POSITIONING CONTEXT

**The Default Assumption:** "CareerLoop is another job board."

**The Truth:** CareerLoop is a career operating system. A command center. Like having a recruiter + strategist + researcher working for you, 24/7.

**Our Core Optimization:** 
- Job boards optimize: application volume
- Resume tools optimize: keyword matching  
- **CareerLoop optimizes: employment probability**

Everyone else asks: "How many jobs can we show you?"

CareerLoop asks: "How do we get you hired?"

See detailed market analysis in: [COMPETITIVE_POSITIONING.md](COMPETITIVE_POSITIONING.md)

---

# THE 3 CORE SEARCH SYSTEMS

CareerLoop has 3 independent but interconnected search engines.

## SEARCH 1 — JOB SEARCH

Goal:
Find relevant opportunities.

Searches:

* ATS pages
* company career portals
* job boards
* hidden APIs
* structured job feeds

Outputs:

* jobs
* companies
* apply links
* resume tailoring targets

---

## SEARCH 2 — RECRUITER SEARCH

Goal:
Find recruiters related to:

* company
* role
* geography

Searches:

* LinkedIn
* company directories
* recruiter pages
* employee search
* recruiter emails

Outputs:

* recruiter LinkedIn
* recruiter email
* recruiter role
* hiring ownership

---

## SEARCH 3 — REFERRAL SEARCH

Goal:
Find employees likely to provide referrals.

Searches:

* LinkedIn employees
* alumni
* same-function employees
* same-location employees

Outputs:

* employee profiles
* warm referral paths
* likely referral candidates

---

# THE SYSTEM IS A FEEDBACK LOOP

The system continuously learns:

## INPUTS

* resume
* job preferences
* company preferences
* applications
* recruiter replies
* interview progression
* rejection patterns

## OUTPUTS

* improved positioning
* improved search ranking
* improved targeting
* improved resume versions
* improved outreach

This is NOT search.

This is:
career convergence.

---

# USER FLOW

## STEP 1 — USER ONBOARDING

User provides:

* resume OR raw experience dump
* preferred roles
* preferred locations
* expected compensation
* work style
* companies they admire
* industries
* timeline urgency

Example:

```json id="y6jtnx"
{
  "roles": ["AI Product Manager"],
  "locations": ["Bangalore", "Remote"],
  "companies_like": ["Razorpay", "CRED", "Meesho"],
  "salary_range": "20-30L",
  "experience": "Consulting + AI"
}
```

---

# STEP 2 — RESUME NORMALIZATION

Current system already partially exists.

Use existing:

* Resume Council
* Humanizer
* Validation
* Template rendering

Refactor into:

```text id="6xpf0x"
Raw Resume
    ↓
NormalizedResume
    ↓
Role Inference
    ↓
Positioning Engine
```

Outputs:

* inferred roles
* inferred seniority
* inferred industries
* inferred transferable skills

---

# STEP 3 — CAREER INTENT VECTOR

This becomes the user's search profile.

```json id="rjlwmc"
{
  "functions": ["product", "ai", "strategy"],
  "industries": ["fintech", "saas"],
  "locations": ["bangalore"],
  "companies_like": ["Razorpay"],
  "seniority": "mid",
  "salary_band": "20-30L"
}
```

This vector drives ALL searches.

---

# SEARCH SYSTEM 1 — JOB SEARCH ENGINE

# GOAL

Find:

* jobs
* companies
* opportunities

NOT just scrape ATS.

---

# EXISTING COMPONENTS

## Already Present

* ATS adapters
* Playwright
* Resume pipeline
* Scoring logic
* Dedup logic
* Role filtering (partial)
* Tailoring pipeline

## Needs Refactor

* ATS-first assumption
* hardcoded company URLs
* static seeding
* HTML-only scraping
* synchronous crawling

---

# NEW ARCHITECTURE

## PHASE A — EMPLOYER DISCOVERY

Input:
Career Intent Vector

Example:

```text id="0e0q9t"
AI Product Manager Bangalore
```

System searches:

* Google Maps
* LinkedIn companies
* Wellfound
* Crunchbase
* G2
* YC
* startup lists
* Naukri company pages
* AmbitionBox

Goal:
discover employers.

Output:

```json id="d6wplm"
[
  {
    "company": "Razorpay",
    "domain": "razorpay.com"
  }
]
```

IMPORTANT:
DO NOT pre-seed all companies in India.

Discovery is:
query-driven.

---

# PHASE B — CAREER PAGE DISCOVERY

Browser agent:

* opens company homepage
* searches:

  * careers
  * jobs
  * work with us
  * hiring

Playwright used here.

Output:

```json id="6v3yfr"
{
  "company": "Razorpay",
  "career_url": "https://razorpay.com/jobs/"
}
```

---

# PHASE C — NETWORK/API DISCOVERY

THIS is the critical missing layer.

Current system incorrectly:
parses HTML.

Correct system:
discovers hidden APIs.

Browser agent:

* renders JS
* intercepts:

  * fetch
  * XHR
  * GraphQL
* captures JSON responses

Detect:

* Greenhouse
* Lever
* Ashby
* Workday
* custom APIs
* internal JSON feeds

Output:

```json id="rw5t42"
{
  "company": "Myntra",
  "platform": "SpireAI",
  "api_endpoint": "/ies/v1/p/requisition/_search"
}
```

---

# PHASE D — STRUCTURED EXTRACTION

Extract:

```json id="g4sp9l"
{
  "title": "",
  "location": "",
  "department": "",
  "description": "",
  "apply_url": ""
}
```

LLM cleans:

* HTML
* garbage formatting
* inconsistent layouts

---

# PHASE E — ROLE FILTERING

Before ranking:
filter irrelevant roles.

Example:

```python id="r8ljv2"
similarity(job, user_target_role)
```

Reject:

* HR
* Legal
* Transport
* unrelated ops

This fixes garbage contamination.

---

# PHASE F — SCORING

Score based on:

* role relevance
* salary fit
* geography fit
* company preference
* inferred hiring probability
* user success history

---

# PHASE G — RESUME TAILORING

Existing tailoring pipeline reused.

Input:

* NormalizedResume
* JobDescription
* User Positioning

Output:
tailored resume.

---

# SEARCH SYSTEM 2 — RECRUITER SEARCH

# GOAL

Find recruiters connected to:

* role
* company
* geography

---

# FLOW

Input:

```text id="9z5c7f"
AI Product Manager
Razorpay
Bangalore
```

Search:

* LinkedIn
* recruiter pages
* hiring pages
* recruiter directories

Find:

* recruiter LinkedIn
* recruiter email
* talent acquisition contacts

Output:

```json id="u5q5j0"
{
  "name": "",
  "linkedin": "",
  "email": "",
  "role": "Technical Recruiter"
}
```

---

# SEARCH SYSTEM 3 — REFERRAL SEARCH

# GOAL

Find employees likely to help.

---

# FLOW

Search:

```text id="hf7x3x"
site:linkedin.com Razorpay AI Product Manager Bangalore
```

Find:

* same-function employees
* alumni
* nearby employees
* mutuals

Output:

```json id="jlwmkk"
{
  "employee_name": "",
  "linkedin": "",
  "department": "",
  "seniority": ""
}
```

---

# FEEDBACK LOOP ENGINE

THIS is the actual moat.

System tracks:

* applications
* interviews
* rejections
* recruiter replies
* resume versions
* outreach versions

---

# EMAIL TRACKING

User connects:

* Gmail
* Outlook

System detects:

* rejection
* interview
* assessment
* recruiter reply
* ghosting

---

# LEARNING ENGINE

Example:

* Resume Version B
* Product-heavy wording
* Fintech companies
* Bangalore

Generated:

* 4 interviews

System increases:

* fintech weighting
* product weighting
* Bangalore weighting

Search converges.

Like hyperparameter tuning.

---

# CORE DATA FLOW

```text id="rf3fh1"
Resume/Input
    ↓
Normalization
    ↓
Intent Vector
    ↓
Employer Discovery
    ↓
Career Discovery
    ↓
Browser Navigation
    ↓
API Discovery
    ↓
Job Extraction
    ↓
Role Filtering
    ↓
Scoring
    ↓
Resume Tailoring
    ↓
Application
    ↓
Email Tracking
    ↓
Feedback Loop
    ↓
Search Optimization
```

---

# WHAT EXISTS TODAY

## Existing

* ATS adapters
* Playwright infra
* Resume council
* Resume rendering
* Dedup logic
* Basic scoring
* Tailoring pipeline

## Broken

* ATS-first architecture
* hardcoded ATS assumptions
* static company seeding
* HTML parsing dependency
* weak role filtering

---

# WHAT NEEDS TO BE BUILT

## P0 — MOST IMPORTANT

### Network Discovery Layer

* intercept XHR/fetch
* detect hidden APIs
* extract JSON payloads

This is the highest priority.

---

## P1

### Employer Discovery Engine

* Google Maps
* LinkedIn companies
* startup discovery
* domain enrichment

---

## P2

### Dynamic Browser Navigation Agent

* click
* paginate
* search
* scroll
* expand jobs

Human-like traversal.

---

## P3

### Recruiter Search Engine

---

## P4

### Referral Search Engine

---

## P5

### Closed-loop Feedback Engine

---

# IMPORTANT ARCHITECTURAL PRINCIPLES

## DO NOT

* scrape entire internet
* seed all companies manually
* hardcode ATS slugs
* assume static URLs
* depend only on ATS

---

## DO

* discover on demand
* browse like humans
* intercept APIs
* cache discovered endpoints
* learn from outcomes

---

# FINAL PRODUCT DEFINITION

CareerLoop is:

An adaptive employment intelligence system that continuously learns how to get a specific person employed faster.

---

---

# IMPLEMENTATION STATUS — 2026-05-19

## SEARCH SYSTEM 1 — JOB SEARCH ENGINE

### Phase Status

| Phase | Status | File | Notes |
|-------|--------|------|-------|
| A — Employer Discovery | ⚠️ Partial | `company_discovery.py` | Google Maps/Wellfound/YC/Inc42 built. Needs SerpAPI key. Untested at scale. |
| B — Career Page Discovery | ⚠️ Partial | `company_portal_scraper.py` | Static HEAD probing. Vision requires Playwright click-nav. |
| C — Network/API Discovery | ✅ Done | `portal_scraper.py` L1 + `api_interceptor.py` | Playwright intercepts XHR/fetch. Detects: Greenhouse, Lever, Ashby, Workday, SpireAI, Skima, custom JSON. Proved: Razorpay, Myntra, Nykaa. |
| D — Structured Extraction | ✅ Done | `ats_adapter.py`, `portal_scraper.py` L2 | JSON→struct for all major ATS. DOM fallback for JS-rendered portals (UUID hrefs, custom cards). LLM cleanup NOT yet wired. |
| E — Role Filtering | ✅ Done | `role_similarity.py` | sentence-transformers all-MiniLM-L6-v2, threshold 0.40, token-overlap fallback. |
| F — Scoring | ✅ Done | `india_fit_engine.py` | 15-dimension fit scoring. |
| G — Resume Archetype | ❌ Not built | — | Correct. Vision defines this as async post-search layer. Not blocking Search 1. |

### 3-Layer Browser Architecture (implemented)

```
L1 — Network/API interception   ← fastest, cleanest
     ↓ (if no API found)
L2 — Rendered DOM extraction    ← JS-rendered HTML + iframes + UUID hrefs
     ↓ (if < 3 jobs)
L3 — Agentic navigation         ← scroll, click Load More, paginate
```

Single Playwright session per company. All layers share one browser open.

### 5 Delivery Metrics

| Metric | Status | Notes |
|--------|--------|-------|
| Scrape from job boards | ✅ Works | JobSpy + Indeed adapter. Fast: 30s for hundreds of jobs. |
| Scrape from company portals | ✅ Works, ⚠️ SLOW | ~15s per site sequential. 20 companies = 5 min. Scalability fix needed. |
| Links open / work | ✅ Yes | ATS API URLs, UUID Skima links, SpireAI direct — all real. |
| Can apply | ⚠️ Partial | Apply URLs present on all jobs. No form auto-fill yet. |
| E2E pipeline works | ✅ Wired | A→B→C→D→E→F complete. `OnDemandSearch.run()` executes full chain. |

### Scalability Problem + Fix

**Problem:** Sequential portal scraping. 1 browser session × 15s × 20 companies = 5 minutes.

**Not acceptable for on-demand search.**

**Fix — 3-tier speed hierarchy:**

```
TIER 1 (0-30s): Job boards first
  → JobSpy / Naukri / Indeed → hundreds of jobs, no browser needed
  → Return these to user immediately

TIER 2 (~0s for cache hits): Known ATS
  → Razorpay → Greenhouse cached → direct API call, skip Playwright
  → Cache TTL: 7 days (ATS rarely changes)

TIER 3 (parallel, for new portals only):
  → N=5 concurrent browser workers
  → 20 companies / 5 workers = 4 batches × 15s = ~60s
  → Results stream back as each batch completes
```

**What needs to be built for scalability:**
- [ ] Parallel portal scraper (asyncio + N workers)
- [ ] ATS cache in DB (discovery caches endpoint, next run hits API directly)
- [ ] Job board results returned first (streaming), portal results appended async

### Known Portal Coverage

| Company | Method | Result |
|---------|--------|--------|
| Myntra | SpireAI API (pre-check) | 14 jobs ✅ |
| Razorpay | Greenhouse via L1 interception | 42 India jobs ✅ |
| Nykaa | Skima SSR DOM (L2) | 10 jobs ✅ |
| Shoppers Stop | Domain parked — wrong URL | 0 ❌ Need correct URL |
| Fabindia | Email-only portal (careers@fabindia.net) | 0 ❌ No job listing system |

### What Fails and Why

| Failure mode | Root cause | Fix |
|--------------|-----------|-----|
| JS portal = 0 jobs | requests.get() doesn't execute JS | ✅ Fixed — Playwright renders |
| UUID hrefs not detected | Link extractor required `/job/` pattern | ✅ Fixed — UUID regex added |
| boards.greenhouse.io → 404 | Deprecated endpoint | ✅ Fixed — boards-api.greenhouse.io |
| Parked domains | Wrong career page URL in DB | Needs better Phase B (Playwright nav) |
| Anti-bot portals (Workday) | Bot detection blocks headless | L3 agentic + realistic headers |

### System Maturity

| Area | Maturity |
|------|----------|
| ATS scraping | Strong |
| API interception | Strong |
| Browser rendering | Strong |
| DOM extraction | Moderate |
| Employer discovery | Weak |
| Scalability / parallelization | Missing |
| Recruiter search | Missing |
| Referral search | Missing |
| Feedback loop learning | Missing |

---

## WHAT TO FOCUS ON NEXT

Priority order:

### 1. Parallelization (P0 — blocks scalability)

Current: sequential, 1 browser × 15s × 20 companies = 5 min.

Fix:
```
TIER 1 (0-30s)  : job boards first → return to user immediately
TIER 2 (~0s)    : cached ATS → direct API call, no browser
TIER 3 (parallel): new portals → asyncio + N=5 browser workers
```

Need to build:
- asyncio parallel portal scraper
- ATS endpoint cache in DB (7-day TTL)
- streaming result return (job boards first, portals append)

### 2. Phase B improvement (P1)

Current: static HEAD probing for career page URL.

Fix: Playwright navigation — open homepage, click links, find careers page.

Fixes parked domain misses + weird portal paths.

### 3. Phase A breadth (P2)

Current: discovery sources exist but untested at scale.

Fix: stress-test, add ranking/dedup, validate SerpAPI integration.

### 4. Apply automation (P3)

Apply URLs exist. Need:
- form detection
- field mapping
- user confirmation before submit

### 5. Search Systems 2 + 3 (P4)

Recruiter search + referral search.

Not started. Blocked on: Search 1 must be stable first.

### 6. Feedback loop (P5)

Email tracking → rejection/interview detection → search reweighting.

Not started. Long-term moat.

---

## SEARCH SYSTEM 2 — RECRUITER SEARCH

**Status: ❌ Not started.**

---

## SEARCH SYSTEM 3 — REFERRAL SEARCH

**Status: ❌ Not started.**

---

## FEEDBACK LOOP ENGINE

**Status: ❌ Not started.**


---

# Resume Approach

Correct. You should NOT fully tailor the resume for every single application. That becomes:

* expensive
* slow
* noisy
* inconsistent
* overfit garbage

What you ACTUALLY want:

# 1. BASE POSITIONING RESUME

One strong master version.

Example:

* AI Product Manager
* Data/Product hybrid
* Consulting + AI systems

This is the PRIMARY resume.

Most applications use this.

---

# 2. LIGHTWEIGHT ADAPTATION

Not full rewriting.

Only:

* keywords
* headline
* summary
* skill ordering
* project emphasis

Example:

For:

* fintech AI PM

emphasize:

* analytics
* growth
* experimentation

For:

* enterprise SaaS PM

emphasize:

* stakeholder management
* roadmap
* platform systems

THAT'S IT.

Not rewriting entire resume.

---

# 3. WHY TAILORING EXISTS

Because ATS/recruiters search for:

* keywords
* relevance
* obvious alignment

If job says:

```text
MLOps, Kubernetes, AWS
```

and your resume says:

```text
AI infrastructure
```

you may get filtered.

So lightweight adaptation improves matching.

---

# 4. REAL SYSTEM

You want:

```text
Master Resume
    ↓
Role Archetype Resume
    ↓
Minor Adaptation
```

NOT:

```text
New Resume Per Job
```

That is stupid.

---

# 5. BEST ARCHITECTURE

User eventually has:

* 1 master resume
* 3-5 archetype resumes

Example:

* Product resume
* AI resume
* Consulting resume
* Operations resume

Then:
small tuning per opportunity.

That is scalable and realistic.

---

# SEARCH 1 PHASE IMPLEMENTATION

# PHASE A — EMPLOYER DISCOVERY

Goal:
Given:

```json id="o6w5ev"
{
  "role": "AI Product Manager",
  "location": "Bangalore"
}
```

Return:

```json id="9obx7j"
[
  {
    "company": "Razorpay",
    "domain": "razorpay.com",
    "source": "wellfound"
  }
]
```

NOT jobs.
ONLY employers.

---

# INPUT PIPELINE

First generate:

* role aliases
* industry aliases
* company type aliases

Example:

```python id="s4gk1i"
ROLE_ALIASES = {
  "AI Product Manager": [
      "Product Manager AI",
      "AI PM",
      "ML Product Manager",
      "GenAI Product Manager"
  ]
}
```

Then generate search queries:

```python id="qzhtv3"
queries = [
  "AI startups Bangalore",
  "product companies Bangalore",
  "fintech startups Bangalore",
  "SaaS Bangalore"
]
```

---

# GOOGLE MAPS IMPLEMENTATION

Use:

* SerpAPI
  OR
* Google Maps scraper

Recommended:

```bash id="t91yif"
pip install serpapi
```

Code:

```python id="8f7uql"
from serpapi import GoogleSearch

params = {
    "engine": "google_maps",
    "q": "AI startups Bangalore",
    "api_key": API_KEY
}

results = GoogleSearch(params).get_dict()

companies = []

for r in results.get("local_results", []):
    companies.append({
        "company": r.get("title"),
        "website": r.get("website"),
        "address": r.get("address"),
        "source": "google_maps"
    })
```

Output:

```json id="x8x93g"
{
  "company": "Razorpay",
  "website": "https://razorpay.com"
}
```

---

# WELLFOUND IMPLEMENTATION

Use Playwright.

Why?
No public API.

Install:

```bash id="q0uy83"
pip install playwright
playwright install
```

Flow:

```python id="4f1s0v"
from playwright.async_api import async_playwright

async def search_wellfound(query):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        url = f"https://wellfound.com/role/l/{query}"
        await page.goto(url)

        await page.wait_for_timeout(5000)

        html = await page.content()

        return html
```

Then parse:

```python id="t7xqyf"
from bs4 import BeautifulSoup

soup = BeautifulSoup(html, "html.parser")
```

Extract:

* company
* startup URL
* hiring tags

---

# CRUNCHBASE IMPLEMENTATION

Do NOT scrape heavily.

Use:

* Google search
* lightweight extraction

Query:

```python id="f1zk9l"
query = "site:crunchbase.com AI startups Bangalore"
```

Use SerpAPI:

```python id="5i5z8s"
params = {
  "engine": "google",
  "q": query,
  "api_key": API_KEY
}
```

Extract:

* company names
* Crunchbase URLs

Then enrich later.

---

# Y COMBINATOR IMPLEMENTATION

Simple.

Use:

```text id="r8dg3m"
https://www.ycombinator.com/companies
```

Playwright:

```python id="3xv9n8"
await page.goto(
  "https://www.ycombinator.com/companies"
)
```

Search:

```python id="yc0jcu"
await page.fill('input[type="text"]', "Bangalore AI")
```

Extract:

* company
* YC URL
* tags

---

# G2 IMPLEMENTATION

Google-first approach.

Query:

```python id="nfrcij"
site:g2.com SaaS companies Bangalore
```

Extract:

* company names
* categories

DO NOT deep scrape G2 initially.

---

# NAUKRI IMPLEMENTATION

Use:

* search pages
* company pages

Example:

```text id="ty6p0u"
https://www.naukri.com/companies-hiring-in-bangalore
```

Playwright:

```python id="w8ltvf"
await page.goto(url)
```

Extract:

* company names
* job counts
* company URLs

---

# AMBITIONBOX IMPLEMENTATION

Search:

```text id="40zsz0"
site:ambitionbox.com Bangalore fintech companies
```

Extract:

* company names
* ratings
* industries

---

# STARTUP LIST IMPLEMENTATION

Use:

* Inc42
* YourStory
* Tracxn lists
* startup ecosystem articles

Google:

```python id="pkovt5"
query = "top fintech startups Bangalore site:yourstory.com"
```

Extract:

* company names

---

# DEDUP

Normalize:

```python id="v99vgx"
def normalize(name):
    return name.lower().strip()
```

Dedup:

```python id="x6x8d2"
key = sha256(normalize(company))
```

---

# OUTPUT OF PHASE A

Final:

```json id="q2q0yx"
[
  {
    "company": "Razorpay",
    "website": "https://razorpay.com",
    "source": "google_maps"
  }
]
```

Store in:

```text id="zjlwmw"
companies_cache
```

TTL:
7 days.

---

# PHASE B — CAREER PAGE DISCOVERY

Goal:
Find:

* careers page
* jobs page

---

# IMPLEMENTATION

Input:

```json id="9f6mlc"
{
  "company": "Razorpay",
  "website": "https://razorpay.com"
}
```

---

# PLAYWRIGHT ROLE

Playwright:

* opens browser
* renders JS
* clicks links
* waits for React/Vue apps

Install:

```bash id="y9w1lz"
pip install playwright
playwright install
```

---

# CAREER PAGE SEARCH

Code:

```python id="grv8zn"
KEYWORDS = [
  "careers",
  "jobs",
  "join us",
  "work with us",
  "hiring"
]
```

Open page:

```python id="n7m5k0"
await page.goto(company_url)
```

Find links:

```python id="11gx1d"
links = await page.locator("a").all()
```

Extract href/text:

```python id="92mj3v"
for link in links:
    text = await link.inner_text()
    href = await link.get_attribute("href")
```

Check keyword similarity.

Return:

```json id="7tn35p"
{
  "career_url": "https://razorpay.com/jobs/"
}
```

---

# PHASE C — NETWORK/API DISCOVERY

THIS is critical.

Goal:
Discover hidden APIs.

---

# IMPLEMENTATION

Playwright intercepts network.

Code:

```python id="pn6tvx"
page.on("response", handle_response)
```

Handler:

```python id="97e2z8"
async def handle_response(response):
    url = response.url

    if any(x in url.lower() for x in [
        "jobs",
        "graphql",
        "careers",
        "requisition",
        "posting"
    ]):
        print(url)
```

Capture:

* GraphQL
* JSON APIs
* XHR

---

# WHY THIS WORKS

Modern sites:

* render jobs via APIs
* not HTML

Browser sees:

```text id="kw2q3l"
fetch("/api/jobs")
```

You intercept it.

---

# JSON EXTRACTION

Check:

```python id="nhwdd6"
content_type = response.headers.get("content-type")
```

If JSON:

```python id="mjlwmm"
data = await response.json()
```

Save:

```json id="3s4pjv"
{
  "company": "Myntra",
  "api_url": "/ies/v1/jobs/search"
}
```

---

# PHASE D — STRUCTURED EXTRACTION

Goal:
Convert garbage → jobs.

---

# INPUT

Could be:

* JSON
* GraphQL
* HTML
* embedded script tags

---

# EXTRACTION

If JSON:
map fields directly.

Example:

```python id="2ccn8u"
job = {
    "title": item.get("title"),
    "location": item.get("location"),
    "description": item.get("description")
}
```

If HTML:

```python id="w6qv7n"
from bs4 import BeautifulSoup
```

Use LLM only LAST.

NOT first.

---

# OUTPUT

```json id="9d9p5k"
{
  "title": "AI Product Manager",
  "location": "Bangalore",
  "description": "...",
  "apply_url": "..."
}
```

---

# PHASE E — ROLE FILTERING

Goal:
Reject garbage jobs.

---

# INPUT

```json id="m3g9j0"
{
  "target_role": "AI Product Manager",
  "job_title": "HR Business Partner"
}
```

---

# IMPLEMENTATION

Use embeddings.

Install:

```bash id="b8q49y"
pip install sentence-transformers
```

Code:

```python id="qjlwmn"
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
```

Embed:

```python id="0dqibz"
model = SentenceTransformer(
  'all-MiniLM-L6-v2'
)
```

Similarity:

```python id="ffm5vq"
score = cosine_similarity(
  role_embedding,
  job_embedding
)
```

Reject:

```python id="jlwm7f"
if score < 0.55:
    reject
```

---

# PHASE F — SCORING

Goal:
Rank best jobs.

---

# INPUT

```json id="t31b7y"
{
  "role_similarity": 0.91,
  "location_match": 1,
  "company_preference": 0.8
}
```

---

# SCORING

```python id="jrnz6g"
final_score = (
  role_similarity * 0.5 +
  location_match * 0.2 +
  company_preference * 0.2 +
  hiring_probability * 0.1
)
```

Sort descending.

---

# PHASE G — RESUME ARCHETYPE GENERATION

THIS IS NOT SEARCH.

THIS IS ASYNC.

Human-in-loop/paywall layer.

Correct.

---

# INPUT

100 jobs collected.

Cluster jobs:

```text id="6fdp4w"
AI PM
Platform PM
Growth PM
Technical PM
Enterprise PM
```

Generate:
5 archetype resumes.

NOT 100 resumes.

---

# FLOW

```text id="06ntcg"
Jobs
    ↓
Role Clustering
    ↓
Archetype Detection
    ↓
Resume Variants
```

---

# OUTPUT

```json id="40gk9r"
[
  {
    "resume_type": "AI Product Resume"
  },
  {
    "resume_type": "Growth Product Resume"
  }
]
```

---

# IMPORTANT

Search system ENDS at:

```text id="ih3m9h"
ranked_jobs
```

Resume generation is:
post-search optimization layer.

Separate pipeline entirely.

