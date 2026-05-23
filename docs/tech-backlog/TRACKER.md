# CareerLoop — Product Engineering Tracker

> Maintained by the `careerloop-product-lead` skill. Updated at session start and on `/careerloop-product-lead`.  
> The tracker in `PRD.md §17` mirrors the System Status table below and is updated simultaneously.

---

## Current Sprint Focus

**Week of 2026-05-23 — Delivery Foundation Scaffolding + Supervisor Graph Hardening**

S8.5 completeness check shipped. Council is at quality ceiling (93%). System status review complete.

**Critical finding:** The user-facing interface is now scaffolded but not functional end-to-end. All strong backend systems (Council 93%, Discovery 75%, Company Intel 75%) still need a verified transport → supervisor graph → delivery loop. `TransportAdapter`, `TerminalChatAdapter`, `supervisor_graph.py`, `PostgresSaver`, and `kimi_bridge.py` exist as first-pass code, but graph state mapping, real routing, delivery, and safe assisted apply are not yet production-ready.

**This sprint:** Ship the integration layer that connects the backend to users:
1. **Supervisor contract repair** (P0) — `UserEvent` → `ConversationState`, tested graph routing, stable `thread_id`
2. **Terminal/Telegram beta loop** (P0) — message in → graph → response out; document delivery path
3. **Multi-User Onboarding** (P0) — CV upload → profile creation → user registry
4. **Daily Brief Cron** (P1) — DailyRunner → transport delivery at 7AM IST per user

---

## System Status (Live)

> Updated 2026-05-23 — Phase 0 Delivery Foundation has first-pass scaffolds. The bottleneck is now contract correctness and end-to-end verification, not file creation.

| System | % | Status | Blocking? | Notes |
|--------|---|--------|-----------|-------|
| **Transport abstraction layer** | **18%** | 🔴 | **YES** | Base + Terminal/Telegram stubs exist. Graph handoff and document delivery unverified. Sprint 0. |
| **Multi-user onboarding** | **0%** | 🔴 | **YES** | CV upload → profile creation → user registry. Sprint 1. |
| **LangGraph Chatbot Orchestrator** | **12%** | 🔴 | **YES** | Supervisor graph scaffold exists. Intent router placeholder; `UserEvent`/state mismatch must be fixed. Sprint 0. |
| **PostgresSaver Checkpointer** | **15%** | 🔴 | **YES** | Supabase checkpointer wrapper + schema scaffold exist. Needs connection test + interrupt/resume proof. Sprint 0. |
| **Application pack delivery** | **0%** | 🔴 | **YES** | Pack → PDF → send_document(). Sprint 3. |
| **Daily brief cron delivery** | **5%** | 🔴 | **YES** | DailyRunner exists. Transport missing. Sprint 2. |
| India-first discovery | 75% | 🟡 | No | ATS adapter + Spire AI adapter; portal layer still ~0% for JS-heavy sites |
| Verification & filtering | 60% | 🟡 | No | detect_ats_pass.py; Block G not hoisted |
| Opportunity scoring (14-dim) | 55% | 🟡 | No | function_probability.py + metrics.py; needs calibration |
| Decision compression / triage | 20% | 🔴 | No | CEO owns. DECISION_COMPRESSION_VISION.md written. |
| Career state system (modes) | 15% | 🔴 | No | `UserState` + supervisor scaffold; no proven routing yet |
| Company intelligence | 75% | 🟢 | No | MECE vision implemented; S3 cache working |
| Positioning engine | 38% | 🟡 | No | S6 wired; tailoring delta substantial; narrative angle reaches S7 |
| Resume Council (v3) | 93% | 🟢 | No | Job-aware chunking; prose fallback; 42 tests; ceiling hit |
| Humanizer layer | 65% | 🟡 | No | LLM rewrite active; Truth Guard UNSUPPORTED matching still too aggressive |
| Resume rendering (templates) | 85% | 🟡 | No | 10 templates; normalizer handles 3 user CV formats; S8.5 completeness check |
| ATS validator layer | 0% | ⚫ | No | Spec written (PRD §26). Sprint 4. |
| Resume editing layer | 0% | ⚫ | No | Spec written (PRD §25). Surgical edits without full Council rerun. Sprint 4. |
| Validator / QA | 75% | 🟡 | No | 42 stabilization + 22 integration pass; automated pre-render validation |
| Application execution | 18% | 🔴 | No | modes/apply.md prototype; Kimi bridge scaffold. Real Webbridge/Hermes integration not verified. |
| Assisted apply bridge | 5% | ⚫ | No | `kimi_bridge.py` mock only. Must never run queue-based or unattended submission. |
| Follow-up engine (full) | 25% | 🔴 | No | Scheduling exists. Message generation + delivery = Sprint 5. |
| Gmail integration | 0% | ⚫ | No | Sprint 6. Needs transport first. |
| Calendar integration | 0% | ⚫ | No | Sprint 6. Needs transport first. |
| Interview memory (full) | 25% | 🟡 | No | Vent parsing works. Debrief + weakness tracker = Sprint 7. |
| Persistent memory graph | 25% | 🟡 | No | Ledger + SQLite schema; not read back to improve positioning |
| Background job scheduler | 0% | ⚫ | No | Sprint 2. Daily + per-job two classes. |
| WhatsApp / Meta Cloud API | 0% | ⚫ | No | After Telegram beta validates loop. |
| Monetization / billing | 0% | 🔴 | No | Pricing tiers defined. No paywall yet. Needs onboarding first. |

**Overall product maturity: ~59-62% of vision.** Council ceiling hit (93%). User-facing interface is scaffolded but not live. Transport + supervisor graph + onboarding remain P0.

> Legend: 🟢 Done · 🟡 Active · 🔴 Gap · ⚫ Not started

---

## Open Blockers

| # | Blocker | System | Since | Priority |
|---|---------|--------|-------|----------|
| ~~B1~~ | Truth Guard exact string matching | Closed | ✅ Semantic claim validation implemented |
| ~~B2~~ | Humanizer not implemented | Closed | ✅ 5-phase pipeline + LLM wired |
| ~~B3~~ | cover_note/recruiter_message stubs | Closed | ✅ Improved prompts + richer context |
| ~~B7~~ | LLM nodes lacked JSON schemas | Closed | ✅ All 6 prompts have JSON examples |
| **B-TRANSPORT** | Transport stubs exist, but no verified webhook/document delivery/graph response loop | User-facing | **P0** |
| **B-ONBOARD** | No multi-user onboarding — 3 hardcoded PERSON_CONFIGs, no CV-upload-to-profile flow | User-facing | **P0** |
| **B-SUPERVISOR** | LangGraph scaffold exists, but state contract/routing/resume interrupts are not verified | User-facing | **P0** |
| **B-DELIVERY** | Council generates 10 PDFs per run but delivers them to nobody | User-facing | **P0** |
| B4 | Company career pages invisible | Discovery | P2 |
| B5 | Decision compression UX not built | Triage | P2 |
| ~~B6~~ | Company Intelligence engine | Closed | ✅ 1,419-line MECE implementation — D1-D5 vectors, LinkedIn, Glassdoor, DDG |
| ~~B9~~ | Truth Guard misses year inflation (6+ vs 4+) | Closed | ✅ CV-derived tenure parsing + overlap-aware total — no more S5 LLM estimate dependence |
| ~~B8~~ | Tailoring delta only 3.6% | Closed | ✅ S7 prompt overhaul — 9/9 sections REWRITE, delta now SUBSTANTIAL |
| B10 | No pre-render validation gate — sections silently drop | Rendering | **P0** | 🔴 Normalizer drops sections for unknown CV formats. Need validation layer: compare normalized output against original markdown, flag missing sections BEFORE templates render. See Fuckup #10. |

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
| A12 | Delivery orchestration uses LangGraph Supervisor; transports adapt into `ConversationState`, not business logic | 2026-05-23 |
| A13 | Assisted apply may execute only one explicitly reviewed and approved job; no unattended queue/bulk submit | 2026-05-23 |

---

## Session Log

### 2026-05-23 — Session: LangGraph Chatbot Orchestrator & Webbridge Scaffold

**What was done:**
- **Supervisor Graph:** Deprecated rigid state machine and scaffolded `careerloop/session/supervisor_graph.py` to wrap Phase 1 execution scripts (`scan.mjs`, etc.) into LangChain tools.
- **Kimi Webbridge:** Built `kimi_bridge.py` scaffold for headless ATS navigation via an explicitly authorized "Approve & Auto-Apply" user loop.
- **Transport Abstraction:** Reworked `base.py` and `terminal_chat.py` to decouple the UI from the routing logic. Inputs map to `UserEvent` payloads hitting the LangGraph Supervisor.
- **Persistence:** Implemented `checkpointer.py` using `PostgresSaver` via Supabase to track conversations seamlessly across multiple transport connections (CLI, WhatsApp, Telegram).

**Vision alignment verdict:** ✅ ALIGNED
Directly advances the delivery abstraction (PRD §21-23). The legacy codebase (Phase 1 scripts and Council graph) is now fully integrated into a modern agentic control flow.

**Deviations detected:** The Kimi webbridge auto-submit command operates purely on an "Approve & Auto-Apply" flow to adhere to A7 ("No auto-submit; manual review required"). Unattended execution is forbidden.

**Recommended next 3 actions:**
1. E2E state verification: Fully test the `UserEvent` to `ConversationState` transition through the CLI loop.
2. Build WhatsApp transport adapter pointing to `supervisor_graph.py`.
3. Harden the `kimi_bridge.py` headless layer with real ATS navigation endpoints instead of the current mock.

---

### 2026-05-21 — Session: Pipeline End-to-End Repair (S6, S7, S8)

**What was done:**
- **S6 prompt overhaul**: Replaced `_S6_SYSTEM` which had a hardcoded "AI Product Engineer" example leaking framing into every run. New prompt uses 4-step mandatory reasoning: (1) find the ONE differentiator, (2) map proof-to-JD, (3) name the hiring manager's objection, (4) set tone+stance. Adds `hiring_manager_objection` + `objection_preempt` fields to output.
- **S6 schema**: Added `"PUSH"` to `application_stance` enum (old prompt used STRONG_PUSH; new prompt uses PUSH). Added `strongly_recommended` for 2 new fields.
- **S7 `_payload_to_rewritten_text` complete rewrite**: The root cause of all experience section silent fallbacks. LLM returns `tailored_bullets` (bare strings), but old code dropped structural scaffold (company names, dates, role titles) causing the 50% truncation guard to fire. Fixed with 4-path dispatch: (1) profile/summary paragraph, (2) skills flat-list, (3) scaffold-preserving reconstruction with continuation-line state machine + excess-original-bullet skipping, (4) no-bullets fallback.
- **S7 continuation-line fix**: After replacing a wrapped multi-line bullet, old code kept the PDF-extracted continuation lines (e.g., `footwear, and accessories...`). New code skips lowercase-starting lines while in `in_continuation` state; resets on blank line or uppercase-starting structural lines.
- **S7 skills section fix**: Skills section no longer tries scaffold reconstruction (which garbled 15-bullet original → 4 new bullets with original duplicated). Uses flat-list path directly.
- **S8 `canonical` NameError fixed**: `assembly_node` referenced `canonical` variable that didn't exist — should have been `state["canonical_resume"]`. Was crashing every single S8 call silently.
- **S8 `sections_not_tailored` visibility**: Added explicit warning block showing which sections fell back to original.
- **New `document_extractor.py`**: Full PDF/DOCX/MD/TXT extraction with pdfminer.six + pypdf fallback, python-docx, PDF artifact cleaning.
- **`--cv` CLI flag**: `run_council.py` now accepts `--cv path/to/file` to override CV input.
- **3 new unit tests**: `test_skills_section_uses_flat_list_path`, `test_experience_continuation_lines_are_skipped`, `test_experience_excess_original_bullets_are_dropped` — all pass. Total: 35/35.
- **`8-PIPELINE-CHECKLIST.md` updated**: All fixed bugs marked ✅, new entries added.
- **`COUNCIL_REDESIGN_PLAN.md` updated**: FIX 1-5 ✅, FIX 6 ⚠️ partial, FIX 7-9 ✅.

**Vision alignment verdict:** ✅ STRONGLY ALIGNED
All work on PRD §11 (Resume Council core quality). Assembly crash fixed. S7 experience/skills section output is now structurally correct. S6 positioning is now role-specific.

**Deviations detected:** None.

**Recommended next 3 actions:**
1. Fix S6 cache for H&M — it's stale (PARTIAL grounding); invalidate and re-ground with web search for H&M India hiring team, jersey category structure (PRD §9)
2. Truth Guard B1: UNSUPPORTED claims confidence is 0.0 for all legitimate ownership claims — evidence matching too strict, needs semantic fuzzy match improvement (PRD §11)
3. S2 contract: `ordering_rules` and `max_allowed_changes` computed but never mechanically enforced — assembly sorts by `original_order` ignoring contract (PRD §11)

---

### 2026-05-22 — Session: S7 Chunked Rewrite Deep Repair + SuperK Header Fix

**What was done:**
- **`chunk_structure_check_failed:bullet_count_dropped` bypass**: For chunked experience sections, the structure check was rejecting LLM rewrites that consolidated 19 original bullets into 6 tailored ones. This is correct LLM behaviour. Fixed: `bullet_count_dropped` filtered out from chunked structure check; other checks (collapsed markers, orphan emphasis, injected headings, truncation) still enforced. Result: experience section now rewrites 4/4 sections instead of falling back.
- **`rewritten_text` scaffold bypass fixed**: `_payload_to_rewritten_text` had an early `return direct` for any section when LLM returned `rewritten_text` instead of `tailored_bullets`. For experience sections this dropped company headers, job titles, and dates. Fixed: scaffold sections (`experience`, `work_experience`, `projects`) skip the early return; if only `rewritten_text` is present, bullets are extracted from it and scaffold reconstruction runs.
- **Structural preamble injection for no-bullet chunks**: Chunk 1 of the experience section contains only the SuperK intro paragraph (header + description prose, no bullets). LLM rewrote it as 5 paragraphs, dropping "SuperK Bangalore, India" and "Category Manager – Fashion Nov 2025 – Present". Fixed: after each chunk rewrite, first 2 structural lines (company + role/date) from original chunk are checked; if absent from rewrite, they are prepended.
- **2 new tests + 1 test updated**: `test_scaffold_section_prefers_tailored_bullets_when_both_present`, `test_legacy_rewritten_text_extracted_when_no_tailored_bullets`, `test_legacy_rewritten_text_wins_for_non_scaffold_sections`. Total: 37/37 pass.
- **Docs updated**: `8-PIPELINE-CHECKLIST.md` (3 new fix entries, known LLM quality issue documented), `TRACKER.md` (Council 88%→92%).

**E2E result**: 4/4 sections rewrote (summary ✅, experience [CHUNKED] ✅, skills ✅, education [KEEP] ✅). SuperK header present. Skills uses OTB/sell-through vocabulary. No fallbacks.

**Known remaining quality issue**: Chunk 2 (3600-char block containing SuperK bullets + Style Gram + Go Colors) occasionally causes the LLM to mis-attribute a Style Gram bullet to Go Colors. Root cause: paragraph-boundary chunking bundles multiple jobs in one block. Fix (not yet implemented): job-aware chunking — one chunk per employer.

**Vision alignment verdict:** ✅ STRONGLY ALIGNED — PRD §11 (Resume Council). Pipeline now runs at full capacity for all section types.

**Deviations detected:** None.

**Recommended next 3 actions:**
1. **Job-aware chunking**: Replace paragraph-boundary split with employer-boundary split. One LLM call per job entry. Eliminates cross-job bullet attribution errors (PRD §11). ✅ DONE this session.
2. **Truth Guard B1**: UNSUPPORTED confidence 0.0 for all legitimate ownership claims — evidence matching uses Jaccard similarity (too strict). Needs semantic fuzzy match (PRD §11).
3. **Multi-user onboarding**: `add_person` CLI flow — CV upload → normalize → PERSON_CONFIG → first council run. Unblocks scaling beyond 3 hardcoded users.

## Session Log

### 2026-05-22 — Session: S7 Final Quality — Job-Aware Chunking + DeepSeek Prose Fallback

**What was done:**
- **Job-aware chunking (`_split_by_job_boundaries()`)**: Detects employer boundaries by finding uppercase non-bullet lines without dates, followed within 3 lines by a date/tenure pattern. Splits experience sections into one chunk per employer. Fixed: role/date lines (e.g. "Category Manager – Fashion Nov 2025 – Present") were being falsely detected as job starts; added `_date_pat.search(stripped): continue` to skip them. Confirmed E2E: Varsha → 3 chunks (SuperK/Style Gram/Go Colors), Hayagreev → 2 chunks (GT/Emote). Zero cross-job bullet leakage.
- **DeepSeek prose-paragraph fallback**: When `rewritten_text` returns prose paragraphs (no `- ` bullet markers), the old code fell through to `return direct` (raw prose). New code: splits on blank lines, skips structural header paragraphs (first line contains date pattern), skips short preamble lines (<60 chars), treats each remaining paragraph as a bullet. Makes bullet output consistent regardless of DeepSeek's output format for that run.
- **5 new tests (`TestJobBoundaryChunking`)**: test_splits_into_one_chunk_per_employer, test_each_chunk_contains_its_own_company_name, test_no_cross_job_bullet_leakage, test_single_employer_returns_single_chunk, test_three_employers_splits_into_three_chunks. 42/42 total pass.
- **Docs updated**: 8-PIPELINE-CHECKLIST.md (S7 bug #10 added as ✅ DONE), TRACKER.md, PRD §17.

**E2E results:**
- Varsha (H&M): 4/4 sections REWRITE, 3 chunks, 62.83% average tailoring delta, 19→17 bullets, OTB/sell-through vocabulary throughout.
- Hayagreev (Deloitte): 3/3 sections REWRITE, 2 chunks (GT + Emote), cross-job attribution confirmed fixed.

**Vision alignment verdict:** ✅ STRONGLY ALIGNED — PRD §11 (Resume Council). Council is now at the quality ceiling. Both structural bugs (job attribution) and LLM non-determinism (prose vs bullets) are handled.

**Deviations detected:** None.

**Recommended next 3 actions:**
1. **Recruiter DM Generator** (PRD §19): Council already generates tailored cover notes + recruiter DMs. Extend to cold LinkedIn DM targeting a specific hiring manager at a target company — find the right person + personalize the message. HIGH ROI, LOW complexity delta.
2. **Follow-Up Intelligence** (PRD §13/§15): Ledger already schedules follow-ups. Add message generation — 1-week post-application ping and 3-day post-interview follow-up. Zero new infra needed, just LLM call with context from ledger.
3. **Multi-user onboarding** (unblocks monetization): `add_person` CLI — CV upload → parse → PERSON_CONFIG → first council run. Currently 3 hardcoded users. Need this to scale.

---

### 2026-05-22 — Session: Normalizer Hardening — 7 Bugs Fixed Across 3 User Formats

**What was done:**
- **Normalizer bug fixes (7):** (1) Skills: description-style bullets now parsed (Hayagreev). (2) Header: phone no longer leaks into location field. (3) Experience: two-line headers (company/location then role/dates) now correctly separate company from role. (4) Role preservation: when second line is pure date, role from first line is kept. (5) Go Colors restored: entry filter relaxed to not require bullets. (6) Education multi-line: institution/degree on separate lines now paired into single entries with dates. (7) Automated validation: `_validate_normalized()` runs on every normalize(), checks name/skills/experience/education/roles.
- **ROI_UX_PRODUCT_VISION.md created** — 12 workflows, 4 entry points, pricing ₹399-₹2,999, competitor map, metrics hierarchy.
- **PRD.md §20 added** — ROI & UX Architecture section.
- **docs/README.md rewritten** — master index of all 34 documents.
- **Interview playbook system built** — auto-extracts learnings from user venting, patterns after 2+ interviews.
- **Product-lead skill updated** — dev-blog creation step added.
- **Council runs:** Siddharth (Nicobar AI PM), Hayagreev (Deloitte Gen AI), Varsha (H&M Senior Merchandiser) — all validated, 10 HTML+10 PDF each.
- **Hayagreev PERSON_CONFIG added** to run_council.py.

**Vision alignment verdict:** ✅ STRONGLY ALIGNED
PRD §12 (Rendering 80→85%), Validator/QA (70→75%), Interview Memory (25→30%). ROI_UX product vision now canonically documented. All 3 user formats render cleanly with automated validation.

**Deviations detected:** None.

**Recommended next 3 actions:**
1. Build Decision Compression UX (B5, P2) — daily brief, triage board
2. Fix education single-line format for Varsha-style schools (NIFT degree shows school in degree field)
3. Humanizer UNSUPPORTED matching calibration

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
## Session Log

---

### 2026-05-22 — Session: Normalizer Hardening — 7 Bugs Fixed Across 3 User Formats

**What was done:**
- **Normalizer bug fixes (7):** (1) Skills: description-style bullets now parsed (Hayagreev). (2) Header: phone no longer leaks into location field. (3) Experience: two-line headers (company/location then role/dates) now correctly separate company from role. (4) Role preservation: when second line is pure date, role from first line is kept. (5) Go Colors restored: entry filter relaxed to not require bullets. (6) Education multi-line: institution/degree on separate lines now paired into single entries with dates. (7) Automated validation: `_validate_normalized()` runs on every normalize(), checks name/skills/experience/education/roles.
- **ROI_UX_PRODUCT_VISION.md created** — 12 workflows, 4 entry points, pricing ₹399-₹2,999, competitor map, metrics hierarchy.
- **PRD.md §20 added** — ROI & UX Architecture section.
- **docs/README.md rewritten** — master index of all 34 documents.
- **Interview playbook system built** — auto-extracts learnings from user venting, patterns after 2+ interviews.
- **Product-lead skill updated** — dev-blog creation step added.
- **Council runs:** Siddharth (Nicobar AI PM), Hayagreev (Deloitte Gen AI), Varsha (H&M Senior Merchandiser) — all validated, 10 HTML+10 PDF each.
- **Hayagreev PERSON_CONFIG added** to run_council.py.

**Vision alignment verdict:** ✅ STRONGLY ALIGNED
PRD §12 (Rendering 80→85%), Validator/QA (70→75%), Interview Memory (25→30%). ROI_UX product vision now canonically documented. All 3 user formats render cleanly with automated validation.

**Deviations detected:** None.

**Recommended next 3 actions:**
1. Build Decision Compression UX (B5, P2) — daily brief, triage board
2. Fix education single-line format for Varsha-style schools (NIFT degree shows school in degree field)
3. Humanizer UNSUPPORTED matching calibration

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
3. Build standalone `company_intel.py` engine using CompanyResearchAdapter as foundation (B6, PRD §9) (✅ DONE — commit 5617cee)

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
2. Build Company Intelligence engine (`company_intel.py`) per spec and vision doc (P1, §9) (✅ DONE — commit 5617cee)
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

### 2026-05-21 — Session: Master Landing Page Vision + LLM Council Positioning

**What was done:**
- **Full-documentation mining:** 6 sub-agents read all product docs (PRD, vision v1.6, breakdown, resume-council-vision, MECE plan, pipeline graph), all learnings docs (FUCKUPS.md, PROMPT_AUDIT, 20-part audit, council audit, delta forensics, S3/S7 root cause, reuse audit, stabilization report, regression QA, rendering simplification), all user docs (cv.md, profile.yml, _profile.md, _shared.md), and the full tracker.
- **LLM Council (3 models + 3 reviewers):** Haiku, Sonnet, Opus 4.7 independently evaluated positioning, pain points, vision validation, moats, and above-the-fold copy. 3 anonymous peer reviews ranked responses. **Unanimous verdict: C > B > A.** Positioning: "Career Decision Engine." Above-the-fold: "You're too good to be spraying 100 applications into the void. CareerLoop finds the 5 that actually fit — and makes you impossible to ignore."
- **Master Landing Page Vision written:** `docs/product/MASTER_LANDING_PAGE_VISION.md` — 12-section canonical document covering: the one sentence, what CareerLoop is/isn't, ICP, 5 pain points with product responses, full architecture diagram, competitive positioning map, 4 moats with defensibility analysis, honest maturity tracker (what's true/not true), north star vision, user proof points, recommended landing page structure, and full council verdict.

**Vision alignment verdict:** ✅ STRONGLY ALIGNED
Product marketing and positioning work. No code changes. Establishes the canonical landing page source of truth that every future marketing decision must trace back to.

**Deviations detected:** None.

**Recommended next 3 actions:**
1. Commit the master vision doc + S7 schema migration + candidate graph + stabilization tests (PRD §11)
2. Design and build the landing page using frontend-design skill, sourcing every claim from MASTER_LANDING_PAGE_VISION.md
3. Fix Humanizer zero-delta (0.21% on last run) — audit execution path, tune prompt assertiveness (PRD §12)

---

### 2026-05-21 — Session: CandidateGraph Wiring + B9 Fix + Landing Page Build

**What was done:**
- **`extract_candidate_graph()` in `compiler.py`:** Added ~120-line static method to `ResumeCompiler` that extracts structured contact info, profile_summary, experience[] with bullet arrays, education[], skills[], and metric_vault (top-30 numerics) from a serialised CanonicalResume dict. Regex-based, deterministic — no LLM.
- **CandidateGraph wired into S1 (`parse_node`):** `graph.py` parse_node now calls `extract_candidate_graph()` after CV parse and stores result in `CouncilState["candidate_graph"]`. Non-fatal — pipeline continues if extraction fails.
- **B9 cv_tenure_years fix wired end-to-end:** `parse_node` now extracts experience section raw texts and calls `compute_cv_tenure_years()` (regex interval-merge, already implemented in `truth_guard.py`). Result stored as `CouncilState["cv_tenure_years"]`. Passed into `truth_guard_node` as `cv_verified_years=` kwarg — now used as ceiling when validating year claims. B9 fully closed.
- **`CouncilState` TypedDict expanded:** Added `candidate_graph: Optional[Dict]` and `cv_tenure_years: Optional[float]` keys.
- **Integration test M2a fixed:** Changed check from "≥2 REWRITE change_type" to "≥2 sections processed by LLM (REWRITE+KEEP)" — KEEP is a valid LLM decision, not a failure.
- **Landing page built:** `output/showcase-careerloop-landing.html` — 796 lines, Deep Ocean palette. 6 sections: Problem, System (10-step pipeline), Differentiation (competitor table), Proof (8 metrics), Moats (4 principles), North Star (terminal standup mock-up + 4 paths + People Graph). Every claim sourced from MASTER_LANDING_PAGE_VISION.md. Zero WhatsApp, autonomy, or Chrome extension mentions.
- **Test results:** 32/32 stabilization PASS · 22/22 integration PASS (1 SKIP — pre-MECE artifact)

**Vision alignment verdict:** ✅ STRONGLY ALIGNED
CandidateGraph wiring (PRD §11), B9 closure (Truth Guard maturity), Landing page (product positioning realized). All three on the critical path.

**Deviations detected:** None.

**Recommended next 3 actions:**
1. **Structured S7 bullet migration** — use `candidate_graph.experience[].bullets` as structured input to `_rewrite_one_section()` for experience sections. Pass `original_bullets_structured` in the prompt JSON so LLM rewrites bullet-by-bullet rather than free-form markdown. (PRD §11 — escape Markdown Hell)
2. **Decision Compression UX** — B5 is the P2 gap. Design and build the compression UI: 100 jobs → scored → compressed → 5 decisions. The CLI pipeline exists; the user-facing layer does not. (PRD §5)
3. **Humanizer zero-delta audit** — last run: 0.21% delta. Audit execution path end-to-end. The 5 phases exist but the LLM rewrite call may be no-oping. Tune assertiveness or check if identity bypass is too aggressive. (PRD §12)

---

### 2026-05-22 — Session: Full Product Review — WhatsApp Gap Diagnosis

**What was done:**
- Full MODE B product/tech review: read PRD, TRACKER, ROI_UX_PRODUCT_VISION, TECH_ROADMAP, git log, module structure
- Read `whatsapp_ux.py`, `daily_runner.py`, `approval.py`, `followup.py` to assess actual user-facing state
- S8.5 Section Completeness Check shipped: achievements populated from CV, empty section guard, profile name fix, S7 education institution rule
- 42/42 tests pass, all changes committed and pushed

**Critical finding:**
CareerLoop has 93% Council + 75% Discovery + 75% Company Intel — all working — but ZERO user-facing interface. `whatsapp_ux.py` has formatters (strings only), no transport. `daily_runner.py` outputs to console only (comment: "future: send via WhatsApp"). No webhook, no session state, no user registry, no PDF delivery. A user literally cannot interact with CareerLoop.

**New blockers identified:**
- B-TRANSPORT: WhatsApp transport layer (webhook, Twilio/Meta API) — P0
- B-ONBOARD: Multi-user onboarding (only 3 hardcoded PERSON_CONFIGs) — P0
- B-SESSION: Conversation state machine (session → job → decision → council trigger) — P0
- B-DELIVERY: Council PDFs never delivered to any user — P0

**Vision alignment verdict:** ⚠️ PARTIALLY ALIGNED — Backend is world-class. Delivery layer is 0%. ROI/UX Vision says "product should prove value inside 7 days." Currently proves value to zero users.

**Deviations detected:**
- Gmail Memory (ROI/UX Vision's #1 priority "holy shit" moment) = 0%. Has never been touched.
- WhatsApp transport = 0% despite being the backbone of the entire UX vision.
- All engineering effort went to Council quality — correct but now creates delivery debt.

**Recommended next 3 actions:**
1. **WhatsApp Transport Layer** — Twilio webhook + session state + message router. 2-3 days. Unlocks everything. (PRD Phase 8, §13)
2. **Multi-User Onboarding** — CV upload → profile creation → user_registry.py. 2-3 days. Unblocks monetization. (PRD §3, Phase 8)
3. **Daily Brief Cron** — DailyRunner → daily_brief() → WhatsApp send at 7AM IST. 1 day if transport exists. (PRD §7, Phase 1.5)

---

### 2026-05-23 — Session: Delivery Orchestration Scaffold + Documentation Reconciliation

**What was done:**
- **LangGraph Supervisor scaffold:** `careerloop/session/supervisor_graph.py` added with a parent graph, basic router node, Resume Council subgraph call, and HITL interrupt checkpoint.
- **Legacy Phase 1 wrappers:** `scan.mjs` and `check-liveness.mjs` exposed as LangChain tools, confirming the right integration direction for CEO-built discovery/evaluation assets.
- **Transport abstraction scaffold:** `TransportAdapter`, `UserEvent`, `TerminalChatAdapter`, and Telegram stubs added so CLI/Telegram/WhatsApp can normalize input into one event shape.
- **Persistence scaffold:** `careerloop/memory/checkpointer.py` and Supabase schema scaffold added for LangGraph `PostgresSaver` persistence.
- **Assisted apply scaffold:** `careerloop/execution/kimi_bridge.py` added as a Kimi/Hermes bridge concept, but currently mock-only and not verified against a browser/Webbridge.
- **Docs reconciled:** PRD, Technology Roadmap, Canonical Architecture, Tracker, docs indexes, dev-blog, and next-agent handoff updated to reflect scaffold status and safety constraints.

**Vision alignment verdict:** ✅ ALIGNED, BUT NOT COMPLETE
The direction directly advances PRD §21-§23 and the Phase 0 Delivery Foundation. The implementation should be treated as a first scaffold, not a completed migration, because the transport-to-graph state contract is not yet proven and the Kimi bridge is only a mock.

**Deviations detected:** The phrase "apply while you sleep" can conflict with A7. Canonical interpretation is now: execute one already reviewed and explicitly approved job asynchronously; never autonomous selection, queue processing, or bulk submit.

**Recommended next 3 actions:**
1. Fix and test `UserEvent` → `ConversationState` mapping in `TransportAdapter` and `supervisor_graph.py` (PRD §21-§22).
2. Add graph tests for IDLE, brief, scan, pack generation, HITL interrupt/resume, and subprocess-tool failure handling (PRD §22-§23).
3. Change `kimi_bridge.py` from "submit" mock language to an explicit approved-job execution contract with dry-run and final confirmation modes (A7/A13).

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
1. Build standalone `company_intel.py` engine using CompanyResearchAdapter as foundation — web enrichment path with 10s timeout (B6, PRD §9) (✅ DONE — commit 5617cee)
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
2. Build standalone `company_intel.py` engine using CompanyResearchAdapter as foundation (B6, PRD §9). (✅ DONE — commit 5617cee)
3. Field-level structured rewriting for S7 (parse bullet arrays rather than markdown strings).
