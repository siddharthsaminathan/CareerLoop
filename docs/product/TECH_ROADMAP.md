# CareerLoop — Technology Roadmap
## MECE / First Principles — May 22, 2026

> This is the single source of truth for what we're building and in what order.
> Status percentages pulled live from `docs/tech-backlog/TRACKER.md`.

---

## PHASE 1 — Application Action Engine (The Paid Wedge)
**Status: ~18% | Owner: CTO**

Turn approved job openings into tailored, ready-to-execute application bundles and outreach targets.

| System | % | Status |
|--------|---|--------|
| Application Route Classifier (A/B/C/D) | 0% | ⚫ |
| Pack Assembly (Resume, Cover, DMs) | 30% | 🟡 |
| Recruiter Discovery & Outreach Draft | 0% | ⚫ |
| Referral Network Mapper & Draft | 0% | ⚫ |
| Status Tracking (Applied/Contacted/Replied) | 15% | 🔴 |

**Exit criteria:** For any job, the system hands the user a completely prepared pack and tells them exactly who to message.

---

## PHASE 1.5 — Momentum Dashboard & Intelligence
**Status: ~5% | Owner: CEO**

Visualize and improve the user's weekly conversation pipeline (not just job scans).

| System | % | Status |
|--------|---|--------|
| Daily Action Brief (Jobs to Apply) | 5% | 🔴 |
| Weekly Momentum Dashboard | 0% | ⚫ |
| Outreach Follow-up Scheduler | 25% | 🔴 |
| Conversion Analytics (App -> Reply) | 0% | ⚫ |
| Strategy Correction Loop | 0% | ⚫ |

**Exit criteria:** Users immediately see if they are getting closer to an interview this week.

---

## PHASE 2 — Market Discovery (Top of Funnel Hook)
**Status: ~75% | Owner: CTO**

Build the free lead magnet: India-native job intelligence infrastructure.

| System | % | Status |
|--------|---|--------|
| India Fit Engine | 75% | ✅ |
| Search adapters (ATS, SpireAI, JobSpy) | 75% | ✅ |
| Deduplication | 75% | ✅ |
| ATS scraping (Greenhouse, Lever, Ashby) | 75% | ✅ |
| ScrapeGraphAI extraction | 75% | ✅ |
| Verification pipeline | 60% | 🟡 |

**Exit criteria:** System reliably produces high-quality India-fit opportunities to feed into the paid Action Engine.

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

## PHASE 3 — Resume Council & Positioning Engine
**Status: ~80% | Owner: CTO**

Generate believable, role-aware application assets (feeds into the Action Engine).

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
**Status: ~8% | Owner: CTO**

Reduce application execution friction.

### 5A — Assisted Apply Bridge

| System | % | Status |
|--------|---|--------|
| Kimi/Hermes bridge scaffold | 5% | ⚫ |
| Autofill / form mapping | 0% | ⚫ |
| Application-pack injection | 5% | ⚫ |
| Smart answer suggestions | 0% | ⚫ |
| Resume auto-selection | 0% | ⚫ |
| Screening-question support | 0% | ⚫ |
| Application logging | 0% | ⚫ |
| Chrome extension fallback | 0% | ⚫ |

**IMPORTANT:** This is NOT blind auto-apply. This is assisted execution. User stays in control. The only allowed execution path is one reviewed pack + one explicit approval + one job. No unattended queue, no bulk submit, no autonomous job selection.

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

- More Resume Council polish (93% is enough — ship it)
- More resume templates (10 is enough)
- More LLM orchestration rewrites
- Full autonomous apply (user stays in control always; assisted apply requires explicit per-job approval)
- Heavy dashboards
- Enterprise admin systems
- Graph visualization UIs
- Chrome extension (Phase 5 fallback; Kimi/Hermes bridge is the current assisted-apply experiment)
- Gmail Memory (Phase 3, needs transport first)

---

## True Product Loop

```
Search → Compress → Position → Prepare → Execute → Track → Learn → Adapt
```

That is the real CareerLoop architecture.

---

## PHASE 0 — Delivery Foundation (The Missing Layer)
**Status: ~12% | Owner: CTO | Priority: P0 — blocks everything**

> Added 2026-05-22. Updated 2026-05-23 after first scaffolds.
> The entire backend exists, and the delivery layer now has initial files, but no verified end-to-end user loop. This phase must ship before any other feature investment.

The MVP operating loop:

```
User onboarded
→ daily jobs discovered
→ top jobs compressed
→ user approves jobs
→ application pack generated
→ user reviews pack
→ user applies via link
→ ledger updates
→ follow-ups scheduled
→ interviews detected
→ prep/debrief stored
→ career memory improves
```

The product becomes real only when this loop works end-to-end for one user.

### Sprint 0 — Transport Foundation
**Goal:** Send and receive messages with one test user.

| Build | File |
|-------|------|
| Transport abstraction | `careerloop/transport/base.py` |
| Telegram adapter | `careerloop/transport/telegram.py` |
| Terminal adapter | `careerloop/transport/terminal_chat.py` |
| LangGraph supervisor | `careerloop/session/supervisor_graph.py` |
| Postgres checkpointer | `careerloop/memory/checkpointer.py` |
| Session store fallback | `careerloop/session/session_store.py` |
| User registry | `careerloop/session/user_registry.py` |

**Success criteria:**
- User sends "hi" → CareerLoop replies
- User sends "brief" → CareerLoop sends mock daily brief
- User taps Apply → state changes to `AWAITING_JOB_DECISION`
- `UserEvent` maps into `ConversationState` without type mismatch
- `thread_id` persists state through one interrupt/resume cycle

---

### Sprint 1 — Multi-User Onboarding
**Goal:** A fourth user can onboard without code changes.

| Build | File |
|-------|------|
| Onboarding flow | `careerloop/onboarding/onboarding_flow.py` |
| CV upload handler | `careerloop/onboarding/document_upload_handler.py` |
| Profile questionnaire (5 questions) | `careerloop/onboarding/profile_questionnaire.py` |
| Person config generator | `careerloop/onboarding/person_config_generator.py` |

**5 onboarding questions:** role targets, location, salary floor, notice period, career mode (Hunt/Upgrade/Explore/Emergency)

**Success criteria:**
- New WhatsApp/Telegram user sends start → uploads CV → answers 5 questions → profile created → mock brief received
- No code changes required for new user

---

### Sprint 2 — Daily Brief Delivery
**Goal:** 7 AM IST daily brief reaches users automatically.

| Build | File |
|-------|------|
| Daily brief scheduler | `careerloop/jobs/daily_brief_job.py` |
| Scheduler cron | `careerloop/jobs/scheduler.py` |
| Brief delivery adapter | `careerloop/jobs/brief_delivery.py` |
| Decision router | `careerloop/session/decision_router.py` |

**Success criteria:**
- Cron fires at 7 AM IST per user
- `DailyRunner.run()` → `daily_brief()` → `send_text()`
- User replies 1/2/skip → session state updates correctly

---

### Sprint 3 — Application Pack Delivery
**Goal:** User approves a job → receives tailored resume PDF on Telegram.

| Build | File |
|-------|------|
| Pack orchestrator | `careerloop/packs/pack_orchestrator.py` |
| Pack storage | `careerloop/packs/pack_storage.py` |
| Pack delivery | `careerloop/packs/pack_delivery.py` |
| PDF selector | `careerloop/packs/pdf_selector.py` |

**Flow:**
```
User approves job
→ pack_orchestrator triggers Council run
→ PDF selected (classic-ats for ATS, product-engineer for PM)
→ send_document(pdf) + summary text
→ user reviews
→ user opens apply link or approves assisted form-fill
→ state = AWAITING_APPLICATION_CONFIRMATION
```

**Success criteria:**
- User receives correct PDF on Telegram within 3 minutes of approval
- Pack stored in `output/packs/{user_id}/{job_id}/`

---

### Sprint 4 — Resume Editor + ATS Validator
**Goal:** User can request small edits without full Council rerun.

| Build | File |
|-------|------|
| Resume editor | `careerloop/resume_editor/editor.py` |
| Section locator | `careerloop/resume_editor/section_locator.py` |
| Resume diff | `careerloop/resume_editor/resume_diff.py` |
| ATS validator | `careerloop/ats_validator.py` |

**Success criteria:**
- User says "make profile less founder-heavy" → only profile section rewrites → before/after diff shown → PDF regenerated
- ATS Health score shown with every pack delivery

---

### Sprint 5 — Follow-Up Engine
**Goal:** Every applied job generates automatic follow-up drafts.

| Build | File |
|-------|------|
| Follow-up scheduler | `careerloop/followup/followup_scheduler.py` |
| Follow-up drafter | `careerloop/followup/followup_drafter.py` |
| Follow-up delivery | `careerloop/followup/followup_delivery.py` |

**Schedule:** Day 5 → Day 10 → Day 17 → Day 25 → mark likely ghosted.
**Adapt based on:** company type, recruiter reply, interview stage, career mode.

**Success criteria:**
- User marks applied → 4 follow-up dates auto-scheduled
- On day 5: message sent with drafted follow-up
- User can send/edit/skip each follow-up

---

### Sprint 6 — Gmail + Calendar Integration
**Goal:** CareerLoop knows about the user's existing applications and interviews.

| Build | File |
|-------|------|
| Gmail connector | `careerloop/integrations/gmail_connector.py` |
| Calendar connector | `careerloop/integrations/calendar_connector.py` |
| Email classifier | `careerloop/integrations/email_classifier.py` |
| Calendar event classifier | `careerloop/integrations/calendar_event_classifier.py` |

**Gmail classify:** application confirmation · rejection · recruiter reply · interview invite · assessment invite · offer · ghosted thread

**Calendar classify:** interview · recruiter call · assessment deadline · follow-up reminder · offer discussion

**Success criteria:**
- "You have an interview with Razorpay tomorrow" triggered by calendar
- Rejection email → application marked REJECTED in ledger automatically

---

### Sprint 7 — Interview Memory
**Goal:** Every interview becomes structured learning.

| Build | File |
|-------|------|
| Interview memory | `careerloop/interview/interview_memory.py` |
| Post-interview debrief | `careerloop/interview/interview_debrief.py` |
| Interview prep generator | `careerloop/interview/interview_prep.py` |
| Weakness tracker | `careerloop/interview/weakness_tracker.py` |

**Flow:**
- User vents after interview → extract questions asked, weak areas, recruiter signals → update profile → next prep improves
- System learns: "You perform better at startups than enterprise." "Avoid SQL-heavy case rounds."

---

## 7-Day Build Plan (Sprint 0 + Sprint 1 start)

| Day | Task | Success Signal |
|-----|------|---------------|
| Day 1 | Telegram bot + transport abstraction + session store | "hi" → reply works |
| Day 2 | User registry + CV upload → profile creation | 4th user onboards without code change |
| Day 3 | Session state machine + mock daily brief routing | User gets brief, taps apply, state changes |
| Day 4 | Connect real DailyRunner output to brief delivery | Real jobs in the brief |
| Day 5 | Apply button triggers Council run → pack generated | Pack stored in output/packs/ |
| Day 6 | Send PDF + apply link + mark applied flow | User receives PDF on Telegram |
| Day 7 | Follow-up scheduling + first live beta user | One real end-to-end loop |

---

## 30-Day Build Plan

| Week | Focus | Output |
|------|-------|--------|
| Week 1 | Sprints 0–1: Telegram MVP + onboarding | First real user, end-to-end loop working |
| Week 2 | Sprint 2–3: Daily brief delivery + pack generation | Daily habit established for beta users |
| Week 3 | Sprint 4–5: Resume editor + ATS check + follow-ups | Quality control + pipeline management |
| Week 4 | Sprint 6: Gmail/calendar + Sprint 7 start: interview memory | CareerLoop learns from user history |

**End state at 30 days:** CareerLoop can onboard users, send daily briefs, generate tailored packs, track applications, schedule follow-ups, and learn from interviews. That is a real product.

---

## Background Job Architecture

Two classes of background work:

**Daily (per user, every morning):**
- Discover jobs
- Dedupe + score
- Compress decisions
- Prepare daily brief
- Update follow-ups
- Read Gmail
- Read calendar
- Detect stale applications

**Per-job (only when user approves):**
- Run Company Intelligence
- Run Application Pack
- Prepare recruiter DM + cover note + screening answers
- Render resume
- ATS validation

Do not run per-job tasks speculatively. Only run when user signals intent. This prevents wasting compute on jobs the user will skip.

---

## Final Architecture Stack

```
Transport Layer (Telegram / WhatsApp)
  └── TransportAdapter → UserEvent → ConversationState
      └── LangGraph Supervisor + PostgresSaver
      └── User Registry + Onboarding
          ├── Daily Brief Engine
          │   └── DailyRunner → Discovery → Scoring → Compression
          ├── Application Pack Orchestrator
          │   └── Company Intel → Council → Render → ATS Check → Deliver
          ├── Resume Editor (surgical, no full rerun)
          ├── Assisted Apply Bridge (explicit approval only)
          ├── Follow-Up Engine
          ├── Gmail + Calendar Connectors
          ├── Interview Memory
          └── Career State Graph
                └── Adaptive Intelligence (Phase 7)
```

---

## Current Overall Maturity: ~59-62%

> Updated 2026-05-23. Phase 0 has scaffolds; contract correctness and E2E verification are the new P0.

| Phase | % | Owner | Status |
|-------|---|-------|--------|
| Phase 0: Delivery Foundation | 12% | CTO | 🔴 P0 |
| Phase 1: Discovery | 75% | CTO | 🟡 |
| Phase 1.5: Decision Compression | 20% | CEO | 🔴 |
| Phase 2: Positioning + Intelligence | 45% | CTO | 🟡 |
| Phase 3: Career Memory | 10% | CTO | 🔴 |
| Phase 4: Interview Intelligence | 25% | Shared | 🟡 |
| Phase 5: Execution (assisted apply) | 8% | CTO | ⚫ |
| Phase 6: Career State Graph | 5% | CTO | ⚫ |
| Phase 7: Adaptive Intelligence | 0% | Future | ⚫ |
| Phase 8: Consumer Product (UX) | 20% | Shared | 🔴 |

---

*Synced with `docs/tech-backlog/TRACKER.md` and `docs/product/PRD.md` — May 23, 2026.*
