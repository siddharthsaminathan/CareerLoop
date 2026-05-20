# CareerLoop — Pipeline Dependency Graph

**Generated:** 2026-05-19  
**Source of truth:** `careerloop/council/graph.py`, `careerloop/rendering/`, `batch/batch-prompt.md`, `modes/`

---

## Pipeline A — Resume Council (LangGraph StateGraph)

```
cv.md ──────────────────────────────────────────────────────┐
jd_text (from ledger) ──────────────────────────────────────┤
company, job_title, job_url (from ledger) ──────────────────┤
profile dict (profile_manager.py) ─────────────────────────┤
today (runtime_context.py) ────────────────────────────────┤
                                                            │
                                                            ▼
                                              ┌─────────────────────┐
                                              │  orchestrator.py    │
                                              │  ResumeCouncil-     │
                                              │  Orchestrator.run() │
                                              └──────┬──────────────┘
                                                     │
                                                     │ graph.py → get_council_graph()
                                                     │ LangGraph StateGraph.invoke()
                                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          CouncilState (TypedDict)                            │
│  job_id, person_id, job_title, company, job_url, jd_text, master_cv,        │
│  profile, today, canonical_resume, preservation_contract,                   │
│  company_intelligence, role_decode, user_truth, positioning_strategy,        │
│  section_rewrites, application_pack, errors                                 │
└──────────────────────────────────────────────────────────────────────────────┘

NODE EXECUTION ORDER (linear):

master_cv (str)
    │
    ▼ [graph.py:80-92]
┌─────────────────────┐    Reads:   compiler.py → ResumeCompiler.parse_markdown()
│  parse_node (S1)    │    Writes:  canonical_resume (dict)
│  DETERMINISTIC      │    Saves:   01_canonical_resume.json
└────────┬────────────┘
         │
         ▼ [graph.py:97-113]
┌─────────────────────┐    Reads:   canonical_resume + profile
│  contract_node (S2) │    Calls:   compiler.py → ResumeCompiler.build_contract()
│  DETERMINISTIC      │    Writes:  preservation_contract (dict)
└────────┬────────────┘    Saves:   02_preservation_contract.json
         ▼ [graph.py:116-165]
┌─────────────────────┐    Reads:   company (str), jd_text[:3000]
│  company_intel (S3) │    Calls:   _call(_S3_SYNTHESIS_SYSTEM, prompt)
│  LLM: DeepSeek T=.2 │    Writes:  company_intelligence (dict)
└────────┬────────────┘    Saves:   03_company_intelligence.json
         │                ✅ GROUNDED Research | ✅ Search Relaxation | ✅ Cache-Busting
         ▼ [graph.py:168-206]
┌─────────────────────┐    Reads:   jd_text + company_intelligence
│  role_decode (S4)   │    Calls:   _call(_S4_SYSTEM, prompt) → DeepSeek "strategy"
│  LLM: DeepSeek T=.2 │    Writes:  role_decode (dict)
└────────┬────────────┘    Saves:   04_role_decode.json
         │                ✅ Has JSON schema in prompt
         ▼ [graph.py:209-246]
┌─────────────────────┐    Reads:   canonical_resume + role_decode
│  user_truth (S5)    │    Calls:   _call(_S5_SYSTEM, prompt) → DeepSeek "strategy"
│  LLM: DeepSeek T=.2 │    Writes:  user_truth (dict)
└────────┬────────────┘    Saves:   05_user_truth.json
         │                ⚠️ No JSON schema | ⚠️ private_constraints in output
         ▼ [graph.py:249-283]
┌─────────────────────┐    Reads:   company_intelligence + role_decode + user_truth
│  positioning (S6)   │    Calls:   _call(_S6_SYSTEM, prompt) → DeepSeek "strategy"
│  LLM: DeepSeek T=.2 │    Writes:  positioning_strategy (dict)
└────────┬────────────┘    Saves:   06_positioning_strategy.json
         │                ⚠️ No JSON schema
         ▼ [graph.py:286-336]
┌─────────────────────┐    Reads:   canonical_resume + preservation_contract
│  section_rewrites(S7)│            + positioning_strategy + user_truth
│  LLM: DeepSeek T=.2 │    Calls:   _call(_S7_SYSTEM, prompt) → DeepSeek "strategy"
└────────┬────────────┘    Writes:  section_rewrites (dict)
         │                Saves:   07_section_rewrites.json
         │                ⚠️ Passes all 4 dicts as raw json.dumps() blobs
         ▼ [graph.py:339-410]
┌─────────────────────┐    Reads:   section_rewrites + user_truth
│  truth_guard (S7.5) │    Calls:   TruthGuard.validate() + repair()
│  DETERMINISTIC      │    Writes:  section_rewrites (repaired), truth_guard_report
└────────┬────────────┘    ⚠️ Exact-string match only (no fuzzy)
         │
         ▼ [graph.py:427-620]
┌─────────────────────────────────────────────────────────────────┐
│  assembly_node (S8) — HYBRID                                    │
│                                                                 │
│  1. ResumeCompiler.assemble()          DETERMINISTIC            │
│     Reads: canonical_resume + section_rewrites + contract       │
│     Writes: final_resume (markdown str)                         │
│                                                                 │
│  2. _call(_COVER_NOTE_SYSTEM, ...)     LLM: DeepSeek "writer"  │
│     Reads: job_title + company + positioning + top_proofs       │
│     Writes: cover_note (str)                                    │
│                                                                 │
│  3. _call(_RECRUITER_DM_SYSTEM, ...)   LLM: DeepSeek "writer"  │
│     Reads: same as cover note                                   │
│     Writes: recruiter_message (str)                             │
│                                                                 │
│  4. Humanizer.humanize(final_resume)   LLM Phases 3-4 optional │
│     Humanizer.humanize(cover_note)                              │
│     Humanizer.humanize(recruiter_message)                       │
│     Reads: company_intelligence.maturity → tone profile         │
│                                                                 │
│  5. ResumeCompiler._verify_links_preserved()  DETERMINISTIC     │
│  6. ResumeCompiler.generate_quality_report()  DETERMINISTIC     │
│                                                                 │
│  Writes: application_pack (dict → ApplicationPack)              │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
  orchestrator.py saves to output/council/{person}/{job}/
         │
         ├── 00_input_snapshot.json
         ├── 01_canonical_resume.json
         ├── 02_preservation_contract.json
         ├── 03_company_intelligence.json
         ├── 04_role_decode.json
         ├── 05_user_truth.json
         ├── 06_positioning_strategy.json
         ├── 07_section_rewrites.json
         ├── 10_final_resume.md         ← humanized, tailored markdown
         ├── 11_cover_note.md
         ├── 15_quality_report.md
         ├── 16_user_review_summary.md
         └── 17_council_run_log.json
```

---

## Pipeline B — career-ops Skill (In-Context, CLI-Agnostic)

```
User pastes JD URL or text
    │
    ▼ Agent reads these files at runtime:
    ├── cv.md
    ├── modes/_shared.md          (scoring, archetypes, global rules)
    ├── modes/_profile.md         (user customizations, archetypes, framing)
    ├── config/profile.yml        (identity, comp targets, role shape)
    └── article-digest.md         (proof points with exact metrics)
    │
    ▼
┌──────────────────────┐
│  Step 0: Archetype   │    Source: modes/_shared.md:74-87
│  Detection           │    Output: archetype label (1 of 6)
└──────┬───────────────┘    Consumer: all downstream blocks
       │
       ▼
┌──────────────────────┐
│  Step 1: JD Acquire  │    Tool: Playwright (primary) → WebFetch (fallback)
│                      │    Output: jd_text (str)
└──────┬───────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│  Step 2: Evaluation A–G                              │
│                                                      │
│  Block A: Role summary (archetype, domain, seniority)│
│  Block B: Match with cv.md (exact line citations)    │
│  Block C: Seniority + strategy                       │
│  Block D: Comp research (WebSearch → Glassdoor/Levels)│
│  Block E: CV personalization plan (top 5 changes)    │
│  Block F: Interview prep (STAR stories, case study)  │
│  Block G: Posting legitimacy (3-tier assessment)     │
│                                                      │
│  Source: modes/_shared.md + batch/batch-prompt.md    │
│  Output: Markdown report (reports/{num}-{slug}.md)   │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│  Step 3: PDF Generation                              │
│                                                      │
│  Reads: cv.md (RAW — NOT Council output)  ⚠️         │
│  Reads: templates/cv-template.html                   │
│  Extracts: 15-20 JD keywords                         │
│  Rewrites: Professional Summary (inline LLM)         │
│  Reorders: bullets by JD relevance (inline LLM)      │
│  Writes: /tmp/cv-{candidate}-{company}.html          │
│  Runs: node generate-pdf.mjs → output/*.pdf          │
│                                                      │
│  Source: modes/pdf.md (interactive)                  │
│          batch/batch-prompt.md §Paso 4 (batch)       │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────┐
│  Step 4: Tracker     │    Writes: batch/tracker-additions/{num}.tsv
│  Line                │    Merges: node merge-tracker.mjs
└──────────────────────┘
```

---

## Pipeline C — India Fit Engine

```
discovery.py → JobPosting list
profile_manager.py → user profile dict
    │
    ▼
LLMIndiaFitEngine.score_batch()     careerloop/india_fit_llm.py
    │
    ├── For each job: score_job(job, profile)
    │   ├── _build_user_prompt(job, profile) → 30-line structured prompt
    │   ├── DeepSeek API call (model=deepseek-chat, T=0.3)
    │   ├── Parse JSON response (handles ```json code blocks)
    │   └── Returns {overall_score, recommendation, dimensions{...}}
    │
    └── sort by overall_score desc
    │
    ▼
daily_runner.py → shortlist_formatter.py → user report
```

---

## Pipeline D — Showcase Builder

```
User data (name, metrics, lessons, principles, target company)
    │
    ▼
.claude/skills/showcase-builder/SKILL.md
    │
    ├── Reads: templates/showcase-template.html (canonical template)
    ├── Selects: color variant (5 options, mapped by company archetype)
    ├── Fills: HTML template slots (single-pass LLM generation)
    ├── Writes: output/showcase-{slug}.html
    └── Runs: generate-pdf.mjs → output/showcase-{slug}.pdf
```

---

## Cross-Pipeline Data Flows (and gaps)

```
cv.md ──────────────────────────────────────────────────┐
    │                                                    │
    ▼                                                    ▼
Pipeline A (Council)                          Pipeline B (career-ops skill)
    │                                                    │
    └─→ 10_final_resume.md                   PDF reads cv.md directly
           │                                    │
           │    ✅ CONNECTED (P0 Fix)            │
           │    run_council calls renderer      │
           │                                    ▼
           └────────────────────────────> HTML template → PDF
```
Pipeline B evaluation (modes/_profile.md user framing)
    │
    │    ⚠️ DISCONNECTED GAP ⚠️
    │    Council never reads _profile.md
    │
    └──── NOT consumed by Pipeline A
```

---

## Function Call Graph (Council)

```
run_council.py / run_council_v3.py
  └── ResumeCouncilOrchestrator.run()               orchestrator.py:42
        ├── CouncilContextLoader.load()              context.py:20
        │     └── ProfileManager.load()              profile_manager.py
        ├── get_council_graph()                      graph.py:656
        │     └── build_council_graph()              graph.py:626
        │           └── StateGraph(CouncilState)
        │                 ├── parse_node             → ResumeCompiler.parse_markdown()
        │                 │                              compiler.py:200-280
        │                 ├── contract_node          → ResumeCompiler.build_contract()
        │                 │                              compiler.py:290-380
        │                 ├── company_intelligence   → _call(_S3_SYSTEM, ...)
        │                 │                              → CouncilLLMClient.complete_json()
        │                 │                                  llm.py:80-149
        │                 ├── role_decode            → _call(_S4_SYSTEM, ...)
        │                 ├── user_truth             → _call(_S5_SYSTEM, ...)
        │                 ├── positioning            → _call(_S6_SYSTEM, ...)
        │                 ├── section_rewrites       → _call(_S7_SYSTEM, ...)
        │                 ├── truth_guard            → TruthGuard.validate()
        │                 │                              truth_guard.py:200-400
        │                 │                          → TruthGuard.repair()
        │                 │                              truth_guard.py:400-600
        │                 └── assembly              → ResumeCompiler.assemble()
        │                                               compiler.py:400-525
        │                                           → _call(_COVER_NOTE_SYSTEM, ...)
        │                                           → _call(_RECRUITER_DM_SYSTEM, ...)
        │                                           → Humanizer.humanize()  (x3)
        │                                               humanizer.py:64-200
        │                                           → ResumeCompiler._verify_links_preserved()
        └── _save_artifacts()                        orchestrator.py:180-250
              └── output/council/{person}/{job}/*.json
```

---

## Prompt Assembly Points (Dynamic Injection)

| Prompt | Variables Injected | Assembly Location |
|--------|--------------------|-------------------|
| `_S3_SYSTEM` | company, jd[:3000] | `graph.py:150-157` |
| `_S4_SYSTEM` | jd_text, company_intelligence JSON | `graph.py:193-197` |
| `_S5_SYSTEM` | today (from runtime_context or state) | `graph.py:239-240` |
| `_S5` user prompt | canonical_resume JSON, role_decode JSON | `graph.py:234-236` |
| `_S6` user prompt | company_intelligence + role_decode + user_truth JSON | `graph.py:274-278` |
| `_S7` user prompt | canonical_resume + contract + strategy + user_truth JSON | `graph.py:320-325` |
| `_COVER_NOTE` user prompt | job_title, company, positioning_strategy, top_proofs | `graph.py:489-495` |
| `_RECRUITER_DM` user prompt | same as cover note | `graph.py:489-495` |
| `TONE_ADAPTER_SYSTEM` | tone (from positioning), company_type (from intel.maturity) | `humanizer_prompts.py:78-79` |
| India Fit user prompt | job fields + user profile fields | `india_fit_llm.py:185-212` |
| batch-prompt.md | `{{URL}}`, `{{JD_FILE}}`, `{{REPORT_NUM}}`, `{{DATE}}`, `{{ID}}` | batch orchestrator (bash) |
