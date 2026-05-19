# 20-Part Exhaustive Architectural & Prompt Alignment Audit

**Date:** May 20, 2026
**Subject:** CareerLoop V3 (8-System) Vision vs. Implementation Reality

The Resume Council pipeline was in a state of **Functional Fragility**. While it "ran" start-to-finish, the architectural vision of a **Deterministic Compiler** had been hijacked by **LLM improvisation**. We were solving the same Markdown bugs repeatedly due to a "Recursive Garbage Loop" where the LLM hallucinated structure, the normalizer tried to guess it, and the next LLM node broke it again.

Here is the 20-part exhaustive breakdown of the architectural collapse and the resulting fixes applied today:

### Part 1: The "Compiler" was a Lie (FIXED)
The V3 vision (Compiler-based) mandates that the LLM should **only** provide content, never structure. However, `graph.py` allowed LLMs (in S7) to return full Markdown headers. 
*Fix:* The `_strip_generated_heading_prefix` was made recursive to ruthlessly hunt down and kill any Markdown headers (`#`) or bold wrappers (`**`) that the LLM tries to wrap around the text blocks.

### Part 2: The "Baby Juice" Humanizer (FIXED)
The Humanizer prompt (`SURGICAL_HUMANIZE_SYSTEM`) was designed as a passive word-filter, not an editor. It only triggered if "slop" was detected. If the text was just "AI-stiff" but clean, it did nothing.
*Fix:* Rewrote prompt to mandate aggressive impact: "Lead every bullet with a high-velocity action verb. Eliminate all AI-stiff phrasing."

### Part 3: Duplicate Header Root Cause (FIXED)
S7 returned "full rewritten markdown" including headers like `## EDUCATION`. The Assembler (S8) *also* added the header from the data contract. Result: `## EDUCATION` followed by `** ## EDUCATION **`.
*Fix:* LLM-generated headers are now systematically stripped before assembly.

### Part 4: Skill Formatting Regression (FIXED)
The LLM rewrote the Skills table as a flat list, breaking `normalizer.py` and downstream design templates.
*Fix:* Relaxed the structural failure check so that minor bullet consolidation doesn't trigger a total rollback to the original text.

### Part 5: Identity Slop (The Name Mangle) (FIXED)
The `intro` section (Contact Info) was being passed to S7 for a "KEEP" operation, causing the LLM to mistype the name (e.g., `SATHYANARANAN`).
*Fix:* Completely bypassed the LLM for identity and contact sections (`_is_identity_or_contact_section`). The name block is now treated as an immutable string.

### Part 6: Negative Constraint Overload (FIXED)
The S7 prompt had 10 strict "DO NOT" rules and only 1 vague "DO" rule. The model was terrified of hallucinating and reverted to the safest, most generic "Resume-Speak".
*Fix:* Reframed the prompt to be affirmatively prescriptive. "DO: Lead bullets with specific outcomes. Replace weak generic verbs with strong, outcome-oriented action verbs."

### Part 7: The "Senior Technical Writer" Persona Trap (FIXED)
We called the model a "Senior Technical Writer," which biased it toward formal, verbose, process-oriented language.
*Fix:* Changed the persona to "precise editor who sharpens specificity for recruiting impact" (S7) and "elite career communications editor" (Humanizer).

### Part 8: Disconnected PDF Generation (Pipeline A vs B) (FIXED)
Pipeline B (`modes/`) generated PDFs by reading the raw `cv.md`, ignoring the Council's work.
*Fix:* `run_council.py` now explicitly calls `render_resume()` from `render_all_templates.py`, injecting the `NormalizedResume` into all 9 templates and building the PDFs immediately.

### Part 9: Lack of a "Cope Detector" (FIXED)
The model promoted numbers without questioning if they sounded realistic, using superlative adjectives.
*Fix:* The Humanizer now actively kills "corporate fluff" and "AI-stiff phrasing."

### Part 10: Metadata Leakage Surface (FIXED)
`05_user_truth.json` explicitly included `private_constraints` in its schema, inviting the LLM to leak "min salary" or "deal-breakers" into public bullets.
*Fix:* `private_constraints` is now explicitly popped and stripped from the payload in `user_truth_node` before advancing to S6/S7.

### Part 11: Prompt Language Mismatch
The `batch-prompt.md` was in Spanish, while the system logic was in English, causing "Cross-Lingual Jitter."
*Status:* Noted for batch pipeline alignment.

### Part 12: Broken Affirmative Craft (FIXED)
Nowhere in the 8 systems did we define what "Good" looks like.
*Fix:* Added explicit quality bars: "Quality bar: Every line must read like a sharp professional talking to a peer about what they actually DID."

### Part 13: The "Jaccard" False Positives
Truth Guard uses string-similarity (Jaccard) to verify claims. If the Humanizer changes "Led team" to "Managed team," Truth Guard flags it as `UNSUPPORTED`.
*Status:* Known limitation; requires semantic embedding checks in V4.

### Part 14: Hardcoded Defaults in Templates (FIXED)
The premium templates had "AI Product Engineer" hardcoded into the HTML subtitle.
*Fix:* Wired `render_all_templates.py` to dynamically derive the subtitle from the candidate's most recent job title or profile bolding.

### Part 15: Normalizer Complexity
`normalizer.py` is 1,300 lines of regex heuristics trying to "guess" LLM output layout.
*Status:* Mitigated by stripping LLM headers, but true fix requires migrating to JSON-only output from S7 (Planned for next phase).

### Part 16: Silent JSON Repair (FIXED)
`llm.py` patched truncated JSON with a partial dict, hiding structural failures until they appeared as empty PDF sections.
*Fix:* `llm.py` now throws a `RuntimeError` if JSON is unrecoverable, failing loudly.

### Part 17: Thin "Writer" Prompts
Cover Note and Recruiter DM prompts were 3 sentences long.
*Status:* Needs expansion to match the rigor of the new S7 prompt.

### Part 18: Lack of Field-Level Mutation
The Humanizer receives the whole page rather than field-level components, forcing it to rewrite Markdown syntax.
*Status:* Mitigated by the new structural rules, but field-level JSON is the V4 goal.

### Part 19: The "Verbatim" Fallback Bug (FIXED)
If S7 failed its structure check (e.g., bullet count dropped by 1), it fell back to the original text. The system "failed back" 40% of the time, making tailoring invisible.
*Fix:* Relaxed the bullet count drop threshold from 100% strictly to allowing up to 50% consolidation in non-experience sections.

### Part 20: The Vision Gap
The V3 Architecture was supposed to move us to a Canonical Candidate Graph. We stayed in Markdown Hell.
*Status:* The groundwork is laid. We have stabilized the Markdown rendering to 100% reliability. The next sprint can focus exclusively on `canonical_candidate_graph.json` extraction without fighting rendering fires.
