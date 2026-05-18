# CareerLoop — Product Engineering Tracker

> Maintained by the `careerloop-product-lead` skill. Updated at session start and on `/careerloop-product-lead`.  
> The tracker in `PRD.md §17` mirrors the System Status table below and is updated simultaneously.

---

## Current Sprint Focus

**Week of 2026-05-18 — Architecture Stabilization Complete**

6-agent stabilization pass finished. Resume renderer produces clean output (0 em dashes, 0 arrows, 0 raw markdown) across all 9 templates. NormalizedResume enforced. Humanizer wired with LLM. Company Intelligence vision published.

**Next sprint:** Company Intelligence engine + Tailoring delta improvement (3.6% → 15%+).

---

## System Status (Live)

> Updated 2026-05-18 after 6-agent stabilization pass.

| System | % | Status | Blocking? | Notes |
|--------|---|--------|-----------|-------|
| India-first discovery | 75% | 🟡 | No | ATS adapter, portal scraper, on-demand search, role keywords shipped |
| Verification & filtering | 60% | 🟡 | No | detect_ats_pass.py; Block G not hoisted |
| Opportunity scoring (14-dim) | 55% | 🟡 | No | function_probability.py + metrics.py; needs calibration |
| Decision compression / triage | 20% | 🔴 | No | modes/ofertas.md reusable; no UX |
| Career state system (modes) | 10% | 🔴 | No | Conceptual only |
| Company intelligence | 20% | 🔴 | No | Vision doc published; Council JD-grounded; company_intel.py not built |
| Positioning engine | 20% | 🟡 | No | Council S6 wired; tailoring delta 3.6% (needs prompt work) |
| Resume Council (v3) | 60% | 🟡 | No | All 8 systems pass; Humanizer; Truth Guard; deterministic compiler |
| Humanizer layer | 50% | 🟡 | No | 5-phase pipeline; 28 banned words; LLM wired; post-Humanizer verification |
| Resume rendering (templates) | 70% | 🟡 | No | NormalizedResume contract; 9 templates; 36/36 clean renders |
| Validator / QA | 60% | 🟡 | No | 10 rules; regression_test.py CI-ready; 94.4% pass rate |
| Application execution | 15% | 🔴 | No | modes/apply.md prototype; Chrome extension not started |
| Chrome extension | 0% | ⚫ | No | Phase 3 |
| Follow-up system | 25% | 🔴 | No | Ledger auto-schedules; UI missing |
| Interview memory | 10% | 🔴 | No | modes/interview-prep.md 4★; no DB persistence |
| Persistent memory graph | 25% | 🟡 | No | Ledger + company_registry + SQLite schema |
| WhatsApp/transport UX | 15% | 🔴 | No | Concept only |
| Monetization logic | 30% | 🟡 | No | Strategic understanding solid |

**Overall product maturity: ~30-35% of vision.** (+10% after 6-agent stabilization.)

> Legend: 🟢 Done · 🟡 Active · 🔴 Gap · ⚫ Not started

---

## Open Blockers

| # | Blocker | System | Since | Priority |
|---|---------|--------|-------|----------|
| ~~B1~~ | Truth Guard exact string matching | Closed | ✅ Semantic claim validation implemented |
| ~~B2~~ | Humanizer not implemented | Closed | ✅ 5-phase pipeline + LLM wired |
| ~~B3~~ | cover_note/recruiter_message stubs | Closed | ✅ Improved prompts + richer context |
| ~~B7~~ | LLM nodes lacked JSON schemas | Closed | ✅ All 6 prompts have JSON examples |
| B4 | Company career pages invisible | Discovery | P2 |
| B5 | Decision compression UX not built | Triage | P2 |
| B6 | Company Intelligence engine not built | Council | **P1** |
| B8 | Tailoring delta only 3.6% | Council | **P0** |

---

## Architecture Decisions (LOCKED)

| # | Decision | Date |
|---|----------|------|
| A1 | Single source of truth: `application_ledger.py` / `ledger.json` | 2026-05-18 |
| A2 | Two-layer evaluation: India Fit (cheap, all) + A-G (lazy, ≤10) | 2026-05-18 |
| A3 | Company Intelligence: lazy-loaded, structured, cached | 2026-05-18 |
| A4 | `modes/deep.md` = fallback, not the engine | 2026-05-18 |
| A5 | Council owns content; `generate-pdf.mjs` owns PDF output | 2026-05-18 |
| A6 | Humanizer on every user-facing text output | 2026-05-18 |
| A7 | No auto-submit; manual review required | 2026-05-18 |
| A8 | Single DeepSeek API key for entire system | 2026-05-18 |
| A9 | Strategy: `deepseek-v4-pro`, Writer: `deepseek-chat` | 2026-05-18 |
| A10 | NormalizedResume = single data contract for ALL renderers | 2026-05-18 |
| A11 | Post-render validation FAILS HARD on `**`, `—`, `→` | 2026-05-18 |

---

## Session Log

---

### 2026-05-18 — Session: 6-Agent Stabilization + Company Intelligence Vision

**What was done:**
- 6 parallel agents: Data Model Architect, Markdown Parser Debugger, Template Reviewer, Humanizer/Sanitizer Reviewer, Validator QA Engineer, Cross-template Regression Tester
- NormalizedResume enforced as single data contract across both renderers (fill-template.py v5, render_all_templates.py)
- Critical bugs fixed: `**bold**` rendering, em dashes `—`, arrows `→` — all 3 caught at normalizer level with post-render hard fail
- Humanizer: "agentic" added to banned words, Phase 5 sanitizer, post-Humanizer verification scan
- Validator: 10 rules, CI-ready regression_test.py, 94.4% pass rate (36/36 clean renders)
- Company Intelligence vision document published
- MODELS.md: full LLM architecture, per-node model usage
- FUCKUPS.md: 8 honest mistakes documented
- Git: stash → pull → pop, no conflicts

**Vision alignment verdict:** ✅ STRONGLY ALIGNED  
PRD §11 (Council 45→60%), §12 (Humanizer 5→50%), §9 (Company Intel 10→20%), Rendering (new: 70%), Validator (new: 60%).

**Recommended next 3 actions:**
1. Fix tailoring delta (3.6% → 15%+): Council S6/S7 prompts need role-specific adaptation (P0, §10-11)
2. Build Company Intelligence engine (`company_intel.py`) per spec and vision doc (P1, §9)
3. Run Nicobar golden test with all fixes → generate final deliverable PDFs (P1, §11)

---

### 2026-05-18 — Session: Architecture Consolidation + Gemini Discovery Push

**What was done:** Council stabilized (JSON prompts, compiler, Humanizer, Truth Guard). Gemini: Discovery Phase 1 (ATS, on-demand, company registry, 7 templates). Docs reorganized, product-lead skill created.
**Vision alignment verdict:** ✅ ALIGNED

---

### 2026-05-18 — Session: Council v3 Fix + Vision/Tracker Setup

**What was done:** career-ops upgraded, Council v3 unblocked, master PRD + tracker created.
**Vision alignment verdict:** ✅ Aligned

---

<!-- product-lead appends new entries above this line -->
