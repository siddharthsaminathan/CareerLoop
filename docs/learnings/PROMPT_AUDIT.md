# CareerLoop — Full Prompt & Pipeline Audit

**Audited:** 2026-05-19  
**Auditor:** Claude (via parallel subagent code inspection)  
**Files inspected:**
- `careerloop/council/graph.py` (661 lines — all 8 LLM prompts live here)
- `careerloop/council/humanizer_prompts.py` (84 lines — 4 LLM prompts)
- `careerloop/council/humanizer.py` (528 lines)
- `careerloop/council/humanizer_rules.py` (97 lines)
- `careerloop/council/compiler.py` (525 lines)
- `careerloop/council/truth_guard.py` (762 lines)
- `careerloop/council/orchestrator.py` (308 lines)
- `careerloop/council/llm.py` (149 lines)
- `careerloop/council/models.py` (255 lines)
- `careerloop/rendering/resume_model.py`, `normalizer.py`, `template_registry.py`
- `careerloop/india_fit_llm.py` (243 lines)
- `batch/batch-prompt.md` (395 lines)
- `modes/_shared.md` (240 lines)
- `modes/pdf.md` (180 lines)
- `modes/deep.md`, `modes/apply.md`, `modes/interview-prep.md`, `modes/patterns.md`, `modes/scan.md`, `modes/tracker.md`, `modes/training.md`, `modes/pipeline.md`, `modes/project.md`
- `.claude/skills/resume-design/SKILL.md`
- `.claude/skills/showcase-builder/SKILL.md`
- `careerloop/docs/CAREERLOOP_COUNCIL_AUDIT.md`
- `careerloop/docs/FUCKUPS.md`
- `careerloop/docs/specs/humanizer-design.md`
- `careerloop/docs/specs/company-intel-design.md`

**Status:** Audit-only. No prompts rewritten.

---

## 1. Executive Summary

### What the current prompt system does

CareerLoop operates **two parallel prompt pipelines** that serve different use cases and are almost completely isolated from each other:

**Pipeline A — Resume Council (Python/LangGraph)**  
A deterministic + LLM-assisted 8-stage graph in `careerloop/council/graph.py`. Takes a master CV and a job description, runs them through 9 nodes (2 deterministic, 5 LLM, 2 hybrid), and produces a tailored resume markdown + cover note + recruiter DM. Uses DeepSeek via `CouncilLLMClient`. Outputs JSON artifacts per stage to `output/council/{person}/{job}/`.

**Pipeline B — career-ops Skill (Markdown-prompt, LLM-agnostic)**  
A prompt library loaded at conversation time by the AI CLI (Claude Code, Gemini, etc.). The core prompts live in `modes/` directory files and `batch/batch-prompt.md`. This pipeline is entirely in-context — the agent is instructed to read files, call WebSearch, generate HTML from a template, and write outputs. No Python orchestration. Uses whatever model the user's CLI is attached to.

**These two pipelines are not connected.** Pipeline A produces a structured resume JSON; Pipeline B generates a PDF by re-reading `cv.md` from scratch. Pipeline A's output (`10_final_resume.md`) is not used as input to Pipeline B's PDF generation.

### Where it is strong

- **S3 Company Intelligence (FIXED):** Now uses a real research engine (`company_intel.py`) with relaxed search queries, incremental result harvesting, and job-board domain isolation. Grounding has moved from JD-only to PARTIAL/READY.
- **Deterministic assembly** (System 1, 2, 8): `ResumeCompiler.parse_markdown()` uses mistune AST — no regex section-splitting. Assembly is zero-LLM. This correctly enforces the preservation contract.
- **Humanizer architecture**: 5-phase (detect → realism → surgical rewrite → tone → sanitize), partially deterministic. The banned-words list (`humanizer_rules.py`) is real and specific.
- **TruthGuard**: deterministic claim extraction using compiled regex patterns for years, percentages, skills, ownership, quantified achievements. Correct approach.
- **Archetype detection** in `batch-prompt.md` and `modes/_shared.md`: 6 archetypes with specific framing per archetype. This is the strongest part of the career-ops skill layer.
- **`_profile.md` override pattern**: User customizations always override system defaults. Data contract is enforced textually.
- **showcase-builder SKILL.md**: Has a real canonical template, 5 color variants mapped to company archetypes, explicit component library — the most design-aware prompt in the system.

### Where it is broken

1. **5 of 6 LLM nodes in the Council have no JSON schema in the system prompt** — they rely on `complete_json()` repair magic to guess output structure.
2. **System 3 (Company Intelligence) is not a research engine** — it is pure LLM memory recall. The prompt sends company name + JD text and asks the model to "analyze the company." There is no web lookup, no API, no grounding. The model invents data.
3. **System 5 (User Truth) can hallucinate confirmed skills** — nothing mechanically cross-checks the LLM's `confirmed_skills` list against the actual parsed sections from System 1.
4. **System 7 (Section Rewrites) passes the full canonical_resume JSON** — the LLM must infer which sections to edit from the preservation contract rather than receiving a structured per-section editing spec. It frequently edits sections it should leave alone.
5. **Cover note and recruiter DM prompts are 1-2 sentences each** — the most candidate-facing outputs are generated from the thinnest prompts.
6. **Pipeline A and Pipeline B are disconnected** — the Council's tailored resume does not flow into the PDF generator. The PDF still reads raw `cv.md`.
7. **The batch-prompt.md is written in Spanish** while the rest of the system is in English — a language mismatch that could confuse monolingual model instances.
8. **Private section detection** (System 2) uses a keyword list that misses variants ("Compensation Philosophy," "Negotiation Notes") — a leak surface.

### Why outputs feel generic/resume-like

The LLM nodes are given **role descriptions** ("You are a senior technical writer") but **no persona**, **no audience model**, and **no output quality bar**. The instructions say what not to do (no cope, no AI-slop) but provide minimal positive guidance about what the output should feel like. The Section Rewrites node (`_S7_SYSTEM`) has 8 constraint bullets and 0 affirmative craft instructions. The model defaults to conservative, formal resume language because that is what its training data associates with "resume" tasks.

### Why portfolio pages feel weak or overhyped

The showcase-builder skill has no instructions for **content strategy** — it asks the user for raw inputs (metrics, lessons, mapping) but does not guide the model in how to select, sequence, or frame those inputs for the specific audience (a Nicobar hiring manager vs. a SaaS founder office). The color variant selection is correct; the narrative strategy is absent. The model fills this gap by defaulting to superlative language ("built X from zero") or overclaiming ownership.

### Where model behavior is being shaped incorrectly

- **System 7 calls the model "a senior technical writer"** — this pushes it toward formal, long-form prose rather than concise, recruiter-readable bullets.
- **System 6 calls the model "a senior career strategist"** — fine, but then passes 3 upstream JSON blobs with no instruction on how to weigh them.
- **The Humanizer's SURGICAL_HUMANIZE_SYSTEM** has 10 negative rules ("DO NOT add new claims") and 1 positive rule ("sound like an experienced professional"). The model's creative output is over-constrained negatively and under-guided positively.
- **batch-prompt.md** correctly defines archetypes but uses **framing language inside the prompt itself** ("Convertir 'builder' en señal profesional") — meaning the model is instructed to spin positioning rather than discover it. This is prompt-induced advocacy.

---

## 2. Pipeline Map

### Pipeline A — Resume Council (Python/LangGraph)

```
Input:
  master_cv (str from cv.md)
  jd_text (str from ledger)
  company, job_title, job_url (from ledger)
  profile (dict from profile_manager)
  today (str date)
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ System 1: parse_node                                        │
│ File: graph.py:80-92 | Fn: parse_node()                    │
│ Prompt: NONE (deterministic)                                │
│ Input: master_cv (str)                                      │
│ Output: canonical_resume (dict → CanonicalResume)          │
│ Tool: compiler.py → ResumeCompiler.parse_markdown()        │
│ Consumer: contract_node                                     │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ System 2: contract_node                                     │
│ File: graph.py:97-113 | Fn: contract_node()                │
│ Prompt: NONE (deterministic)                                │
│ Input: canonical_resume (dict), profile (dict)             │
│ Output: preservation_contract (dict → PreservationContract)│
│ Tool: compiler.py → ResumeCompiler.build_contract()        │
│ Consumer: section_rewrites_node                             │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ System 3: company_intelligence_node                         │
│ File: graph.py:118-165 | Fn: company_intelligence_node()   │
│ Prompt: _S3_SYSTEM (graph.py:118-138) — 10 lines           │
│ Input: company (str), jd_text[:3000] (str)                 │
│ Output: company_intelligence (dict)                        │
│ LLM: DeepSeek via CouncilLLMClient("strategy") T=0.2      │
│ Consumer: role_decode_node, positioning_node                │
│ ⚠️ NO JSON schema | ⚠️ Pure LLM recall | ⚠️ HIGH hallucination│
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ System 4: role_decode_node                                  │
│ File: graph.py:170-206 | Fn: role_decode_node()            │
│ Prompt: _S4_SYSTEM (graph.py:170-185) — 11 lines           │
│ Input: jd_text (str), company_intelligence (dict)          │
│ Output: role_decode (dict → RoleDecode)                    │
│ LLM: DeepSeek via CouncilLLMClient("strategy") T=0.2      │
│ Consumer: user_truth_node, positioning_node                 │
│ ✅ Has JSON schema in prompt | ⚠️ inherits S3 bad data      │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ System 5: user_truth_node                                   │
│ File: graph.py:211-246 | Fn: user_truth_node()             │
│ Prompt: _S5_SYSTEM (graph.py:211-226) — 15 lines           │
│ Input: canonical_resume (dict), role_decode (dict)         │
│ Output: user_truth (dict → UserTruth)                      │
│ LLM: DeepSeek via CouncilLLMClient("strategy") T=0.2      │
│ Consumer: positioning_node, section_rewrites_node, truth_guard│
│ ⚠️ NO JSON schema | ⚠️ HIGH hallucination on confirmed_skills│
│ ⚠️ private_constraints appear IN OUTPUT (see §3.4)          │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ System 6: positioning_node                                  │
│ File: graph.py:251-283 | Fn: positioning_node()            │
│ Prompt: _S6_SYSTEM (graph.py:251-266) — 13 lines           │
│ Input: company_intelligence + role_decode + user_truth      │
│ Output: positioning_strategy (dict → PositioningStrategy)  │
│ LLM: DeepSeek via CouncilLLMClient("strategy") T=0.2       │
│ Consumer: section_rewrites_node, assembly_node              │
│ ⚠️ NO JSON schema | ⚠️ no instruction on how to weigh inputs│
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ System 7: section_rewrites_node                             │
│ File: graph.py:288-336 | Fn: section_rewrites_node()       │
│ Prompt: _S7_SYSTEM (graph.py:288-313) — 17 lines           │
│ Input: canonical_resume + preservation_contract + positioning│
│        + user_truth (all as raw JSON dumps)                 │
│ Output: section_rewrites (dict → SectionRewrites)          │
│ LLM: DeepSeek via CouncilLLMClient("strategy") T=0.2       │
│ Consumer: truth_guard_node, assembly_node                   │
│ ⚠️ No per-section allowed_to_edit flag                      │
│ ⚠️ Full resume JSON dump instead of structured per-section  │
│ ⚠️ HIGH hallucination — link drop, unauthorized edits       │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ System 7.5: truth_guard_node                                │
│ File: graph.py:341-410 | Fn: truth_guard_node()            │
│ Prompt: NONE (deterministic — regex + Jaccard similarity)  │
│ Input: section_rewrites + user_truth                        │
│ Output: section_rewrites (repaired), truth_guard_report     │
│ Tool: truth_guard.py → TruthGuard.validate() + repair()    │
│ Consumer: assembly_node                                     │
│ ⚠️ Exact-string matching insufficient for paraphrased claims│
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ System 8: assembly_node                                     │
│ File: graph.py:427-620 | Fn: assembly_node()               │
│ Sub-prompts: _COVER_NOTE_SYSTEM (graph.py:415-418) 3 lines  │
│              _RECRUITER_DM_SYSTEM (graph.py:420-423) 3 lines│
│ Input: all prior artifacts                                  │
│ Output: application_pack (dict → ApplicationPack)          │
│ Assembly: DETERMINISTIC via ResumeCompiler.assemble()      │
│ Messages: LLM (DeepSeek "writer" model) for cover + DM     │
│ Humanizer: runs on resume + cover + DM (Humanizer class)   │
│ Consumer: orchestrator.py (saves to disk)                   │
│ ⚠️ Cover note prompt: 3 sentences                           │
│ ⚠️ DM prompt: 3 sentences                                   │
│ ⚠️ user_review_summary is hardcoded string                  │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
Output artifacts (output/council/{person}/{job}/):
  00_input_snapshot.json
  01_canonical_resume.json
  02_preservation_contract.json
  03_company_intelligence.json
  04_role_decode.json
  05_user_truth.json
  06_positioning_strategy.json
  07_section_rewrites.json
  10_final_resume.md        ← humanized resume markdown
  11_cover_note.md
  15_quality_report.md
  16_user_review_summary.md
  17_council_run_log.json
```

### Pipeline B — career-ops Skill (Markdown/In-Context)

```
Input:
  Job URL or JD text (from user)
  cv.md (read from disk at runtime)
  modes/_profile.md + config/profile.yml
  article-digest.md (if exists)
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 0: Archetype Detection                                  │
│ File: modes/_shared.md:74-87, batch/batch-prompt.md:70-104  │
│ Prompt: Inline in modes files (classify into 6 archetypes)  │
│ Consumer: All subsequent steps                               │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 1: JD Acquisition                                       │
│ Tool: Playwright (browser_navigate + browser_snapshot)       │
│ Fallback: WebFetch                                           │
│ Batch: reads from local JD file                              │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 2: Evaluation A–G                                       │
│ File: modes/_shared.md + modes/_profile.md + oferta.md*     │
│ (*oferta.md does not exist — inlined in batch-prompt.md)    │
│ Blocks: A(role summary) B(match) C(seniority) D(comp)       │
│         E(personalization plan) F(interview prep) G(posting)│
│ Output: Markdown report → reports/{num}-{slug}-{date}.md    │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 3: PDF Generation                                       │
│ File: modes/pdf.md (interactive), batch-prompt.md §Paso 4  │
│ Template: templates/cv-template.html                         │
│ Input: cv.md (re-read from scratch, NOT Council output)      │
│ Output: output/cv-{candidate}-{company}-{date}.pdf          │
│ ⚠️ Does NOT use Pipeline A output                            │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 4: Tracker Line                                         │
│ Output: batch/tracker-additions/{num}.tsv                    │
│ Merges via: node merge-tracker.mjs                           │
└──────────────────────────────────────────────────────────────┘
```

### Pipeline C — India Fit Engine (Python/LLM)

```
Input: JobPosting list + user profile dict
        │
        ▼
LLMIndiaFitEngine.score_job()
File: careerloop/india_fit_llm.py
System Prompt: SYSTEM_PROMPT (lines 69-103) — 9-dimension JSON schema
Input: JD snippet + user profile structured dict
Output: {overall_score, recommendation, reason, risks, dimensions{}}
Model: deepseek-chat (configurable via config/models.yml)
Temperature: 0.3
Consumer: daily_runner.py → shortlist formatter
```

### Pipeline D — Showcase Builder (Skill/In-Context)

```
Input: User provides profile data (name, metrics, lessons, principles)
       + target company + role
        │
        ▼
File: .claude/skills/showcase-builder/SKILL.md
Template: templates/showcase-template.html (canonical template)
Output: output/showcase-{slug}.html + .pdf
No intermediate stages — single LLM generation
```

---

## 3. Prompt Inventory Table

| # | Prompt Name | File Path | Stage | Purpose | Inputs | Output Format | Model | Temperature | Called By | Downstream Consumer | Status |
|---|-------------|-----------|-------|---------|--------|---------------|-------|-------------|-----------|---------------------|--------|
| 1 | `_S3_SYSTEM` | `graph.py:118-138` | Company Intelligence | Extract company signals from JD | company name, JD[:3000] | JSON dict | DeepSeek (strategy) | 0.2 | `company_intelligence_node()` | role_decode, positioning | **active** |
| 2 | `_S4_SYSTEM` | `graph.py:170-185` | Role Decoder | Decode JD requirements | JD text, company_intelligence | JSON dict (schema in prompt) | DeepSeek (strategy) | 0.2 | `role_decode_node()` | user_truth, positioning | **active** |
| 3 | `_S5_SYSTEM` | `graph.py:211-226` | User Truth | Map candidate experience to role | canonical_resume, role_decode | JSON dict | DeepSeek (strategy) | 0.2 | `user_truth_node()` | positioning, rewrites, truth_guard | **active** |
| 4 | `_S6_SYSTEM` | `graph.py:251-266` | Positioning | Create strategic narrative | company_intel, role, user_truth | JSON dict | DeepSeek (strategy) | 0.2 | `positioning_node()` | rewrites, assembly | **active** |
| 5 | `_S7_SYSTEM` | `graph.py:288-313` | Section Rewrites | Rewrite allowed resume sections | resume JSON, contract, strategy, user_truth | JSON dict (rewrites per section) | DeepSeek (strategy) | 0.2 | `section_rewrites_node()` | truth_guard, assembly | **active** |
| 6 | `_COVER_NOTE_SYSTEM` | `graph.py:415-418` | Cover Note | Generate 3-sentence cover note | role, company, strategy, proof points | `{"cover_note": "..."}` | DeepSeek (writer) | 0.2 | `assembly_node()` | ApplicationPack | **active** |
| 7 | `_RECRUITER_DM_SYSTEM` | `graph.py:420-423` | Recruiter DM | Generate 2-sentence LinkedIn DM | role, company, strategy | `{"recruiter_message": "..."}` | DeepSeek (writer) | 0.2 | `assembly_node()` | ApplicationPack | **active** |
| 8 | `SLOP_DETECTOR_SYSTEM` | `humanizer_prompts.py:3-22` | Humanizer Phase 1 | Detect AI-generated language patterns | text to humanize | `{"flags": [...]}` | DeepSeek (writer) | inherited | `Humanizer._detect_slop()` | surgical_humanize | **active** |
| 9 | `RECRUITER_REALISM_SYSTEM` | `humanizer_prompts.py:24-39` | Humanizer Phase 2 | Identify credibility risks | text | `{"concerns": [...]}` | DeepSeek (writer) | inherited | `Humanizer._check_realism()` | (advisory only) | **active** |
| 10 | `SURGICAL_HUMANIZE_SYSTEM` | `humanizer_prompts.py:41-62` | Humanizer Phase 3 | Minimal surgical rewrite | text + slop flags | `{"humanized_text": "..."}` | DeepSeek (writer) | inherited | `Humanizer._surgical_humanize()` | tone_adapter | **active** |
| 11 | `TONE_ADAPTER_SYSTEM` | `humanizer_prompts.py:64-83` | Humanizer Phase 4 | Adapt tone to company type | humanized text, tone, company_type | `{"adapted_text": "..."}` | DeepSeek (writer) | inherited | `Humanizer._adapt_tone()` | sanitizer | **active** |
| 12 | `LLMIndiaFitEngine.SYSTEM_PROMPT` | `india_fit_llm.py:69-103` | India Fit Engine | Score job fit across 9 dimensions | job + user profile | Full JSON with dimensions | DeepSeek (fit model) | 0.3 | `score_job()` | daily_runner, shortlist | **active** |
| 13 | Archetype detection (inline) | `modes/_shared.md:74-87` | Evaluation Step 0 | Classify JD into 6 archetypes | JD text | Archetype label | CLI model | n/a | Agent at evaluation time | All A-G blocks | **active** |
| 14 | Evaluation A–G (inline) | `modes/_shared.md:29-115` + `batch/batch-prompt.md:69-395` | Offer Evaluation | Full offer analysis pipeline | JD, cv.md, profile | Markdown report | CLI model | n/a | Agent at evaluation time | PDF gen, tracker | **active (dual — interactive + batch)** |
| 15 | PDF generation pipeline | `modes/pdf.md:1-180` | PDF Mode | Generate ATS-optimized PDF | cv.md, JD, template | HTML → PDF | CLI model | n/a | Agent when user says /pdf | output/*.pdf | **active** |
| 16 | Interview prep | `modes/interview-prep.md:1-142` | Interview Prep | STAR stories, company research | cv.md, JD, company | Markdown prep doc | CLI model | n/a | Agent on demand | user review | **active** |
| 17 | Deep research | `modes/deep.md:1-68` | Company Research | Deep company + role analysis | company, role | Markdown report | CLI model | n/a | Agent on demand | evaluation | **active** |
| 18 | Apply mode | `modes/apply.md:1-108` | Application Filling | Fill application forms | JD, cv.md, profile | Form answers (STOP before submit) | CLI model | n/a | Agent when user applies | human approval | **active** |
| 19 | Pattern analysis | `modes/patterns.md:1-155` | Pattern Analysis | Rejection/acceptance pattern mining | applications.md, reports | Analysis + recommendations | CLI model | n/a | Agent on demand | user review | **active** |
| 20 | Showcase builder | `.claude/skills/showcase-builder/SKILL.md:1-209` | Portfolio Builder | Build editorial HTML showcase | user data, company, role | HTML + PDF | CLI model | n/a | Skill invocation | output/showcase-* | **active** |
| 21 | Resume design | `.claude/skills/resume-design/SKILL.md` | Resume Design | Design resume layout/style | user data | HTML resume | CLI model | n/a | Skill invocation | output/* | **active** |
| 22 | Writing style calibration (inline) | `modes/_shared.md:138-212` | Style Calibration | Extract user voice from samples | writing-samples/ | Style descriptor block | CLI model | n/a | Auto-run on evaluation | _profile.md | **active** |
| 23 | Scan mode | `modes/scan.md:1-250` | Portal Scanner | Scan ATS portals for new roles | portals.yml | Markdown shortlist | CLI model | n/a | /scan command | pipeline.md | **active** |
| 24 | Tracker mode | `modes/tracker.md` | Status Tracking | Read/update applications.md | applications.md | Status summary | CLI model | n/a | /tracker command | user review | **active** |
| 25 | compare.md | `modes/compare.md` | Offer Compare | Compare multiple offers | multiple reports | Comparison table | CLI model | n/a | /compare command | DOES NOT EXIST | **dead** |
| 26 | contact.md | `modes/contact.md` | LinkedIn Outreach | LinkedIn DM generation | contact info, JD | DM text | CLI model | n/a | /contact command | DOES NOT EXIST | **dead** |
| 27 | oferta.md | `modes/oferta.md` | Single Offer Eval | Interactive offer evaluation | JD, cv.md | Blocks A-G | CLI model | n/a | Auto-pipeline | DOES NOT EXIST | **dead (inlined in batch-prompt.md)** |

---

## 4. Full Prompt Extraction

### 4.1 `_S3_SYSTEM` — Company Intelligence (graph.py:118-138)

**Role assigned to model:** "a company researcher"

```
You are a company researcher extracting signals from the job description and your knowledge.
CRITICAL: Distinguish JD-extracted facts from recalled knowledge. Mark source clearly.
JD text contains rich signals: company mission, team structure, tech stack, culture hints, hiring posture.
Extract what the JD reveals. For facts NOT in the JD, mark confidence LOW and add to missing_data.
NEVER invent funding amounts, employee counts, or revenue figures.

EXAMPLE JSON OUTPUT:
{
    "summary": "Nicobar is a D2C lifestyle brand...",
    "business_model": "D2C e-commerce, premium home and apparel",
    "india_presence": "Delhi HQ, retail stores across India (from JD context)",
    "maturity": "growth",
    "hiring_urgency": "HIGH",
    "culture_signals": ["design-driven", "founder-led", "CEO-office role signals flat hierarchy"],
    "red_flags": [],
    "positioning_implications": "Lead with consumer-facing AI product experience",
    "interview_implications": "Expect design-thinking + business-outcome focus",
    "signals_from_jd": ["CEO-office role", "AI-native ambition", "retail/e-commerce domain", "4 product areas"],
    "confidence": 0.5,
    "missing_data": ["funding_round", "employee_count", "recent_layoffs", "glassdoor_rating"]
}
```

**User prompt at runtime:**
```
Company: {company}

JD EXCERPT (extract signals from this):
{jd[:3000]}

Extract company intelligence from the JD text above.
For facts the JD does NOT reveal, use UNKNOWN and add to missing_data.
```

**Variables injected:** `state['company']`, `state['jd_text'][:3000]`  
**Temperature:** 0.2  
**JSON schema:** Embedded as example only — not enforced  

---

### 4.2 `_S4_SYSTEM` — Role Decoder (graph.py:170-185)

**Role assigned to model:** "a master role decoder"

```
You are a master role decoder. Extract what the job actually wants from the JD.
Separate must-haves from nice-to-haves. Identify hidden expectations.
Output JSON matching the example format below.

EXAMPLE JSON OUTPUT:
{
  "normalized_title": "AI Product Engineer",
  "seniority": "mid-senior",
  "must_haves": ["Python", "LLM API experience", "SQL", "frontend skills"],
  "nice_to_haves": ["retail/e-commerce experience", "IIT/BITS/NIT"],
  "hidden_expectations": ["CEO-facing communication", "business-outcome thinking"],
  "day_one_deliverables": ["Customer personalization intelligence layer"],
  "screening_keywords": ["AI-native", "clienteling", "business intelligence"],
  "disqualifiers": ["no LLM experience", "no coding skills"],
  "confidence": 0.85
}
```

**User prompt at runtime:**
```
JD: {state['jd_text']}
Company Context: {json.dumps(state['company_intelligence'])}
```

**Variables injected:** full JD text, full company_intelligence dict  
**Temperature:** 0.2  
**JSON schema:** Embedded as example (best-structured prompt in the system)  

---

### 4.3 `_S5_SYSTEM` — User Truth (graph.py:211-226)

**Role assigned to model:** "a rigorous auditor"

```
You are a rigorous auditor. Build a truthful evidence map in JSON.
Map candidate's experience to role requirements. Calculate seniority accurately.
Seniority is locked based on the earliest professional date in the resume.
Today is {today}.

EXAMPLE JSON OUTPUT:
{{
  "total_years_experience": 4.5,
  "confirmed_skills": [{{"skill": "Python", "years": 4, "evidence": "Built production AI systems"}}],
  "weak_skills": ["Kubernetes"],
  "evidence_bank": {{"Python": ["Built AI quality management system", "Multi-agent orchestration"]}},
  "strongest_proof_points": ["Shipped AI that automates enterprise workflows"],
  "claims_allowed": ["4+ years Python", "LLM API experience", "Agent architectures"],
  "claims_not_allowed": ["10 years AI experience", "Deep learning expert"],
  "private_constraints": ["min salary 25L", "Chennai location preferred"]
}}
```

**User prompt at runtime:**
```
Resume: {json.dumps(state['canonical_resume'])}
Role: {json.dumps(state['role_decode'])}
```

**Variables injected:** full canonical_resume dict (all sections), full role_decode dict  
**Temperature:** 0.2  
**JSON schema:** Example only — not enforced  
**Critical leak:** `private_constraints` is in the example output — LLM may include salary/location data in this dict which is then stored in `05_user_truth.json`

---

### 4.4 `_S6_SYSTEM` — Positioning Strategy (graph.py:251-266)

**Role assigned to model:** "a senior career strategist"

```
You are a senior career strategist. Create the strategic narrative in JSON.
Do NOT rewrite the resume. Decide on the application stance and angle.
Base all proof points on evidence from User Truth evidence_bank only.

EXAMPLE JSON OUTPUT:
{
  "one_line_positioning": "AI Product Engineer who ships enterprise AI from concept to production",
  "narrative_angle": "Product-minded AI engineer with manufacturing quality digitization experience",
  "lead_strengths": ["LLM API production experience", "Multi-agent orchestration", "End-to-end shipping"],
  "proof_points_to_emphasize": ["Built AI quality management from scratch", "Real-time AI at scale"],
  "things_to_downplay": ["Academic research background", "Non-e-commerce experience"],
  "tone_guidance": "Direct, technical, business-outcome focused",
  "recruiter_first_impression_target": "Engineer who thinks in business outcomes, not just code",
  "application_stance": "CAREFUL_PUSH",
  "reasoning": "Strong AI engineering match; D2C retail domain is new but transferable"
}
```

**User prompt at runtime:**
```
Company: {json.dumps(state['company_intelligence'])}
Role: {json.dumps(state['role_decode'])}
User: {json.dumps(state['user_truth'])}
```

**Variables injected:** all 3 upstream dicts as JSON dumps  
**Temperature:** 0.2  
**JSON schema:** Example only — `application_stance` enum not specified (STRONG_PUSH/CAREFUL_PUSH/STRETCH/HOLD/SKIP)  

---

### 4.5 `_S7_SYSTEM` — Section Rewrites (graph.py:288-313)

**Role assigned to model:** "a senior technical writer"

```
You are a senior technical writer. Rewrite only the allowed sections in JSON.
CRITICAL:
1. Preserve all links [Text](URL).
2. No 'cope' language or AI-slop.
3. No unsupported claims.
4. Do NOT touch private strategy metadata sections.
Only rewrite sections whose section_id appears in preservation_contract.ordering_rules
and are NOT in preservation_contract.sections_to_exclude.

EXAMPLE JSON OUTPUT:
{
  "rewrites": {
    "experience": {
      "section_id": "experience",
      "original_text": "Built AI at XYZ Corp.",
      "rewritten_text": "Built production AI systems at XYZ Corp.",
      "change_type": "KEEP",
      "change_reason": "Added specificity",
      "claims_added": [],
      "claims_removed": [],
      "evidence_used": ["Python ML pipeline (cv line 15)"],
      "risk_level": "low"
    }
  }
}
```

**User prompt at runtime:**
```
Resume: {json.dumps(state['canonical_resume'])}
Contract: {json.dumps(state['preservation_contract'])}
Strategy: {json.dumps(state['positioning_strategy'])}
User Truth: {json.dumps(state['user_truth'])}
```

**Variables injected:** ALL 4 upstream dicts as raw JSON dumps  
**Temperature:** 0.2  
**Critical issue:** No per-section `allowed_to_edit` flag — LLM must infer from contract JSON  

---

### 4.6 `_COVER_NOTE_SYSTEM` — Cover Note (graph.py:415-418)

**Role assigned to model:** none specified

```
Write a 3-sentence cover note that compels a recruiter to interview. Lead with a concrete achievement from the candidate's strongest proof points — not "I am writing". Be specific. Use only confirmed experience.

EXAMPLE JSON OUTPUT:
{"cover_note": "I built Emote from zero to 450+ users, driving activation from 20% to 75% through continuous product iteration. At Omnex, I built production multi-agent AI that automates manufacturing quality workflows across global supply chains. For Nicobar's AI Product Engineer role, I'd bring the same zero-to-one product ownership to customer personalization and store clienteling."}
```

**User prompt at runtime:**
```
Role: {state['job_title']}
Company: {state['company']}
Positioning Strategy: {json.dumps(state['positioning_strategy'])}
Strongest Proof Points: {json.dumps(top_proofs[:3])}
```

**Temperature:** 0.2  
**Critical issue:** Example is Nicobar-specific hardcoded — model may anchor to this framing  

---

### 4.7 `_RECRUITER_DM_SYSTEM` — LinkedIn DM (graph.py:420-423)

**Role assigned to model:** none specified

```
Write a 2-sentence LinkedIn DM to a recruiter in JSON.
One sentence on the role, one sentence on why the candidate fits. Under 250 chars. No fluff, no "I'm excited to apply".

EXAMPLE JSON OUTPUT:
{"recruiter_message": "Your AI Product Engineer role caught my eye — exactly the kind of AI-native, CEO-office work I thrive on. I shipped production AI from zero at Emote (agentic quality management, multi-agent orchestration) and would bring that same builder mindset to Nicobar."}
```

**Variables injected:** same as cover note  
**Critical issue:** Example is Nicobar-specific and contains "agentic" — a word the humanizer bans  

---

### 4.8 Humanizer Prompts (humanizer_prompts.py)

#### 4.8.1 `SLOP_DETECTOR_SYSTEM` (lines 3-22)

```
You are an expert technical recruiter and resume editor.

Your task is NOT to improve the resume.
Your task is to identify language patterns that make the text sound AI-generated, inflated, generic, corporate, or unbelievable.

Flag:
- corporate buzzwords
- exaggerated claims
- unnatural confidence
- repetitive cadence
- keyword stuffing
- vague impact language
- emotionally empty statements
- GPT-style transitions

Return structured JSON only. Do not rewrite yet.

Output schema:
{"flags": [{"text": "...", "category": "buzzword|exaggeration|vagueness|cadence|filler", "suggestion": "..."}]}
```

#### 4.8.2 `RECRUITER_REALISM_SYSTEM` (lines 24-39)

```
You are a skeptical hiring manager reviewing this resume.

Your task is to identify:
- suspicious claims (too good to be true)
- unbelievable scope (one person couldn't do all this)
- inflated ownership ("led" when they contributed)
- fake metrics (numbers that sound made up)
- unrealistic breadth (too many unrelated skills at expert level)
- likely recruiter skepticism points

Do NOT reject the candidate. Do NOT rewrite. Only identify credibility risks.

Return structured JSON only.
Output schema:
{"concerns": [{"claim": "...", "risk": "high|medium|low", "reason": "...", "suggested_fix": "..."}]}
```

#### 4.8.3 `SURGICAL_HUMANIZE_SYSTEM` (lines 41-62)

```
You are rewriting isolated resume text to sound naturally human, technically credible, concise, and interview-defensible.

Rules:
- preserve meaning
- preserve facts
- preserve metrics
- preserve links [text](url)
- preserve chronology
- preserve tone
- DO NOT add new claims
- DO NOT increase seniority
- DO NOT increase ownership
- DO NOT introduce buzzwords
- DO NOT rewrite entire sections
- DO NOT sound motivational
- DO NOT sound corporate

Rewrite minimally. The text should sound like an experienced professional wrote it naturally.

Input: the text to humanize, plus flags from slop detector.
Output: {"humanized_text": "..."} (the rewritten text, changed ONLY where needed)
```

#### 4.8.4 `TONE_ADAPTER_SYSTEM` (lines 64-83)

```
You are adapting communication style to match a target company type.

You may adjust:
- sentence sharpness
- tone
- verbosity
- confidence calibration

You may NOT:
- alter facts
- add skills
- change chronology
- change ownership

Target tone: {tone}
Company type: {company_type}

Input: humanized text.
Output: {"adapted_text": "..."}
```

**Variables injected:** `tone` (from PositioningStrategy.tone_guidance), `company_type` (from company_intelligence.maturity)

---

### 4.9 India Fit Engine System Prompt (india_fit_llm.py:69-103)

```
You are an India-specific career fit evaluator. Analyze the job posting against the user profile and return ONLY the JSON object below. No markdown. No explanation.

Return exactly this JSON structure:
{
  "overall_score": 0,
  "recommendation": "APPLY",
  "reason": "why this is a good fit in 1 sentence",
  "risks": ["risk 1", "risk 2"],
  "why_user_might_like_it": "what makes this attractive to this specific user",
  "why_user_might_hate_it": "what might make this user reject this job",
  "missing_info": ["info not available that would help scoring"],
  "confidence": 0.0,
  "dimensions": {
    "role_fit": 0,
    "skill_fit": 0,
    "location_fit": 0,
    "salary_fit": 5,
    "work_mode_fit": 5,
    "company_stability": 5,
    "brand_value": 5,
    "career_trajectory": 5,
    "response_likelihood": 5
  }
}

RULES:
- overall_score: 0-100 (weighted average of dimensions)
- recommendation: "APPLY" (>=70), "MAYBE" (50-69), or "SKIP" (<50)
- dimensions: each 0-10
- If user rejected_roles includes this role type → SKIP, score < 40
- If user rejected_company_types matches → SKIP, score < 40
- If location is not India and user is in India → lower location_fit
- If salary unknown → salary_fit = 5
- confidence: 0-1 (how confident are you in this score given available info)
- Be honest: low info = low confidence
```

---

### 4.10 batch-prompt.md (lines 1-395) — Key Excerpts

**Language:** Spanish (entire prompt is in Spanish)  
**Role assigned:** "worker de evaluación de ofertas"  
**Self-described:** "Este prompt es self-contained. Tienes TODO lo necesario aquí."

This is the largest single prompt in the system. Key injected variables:
- `{{URL}}` — job URL
- `{{JD_FILE}}` — local JD file path
- `{{REPORT_NUM}}` — 3-digit zero-padded report number
- `{{DATE}}` — YYYY-MM-DD
- `{{ID}}` — batch job ID

The prompt orchestrates: JD acquisition → 6-block evaluation → markdown report → PDF generation → TSV tracker line → JSON stdout summary.

**Design instruction (PDF section):**
- Space Grotesk headings, DM Sans body
- Header gradient: `hsl(187,74%,32%) → hsl(270,70%,45%)`
- Section headers cyan, company names purple

---

## 5. Prompt Behavior Analysis

| # | Prompt | Model Role | Behavior Bias | Too Broad? | Hard Output Constraints? | Preserves Truth? | Generic Language Risk | Private Leak Risk |
|---|--------|-----------|----------------|------------|--------------------------|------------------|-----------------------|-------------------|
| 1 | _S3 Company Intel | researcher | Summary writer + hallucinator | Yes (research + synthesis combined) | No (example only) | No — pure recall | HIGH | Low |
| 2 | _S4 Role Decoder | decoder | JD parser | No — focused | Yes — explicit schema in prompt | Medium — inherits S3 | LOW | Low |
| 3 | _S5 User Truth | auditor | Evidence mapper + claim gatekeeper | Yes (mapping + gating + private constraints) | No | HIGH risk — can fabricate confirmed skills | MEDIUM | **HIGH** — private_constraints in output |
| 4 | _S6 Positioning | strategist | Narrative creator | No | No | Medium | LOW | Low |
| 5 | _S7 Section Rewrites | technical writer | Resume rewriter | **YES — all sections at once** | Partial (8 negative rules, no schema) | LOW risk per-section | **HIGH** — defaults to formal resume mode | Medium (private sections may be touched) |
| 6 | _COVER_NOTE | none | Cover writer | No | `{"cover_note": "..."}` only | Low — grounded in proof points | MEDIUM | Low |
| 7 | _RECRUITER_DM | none | DM writer | No | `{"recruiter_message": "..."}` only | Low — uses same proof points | HIGH — 250 char limit causes compression clichés | Low |
| 8 | SLOP_DETECTOR | recruiter+editor | Pattern detector | No — single purpose | `{"flags": [...]}` | N/A (detection only) | N/A | N/A |
| 9 | RECRUITER_REALISM | hiring manager | Credibility auditor | No — single purpose | `{"concerns": [...]}` | N/A | N/A | N/A |
| 10 | SURGICAL_HUMANIZE | humanizer | Minimal rewriter | No | `{"humanized_text": "..."}` | YES — 6 preserve rules | LOW | Low |
| 11 | TONE_ADAPTER | style adapter | Tone matcher | No | `{"adapted_text": "..."}` | YES — explicit can't rules | LOW | Low |
| 12 | India Fit Engine | fit evaluator | Scorer | No — very focused | Full JSON schema enforced | HIGH — dimensions have defaults that hide bad data | LOW | Low |
| 13 | Archetype detect (inline) | agent | Classifier | No | Label output | N/A | N/A | N/A |
| 14 | Eval A–G (modes/_shared) | evaluator | Full pipeline orchestrator | **YES — evaluates + advises + generates** | Markdown blocks A-G | Medium | MEDIUM | Low |
| 15 | PDF generation (modes/pdf) | generator | PDF builder | No — focused | HTML with placeholders | YES — NUNCA inventa | LOW | Low |
| 16 | Showcase builder | designer | Portfolio builder | **YES — narrative + design + HTML combined** | HTML file | YES — NEVER invent metrics | HIGH — fills gaps with superlatives | Low |

**Key behavioral patterns detected:**

**Pattern 1: Negative-constraint overload**  
`_S7_SYSTEM` has 8 "do not" rules and 0 "do" rules beyond the JSON schema. The model's positive behavior is entirely undefined. When unconstrained positively, it defaults to what resume text sounds like in training data: formal, corporate, passive-voice.

**Pattern 2: Role-identity mismatch**  
"Senior technical writer" (S7) is a different frame than "builder who thinks in outcomes" (the persona the positioning strategy wants). The S7 role pushes toward editing-for-clarity; the desired output is editing-for-impact.

**Pattern 3: Example anchoring**  
Every prompt with a JSON example uses Nicobar-specific data (a real company). The model may anchor to this specific example and produce Nicobar-flavored output for unrelated companies.

**Pattern 4: Too-broad user prompts**  
Systems 5, 6, and 7 dump their full upstream artifacts as `json.dumps()` blobs in the user message. A 4,000-token canonical resume + 600-token role decode + 400-token user truth = 5,000+ token user message before any instruction. The model's attention diffuses.

**Pattern 5: Spanish/English mismatch**  
`batch-prompt.md` is Spanish. All Council Python prompts are English. The India fit prompt is English. The user may be in any language context. There is no flag or router to ensure the model responds in the right language.

---

## 6. Prompt Conflict Matrix

| # | Conflict | Prompt A | Prompt B | Impact | Severity |
|---|---------|---------|---------|--------|---------|
| 1 | Output format mismatch | `_S7_SYSTEM` expects `{"rewrites": {"section_id": {...}}}` | `assembly_node` calls `rewrites_data.get("rewrites", {})` expecting a flat dict of section_id → SectionRewrite | If S7 nests differently, rewrites silently dropped | **HIGH** |
| 2 | Language mismatch — batch prompt is Spanish | `batch-prompt.md` written in Spanish | All Council prompts + `modes/_shared.md` written in English | If user is running English CLI, batch worker may produce Spanish reports | **HIGH** |
| 3 | "be concise" vs "include full detail" | `_S7_SYSTEM`: "No AI-slop" (implies conciseness) | `batch-prompt.md Block B`: full requirement-by-requirement match table with gaps and mitigation plans | Two very different resume-related outputs have opposite density targets | MEDIUM |
| 4 | "professional" vs "founder-like" | `_S7_SYSTEM` role = "senior technical writer" (professional) | `_S6_SYSTEM` often produces `tone_guidance: "Direct, founder-like"` | S7 doesn't read S6's tone_guidance — produces corporate text, S6 says founder voice | **HIGH** |
| 5 | "humanize" vs validator expects schema | `SURGICAL_HUMANIZE_SYSTEM` outputs `{"humanized_text": "..."}` | `assembly_node` uses the string directly (correct) BUT if humanizer runs before truth guard... wait, it runs AFTER (correct sequence). This is OK. | No conflict in current flow | LOW |
| 6 | PDF generates from cv.md, not Council output | `modes/pdf.md`: "Lee cv.md" | Council (Pipeline A) generates `10_final_resume.md` | User gets Council-tailored resume in Markdown but PDF reflects base cv.md — different content | **CRITICAL** |
| 7 | "no cope language" appears in two places but different scopes | `_S7_SYSTEM`: "No cope language" (applies to resume bullets) | `humanizer_rules.py` BANNED_WORDS: "passionate", "leverage", etc. | Both aim to remove AI slop but S7 says it and then passes to humanizer who also checks — double redundancy | LOW (redundancy, not conflict) |
| 8 | Temperature inconsistency | All Council nodes use `T=0.2` (strategy) | India fit engine uses `T=0.3` | Different tasks, similar temperature. Cover note (creative) uses same T as deterministic parsing. | MEDIUM |
| 9 | `_S5_SYSTEM` exposes private_constraints in output | `_S5_SYSTEM` example shows `"private_constraints": ["min salary 25L", ...]` | `_S7_SYSTEM` receives `user_truth` as input (including private_constraints) | S7 LLM can see salary expectations and may leak them into rewrites | **HIGH** |
| 10 | "agentic" is banned by humanizer, used in recruiter DM example | `_RECRUITER_DM_SYSTEM` example: "agentic quality management, multi-agent orchestration" | `humanizer_rules.py` BANNED_WORDS includes "agentic", "multi-agent" | Humanizer will flag and rewrite what the DM prompt was explicitly told to generate | MEDIUM |
| 11 | _S4 schema requires `confidence: 0.85` (float) but _S5 does not | `_S4_SYSTEM`: confidence in schema | `_S5_SYSTEM`: no confidence field | Downstream code that aggregates confidence cannot work uniformly | LOW |
| 12 | Cover note example anchors to Nicobar | `_COVER_NOTE_SYSTEM` example: "For Nicobar's AI Product Engineer role..." | Runtime user prompt: different company | LLM may produce Nicobar-flavored output for unrelated companies via example anchoring | MEDIUM |
| 13 | WritingStyle calibration is advisory only but _S7 doesn't read it | `modes/_shared.md` Writing Style section cached in `_profile.md` | `_S7_SYSTEM` in graph.py has no access to `_profile.md` (Pipeline A has no file read) | Pipeline A ignores user voice calibration; Pipeline B uses it | **HIGH** |

---

## 7. Output Contract Audit

### System 1: parse_node → `canonical_resume`

| Item | Expected | Actual | Schema enforced? | Drift? |
|------|---------|--------|-----------------|--------|
| Type | `CanonicalResume` dataclass | dict via `to_dict()` | Yes — `safe_construct()` in assembly | No |
| Sections | `List[ResumeSection]` | list of dicts | Yes — reconstructed in assembly | No |
| normalized_type | "experience", "education", "skills", "summary" | **"unknown"** for most sections (FUCKUP #1) | No enforcement | **YES — section type is wrong** |
| visibility | PUBLIC/PRIVATE/UNKNOWN | UNKNOWN for ambiguous sections | No downstream validation | YES — leakage surface |

### System 2: contract_node → `preservation_contract`

| Item | Expected | Actual | Schema enforced? | Drift? |
|------|---------|--------|-----------------|--------|
| sections_to_exclude | list of section_ids for PRIVATE sections | Derived from visibility=PRIVATE | Yes — rule-based | No |
| ordering_rules | ordered list of section_ids | Present | Passed to S7 as JSON, not enforced | **YES — S7 LLM ignores ordering** |
| max_allowed_changes | int limit | Present in dataclass | NOT enforced in assembly | **YES — assembly doesn't check** |
| links_to_preserve | dict of link text → URL | Present | Verified after assembly in link_audit | Partial |

### System 3: company_intelligence_node → `company_intelligence`

| Item | Expected | Actual | Schema enforced? | Drift? |
|------|---------|--------|-----------------|--------|
| confidence | 0.0–1.0 float | Present in example | Not validated | Possible |
| funding/employees | UNKNOWN if not in JD | Often hallucinated | Only instructed, not validated | **YES — hallucination** |
| maturity | "seed/startup/growth/late/enterprise" | Free string from LLM | Not validated | YES |
| missing_data | list of unknown fields | Present | Not used downstream | YES — not consumed |

### System 5: user_truth_node → `user_truth`

| Item | Expected | Actual | Schema enforced? | Drift? |
|------|---------|--------|-----------------|--------|
| confirmed_skills | List of {skill, years, evidence} | Varies — sometimes strings, sometimes dicts | No schema in prompt | **YES — format inconsistency** |
| claims_not_allowed | List of exact strings | LLM generates paraphrases | Not validated | **YES — truth guard can't match** |
| private_constraints | Internal only | **In the example output — may appear in final JSON** | Not stripped before S7 sees it | **CRITICAL LEAK SURFACE** |
| evidence_bank | dict of skill → list of evidence strings | Varies — sometimes just descriptions | No schema | YES |

### System 7: section_rewrites → `section_rewrites`

| Item | Expected | Actual | Schema enforced? | Drift? |
|------|---------|--------|-----------------|--------|
| rewrites key | `{"rewrites": {section_id: SectionRewrite}}` | Varies — sometimes `{"experience": {...}}` without wrapping key | No schema enforcement | **YES — frequent** |
| change_type | "KEEP"/"MINOR"/"MAJOR"/"NEW" | Varies | No validation | YES |
| rewritten_text | str | Sometimes a list of bullets | No validation | YES |

### System 8: assembly_node → `application_pack`

| Item | Expected | Actual | Schema enforced? | Missing? |
|------|---------|--------|-----------------|---------|
| resume_markdown | humanized markdown str | Present | Yes | No |
| cover_note | 3-sentence humanized str | Present — sometimes generic | Yes | No |
| recruiter_message | 2-sentence humanized str | Present — often generic | Yes | No |
| positioning_summary | Summary of S6 output | **NOT IN OUTPUT** | N/A | **YES — missing** |
| preserved_links | List of confirmed links | Present (added recently) | Yes | No |
| blocked_claims | List of TruthGuard-blocked claims | **NOT IN OUTPUT** | N/A | **YES — missing** |
| user_review_summary | User-facing summary | Hardcoded string | No | Partial |
| link_audit | LinkAudit object | Present | Yes | No |

---

## 8. Humanizer Audit

### When does humanizer run?

The humanizer runs **once**, at the end of `assembly_node` (graph.py:522-536), after:
- Deterministic assembly has produced `final_resume` markdown
- Cover note and recruiter DM have been LLM-generated

It runs **three separate times** (once per artifact):
1. `humanizer.humanize(final_resume, mode="resume", context={company_type})`
2. `humanizer.humanize(cover_note, mode="cover_note", context={company_type})`
3. `humanizer.humanize(recruiter_message, mode="recruiter_message", context={company_type})`

### What input does it receive?

- **Resume:** assembled markdown string (post-TruthGuard)
- **Cover note:** LLM-generated string (2-sentence cover note from `_COVER_NOTE_SYSTEM`)
- **DM:** LLM-generated string (from `_RECRUITER_DM_SYSTEM`)
- **Context:** `{"company_type": company_intelligence.get("maturity", "default")}`

### What output does it produce?

`HumanizerResult` with:
- `humanized_text` — the final string sent downstream
- `flags` — detected slop flags (logged, not surfaced to user)
- `changes_made` — int count
- `recruiter_concerns` — list of credibility concerns (logged, not surfaced)

### Does its output get overwritten later?

**No.** The humanized text goes directly into `ApplicationPack.resume_markdown` and that's the final output.

### Does it sanitize or rewrite?

Both:
- Phase 1 (deterministic): Scans for banned words from `humanizer_rules.py:BANNED_WORDS` and flags them
- Phase 2 (deterministic): Structural checks (all bullets starting with "I", exclamation marks, etc.)
- Phase 3 (LLM): `SURGICAL_HUMANIZE_SYSTEM` minimally rewrites flagged text
- Phase 4 (LLM): `TONE_ADAPTER_SYSTEM` adjusts for company type
- Phase 5 (deterministic): Smart-quote normalization, whitespace cleanup

### Does it remove jargon?

Partially. `BANNED_WORDS` in `humanizer_rules.py` includes:
`["passionate", "leverage", "spearheaded", "synergize", "robust", "seamless", "cutting-edge", "innovative", "best-in-class", "thought leader", "results-driven"]` and more.

**Not in the list but problematic:** "transformative," "strategic," "exceptional," "streamlined," "world-class," "dynamic."

### Does it preserve truth?

Yes — `SURGICAL_HUMANIZE_SYSTEM` has 6 explicit preserve rules (meaning, facts, metrics, links, chronology, tone) and 3 explicit increase prohibitions (seniority, ownership, claims).

### Is it used for resume, portfolio, or both?

**Only resume and its derived artifacts** (cover note, recruiter DM). The showcase-builder and PDF-from-modes pipelines do NOT use the Python Humanizer. They rely on the model following `modes/_shared.md` writing style rules.

### Does it run before or after validator?

**After TruthGuard (7.5) and after assembly (8).** Sequence:
```
section_rewrites (S7) 
→ truth_guard (S7.5) repairs claims 
→ assembly (S8) assembles markdown 
→ humanizer runs on assembled markdown 
```

**Issue:** Humanizer could re-introduce problems that TruthGuard already removed, or it could flag TruthGuard's repaired text as "unnatural" and re-rewrite it — potentially restoring the original problematic phrasing.

### Documented failures

- **FUCKUP #3:** `_adapt_tone()` used `" ".join()` which destroyed all `\n\n` paragraph separators. **Fixed:** paragraph-aware processing.
- **FUCKUP #4:** Sanitizer used `\s{2,}` regex which collapsed all newlines. **Fixed:** Changed to `[^\S\n]{2,}`.
- **Post-humanizer verification:** `assembly_node` runs a spot-check for surviving slop terms (`agentic`, `leverage`, etc.) after humanizer runs. Words with >2 occurrences or `agentic` trigger manual review flags (line 563-565).

---

## 9. Design / Portfolio Builder Audit

### Showcase Builder (`.claude/skills/showcase-builder/SKILL.md`)

**Does it think it is building a resume?**  
No. The skill explicitly frames itself as "premium editorial HTML showcase pages" distinct from resume. It has its own template (`templates/showcase-template.html`), component library, and design system.

**Does it think it is writing a story?**  
Partially. It asks for "Key lessons," "Acquisition/growth story," "Working principles" — these are narrative frames. But it provides NO guidance on how to sequence these for a specific audience or company archetype. The model fills the narrative gap.

**Does it understand audience/company?**  
Minimally. The skill maps company type to color variant (5 variants: Warm Earth/D2C, Deep Ocean/Enterprise, Forest/Health, Merlot/Creative, Slate/Consulting). This is the only audience signal. There is no guidance on tone, vocabulary, or story frame per company archetype.

**Does it select visual style from company archetype?**  
Yes — color variant selection is the strongest design-aware element in the skill. The mapping is specific and defensible.

**Does it output structured sections or raw HTML?**  
Raw HTML directly from the template. There is no intermediate structured representation. The model fills template slots in a single generation pass.

**Does it include design QA?**  
No. The skill says "ALWAYS validate PDF exports" but provides no validation criteria. There is no instruction to check: link integrity, metric accuracy, dark mode (correctly prohibited), typography scale, responsive breakpoints, or print CSS.

**Does it support feedback loops?**  
No. Single generation. No staging, no user approval step, no comparison view.

**Specific issues found:**

1. **No content strategy guidance** — the skill collects inputs (metrics, lessons, principles) but gives the model no frame for selecting WHICH metrics matter for the specific audience. A Nicobar hiring manager cares about different signals than a SaaS founder office.

2. **"NEVER invent metrics"** — correct rule, but no instruction on what to do when the user provides too few or too many metrics. The model will either pad or truncate arbitrarily.

3. **No negative examples** — the skill says what not to do ("not demos," "not POCs") in one rule but has no examples of bad showcase copy vs. good showcase copy.

4. **The `frontend-design` skill reference is broken** — `SKILL.md` line 36 says "use frontend-design skill" but there is no `frontend-design` skill in `.claude/skills/`. This is a dead dependency.

5. **Dark mode rule is absolute** — "NEVER use dark mode for application pages." This is correct for recruiter-facing docs, but the existing output directory contains `dark.html` variants (e.g., `output/council/siddharth/nicobar-final/nicobar-compact-dark.html`), indicating the rule is not consistently enforced.

---

## 10. Company Intelligence Prompt Audit

### Current Implementation (System 3, `_S3_SYSTEM`)

**What sources does it ask for?**  
None. It receives `company name + JD[:3000]` and asks the LLM to extract signals. There is no instruction to use any external source. The model uses its training data.

**Does it do deep research or shallow summary?**  
Shallow summary — pure LLM recall. The prompt asks the LLM to "distinguish JD-extracted facts from recalled knowledge" and mark recalled facts as LOW confidence. In practice, the model often outputs recalled facts at normal confidence.

**Does it create a company graph?**  
No.

**Does it separate facts from inferences?**  
It attempts to — the `signals_from_jd` field is intended to separate JD-extracted signals. But the `summary` field mixes both without attribution.

**Does it cite/provenance sources?**  
No. The prompt says "Mark source clearly" but the output schema has no source field. The model writes facts without provenance.

**Does it feed role positioning downstream?**  
Yes — `positioning_implications` and `interview_implications` fields go into the S6 positioning prompt. If these are hallucinated, S6 builds strategy on wrong intelligence.

**Does it influence resume/design outputs or just produce a report?**  
It influences resume via S6 (tone_guidance), and it influences humanizer via `company_type` (maturity field maps to tone profile). A hallucinated `maturity: "enterprise"` will push the humanizer to enterprise tone even for a 10-person startup.

**The design spec for the real Company Intelligence system** (`careerloop/docs/specs/company-intel-design.md`) exists and is detailed — it specifies: cache-first, web search, LLM synthesis, source attribution, TTL-based caching. **This system has not been built.** The current node is a placeholder.

---

## 11. Failure Mode Analysis

### 1. Raw markdown leaking

**Root cause:** `render_all_templates.py` mapped sections by `section.normalized_type == "experience"` but the Council Compiler classifies role sections as `normalized_type="unknown"`. All content was silently dropped and the template kept its placeholder `{{EXPERIENCE}}` text.  
**File:** `careerloop/rendering/render_all_templates.py` (FUCKUP #1)  
**Fix applied:** Switched to `normalizer.py` (NormalizedResume) approach.

### 2. Generic resume language

**Root cause (primary):** `_S7_SYSTEM` assigns "senior technical writer" role with 8 negative constraints and no affirmative voice instructions. Model defaults to formal resume prose.  
*(FIXED 2026-05-20: S7 Prompt overhauled to be affirmatively prescriptive. "Senior technical writer" replaced with "precise editor". Humanizer prompt rewritten to be highly aggressive and outcome-focused.)*
**Root cause (secondary):** Pipeline A's `10_final_resume.md` is not used by Pipeline B's PDF generator — the PDF re-reads `cv.md`, so the Council's tailoring is lost.  
**Root cause (tertiary):** Writing style from `modes/_shared.md` is calibrated for Pipeline B only — Pipeline A never reads `_profile.md`.

### 3. Weak design output

**Root cause:** Showcase-builder has color variant logic but no narrative content strategy. The model fills content gaps with generic superlatives. No negative examples or quality bar defined.  
**Root cause (secondary):** `frontend-design` skill referenced but does not exist.

### 4. Overhyped portfolio copy

**Root cause:** The skill DOES say "NEVER use 'not demos,' 'not POCs'" — but this is one negative rule. There is no positive instruction for calibrated, interview-defensible language. The model reaches for impressive language to fill the narrative gap.

### 5. Dark mode pipeline failure

**Root cause:** Multiple dark-mode outputs exist in `output/` despite the showcase-builder SKILL.md saying "NEVER use dark mode for application pages." The rule is in SKILL.md but not enforced programmatically. Earlier sessions generated dark variants before the rule was written.

### 6. Wrong metrics rendering

**Root cause (FUCKUP #1):** `render_all_templates.py` path confusion — user looked at stale folder, Claude reported from new folder.  
**Root cause (secondary):** NormalizedResume normalizer may produce `NaN` for metrics when the resume markdown has a metric format it doesn't recognize (e.g., "3.2x" vs "320%").

### 7. NaNWednesday

Not traceable to a specific prompt — likely a date formatting issue where `get_runtime_context()` produced an unexpected format that was injected into a template as-is. The `runtime_context.py` returns `current_month` as a human-readable string (e.g., "May 2026") which if used in date arithmetic could produce NaN.

### 8. Sections like "Target Roles / Deal-breakers" leaking

**Root cause:** `_classify_section()` in `compiler.py` uses a keyword list for PRIVATE classification. "Target Roles" appears in the keyword list; "Deal-breakers" does not. Sections with unusual headers leak through as UNKNOWN and can be passed to S7 for rewriting.  
**Root cause (secondary):** The `_S5_SYSTEM` example shows `private_constraints` in the User Truth output dict. If S7 receives this in `user_truth`, salary and location constraints can appear in the LLM's context and be inadvertently included in rewrites.

### 9. Resume not role-tailored enough

**Root cause (primary):** S7 receives the FULL canonical_resume JSON and must infer which sections to edit from the PreservationContract. The LLM frequently edits too many sections (over-tailoring) or too few (under-tailoring) because the per-section `allowed_to_edit` flag doesn't exist.  
**Root cause (secondary):** The positioning strategy (S6) includes `tone_guidance` but S7 does not explicitly consume it — it receives strategy as a blob and may ignore tone_guidance.  
**Root cause (tertiary):** Pipeline A tailoring is lost in Pipeline B's PDF generation (see conflict #6).

---

## 12. Control Surface Map

| Control Surface | Location in Code | How to Adjust | Risk |
|----------------|-----------------|----------------|------|
| **System prompt text** | `graph.py:118-138, 170-185, 211-226, 251-266, 288-313, 415-418, 420-423` | Edit string constants | Medium — test each node output |
| **Humanizer prompts** | `humanizer_prompts.py:3-83` | Edit 4 string constants | Low — localized, well-tested |
| **Banned words/phrases** | `humanizer_rules.py:BANNED_WORDS, BANNED_PHRASES` | Add/remove words from lists | Low — deterministic |
| **Tone profiles** | `humanizer_rules.py:TONE_PROFILES` | Add/edit dict keys | Low |
| **JSON schema enforcement** | Currently: example only in prompts | Add explicit schema + validation after each LLM call | HIGH — adds latency, can break parsing |
| **Model choice (strategy vs writer)** | `llm.py:load_council_model_config()` + `config/models.yml` | Edit models.yml or env CAREERLOOP_FIT_MODEL | Medium |
| **Temperature per node** | `graph.py:58-70` `_call()` default T=0.2 | Pass per-node temperature | Low — adjust per node |
| **Private section keywords** | `compiler.py:_classify_section()` | Extend keyword lists | Low |
| **Archetype framing rules** | `modes/_profile.md` (user layer) | Edit _profile.md | Low — user-controlled |
| **Archetype definitions (system)** | `modes/_shared.md:74-87` + `batch-prompt.md:70-104` | Edit modes files | Medium — affects all users |
| **Writing style calibration** | `modes/_shared.md:138-212` → writes to `_profile.md` | Automatic via scan of writing-samples/ | Low |
| **Truth Guard rules** | `truth_guard.py` (762 lines, compiled regex) | Extend regex patterns or Jaccard threshold | Medium — needs test coverage |
| **Pipeline A→B connector** | Does not exist | Create: make assembly output feed pdf.md template | HIGH — new plumbing |
| **Humanizer runs** | `assembly_node:522-536` | Adjust mode, context, or skip | Low per-run |
| **Stage ordering** | `graph.py:628-648` LangGraph edges | Change edge definitions | HIGH — architectural |
| **Per-section editing spec** | `_S7_SYSTEM` prompt | Add `allowed_to_edit` flag per section | Medium |
| **Showcase color variants** | `showcase-builder/SKILL.md:85-170` | Add/edit color variant blocks | Low |
| **Feedback loop** | Does not exist (showcase) | Add staging → user approval → commit pattern | HIGH — new architecture |

---

## 13. Recommendations (No Implementation Yet)

### P0: Must Fix

**P0-1: Reconnect Pipeline A and Pipeline B**  
The Council's `10_final_resume.md` must be used as the input to PDF generation in `modes/pdf.md`. Currently the PDF re-reads `cv.md`, losing all Council tailoring. Either: (a) have `modes/pdf.md` check for a Council output for the current job before reading cv.md, or (b) run the Council explicitly before every PDF and pass its output.

**P0-2: Add JSON schema to every LLM prompt**  
S3 (Company Intel), S5 (User Truth), S6 (Positioning) all lack schemas in their prompts. Add explicit JSON schema definitions — not as "examples" but as mandatory output contract. Consider moving to DeepSeek tool calling per the existing `deepseek-tool-calling-audit.md` spec.

**P0-3: Strip `private_constraints` from S7 input**  
Before passing `user_truth` to `section_rewrites_node`, remove the `private_constraints` key from the dict. Salary and location data should never reach a LLM that is rewriting public resume text.

**P0-4: Build real Company Intelligence**  
The `company-intel-design.md` spec is written. Implement it. Until then, mark all S3 outputs as `confidence: 0.2` and surface this to the user so they know the intelligence is placeholder-quality.

**P0-5: Translate batch-prompt.md to English or add language routing**  
The batch worker prompt is Spanish. This will cause Spanish-language reports for English-speaking users unless the CLI model happens to detect and override the language. Either translate to English and add an i18n mechanism, or add a `{{LANG}}` placeholder that the orchestrator fills.

### P1: Should Fix

**P1-1: Add `allowed_to_edit` flag to S7 per section**  
Instead of passing the full contract JSON and asking the LLM to interpret it, pass each section with `{"section_id": "...", "text": "...", "allowed_to_edit": true/false, "strategy_hints": [...]}`. This removes ambiguity and reduces hallucinated edits.

**P1-2: Upgrade TruthGuard to fuzzy matching**  
Current exact-string matching misses paraphrased claims. At minimum: normalize both claim and text, extract numeric claims with regex, add Jaccard similarity for non-numeric claims. The existing spec in CAREERLOOP_COUNCIL_AUDIT.md is correct.

**P1-3: Replace "senior technical writer" role in S7 with correct frame**  
The role should be "a precise editor who sharpens specificity for recruiting impact" — not a writer. Add 3-5 positive instructions: prefer active voice, lead bullets with outcomes, use concrete nouns over abstract descriptions.

**P1-4: Replace hardcoded `user_review_summary` string**  
`"Check your new resume. 8-system architecture ensured zero metadata leakage."` is a marketing claim and a placeholder. Generate a 2-3 bullet summary of actual changes made, claims blocked by TruthGuard, and sections that needed significant edits.

**P1-5: Add content strategy instructions to showcase-builder**  
Add a "What to emphasize for this company type" section per color variant (5 variants = 5 strategy frames). The color variant already knows the company archetype — use it to guide content selection, not just color.

**P1-6: Fix the `frontend-design` skill dead reference**  
Line 36 of showcase-builder SKILL.md says "use frontend-design skill." This skill doesn't exist. Either remove the reference or implement the skill.

**P1-7: Surface TruthGuard output in `application_pack`**  
Add `blocked_claims` to `ApplicationPack` — the list of claims TruthGuard caught and repaired. Users need to see this before submitting.

### P2: Later Improvements

**P2-1: Remove Nicobar-specific examples from system prompts**  
Replace concrete company examples in `_COVER_NOTE_SYSTEM` and `_RECRUITER_DM_SYSTEM` with generic placeholder examples. Nicobar anchoring is causing all cover notes to trend toward D2C/retail framing.

**P2-2: Add explicit tone_guidance consumption to S7**  
Extract `positioning_strategy.tone_guidance` before the S7 call and add it as an explicit instruction: `"Tone target for this rewrite: {tone_guidance}"`. Currently this field is buried in the strategy JSON blob.

**P2-3: Add post-humanizer quality assertion**  
Beyond the spot-check for surviving slop terms, add a schema validation step: verify the humanized resume still has all required sections (Experience, Education, Skills at minimum), all links preserved, and reasonable length (not truncated by humanizer newline destruction — FUCKUP #3/#4 are fixed but worth guarding).

**P2-4: Write style calibration into Pipeline A**  
The writing style extracted by `modes/_shared.md` into `_profile.md` should be injected into S7's prompt. This closes the gap where Pipeline A ignores the user's voice calibration.

**P2-5: Add showcase content quality bar**  
Define 3-5 negative examples of overhyped showcase copy ("I built the entire AI platform from zero, revolutionizing the industry") and 3-5 positive examples of calibrated copy ("Shipped X from concept to 450 users in 4 months: specific outcome, specific constraint, specific proof"). Add these to the SKILL.md.

**P2-6: Add per-node validation after each LLM call**  
After each `_call()` in graph.py, validate that required keys are present before proceeding. Current code passes LLM output directly to `state.setdefault()` — a node with missing keys silently propagates None downstream.

---

*End of audit. Implementation is blocked on this document being reviewed and priorities set.*  
*Next action: use this document to write the P0 and P1 fix specs before touching any prompt text.*
