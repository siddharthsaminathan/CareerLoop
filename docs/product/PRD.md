# CareerLoop — Product Requirements Document

**Author:** Siddharth Saminathan  
**Status:** Canonical Vision v1.0 — Active  
**Last Updated:** 2026-05-29  

> This is the single source of truth for what CareerLoop is, who it's for, and what it must do.  
> All engineering, design, and agent work must align to this document.  
> The tracker at the bottom is updated by the `careerloop-product-lead` skill each session.

---

## 0. One-Liner

**CareerLoop is an AI-native career execution system for Indian professionals.**

---

## 1. What CareerLoop Is — and Is Not

CareerLoop is **not**:
- A job board (Naukri, LinkedIn Jobs, Indeed, JobLeads)
- A resume builder (Teal, Huntr, Kickresume)
- A chatbot
- A spreadsheet tracker
- An ATS spray tool (LazyApply, LoopCV)

CareerLoop **is**:
- **A Momentum Generator** — turning job openings into interviews.
- **An Execution Operator** — handling the heavy lifting of applying, outreaching, and following up.
- **A closed-loop employment intelligence layer** — learning from outcomes and continuously improving conversion rates.

CareerLoop **exists** to help users create visible weekly momentum:
```
applications submitted → humans contacted → replies received → interviews booked
```
without drowning in cognitive overload.

**Core philosophy:**
> Finding jobs is a free commodity. Getting interviews is a paid execution problem.

**Core differentiation:**
> Others optimize: jobs scanned. We optimize: meaningful career conversations generated per week.

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

## 2.5 Why Existing Solutions Fail

**Job boards** (Naukri, LinkedIn, Indeed, JobLeads):
- Optimize: listing volume and ad inventory
- Problem: spam, noise, stale postings, no personalization
- Missing: execution layer, outcome optimization, recruiter routing
- User experience: "here are 500 jobs, good luck"

**AI Resume/Application tools** (Teal, Huntr, LazyApply):
- Optimize: resume generation and application volume
- Problem: quality over quantity, application fatigue, no strategic targeting
- Missing: employer discovery, recruiter intelligence, feedback loops
- User experience: "apply to more jobs"

**Remote job platforms** (RemoteOK, We Work Remotely, FlexJobs):
- Optimize: remote filtering
- Problem: narrow vertical, no strategy
- Missing: everything else

**Network-based hiring** (LinkedIn, referrals, recruiter DMs):
- Most effective path (actually where hiring happens)
- Problem: opaque, unstructured, opportunity-dependent, no system
- Missing: systematic recruiter discovery, referral optimization, cold outreach playbook

**Specialized platforms** (Hired, Toptal, FindAPhD):
- Optimize: vetting + matching for narrow verticals
- Problem: limited scope, expensive, not for most markets
- Missing: broad market coverage, employment intelligence

**The Real Gap:**
Nobody operationalizes the closed-loop optimization system. Everyone optimizes one lever. CareerLoop optimizes the entire funnel — continuously.

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
Discover (Free Hook)
→ Decide (Paid Wedge)
→ Create Application Pack (Resume, Cover, DMs)
→ Execute Route (Direct, Recruiter, Referral)
→ Push via Humans (Outreach)
→ Track Momentum (Dashboard)
→ Follow up
→ Improve Conversion
```

Every feature must strengthen this momentum chain. Every session must move the user closer to an interview. Scanning metrics are vanity; conversation metrics are reality.

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

## 13. Application Execution Layer (The Action Engine)

CareerLoop reduces application friction and optimizes the conversion path. For every approved job, the system determines the **Apply Route**:

- **Route A — Direct Apply**: Prepare pack, open link, track, follow up.
- **Route B — Recruiter First**: Find recruiter, draft DM, user sends, track reply, then apply.
- **Route C — Referral First**: Find employees/alumni, draft referral ask, track reply, apply after signal.
- **Route D — Skip**: Bad ROI, poor fit, weak company.

The system prepares a complete **Application Pack**:
- Resume/profile (tailored)
- Recruiter messages
- Referral DMs
- Cover notes
- Screening answers
- Follow-ups

**The user remains in control of final submission — always.** The system removes the friction of *creation* and *planning*, but the user executes the final human interaction.

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

## 16. The End-State Vision and Monetization

CareerLoop should feel like:

```
a recruiter
+ an outreach strategist
+ a researcher
+ a career coach
+ an execution operator
+ a brutally honest editor
```
working together to turn openings into interviews.

### Monetization Tiers (The Paid Packaging)

- **Free Tier:** Search + Shortlist. A taste of discovery, but no execution engine. "Here are 5 roles worth your time. Upgrade to prepare applications and outreach."
- **₹499 Student:** Shortlist + Starter Packs + Basic Outreach.
- **₹1299 Accelerator:** Application Packs + Outreach + Follow-ups + Momentum Dashboard.
- **₹2999 Offer Mode:** Daily execution support + interview prep + negotiation + aggressive outreach.

**The Upgrade Moment:** When the user clicks "Apply" on a free role, the system states: "I can prepare the resume, screening answers, recruiter DM, referral message, and follow-up plan for this role." This is the core conversion wedge.

---

## 17. Product Engineering Tracker

> Updated by the `careerloop-product-lead` skill. Last updated: 2026-05-26.

| System | Completion | Status | Notes |
|--------|------------|--------|-------|
| **Transport abstraction layer** | **65%** | 🟡 | Base + Terminal stubs. Echo fallback removed. Safe error messages. /brief + /scan + CommandRouter wired. |
| **Multi-user onboarding** | **75%** | 🟢 | 3-user real E2E verified against Supabase + DeepSeek. 5 pillars extracted, CV→profile flow works, PROFILE_READY reached. _load_profile_data returns master_cv_markdown + has_cv. |
| **LangGraph Chatbot Orchestrator** | **85%** | 🟢 | 2-node pipeline. GENERAL_CHAT returns real LLM. ActionResolver context injection. Live scan rendering. Supabase-only. |
| **PostgresSaver Checkpointer** | **20%** | 🔴 | SQLite sessions functional without Postgres. Dual-mode verified. Interrupt/resume proof still needed. |
| **Application pack delivery** | **95%** | 🟢 | PackageAssembler + Playwright PDFs. E2E validated on real job. |
| **Daily brief cron delivery** | **90%** | 🟢 | Daily Runner triggers scan and fully populates daily_briefs and daily_brief_items SQL tables. E2E database brief retrieval verified. |
| India-first discovery | 92% | 🟢 | Geo filter on all ATS adapters. Location spoofing fixed. CSV India filter. 14 ATS adapters + 6 boards. |
| Verification & filtering | 78% | 🟡 | India filter enforced at 3 choke points. Block G not hoisted. |
| Opportunity scoring (14-dim) | 62% | 🟡 | Scoring caps (CPU=50, LLM=15). Token accounting per call. _get_score() unified schema. |
| Decision compression / triage | 20% | 🔴 | CEO owns. DECISION_COMPRESSION_VISION.md written. |
| Career state system (modes) | **60%** | 🟡 | 11 real states with legacy migration. All states have setter+handler+test paths. Natural approval phrases work. |
| Company intelligence | 75% | 🟢 | MECE vision implemented; S3 cache working |
| Positioning engine | 38% | 🟡 | S6 wired; tailoring delta substantial; narrative angle reaches S7 |
| Resume Council (v3) | 93% | 🟢 | Job-aware chunking; prose fallback; 42 tests; ceiling hit |
| Humanizer layer | 65% | 🟡 | LLM rewrite active; Truth Guard UNSUPPORTED matching too aggressive |
| Resume rendering (templates) | 90% | 🟢 | 10 templates; normalizer handles 3 user CV formats; automated validation |
| ATS validator layer | 0% | ⚫ | Spec written (PRD §26). Sprint 4. |
| Resume editing layer | 0% | ⚫ | Spec written (PRD §25). Surgical edits without full Council rerun. Sprint 4. |
| Validator / QA | **83%** | 🟢 | 42 stabilization + 22 integration + 14 chat runtime regression. All passing. |
| Application execution | 18% | 🔴 | modes/apply.md prototype; Kimi bridge scaffold. Real Webbridge/Hermes integration not verified. |
| Assisted apply bridge | 5% | ⚫ | `kimi_bridge.py` mock only. Must never run queue-based or unattended submission. |
| Follow-up engine (full) | 25% | 🔴 | Scheduling exists. Message generation + delivery = Sprint 5. |
| Gmail integration | 0% | ⚫ | Sprint 6. Needs transport first. |
| Calendar integration | 0% | ⚫ | Sprint 6. Needs transport first. |
| Interview memory (full) | 25% | 🟡 | Vent parsing works. Debrief + weakness tracker = Sprint 7. |
| Persistent memory graph | **60%** | 🟡 | Schema isolation (careerloop.*). Repository layer. Fingerprint dedup. User-job relationships. |
| Background job scheduler | 0% | ⚫ | Sprint 2. Daily + per-job two classes. |
| WhatsApp / Meta Cloud API | 0% | ⚫ | After Telegram beta validates loop. |
| Monetization / billing | 0% | 🔴 | Pricing tiers defined. No paywall yet. Needs onboarding first. |
| Data engineering V3 | **95%** | 🟢 | careerloop.users identity spine. 20 FKs migrated. 14 users backfilled. 7 new tables. 12 canonical docs. Phase 1+2 complete. Companies populated, Cutshort parsing, cache-hit wired, memory architecture documented. |
| Memory architecture | **70%** | 🟡 | 7-layer model defined. 4-level recall hierarchy. 8 propagation flows. 10 anti-patterns. MEMORY_SYSTEMS_ARCHITECTURE.md created. |
| **E2E Runtime Verification** | **90%** | 🟢 | 3-user real onboarding E2E: 3/3 passed against live Supabase + DeepSeek. Priya (happy path), Rohan (correction), Ananya (gap-fill). Results in e2e_real_supabase.json. |
| **Chat quality (known issues)** | **⚠️** | 🟡 | Polite closings misclassified as HELP (2/7 E2E turns). Fix: 1-line ActionResolver prompt update. |
| Job persistence engine | **75%** | 🟡 | Global cache + user relationships. Fingerprint dedup. TTL strategy. Cache-hit check wired, companies linked via FK, Cutshort parsing. |
 
**Overall product maturity: ~77-80% of vision.** Data engineering V3 at 95%. Multi-user onboarding E2E verified (3/3 real Supabase + DeepSeek). E2E at 90%. B-ONBOARD blocker closing. Remaining: transport deployment, async scan, chat fallback.
 
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

---

## 20. ROI & UX Architecture (Addendum — 2026-05-21)

> This section references the full ROI/UX Product Vision document at `docs/product/ROI_UX_PRODUCT_VISION.md`. That document is the canonical source for the product's ROI thesis, UX philosophy, metric hierarchy, and competitive landscape. This section summarizes the key architectural decisions that flow from it.

### Core Principle

**Intelligence is the product. Automation is the UX.**

CareerLoop's ROI is measured as: how much uncertainty, time, repetition, and missed opportunity it removes from a user's career transition. Every feature must justify itself against that measure.

### ROI Formula

The core ROI of CareerLoop is:

```
ROI = (time saved × decision quality improvement) ÷ (cognitive load + application friction)
```

The system wins when the numerator grows and the denominator shrinks. This drives all prioritization.

### The 12 Product Workflows

The ROI/UX Vision maps 12 end-to-end workflows, each with a user pain point and a measurable ROI delta:

| # | Workflow | User Pain | ROI Metric |
|---|----------|-----------|------------|
| 1 | Market Scan | Manual job search across 7+ platforms | Time saved per search session |
| 2 | Job Quality Filtering | Fake/stale/irrelevant postings | Signal-to-noise ratio |
| 3 | Decision Compression | Choice paralysis from 500+ results | Decisions per session |
| 4 | Application Pack Creation | Manual resume tailoring per job | Packs generated per session |
| 5 | Humanizer Layer | Generic AI-slop language hurting credibility | Human-reader acceptance rate |
| 6 | Company Intelligence | Uninformed applications to bad-fit companies | Informed decision rate |
| 7 | Chrome Extension / Application Assist | Re-typing same info across ATS forms | Fields auto-filled per app |
| 8 | Follow-Up Intelligence | Forgetting to follow up, missing timing windows | Follow-up conversion rate |
| 9 | Gmail Career Memory | Losing context across recruiter email threads | Context retention across threads |
| 10 | Interview Prep | Unprepared, generic answers | Interview-to-offer conversion |
| 11 | Interview Post-Mortem / Venting | No structured learning from rejections | Learning captured per rejection |
| 12 | Salary / Notice Period / Negotiation | Leaving money on the table, bad notice-period timing | Comp uplift from baseline |

### The Four Entry Points

CareerLoop serves four distinct user states, each with different ROI expectations:

| Entry Point | State | Primary ROI Need |
|-------------|-------|------------------|
| A. Student / Fresher | No experience, no network | Discovery + positioning + confidence |
| B. Graduate Applying Without Results | Applying blindly, no feedback loop | Decision compression + feedback + iteration |
| C. Working Switcher | Employed, seeking upgrade | High-signal filtering + negotiation leverage |
| D. Notice-Period Warrior | Clock ticking, high pressure | Velocity + accountability + opportunity cost minimization |

### Metrics Hierarchy

The ROI/UX Vision defines a 3-tier metrics hierarchy:

1. **North Star Metric:** Career transition conversion rate (how many users land roles they're happy with)
2. **Leading Indicators:** Application-to-interview rate, interview-to-offer rate, time-to-first-interview, pack quality scores
3. **Operational Metrics:** Daily active sessions, packs generated, companies researched, follow-ups sent

### Over-Engineering Guard

The ROI/UX Vision includes a built-in anti-bloat rule: **no feature ships without a measurable ROI line item.** If a proposed feature cannot answer "what user pain does this remove and how do we measure that?", it is deferred. This is the primary defense against scope creep and feature factories.

### Brutal Prioritization (from ROI/UX Vision)

All features rank on a 2×2 matrix: **User ROI Impact × Engineering Complexity**. Low-complexity, high-ROI items ship first. High-complexity, low-ROI items are killed. This is enforced at every product review session.

### UX Architecture Principle

CareerLoop is not a dashboard. It is a command center. The UX must feel like:

> "Tell me what to do next. I'll do it. Then tell me what just happened and what to do after that."

This means: minimal UI chrome, maximum action density, conversational interface with structured outputs, zero-config onboarding, progressive disclosure of complexity.

### Reference Document

The complete ROI thesis, 12-workflow deep-dives, competitor map, monetization strategy, and rollout phasing live at:

**→ `docs/product/ROI_UX_PRODUCT_VISION.md`**

All engineering and agent work must align to both this PRD (what we build) and the ROI/UX Vision (why we build it, and how we measure success).

---

## 21. Delivery Surface Strategy (Updated — 2026-05-29)

> The API is the transport layer. The web app is the delivery surface.

### 🔴 Updated Decision: Web-First, Telegram/WhatsApp — PERMANENTLY DELAYED

**Decision (2026-05-29):** All Telegram webhook, WhatsApp webhook, and transport abstraction layer work is **permanently delayed until further notice.**

**Rationale for the pivot:**
1. The REST API (7 endpoints, live) is now the transport layer — same API serves web, iOS, Android
2. A web app provides richer UI (TAL-style cards, swipe gestures, color-coded fit scores, real-time SSE streaming)
3. Telegram Bot API limits rich card rendering; WhatsApp 24hr messaging window breaks async workflows
4. No platform approval process needed (Google OAuth via Supabase is universal)
5. Deployment cycle: minutes vs days for bot updates

**Historical reference (superseded):**
The original Telegram-first/WhatsApp-later strategy was correct for the CLI/Telegram era (2026-05-22 → 2026-05-28). With the REST API now live (2026-05-29), the correct transport is **HTTP from a web frontend**.

**What this means for existing code:**
- `careerloop/transport/` — archived, not deleted. Code kept as reference for the pattern.
- `webhook_server.py` — deprecated for user-facing use. Retained as reference for the supervisor graph invocation pattern.
- All references to Telegram/WhatsApp as primary delivery channels in the PRD and TRACKER are superseded.
- The REST API (`careerloop_api/`) IS the production transport layer.

### Canonical Transport Path (Updated)

```
REST API (careerloop_api/)
├── /v1/auth/*        — Supabase JWT auth, auto-provisioning
├── /v1/me/*          — User profile + preferences
├── /v1/briefs/*      — Daily brief + TAL-style job cards
├── /v1/jobs/*        — Job detail + save/skip (swipe)
├── /v1/chat/*        — NL interface (onboarding + supervisor graph)
├── /v1/scans/*       — Async scan + SSE event streaming
└── /health           — Health check

Frontend (React/TS)
├── consumes JSON from all endpoints
├── renders TAL cards with fit_tier colors
├── SSE stream for live scan progress
└── Supabase Google OAuth for auth
```

**The adapter pattern is now: HTTP request → JSON response.** The product layer never changes — the supervisor graph, onboarding flow, and scan pipeline are all invoked identically whether the input came from a web app, CLI, or (future) native app.

---

## 22. Conversation State Machine (Addendum — 2026-05-22)

Every user has exactly one current state. The state machine is P0 — without it, the product has no memory of what it was doing.

### States

```
IDLE
ONBOARDING_WAITING_CV
ONBOARDING_PROFILE_QUESTIONS
DAILY_BRIEF_SENT
REVIEWING_JOB
AWAITING_JOB_DECISION
PACK_GENERATING
PACK_READY
AWAITING_RESUME_REVIEW
AWAITING_APPLICATION_CONFIRMATION
APPLIED
FOLLOWUP_DUE
INTERVIEW_SCHEDULED
INTERVIEW_PREP_READY
POST_INTERVIEW_DEBRIEF
```

### Example Flow

```
Daily brief sent
→ user taps Apply
→ state = PACK_GENERATING
→ Council runs
→ state = PACK_READY
→ user taps Review Resume
→ user requests edit
→ Resume Editor runs
→ user taps Apply Link
→ state = AWAITING_APPLICATION_CONFIRMATION
→ user says Done
→ state = APPLIED
→ follow-up scheduled
→ state = FOLLOWUP_DUE (day 5)
```

### Implementation

- `careerloop/memory/checkpointer.py` — `PostgresSaver` backed by Supabase using `thread_id` (phone number/email) for persistence flawless across async webhook hits.
- `careerloop/session/supervisor_graph.py` — LangGraph `StateGraph` maintaining `ConversationState` (`current_state`, `pending_job_id`, `user_id`).
- An Intent Router node classifies free-form messages against the current state.
- State transitions are deterministic. The Supervisor decides what happens next, routing to sub-graphs or wrapping legacy scripts (`scan.mjs`, `check-liveness.mjs`) as LangChain Tools.

**Canonical path:** `careerloop/session/`

**Current implementation status (2026-05-23):** first scaffold. The supervisor graph, tool wrappers, and checkpointer entry point exist, but routing logic is still placeholder-level. Before this can be treated as live, tests must prove:
- `UserEvent` → `ConversationState` mapping works
- `IDLE` + "scan"/"brief"/"apply" route to expected graph nodes
- `PACK_GENERATING` invokes the Council subgraph with a complete `council_state`
- interrupts pause and resume on a stable `thread_id`
- failed subprocess tools return safe user-facing errors

---

## 23. Agent Orchestration Layer (Addendum — 2026-05-22)

**Do not build one big agent.** Use a Parent-Child Subgraph Architecture (LangGraph Supervisor) + small focused agents.

### The 7 Agents

| Agent | Responsibility |
|-------|---------------|
| **Router Agent** | Classifies user intent: apply, skip, review, edit, follow-up, interview, mark-applied |
| **Job Decision Agent** | Explains why a job is/isn't recommended; handles MAYBE |
| **Application Pack Agent** | Runs Company Intel + Council subgraph + document assembly |
| **Resume Edit Agent** | Surgical single-section edits without full Council rerun |
| **Follow-Up Agent** | Schedules, drafts, and delivers follow-up messages |
| **Interview Agent** | Prepares role-specific briefings; debriefs post-interview |
| **Memory Agent** | Retrieves relevant context from past applications, rejections, and conversations |

### Orchestration Principle

> The state machine decides what should happen. Agents only complete specific tasks.

Never chain agents autonomously. Every agent handoff goes through the LangGraph Supervisor. The Supervisor routes to execution sub-graphs (e.g., the existing linear Resume Council graph converted into a callable Subgraph) or implements Human-in-the-Loop (HITL) checkpoints using `interrupt()`. This keeps the system predictable, debuggable, and safe to hand to a non-technical user.

### Assisted Apply Safety Rule

The execution layer is allowed to reduce form-filling friction, not remove judgment. The only compliant path is:

```
Pack generated
→ user reviews resume, cover note, recruiter DM, screening answers
→ user explicitly approves one job
→ bridge fills the ATS form
→ final submit occurs only within that approved job context
→ ledger records the application
```

The bridge must never scan a queue and submit applications while the user is absent. "Apply while I sleep" is interpreted as "execute an already reviewed, explicitly approved job asynchronously," not as autonomous job selection or bulk submission.

**Canonical path:** `careerloop/session/supervisor_graph.py`

---

## 24. Application Pack Definition (Addendum — 2026-05-22)

An application pack is the complete bundle generated for one user × one job. It is assembled once, stored, and delivered in pieces as needed.

### Pack Contents (11 items)

| # | Item | Source |
|---|------|--------|
| 1 | Final resume PDF | Resume Council → renderer |
| 2 | Final resume markdown | Resume Council |
| 3 | Company intelligence summary | Company Intel (S3) |
| 4 | Positioning summary | Positioning Engine (S6) |
| 5 | Recruiter DM | Council application pack |
| 6 | Cover note | Council application pack |
| 7 | Screening answers | Council application pack |
| 8 | Follow-up message | Follow-Up Agent |
| 9 | Apply link | Ledger (source_url) |
| 10 | Risks / user review notes | Truth Guard + positioning |
| 11 | Ledger state | Application state engine |

### User-Facing UX (WhatsApp/Telegram)

The user sees a minimal summary, not all 11 items:

```
Application pack ready for Stripe.
✅ Resume: ready
✅ Cover note: ready
✅ Recruiter DM: ready
🔗 Apply link: ready

Reply: review resume | apply now | edit | skip
```

The full pack stays in storage. Items are surfaced on demand.

**Canonical path:** `output/packs/{user_id}/{job_id}/`

---

## 25. Resume Editing Layer (Addendum — 2026-05-22)

Rerunning the full 8-system Council for every small edit is expensive and slow. A lightweight Resume Editor handles surgical changes without touching the pipeline.

### Edit Types

- Tone edit (less aggressive / more conservative)
- Section edit (rewrite one section)
- Bullet edit (change one bullet)
- Remove claim
- Make stronger / Make safer
- Shorten to one page
- Reframe for different role family

### Flow

```
User: "Make the profile less founder-heavy"
→ identify affected section
→ edit only that section (single LLM call)
→ validate claims (Truth Guard mini-check)
→ re-render PDF
→ show before/after diff
→ user confirms or reverts
```

### Guardrails

- Never edit unrelated sections
- Never break markdown structure
- Never remove existing links
- Never add unsupported skills
- Always produce a diff before confirming

**Canonical path:** `careerloop/resume_editor/`

---

## 26. ATS Validator Layer (Addendum — 2026-05-22)

Every generated resume gets a fast ATS health check before delivery. Not a compliance audit — a practical signal to the user.

### MVP ATS Checks

| Check | Pass Condition |
|-------|---------------|
| Text selectable in PDF | pdfminer can extract text |
| Links preserved | All hyperlinks survive PDF render |
| No images as text | No rasterized text blocks |
| Standard section headings | Experience, Education, Skills present |
| Keyword coverage | ≥60% of JD must-haves appear |
| No tables in ATS template | classic-ats.html is table-free |
| No multi-column layout in ATS template | Single-column confirmed |
| Clean file name | No spaces, no special chars |
| Page count | ≤2 pages for most roles |
| Missing must-have keywords | Flagged individually |

### Output to User

```
ATS Health: 86/100
✅ Selectable text
✅ Standard sections
✅ Keyword coverage strong
⚠️  Kubernetes in JD but not in resume
⚠️  Resume is 2 pages
```

**Canonical path:** `careerloop/ats_validator.py`

---

## 27. Persistent Memory Architecture (Addendum — 2026-05-22)

CareerLoop needs 5 distinct memory scopes. Use structured DB first. Use embeddings only for fuzzy retrieval.

### The 5 Memory Scopes

**A. User Memory** — who the user is
```
user_id, name, phone/telegram_id, email
resume_path, profile_path, career_mode
salary_floor, notice_period, locations
target_roles, avoid_list
```

**B. Job Memory** — each discovered job
```
job_id, company, title, location
source_url, apply_url, JD
fit_score, status, discovered_at
company_intelligence_id
```

**C. Application Memory** — one user × one job
```
application_id, user_id, job_id
status, pack_id, resume_used
applied_at, followup_due_at
recruiter_contact, notes, outcome
```

**D. Interview Memory** — interview events
```
interview_id, application_id
company, round, scheduled_time
questions_asked, user_vent
system_summary, weaknesses, strengths
next_prep_plan, outcome
```

**E. Communication Memory** — conversations and reminders
```
message_id, user_id, channel
intent, state_before, state_after
timestamp, raw_text, parsed_action
```

### Storage Strategy

| Layer | MVP | Production |
|-------|-----|-----------|
| Structured data | SQLite + JSON artifacts | Postgres |
| Fuzzy retrieval (vents, convos, resume bullets) | Local file + string match | pgvector embeddings |
| File storage | Local filesystem | Object storage (S3/GCS) |

### MVP Tables

`users` · `profiles` · `jobs` · `applications` · `application_packs` · `followups` · `interviews` · `messages` · `documents` · `calendar_events` · `gmail_events` · `memory_chunks`

**Canonical path:** `careerloop/memory/`
