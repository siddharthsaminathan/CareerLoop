# Dev Blog — 2026-05-20: Deep Delta, Humanizer Assertiveness, and Rendering Fixes

**Session type:** Deep architectural alignment + rendering fixes + humanizer overhaul
**Engineers:** Siddharth (product direction) + Gemini CLI 

---

## What We Were Fighting

After the initial stabilization pass, we realized the pipeline was still fundamentally flawed. While it ran without crashing, the semantic output was identical to the input.
1. The **Humanizer** was acting as a passive word filter rather than an active editor. If there were no explicit "slop" words, it did nothing. The output still sounded like an AI.
2. The **S7 Section Rewriter** was paralyzed by 10 strict "DO NOT" constraints and only 1 vague "DO", making it default to keeping the original text.
3. The **Design Templates** (specifically `compact-sidebar-premium` and `design-brand-compact`) were ignoring the candidate's data because the `render_all_templates.py` Python script didn't know about their custom placeholders (like `{{PREMIUM_SUMMARY_BLOCK}}`).
4. The **Role Subtitle** was hardcoded to "AI Product Engineer" for everyone.
5. The **Identity Integrity** was flawed because S7 was "keeping" the contact info but introducing typos (e.g. spelling "Sathyanarayanan" as "Sathyanaranan").

## What Was Built

### 1. 20-Part Pipeline Alignment Audit
We stopped building features and audited the entire pipeline against the V3 Architecture vision. I produced `docs/20_PART_ARCHITECTURAL_AUDIT.md` which lists the 20 exact reasons the outputs felt like "AI slop" or were missing entirely.

### 2. The "Cope-Killer" Humanizer
Rewrote `SURGICAL_HUMANIZE_SYSTEM` in `humanizer_prompts.py` to be aggressively outcome-focused. We eliminated the "minimal rewrite" mindset. Now the prompt explicitly demands: "Rewrite with ASSERTIVE impact... Lead every bullet with a concrete result or a high-velocity action verb."

### 3. Rendering Logic & Subtitle Fix
Fixed `render_all_templates.py`:
- Added `PREMIUM_` and `SIDEBAR_` placeholders to match the new HTML templates.
- Overhauled `_derive_role_subtitle()` to derive a concise job title (e.g. "Senior Merchandiser") rather than a 120-character sentence fragment.

### 4. S7 Header Stripping & Identity Bypass
- **Duplicate Headers Fixed:** `_strip_generated_heading_prefix` was updated to recursively remove all `**` and `##` artifacts the LLM accidentally wraps around its output.
- **Identity Bypass:** Implemented `_is_identity_or_contact_section` to ensure the Intro block never hits the LLM, preserving the candidate's name and contact info exactly.

### 5. Resume Quality Auditor Skill
Created the global `resume-quality-auditor` skill across Gemini CLI and Claude Code to perform a rigorous 16-part data quality audit on Resume Council pipeline outputs, computing the actual semantic delta to ensure we are truly tailoring the resumes.

## Status
The pipeline ran successfully for Varsha (H&M Senior Merchandiser). 10 templates rendered perfectly, the subtitle was accurate ("Senior Merchandiser"), the name typo is gone, and the humanizer caught 70+ slop flags, significantly improving the semantic quality of the resume.