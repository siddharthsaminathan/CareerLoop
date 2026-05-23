# CareerLoop — MVP Sprint Plan
## Delivery Foundation: Phase 0

> **Author:** Product Engineering Lead
> **Date:** 2026-05-23
> **Status:** Active — this is the current engineering mandate
> **Source:** CEO/CTO product session handoff

---

## The Problem This Solves

CareerLoop has:
- 93% Resume Council
- 75% Discovery engine
- 75% Company Intelligence
- 10 HTML/PDF templates
- WhatsApp message formatters (strings only)

CareerLoop does NOT have:
- Any mechanism to reach a user
- Multi-user onboarding
- A conversation state machine
- PDF delivery to users
- A daily brief cron

**A user cannot interact with CareerLoop today.** This sprint plan fixes that.

---

## Core Operating Loop (the target)

```
User onboarded
→ daily jobs discovered
→ top 5 compressed
→ user approves job
→ application pack generated
→ user reviews PDF
→ user applies via link
→ ledger updated
→ follow-ups scheduled
→ interviews detected
→ debrief stored
→ career memory improves
```

The product becomes real only when this loop works end-to-end for one user.

---

## Transport Decision

**Telegram-first for internal beta. Meta WhatsApp Cloud API for production.**

Never use WhatsApp Web unofficial harness (session breaks, account risk, not production-safe).

### Transport Abstraction (non-negotiable — build this first)

```
careerloop/transport/
├── base.py                 TransportAdapter (abstract)
│   ├── parse_payload(payload) → UserEvent
│   ├── map UserEvent → ConversationState
│   ├── send_text(user_id, text)
│   ├── send_buttons(user_id, text, buttons[])
│   └── send_document(user_id, file_path, caption)
├── telegram.py             TelegramAdapter
├── terminal_chat.py        Local smoke-test adapter
└── whatsapp_meta.py        MetaWhatsAppAdapter (later)
```

Product logic never imports from `telegram.py`, `terminal_chat.py`, or `whatsapp_meta.py` directly. Always through `TransportAdapter` into the LangGraph Supervisor. This means swapping from Telegram to WhatsApp touches zero business logic files.

---

## Sprint 0 — Transport Foundation
**Duration:** 1–2 days
**Goal:** Send and receive one message with one test user.

### Files to Build

| File | Responsibility |
|------|---------------|
| `careerloop/transport/base.py` | Abstract TransportAdapter interface |
| `careerloop/transport/telegram.py` | Telegram Bot API implementation |
| `careerloop/transport/terminal_chat.py` | Local CLI smoke-test adapter |
| `careerloop/session/supervisor_graph.py` | LangGraph Supervisor, intent router, HITL checkpoints |
| `careerloop/memory/checkpointer.py` | `PostgresSaver` wrapper for persistent graph state |
| `careerloop/session/session_store.py` | Per-user state: `{user_id, state, current_job_id, updated_at}` |
| `careerloop/session/message_router.py` | Legacy fallback; do not expand unless needed |
| `careerloop/session/user_registry.py` | Maps `telegram_id / whatsapp_number → person_id → cv_path` |

### Conversation State Machine

```python
class UserState(Enum):
    IDLE = "IDLE"
    ONBOARDING_WAITING_CV = "ONBOARDING_WAITING_CV"
    ONBOARDING_PROFILE_QUESTIONS = "ONBOARDING_PROFILE_QUESTIONS"
    DAILY_BRIEF_SENT = "DAILY_BRIEF_SENT"
    REVIEWING_JOB = "REVIEWING_JOB"
    AWAITING_JOB_DECISION = "AWAITING_JOB_DECISION"
    PACK_GENERATING = "PACK_GENERATING"
    PACK_READY = "PACK_READY"
    AWAITING_RESUME_REVIEW = "AWAITING_RESUME_REVIEW"
    AWAITING_APPLICATION_CONFIRMATION = "AWAITING_APPLICATION_CONFIRMATION"
    APPLIED = "APPLIED"
    FOLLOWUP_DUE = "FOLLOWUP_DUE"
    INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED"
    INTERVIEW_PREP_READY = "INTERVIEW_PREP_READY"
    POST_INTERVIEW_DEBRIEF = "POST_INTERVIEW_DEBRIEF"
```

### Success Criteria

- [ ] User sends "hi" → bot replies
- [ ] User sends "brief" → bot sends mock daily brief text
- [ ] User taps "Apply" button → state changes to `AWAITING_JOB_DECISION`
- [ ] User sends "skip" → state returns to `DAILY_BRIEF_SENT`

---

## Sprint 1 — Multi-User Onboarding
**Duration:** 2 days
**Goal:** A 4th user can onboard without any code changes.

### Files to Build

| File | Responsibility |
|------|---------------|
| `careerloop/onboarding/onboarding_flow.py` | State machine for new user setup |
| `careerloop/onboarding/document_upload_handler.py` | Receives PDF/DOCX → `document_extractor.py` |
| `careerloop/onboarding/profile_questionnaire.py` | 5-question conversation → profile dict |
| `careerloop/onboarding/person_config_generator.py` | Creates PERSON_CONFIG + profile.yml from answers |

### Onboarding Flow

```
User sends "start"
→ "Welcome. Please send your CV (PDF or Word)."
→ User uploads file
→ document_extractor.py parses CV
→ "Got it. 5 quick questions:"
  Q1: "What roles are you targeting? (e.g. Product Manager, Data Analyst)"
  Q2: "Which cities work for you?"
  Q3: "What's your salary floor? (e.g. 15 LPA)"
  Q4: "What's your notice period?"
  Q5: "How active is your search? (1=Exploring / 2=Actively looking / 3=Urgent)"
→ profile.yml created
→ PERSON_CONFIG entry created
→ "Done. I'll send your first daily brief tomorrow at 7 AM."
```

### 5 Profile Questions Map

| Question | Maps to |
|----------|---------|
| Target roles | `target_roles[]` |
| Cities | `locations[]` |
| Salary floor | `salary_floor_lpa` |
| Notice period | `notice_period_days` |
| Career mode | `career_mode` (Explore/Hunt/Upgrade/Emergency) |

### Success Criteria

- [ ] New Telegram user completes onboarding flow
- [ ] `user_registry.json` has the new user
- [ ] `profiles/{user_id}/profile.yml` created from questionnaire
- [ ] No code change required for any new user

---

## Sprint 2 — Daily Brief Delivery
**Duration:** 1 day (requires Sprint 0 complete)
**Goal:** 7 AM IST brief arrives automatically for every registered user.

### Files to Build

| File | Responsibility |
|------|---------------|
| `careerloop/jobs/daily_brief_job.py` | Runs DailyRunner per user, formats brief |
| `careerloop/jobs/scheduler.py` | Cron-style per-user job scheduler (APScheduler or cron) |
| `careerloop/jobs/brief_delivery.py` | Sends formatted brief via TransportAdapter |
| `careerloop/session/decision_router.py` | Routes user replies ("1"/"apply"/"skip") to handlers |

### Daily Brief Flow

```
06:00 AM — Gmail scan (if connected)
06:30 AM — DailyRunner.run() per user
06:45 AM — whatsapp_ux.daily_brief() called
07:00 AM — brief_delivery.send() via TelegramAdapter
07:xx AM — user replies
           "1" or "apply" → state = REVIEWING_JOB, send job_review_card()
           "2" or "all"   → show all jobs in sequence
           "skip"         → state = IDLE
```

### Success Criteria

- [ ] Brief fires at 7 AM for each registered user
- [ ] User reply "1" shows job card for top job
- [ ] User reply "skip" suppresses brief
- [ ] Follow-ups appended to brief when due

---

## Sprint 3 — Application Pack Delivery
**Duration:** 2 days
**Goal:** User approves job → receives tailored resume PDF on Telegram within 3 minutes.

### Files to Build

| File | Responsibility |
|------|---------------|
| `careerloop/packs/pack_orchestrator.py` | Triggers Council run, assembles pack |
| `careerloop/packs/pack_storage.py` | Saves pack to `output/packs/{user_id}/{job_id}/` |
| `careerloop/packs/pack_delivery.py` | Sends PDF + summary via TransportAdapter |
| `careerloop/packs/pdf_selector.py` | Picks best template for role type |

### Pack Delivery Flow

```
User says "apply" on a job card
→ state = PACK_GENERATING
→ send: "Generating your application pack for {Company}. Takes ~2 min."
→ pack_orchestrator.run(user_id, job_id)
    → Company Intel (S3)
    → Resume Council (S1–S8)
    → PDF render (10 templates)
    → pdf_selector picks best match
    → ATS validator runs
→ state = PACK_READY
→ send_document(best_pdf, caption="Your resume for {Company}")
→ send_text(pack_summary: resume ready, cover note ready, recruiter DM ready, apply link)
→ send_buttons: [Review resume] [Apply now] [Edit] [Skip]
```

### PDF Selection Logic

| Role type | Template |
|-----------|---------|
| ATS-heavy (finance, MNC) | `classic-ats` |
| PM / Product | `product-engineer` |
| Founder / Operator | `founder-operator` |
| Executive | `executive-clean` |
| Design / Brand | `design-brand-compact` |

### Success Criteria

- [ ] User receives PDF in Telegram within 3 minutes of tapping Apply
- [ ] Pack stored at `output/packs/{user_id}/{job_id}/`
- [ ] ATS Health score shown with pack
- [ ] User can tap "Apply now" to get direct apply URL

---

## Sprint 4 — Resume Editor + ATS Validator
**Duration:** 2 days

### Files to Build

| File | Responsibility |
|------|---------------|
| `careerloop/resume_editor/editor.py` | Surgical section-level edits |
| `careerloop/resume_editor/section_locator.py` | Identifies which section to edit |
| `careerloop/resume_editor/resume_diff.py` | Before/after diff for user review |
| `careerloop/ats_validator.py` | 10-check ATS health score |

### Edit Types Supported

| User says | Action |
|-----------|--------|
| "make profile less founder-heavy" | Rewrite profile section only |
| "shorten bullet 3 in Emote" | Edit specific bullet |
| "remove the TensorFlow claim" | Remove from skills |
| "make it one page" | Compression mode |
| "make it safer" | Remove aggressive claims |

### ATS Checks

1. Text selectable (pdfminer extraction succeeds)
2. Links preserved in PDF
3. Standard section headings (Experience, Education, Skills)
4. JD keyword coverage ≥ 60%
5. No tables in classic-ats template
6. Single-column layout confirmed
7. Clean filename (no spaces)
8. Page count ≤ 2
9. Missing must-have keywords listed
10. No images masking text

### Success Criteria

- [ ] User says "make it less aggressive" → only profile rewrites → diff shown → PDF regenerates
- [ ] Full Council rerun NOT triggered for single-section edits
- [ ] ATS score shown with every pack: "ATS Health: 86/100"

---

## Sprint 5 — Follow-Up Engine
**Duration:** 2 days

### Files to Build

| File | Responsibility |
|------|---------------|
| `careerloop/followup/followup_scheduler.py` | Creates follow-up calendar from applied_at |
| `careerloop/followup/followup_drafter.py` | LLM drafts contextual follow-up message |
| `careerloop/followup/followup_delivery.py` | Surfaces due follow-ups via transport |

### Follow-Up Schedule

```
Day 0:  applied
Day 5:  soft follow-up ("Following up on my application…")
Day 10: second follow-up (different angle)
Day 17: final follow-up
Day 25: mark likely ghosted
```

Adapt based on: company type, recruiter reply status, interview stage, career mode (Emergency = tighter cadence).

### User-Facing UX

```
3 follow-ups due today.

1. Stripe recruiter — applied 6 days ago
2. Razorpay HR — interview done, no update
3. CRED hiring manager — referral pending

Send drafts? Reply: send all | review each | skip
```

### Success Criteria

- [ ] User marks applied → 4 follow-up dates auto-created in ledger
- [ ] Day 5 message fires with drafted follow-up text
- [ ] User can edit or skip individual follow-ups
- [ ] Ghosted applications surface after day 25

---

## Sprint 6 — Gmail + Calendar Integration
**Duration:** 3 days

### Files to Build

| File | Responsibility |
|------|---------------|
| `careerloop/integrations/gmail_connector.py` | OAuth + email fetch |
| `careerloop/integrations/calendar_connector.py` | Google Calendar fetch |
| `careerloop/integrations/email_classifier.py` | Classify emails into 7 types |
| `careerloop/integrations/calendar_event_classifier.py` | Classify calendar events into 5 types |

### Gmail Classification (7 types)

```
application_confirmation → update ledger to APPLIED
rejection               → update ledger to REJECTED; surface for debrief
recruiter_reply         → surface in next brief; update recruiter_contact
interview_invite        → create INTERVIEW_SCHEDULED state; trigger prep
assessment_invite       → create task with deadline
offer                   → surface immediately with negotiation prompt
ghosted_thread          → flag after 25+ days silence
```

### Calendar Classification (5 types)

```
interview               → trigger INTERVIEW_PREP_READY state
recruiter_call          → surface company intel summary
assessment_deadline     → reminder 24h before
follow_up_reminder      → surface in daily brief
offer_discussion        → negotiation prep
```

### Success Criteria

- [ ] "You have an interview with Razorpay tomorrow at 3 PM" triggered by calendar event
- [ ] Rejection email → ledger auto-updated, debrief prompted
- [ ] Historical applications reconstructable from Gmail

---

## Sprint 7 — Interview Memory
**Duration:** 2 days

### Files to Build

| File | Responsibility |
|------|---------------|
| `careerloop/interview/interview_memory.py` | Stores interview events + outcomes |
| `careerloop/interview/interview_debrief.py` | Structures vent → actionable learnings |
| `careerloop/interview/interview_prep.py` | Generates company + role-specific prep |
| `careerloop/interview/weakness_tracker.py` | Identifies recurring failure patterns |

### Debrief Flow

```
Post-interview (state = POST_INTERVIEW_DEBRIEF):
→ "How did it go? What happened?"
→ User vents freely
→ interview_debrief.py extracts:
   - Questions asked
   - Weak areas ("couldn't answer SQL optimization question")
   - Recruiter signals ("seemed impressed by Emote metrics")
   - Outcome (passed / rejected / unknown)
→ profile updated: weakness_tracker += SQL optimization
→ Next prep: "You've struggled with SQL optimization in 2 rounds. Prep this."
```

### Success Criteria

- [ ] User vents post-interview → structured debrief stored
- [ ] Recurring weakness pattern detected after 2+ interviews
- [ ] Prep for interview 3 incorporates lessons from interviews 1 and 2

---

## Immediate Engineering Order

Stop touching Resume Council. Start here:

```
1. Stop touching Resume Council
2. Build TransportAdapter + TerminalChatAdapter
3. Build user_registry.py
4. Build LangGraph Supervisor state contract and tests
5. Send daily brief to one real user
6. Let user approve one job
7. Generate and send one PDF
8. Let user mark applied
9. Schedule follow-up
10. Repeat for 5 users
```

That is the product now.

---

## What Not to Build During These Sprints

| Do Not Build | Why |
|-------------|-----|
| More Council improvements | At 93% — diminishing returns |
| Additional resume templates | 10 is enough |
| Chrome extension | Phase 5 fallback; Kimi/Hermes assisted bridge is current experiment |
| Gmail Memory (Sprint 6) | Before Sprints 0-3 are done |
| Decision Compression dashboard | CEO owns |
| Full autonomous apply | User must control final submission; only explicit per-job assisted execution is allowed |
| Enterprise admin | No users to administer yet |

---

*Owner: CTO*
*Synced with: `docs/product/TECH_ROADMAP.md`, `docs/product/PRD.md §21–27`, `docs/tech-backlog/TRACKER.md`*
*Last updated: 2026-05-23*
