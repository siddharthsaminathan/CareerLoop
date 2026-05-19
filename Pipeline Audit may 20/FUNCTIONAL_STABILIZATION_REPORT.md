# CareerLoop — Functional Stabilization Report

**Date:** 2026-05-19  
**Status:** In progress  
**Scope:** P0/P1 engineering fixes only. No prompt rewrites.

---

## 1. Current Path Tracing

### Q: "Which file/object feeds final PDF rendering?"

**Answer: It depends on which pipeline the user triggers.**

| Pipeline | PDF source | Path |
|----------|-----------|------|
| **A — Council** | `output/council/{person}/{job}/10_final_resume.md` | `orchestrator.py` → `graph.py` → `assembly_node` → humanizer → `10_final_resume.md` → **manual** call to `render_all_templates.py --input 10_final_resume.md` → normalizer → HTML templates → `generate-pdf.mjs` |
| **B — career-ops skill** | Raw `cv.md` (project root) | Agent reads `cv.md` at runtime → generates HTML inline from `templates/cv-template.html` → `generate-pdf.mjs` |

**The disconnect:** Pipeline A generates a tailored `10_final_resume.md` but Pipeline B never reads it. Pipeline B always re-reads raw `cv.md`. There is no automatic handoff.

### Detailed Call Chain — Pipeline A (Council → Render)

```
1. run_council_v3.py / orchestrator.py:run()
   └─ graph.py:get_council_graph().invoke(initial_state)
      ├─ parse_node()       → compiler.py:ResumeCompiler.parse_markdown(master_cv)
      ├─ contract_node()    → compiler.py:ResumeCompiler.build_contract()
      ├─ company_intel()    → _call(_S3_SYSTEM, ...) → DeepSeek
      ├─ role_decode()      → _call(_S4_SYSTEM, ...) → DeepSeek
      ├─ user_truth()       → _call(_S5_SYSTEM, ...) → DeepSeek
      ├─ positioning()      → _call(_S6_SYSTEM, ...) → DeepSeek
      ├─ section_rewrites() → _call(_S7_SYSTEM, ...) → DeepSeek
      ├─ truth_guard()      → truth_guard.py:TruthGuard.validate() + repair()
      └─ assembly_node()    → compiler.py:ResumeCompiler.assemble()
                            → _call(_COVER_NOTE_SYSTEM, ...)
                            → _call(_RECRUITER_DM_SYSTEM, ...)
                            → humanizer.py:Humanizer.humanize() × 3
                            → compiler.py:ResumeCompiler._verify_links_preserved()
                            → ApplicationPack.resume_markdown ← HUMANIZED MARKDOWN

2. orchestrator.py:_save_artifacts()
   └─ Writes: output/council/{person}/{job}/10_final_resume.md
              (this is pack["resume_markdown"])

3. render_all_templates.py (MUST BE CALLED MANUALLY)
   └─ reads 10_final_resume.md via --input flag
   └─ normalizer.py:normalize(text) → NormalizedResume
   └─ builds placeholder dict from NormalizedResume fields
   └─ fills 7 HTML templates from careerloop/rendering/templates/
   └─ calls generate-pdf.mjs per template
   └─ validates HTML for forbidden characters (em dashes, arrows, **)
```

### Detailed Call Chain — Pipeline B (career-ops skill)

```
1. User pastes JD URL or text
2. Agent reads: cv.md, modes/_shared.md, modes/_profile.md, config/profile.yml
3. Agent evaluates JD (Blocks A–G) inline
4. Agent reads: cv.md AGAIN for PDF generation
5. Agent reads: templates/cv-template.html
6. Agent generates HTML by replacing {{placeholders}}
7. Agent writes HTML to /tmp/cv-{candidate}-{company}.html
8. Agent runs: node generate-pdf.mjs {input} {output}
```

**Pipeline B never calls normalizer.py.** It does raw markdown → HTML conversion inline in the agent's context, not through the Python normalizer.

### Source of Truth per Output

| Output | Source of truth | File |
|--------|----------------|------|
| Council `10_final_resume.md` | Assembly of humanized section rewrites | `graph.py:assembly_node()` |
| Council rendered HTML/PDF | `10_final_resume.md` → NormalizedResume | `render_all_templates.py` |
| career-ops skill PDF | Raw `cv.md` (re-read every time) | Agent inline generation |
| Showcase HTML | User-provided data (no resume source) | `.claude/skills/showcase-builder/SKILL.md` |

---

## 2. Bugs Found

### BUG-1: Collapsed bullets in Council output

**File:** `output/council/siddharth/nicobar-final/10_final_resume.md`  
**Lines:** 61 (Emote), 77 (Positive Integers)

The council/humanizer collapses multi-line bullets into single lines joined by ` - `:
```
- Built and iterated a production AI system... - Designed and scaled... - Drove core system...
```
Should be:
```
- Built and iterated a production AI system...
- Designed and scaled...
- Drove core system...
```

**Root cause:** The humanizer's `_adapt_tone()` or `_surgical_humanize()` receives the full markdown text and the LLM (or deterministic processing) joins bullets onto one line. Historical FUCKUP #3 (`" ".join()`) was fixed for paragraphs but bullets still collapse.

**Normalizer mitigation:** `normalizer.py:_split_collapsed_bullets()` has a `COLLAPSED_BULLET_RE` pattern that splits on `. - [A-Z]` — this DOES handle the collapsed format, so rendered output should be correct IF the normalizer runs. But Pipeline B doesn't use the normalizer.

### BUG-2: Collapsed skills table in Council output

**File:** `output/council/siddharth/nicobar-final/10_final_resume.md`, line 30  
All table rows are on one line:
```
| Category | Technologies ||----------|-------------|| **Programming** | Python, SQL ||...
```

**Root cause:** Same humanizer flattening. The `normalizer.py` handles this with `if "||" in table_text: table_text = re.sub(r"\|\|", "|\n|", table_text)` — another mitigation that works IF the normalizer runs.

### BUG-3: Pipeline A → PDF disconnected

No automatic path from `10_final_resume.md` to PDF. User must manually run `render_all_templates.py`.

### BUG-4: Pipeline B reads raw cv.md including private sections

`test data/siddharth_resume_0426.md` lines 80-93 contain "Target Roles" and "Deal-breakers". These would appear in a Pipeline B PDF unless the agent happens to omit them. No programmatic guard.

### BUG-5: No schema validation on LLM node outputs

Systems 3, 5, 6 pass LLM output directly to state without schema check. Malformed JSON propagates silently.

### BUG-6: section_rewrites contract is loose

S7 must infer allowed sections from the contract JSON blob. No per-section `allowed_to_edit` flag.

### BUG-7: Company Intelligence is ungrounded

S3 uses pure LLM recall. No web search, no API, no source attribution.

---

## 3. Fixes Applied

*(Updated as fixes are implemented)*

| # | Fix | Files Changed | Tests Added | Status |
|---|-----|---------------|-------------|--------|
| P0.2 | Connect council output to renderer | | | PENDING |
| P0.3 | Fix bullet preservation | | | PENDING |
| P0.4 | Enforce normalized model | | | PENDING |
| P0.5 | Schema validation on LLM nodes | | | PENDING |
| P0.6 | Section rewrites contract | | | PENDING |
| P0.7 | Final validators | | | PENDING |
| P0.8 | Company intelligence grounding | | | PENDING |

---

## 4. Remaining Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Humanizer re-collapsing bullets after fix | MEDIUM | Humanize per-field, not full markdown |
| DeepSeek schema non-compliance | HIGH | Retry with repair prompt, fail loudly |
| Private sections leaking via Pipeline B | MEDIUM | Normalizer FORBIDDEN_KEYWORDS already exists, must enforce |
| batch-prompt.md in Spanish | LOW (for now) | Not blocking P0; flag for P2 |
