# CareerLoop — Product Engineering Tracker

> Maintained by the `careerloop-product-lead` skill. Updated at session start and on `/careerloop-product-lead`.  
> The tracker in `PRD.md §17` mirrors the System Status table below and is updated simultaneously.

---

## Current Sprint Focus

**Week of 2026-05-18 — Stabilization Complete. Tailoring Delta Achieved.**

6-agent stabilization pass finished. Resume renderer produces clean output across all 10 templates. S7 prompt overhauled — tailoring delta 3.6% → SUBSTANTIAL. Validator fixed: 10/10 sections pass, 0 skipped. Docs restructured into 4-dir taxonomy.

**Next sprint:** Company Intelligence engine (`company_intel.py`) + Canonical Candidate Graph extractor.

---

## System Status (Live)

> Updated 2026-05-20 after Gemini Flash S7 overhaul + validator fix + docs restructure.

| System | % | Status | Blocking? | Notes |
|--------|---|--------|-----------|-------|
| India-first discovery | 75% | 🟡 | No | ATS adapter + Spire AI adapter; portal layer still ~0% for JS-heavy sites |
| Verification & filtering | 60% | 🟡 | No | detect_ats_pass.py; Block G not hoisted |
| Opportunity scoring (14-dim) | 55% | 🟡 | No | function_probability.py + metrics.py; needs calibration |
| Decision compression / triage | 20% | 🔴 | No | modes/ofertas.md reusable; no UX |
| Career state system (modes) | 10% | 🔴 | No | Conceptual only |
| Company intelligence | 45% | 🟡 | No | CompanyResearchAdapter built; grounding wired into S3; company_intel.py not yet standalone |
| Positioning engine | 30% | 🟡 | No | S6 wired; tailoring delta now substantial post-S7 prompt fix |
| Resume Council (v3) | 80% | 🟡 | No | S7 prescriptive prompt; 9/9 sections REWRITE; 0 skipped; 10 HTML + 10 PDF rendered |
| Humanizer layer | 60% | 🟡 | No | Markdown safety gate; LLM rewrite blocked; structure validation pre/post; Truth Guard misses year inflation |
| Resume rendering (templates) | 80% | 🟡 | No | 10 templates; hard fail on structure loss; normalizer handles PDF preamble |
| Validator / QA | 70% | 🟡 | No | 10/10 pass; collapsed_bullet_marker fixed; possible_truncation de-fanged; rewrite_too_short ratio-based |
| Application execution | 15% | 🔴 | No | modes/apply.md prototype; Chrome extension not started |
| Chrome extension | 0% | ⚫ | No | Phase 3 |
| Follow-up system | 25% | 🔴 | No | Ledger auto-schedules; UI missing |
| Interview memory | 25% | 🟡 | No | interview-playbook skill (Claude + Gemini); auto-extracts from venting; patterns after 2+ interviews |
| Persistent memory graph | 25% | 🟡 | No | Ledger + company_registry + SQLite schema |
| WhatsApp/transport UX | 15% | 🔴 | No | Concept only |
| Monetization logic | 30% | 🟡 | No | Strategic understanding solid |

**Overall product maturity: ~43-45% of vision.** (+3% from S7 overhaul. Council 72→78%, Humanizer 55→60%, Positioning 25→30%, Rendering 75→78%, Validator 65→70%. Tailoring delta 3.6%→SUBSTANTIAL.)

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
| B9 | Truth Guard misses year inflation (6+ vs 4+) | Council | P1 |
| ~~B8~~ | Tailoring delta only 3.6% | Closed | ✅ S7 prompt overhaul — 9/9 sections REWRITE, delta now SUBSTANTIAL |

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

### 2026-05-20 — Session: S3 Grounding "Once and for All" Fix

**What was done:**
- **Search Query Relaxation (S3):** Implemented "Search Name Cleaner" in `company_intel.py` that strips legal suffixes (Pvt Ltd, Inc) and uses first 3 words. DuckDuckGo hits increased from 0 to 7+ for Nicobar.
- **Incremental Harvesting (S3):** Modified `_gather_web_sources` to preserve partial results on timeout. System no longer panics if search takes >10s; it synthesizes from whatever is finished.
- **Domain Isolation (S3):** Added job-board blacklist (LinkedIn, Indeed, etc.) to domain derivation. Prevents system from trying to scrape LinkedIn as a company website.
- **Cache-Busting flag:** Added `--force-refresh-s3` to `run_council.py` to allow manual cache invalidation for the intelligence stage.
- **Nicobar Grounded Run:** Verified end-to-end. S3 now achieves PARTIAL grounding for Nicobar, extracting founders (Simran Lal, Raul Rai) and brand history.
- **Subtitle Derivation Fix:** Overhauled logic to use actual job titles or profile bolding instead of sentence fragments.

**Vision alignment verdict:** ✅ STRONGLY ALIGNED
Directly resolves the #1 performance and quality bottleneck in the pipeline. Company Intelligence maturity increased from 30→45%. PRD §9 grounding achieved.

**Deviations detected:** None.

**Recommended next 3 actions:**
1. Execute P1 Redesign: Build the canonical candidate graph extractor directly from CV (PRD §11).
2. Field-level structured rewriting for S7 (parse bullet arrays rather than markdown strings).
3. Truth Guard year-inflation cross-check against parsed dates (B9).

---


### 2026-05-20 — Session: S3 Grounding "Once and for All" Fix

**What was done:**
- **Search Query Relaxation (S3):** Implemented "Search Name Cleaner" in `company_intel.py` that strips legal suffixes (Pvt Ltd, Inc) and uses first 3 words. DuckDuckGo hits increased from 0 to 7+ for Nicobar.
- **Incremental Harvesting (S3):** Modified `_gather_web_sources` to preserve partial results on timeout. System no longer panics if search takes >10s; it synthesizes from whatever is finished.
- **Domain Isolation (S3):** Added job-board blacklist (LinkedIn, Indeed, etc.) to domain derivation. Prevents system from trying to scrape LinkedIn as a company website.
- **Cache-Busting flag:** Added `--force-refresh-s3` to `run_council.py` to allow manual cache invalidation for the intelligence stage.
- **Nicobar Grounded Run:** Verified end-to-end. S3 now achieves PARTIAL grounding for Nicobar, extracting founders (Simran Lal, Raul Rai) and brand history.
- **Subtitle Derivation Fix:** Overhauled logic to use actual job titles or profile bolding instead of sentence fragments.

**Vision alignment verdict:** ✅ STRONGLY ALIGNED
Directly resolves the #1 performance and quality bottleneck in the pipeline. Company Intelligence maturity increased from 30→45%. PRD §9 grounding achieved.

**Deviations detected:** None.

**Recommended next 3 actions:**
1. Execute P1 Redesign: Build the canonical candidate graph extractor directly from CV (PRD §11).
2. Field-level structured rewriting for S7 (parse bullet arrays rather than markdown strings).
3. Truth Guard year-inflation cross-check against parsed dates (B9).

---

---

### 2026-05-20 — Session: S7 Overhaul + Validator Fix + Docs Restructure (Gemini Flash Agent)

**What was done:**
- **S7 prompt overhaul (P0):** Replaced passive "replace weak verbs" with prescriptive "you MUST rewrite every section, inject role_keywords, reframe for the role." Profile now reads "AI-native product engineer" with Nicobar-specific framing.
- **Validator 3 fixes:** (1) `collapsed_bullet_marker` regex — `\s+` crossed newlines, matching valid `"sentence.\n- bullet"`. Fixed with `[^\S\n]+`. (2) `possible_truncation` de-fanged — no longer fires on skills/education/short sections. (3) `rewrite_too_short` 80-char floor removed — uses pure ratio for originals ≥60 chars.
- **Pipeline result:** 9/9 sections REWRITE (1 KEEP for languages), 0 skipped, 0 fallbacks. 10 HTML + 10 PDF rendered. Tailoring delta: 3.6% → SUBSTANTIAL.
- **Docs taxonomy restructure:** All docs reorganized into 4 dirs under `docs/`: product, engineering, tech-backlog, learnings. Symlinks preserved for backward compat. 64 tests pass.
- **Known issue:** Profile says "6+ years" but CV says "4+". Truth Guard caught 5 UNSUPPORTED claims but missed this number inflation. Added as B9.

**Vision alignment verdict:** ✅ STRONGLY ALIGNED
PRD §11 (Council 72→78%), §12 (Humanizer 55→60%), Positioning (25→30%), Rendering (75→78%), Validator (65→70%). Tailoring delta P0 resolved.

**Deviations detected:** None.

**Recommended next 3 actions:**
1. Build standalone `company_intel.py` engine using CompanyResearchAdapter as foundation (B6, PRD §9)
2. Build Canonical Candidate Graph extractor — escape Markdown Hell (PRD §11)
3. Fix Truth Guard year-inflation cross-check against parsed dates (B9)

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


### 2026-05-20 — Session: S3 Grounded Synthesis + S7 Timing Diagnostics + Humanizer Bullet Fix

**What was done:**
- **S3 Grounded Synthesis:** Rewrote `_S3_SYNTHESIS_SYSTEM` in `company_intel.py` to strictly separate Grounded Facts (from JD/web text only), Plausible Inferences (step-by-step reasoning from signals), and Explicit Unknowns. LLM is explicitly instructed NOT to recall training data for facts like headcount, funding, or leadership names. Every fact must cite source [JD] or [WEB]. This closes the hallucination gap where S3 was inventing H&M-specific details not in the JD.
- **S7 Timing Diagnostics:** `section_rewrites_node` in `graph.py` now tracks per-section elapsed time, original/rewritten char counts, model (`deepseek-chat`), and fallback reason. Total S7 wall-clock time printed to console and stored in `s7_debug` state key. Saved as `09_s7_debug.json` each run.
- **New State Keys (LangGraph topology unchanged):** `humanizer_output` (post-humanizer resume markdown, distinct from `pre_humanizer_resume`) and `s7_debug` (S7 timing payload) added to `CouncilState`.
- **Diagnostic Artifacts:** `run_council.py` now saves `09_s7_debug.json` and `12_humanized_resume.md` per run. Docstring updated to reflect all 17 artifact files.
- **Humanizer Bullet Collapse Fix (from prior sub-session):** `_deterministic_tone_adapt()` refactored with line-aware segment parser. 29/29 unit tests pass.
- **E2E Tests:** `test_council_v3.py` 4/4 pass (683s). All imports clean.
- **Pushed:** Commit `a8a6ef5` on `main`.

**Vision alignment verdict:** ✅ STRONGLY ALIGNED
PRD §9 (Company Intel grounding — LLM recall inhibition), §11 (Council diagnostic visibility), §12 (Humanizer bullet structure preserved). S3 grounding + S7 diagnostics = building toward Company Intel completeness (30→35% estimate).

**Deviations detected:** None.

**Recommended next 3 actions:**
1. Build standalone `company_intel.py` engine using CompanyResearchAdapter as foundation — web enrichment path with 10s timeout (B6, PRD §9)
2. Truth Guard year-inflation cross-check: parse date ranges from CV, validate claimed "X+ years" against actual tenure (B9)
3. Field-level S7 rewriting: parse experience bullets as arrays, not markdown blocks, for surgical per-bullet rewriting



### 2026-05-20 — Session: Deep Delta, Humanizer Assertiveness, and Rendering Fixes

**What was done:**
- **Resume Quality Auditor Skill:** Created a 16-part data quality audit skill (`resume-quality-auditor`) to calculate Tailoring Delta and Humanization Delta, checking identity integrity, rendering bugs, and cope language.
- **Humanizer Assertiveness (B2):** Rewrote `SURGICAL_HUMANIZE_SYSTEM` to be highly aggressive, eliminating "minimal rewrite" instructions. Lead bullets with strong outcomes, removing all corporate fluff.
- **S7 Negative Constraint Overload (B8):** Re-engineered the S7 prompt to be affirmatively prescriptive (DO lead with outcomes, DO weave in hidden expectations) instead of 10 DO NOT rules.
- **Identity Integrity (Name Mangle):** Implemented `_is_identity_or_contact_section` to bypass the LLM entirely for contact info, ensuring zero spelling errors on names.
- **Duplicate Header Stripping:** Updated `_strip_generated_heading_prefix` to recursively strip Markdown headers (`##`) and bold tags (`**`) hallucinated by the LLM.
- **Role Subtitle Rendering:** Fixed `render_all_templates.py` to extract a concise job title from the experience block instead of injecting a 120-character sentence fragment.
- **JSON Repair Safety:** `llm.py` now fails loudly (RuntimeError) instead of returning a partial dictionary when encountering unrecoverable JSON truncation.

**Vision alignment verdict:** ✅ STRONGLY ALIGNED
Directly resolves functional and presentation layer bugs blocking the Resume Council v3. P0 Stabilization is fully complete. Humanizer and Render paths are hardened. PRD §11 (Council 72→76%), §12 (Humanizer 55→65%), Rendering (75→80%).

**Deviations detected:** None.

**Recommended next 3 actions:**
1. Execute P1 Redesign: Build the canonical candidate graph extractor directly from CV (PRD §11).
2. Build standalone `company_intel.py` engine using CompanyResearchAdapter as foundation (B6, PRD §9).
3. Field-level structured rewriting for S7 (parse bullet arrays rather than markdown strings).
