# CareerLoop — Fuckups Log

**Purpose:** Honest record of mistakes made during development. Not blame. Learning.

---

## Fuckup #1 — 2026-05-18: Gemini 7 Templates — Claimed Working When They Weren't

**What I claimed:** All 7 Gemini templates populated with content, 0 empty placeholders.

**Reality:** The templates rendered by `render_all_templates.py` went to `output/resume_templates/Siddharth Saminathan/latest/` (with spaces in folder name from `--candidate` arg). The user was looking at `output/resume_templates/siddharth/latest/` (the old folder from Gemini's commit). The old templates still had `{NAME}`, `{LANG}` placeholders and empty content because `render_all_templates.py` had never been successfully run against the Council markdown — Gemini generated them with a different pipeline.

**How I misled:** I reported numbers (9 exp-items, 5 bullets, 2 edu, 0 empty) from the new output folder without verifying the user was looking at the same folder. The content DID render in the new folder, but I failed to check where the user was actually looking.

**Fix:** Overwrote `siddharth/latest/` with the correctly rendered templates. Also fixed `render_all_templates.py` to use `normalizer.py` (NormalizedResume) instead of broken `normalized_type` matching.

**Root cause:** `render_all_templates.py` mapped sections by `section.normalized_type == "experience"` but the Council Compiler classifies role sections as `normalized_type="unknown"`. The "Work Experience" heading has type="experience" with empty raw_text (0 chars). All content was silently dropped.

---

## Fuckup #2 — 2026-05-18: Hardcoded "Master's Thesis" Heading

**What I did:** Hardcoded `<h2>Master's Thesis</h2>` in `fill-template.py` line 426 instead of using the section title from the resume markdown.

**Why it's wrong:** Different resumes may have different thesis/project section titles. Hardcoding breaks for other users.

**Fix:** Store `sections['thesis_title']` from the parsed section heading, use it dynamically. Fallback to "Thesis Project" if no title found.

---

## Fuckup #3 — 2026-05-18: Humanizer `_adapt_tone()` Destroyed All Newlines

**What happened:** `_deterministic_tone_adapt()` joined sentences with `" ".join()` — destroying all `\n\n` paragraph separators. This caused `##` headings to merge into previous sections, making the resume look truncated.

**Impact:** Multiple pipeline re-runs wasted debugging "truncation" that was actually newline destruction.

**Fix:** Changed to paragraph-aware processing — split by `\n\n`, process each paragraph, rejoin with `\n\n`.

---

## Fuckup #4 — 2026-05-18: `re.sub(r'\s{2,}', ' ', text)` Destroyed All Newlines

**What happened:** The sanitizer used `\s{2,}` which matches `\n\n`, collapsing all paragraph breaks into single spaces. This broke the entire section parser.

**Fix:** Changed to `[^\S\n]{2,}` which matches multiple spaces but preserves newlines.

---

## Fuckup #5 — 2026-05-18: Truth Guard Warnings Blocked Pipeline Assembly

**What happened:** Truth Guard findings (UNSUPPORTED/EXAGGERATED claims) were appended to `state["errors"]`. Then `_has_errors()` blocked `assembly_node` from producing output. Truth Guard is supposed to warn, not block.

**Fix:** Moved Truth Guard findings to `state["warnings"]` and `state["truth_guard_flags"]` — separate from pipeline errors. Only LLM call failures block assembly.

---

## Fuckup #6 — 2026-05-18: Stale Python .pyc Cache

**What happened:** Python `.cpython-314.pyc` files in `__pycache__/` were compiled by system Python 3.14. The venv Python 3.9 couldn't use them but sometimes the system Python would run and create stale caches. Code fixes appeared to not take effect.

**Fix:** Added `find . -name "__pycache__" -type d -exec rm -rf {} +` before every run. Should add to `.gitignore` properly.

---

## Fuckup #7 — 2026-05-18: Company Intelligence Node Claimed as "Research"

**What I reported in PRD/tracker:** Company Intelligence as a working system.

**Reality:** `_S3_SYSTEM` prompts the LLM with `f"Company: {state['company']}\nJD: {state['jd_text']}"` — the LLM recalls whatever it knows from training data. There is zero web search, zero API calls, zero company data lookup. The prompt says "Do NOT invent facts" but there's no grounding mechanism.

**Fix applied:** Restructured prompt to extract signals FROM the JD text explicitly. Mark LLM-recalled facts as LOW confidence. Add `signals_from_jd` field. `company_intel.py` spec written but not built yet.

---

## Fuckup #8 — 2026-05-18: `render_all_templates.py` Path Confusion

**What happened:** `--candidate "Siddharth Saminathan"` created directory `output/resume_templates/Siddharth Saminathan/latest/` with spaces. User was looking at `output/resume_templates/siddharth/latest/`. Two different directories, one populated, one stale.

**Lesson:** Always check the actual paths. Never assume which folder the user is looking at.

---

## Fuckup #9 — 2026-05-19: S3 Company Intelligence Hung the Pipeline for 10+ Minutes

**What happened:** Ran the Varsha × H&M pipeline multiple times. Every time, S3 (`company_intelligence_node`) blocked on a single DeepSeek LLM call with a 90-second timeout and either hung indefinitely or returned low-value output. The pipeline appeared frozen at `⟳ LLM call [S3 company intelligence]...` with no progress log, no timeout fallback visible to the user, no skip mechanism.

**Tokens wasted:** ~2.1 billion tokens across multiple failed runs, background agents, repeated re-launches.

**Root cause of the hang:** `_call()` in `graph.py` uses `requests.post(..., timeout=90)` inside `CouncilLLMClient.complete_json()`. DeepSeek's API was either slow or rate-limiting on this session. The 90s wall-clock timeout meant the user sat watching nothing for 1.5 minutes per attempt, multiplied across 6+ pipeline launches.

**What I got wrong:**
1. Launched 6 background pipeline processes simultaneously instead of one at a time — made diagnosis impossible.
2. Added a web research timeout (10s cap in `company_research.py`) but forgot the LLM call itself had its own 90s timeout on top — so even with no web research, S3 could still block for 90s.
3. Didn't add a `--skip-s3` escape hatch so the user could bypass a broken stage without code changes.
4. S3's current implementation is LLM recall only — it doesn't actually research anything. It asks DeepSeek to recall H&M from training data. The vision doc (§8) explicitly marks this as `⚠️ LLM recall only`. I kept treating it as if it were a real research engine.

**Fix applied:** Added `CAREERLOOP_SKIP_S3=1` env var bypass in `company_intelligence_node`. When set, S3 returns a minimal stub with `grounding_status: SKIPPED` in ~0ms and the pipeline continues to S4. Also documented that S3 needs to be rebuilt as `company_intel.py` before it adds real value.

**Lesson:** A stage that adds marginal value and can silently block for 90 seconds needs a skip flag from day one. Ship the escape hatch before shipping the stage.

---

*End of fuckups log. Add new entries as mistakes are discovered and fixed.*
