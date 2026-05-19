# Council Redesign Implementation Plan
**Date:** 2026-05-19  
**Status:** Actionable — fixes sorted by dependency order  
**Inputs read:** `graph.py`, `llm.py`, `humanizer.py`, `compiler.py`, `run_council.py`, `models.yml`, `S3_S7_ROOT_CAUSE_AUDIT.md`, `COMPANY_INTELLIGENCE_VISION.md`, `CAREERLOOP_REDESIGN_IMPLEMENTATION_PLAN.md`, both pipeline runs, `10_final_resume.md`

---

## What Is Actually Broken (Evidence-Based)

| System | Broken? | Root Cause |
|--------|---------|-----------|
| S1 Document Parser | ⚠️ Partial | Correctly parses markdown. Fails on PDF-extracted text: split words (`Inventory\nControl`), concatenated company+location on one line, two education entries in one line. These artifacts go into `raw_text` and survive into the final MD verbatim. |
| S2 Preservation Contract | ✅ Works | — |
| S3 Company Intelligence | ❌ Silent skip | Using stub (CAREERLOOP_SKIP_S3=1). When enabled: 90s timeout with no progress. Real issue: `_call()` hardcodes `"strategy"` model but `deepseek-v4-pro` has no real-time web access. S3 vision is a research engine. Current implementation is LLM recall. |
| S4 Role Decoder | ✅ Works | Good output. |
| S5 User Truth | ✅ Works | Good output, correct metrics. |
| S6 Positioning | ⚠️ Mediocre | Works mechanically. Quality is limited because company intelligence is a stub. No real H&M-specific signals (Bengaluru team size, buying cycle, category ownership structure). Strategy output is generic "transferable merchandiser" rather than H&M-specific. |
| S7 Section Rewrites | ❌ 3/5 fail | **Bug 1:** `_call()` hardcodes `model_kind="strategy"` → all calls use `deepseek-v4-pro` instead of `deepseek-chat`. **Bug 2:** `max_tokens=2500/4000` override → truncation. Config says 10000. **Bug 3:** 5 parallel calls to v4-pro → rate limit → 0 char empty responses → silent fallback. **Bug 4:** No retry on empty response. |
| S7.5 Truth Guard | ✅ Works | — |
| S8 Assembly | ⚠️ Partial | Assembly is deterministic and correct. Cover note and DM are good. **Bug:** Humanizer output not saved separately. `10_final_resume.md` gets pre-humanizer markdown. Humanizer runs but its result only goes into `application_pack.resume_markdown` which is printed in logs but never written as its own file. |
| Humanizer | ⚠️ Invisible | Humanizer runs but: (1) For resume mode, Phase 3 (LLM surgical humanize) is SKIPPED — hardcoded `if mode == "resume": return self._deterministic_clean(text, flags)`. (2) Output not saved as `12_humanized_resume.md`. (3) No diff between pre/post humanizer in artifacts. |
| MD Formatting | ❌ Garbage | Three layers: (1) PDF extraction artifacts in raw CV (job entries run together, split words). (2) S1 preprocessor doesn't fix them all. (3) S7 falling back to raw_text with those artifacts. Assembler has no structure enforcement per job entry. |
| Input Pipeline | ❌ Missing | Only accepts `.md` files. User wants PDF/DOCX → extract text → pipeline. No PDF/DOCX extractor wired. |

---

## Fix Plan — Ordered by Dependency

### FIX 1 — Model Routing Bug (15 min, CRITICAL)

**File:** `careerloop/council/graph.py` — `_call()` function  
**File:** `careerloop/council/graph.py` — all S7 and S8 call sites

`_call()` hardcodes `CouncilLLMClient("strategy")`. Add `model_kind` param. S7 and S8 call with `"writer"`.

```python
# BEFORE
def _call(system, user, temperature=0.2, max_tokens=None, label=""):
    client = CouncilLLMClient("strategy")

# AFTER  
def _call(system, user, temperature=0.2, max_tokens=None, label="", model_kind="strategy"):
    client = CouncilLLMClient(model_kind)
```

Every `_call(...)` in `_rewrite_one_section()` and `assembly_node` (cover note, DM, humanizer LLM calls) adds `model_kind="writer"`.

**Impact:** S7 now uses `deepseek-chat` — 10x cheaper, higher rate limits, same quality for writing tasks.

---

### FIX 2 — Remove max_tokens Overrides (5 min, CRITICAL)

**File:** `careerloop/council/graph.py` — `_rewrite_one_section()`

```python
# DELETE these two lines:
cresult = _call(..., max_tokens=2500, ...)  # chunk call
result = _call(..., max_tokens=4000, ...)   # standard call

# REPLACE WITH:
cresult = _call(..., model_kind="writer")
result = _call(..., model_kind="writer")
```

Config says `max_tokens: 10000`. Let it be. No override.

---

### FIX 3 — Retry on Empty Response (30 min, HIGH)

**File:** `careerloop/council/graph.py` — `_call()`

```python
def _call(system, user, temperature=0.2, max_tokens=None, label="", model_kind="strategy", retries=1):
    client = CouncilLLMClient(model_kind)
    tag = f" [{label}]" if label else ""
    for attempt in range(retries + 1):
        print(f"  ⟳ LLM call{tag}{'(retry)' if attempt > 0 else ''}...", end=" ", flush=True)
        try:
            payload = client.complete_json(system, user, max_tokens=max_tokens)
            if payload.get("_parse_error") and attempt < retries:
                import time; time.sleep(3)
                continue
            print("done")
            return NodeResult(success=True, confidence=0.8, payload=payload)
        except Exception as e:
            if attempt < retries:
                import time; time.sleep(3)
                continue
            print(f"FAILED: {e}")
            return NodeResult(success=False, confidence=0.0, errors=[str(e)])
```

`_rewrite_one_section()` passes `retries=1`. One retry after 3 seconds catches most rate-limit throttles.

---

### FIX 4 — Cap Parallel Workers at 3 (5 min, HIGH)

**File:** `careerloop/council/graph.py` — `section_rewrites_node()`

```python
# BEFORE
n_workers = max(1, len(allowed_sections))

# AFTER
n_workers = min(3, max(1, len(allowed_sections)))
```

3 concurrent `deepseek-chat` calls won't trigger rate limits. Worst case: 5 sections in 2 batches = marginal extra time vs 5 parallel hits that all fail.

---

### FIX 5 — Remove Silent Fallback, Make S7 Failures Visible (20 min, HIGH)

**Current behavior:** S7 fails → silently uses original `raw_text` → nobody knows → garbage output.

**New behavior:** S7 fails → logs LOUDLY in the section rewrite entry → assembler marks the section as UNEDITED in the quality report → user sees exactly which sections need attention.

```python
# In _rewrite_one_section, instead of returning None on failure:
return sid, None, reason  # current

# Keep returning None (assembler falls back to original) BUT:
# In section_rewrites output, add explicit "fallback_used" flag per section
```

**In assembler:** Add to quality report: `"sections_not_tailored": ["professional_experience", "education", "skills"]` and print at the end: `!! WARNING: 3 sections could not be rewritten. Output is partially original.`

The resume still needs to be produced (can't return nothing), but the gap must be explicitly visible in the output, not silently hidden.

---

### FIX 6 — Fix MD Formatting: Assembler Must Structure Experience (1 hour, HIGH)

**File:** `careerloop/council/graph.py` — `assembly_node()`  
**File:** `careerloop/council/compiler.py` — add `_format_experience_section()`

The fundamental problem: PDF-extracted CVs have job entries concatenated without blank lines. S7 should rewrite them into clean structure, but when S7 fails, the assembler outputs raw PDF text.

**Two-part fix:**

**Part A — S1 preprocessor additions** (`compiler.py::_preprocess_plaintext_cv()`):
```python
# 6. Fix column-wrapped words: "Inventory\nControl" → "Inventory Control"
#    Pattern: word ending a line, continued word on next line with no bullet
text = re.sub(r'([a-zA-Z])\n([a-z])', r'\1 \2', text)

# 7. Add blank line before company name patterns:
#    "XYZ Company Location\nJob Title" → "\n\nXYZ Company..."  
#    Detect: text ending with city/India/Remote, next line has job title words
# (Regex: line ending in known location words, followed by non-bullet next line)
```

**Part B — Assembler structure enforcement**:
When assembling `professional_experience` from `raw_text` (fallback path), run `_clean_experience_section(raw_text)`:
```python
def _clean_experience_section(text: str) -> str:
    """Add blank lines between job entries in raw CV text.
    
    Detects job entry boundaries by pattern:
    - Line that ends with a month/year date range
    - Line that has company name followed by location
    Apply: ensure blank line before each detected company block.
    """
    # Split into paragraphs at existing double-newlines
    # Within each paragraph, detect "CompanyName Location" + "Title Date" pairs
    # Ensure blank line before each pair
```

---

### FIX 7 — Save Humanizer Output Separately (20 min, MEDIUM)

**File:** `run_council.py` — artifact saving section  
**File:** `careerloop/council/graph.py` — `assembly_node()` must store humanized text in state

**Current:** Humanizer runs in `assembly_node`, result goes into `application_pack.resume_markdown` (which IS the humanized version), but `10_final_resume.md` is written from `pack["resume_markdown"]` which may or may not be post-humanizer depending on whether the humanizer safety gate rejected the output.

**What's actually happening:** Looking at `assembly_node` logs: `→ Humanizer (resume): 0 slop flags, 1 realism concerns` — the humanizer ran, found concerns, but the safety gate in `humanizer.py` rejects rewrites that lose markdown structure. The result is the deterministic cleaned version, not an LLM rewrite (because `mode="resume"` skips the LLM phase 3 entirely — hardcoded).

**Fix:**
1. Add `humanizer_output` key to CouncilState
2. In `assembly_node`: store `humanizer_result.humanized_text` in state as `humanizer_output`
3. In `run_council.py`: save `state["humanizer_output"]` → `12_humanized_resume.md`
4. In the log: print a diff showing what the humanizer changed (before/after char count + flag count)

---

### FIX 8 — Enable Resume Phase 3 LLM in Humanizer (30 min, MEDIUM)

**File:** `careerloop/council/humanizer.py` — `_surgical_humanize()`

```python
# CURRENT — LLM phase skipped for resume mode
def _surgical_humanize(self, text, flags, mode):
    if not flags:
        return text
    if mode == "resume":
        return self._deterministic_clean(text, flags)  # ← SKIPS LLM

# FIXED — LLM runs for resume mode too if client available
def _surgical_humanize(self, text, flags, mode):
    if not flags:
        return text
    if self.llm is not None:
        return self._llm_surgical_humanize(text, flags)  # runs for resume too
    return self._deterministic_clean(text, flags)
```

The safety gate at the end (`_markdown_structure_safe`) already prevents structural damage. The LLM skip was a conservative choice that defeats the purpose of having an LLM humanizer. Enable it.

---

### FIX 9 — PDF/DOCX Input Extraction (2 hours, MEDIUM)

**New file:** `careerloop/council/document_extractor.py`

```python
"""
Extract text from PDF or DOCX resume files.
Output: clean plain-text string ready for ResumeCompiler.parse_markdown().

Supported input types:
  - .pdf  → pdfminer.six or pypdf2
  - .docx → python-docx
  - .md   → passthrough
  - .txt  → passthrough
"""

def extract_resume_text(file_path: str | Path) -> str:
    """Extract text from PDF, DOCX, MD, or TXT. Returns plain text string."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix == ".docx":
        return _extract_docx(path)
    elif suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

def _extract_pdf(path: Path) -> str:
    """Extract text from PDF preserving paragraph structure."""
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(str(path))
        return _clean_pdf_text(text)
    except ImportError:
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return _clean_pdf_text("\n".join(pages))
        except ImportError:
            raise ImportError("Install pdfminer.six or pypdf: pip install pdfminer.six")

def _extract_docx(path: Path) -> str:
    """Extract text from DOCX preserving paragraph breaks."""
    try:
        from docx import Document
        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except ImportError:
        raise ImportError("Install python-docx: pip install python-docx")

def _clean_pdf_text(text: str) -> str:
    """Post-process PDF-extracted text to fix common artifacts."""
    # Fix column-wrap word splits: "Inven-\ntory" → "Inventory"
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    # Fix soft-wrap word splits: "Inven\ntory" → "Inventory"  
    text = re.sub(r'([a-zA-Z])\n([a-z])', r'\1 \2', text)
    # Normalize excessive whitespace
    text = re.sub(r' {2,}', ' ', text)
    # Preserve paragraph breaks (double newline)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
```

**Wire into `run_council.py`:** Add `--cv` flag accepting any file path. If `.pdf` or `.docx`, run through `extract_resume_text()` before passing to pipeline.

```bash
python run_council.py --cv /path/to/resume.pdf --job-id varsha-hm-merchandiser
```

---

### FIX 10 — S3 Real Company Intelligence (3 hours, HIGH)

**Current:** S3 = DeepSeek recall from training data. Produces hallucinated facts. Slow (90s timeout). No real research.

**What the vision says it should be:** Research engine with sources, facts vs inferences separation, readiness levels.

**Pragmatic implementation using what we already have:**

**Step 1 — Fast JD-only intelligence (no web, instant):**
S3 currently sends the JD to DeepSeek and asks it to recall company facts. This is fine as a starting point but the prompt should be radically different:

```
WRONG: "Tell me about H&M"
RIGHT: "Extract ALL signals from this JD text. 
        Facts = only things explicitly stated in the JD.
        Inferences = things you can reasonably infer from JD patterns.
        Unknowns = things you cannot determine from JD alone.
        Do NOT use training data for facts. Only use JD text."
```

This makes S3 a **JD signal extractor**, not a recall machine. It's fast (< 10s), deterministic (grounded in the JD), and doesn't hallucinate.

**Step 2 — Optional web enrichment (add when working):**
The `CompanyResearchAdapter._search_web()` already exists with a 10s timeout. When `CAREERLOOP_ENABLE_WEB_RESEARCH=1`, it fetches DuckDuckGo results. Wire those results into the Step 1 prompt as additional sources.

**Step 3 — Add to prompt:**
```
SOURCES AVAILABLE:
[JD] <jd_text>
[WEB] <search result snippets if available>

Extract: facts (JD-sourced only), inferences (labeled), unknowns (explicit gaps).
```

**S3 system prompt rewrite:**
```python
_S3_SYSTEM = """You are extracting company intelligence from a job description.

STRICT RULES:
1. FACTS: only extract what is explicitly stated in the JD text. No training data.
2. INFERENCES: label separately. "The role mentions 95%+ on-time delivery targets → implies strong supply chain discipline."
3. UNKNOWNS: list explicitly. "Team size: unknown. Headcount: unknown."
4. Do NOT hallucinate funding rounds, Glassdoor ratings, or facts not in the JD.
5. Focus on: what this company VALUES based on what they asked for. That's the real intel.
"""
```

---

### FIX 11 — Positioning Quality (1 hour, MEDIUM)

**Current problem:** S6 prompt is generic. It doesn't have company-specific hooks from S3 (because S3 was a stub). It generates "transferable merchandiser ready to learn OTB" — correct but bland.

**What better positioning looks like:**
- Uses specific S3 signals: "H&M emphasizes 95%+ on-time delivery → lead with Varsha's 95% OTB record"
- Uses hidden expectations: "H&M wants range review presentation skills → lead with the 3 subcategory launches"
- Uses company culture: "H&M Bengaluru team = matrix org, cross-functional → lead with collaboration bullets"
- Has an actual differentiator: not "transferable expert" but "the only candidate who has run category P&L from zero at a value retail startup AND managed 20+ supplier PO/PI at a structured org — both sides of the H&M job"

**Fix:** Rewrite `_S6_SYSTEM` prompt to require the model to:
1. State the ONE differentiating insight (what makes this candidate specifically interesting to THIS company, not generically)  
2. Map proof points to specific JD requirements (not generic strengths)
3. Identify the hiring manager's likely objection and neutralize it upfront

---

### FIX 12 — Comprehensive Per-Run Logging (1 hour, MEDIUM)

**What's missing from current artifacts:**
- No `12_humanized_resume.md` (humanizer output)
- No delta file: what changed between original CV and final resume
- No `09_s7_debug.json` showing per-section: input tokens, output tokens, model used, time taken, success/fail reason
- Log lines have no timestamps — impossible to see where time was spent

**Add:**
1. `12_humanized_resume.md` — post-humanizer version
2. `09_s7_debug.json` — per-section timing, model, token estimate, success/fail
3. Timestamp each `---System N---` log line: `2026-05-19 14:32:01 | System 4...`
4. End-of-run summary: total wall clock, per-stage time, sections rewritten vs fallback, tokens estimated

---

## Architecture Decisions (These Must Not Change Mid-Implementation)

| Decision | Rationale |
|----------|-----------|
| S7 uses `deepseek-chat` for all rewrite calls | Cost + rate limits. v4-pro is for strategy only (S3-S6). |
| No max_tokens override in S7/S8 | Config drives it. 10000 is the right default. |
| S3 = JD extractor first, web enricher second | Fast, grounded, no hallucination. Web is additive. |
| S7 fallback = original text, but LOUDLY flagged | Can't return nothing. But must be visible in quality report. |
| PDF/DOCX extraction before pipeline | Extraction happens at input layer. Pipeline only sees clean text. |
| Humanizer LLM enabled for resume mode | Safety gate already prevents structure damage. |
| Humanizer output saved as separate artifact | Debugging requires before/after visibility. |

---

## Implementation Order (Do In This Sequence)

```
FIX 1  →  FIX 2  →  FIX 3  →  FIX 4   (S7 LLM bugs — 1 hour total)
     ↓
FIX 5  →  FIX 6                         (MD quality — 1.5 hours)
     ↓
FIX 7  →  FIX 8                         (Humanizer visibility — 45 min)
     ↓
FIX 10  →  FIX 11                       (S3 + Positioning — 4 hours)
     ↓
FIX 9  →  FIX 12                        (PDF input + logging — 3 hours)
```

**Test gate after each group:** Run `python run_council.py --job-id varsha-hm-merchandiser --person varsha` and verify the group's output before proceeding.

---

## Success Criteria

After all fixes are implemented:

| Check | Expected |
|-------|----------|
| S7 rewrite rate | 5/5 sections rewritten (not 2/5) |
| S7 model | `deepseek-chat` visible in debug log |
| S7 time | ~45s (parallel, no rate limits) |
| `10_final_resume.md` experience section | Experience bullets rewritten with OTB/jersey/H&M language |
| `10_final_resume.md` formatting | Blank lines between job entries, no split words |
| `12_humanized_resume.md` | Exists, non-empty, shows humanizer flags |
| S3 output | JD-extracted facts with explicit UNKNOWN fields, no hallucinated H&M headcount |
| S6 positioning | Specific differentiator for THIS candidate × THIS company, not generic |
| Cover note | Already good — should remain H&M-specific |
| PDF input | `python run_council.py --cv resume.pdf --job-id ...` works |
| Total pipeline time | < 3 min (S3 < 10s, S7 parallel ~45s, S8 ~45s) |

---

## What NOT To Do

- Do NOT redesign the LangGraph topology (nodes, edges, state keys)
- Do NOT replace DeepSeek as provider
- Do NOT rewrite the Truth Guard regex patterns
- Do NOT touch the rendering pipeline (normalizer, templates, validator)
- Do NOT add new CouncilState keys beyond `humanizer_output` and `s7_debug`
- Do NOT make S3 a full research engine right now — JD extraction is the correct scope for this sprint

---

## Current State of Each File

| File | What Needs Changing |
|------|-------------------|
| `graph.py` | Fix `_call()` model_kind, remove max_tokens overrides, add retry, cap workers, save humanizer output to state, rewrite S3 prompt, rewrite S6 prompt |
| `llm.py` | No changes needed — `_call()` fix is in graph.py |
| `humanizer.py` | Enable LLM phase 3 for resume mode |
| `compiler.py` | Add column-wrap fix (rule 6) and location concat fix (rule 7) to `_preprocess_plaintext_cv()` |
| `run_council.py` | Add `--cv` flag for PDF/DOCX, save `12_humanized_resume.md`, save `09_s7_debug.json`, add timestamps |
| `document_extractor.py` | New file — PDF/DOCX extraction |
| `requirements.txt` | Add `pdfminer.six` and `python-docx` |
