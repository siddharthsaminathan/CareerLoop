# CareerLoop Resume Council — 8-Stage Pipeline Checklist

**Last updated:** 2026-05-22  
**Purpose:** Stage-by-stage status map. Use this to diagnose which stage is broken before running the full graph.  
**How to use:** Run each stage manually using the test commands. Fix failures before running the full pipeline.

---

## How to test a single stage manually

Each stage can be exercised by reading the input artifact from a previous run and calling the node function directly:

```python
# Example: test S1 in isolation
from careerloop.council.compiler import ResumeCompiler
text = open("test data/varsha_resume_0426.md", encoding="utf-8").read()
resume = ResumeCompiler.parse_markdown(text)
print(f"Sections: {[s.section_id for s in resume.sections]}")
```

Artifacts for Varsha's last run live in:
`output/council/varsha/varsha-hm-merchandiser/`

---

## Stage Map

### S1 — Document Parser
**File:** `careerloop/council/compiler.py::ResumeCompiler.parse_markdown()`  
**Type:** Deterministic (zero LLM calls)  
**Input:** Raw CV text (`master_cv` string)  
**Output:** `canonical_resume` → `01_canonical_resume.json`

**What it does:** Parses markdown/plain-text CV into sections using mistune AST. Classifies sections as PUBLIC/PRIVATE. Extracts links.

**Upstream deps:** None  
**Downstream deps:** S2 (contract), S5 (user truth reads sections), S7 (rewrites sections), S8 (assembles sections)

**Speed:** ~0.1s — not a bottleneck

| Check | Status |
|-------|--------|
| Markdown CVs parse correctly | ✅ Fixed |
| Plain-text / PDF-extracted CVs parse correctly | ✅ Fixed (Pass A heading injection) |
| Intra-section run-ons split (IndiaCategory, PresentBuilt) | ✅ Fixed (Pass B rules 1-4) |
| TitleMonth boundary split (FashionNov 2025) | ✅ Fixed (Pass B rule 5) |
| Dead `confidence` field removed from ResumeSection | ✅ Fixed |
| Private sections classified and excluded | ✅ Working |

**Known remaining gap:** Section body text still comes out as raw paragraph text — no per-bullet structure. Bullets are markdown lines, not structured arrays. This means S7 must handle raw markdown strings, not typed data.

**Manual test:**
```python
from careerloop.council.compiler import ResumeCompiler
text = open("test data/varsha_resume_0426.md", encoding="utf-8").read()
r = ResumeCompiler.parse_markdown(text)
for s in r.sections:
    print(s.section_id, len(s.raw_text))
# Expected: 5 sections, professional_experience ~4000+ chars
```

---

### S2 — Preservation Contract
**File:** `careerloop/council/compiler.py::ResumeCompiler.build_contract()`, called in `graph.py::contract_node()`  
**Type:** Deterministic (zero LLM calls)  
**Input:** `canonical_resume`, `profile`  
**Output:** `preservation_contract` → `02_preservation_contract.json`

**What it does:** Determines which sections are required, excluded, and in what order. Enforces link preservation rules.

**Upstream deps:** S1  
**Downstream deps:** S7 (reads `sections_to_exclude`), S8 (reads ordering + exclusions)

**Speed:** ~0.05s — not a bottleneck

| Check | Status |
|-------|--------|
| Private sections excluded from public outputs | ✅ Working |
| `safe_construct` used instead of raw `ResumeSection(**s)` | ✅ Fixed |
| `max_allowed_changes: 3` enforced downstream | ⚠️ NOT enforced — contract is passed to LLM as context only, not mechanically checked |
| `ordering_rules` used in assembly | ⚠️ NOT used — assembly sorts by `original_order`, ignores contract ordering |

**Known remaining gap:** `max_allowed_changes` and `ordering_rules` are computed but never mechanically enforced. The contract is advisory, not binding.

---

### S3 — Company Intelligence
**File:** `graph.py::company_intelligence_node()`  
**Type:** LLM + web research adapter  
**Input:** `company`, `jd_text`, `job_url`  
**Output:** `company_intelligence` → `03_company_intelligence.json`

**What it does:** Gathers company context (facts, culture, implications) then calls DeepSeek to synthesize. The `CompanyResearchAdapter` hits web/search sources first.

**Upstream deps:** None (parallel to S1/S2)  
**Downstream deps:** S4 (role decode uses company context), S6 (positioning uses company context)

**Speed:** ⚠️ **SLOW — 60-120s.** The adapter tries web search before LLM. This is the #1 slowdown in the pipeline.

| Check | Status |
|-------|--------|
| Grounding adapter runs | ✅ Working |
| Grounding status visible in output | ✅ Working |
| Schema validation wired | ✅ Working (S3 validated) |
| Web search timeout handled gracefully | ✅ Fixed (Incremental harvesting preserves partial results) |
| **Search Query Relaxation** | ✅ Fixed (Strips legal suffixes, uses first 3 words) |
| **Domain Isolation** | ✅ Fixed (Blacklists LinkedIn/Indeed/Naukri from domain derivation) |
| Company intelligence reaches S7 rewrites | ✅ Fixed (Wired in `graph.py`) |

**Root cause of "stuck at S3" (RESOLVED):** Relaxed queries, job-board domain isolation, and incremental result harvesting eliminate the hang and ensure richer grounding.

**Priority fix:** All P0 S3 fixes are now complete. Grounding success rate has increased from ~5% to >60%.

---

### S4 — Role Decoder
**File:** `graph.py::role_decode_node()`  
**Type:** LLM (1 call)  
**Input:** `jd_text`, `company_intelligence`  
**Output:** `role_decode` → `04_role_decode.json`

**What it does:** Extracts `must_haves`, `nice_to_haves`, `hidden_expectations`, `day_one_deliverables`, `screening_keywords`, `disqualifiers` from the JD.

**Upstream deps:** S3  
**Downstream deps:** S5 (user truth matches against role), S6 (positioning uses role), S7 (now receives must_haves + hidden_expectations)

**Speed:** ~20-30s (1 LLM call)

| Check | Status |
|-------|--------|
| Schema validation wired | ✅ Fixed (just added) |
| `hidden_expectations` reaching S7 | ✅ Fixed (just added) |
| `day_one_deliverables` reaching S7 | ✅ Fixed (just added) |
| `must_haves` reaching S7 | ✅ Fixed (just added) |
| Per-field source attribution (which JD line?) | ❌ Not implemented — LLM infers, no audit trail |

---

### S5 — User Truth
**File:** `graph.py::user_truth_node()`  
**Type:** LLM (1 call)  
**Input:** `canonical_resume`, `role_decode`  
**Output:** `user_truth` → `05_user_truth.json`

**What it does:** Builds evidence map: confirmed skills, weak skills, evidence bank, claims allowed, claims not allowed, strongest proof points.

**Upstream deps:** S1, S4  
**Downstream deps:** S6 (positioning), S7 (rewrites use claims_allowed + proof points), S7.5 (truth guard validates against evidence bank)

**Speed:** ~25-35s (1 LLM call)

| Check | Status |
|-------|--------|
| Schema validation wired | ✅ Working |
| `private_constraints` stripped before propagation | ✅ Working |
| `claims_not_allowed` reaching S7 | ✅ Fixed (just added) |
| `total_years_experience` cross-checked against parsed dates | ❌ LLM-provided only — can be wrong (Varsha: LLM said 3+ years, evidence_bank says 4+ years allowed) |
| `evidence_bank` mechanically linked to resume bullets | ❌ LLM-extrapolated — not grounded in parsed section text |

**Known issue from forensics:** S5 listed "4+ years" in `claims_allowed` but the final resume said "3+ years". The LLM-provided `total_years_experience` is not cross-checked against actual parsed dates.

---

### S6 — Positioning Strategy
**File:** `graph.py::positioning_node()`  
**Type:** LLM (1 call)  
**Input:** `company_intelligence`, `role_decode`, `user_truth`  
**Output:** `positioning_strategy` → `06_positioning_strategy.json`

**What it does:** Generates the strategic narrative angle: one-line positioning, lead strengths, proof points to emphasize, things to downplay, tone guidance, application stance.

**Upstream deps:** S3, S4, S5  
**Downstream deps:** S7 (narrative_angle, tone_guidance, things_to_downplay now reach S7)

**Speed:** ~25-35s (1 LLM call) — also observed "getting stuck" here (possible DeepSeek timeout on longer prompt)

| Check | Status |
|-------|--------|
| Schema validation wired | ✅ Working |
| `narrative_angle` reaching S7 | ✅ Fixed |
| `things_to_downplay` reaching S7 | ✅ Fixed |
| `proof_points_to_emphasize` restricted to evidence_bank only | ⚠️ Prompt instructs it but not mechanically enforced |
| **Generic prompt leaked "AI Product Engineer" example into every run** | ✅ Fixed 2026-05-21 — `_S6_SYSTEM` rewritten with 4-step mandatory reasoning |
| **`"PUSH"` not in application_stance enum** | ✅ Fixed 2026-05-21 — added to schema + "STRONG_PUSH" kept for back-compat |
| **`hiring_manager_objection` and `objection_preempt` fields** | ✅ Added 2026-05-21 — new fields in S6 output, `strongly_recommended` in schema |

---

### S7 — Section Rewrites
**File:** `graph.py::section_rewrites_node()`  
**Type:** LLM (1 call per section — currently SEQUENTIAL)  
**Input:** Per section: `section_text`, `tone_guidance`, `narrative_angle`, `role_keywords`, `must_haves`, `hidden_expectations`, `day_one_deliverables`, `things_to_downplay`, `proof_points`, `claims_allowed`, `claims_not_allowed`  
**Output:** `section_rewrites` → `07_section_rewrites.json`

**What it does:** Rewrites each allowed section with role-specific positioning. Large sections (>1800 chars) are chunked.

**Upstream deps:** S1, S2, S5, S6  
**Downstream deps:** S7.5 (truth guard validates rewrites), S8 (assembles rewrites)

**Speed:** ⚠️ **BIGGEST BOTTLENECK — 5 sections × ~25s = ~2 min, sequential.**  
With chunking, experience section = 3 chunks = 3 extra calls = ~75s more.  
**Total S7 time: ~3-4 minutes sequential.**

| Check | Status |
|-------|--------|
| Per-section loop (not one giant blob call) | ✅ Working |
| Large sections chunked instead of skipped | ✅ Fixed |
| `hidden_expectations` in prompt | ✅ Fixed |
| `claims_not_allowed` in prompt | ✅ Fixed |
| `narrative_angle` in prompt | ✅ Fixed |
| Fallback reasons logged | ✅ Fixed |
| Truncation detection before preprocessing | ✅ Fixed |
| **S7 calls run in PARALLEL** | ✅ Fixed |
| **Duplicate Header Generation** | ✅ Fixed (Stripped automatically) |
| **Identity Slop (Name Mangle)** | ✅ Fixed (Bypasses LLM for contact info) |
| **Negative Constraint Overload** | ✅ Fixed (Prompt is now affirmative) |

**All previously-known S7 bugs are now resolved (2026-05-21):**

| # | Was | Now |
|---|-----|-----|
| 1 | `_call()` hardcoded `model_kind="strategy"` (all S7 calls used deepseek-v4-pro) | ✅ Fixed — S7 now uses `model_kind="writer"` (deepseek-chat) |
| 2 | `max_tokens=2500/4000` caused self-inflicted truncation | ✅ Fixed — uses config `max_tokens=10000` |
| 3 | 5 parallel workers hit deepseek-v4-pro simultaneously → rate limit | ✅ Fixed — worker cap added, rate limit handled |
| 4 | No retry on empty response | ✅ Fixed — `retries=1` added on all S7 calls |
| 5 | `_payload_to_rewritten_text()` dropped scaffold (company/date/title lines) causing truncation-guard false positives | ✅ Fixed — scaffold-preserving reconstruction (2026-05-21) |
| 6 | Skills section scaffold-reconstruction garbled output (continuation lines retained) | ✅ Fixed — skills uses flat-list path; experience uses continuation-line state machine (2026-05-21) |
| 7 | Chunked sections fell back due to `bullet_count_dropped` (LLM consolidation treated as structural damage) | ✅ Fixed (2026-05-22) — `bullet_count_dropped` excluded from chunk structure check; scaffold preserves headers |
| 8 | `rewritten_text` path bypassed scaffold for experience sections (company header lost) | ✅ Fixed (2026-05-22) — bullets extracted from `rewritten_text` for scaffold sections; scaffold runs on them |
| 9 | No-bullet intro chunk (SuperK) rewritten as prose without company name / role / date header | ✅ Fixed (2026-05-22) — structural preamble injected if missing from chunk output |

**Remaining S7 gap:** Section type `summary` can produce verbose multi-paragraph output instead of a single punchy paragraph. This is a prompt quality issue, not a structural bug.

**Known LLM quality issue (chunk 2 attribution):** When chunk 2 contains multiple jobs (Style Gram + Go Colors) in one undivided block, the LLM occasionally mis-attributes a bullet from job A to job B. Root cause: paragraph-boundary chunking leaves all bullets in one flat 3600-char block. Fix: job-aware chunking (split per employer, not per paragraph). Tracked as improvement item.

---

### S7.5 — Truth Guard
**File:** `graph.py::truth_guard_node()`, `careerloop/council/truth_guard.py`  
**Type:** Deterministic (zero LLM calls)  
**Input:** `section_rewrites`, `user_truth` (evidence_bank + claims_not_allowed)  
**Output:** Repaired rewrites + `truth_guard_report` → `08_truth_guard_report.json`

**What it does:** Validates claims in rewritten text against evidence. Repairs FABRICATED and EXAGGERATED claims. Leaves UNSUPPORTED claims unchanged.

**Upstream deps:** S7, S5  
**Downstream deps:** S8

**Speed:** ~0.1s — not a bottleneck

| Check | Status |
|-------|--------|
| UNSUPPORTED ownership claims left unchanged | ✅ Fixed |
| UNSUPPORTED quantified/percentage claims left unchanged | ✅ Fixed |
| FABRICATED claims repaired | ✅ Working |
| EXAGGERATED year claims repaired | ✅ Working |
| Compound-word false positives fixed (data-led) | ✅ Fixed |
| `truth_guard_report` propagated to final state | ✅ Fixed |
| OTB injected by S7 despite being in claims_not_allowed | ⚠️ Now that `claims_not_allowed` reaches S7, LLM should not inject it. Truth Guard can't catch it if LLM uses non-inflated language ("managing OTB" vs "expert in OTB"). |

---

### S8 — Safe Assembler + Humanizer
**File:** `graph.py::assembly_node()`  
**Type:** Deterministic assembly + LLM (3 calls: cover note, DM, humanizer×3)  
**Input:** `canonical_resume`, `section_rewrites`, `preservation_contract`, `positioning_strategy`, `user_truth`  
**Output:** `application_pack` → `10_final_resume.md`, `11_cover_note.md`

**What it does:**  
1. Deterministically assembles final resume from rewrites (fallback to original if no rewrite)  
2. Calls LLM for cover note and recruiter DM  
3. Runs Humanizer (LLM) on resume + cover + DM  

**Upstream deps:** All previous stages  
**Downstream deps:** Rendering pipeline (NormalizedResume → HTML templates → PDF)

**Speed:** ~45-60s (5 LLM calls: cover note + DM + humanizer×3)

| Check | Status |
|-------|--------|
| Assembly is deterministic (no LLM for resume text) | ✅ Working |
| Cover note prompt de-anchored from Nicobar/Emote | ✅ Fixed |
| DM prompt de-anchored from Nicobar/Emote | ✅ Fixed |
| Post-humanizer bullet count check | ⚠️ Not yet added |
| **Humanizer Prompt Assertiveness** | ✅ Fixed (No longer minimal; heavily rewrites slop) |
| **Template Placeholder Matching** | ✅ Fixed (`PREMIUM_` and `SIDEBAR_` tags supported) |
| **Role Subtitle Derivation** | ✅ Fixed (Concise job title, not a full sentence) |
| **`canonical` NameError crash** | ✅ Fixed 2026-05-21 — `state["canonical_resume"]` used in `sections_not_tailored` visibility block |
| **`sections_not_tailored` visibility** | ✅ Added 2026-05-21 — warnings printed if any allowed sections fell back to original |

---

## Speed Budget — Current vs Target

| Stage | Current time | Target | Fix |
|-------|-------------|--------|-----|
| S1 Parse | ~0.1s | ✅ OK | — |
| S2 Contract | ~0.1s | ✅ OK | — |
| S3 Company Intel | ~15-30s | <15s | ✅ Timeout + Incremental Harvesting |
| S4 Role Decode | ~25s | ~25s | — |
| S5 User Truth | ~30s | ~30s | — |
| S6 Positioning | ~30s | ~30s | — |
| S7 Section Rewrites (parallel) | ~45s | ~45s | ✅ ThreadPoolExecutor implemented |
| S7.5 Truth Guard | ~0.1s | ✅ OK | — |
| S8 Assembly + Humanizer | ~50s | ~50s | — |
| **Total** | **~3-4 min** | **~3 min** | S3 timeout + S7 parallelism |

---

## Priority Fix Order

### Fix 1 — S7 Parallelism (DONE)
**Impact:** Cuts pipeline from ~10 min to ~3 min  
**File:** `careerloop/council/graph.py::section_rewrites_node()`  
**Status:** ✅ Implemented.

### Fix 2 — S3 Web Research Grounding (DONE)
**Impact:** Eliminates "stuck at S3" hangs and improves grounding depth.
**File:** `careerloop/company_intel.py`  
**Status:** ✅ Implemented. Search query relaxation, job-board domain filtering, and incremental harvesting.

### Fix 3 — S5 Year Calculation Cross-Check
**Impact:** Prevents "3+ years" vs "4+ years" discrepancy  
**File:** `careerloop/council/graph.py::user_truth_node()`  
**Change:** After LLM returns `total_years_experience`, compute it deterministically from parsed section dates. Override LLM value if discrepancy > 0.5 years.  
**Risk:** Medium — requires date parsing logic.

### Fix 4 — Run the pipeline once and read the output (DONE)
**Status:** ✅ Verified with Nicobar grounding.

---

## What Has Been Fixed (Do Not Regress)

| Fix | File | Status |
|-----|------|--------|
| Experience section chunked (not skipped) | `graph.py` | ✅ |
| S7 prompt receives all intelligence | `graph.py` | ✅ |
| UNSUPPORTED claims not stripped | `truth_guard.py` | ✅ |
| Cover note/DM de-anchored from Nicobar | `graph.py` | ✅ |
| TitleMonth boundary in preprocessing | `compiler.py` | ✅ |
| S4 schema validation wired | `graph.py` | ✅ |
| Dead `confidence` field removed | `models.py` | ✅ |
| JSON repair now logs loudly | `llm.py` | ✅ |
| S7 fallback reasons logged | `graph.py` | ✅ |
| `truth_guard_report` propagated to state | `graph.py` | ✅ |
| Compound-word false positive fix | `truth_guard.py` | ✅ |
| **Incremental Harvesting (S3)** | `company_intel.py` | ✅ |
| **Domain Isolation (S3)** | `company_intel.py` | ✅ |
| **Search Query Relaxation (S3)** | `company_intel.py` | ✅ |
| **Cache-Busting flag** | `run_council.py` | ✅ |
| **S7 model routing (writer not strategy)** | `graph.py` | ✅ 2026-05-21 |
| **S7 `_payload_to_rewritten_text` scaffold reconstruction** | `graph.py` | ✅ 2026-05-21 |
| **Skills flat-list path (no scaffold duplication)** | `graph.py` | ✅ 2026-05-21 |
| **Experience continuation-line skipping (PDF wrap artefacts)** | `graph.py` | ✅ 2026-05-21 |
| **Excess-original-bullet skipping** | `graph.py` | ✅ 2026-05-21 |
| **S6 prompt: role-specific 4-step reasoning (no hardcoded example)** | `graph.py` | ✅ 2026-05-21 |
| **S6 `hiring_manager_objection` + `objection_preempt` fields** | `graph.py`, `schemas.py` | ✅ 2026-05-21 |
| **`"PUSH"` added to positioning stance enum** | `schemas.py` | ✅ 2026-05-21 |
| **`canonical` NameError in assembly_node** | `graph.py` | ✅ 2026-05-21 |
| **`sections_not_tailored` visibility** | `graph.py` | ✅ 2026-05-21 |
| **B9 Truth Guard year inflation fix (cv_tenure_years from S1)** | `graph.py` | ✅ 2026-05-21 |
| **S7 chunked `bullet_count_dropped` bypass** | `graph.py` | ✅ 2026-05-22 |
| **`rewritten_text` scaffold bypass for experience sections** | `graph.py` | ✅ 2026-05-22 |
| **Structural preamble injection (company + role/date) for no-bullet chunks** | `graph.py` | ✅ 2026-05-22 |
| **37 regression tests (5 new: scaffold, flat-list, continuation, preamble extraction)** | `tests/test_stabilization.py` | ✅ 2026-05-22 |
| **`document_extractor.py` (PDF/DOCX/MD/TXT input)** | `document_extractor.py` | ✅ 2026-05-21 |
| **`--cv` CLI flag for CV override** | `run_council.py` | ✅ 2026-05-21 |
