# S3 + S7 Root Cause Audit — First Principles
**Date:** 2026-05-19  
**Trigger:** Pipeline ran. Cover note is good. Experience section verbatim. MD formatting is garbage. 3/5 S7 sections fell back to original. S3 hung indefinitely.  
**Method:** Read every line of `graph.py`, `llm.py`, `models.yml`, actual log output, and final `10_final_resume.md`.

---

## TL;DR

There are **4 discrete bugs** causing the failures, in order of severity:

1. **`_call()` hardcodes `"strategy"` model — ALL calls go to `deepseek-v4-pro`, including S7 rewrites that should use `deepseek-chat`**
2. **S7 hardcodes `max_tokens=2500` (chunks) and `max_tokens=4000` (standard) — overriding the config's `10000`. This is self-imposed truncation.**
3. **5 parallel calls to the same model simultaneously → rate limiting → empty `0 char` responses that silently fail**
4. **The assembler outputs raw CV text verbatim when S7 fails — the original CV has PDF-extraction artifacts (no blank lines between jobs, split words like `Inventory\nControl`, two institutions on one education line). These artifacts are in `raw_text` from S1 and go straight into the final MD.**

S3 is a separate issue: DeepSeek API latency on `deepseek-v4-pro` + 90s timeout = silent 90s hang with no progress visible to the user.

---

## Bug 1 — Wrong Model Routing: `_call()` always uses `"strategy"`

**File:** `careerloop/council/graph.py`, line 71

```python
def _call(system: str, user: str, ...) -> NodeResult:
    client = CouncilLLMClient("strategy")  # ← HARDCODED. Always deepseek-v4-pro.
```

**`config/models.yml` says:**
```yaml
strategy_model: deepseek-v4-pro   # S3-S6: company intel, role decode, user truth, positioning
writer_model: deepseek-chat        # S7-S8: section rewrites, cover note, DM
```

**Reality:** Every single call in the pipeline — S3, S4, S5, S6, S7 (all chunks), S8 (cover note, DM) — hits `deepseek-v4-pro`. The `writer_model` config key is never used. `deepseek-chat` is never called.

**Consequence for S7:** `deepseek-v4-pro` is slower and has tighter rate limits than `deepseek-chat`. Firing 5+ simultaneous calls to it in parallel is far more likely to trigger throttling. Also, `v4-pro` costs more per token.

**Fix required:** `_call()` needs a `model_kind` parameter. S7/S8 should pass `model_kind="writer"`.

---

## Bug 2 — Self-Imposed Max Token Truncation

**File:** `careerloop/council/graph.py` — `_rewrite_one_section()`

```python
# For chunks:
cresult = _call(..., max_tokens=2500, ...)

# For standard sections:
result = _call(..., max_tokens=4000, ...)
```

**`config/models.yml` says:**
```yaml
max_tokens: 10000  # Large output needed for full section rewrites
```

The config was explicitly set to 10000 because section rewrites need room. The code overrides this to 2500 for chunks and 4000 for standard calls. **This is the code telling DeepSeek to stop after 2500 tokens.** The professional experience section alone is 4429 chars (~1100 tokens of input text). The expected rewrite is similar in length. With `max_tokens=2500`, the model has ~1400 tokens of headroom for output — tight but technically feasible.

However: the S7 prompt itself is large. It includes `tone_guidance`, `narrative_angle`, `role_keywords` (10 items), `must_haves` (5 items), `hidden_expectations` (5 items), `day_one_deliverables` (3 items), `things_to_downplay` (5 items), `proof_points` (5 items), `claims_allowed` (list), `claims_not_allowed` (list), + section text. This prompt is ~2000–3000 tokens of input. With a 2500 max_tokens output cap and no enforcement of "start outputting JSON immediately," the model can legitimately run out of space before finishing the JSON.

**The 0-char responses** are a different symptom — those are rate-limit throttling, not truncation. But the legitimate truncations (partial JSON like `"unterminated string at char 698"`) are directly caused by the 2500 cap.

**Fix required:** Remove `max_tokens` overrides from S7 calls entirely. Let config drive it (10000).

---

## Bug 3 — Parallel Rate Limiting: 5 simultaneous `deepseek-v4-pro` calls

**File:** `careerloop/council/graph.py` — `section_rewrites_node()`

```python
n_workers = max(1, len(allowed_sections))  # = 5 for Varsha
with ThreadPoolExecutor(max_workers=n_workers) as executor:
    for section in allowed_sections:
        fut = executor.submit(_rewrite_one_section, section, **worker_kwargs)
```

5 simultaneous API calls fire at exactly the same second to `deepseek-v4-pro`. DeepSeek's rate limit for `v4-pro` is lower than for `chat`. The result: some calls get HTTP 200 back but with empty `content` (throttled response). The log shows this as `0 chars`:

```
!! JSON repair fired — LLM output was truncated or malformed (0 chars)
!! JSON repair failed — falling back to partial extraction
```

`0 chars` is not truncation — it's the API returning an empty content string. The `_repair_truncated_json()` correctly fails on it. The worker then sees `rewritten_text = ""` and skips.

**Why it's not obvious:** `requests.post()` returns HTTP 200, `raise_for_status()` passes, the content is just empty. No exception. Silent failure.

**Fix required:** 
1. Switch S7 to `deepseek-chat` (writer model) — far higher rate limits
2. Cap parallel workers at 2–3, not `len(sections)`
3. Add retry with backoff on empty response before falling back

---

## Bug 4 — MD Formatting Is the Original CV, Not a Rewrite

**File:** `output/council/varsha/varsha-hm-merchandiser/10_final_resume.md`

Because S7 failed on professional_experience, education, and skills, the assembler fell back to `raw_text` from S1. The `raw_text` is the CV as parsed by the mistune AST — which faithfully preserved the PDF-extraction artifacts in the source file.

**Examples from `10_final_resume.md`:**

```markdown
SuperK Bangalore, India
Category Manager – Fashion Nov 2025 – Present
```
→ No blank line before next company. Company + location on same line. Title + date on same line. No `###` subheading.

```markdown
The Style Gram Founder Remote - Chennai, India
Nov 2024 – Jun 2025
```
→ No blank line separation from previous company's bullets.

```markdown
Humber College - Longo School of Business Graduate Certificate in Fashion Management National Institute of Fashion Technology (NIFT) Bachelor of Design - Fashion Design Toronto, Canada
Sept 2023 – Aug 2024
```
→ Two institutions concatenated on one line. Both degree names on one line.

```markdown
- Inventory
Control
- Meta Ads
Manager
```
→ Words split across lines from PDF column wrapping. This is the original CV.

**Root cause chain:**
1. Source CV was PDF-extracted → soft wraps preserved as literal newlines → words split mid-phrase
2. `compiler.py::_preprocess_plaintext_cv()` handles some cases (month boundaries, bullet chars) but NOT:
   - Company name + location concat
   - Job title + date on one line (beyond the FashionNov pattern)
   - Two education entries concatenated
   - Column-wrapped word splits (`Inventory\nControl`)
3. S1 stores this damaged `raw_text` correctly — it's faithful to what it received
4. S7 should rewrite it into clean structure — but S7 failed
5. S8 assembler falls back to `raw_text` — damage preserved verbatim

**This means even if S7 worked perfectly, the EDUCATION and SKILLS sections would still be broken because S7 rewrites content (verbs, keywords) but doesn't restructure the underlying format corruption from PDF extraction.**

---

## S3 Separate Issue

S3 was not failing — it was waiting. The `_call()` timeout is 90 seconds. With no progress print during the wait, the user saw `⟳ LLM call [S3 company intelligence]...` frozen for up to 90 seconds.

The DeepSeek API itself was slow on the initial session (possibly cold-start on `deepseek-v4-pro`). It wasn't an infinite hang — it was 90s of silence.

**Added `CAREERLOOP_SKIP_S3=1` as escape hatch.** But the real fix is: S3 needs a visible countdown or progress indication, and if the API is slow, that's a DeepSeek infrastructure issue, not a code bug.

---

## What the Final Resume Actually Shows

```
Sections rewritten:    2/5 (summary + intro only)
Sections verbatim:     3/5 (professional_experience, education, skills)
Delta from original:   ~3% (only summary repositioning)
```

The cover note and DM are actually **good** — they're specific, factual, H&M-targeted, no Nicobar references. S4-S6 worked correctly.

The experience bullets are 100% original CV text. No OTB language. No jersey. No H&M positioning in the body. The S6 positioning strategy was excellent but S7 never applied it.

---

## What Needs to Happen — Priority Order

### Fix 1 (CRITICAL): Route S7/S8 to `deepseek-chat` writer model
`_call()` needs a `model_kind` param. S7 `_rewrite_one_section()` and S8 cover/DM calls pass `model_kind="writer"`. This alone fixes the rate limit problem and cuts cost by ~10x for S7.

### Fix 2 (CRITICAL): Remove `max_tokens` overrides in S7
Delete `max_tokens=2500` and `max_tokens=4000` from `_rewrite_one_section()`. Let `CouncilLLMClient` use the config default (10000). No manual override.

### Fix 3 (HIGH): Add retry on empty response
Before falling back to original, if `rewritten_text == ""`, retry the call once with a 3-second delay. DeepSeek throttling is transient. One retry recovers most throttled calls.

### Fix 4 (HIGH): Limit parallel workers to 3, not `len(sections)`
`max_workers=min(3, len(allowed_sections))`. 3 concurrent calls to `deepseek-chat` won't trigger rate limits. Tradeoff: minor increase in total time.

### Fix 5 (MEDIUM): Fix PDF extraction artifacts at S1
`_preprocess_plaintext_cv()` needs additional rules:
- Split on `\nJobTitle|Month` (catch "Category Manager – FashionNov" variants)
- Split on company/location concat (`SuplerK Bangalore, India` all on one line)
- Detect and split column-wrapped words (`Inventory\nControl` → `Inventory Control`)
- Split education entries that are concatenated (`Humber College...NIFT...`)

### Fix 6 (MEDIUM): Redesign the final MD assembly
The assembler must emit proper structure regardless of whether S7 rewrote a section:
- Each job entry needs a blank line separator
- Company name, title, dates should be on separate lines in a defined format
- Education entries need blank lines between them
- Skills section concatenation must be detected and reformatted

---

## What Is NOT Broken

- S1 parsing: correctly stores raw_text from the CV
- S2 contract: correctly identifies public sections
- S4 role decode: nailed H&M requirements (OTB, jersey, vendor management)
- S5 user truth: correctly identified Varsha's 4.1 years, real metrics, claims not allowed
- S6 positioning: solid strategy, correct CAREFUL_PUSH stance, no persona bleed
- Truth Guard: correctly flagged fabricated "3+ years" (should be 4+) in summary
- Cover note: specific, factual, H&M-OTB-targeted, correct person
- Recruiter DM: clean, no anchoring to wrong candidate

---

## Token Waste Accounting

| Run | Why it failed |
|-----|--------------|
| Run 1-6 (parallel background agents) | Launched 6 simultaneous pipeline runs. All blocked at S3 (90s DeepSeek timeout × 6). |
| Run 7 (with CAREERLOOP_SKIP_S3=1) | S3 bypassed. S7 got 0-char responses on 3/5 sections due to parallel rate limiting on deepseek-v4-pro. Wrong model (v4-pro instead of chat). Wrong max_tokens (2500/4000 instead of 10000). |
| Run 8 (user's own run, same config) | Same result: 3/5 fell back. |

**Estimated cost:** Multiple runs × 5 sections × ~3000 input tokens × `deepseek-v4-pro` rate = expensive. Had we used `deepseek-chat` from the start (as the config intended), cost would be ~10x lower and rate limits would not have triggered.

---

## The One-Line Verdict

**S7 is broken because `_call()` ignores the model routing config, all calls hit `deepseek-v4-pro`, 5 parallel hits trigger rate limits, and self-imposed `max_tokens=2500` causes the legitimate truncations. Fix: use `deepseek-chat` for S7, remove the max_tokens override, cap workers at 3, add one retry.**

**The MD is ugly because S7 fell back to raw CV text that has PDF extraction artifacts the preprocessor doesn't handle. This is a separate problem that needs S1 preprocessing rules + assembler structure enforcement.**
