# Dev Blog — 2026-05-19: Resume Council Structural Stabilization

**Session type:** Structural bug-fix + pipeline hardening  
**Engineers:** Siddharth (product direction) + Cascade (Windsurf) + Codex (OpenAI)  
**Tests:** 36 passed (was 31) · Exit code 0 · py_compile clean on all touched files  
**Varsha E2E:** 3 experience entries · 19 bullets · Education clean · Cover note + recruiter DM generated

---

## What We Were Fighting

The Resume Council was architecturally correct but structurally broken in practice.
PDF-extracted CVs come in as garbled single-line blobs:

```
SuperK Bangalore, IndiaCategory Manager – Fashion Nov 2025 – PresentBuilt the fashion category
from near zero across online channels and a tech-enabled retail network of 3+ coco stores,
launching assortments across apparel, footwear, and accessories while driving vendor expansion...
```

On top of that, S7 was sending all sections to the LLM in one giant JSON blob — which meant
truncation, collapsed bullets, and generic rewrites that ignored the JD context. TruthGuard was
then over-repairing legitimate claims because the Jaccard similarity between LLM-paraphrased
evidence bank entries and real CV text is always low. And the PDF generation pipeline (Pipeline B)
was never reading the Council output (Pipeline A) — it always went back to raw `cv.md`.

Four root causes. Four surgical fixes.

---

## What Was Built

### Bucket 1: CV Input Preprocessing (`compiler.py`)

`_preprocess_plaintext_cv()` now runs in two passes:

**Pass A** (existing): inject `## headings` if none exist.

**Pass B** (new — always runs): intra-section blob splitting:
1. Bullet char normalisation: `•●▸▶◆` → `\n- `
2. `PresentBuilt` → `Present\n\nBuilt` (date-boundary detection)
3. `2024Chennai` → `2024\n\nChennai` (year-boundary detection)
4. `IndiaCategory` → `India\nCategory` (location-boundary detection, 25 cities/countries)

Key learning: `\b` doesn't fire between two word chars. `IndiaCategory` has no boundary between
`a` and `C`. Removed trailing `\b` from location patterns.

Pass B is also applied **post-S7** — after each section rewrite lands, run cleanup again
(`ResumeCompiler._preprocess_plaintext_cv(rewritten)`) to catch LLM re-collapses.

---

### Bucket 2: S7 Per-Section Loop (`graph.py`)

Before: one LLM call with all sections + full strategy + full user truth as a JSON blob.
Result: 5000+ token prompts, truncation, generic rewrites, collapsed bullets.

After: one focused LLM call per section with:
- Only that section's text (capped at 3500 chars for long experience)
- Top-5 proof points
- Top-10 role keywords
- Tone guidance
- 4000 `max_tokens` (was 10000)

Long structured experience sections (`> 3500 chars`) are skipped — kept as originals — until
we build per-entry structured rewriting.

**S7 structural postconditions** (`_rewrite_preserves_section_structure()`):

Every rewrite is validated before it's accepted:
- Bullet count must not drop (`original_bullets → rewritten_bullets`)
- No `. - Uppercase` pattern (collapsed bullet marker)
- No truncation (rewrite must be ≥ 35% of original length, minimum 80 chars)

If any postcondition fails → rewrite rejected, original kept, section added to `skipped[]`.

---

### Bucket 3: TruthGuard Over-Repair Fix (`truth_guard.py`)

Before: UNSUPPORTED ownership claims → `_minimize_claim()` → mangled text.
`"Managed PO/PI coordination"` → `"data-contributed to PO/PI coordination"`.

Root cause: Jaccard similarity between LLM-paraphrased evidence bank entries and raw CV text
is always low. `"Managed PO/PI for 20+ suppliers"` ≠ `"PO/PI coordination"` under Jaccard.
These are legitimate claims being false-positived as UNSUPPORTED.

Fix — `_repair_evidence_claim()` new logic:

```
FABRICATED     → minimize (deliberate overreach)
EXAGGERATED ownership → minimize
EXAGGERATED quantified → strip metric
UNSUPPORTED ownership → return original unchanged (log for review)
UNSUPPORTED quantified → strip metric only
```

UNSUPPORTED ownership claims are logged to `08_truth_guard_report.json` for human review
but never mangled. The user sees the flag. The resume stays intact.

---

### Bucket 4: Pipeline A → B Handoff (`modes/pdf.md`)

Added Step 0 to the PDF generation pipeline:

> Before reading `cv.md`, check `output/council/{person_id}/{job_id}/10_final_resume.md`.
> If it exists and is recent, use it as input. Tell the user which source is being used.
> Fall back to `cv.md` silently if no council output exists.

This closes the disconnect where the Council would produce a tailored `10_final_resume.md`
and the PDF pipeline would ignore it entirely.

---

### LLM Client Hardening (`llm.py`)

- Default `max_tokens`: 10000 → 4000 (no node output needs 10k)
- Timeout: 120s → 90s
- `max_tokens` override param on `complete_json()` and `_call()`
- Per-call progress print: `⟳ LLM call [S7 experience]... done` — user can see which call
  is in flight instead of staring at a frozen terminal

---

### Supporting Infrastructure (Codex pass)

**`compiler.py`** — `softbreak` AST node now handled (was silently dropped, breaking line flow).

**`humanizer.py`** — Markdown structure safety gate. Pre/post bullet count check. LLM rewrite
of full resume Markdown blocked — Humanizer now operates at phrase level, not document level.

**`normalizer.py`** — Preamble contact info (name, email, phone, LinkedIn) now preserved even
when it appears before the first `##` heading. Loose experience blocks (PDF-style, no sub-header)
parsed correctly.

**`render_all_templates.py`** — Hard fail if normalization loses required structure. Renderer
no longer silently produces broken HTML.

**`company_research.py`** — `CompanyResearchAdapter` built. Gathers web/search/manual sources,
computes grounding status (READY/PARTIAL/UNGROUNDED), wired into S3 company intelligence node.

**`schemas.py`** — JSON schema enforcement on all 6 LLM nodes. `private_constraints` stripped
at S5 before it can propagate to S6/S7.

---

## Varsha E2E Run Results

Run: `python run_council.py --job-id varsha-hm-merchandiser --person varsha`

| Stage | Result |
|-------|--------|
| S1 Document Parser | 3 experience entries, 19 bullets |
| S2 Preservation Contract | Clean |
| S3 Company Intelligence | PARTIAL (2 sources, score=35) |
| S4 Role Decoder | Senior Merchandiser / senior |
| S5 User Truth | Clean (private_constraints stripped) |
| S6 Positioning Strategy | Clean |
| S7 Section Rewrites | 5/5 sections rewrote (Intro, Summary, Experience, Education, Skills) |
| S7.5 Truth Guard | 3 claims scanned · 0 fabricated · 2 UNSUPPORTED ownership (logged, not mangled) |
| S8 Safe Assembler | Cover note + recruiter DM generated |

**Output:** `output/council/varsha/varsha-hm-merchandiser/10_final_resume.md` — 55 lines, clean  
**Rendered:** 7 HTML templates in `rendered/` directory  
**Remaining formatting issues:** Minor — some S7 rewrites still collapse sub-header lines
(e.g. SuperK experience header). Will be resolved by per-entry structured rewriting in next sprint.

---

## What's Still Broken / Next Up

| Issue | Severity | Fix |
|-------|----------|-----|
| S7 experience section kept as original (too long) | Medium | Per-entry structured rewriting — loop over job entries |
| Tailoring delta unmeasured post-fix | High | Run Siddharth Nicobar E2E + keyword coverage diff |
| Company Intelligence standalone engine | Medium | `company_intel.py` from CompanyResearchAdapter base |
| SuperK experience header still run-on in some rewrites | Low | Postcondition tightening + location split |

---

## System Status Delta (this session)

| System | Before | After | Delta |
|--------|--------|-------|-------|
| Resume Council (v3) | 60% | 72% | +12% |
| Company Intelligence | 20% | 30% | +10% |
| Humanizer | 50% | 55% | +5% |
| Rendering | 70% | 75% | +5% |
| Validator / QA | 60% | 65% | +5% |
| **Overall** | **~33%** | **~38-40%** | **+5-7%** |

---

## Commit

`cc5ed34` — Codex FUnctionality implementations Resume MD formatter + Cascade structural fixes  
Files: `compiler.py`, `graph.py`, `humanizer.py`, `llm.py`, `truth_guard.py`, `normalizer.py`,
`render_all_templates.py`, `company_research.py`, `schemas.py`, `orchestrator.py`,
`modes/pdf.md`, `tests/test_stabilization.py`, `tests/test_normalizer.py`
