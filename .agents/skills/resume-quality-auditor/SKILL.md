# Resume Quality Auditor

## Description
Performs a rigorous 16-part data quality audit on Resume Council pipeline outputs using multi-agent orchestration. It calculates the semantic "Delta" between versions to prove tailoring depth.

## Instructions
1. **Target Directory:** Identify the latest run in `output/council/{candidate}/{job_id}/`.
2. **Versions to Audit:** 
   - **V_ORIGINAL:** `test data/{candidate}_resume_*.md` (or from snapshot)
   - **V_TAILORED:** `output/council/{candidate}/{job_id}/12_pre_humanizer_resume.md`
   - **V_FINAL:** `output/council/{candidate}/{job_id}/10_final_resume.md`
3. **Delta Calculation (Mandatory):**
   - **Tailoring Delta:** Compare V_ORIGINAL to V_TAILORED. Count changed bullet points and repositioned sections. Report as % of total content changed.
   - **Humanization Delta:** Compare V_TAILORED to V_FINAL. Identify exactly where "AI-stiff" language was replaced with human builder language.
   - **Cope Detection:** Identify any superlative adjectives or fluff added by the LLM that wasn't in the original.
4. **Identity & Structure Audit (Sub-agent: codebase_investigator):**
    - **Part 1 (Identity Integrity):** Verify candidate name spelling matches the input exactly. No typos in "KEEP" sections.
    - **Part 2 (Structural Cleanliness):** Scan for duplicated headers (e.g., `## EDUCATION` followed by `** ## EDUCATION **`).
    - **Part 3 (Markdown Assembly):** Ensure `10_final_resume.md` is syntactically valid and has no raw JSON artifacts.
5. **Semantic Tailoring Audit (Sub-agent: codebase_investigator):**
    - **Part 4 (Metric Preservation):** Trace all metrics from `01_canonical_resume.json`. 100% must be preserved.
    - **Part 5 (Keyword Depth):** Count hits for target keywords (e.g., OTB, Jersey) in Final vs Master.
    - **Part 6 (Action Verbs):** Verify verbs are outcome-oriented (Built, Shipped) not process-oriented (Supported, Assisted).
    - **Part 7 (Humanizer Impact):** Diff `12_pre_humanizer` and `10_final`. Report if it actually improved prose.
    - **Part 8 (Slop Detection):** Fail if `spearheaded`, `leveraged`, `synergy`, or `passionate` are found.
6. **Rendering & Template Audit (Sub-agent: generalist):**
    - **Part 9 (Placeholder Scan):** Full grep for `{{` in `rendered/*.html`. Fail if any unrendered tags exist.
    - **Part 10 (Premium Blocks):** Verify `SIDEBAR_` and `PREMIUM_` content exists in premium templates.
    - **Part 11 (Education Fragmentation):** Check if education entries are combined into clean blocks.
    - **Part 12 (Sidebar Integrity):** Scan for empty `<li>` tags or layout gaps in sidebars.
    - **Part 13 (Role Subtitle):** Ensure subtitle is a CONCISE job title (e.g., "Category Manager"), not a long sentence.
    - **Part 14 (CSS Stability):** Check for overlapping divs or broken responsive layouts.
7. **System Integrity Audit (Sub-agent: codebase_investigator):**
    - **Part 15 (PDF Health):** Confirm all 9 PDFs exist in the folder and are > 100KB.
    - **Part 16 (Link Audit):** Verify LinkedIn and Portfolio links work and are not truncated.

## Acceptance Criteria
- Full 16-part report generated with **Tailoring Delta %**.
- Status (PASS/FAIL) assigned to each part.
- Detailed breakdown of differences between Original, Tailored, and Final versions.
