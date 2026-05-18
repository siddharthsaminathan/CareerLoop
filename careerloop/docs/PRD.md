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
| India-first discovery | 70% | 🟡 Active | Multi-source works; verification/lifecycle maturing |
| Verification & filtering | 60% | 🟡 Active | Search page rejection added; needs confidence layering |
| Opportunity scoring (14-dim) | 55% | 🟡 Active | Heuristic works; needs calibration + LLM hybrid |
| Decision compression / triage | 25% | 🔴 Gap | Triage UX not finalized |
| Career state system (modes) | 10% | 🔴 Gap | Conceptual only; not wired to pipeline |
| Company intelligence | 15% | 🔴 Gap | Research direction exists; not automated |
| Positioning engine | 5% | 🔴 Gap | Not properly implemented |
| Resume Council (v3) | 40% | 🟡 Active | Pipeline fixed; Truth Guard + Humanizer missing |
| Humanizer layer | 10% | 🔴 Gap | Distributed across stages; no dedicated pass |
| Application execution | 5% | 🔴 Gap | Concept only |
| Chrome extension | 0% | ⚫ Not started | — |
| Follow-up system | 10% | 🔴 Gap | Basic concepts only |
| Interview memory | 0% | ⚫ Not started | — |
| Persistent memory graph | 10% | 🔴 Gap | SQLite schema exists; retrieval thin |
| WhatsApp/transport UX | 20% | 🔴 Gap | Transport concept exists; UX not mature |
| Monetization logic | 30% | 🟡 Active | Strategic understanding solid; pricing not built |

**Overall product maturity: ~20–25% of vision.**

> Legend: 🟢 Done · 🟡 Active · 🔴 Gap · ⚫ Not started
