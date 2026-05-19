# CareerLoop — Company Intelligence Engine

## Vision Document v1

**Date:** 2026-05-18  
**Status:** Product Vision — guiding architecture, not implementation spec  
**Implementation spec:** [company-intel-design.md](../engineering/specs/company-intel-design.md)

---

## 0. The Core Insight

People think hiring is:

```
resume ↔ job description
```

It isn't. Hiring is:

```
candidate psychology
↔ company psychology
↔ business needs
↔ organizational timing
↔ communication alignment
```

Most career tools optimize for: **documents** (ATS keywords, formatting, generic AI rewrites).

CareerLoop optimizes for: **strategic alignment** — understanding what a company values, how it operates, what it's trying to become, and how a candidate should position themselves within that context.

---

## 1. Product Philosophy

### Hiring is contextual

A strong candidate can fail because of:
- Wrong positioning
- Wrong tone
- Wrong emphasis
- Wrong company fit
- Wrong timing

The system optimizes: **alignment**, NOT keyword density.

### Honesty over inflation

CareerLoop should NEVER hallucinate fit. If gaps exist:
- Acknowledge them
- Reposition strengths
- Identify transferable value

The system optimizes: **truthful positioning**, NOT resume inflation.

---

## 2. What CareerLoop Must Answer

```
What kind of company is this REALLY?
What problems are they trying to solve?
What kind of people succeed there?
What language resonates with them?
What does this role actually require?
How should THIS candidate position themselves?
Should this candidate even apply?
```

This requires:

| Layer | Purpose |
|-------|---------|
| **Organizational Intelligence** | How the company thinks, decides, executes |
| **Business Intelligence** | Revenue model, growth drivers, constraints |
| **Cultural Intelligence** | Values, communication style, founder psychology |
| **Role Intelligence** | Real requirements, hidden expectations, failure modes |
| **Positioning Intelligence** | Strategic angle, language, emphasis for this candidate |

---

## 3. MECE Breakdown

### 3.1 Company Identity Intelligence

Understand the company's personality:

| Dimension | What to research | Sources |
|-----------|-----------------|---------|
| Brand personality | How they present themselves publicly | Website, social, design language |
| Founder psychology | Founder background, communication style | Interviews, blog posts, Twitter |
| Decision-making culture | Consensus vs top-down, speed vs deliberation | Glassdoor, employee reviews |
| Risk tolerance | Startup velocity vs enterprise caution | Funding stage, hiring patterns |

### 3.2 Business Intelligence

Understand the economic reality:

| Dimension | Questions to answer |
|-----------|-------------------|
| Business model | How do they make money? B2B/B2C? Recurring/transactional? |
| Revenue drivers | What actually generates revenue? |
| Growth constraints | What's limiting them right now? |
| Strategic priorities | What are they optimizing for this year? |
| Competitive position | Who are they competing with? What's their wedge? |

### 3.3 Organizational Intelligence

Understand the operating system:

| Dimension | Questions |
|-----------|----------|
| Org maturity | How structured are teams? How defined are processes? |
| Engineering maturity | CI/CD? Testing? Infrastructure? Code quality culture? |
| Cross-functional behavior | How do eng, product, design collaborate? |
| Founder involvement | Hands-on or hands-off? |
| Execution style | Ship fast and iterate, or plan thoroughly then execute? |

### 3.4 Role Intelligence

Understand what the job actually needs:

| Signal | Source |
|--------|--------|
| Explicit requirements | JD text |
| Hidden expectations | Read between JD lines, company context |
| Real success criteria | What does "great" look like in this role after 12 months? |
| Likely failure modes | What gets people fired or sidelined here? |
| Hiring psychology | Are they filling a gap, replacing someone, or creating a new role? |

### 3.5 People Intelligence

Understand who works there:

| Signal | Source |
|--------|--------|
| Leadership style | Founder/CEO interviews, Glassdoor |
| Hiring manager behavior | LinkedIn activity, public talks |
| Team structure | LinkedIn org chart, job postings |
| Communication patterns | Slack culture? Email-heavy? Async-first? |
| Prior hires | Who did they hire recently? What backgrounds? |

### 3.6 Technical Intelligence

Understand the technology landscape:

| Signal | Source |
|--------|--------|
| Likely stack | Job postings, engineering blog, GitHub |
| Data maturity | Do they have a data team? Analytics? ML? |
| AI maturity | Are they AI-native or AI-curious? |
| Workflow systems | What tools do they use? CRM, ERP, project mgmt? |
| Operational tooling | Monitoring, deployment, infrastructure |

---

## 4. Positioning Engine

The Positioning Engine is the core moat. It transforms:

```
candidate + company → strategic positioning
```

### Output

```json
{
  "positioning_angle": "AI-native product engineer who ships from zero to one",
  "projects_to_emphasize": ["Emote (0→1 product ownership)", "Omnex (enterprise AI workflow)"],
  "language_to_use": ["shipped", "built", "owned", "customer continuity"],
  "language_to_avoid": ["agentic", "multi-agent", "spearheaded", "leveraged"],
  "resume_strategy": "Lead with product ownership and customer-facing AI, soft-pedal infrastructure depth",
  "interview_strategy": "Prepare: D2C/e-commerce domain context, CEO-office communication style, design-thinking vocabulary",
  "outreach_strategy": "3-sentence DM referencing Nicobar's AI-native ambition and Emote's 0→1 journey",
  "risk_mitigations": ["No D2C experience → frame as consumer-product adjacent", "No retail domain → position as fast learner with manufacturing-to-consumer transfer"]
}
```

### Positioning adapts per company

The same candidate should position differently for:

| Company Type | Lead With | Soft-Pedal | Tone |
|-------------|-----------|------------|------|
| **YC startup** | Speed, ownership, shipping under ambiguity | Process, enterprise experience | Direct, bold |
| **Enterprise** | Reliability, stakeholder management, process maturity | Startup chaos tolerance | Measured, professional |
| **Nicobar (D2C, design-led)** | Product taste, systems thinking, customer continuity | Heavy manufacturing framing | Warm, design-aware |
| **AI research lab** | Technical depth, publications, novel architectures | Product metrics, business outcomes | Technical, precise |

---

## 5. Deep Research Architecture

CareerLoop's company intelligence should function as **recursive organizational research**:

### Step 1 — Planning
Break company research into sub-tasks: founders, business model, culture, tech maturity, operational signals, hiring signals, product signals.

### Step 2 — Retrieval
Search across: LinkedIn, websites, news, podcasts, Glassdoor, GitHub, employee profiles, hiring posts, social media.

### Step 3 — Entity Graphing
Build relationships:
```
Founder ↔ Company culture ↔ Hiring philosophy ↔ Role expectations ↔ Business priorities
```

### Step 4 — Gap Detection
System identifies missing knowledge:
```
Need more engineering maturity signals
Need more operational clues
Need more founder communication patterns
```
Then recursively researches further.

### Step 5 — Synthesis
Generate: company profile, strategic positioning, likely expectations, candidate fit analysis, communication guidance.

---

## 6. End-to-End Pipeline

```
Web / LinkedIn / JD / News / Glassdoor
        ↓
Company Intelligence Engine (structured extraction)
        ↓
Company Memory (SQLite, cached, TTL-aware)
        ↓
Candidate Intelligence (profile + preferences + history)
        ↓
Positioning Engine (strategic matching)
        ↓
Resume Council (8-system, deterministic assembly)
        ↓
Humanizer (4-phase anti-AI pipeline)
        ↓
Renderer (9 templates, structured data input)
        ↓
Application Pack (MD + HTML + PDF)
        ↓
Feedback Loop (interview outcomes, recruiter responses)
        ↓
Learning Engine (pattern analysis, positioning improvement)
```

---

## 7. The Real Moat

The moat is NOT:
- Prompts
- Resume formatting
- ATS optimization

The moat IS:
- **Structured organizational understanding** — knowing what companies actually value
- **Adaptive candidate positioning** — dynamically matching strengths to company context
- **Honest differentiation** — truthful positioning that stands out because it's real

---

## 8. Current Implementation Status

| Component | Status | Module |
|-----------|--------|--------|
| Company identity intelligence | ⚠️ LLM recall only | `graph.py:_S3_SYSTEM` |
| Business intelligence | ⚠️ LLM recall only | Same |
| Organizational intelligence | ❌ Not built | — |
| Role intelligence | ✅ Working | `graph.py:_S4_SYSTEM` (Role Decoder) |
| People intelligence | ❌ Not built | — |
| Technical intelligence | ⚠️ Partial (from JD) | Same as company intel |
| Company registry (static) | ✅ Built | `company_registry.py` |
| Company memory (cache) | ❌ Schema exists, not used | `memory/schema.sql` |
| Positioning engine | ⚠️ Partial | `graph.py:_S6_SYSTEM` (Positioning Strategy) |
| Learning loop | ❌ Not built | `analyze-patterns.mjs` (pre-requisite) |

---

## 9. Build Priority

| Priority | Component | Dependencies | Est. Effort |
|----------|-----------|-------------|-------------|
| **P0** | `company_intel.py` — structured intelligence engine | WebSearch, company_memory table | 3-5 days |
| **P1** | Positioning Engine v2 — company-type-aware adaptation | Company intel output | 2-3 days |
| **P2** | Entity graphing + recursive research | Company intel v1 | 5-7 days |
| **P3** | Learning loop — outcome tracking + positioning improvement | Application history | 5-7 days |
| **P4** | People intelligence + network analysis | LinkedIn API, public data | 7-10 days |

---

## 10. Success Metrics

### Candidate Metrics
- Interview conversion rate
- Recruiter response rate
- Application-to-interview ratio
- Offer rate
- Candidate satisfaction

### Intelligence Metrics
- Positioning quality (human review)
- Company understanding depth
- Tailoring differentiation (delta % from base resume)
- Hallucination rate (<1%)
- Role-fit accuracy

### System Metrics
- Research completeness (% of MECE dimensions covered)
- Structured extraction accuracy
- Cache hit rate (company_memory)
- Research latency (target: <15s cache miss, <3s cache hit)

---

## 11. North Star

CareerLoop is not trying to generate:

> *better resumes*

It is trying to generate:

> **better strategic alignment between humans and organizations.**

Every feature, every prompt, every module should serve that goal.

---

*Vision v1. Implementation begins with `company_intel.py` per `specs/company-intel-design.md`.*
