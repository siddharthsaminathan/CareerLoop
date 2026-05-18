# CareerLoop — Product Engineering Tracker

> Maintained by the `careerloop-product-lead` skill. Updated at session start and on `/careerloop-product-lead`.  
> The tracker in `PRD.md §17` mirrors the System Status table below and is updated simultaneously.

---

## Current Sprint Focus

**Week of 2026-05-18 — Architecture Consolidation**

Architecture consolidation complete. All final decisions locked in `CANONICAL_ARCHITECTURE.md`.  
Next sprint: Humanizer implementation (P0) + Truth Guard upgrade (P1) + Company Intelligence engine (P1).

---

## System Status (Live)

> Recalibrated 2026-05-18 after deep Council audit and Career-Ops reuse audit. Honest assessment.

| System | % | Status | Blocking? | Notes |
|--------|---|--------|-----------|-------|
| India-first discovery | 65% | 🟡 | No | ATS scan solid; 0/5 India portals (Naukri, Instahyre, etc.) |
| Verification & filtering | 55% | 🟡 | No | Search page rejection works; Block G (legitimacy) not hoisted |
| Opportunity scoring (14-dim) | 50% | 🟡 | No | Heuristic works for AI roles; needs calibration for non-AI |
| Decision compression / triage | 20% | 🔴 | No | modes/ofertas.md reusable but no UX built |
| Career state system (modes) | 10% | 🔴 | No | Conceptual only; not wired to pipeline |
| Company intelligence | 10% | 🔴 | **Yes** | Council node is unreliable LLM recall; company_intel.py spec written, code not started |
| Positioning engine | 15% | 🟡 | No | Council positioning_node exists; prompt hardening + schema needed |
| Resume Council (v3) | 45% | 🟡 | **Yes** | Pipeline passes; 4/8 output fields missing + Humanizer not integrated |
| Humanizer layer | 5% | 🔴 | **Yes (P0)** | Spec written; code not started. Blocks Council quality + outreach quality |
| Application execution | 15% | 🔴 | No | modes/apply.md is working prototype; Chrome extension not started |
| Chrome extension | 0% | ⚫ | No | Phase 3 |
| Follow-up system | 25% | 🔴 | No | Ledger auto-schedules; cadence logic exists; UI missing |
| Interview memory | 10% | 🔴 | No | modes/interview-prep.md is 4★; no DB persistence |
| Persistent memory graph | 20% | 🟡 | No | Ledger full lifecycle + auto-schedules; SQLite schema drafted |
| WhatsApp/transport UX | 15% | 🔴 | No | Concept exists; no implementation |
| Monetization logic | 30% | 🟡 | No | Strategic understanding solid; pricing not built |

**Overall product maturity: ~20–25% of vision.** (Unchanged from prior estimate — the deeper audit revealed some systems further along and some further behind. Net neutral.)

> Legend: 🟢 Done · 🟡 Active · 🔴 Gap · ⚫ Not started

---

## Open Blockers

| # | Blocker | System | Since | Priority |
|---|---------|--------|-------|----------|
| B1 | Truth Guard uses exact string matching — paraphrases bypass it | Resume Council | 2026-05-18 | P1 |
| B2 | Humanizer not implemented — all user-facing text is raw LLM output | Resume Council | 2026-05-18 | **P0** |
| B3 | cover_note + recruiter_message prompts are 1-sentence stubs → generic output | Resume Council | 2026-05-18 | **P0** |
| B4 | Company career pages invisible — only seeing ~30% of market | Discovery | 2026-05-17 | P2 |
| B5 | Decision compression / triage UX not built | Triage | 2026-05-18 | P2 |
| B6 | Company Intelligence node uses LLM memory recall, not web research | Council | 2026-05-18 | P1 |
| B7 | 5 of 6 LLM Council nodes lack explicit JSON schemas in prompts | Council | 2026-05-18 | P1 |

---

## Architecture Decisions (LOCKED)

These are final. See `CANONICAL_ARCHITECTURE.md` for full detail.

| # | Decision | Date |
|---|----------|------|
| A1 | Single source of truth: `application_ledger.py` / `ledger.json`. Markdown files are generated views, not writers. | 2026-05-18 |
| A2 | Two-layer evaluation: India Fit Engine (cheap pre-filter, all jobs) + A-G (deep, lazy, ≤10 jobs) | 2026-05-18 |
| A3 | Company Intelligence is lazy-loaded, structured, cached in `company_memory` (SQLite) | 2026-05-18 |
| A4 | `modes/deep.md` is a fallback manual tool, not the intelligence engine | 2026-05-18 |
| A5 | Council owns all content. Renderer (`generate-pdf.mjs`) owns PDF output only. No other CV generator. | 2026-05-18 |
| A6 | Humanizer runs on every user-facing text output (resume, cover note, recruiter DM, follow-ups) | 2026-05-18 |
| A7 | No auto-submit. Every form, message, application requires manual user review. | 2026-05-18 |
| A8 | Resume Council writes application_pack back to ledger entry on completion. | 2026-05-18 |

---

## Session Log

---

### 2026-05-18 — Session: Architecture Consolidation

**What was done:**
- Career-Ops reuse audit complete — 17 capabilities classified (Reuse/Wrap/Rewrite/Ignore/Future)
- Resume Council deep audit — 8 nodes analyzed, hallucination points identified, output contract gaps mapped
- Humanizer design spec written (`specs/humanizer-design.md`) — 4-phase pipeline, banned words, tone profiles
- Company Intelligence design spec written (`specs/company-intel-design.md`) — web-sourced, cached, lazy-loaded
- Canonical Architecture locked (`CANONICAL_ARCHITECTURE.md`) — ownership, deprecation, lifecycle, phase map
- 8 hard architecture rules established (non-negotiable)
- Tracker percentages recalibrated on honest audit-grade assessment
- 8 vision amendments proposed (integration clarifications, no direction changes)

**Vision alignment verdict:** ✅ ALIGNED  
Consolidation directly strengthens PRD §11 (Resume Council), §12 (Humanizer), §9 (Company Intelligence), §6 (Opportunity Intelligence), §15 (Persistent Memory). No deviations.

**Deviations detected:** None. Architecture is now locked.

**Recommended next 3 actions:**
1. Implement Humanizer layer (`careerloop/council/humanizer.py`) — P0, blocks Council quality
2. Upgrade Truth Guard to fuzzy/semantic matching — P1, current exact-match is bypassable
3. Build Company Intelligence engine (`careerloop/company_intel.py`) — P1, replaces unreliable Council node

---

### 2026-05-18 — Session: Council v3 Fix + Vision/Tracker Setup

**What was done:**
- career-ops upgraded v1.3.0 → v1.8.0
- Resume Council v3 pipeline unblocked: `_safe_init()` helper added to `orchestrator.py`
- All 3 fixture tests pass (experienced / fresher / business profiles)
- Leakage guard ✅ Link preservation ✅
- Created master PRD, product engineering tracker, docs reorganized to `careerloop/docs/`
- Created `careerloop-product-lead` cross-agent skill

**Vision alignment verdict:** ✅ Aligned  
Council v3 work directly advances §11 (Resume Council) and §12 (Humanizer). Infrastructure work (docs, skill) enables §15 (Persistent Memory) and §16 (End-state).

**Deviations detected:** None this session.

**Recommended next 3 actions:**
1. Implement Truth Guard (§11 — Resume Council, B1) — independent verification pass before output
2. Implement dedicated Humanizer pass (§12, B2) — strip AI-isms from generated copy
3. Build company career page scraper (§5 — Discovery, B4) — closes the 70% market gap

---

<!-- product-lead appends new entries above this line -->
