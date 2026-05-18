# CareerLoop — Product Requirements Document

**Author:** Siddharth Saminathan  
**Status:** Canonical Vision v1.0 — Active  
**Last Updated:** 2026-05-18  

> This is the single source of truth for what CareerLoop is, who it's for, and what it must do.  
> All engineering, design, and agent work must align to this document.  
> The tracker at the bottom is updated by the `careerloop-product-lead` skill each session.

---

## 0. One-Liner

**CareerLoop is an AI-native career execution system for Indian professionals.**

---

## 1. What CareerLoop Is — and Is Not

CareerLoop is **not**:
- A job board
- A resume builder
- A chatbot
- A spreadsheet tracker
- An ATS spray tool

CareerLoop **exists** to help users:

```
discover → decide → position → apply → follow up → prepare → learn → improve
```

without drowning in cognitive overload.

**Core philosophy:**
> The user should make decisions. The system should handle the chaos.

---

## 2. The Core Problem

The internet has infinite job information. But users still fail because:

- Too much noise
- Weak positioning
- Low confidence
- Application fatigue
- Poor follow-up
- Fragmented tools
- Generic AI outputs
- No memory
- No strategy
- No accountability

The real bottleneck is **career execution under uncertainty** — not information access.

---

## 3. The User We Are Building For

**Primary ICP:** Indian professionals trying to improve their career situation.

This includes:
- Freshers
- Employed switchers
- AI/tech workers
- Analysts and consultants
- Burned-out employees
- People escaping toxic jobs
- People wanting higher salary/stability/growth

**Emotional state matters.** Users are: anxious, overwhelmed, tired, uncertain, overprompting ChatGPT, manually managing chaos.

CareerLoop must reduce psychological load.

---

## 4. The Core Product Loop

```
Discover
→ Verify
→ Filter
→ Decide
→ Research
→ Position
→ Prepare
→ Apply
→ Follow up
→ Interview
→ Learn
→ Improve
```

Every feature must strengthen this loop. Every session must move the user forward on it.

---

## 5. Discovery Engine

CareerLoop discovers jobs using:
- LinkedIn, Naukri, Instahyre, Cutshort, Hirist, IIMJobs, Foundit
- Company career pages and ATS pages
- Referrals and recruiter signals
- Google search with structured extraction

Discovery is:
- **India-first** — geographic hard filter
- **Verified** — stale/fake/search-page jobs are rejected
- **Deduplicated** — cross-source dedup
- **Relevance-scored** — not just keyword-matched
- **Temporally aware** — posting age matters

The system must understand: stale jobs, fake jobs, search pages, category pages, blog spam, duplicate listings.

**Only verified opportunities survive.**

---

## 6. Opportunity Intelligence

Every job becomes a structured object — not just title + company + link, but:

- Role quality
- Hiring intent signals
- Compensation signals
- Company maturity
- Application difficulty
- Recruiter visibility
- Relevance confidence
- Strategic upside
- User-fit confidence

The product must answer: **Is this actually worth the user's time?**

---

## 7. Decision Compression

**This is one of the biggest wedges.**

CareerLoop must compress 100 noisy results into 5 intelligent decisions. Never dump giant lists.

The system should say:
> "I scanned 100 opportunities. 12 survived verification. 5 are worth acting on today."

This is not search. **This is strategic filtering.**

---

## 8. Career State Awareness

CareerLoop must understand the user's current emotional and strategic state:

| Mode | Trigger | Behavior |
|------|---------|---------|
| **Hunt** | Unemployed / active seeker | Max application surface, daily queue, aggressive pre-generation |
| **Upgrade** | Employed but unhappy | Fewer roles, higher bar, comp/trajectory focused |
| **Explore** | Passive browser | Zero pressure, weekly digests, long-term mapping |
| **Emergency** | Tight timeline / severe pressure | Daily velocity, strict accountability, momentum tracking |

The same jobs should not be shown identically to every user.

---

## 9. Company Intelligence

After the user expresses interest, the system researches:
- What the company actually does
- Business model and culture signals
- Hiring intent and stability
- Growth trajectory
- Likely interview style and compensation expectations
- Recruiter expectations
- Risks and red flags

**Goal:** Help the user decide whether this company deserves their effort. Not generic internet summaries.

---

## 10. Positioning Engine

CareerLoop must strategically position the user for this company, this role, this market context.

The system must answer: **Why this user for this role right now?**

This includes:
- Tone and narrative angle
- Strengths to lead with
- What to soften or not claim
- Recruiter-first impression
- What makes this candidate credible in 10 seconds

**This is not keyword stuffing. This is strategic representation.**

---

## 11. Resume Council

Resume Council is a structured application compiler — not freeform generation.

It:
- Parses the master profile
- Preserves structure and truthfulness
- Separates private vs public metadata
- Validates claims (Truth Guard)
- Rewrites sections surgically
- Humanizes output
- Assembles deterministic application packs

The system must prevent:
- Hallucinated skills
- AI slop language
- Private metadata leakage
- Broken chronology
- Over-positioning
- Fake expertise

**This becomes one of the deepest moats.**

---

## 12. Humanizer Layer

**This is a monetizable wedge.**

The Humanizer removes:
- Generic AI language ("leverage", "spearheaded", "synergy")
- Corporate filler
- Fake confidence
- Unnatural phrasing
- Keyword spam
- Robotic cadence

Output must feel: grounded, intelligent, specific, human, interview-defensible.

> **The bar:** "Looks like a thoughtful human wrote this."

---

## 13. Application Execution Layer

CareerLoop reduces application friction. The system prepares:
- Resume/profile (tailored)
- Recruiter messages
- Cover notes
- Screening answers
- Follow-ups
- Interview prep

Future execution:
- Chrome extension for assisted autofill
- Application tracking
- Recruiter outreach automation

**The user remains in control of final submission — always.**

---

## 14. Interview Memory and Learning Loop

**This is another moat.**

The system remembers:
- Interview rounds and questions asked
- Weak vs strong areas
- Recruiter reactions
- Rejection patterns
- Successful positioning
- Company-specific learnings

After rejection, the system answers:
> "What actually happened? What mattered? What should we improve? What should we ignore?"

**This creates compounding intelligence.**

---

## 15. Persistent Career Memory

CareerLoop becomes a **career operating system**. It remembers:
- User preferences and deal-breakers
- Successful applications and rejected jobs
- Interview learnings
- Communication preferences
- Confidence patterns and risk tolerance

Over time: less prompting, less explaining, better positioning, better recommendations.

**This is a long-term memory graph. The longer you use it, the smarter it gets.**

---

## 16. The End-State Vision

CareerLoop should feel like:

```
a recruiter
+ a strategist
+ a researcher
+ a career coach
+ an execution operator
+ a brutally honest editor
+ a memory system
```

working together, 24/7, for one user.

The user should feel:
> "I am no longer handling my career transition alone."

---

## 17. Product Engineering Tracker

> Updated by the `careerloop-product-lead` skill. Last updated: 2026-05-18.

| System | Completion | Status | Notes |
|--------|-----------|--------|-------|
| India-first discovery | 75% | 🟡 Active | ATS adapter, portal scraper, on-demand search, role keywords shipped |
| Verification & filtering | 60% | 🟡 Active | detect_ats_pass.py; Block G not hoisted |
| Opportunity scoring (14-dim) | 55% | 🟡 Active | function_probability.py + metrics.py; needs calibration |
| Decision compression / triage | 20% | 🔴 Gap | modes/ofertas.md reusable; no UX |
| Career state system (modes) | 10% | 🔴 Gap | Conceptual only |
| Company intelligence | 20% | 🔴 Gap | Vision doc published; Council JD-grounded; company_intel.py not built |
| Positioning engine | 20% | 🟡 Active | Council S6 wired; tailoring delta 3.6% (needs prompt work) |
| Resume Council (v3) | 60% | 🟡 Active | All 8 systems pass; Humanizer; Truth Guard; deterministic compiler |
| Humanizer layer | 50% | 🟡 Active | 5-phase pipeline; 28 banned words; LLM wired; post-Humanizer verification |
| Resume rendering (templates) | 70% | 🟡 Active | NormalizedResume contract; 9 templates; 36/36 clean renders |
| Validator / QA | 60% | 🟡 Active | 10 rules; regression_test.py CI-ready; 94.4% pass rate |
| Application execution | 15% | 🔴 Gap | modes/apply.md prototype; Chrome extension not started |
| Chrome extension | 0% | ⚫ Not started | Phase 3 |
| Follow-up system | 25% | 🔴 Gap | Ledger auto-schedules; UI missing |
| Interview memory | 10% | 🔴 Gap | modes/interview-prep.md 4★; no DB persistence |
| Persistent memory graph | 25% | 🟡 Active | Ledger + company_registry + SQLite schema |
| WhatsApp/transport UX | 15% | 🔴 Gap | Concept only |
| Monetization logic | 30% | 🟡 Active | Strategic understanding solid |

**Overall product maturity: ~30-35% of vision.** (+10% after 6-agent stabilization pass. Council 45→60%, Humanizer 5→50%, Rendering 60→70%, Validator new at 60%.)

> Legend: 🟢 Done · 🟡 Active · 🔴 Gap · ⚫ Not started

> Legend: 🟢 Done · 🟡 Active · 🔴 Gap · ⚫ Not started

---

## 18. Employer Discovery Engine (Addendum — 2026-05-18)

> This section extends Section 5 (Discovery Engine). Job boards are not the complete market. This layer finds employers first, then surfaces opportunities from them.

### The Gap

Job boards capture roles companies actively broadcast. They miss: companies using proprietary ATS that don't syndicate everywhere, companies that rely on direct recruiter outreach, and roles that appear only on internal career portals. For high-quality employers (funded startups, MNCs, product-first companies), their own career page is the source of truth.

### Architecture

**Discover employers → Enrich them → Infer hiring functions → Scrape career pages → Deduplicate against job boards**

This is distinct from job board scraping. The input is not a search query. The input is: geography + sector + function.

**Stage 1 — Company Universe Discovery**

Sources (priority order):
- Google Maps — real operating businesses, best regional coverage
- LinkedIn Companies — employee count, industry, growth signals
- YC / Wellfound / Crunchbase — funded startups with high hiring velocity
- Inc42 / StartupIndia / YourStory — India-specific startup directories
- Apollo / Clearbit — domain enrichment, tech stack signals

Not used: JustDial, MCA registrations (too much noise, too many shell companies).

**Stage 2 — Company Enrichment**

Per company: detect ATS provider (Greenhouse/Lever/Ashby/Workday/SmartRecruiters), find career page URL, find LinkedIn, identify engineering blog / hiring signals.

ATS detection is the most valuable step — it turns the company into a structured crawl target rather than an unstructured HTML page.

**Stage 3 — Function Probability Engine**

Not every company hires every function. A garment manufacturer has low ML engineering probability. Myntra has high ML probability. This layer infers function-hiring likelihood from: employee LinkedIn titles, tech stack, historical posting patterns, company category.

This prevents irrelevant company suggestions. A user searching for MLOps jobs does not see companies with near-zero ML hiring probability.

**Stage 4 — Career Page Scraping**

Priority: ATS structured APIs first (Greenhouse `/jobs`, Lever `/postings`, Ashby GraphQL) — these return clean JSON, no scraping needed. Then: career page HTML via ScrapeGraph + Playwright. Then: LinkedIn jobs for that company. Then: Naukri company page.

**Stage 5 — Cross-Source Deduplication**

Same job appearing on Naukri AND company career portal must appear once. Dedup key: `sha256(normalize(company) + normalize(title) + normalize(city))`. Both records are stored (provenance preserved); users see one result.

### MECE Sector Map

15 sectors cover all Indian employers. Functions are horizontal (cross-sector). Discovery routes by `Function → Geography → Company Universe`, not by industry alone.

| Sector | Examples |
|--------|---------|
| Technology & Software | SaaS, AI/ML, DevTools, IT Services, GCCs, Cybersecurity |
| Financial Services | Fintech, Payments, Lending, Banking, Insurtech, Wealthtech |
| Consulting & Professional Services | Strategy, Big 4 Audit, Tax, Legal, Staffing |
| Retail & Commerce | Fashion, Fast Fashion, D2C, E-commerce, FMCG |
| Manufacturing & Industrial | Automotive, Electronics, Textiles, Chemicals |
| Healthcare & Life Sciences | Hospitals, Pharma, Biotech, Healthtech, Diagnostics |
| Media & Creative | Advertising, Marketing Agencies, Film/TV, Creator Economy |
| Education | EdTech, Universities, Coaching, Corporate Training |
| Logistics & Mobility | Logistics, Supply Chain, Last-mile, Mobility |
| Real Estate & Infra | Construction, PropTech, Facility Management |
| Energy & Utilities | Oil & Gas, Renewables, EV Infra |
| Government & Public Sector | PSUs, GovTech, Smart City |
| Hospitality & Travel | Hotels, Tourism, Travel Tech |
| Agriculture & Food | AgriTech, Food Processing, Farming Supply Chain |
| Nonprofit & Social Impact | NGOs, Climate Orgs, Social Enterprise |

---

## 19. Human Pipeline Layer — Referral, Recruiter, Cold Outreach (Addendum — 2026-05-18)

> This section formalizes the four application paths and positions CareerLoop's role in each.

### The Four Paths to a Role

The job market operates on four distinct channels. CareerLoop must understand and assist with all four, not just the first.

| Path | Description | What CareerLoop Does |
|------|-------------|---------------------|
| **1. Direct Application** | Apply via ATS or career portal | Fully covered: discovery → scoring → application pack → submit |
| **2. Recruiter Inbound** | Respond to recruiter outreach (LinkedIn, email) | Evaluate the role, prep positioning, draft reply, fast-track Council |
| **3. Warm Referral** | Someone inside the company refers you | Find employees at target company → identify likely connectors → draft outreach → track referral ask |
| **4. Cold Outreach** | Proactively contact hiring manager, recruiter, or relevant employee | Find the right person → draft cold DM/email → personalize per company → track responses |

### Recruiter Discovery

For every high-priority company in the employer graph:
- Find active recruiters at that company (LinkedIn: "recruiter at {company}", "talent acquisition at {company}")
- Find relevant hiring managers (LinkedIn: "{function} manager at {company}", "{team} lead at {company}")
- Store as `people` records with: name, title, LinkedIn URL, company_id, discovered_at

This turns the employer graph into a people graph over time.

### Warm Referral Path

Steps:
1. User marks a company as high-priority
2. System scans user's 1st-degree LinkedIn connections at that company
3. Identifies best connection based on: relationship depth, function relevance, seniority
4. Drafts a referral ask message — personal, specific, non-generic
5. Tracks: asked → responded → submitted referral → outcome

### Cold Outreach Path

Steps:
1. User targets a company with no open roles or no connection
2. System finds: hiring manager or senior IC in the relevant function
3. Drafts cold DM (LinkedIn) or cold email: specific to their work, company context, user's positioning
4. Output: ready-to-send message, not a template
5. Tracks: sent → replied → call booked → outcome

### The People Graph

The people layer compounds over time. Every recruiter who replied, every hiring manager who responded, every referral that converted — these are signals. The system learns: which outreach patterns work per sector, which companies are referral-friendly, which recruiters are responsive.

This is the real long-term moat. Not scraped job counts. **Career transition conversion rate.**

### Implementation Priority

| Component | Priority | Status |
|-----------|----------|--------|
| Employer discovery (Stage 1-2) | P0 | Not started |
| Career page scraping (Stage 4) | P0 | Not started |
| Cross-source dedup (Stage 5) | P0 | Partial (job boards only) |
| Function probability engine (Stage 3) | P1 | Not started |
| Recruiter discovery | P1 | Not started |
| Warm referral path | P2 | Not started |
| Cold outreach path | P2 | Not started |
| People graph persistence | P3 | Not started |
