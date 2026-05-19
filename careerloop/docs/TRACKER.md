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

> Updated 2026-05-19 after Resume Council structural stabilization + Codex functional pass.

| System | % | Status | Blocking? | Notes |
|--------|---|--------|-----------|-------|
| India-first discovery | 75% | 🟡 | No | ATS adapter + Spire AI adapter; portal layer still ~0% for JS-heavy sites |
| Verification & filtering | 60% | 🟡 | No | detect_ats_pass.py; Block G not hoisted |
| Opportunity scoring (14-dim) | 55% | 🟡 | No | function_probability.py + metrics.py; needs calibration |
| Decision compression / triage | 20% | 🔴 | No | modes/ofertas.md reusable; no UX |
| Career state system (modes) | 10% | 🔴 | No | Conceptual only |
| Company intelligence | 30% | � | No | CompanyResearchAdapter built; grounding/provenance wired into S3; company_intel.py not yet standalone |
| Positioning engine | 25% | 🟡 | No | S6 wired + schema validated; tailoring delta still unmeasured post-fix |
| Resume Council (v3) | 72% | 🟡 | No | Per-section S7 loop; structural postconditions; Truth Guard UNSUPPORTED fix; schema validation on all nodes; Pipeline A→B connected |
| Humanizer layer | 55% | 🟡 | No | Markdown safety gate added; full LLM rewrite of resume blocked; structure validation pre/post |
| Resume rendering (templates) | 75% | 🟡 | No | Hard fail on structure loss; normalizer handles PDF-style preamble + loose experience blocks |
| Validator / QA | 65% | 🟡 | No | 36 regression tests (was 31); structural guard tests added; render pipeline validation |
| Application execution | 15% | 🔴 | No | modes/apply.md prototype; Chrome extension not started |
| Chrome extension | 0% | ⚫ | No | Phase 3 |
| Follow-up system | 25% | 🔴 | No | Ledger auto-schedules; UI missing |
| Interview memory | 10% | 🔴 | No | modes/interview-prep.md 4★; no DB persistence |
| Persistent memory graph | 25% | 🟡 | No | Ledger + company_registry + SQLite schema |
| WhatsApp/transport UX | 15% | 🔴 | No | Concept only |
| Monetization logic | 30% | 🟡 | No | Strategic understanding solid |

**Overall product maturity: ~38-40% of vision.** (+5% from structural stabilization pass. Council 60→72%, Company Intel 20→30%, Humanizer 50→55%, Rendering 70→75%, Validator 60→65%.)

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

### 2026-05-19 — Session: Resume Council Structural Stabilization (Cascade + Codex)

**What was done:**
- **Bucket 1 — CV input preprocessing:** Extended `_preprocess_plaintext_cv()` (Pass B) to split run-on date/location/bullet blobs from PDF-extracted CVs. Detects `PresentBuilt` → `Present\n\nBuilt`, `IndiaCategory` → `India\nCategory`, `2024Chennai` → `2024\n\nChennai`, bullet chars `•●▸` → `\n- `. Runs on all inputs, not just headingless text. Also applied post-S7 to catch LLM re-collapses.
- **Bucket 2 — S7 per-section loop:** Replaced single giant JSON blob LLM call with one focused call per section. Each call gets only its section text + top-5 proof points + tone + keywords + 4000 max_tokens. Long experience sections (>3500 chars) kept as originals.
- **Bucket 2b — S7 structural postconditions:** `_rewrite_preserves_section_structure()` checks bullet count drop, collapsed bullet markers, truncation, and too-short rewrites. Rejects bad rewrites and keeps originals.
- **Bucket 3 — TruthGuard over-repair fix:** `_repair_evidence_claim()` now returns original unchanged for UNSUPPORTED ownership claims (Jaccard false positives). Only FABRICATED/EXAGGERATED ownership gets minimized. Killed `data-contributed to` / `fashion-contributed to` artifacts.
- **Bucket 4 — Pipeline A→B:** `modes/pdf.md` now has Step 0: check `output/council/{person_id}/{job_id}/10_final_resume.md` before reading `cv.md`.
- **LLM client:** `max_tokens` default 10000→4000, timeout 120→90s, per-call override param, per-call progress print `⟳ LLM call [label]...`
- **Humanizer safety gate:** Markdown structure validation pre/post — rejects rewrites that lose bullets or structure.
- **Normalizer:** PDF-style preamble contact preservation; loose experience block parsing; `softbreak` AST node handled.
- **Render pipeline:** Hard fail if normalization loses required structure.
- **Company intelligence grounding:** `CompanyResearchAdapter` built; wired into S3 with grounding status + provenance.
- **Schemas:** JSON schema validation on all 6 LLM nodes; `private_constraints` stripped at S5.
- **Tests:** 36 regression tests (31 → 36); structural guard tests added.
- **Varsha E2E run:** 3 experience entries / 19 bullets correctly parsed and preserved. Education, Skills clean. Cover note and recruiter DM generated.

**Vision alignment verdict:** ✅ STRONGLY ALIGNED  
PRD §11 (Council 60→72%), §12 (Humanizer 50→55%), Rendering (70→75%), §9 (Company Intel 20→30%), Validator (60→65%).

**Deviations detected:** None. All work directly on the Council pipeline's core quality and correctness.

**Recommended next 3 actions:**
1. Measure tailoring delta post-fix — run Siddharth Nicobar end-to-end, compare keyword coverage before/after (B8, PRD §10-11)
2. Build per-entry structured rewriting for S7 experience section — loop over individual job entries instead of skipping long sections (PRD §11)
3. Build standalone `company_intel.py` engine using CompanyResearchAdapter as foundation (B6, PRD §9)

---

### 2026-05-19 — Session: Discovery Pipeline Debugging (Varsha dry run)

**What was done:**
- Lever slug bug fixed (was extracting "v0" instead of company name)
- Sector→function probability fixed: Finance & Fintech companies now correctly excluded from fashion buyer targeting (fn_prob 0.5→0.02)
- Role relevance filter de-hardcoded: `rejected_roles` from YAML, generic business words ("manager", "senior", etc.) excluded from domain signal tokens
- Spire AI adapter built (`careerloop/sources/spireai_adapter.py`): REST API discovery for Spire AI career portals; Myntra confirmed → 14 jobs
- 16 fashion company career URLs seeded in DB
- Varsha dry run: 39 jobs (fashion buyer / Bangalore), top results from Myntra SpireAI + JobSpy LinkedIn/Indeed
- Discovery pipeline status doc fully rewritten

**What didn't work:** 15/16 fashion company portals return 0 jobs (JS-heavy SPAs). Meesho Lever board still contaminates fashion results. Score range still compressed (47-67). Profile bleed: Varsha dry run uses Hayagreev's target_roles.

**Vision alignment verdict:** ⚠️ PARTIALLY ALIGNED — bugs fixed but no new capability shipped. Discovery portal layer still broken for fashion companies.

**No progress on:** tailoring delta, company intel engine, Nicobar golden run.

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
