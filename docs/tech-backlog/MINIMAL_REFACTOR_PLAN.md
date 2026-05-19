# Minimal Refactor Plan — CareerLoop Resume Council

**Date:** 2026-05-19  
**Scope:** Bugs only. No architecture changes, no prompt rewrites, no new infrastructure.  
**Inputs read:** `FUNCTIONAL_STABILIZATION_REPORT.md`, `CAREERLOOP_REDESIGN_IMPLEMENTATION_PLAN.md`, `graph.py`, `truth_guard.py`, `compiler.py`, `07_section_rewrites.json`, `10_final_resume.md`

---

## Guiding Principle

Ship correct output from the pipeline that already exists. Every fix must make the current Varsha/H&M run produce better output — measured against the actual `10_final_resume.md` and rendered HTML — without changing graph topology, state schema keys, or the LLM provider. If a fix cannot be expressed as a change to an existing function, it is out of scope for this plan.

---

## Must Fix (P0 — breaks correctness)

### P0-A — Truth Guard repairs UNSUPPORTED ownership claims it should not touch

**What breaks:** `truth_guard_node` in `graph.py` (line 522) passes UNSUPPORTED claims to `guard.repair()`. Inside `truth_guard.py::_repair_evidence_claim`, ownership claims classified UNSUPPORTED are already correctly returned unchanged (`return original`, line 776). However, the call site in `graph.py` unconditionally calls `guard.repair(text, claims)` whenever any claim is flagged UNSUPPORTED, EXAGGERATED, or FABRICATED. This means that if a section has one FABRICATED claim and several UNSUPPORTED ownership claims, `repair()` is invoked and all of the UNSUPPORTED ownership claims are re-evaluated in the backward pass — they return `original` correctly, but the FABRICATED claim repair can shift string positions and corrupt surrounding valid text via the position-based replacement loop in `repair()`.

More critically, the flagged list fed to `repair()` includes UNSUPPORTED entries. The `_repair_evidence_claim` path does return `original` for UNSUPPORTED ownership — but UNSUPPORTED `quantified_achievement` and `percentage` claims have their numbers stripped (lines 778-783), which incorrectly removes verified metrics like "₹3.5 lakh" that are grounded in the original CV but scored UNSUPPORTED due to Jaccard mismatch between the LLM-paraphrased evidence bank and the resume text.

**File/function:** `careerloop/council/truth_guard.py::TruthGuard.repair` and `careerloop/council/graph.py::truth_guard_node`

**Fix:** In `truth_guard_node` (graph.py line 522), change the repair trigger condition from `c.risk_level in ("UNSUPPORTED", "EXAGGERATED", "FABRICATED")` to `c.risk_level in ("EXAGGERATED", "FABRICATED")` only. UNSUPPORTED claims should be logged as warnings (already done at line 548-543) but must never enter the repair path. Separately, add an UNSUPPORTED-specific log line so they remain visible.

**Effort:** 1 hour (2-line change + regression test update)

---

### P0-B — Cover note and recruiter DM system prompts are hardcoded to Siddharth/Nicobar/Emote

**What breaks:** `_COVER_NOTE_SYSTEM` and `_RECRUITER_DM_SYSTEM` in `graph.py` (lines 568-577) contain `EXAMPLE JSON OUTPUT` blocks with hardcoded candidate-specific content: "I built Emote from zero to 450+ users", "At Omnex, I built production multi-agent AI", "For Nicobar's AI Product Engineer role", "I shipped production AI from zero at Emote (agentic quality management, multi-agent orchestration)". When Varsha runs the council, DeepSeek sees these as examples and anchors its cover note output to Siddharth's profile, producing Nicobar/Emote references in Varsha's cover note. This is a correctness bug, not a quality issue.

**File/function:** `careerloop/council/graph.py`, `_COVER_NOTE_SYSTEM` constant (line 568) and `_RECRUITER_DM_SYSTEM` constant (line 573)

**Fix:** Replace the hardcoded candidate-specific JSON examples with role-neutral placeholder examples that demonstrate structure without referencing any real person, company, or metric. Keep the instruction language identical. Examples should use `<CANDIDATE_ACHIEVEMENT>`, `<COMPANY>`, `<ROLE>` placeholders.

**Effort:** 1 hour (prompt text edit + manual verification with one Council run)

---

### P0-C — `_preprocess_plaintext_cv` does not split intra-section run-ons for job title + date concatenations

**What breaks:** `compiler.py::_preprocess_plaintext_cv` (lines 213-268) handles four boundary patterns in Pass B but misses the "JobTitle Date" pattern where a job title and start date are concatenated without a space or newline. From the Varsha sample: `"Category Manager – Fashion Nov 2025 – Present"` arrived concatenated as `"Category Manager – FashionNov 2025"` in earlier pipeline runs. The current code handles `PresentBuilt` (rule 2) and `2024Chennai` (rule 3) but not `FashionNov` (title word immediately followed by a month abbreviation like Jan/Feb/Mar/Apr/May/Jun/Jul/Aug/Sep/Oct/Nov/Dec). This causes job title and dates to parse into the same AST text node, which means section headings in the experience section lose their date structure.

**File/function:** `careerloop/council/compiler.py::ResumeCompiler._preprocess_plaintext_cv`

**Fix:** Add a Pass B rule 5: split on any non-whitespace character followed immediately by a three-letter month abbreviation followed by a space and a 4-digit year. Regex: `r'(\S)(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})'` → `r'\1\n\2 \3'`. Insert after rule 4 (location token split), before the tidy-up block.

**Effort:** 2 hours (regex + tests against Varsha fixture and two additional plain-text CV samples)

---

## Should Fix (P1 — improves reliability)

### P1-A — S4 Role Decode node has no schema validation

**What degrades:** `role_decode_node` in `graph.py` (lines 249-267) calls `_call()` and stores `result.payload` directly into state with no `validate_payload("role_decode", payload)` call. `schemas.py` has a contract for `role_decode` (confirmed in `FUNCTIONAL_STABILIZATION_REPORT.md` — schema exists but node not patched). If DeepSeek returns a malformed role decode (missing `must_haves`, wrong type on `confidence`), S5 and S6 silently consume the partial dict.

**File/function:** `careerloop/council/graph.py::role_decode_node`

**Fix:** Add `vresult = validate_payload("role_decode", payload)` and use `vresult.payload` as the return value, identical to the pattern used in S3/S5/S6/S7.

**Effort:** 30 minutes (3-line addition, copy pattern from `user_truth_node`)

---

### P1-B — LLM JSON repair fires silently

**What degrades:** `careerloop/council/llm.py::_repair_truncated_json` (referenced in `FUNCTIONAL_STABILIZATION_REPORT.md` remaining risks) swallows malformed LLM output silently. When repair fires, the payload may be structurally incomplete but schema-valid enough to pass downstream. This produces subtle positioning or rewrite errors that are invisible in the run log.

**File/function:** `careerloop/council/llm.py` — the `_repair_truncated_json` function (or its caller `complete_json`)

**Fix:** Add a single `print(f"  !! JSON repair fired for {label} — output may be truncated")` log line when repair is invoked. Do not change the repair logic itself.

**Effort:** 30 minutes

---

### P1-C — Humanizer re-collapses bullets after S7 per-section rewrites

**What degrades:** `assembly_node` in `graph.py` calls `humanizer.humanize(final_resume, mode="resume", ...)` on the assembled resume markdown (line 678). The humanizer processes full-text sections and can re-collapse bullets that S7 correctly kept separated. `FUNCTIONAL_STABILIZATION_REPORT.md` lists this as remaining risk: "Humanizer phase 3/4 rewrites full text sections — could re-collapse bullets. No post-humanize re-split exists yet."

**File/function:** `careerloop/council/graph.py::assembly_node`, `careerloop/council/humanizer.py`

**Fix:** After `resume_result = humanizer.humanize(...)` in `assembly_node`, call `_count_markdown_bullets(final_resume)` and `_count_markdown_bullets(resume_result.humanized_text)` and log a warning if the count drops. Do not block — log only. This makes the regression visible without requiring a Humanizer rewrite. The `_count_markdown_bullets` helper is already defined in `graph.py` at line 90.

**Effort:** 1 hour (add post-humanizer bullet count comparison + warning print)

---

### P1-D — Council output encoding not always UTF-8

**What degrades:** `FUNCTIONAL_STABILIZATION_REPORT.md` notes that orchestrator now saves with `encoding="utf-8"` but older artifacts on disk may contain garbled `â€"` sequences. The normalizer has `_fix_encoding_artifacts()` as mitigation but the root cause (inconsistent write encoding) can still affect new Council runs on Windows if any save path omits the encoding parameter.

**File/function:** `careerloop/council/orchestrator.py` — all `open(..., "w")` calls

**Fix:** Audit `orchestrator.py` for any `open(..., "w")` without `encoding="utf-8"` and add the parameter. Run a grep for `open(` in the council directory.

**Effort:** 1 hour (audit + add encoding params + one regression test)

---

## Do NOT Touch (explicit freeze list)

These components work correctly as of the 31/31 passing test baseline. Any change risks regression without compensating benefit within this plan's scope.

| Component | Reason to freeze |
|---|---|
| `StateGraph` topology in `graph.py` (node names, edge order) | Works end-to-end on Varsha/H&M. Changing topology risks breaking LangGraph checkpoint serialization. |
| `CouncilState` TypedDict keys | Downstream code (`orchestrator.py`, `assembly_node`, tests) depend on exact key names. |
| `TruthGuard._extract_claims` regex patterns | Well-tested, false positive rate is acceptable. Changing patterns risks breaking the 6 `TestSchemaValidation` tests. |
| `TruthGuard._classify_year_claim`, `_classify_skill_claim` | Correctly verified in Varsha run. YEAR_EXAGGERATION_MARGIN=2 is a deliberate design choice. |
| `TruthGuard._repair_evidence_claim` UNSUPPORTED ownership branch | Already returns `original` correctly — do not change the repair function itself. Only change the call site in `graph.py`. |
| `ResumeCompiler.parse_markdown()` mistune AST path | The mistune AST parser is stable and handles all Varsha sections correctly. |
| `PreservationContract` / `contract_node` logic | Contract correctly excludes private sections. |
| `NormalizedResume` dataclass fields | Templates depend on these field names. |
| `render_all_templates.py::render_resume()` entry point | P0.2 fix from stabilization — correctly wired, do not rewire. |
| `careerloop/council/schemas.py` node contracts | 21 tests depend on these. |
| `careerloop/council/company_research.py` | P0.8 fix from stabilization — grounding adapter is working. |
| `careerloop/rendering/normalizer.py` bullet split threshold | BUG-ENCODING and BUG-1 were fixed in stabilization. Do not adjust thresholds again without a new failing test. |
| DeepSeek as LLM provider | No provider migration in this plan. |
| `generate-pdf.mjs` and Node.js PDF path | Works when Node is present, gracefully skips when absent. |

---

## LLM vs Deterministic Boundary

| Component | Current | Should be | Reason |
|---|---|---|---|
| S1 Parse (`parse_node`) | Deterministic (mistune AST) | Keep deterministic | Parsing must be 100% reproducible |
| S2 Contract (`contract_node`) | Deterministic (rule-based) | Keep deterministic | Exclusion rules must be auditable |
| S3 Company Intelligence (`company_intelligence_node`) | LLM + deterministic grounding adapter | Keep LLM for synthesis; make grounding mandatory not optional | Grounding is partially opt-in via env var — should default to PARTIAL from JD always |
| S4 Role Decode (`role_decode_node`) | LLM | Keep LLM | Role interpretation requires language understanding |
| S5 User Truth (`user_truth_node`) | LLM | Keep LLM for paraphrase; **make year calculation deterministic** | `total_years_experience` is computable from dates in `canonical_resume` — should not be LLM-guessed |
| S6 Positioning (`positioning_node`) | LLM | Keep LLM | Strategy synthesis requires judgment |
| S7 Section Rewrites (`section_rewrites_node`) | LLM per-section loop | Keep LLM; structure is already compact (P0.6 fixed) | Already sending per-section spec with `allowed_to_edit` flag — correct boundary |
| S7.5 Truth Guard (`truth_guard_node`) | Deterministic (regex + Jaccard) | Keep deterministic; **fix call site for UNSUPPORTED** | Repair logic is sound; only the call site trigger is wrong (P0-A above) |
| S8 Cover Note + Recruiter DM | LLM | Keep LLM; **fix example anchoring** (P0-B above) | Templates should be role-neutral; LLM fills from context |
| S8 Assembly (`assembly_node`) | Deterministic merge | Keep deterministic | Assembly must be lossless |
| S8 Humanizer | LLM (full-text) | Keep for now; **add post-humanizer bullet count check** (P1-C) | Full Humanizer redesign is P3 in the architecture plan; add detection before redesign |
| Cover note example prompts | Hardcoded to Siddharth/Nicobar | Make role-neutral (P0-B) | Examples anchor LLM output to wrong candidate |
| `total_years_experience` calculation | LLM-provided in S5 | Should be cross-checked against parsed dates in `canonical_resume` | Prevents EXAGGERATED year claims at source rather than at repair |

---

## Ship Order

Fix these in strict sequence. Each fix is independently testable. Do not batch them.

1. **P0-A: Fix Truth Guard repair trigger** — `graph.py::truth_guard_node` line 522. Change UNSUPPORTED out of the repair set. Run existing truth guard tests. This is the highest-correctness-risk issue: it currently strips verified Indian Rupee metrics from real resumes.

2. **P0-B: Neutralize cover/DM example prompts** — `graph.py::_COVER_NOTE_SYSTEM` and `_RECRUITER_DM_SYSTEM`. Replace hardcoded examples. Verify by running a Council pass for Varsha and confirming no Nicobar/Emote/Omnex text appears in the cover note output.

3. **P1-A: Wire S4 schema validation** — `graph.py::role_decode_node`. 3-line addition. Run full test suite to confirm no regression.

4. **P0-C: Add month-boundary split to `_preprocess_plaintext_cv`** — `compiler.py`. Add regex rule 5. Test against Varsha fixture (raw concatenated CV text) and a second plain-text sample. Confirm `07_section_rewrites.json` shows correct section splits.

5. **P1-B: Log JSON repair when it fires** — `llm.py`. Add one print statement. No test change needed.

6. **P1-C: Add post-humanizer bullet count warning** — `assembly_node` in `graph.py`. Log-only, non-blocking. Add one test asserting the log fires on a fixture where a bullet count drops.

7. **P1-D: Audit orchestrator encoding** — `orchestrator.py`. Add `encoding="utf-8"` to any write path that lacks it. Run on Windows to confirm no garbled characters in new output artifacts.

---

## Success Criteria

The refactor is done when ALL of the following pass:

1. **Truth Guard UNSUPPORTED non-repair:** Run Varsha/H&M Council. Grep `08_truth_guard_report.json` for UNSUPPORTED ownership entries. Confirm their text appears unchanged in `10_final_resume.md`. Metrics like `₹3.5 lakh`, `80+ orders`, `45% gross margins` must survive verbatim.

2. **Cover note persona isolation:** Run Varsha/H&M Council. `grep -i "nicobar\|emote\|omnex" output/council/varsha/*/11_cover_note.md` returns 0 matches.

3. **S4 schema warnings visible:** Introduce a malformed S4 fixture (remove `must_haves` key). Confirm `!! Schema warning (role_decode):` appears in console output and Council does not crash.

4. **Plain-text CV date parsing:** Feed the raw concatenated Varsha CV text (pre-preprocessing) through `_preprocess_plaintext_cv`. Assert that `"Category Manager – FashionNov 2025"` (or equivalent run-on) produces `"Category Manager – Fashion\nNov 2025"` in the output.

5. **LLM repair visibility:** Inject a broken JSON response in a test fixture for `complete_json`. Assert that `!! JSON repair fired` appears in captured stdout.

6. **Bullet count warning fires:** Create a fixture where humanizer collapses 6 bullets to 4. Assert the `!!` bullet count warning is printed. Assert the run does not crash.

7. **Full test suite:** `python -m pytest tests/ -q` passes with 31+ tests. No regressions from stabilization baseline.

8. **Varsha/H&M golden run:** Full end-to-end Council run completes without errors. `10_final_resume.md` contains all three employers, correct education entries, and no Nicobar/Emote/Omnex references. `11_render_metadata.json` exists and lists at least one rendered HTML template.
