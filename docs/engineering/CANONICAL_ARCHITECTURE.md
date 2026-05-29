# CareerLoop — Canonical Architecture v1.0

**Status:** FINAL — all architecture decisions locked
**Date:** 2026-05-23
**Supersedes:** All prior architecture documents
**Based on:** PRD.md v1.0 + CAREERLOOP_REUSE_AUDIT.md + CAREERLOOP_COUNCIL_AUDIT.md

---

## 1. Single Source of Truth

### Jobs & Applications

**Source of truth:** `careerloop/application_ledger.py` → `careerloop/ledger.json`

Every system reads/writes through the ledger. No exceptions.

| File | Role | Status |
|------|------|--------|
| `careerloop/ledger.json` | Canonical store | ✅ LIVE |
| `data/pipeline.md` | Generated view (pending URLs) | ⚠️ Read-only, will be generated from ledger |
| `data/applications.md` | Generated view (tracker) | ⚠️ Read-only, will be generated from ledger |
| `data/follow-ups.md` | Generated view (follow-ups) | ⚠️ Read-only, will be generated from ledger |
| `data/scan-history.tsv` | Dedup log (flat) | ✅ Keep as-is (scanner dedup) |

### Company Intelligence

**Source of truth:** `careerloop/company_intel.py` → SQLite `company_memory` table

`modes/deep.md` is a fallback manual tool, not the engine.

### User Profile

**Source of truth:** `config/profile.yml` + `modes/_profile.md` + `cv.md`

These are the user-layer files (DATA_CONTRACT.md). Never auto-updated.

### Resume/CV Content

**Source of truth:** Resume Council → `application_pack`

No independent CV generator. Council owns all content generation. Renderer owns PDF output only.

---

## 2. System Ownership Map

### Owned by CareerLoop (built here, maintained here)

| System | File(s) | % Complete |
|--------|---------|------------|
| Discovery Engine | `careerloop/on_demand.py::OnDemandSearch` | 85% |
| India Fit Engine (14-dim) | `careerloop/india_fit_engine.py` | 55% |
| Verification | `careerloop/verification.py` | 60% |
| Apply Route | `careerloop/apply_route.py` | 60% |
| Application Ledger | `careerloop/application_ledger.py` | 70% |
| Profile Manager | `careerloop/profile_manager.py` | 50% |
| Resume Council | `careerloop/council/` (10 files) | 82% |
| Memory Layer | `careerloop/memory/` (4 files) | 10% |
| Delivery Orchestration | `careerloop/session/`, `careerloop/transport/` | 12% 🔴 SCAFFOLD — supervisor/transport exist, contract unverified |
| Assisted Apply Bridge | `careerloop/execution/kimi_bridge.py` | 5% ⚫ MOCK — no real Webbridge/Hermes execution yet |
| Company Intelligence | `careerloop/company_intel.py` | 75% ✅ LIVE — MECE D1-D5 vectors, LinkedIn PortalScraper, Glassdoor ScrapeGraph, DDG web enrichment |
| Humanizer | `careerloop/council/humanizer.py` | 65% ✅ LIVE — 5-phase pipeline, 29 regression tests, aggressive rewrite prompt |
| Product Lead Skill | `.claude/skills/careerloop-product-lead/` | 100% |

### Inherited from Career-Ops (kept, maintained here)

| System | File(s) | Relationship |
|--------|---------|-------------|
| ATS PDF Renderer | `generate-pdf.mjs` | Reused as-is — Council output renderer |
| LaTeX Renderer | `generate-latex.mjs` | Reused as-is — opt-in alternative renderer |
| ATS Scanner | `scan.mjs` | Reused as-is — ATS-hosted India job discovery |
| Portal Config | `portals.yml` | Kept as-is — scan target list |
| CV Template (HTML) | `templates/cv-template.html` | Kept as-is — render target for compiler |
| CV Template (LaTeX) | `templates/cv-template.tex` | Kept as-is — opt-in render target |
| Fonts | `fonts/` | Kept as-is — PDF rendering |
| States Taxonomy | `templates/states.yml` | Kept as reference — map to LEDGER_STATUSES |
| Pattern Analyzer | `analyze-patterns.mjs` | Kept — port to Python later |
| Follow-up Calculator | `followup-cadence.mjs` | Kept — logic subsumed by ledger's FOLLOW_UP_SCHEDULE |

### Wrapped (Career-Ops prompt modes, adapted to CareerLoop pipeline)

| Mode | File | CareerLoop Integration |
|------|------|----------------------|
| A-G Evaluation | `modes/oferta.md` | Deep evaluation layer (lazy, ≤10 jobs) |
| Multi-Offer Compare | `modes/ofertas.md` | Decision compression surface |
| LinkedIn Outreach | `modes/contacto.md` | Recruiter/referral message drafts |
| Live Apply Assistant | `modes/apply.md` | Future Chrome extension prototype |
| Interview Prep | `modes/interview-prep.md` | Post-Company-Intel prep, cached questions |
| Tracker Display | `modes/tracker.md` | Generated view over ledger |
| Follow-up Display | `modes/followup.md` | Generated view over ledger |

### Deprecated / Ignored

| Item | Reason | Replacement |
|------|--------|-------------|
| `scan.mjs` | Legacy ATS scanner, no SSE streaming, filesystem-only output | `OnDemandSearch` in `careerloop/on_demand.py` |
| `careerloop/discovery.py` | Older discovery engine, no unified event streaming | `OnDemandSearch` in `careerloop/on_demand.py` |
| `daily_runner.py::run()` discovery path | Subprocess-based, no SSE, no cache-first strategy | `OnDemandSearch` in `careerloop/on_demand.py` |
| `modes/deep.md` (research engine) | Prompt generator, not intelligence | `company_intel.py` |
| `modes/batch.md` | Runs A-G on all jobs — anti-pattern | India Fit pre-filter |
| `batch/` directory | Batch orchestration for mass A-G | Not needed with lazy evaluation |
| `data/pipeline.md` as writer | Markdown is not a database | Ledger (generated view only) |
| `data/applications.md` as writer | Markdown is not a database | Ledger (generated view only) |
| `data/follow-ups.md` as writer | Split state, no sync | Ledger entries |
| `modes/training.md` | Future Phase 4+ | Parked |
| `modes/project.md` | Future Phase 4+ | Parked |

---

## 3. Canonical Pipeline

```
Discover (50+ jobs)
    │
    ├── OnDemandSearch (careerloop/on_demand.py) — Canonical path
    │   ├── scan.mjs (ATS APIs: Greenhouse, Lever, Ashby — DEPRECATED, use on_demand)
    │   ├── discovery.py (DDG search + ScrapeGraphAI extraction — DEPRECATED, use on_demand)
    │   └── Future: Naukri/Instahyre/Cutshort/Hirist adapters
    └── SSE streaming via scan_service.py::stream_scan_events()
    │
    ▼
Verify
    │
    ├── verification.py (liveness check, URL reachability)
    ├── india_filter.py (geographic hardening)
    └── apply_route.py (cross-source dedup)
    │
    ▼
Pre-Filter — India Fit Engine (14-dim, heuristic, ZERO LLM)
    │
    ├── Score all verified jobs 0–100
    ├── Categorize: GO / MAYBE / SKIP
    └── Persist to ledger (DISCOVERED → SHORTLISTED)
    │
    ▼
Triage — Daily Standup (user reviews 5–8 candidates)
    │
    ├── "Apply to these 5. Save 3. Ignore the rest."
    └── User marks jobs INTERESTED (ledger transition)
    │
    ▼
Deep Evaluation — A-G (LAZY: only on INTERESTED jobs, ≤10)
    │
    ├── modes/oferta.md framework (wrapped, not raw)
    ├── Block G (legitimacy) hoisted to Verification layer
    └── Output feeds Company Intel + Council
    │
    ▼
Company Intelligence (LAZY: after INTERESTED)
    │
    ├── company_intel.py
    ├── WebSearch → structured extraction → CompanyIntelligence
    ├── Cached in company_memory (SQLite)
    └── Answers: "Should THIS user want THIS company?"
    │
    ▼
Resume Council (LAZY: after user says APPLY or PREPARE_APPLICATION)
    │
    ├── 8-system LangGraph pipeline
    ├── Deterministic parse + contract
    ├── LLM: intel → decode → truth → strategy → rewrites → guard → assembly
    └── Output: application_pack (resume + cover + DM + quality report)
    │
    ▼
Humanizer (post-Council, pre-render)
    │
    ├── humanizer.py
    ├── Strip AI-isms, enforce banned-words, adapt tone
    └── Produce human-grade text
    │
    ▼
Renderer
    │
    ├── compiler.py → fill cv-template.html
    └── generate-pdf.mjs → ATS-clean PDF
    │
    ▼
Apply Assist
    │
    ├── modes/apply.md workflow (wrapped)
    ├── Fill form fields, draft answers
    ├── User reviews every application pack
    ├── Optional assisted execution only after explicit per-job approval
    └── Future: Kimi/Hermes bridge or Chrome extension with native DOM hooks
    │
    ▼
Track + Follow Up
    │
    ├── application_ledger.py (status transitions + follow_up_dates)
    ├── FOLLOW_UP_SCHEDULE = [5, 10, 17, 25] days
    └── Generated tracker view (modes/tracker.md)
    │
    ▼
Learn
    │
    ├── analyze-patterns.mjs (port to careerloop/learning.py)
    ├── Rejection pattern mining
    ├── Success pattern mining
    ├── Score threshold calibration
    └── Feed into Profile Manager (auto-tune preferences)
```

---

## 4. Ledger Lifecycle

```
                    ┌──────────────┐
                    │  DISCOVERED   │  ← OnDemandSearch adds jobs here
                    └──────┬───────┘
                           │ India Fit Engine scores job
                           ▼
                    ┌──────────────┐
                    │  SHORTLISTED  │  ← fit_score ≥ threshold (configurable per mode)
                    └──────┬───────┘
                           │ User reviews in daily standup
                           ▼
                    ┌──────────────┐
                    │  INTERESTED   │  ← user explicitly marks interest
                    └──────┬───────┘
                           │ Triggers: A-G Evaluation + Company Intelligence
                           ▼
                    ┌──────────────┐
                    │   APPROVED    │  ← user decides to apply
                    └──────┬───────┘
                           │ Triggers: Resume Council + Humanizer
                           ▼
                    ┌──────────────┐
                    │   APPLIED     │  ← user confirms application submitted
                    └──────┬───────┘
                           │ Auto-schedules follow_up_dates [5, 10, 17, 25]
                           ▼
                    ┌──────────────┐
                    │  RESPONDED    │  ← company responds (any communication)
                    └──────┬───────┘
                           │
                    ┌───────┴────────┐
                    ▼                ▼
             ┌──────────┐    ┌──────────────┐
             │ INTERVIEW │    │   REJECTED    │
             └────┬─────┘    └──────────────┘
                  │
           ┌──────┴──────┐
           ▼              ▼
    ┌──────────┐   ┌──────────┐
    │  OFFER    │   │ REJECTED  │
    └──────────┘   └──────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌──────┐ ┌──────────┐
│ACCEPT│ │ DECLINED  │
└──────┘ └──────────┘

TERMINAL STATES: REJECTED, DISCARDED, ACCEPTED, DECLINED
DORMANT STATES:   All terminal + SKIP (user explicitly passes)
ACTIVE STATES:    All non-terminal, non-dormant
```

### Status Mapping: Ledger ↔ Career-Ops States

| Ledger Status | Career-Ops State (`states.yml`) | Notes |
|---------------|--------------------------------|-------|
| DISCOVERED | — | New — no Career-Ops equivalent |
| SHORTLISTED | — | New — no Career-Ops equivalent |
| INTERESTED | — | New — no Career-Ops equivalent |
| APPROVED | — | New — no Career-Ops equivalent |
| APPLIED | Applied | Match |
| RESPONDED | Responded | Match |
| INTERVIEW | Interview | Match |
| OFFER | Offer | Match |
| REJECTED | Rejected | Match |
| DISCARDED | Discarded | Match |
| SKIP | SKIP | Match |
| ACCEPTED | — (implicit) | New — explicit terminal state |
| DECLINED | — (implicit) | New — explicit terminal state |

---

## 5. Deprecation Map

### Phase 1.5 (Now) — Deprecate as Writers

| File | Action | Replacement |
|------|--------|-------------|
| `data/pipeline.md` | Stop writing. Keep file, mark as generated view. | `scan.mjs` → ledger |
| `data/applications.md` | Stop writing new entries. Keep file, mark as generated view. | Ledger → generate markdown view |
| `data/follow-ups.md` | Stop writing. | Ledger entries |

### Phase 2 — Deprecate Entirely

| File | Action | Replacement |
|------|--------|-------------|
| `modes/deep.md` | Deprecate as primary path. Keep as manual fallback. | `company_intel.py` |
| `modes/batch.md` | Deprecate. | Not needed (lazy eval, not batch eval) |
| `batch/` | Archive directory. | Not needed. |

### Phase 3 — Deprecate

| File | Action | Replacement |
|------|--------|-------------|
| `modes/apply.md` | Deprecate as primary execution engine. Keep as spec/reference. | Assisted apply bridge (Kimi/Hermes or Chrome extension) |
| `modes/pdf.md` (content part) | Deprecate content generation. Keep renderer invocation. | Council owns content; pdf.md becomes renderer trigger only. |

---

## 6. File System Layout (Current + Planned)

```
~/Projects/CareerLoop/
├── careerloop/                           ← CareerLoop owns this
│   ├── on_demand.py                      ✅ Unified discovery engine (OnDemandSearch)
│   ├── india_fit_engine.py               ✅ 14-dim pre-filter
│   ├── india_fit_llm.py                  ✅ LLM scoring alternative
│   ├── india_filter.py                   ✅ Geographic hardening
│   ├── verification.py                   ✅ Liveness check
│   ├── apply_route.py                    ✅ Cross-source dedup
│   ├── application_ledger.py             ✅ Source of truth
│   ├── profile_manager.py                ✅ User profile
│   ├── role_strategy.py                  ✅ Role search strategy
│   ├── models.py                         ✅ Data contracts
│   ├── config.py                         ✅ Weights, signals, cities
│   ├── audit.py                          ✅ Pipeline health
│   ├── shortlist_formatter.py            ✅ WhatsApp-style output
│   ├── daily_runner.py                   ✅ Daily pipeline orchestrator
│   ├── company_intel.py                  ✅ LIVE — 1,419 lines, full MECE implementation
│   ├── chat_cli.py                       🔴 Phase 0 scaffold — Terminal entry point
│   ├── learning.py                       🔴 Phase 2 — pattern analysis (port of analyze-patterns.mjs)
│   ├── transport/                        🔴 Phase 0 scaffold — adapters normalize platform payloads
│   │   ├── base.py                       🔴 TransportAdapter + UserEvent; needs graph-state mapping fix
│   │   ├── terminal_chat.py              🔴 Local test adapter
│   │   └── telegram.py                   🔴 Telegram stub
│   ├── session/                          🔴 Phase 0 scaffold — conversational state + supervisor
│   │   ├── supervisor_graph.py           🔴 LangGraph parent graph; router placeholder
│   │   ├── states.py                     🔴 UserState enum
│   │   ├── session_store.py              🔴 fallback store
│   │   └── user_registry.py              🔴 user registry
│   ├── execution/                        ⚫ Phase 5 mock — assisted apply bridge
│   │   └── kimi_bridge.py                ⚫ Kimi/Hermes concept; no real browser integration yet
│   ├── council/                          ✅ Resume Council
│   │   ├── graph.py                      ✅ LangGraph state machine (S1-S8 + Truth Guard); CouncilState: candidate_graph + cv_tenure_years wired
│   │   ├── orchestrator.py               ✅ One-job runner
│   │   ├── compiler.py                   ✅ Deterministic parse + assemble + extract_candidate_graph() static method
│   │   ├── candidate_graph.py            ✅ Canonical structured identity (CandidateGraph dataclass); wired into S1 parse_node
│   │   ├── models.py                     ✅ Council data contracts
│   │   ├── context.py                    ✅ Council context loader
│   │   ├── llm.py                        ✅ DeepSeek client
│   │   ├── truth_guard.py               ✅ Semantic claim validation + CV-tenure year-inflation guard
│   │   └── humanizer.py                 ✅ LIVE — 5-phase Cope-Killer pipeline (29 tests)
│   ├── memory/                           🟡 Persistence
│   │   ├── models.py                     ✅ SQLAlchemy models (6 entities)
│   │   ├── connection.py                 ✅ SQLite connection
│   │   ├── checkpointer.py               🔴 LangGraph PostgresSaver wrapper; needs Supabase connection test
│   │   ├── supabase_schema.sql           🔴 Supabase schema scaffold
│   │   ├── repository.py                 ✅ CRUD
│   │   └── retrieval.py                  ✅ Query layer
│   ├── sources/                          ✅ Discovery adapters
│   │   ├── search_adapter.py             ✅ DDG search
│   │   ├── scrapegraph_adapter.py        ✅ Deep extraction
│   │   └── jobspy_adapter.py             ✅ Multi-board
│   ├── tests/                            ✅ Regression + stabilization tests
│   │   └── test_stabilization.py         ✅ 70 P0/P1 stabilization tests
│   └── docs/                             ✅ Product + architecture docs
│       ├── PRD.md                        ✅ Canonical vision
│       ├── TRACKER.md                    ✅ Rolling session log
│       ├── CANONICAL_ARCHITECTURE.md     ✅ This file
│       ├── CAREERLOOP_REUSE_AUDIT.md     ✅ Reuse audit
│       ├── CAREERLOOP_MASTER_VISION_AMENDMENTS.md ✅ Vision amendments
│       ├── CAREERLOOP_COUNCIL_AUDIT.md   ✅ Council deep audit
│       ├── vision.md                     ✅ Historical v1.6
│       ├── breakdown-20-part.md          ✅ 20-part architecture
│       ├── resume-council-vision.md      ✅ Council 8-system spec
│       └── specs/                        🔴 Design specs (pending implementation)
│           ├── humanizer-design.md        🔴
│           └── company-intel-design.md    🔴
│
├── Inherited from Career-Ops (kept)
├── modes/        ← Prompt modes (several wrapped by CareerLoop)
├── *.mjs         ← Node scripts (scan, generate-pdf, analyze-patterns, etc.)
├── templates/    ← CV templates (HTML, LaTeX), states.yml
├── config/       ← User config (profile.yml, portals.yml)
├── data/         ← Generated views (not writers)
├── assets/       ← Images
├── fonts/        ← PDF fonts
├── cv.md         ← Master resume
├── .claude/      ← Claude Code skills
├── .gemini/      ← Gemini CLI commands
└── .opencode/    ← OpenCode commands
```

---

## 7. Hard Architecture Rules (Non-Negotiable)

1. **One source of truth for job state:** `application_ledger.py` / `ledger.json`. No system writes to `data/pipeline.md`, `data/applications.md`, or `data/follow-ups.md`.

2. **Lazy-loaded deep intelligence:** A-G evaluation, Company Intelligence, Resume Council, and Humanizer run ONLY after explicit user interest. Never on all discovered jobs.

3. **Council owns content. Renderer owns PDF output.** No system generates resume content outside the Council. `generate-pdf.mjs` and `generate-latex.mjs` are pure renderers.

4. **No auto-submit.** Every application, every message, every form requires manual user review and confirmation before sending.

4a. **Assisted apply is single-job and approval-gated.** A bridge may fill and submit only after the user has reviewed one application pack and issued an explicit per-job approval. It may not process a queue, choose jobs, or submit unattended bulk applications.

5. **Humanizer runs on every user-facing text output.** No exception for cover notes, recruiter messages, resume text, or follow-ups.

6. **Company intelligence is structured, not narrative.** Output is a populated dataclass with confidence scores and source attribution. It is cached in `company_memory`. It answers "should THIS user want THIS company."

7. **No duplicate systems.** If CareerLoop has `company_intel.py`, `modes/deep.md` is not the intelligence layer. If CareerLoop has `application_ledger.py`, `data/applications.md` is not the tracker.

8. **Council never invents content.** Every claimed skill, achievement, and metric must trace back to `cv.md` or `article-digest.md`. Truth Guard enforces this mechanically.

9. **Transports do not own business logic.** CLI, Telegram, WhatsApp, or future UI channels must normalize into `UserEvent`, map into `ConversationState`, and invoke the LangGraph Supervisor with a stable `thread_id`.

---

## 8. Phase Map (Post-Consolidation)

| Phase | Systems | % of Vision | Est. Completion |
|-------|---------|-------------|-----------------|
| **Phase 0** (Delivery Foundation) | Transport, Supervisor, Checkpointer, Onboarding (7-step name-first: name → LinkedIn → identity card → CV → extraction → gap-fill → PROFILE_READY) | ~10% | 12% scaffolded |
| **Phase 1** (Discovery + Pre-filter) | Discovery, Verification, India Fit Engine, Ledger | ~25% | 70% built |
| **Phase 1.5** (Decision + Memory) | Triage UX, Career State Modes, A-G wrapper, Ledger migration | ~20% | 25% built |
| **Phase 2** (Intelligence + Positioning) | Company Intel, Humanizer, Council hardening, Positioning engine | ~25% | 50% built (Company Intel + Humanizer live) |
| **Phase 3** (Execution) | Application assist, Kimi/Hermes bridge, Chrome extension fallback, Follow-up surface, Outreach | ~20% | 8% built |
| **Phase 4** (Learning Loop) | Interview memory, Pattern learning, Profile auto-tuning, Monetization | ~10% | 2% built |

---

*Architecture locked 2026-05-18. Amendments require PRD §17 update + this document update.*

---

## 9. Discovery Architecture (Addendum — 2026-05-29)

### Canonical Engine

**`careerloop/on_demand.py::OnDemandSearch`** is the single, unified job discovery engine. Every discovery flow — Daily Brief, Scan More, Copilot Discovery, or future search APIs — MUST route through `OnDemandSearch.run()`.

### SSE Event Contract

The discovery pipeline emits structured events via Server-Sent Events (SSE). The canonical producer is `careerloop_api/services/scan_service.py::stream_scan_events()`, which polls the `careerloop.run_events` table. The canonical consumer is the frontend `EventSource` in `ChatPage.tsx`.

#### Event Types

| Event Type | Stage | Description |
|------------|-------|-------------|
| `QUEUED` | Init | Scan accepted into the worker queue |
| `SCAN_STARTED` | Discovery | Discovery pipeline initialized |
| `SCAN_COMPLETED` | Terminal | All sources scanned, results aggregated |
| `SCAN_FAILED` | Terminal | Scan worker crashed or timed out |
| `SOURCE_SCANNING` | In-flight | Per-company/portal progress: `{ source: string, roles_found: int }` |
| `JOB_FOUND` | Raw | Raw job listing found: `{ job_title, company, location, source, apply_url }` |
| `JOB_EVALUATED` | Filtered | Job scored against targets: `{ job_title, company, fit_score, reason }` |
| `JOB_REJECTED` | Filtered | Job rejected by a filter stage: `{ job_title, company, reason, rejection_stage }` |
| `CANDIDATE_MATCHED` | Scored | Final candidate passed all filters: `{ job_title, company, location, fit_score, match_index }` |
| `BRIEF_ADDED` | Output | Brief updated in DB: `{ jobs_added: int }` |
| `FILTER_SUMMARY` | Summary | Aggregated filter stats: `{ raw, new, scored }` |
| `BRIEF_CREATED` | Terminal | Brief persisted and ready for retrieval |
| `DONE` | Terminal | SSE stream complete — EventSource should close |
| `TIMEOUT` | Terminal | Hard timeout (5 min) reached |
| `ERROR` | Terminal | Stream error |

#### Transport

Events are stored in `careerloop.run_events` (PostgreSQL) and polled by `stream_scan_events()` every 1 second. The producer writes to `run_events` directly; no message broker is involved.
