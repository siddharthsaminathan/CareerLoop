# CareerLoop — Technology Roadmap
## MECE / First Principles — May 22, 2026

> This is the single source of truth for what we're building and in what order.
> Status percentages pulled live from `docs/tech-backlog/TRACKER.md`.

---

## PHASE 1 — Market Discovery Engine
**Status: ~75% | Owner: CTO**

Build India-native job intelligence infrastructure.

| System | % | Status |
|--------|---|--------|
| India Fit Engine | 75% | ✅ |
| Search adapters (ATS, SpireAI, JobSpy) | 75% | ✅ |
| Deduplication | 75% | ✅ |
| ATS scraping (Greenhouse, Lever, Ashby) | 75% | ✅ |
| ScrapeGraphAI extraction | 75% | ✅ |
| Verification pipeline | 60% | 🟡 |
| Ledger system | 75% | ✅ |
| Daily shortlist generation | 55% | 🟡 |

**Remaining:** Better JS portal handling, direct company page indexing, search freshness tuning.

**Exit criteria:** System reliably produces high-quality India-fit opportunities daily.

---

## PHASE 1.5 — Decision Compression
**Status: ~20% | Owner: CEO (Hayagreev)**

Convert job overload into daily strategic clarity.

> See `docs/product/DECISION_COMPRESSION_VISION.md` for full spec.

| System | % | Status |
|--------|---|--------|
| Search Modes (Explore/Upgrade/Hunt/Emergency) | 10% | 🔴 |
| Aggression Slider | 0% | ⚫ |
| Track Clustering | 0% | ⚫ |
| Daily Triage Engine | 0% | ⚫ |
| Job Memory Cards | 0% | ⚫ |
| Morning Brief UX | 0% | ⚫ |
| Role-track grouping | 0% | ⚫ |

**Exit criteria:** Users consistently know "What should I do today?"

---

## PHASE 2 — Positioning + Application Intelligence
**Status: ~45% | Owner: CTO**

Generate believable, role-aware application strategy.

### 2A — Resume Council
**Status: ~92% 🟢**

| System | % | Status |
|--------|---|--------|
| CandidateGraph | 92% | ✅ |
| Section Rewrite (S7) | 92% | ✅ |
| Humanizer | 65% | 🟡 |
| Rendering pipeline | 85% | 🟡 |
| Template routing | 85% | ✅ |
| Truth Guard | 92% | ✅ |
| Humanizer calibration | 65% | 🟡 |
| Positioning refinement | 38% | 🟡 |

**Remaining:** Stronger positioning, less AI tone leakage, company-aware emphasis shifting.

### 2B — Positioning Engine
**Status: ~38%**

| System | % | Status |
|--------|---|--------|
| Narrative positioning | 38% | 🟡 |
| Company-aware emphasis | 38% | 🟡 |
| Risk-reduction layer | 0% | ⚫ |
| Recruiter psychology tuning | 0% | ⚫ |
| Startup vs enterprise tone | 0% | ⚫ |
| Role-family positioning | 0% | ⚫ |

**Exit criteria:** Same candidate can be strategically reframed for different hiring environments.

### 2C — Company Intelligence
**Status: ~75% 🟢**

| System | % | Status |
|--------|---|--------|
| LinkedIn scraping | 75% | ✅ |
| Glassdoor extraction | 75% | ✅ |
| DDG enrichment | 75% | ✅ |
| Company vectors (D1-D5) | 75% | ✅ |
| Hiring signal inference | 30% | 🟡 |
| Interview expectations | 10% | 🔴 |
| Team/recruiter inference | 0% | ⚫ |

**Remaining:** Direct career-page indexing, stronger risk analysis, hiring urgency scoring.

**Exit criteria:** User understands "Should I spend effort on this company?"

---

## PHASE 3 — Career Memory Infrastructure
**Status: ~10% | Owner: CTO**

Turn scattered applications into persistent career intelligence.

### 3A — Gmail Intelligence

| System | % | Status |
|--------|---|--------|
| Gmail connector | 0% | ⚫ |
| Application reconstruction | 0% | ⚫ |
| Rejection parsing | 0% | ⚫ |
| Recruiter memory | 0% | ⚫ |
| Interview extraction | 0% | ⚫ |
| Ghosting analysis | 0% | ⚫ |
| Offer tracking | 0% | ⚫ |

**Core Insight:** CareerLoop should remember where the user applied, who ghosted, where they failed, what patterns exist.

**Exit criteria:** User career history becomes queryable intelligence.

### 3B — Application State Engine

| System | % | Status |
|--------|---|--------|
| Universal application lifecycle | 15% | 🔴 |
| Follow-up scheduler | 25% | 🔴 |
| Recruiter contact memory | 0% | ⚫ |
| Timeline reconstruction | 0% | ⚫ |
| Offer state management | 0% | ⚫ |

**States:** DISCOVERED → SHORTLISTED → PREPARED → APPLIED → FOLLOWUP_DUE → INTERVIEWING → REJECTED → OFFER → ACCEPTED

---

## PHASE 4 — Interview Intelligence
**Status: ~25% | Owner: Shared**

Convert interviews into learning systems.

### 4A — Interview Memory

| System | % | Status |
|--------|---|--------|
| Interview vent parsing | 25% | 🟡 |
| Question extraction | 25% | 🟡 |
| Weakness detection | 10% | 🔴 |
| Emotional-state inference | 0% | ⚫ |
| Story-bank memory | 25% | 🟡 |

**Exit criteria:** System learns recurring interview weaknesses.

### 4B — Dynamic Interview Prep

| System | % | Status |
|--------|---|--------|
| Personalized prep plans | 0% | ⚫ |
| Company-specific prep | 10% | 🔴 |
| Weak-area targeting | 0% | ⚫ |
| Mock simulations | 0% | ⚫ |
| Interview progression tracking | 0% | ⚫ |

**Exit criteria:** Prep becomes adaptive instead of generic.

---

## PHASE 5 — Execution Layer
**Status: ~5% | Owner: CTO**

Reduce application execution friction.

### 5A — Chrome Extension

| System | % | Status |
|--------|---|--------|
| Autofill | 0% | ⚫ |
| Application-pack injection | 0% | ⚫ |
| Smart answer suggestions | 0% | ⚫ |
| Resume auto-selection | 0% | ⚫ |
| Screening-question support | 0% | ⚫ |
| Application logging | 0% | ⚫ |

**IMPORTANT:** This is NOT blind auto-apply. This is assisted execution. User stays in control.

**Exit criteria:** User can apply 5–10x faster without losing control.

---

## PHASE 6 — Career State Graph
**Status: ~5% | Owner: CTO**

Build persistent career intelligence over time.

| Node Type | % | Status |
|-----------|-----|--------|
| Skills | 25% | 🟡 |
| Companies | 25% | 🟡 |
| Recruiters | 0% | ⚫ |
| Applications | 25% | 🟡 |
| Interview outcomes | 10% | 🔴 |
| Compensation | 0% | ⚫ |
| Emotional state | 0% | ⚫ |
| Career goals | 0% | ⚫ |

**Relationships:** Success patterns, failure patterns, salary progression, interview difficulty, company response behavior.

**Exit criteria:** CareerLoop understands the user's career trajectory over time.

---

## PHASE 7 — Adaptive Intelligence Layer
**Status: 0% | Owner: Future**

Continuously personalize the system.

| System | % | Status |
|--------|---|--------|
| Dynamic fit recalibration | 0% | ⚫ |
| Application outcome learning | 0% | ⚫ |
| User preference evolution | 0% | ⚫ |
| Interview adaptation | 0% | ⚫ |
| Personalized strategy generation | 0% | ⚫ |

**Example insights:** "You perform better in startup interviews than enterprise. Your recruiter reply rate increases with execution-heavy positioning. Avoid PM roles requiring SQL-heavy case rounds."

---

## PHASE 8 — Consumer Product Layer
**Status: ~20% | Owner: Shared**

Turn infrastructure into habit-forming UX.

| System | % | Status |
|--------|---|--------|
| Landing page | 20% | 🟡 |
| Waitlist funnel | 0% | ⚫ |
| User onboarding | 0% | ⚫ |
| WhatsApp conversational UX | 15% | 🔴 |
| Weekly reports | 0% | ⚫ |
| Daily rituals | 0% | ⚫ |
| Notifications | 0% | ⚫ |
| Progress systems | 0% | ⚫ |

**Exit criteria:** CareerLoop becomes a daily operational habit.

---

## WHAT NOT TO BUILD RIGHT NOW

- More orchestration rewrites
- More LLM councils
- More templates
- Full autonomous apply
- Heavy dashboards
- Enterprise admin systems
- Graph visualization UIs

---

## True Product Loop

```
Search → Compress → Position → Prepare → Execute → Track → Learn → Adapt
```

That is the real CareerLoop architecture.

---

## Current Overall Maturity: ~57-60%

| Phase | % | Owner |
|-------|---|-------|
| Phase 1: Discovery | 75% | CTO |
| Phase 1.5: Decision Compression | 20% | CEO |
| Phase 2: Positioning + Intelligence | 45% | CTO |
| Phase 3: Career Memory | 10% | CTO |
| Phase 4: Interview Intelligence | 25% | Shared |
| Phase 5: Execution | 5% | CTO |
| Phase 6: Career State Graph | 5% | CTO |
| Phase 7: Adaptive Intelligence | 0% | Future |
| Phase 8: Consumer Product | 20% | Shared |

---

*Synced with `docs/tech-backlog/TRACKER.md` and `docs/product/PRD.md` — May 22, 2026.*
