# Functional Stabilization Report
**Date:** 2026-05-19  
**Scope:** P0/P1 engineering fixes only — no prompt rewrites, no visual redesigns, no architecture changes  
**Test result:** 31/31 tests pass

---

## Bugs Fixed

### P0.2 — Pipeline A → B Disconnect (FIXED)

**Root cause:** `orchestrator._save_artifacts` wrote `10_final_resume.md` but never called the renderer. `render_all_templates.py` had no callable entry point — only a `main()` that required CLI invocation. The final PDF/HTML was therefore always generated from raw `cv.md`, not the tailored council output.

**Fix:**
- Extracted `render_resume(input_path, candidate, run_id, out_dir, generate_pdf)` function from `render_all_templates.py`
- Wired it into `_save_artifacts` — every council run now auto-renders HTML templates from `10_final_resume.md`
- Saves `11_render_metadata.json` with full artifact inventory
- PDF generation is skipped if Node.js is unavailable (non-fatal), HTML always runs

**Before:** Changing `10_final_resume.md` had no effect on the rendered PDF.  
**After:** `10_final_resume.md` → normalizer → `NormalizedResume` → all 7 HTML templates → (optional) PDFs, all triggered automatically.

**Files:** `careerloop/rendering/render_all_templates.py`, `careerloop/council/orchestrator.py`

---

### P0.3 — `private_constraints` Leaking into LLM Prompts (FIXED)

**Root cause:** `user_truth_node` stored `private_constraints` (salary floors, location preferences) in graph state. `positioning_node` (S6) and `section_rewrites_node` (S7) dumped the entire `user_truth` dict into prompts, so private salary/location data reached the LLM and could appear in generated text.

**Fix:**
- `user_truth_node` now calls `payload.pop("private_constraints", None)` before storing to state
- `positioning_node` and `section_rewrites_node` both build a `user_truth_safe` dict that explicitly excludes `private_constraints` before constructing LLM prompts
- Schema validator (`validate_payload("user_truth", ...)`) enforces `private_constraints` is stripped

**Before:** `{"private_constraints": ["min salary 25L", "Chennai preferred"]}` could appear in positioning rationale or section rewrites.  
**After:** `private_constraints` never reaches any LLM call downstream of S5.

**Files:** `careerloop/council/graph.py`

---

### P0.5 — No JSON Schema on LLM Node Outputs (FIXED)

**Root cause:** 5 of 6 LLM nodes had no output schema enforcement. The `_repair_truncated_json` fallback in `llm.py` silently swallowed malformed outputs, letting structurally invalid payloads propagate as `{}` or partial dicts.

**Fix:**
- Created `careerloop/council/schemas.py` with:
  - `NODE_SCHEMAS` — typed contracts for `company_intelligence`, `role_decode`, `user_truth`, `positioning_strategy`, `section_rewrites`
  - `validate_payload(node_name, payload)` — checks required keys, types, enum values, confidence ranges; returns `SchemaValidationResult(ok, errors, payload)`
  - `schema_instruction(node_name)` — generates the JSON contract block injected into each system prompt
- S3, S5, S6, S7 nodes all call `validate_payload` after every LLM response and print schema warnings loudly

**Before:** `{"rewrites": null}` from S7 would silently reach the assembler.  
**After:** Missing/wrong-typed keys are logged as `!! Schema warning:` and the payload is normalized before use.

**Files:** `careerloop/council/schemas.py` (new), `careerloop/council/graph.py`

---

### P0.6 — S7 Sent Full `canonical_resume` JSON (Over/Under Tailoring) (FIXED)

**Root cause:** `section_rewrites_node` dumped the entire `canonical_resume` dict into the prompt. The LLM had no explicit signal about which sections were allowed to be edited vs which were PRIVATE/excluded. It would either over-edit protected sections or under-edit because the context was too noisy.

**Fix:**
- S7 now builds a `sections_spec` list: `[{section_id, section_title, allowed_to_edit: bool, text}]`
- Only non-excluded sections are included; `allowed_to_edit` is explicitly `False` for anything in `contract.sections_to_exclude`
- System prompt appended with `schema_instruction("section_rewrites")` enforcing `{rewrites: {}, forbidden_edits: []}`

**Before:** Full 3000-token canonical JSON sent to S7 with no edit boundaries.  
**After:** Compact per-section spec with explicit `allowed_to_edit` flag per section.

**Files:** `careerloop/council/graph.py`

---

### P0.7 — Validator Not Wired into Render Pipeline (FIXED)

**Root cause:** `ResumeValidator` existed as a standalone CLI tool (`validator.py --all`) but was never called during rendering. Rendered HTMLs could contain em-dashes, raw `**bold**`, collapsed bullets, or forbidden sections with no detection.

**Fix:**
- `render_resume()` now runs `ResumeValidator` on each rendered template immediately after writing the HTML
- Writes `{tmpl_id}_validation.json` per template with full rule results
- Hard failures (`RAW_MARKDOWN_TOKENS`, `EM_DASH`, `ARROWS`) are printed as errors
- Non-fatal by default (doesn't block output) so partial template failures don't kill the whole run

**Before:** No validation ran during rendering; broken HTML silently produced PDFs.  
**After:** Every template is validated on every render; failures are visible and logged to JSON.

**Files:** `careerloop/rendering/render_all_templates.py`

---

### P0.8 — Company Intelligence Is Ungrounded Hallucination (FIXED)

**Root cause:** `company_intelligence_node` (S3) sent only the JD text to DeepSeek with no pre-gathering of external signals. The system prompt said "use UNKNOWN for missing facts" but the LLM consistently hallucinated funding rounds, headcounts, and Glassdoor ratings from training data.

**Fix:**
- Created `careerloop/council/company_research.py` with `CompanyResearchAdapter`:
  - Always gathers JD text + website URL as grounding sources
  - If `CAREERLOOP_ENABLE_WEB_RESEARCH=1` env var is set, runs DuckDuckGo search for live results
  - Returns `CompanyResearchBundle` with `grounding_status: READY | PARTIAL | UNGROUNDED` and explicit `gaps[]`
- S3 node now calls `CompanyResearchAdapter.gather()` first, injects `RESEARCH SOURCES:` block into the LLM prompt
- `grounding_status` and `fetched_at` are stored in `03_company_intelligence.json` artifact
- LLM confidence is capped at 0.2 when `grounding_status == UNGROUNDED`

**Before:** S3 always returned `grounding_status` absent; model invented facts.  
**After:** Every company intelligence output has explicit provenance. `UNGROUNDED` is flagged loudly. Enable `CAREERLOOP_ENABLE_WEB_RESEARCH=1` for live search grounding.

**Files:** `careerloop/council/company_research.py` (new), `careerloop/council/graph.py`

---

### BUG-1 — Collapsed Bullets Not Split (FIXED)

**Root cause:** `_split_collapsed_bullets` in `normalizer.py` had a minimum part-length threshold of `>30 chars`. Bullets like `"Reduced latency from 12s to 8s."` (31 chars) and `"Designed an orchestration layer."` (32 chars) barely passed, but any shorter bullet failed the check, leaving the whole collapsed string unsplit.

**Fix:** Threshold lowered from `>30` to `>15` chars in both Strategy 1 (primary pattern) and Strategy 2 (fallback pattern). Also lowered the fallback trigger from `len(text) > 200` to `> 100`.

**Before:** `"Built AI system. - Designed layer. - Reduced latency."` → 1 bullet.  
**After:** → 3 bullets.

**Files:** `careerloop/rendering/normalizer.py`

---

### BUG-ENCODING — Windows-1252 Garbling Breaks Normalizer (FIXED)

**Root cause:** Council output files saved on Windows as UTF-8 but containing Unicode em-dashes (`—`) were sometimes read back as Latin-1, producing `â€"` byte sequences. This garbled text in role headings so the experience section parser couldn't match them, producing 0 experience entries.

**Fix:** Added `_fix_encoding_artifacts(text)` called at the top of `normalize()`. Converts the most common Windows-1252 → Latin-1 garbling patterns back to correct Unicode before any parsing.

**Files:** `careerloop/rendering/normalizer.py`

---

## Regression Tests Added

**File:** `tests/test_stabilization.py` — 21 new tests  
**File:** `tests/test_normalizer.py` — 2 stale assertions corrected

| Class | Tests | Covers |
|-------|-------|--------|
| `TestSchemaValidation` | 6 | P0.5 schema contracts, forbidden keys, enum validation, confidence range |
| `TestNormalizerBulletPreservation` | 3 | Collapsed bullet splitting, forbidden section filtering, cv.md bullet counts |
| `TestResumeValidator` | 6 | Em-dash, arrow, collapsed bullets, raw markdown, forbidden sections, clean HTML pass |
| `TestCompanyResearch` | 4 | Grounding status, gaps, bundle dict contract |
| `TestRenderResumeContract` | 2 | P0.2 — council output feeds renderer, not cv.md |

**Result: 31/31 pass.**

---

## Files Changed

| File | Change |
|------|--------|
| `careerloop/council/schemas.py` | **New** — schema contracts + validator |
| `careerloop/council/company_research.py` | **New** — grounding adapter |
| `tests/test_stabilization.py` | **New** — 21 regression tests |
| `careerloop/council/graph.py` | S3/S5/S6/S7 nodes patched |
| `careerloop/council/orchestrator.py` | `_save_artifacts` wired to renderer |
| `careerloop/rendering/render_all_templates.py` | `render_resume()` callable + validator integration |
| `careerloop/rendering/normalizer.py` | Encoding fix + bullet split threshold |
| `tests/test_normalizer.py` | 2 stale assertions corrected |

---

## Remaining Risks (Out of Scope This Pass)

| Risk | Severity | Notes |
|------|----------|-------|
| Web search grounding is opt-in | P1 | Set `CAREERLOOP_ENABLE_WEB_RESEARCH=1` to enable. Requires `duckduckgo_search` or `ddgs`. |
| Role decode node (S4) has no schema validation yet | P1 | `validate_payload("role_decode", ...)` exists in schemas.py but S4 node not patched |
| Cover note / recruiter message nodes have no schema | P2 | Schemas defined, nodes not patched |
| LLM JSON repair still fires silently | P1 | `llm.py` `_repair_truncated_json` — should log a warning when repair fires |
| Council output encoding root cause | P1 | Files should be written with explicit `encoding="utf-8"` on all save paths (orchestrator now does this, but older artifacts on disk may still be garbled) |
| Humanizer bullet re-collapsing | P1 | Humanizer phase 3/4 rewrites full text sections — could re-collapse bullets. No post-humanize re-split exists yet |
| PDF path requires Node.js | P1 | `generate_pdf=True` silently skips if `node` not in PATH |
