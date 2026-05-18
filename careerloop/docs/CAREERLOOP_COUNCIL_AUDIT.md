# CareerLoop — Resume Council v3 Deep Audit

**Audited:** 2026-05-18  
**Files audited:** `graph.py`, `orchestrator.py`, `compiler.py`, `llm.py`, `context.py`, `models.py`  
**Purpose:** Identify duplication, hallucination points, missing constraints, weak prompts, output contract gaps

---

## 1. Architecture Summary

The Council runs as a LangGraph StateGraph with 9 nodes in linear order:

```
parse → contract → intelligence → decode → truth → strategy → rewrites → truth_guard → assembly → END
```

8 systems total (parse + contract are Systems 1-2, assembly is System 8). Each node calls DeepSeek via `CouncilLLMClient` except `parse`, `contract`, `truth_guard` (deterministic), and `assembly` (deterministic + 2 LLM calls for messages).

---

## 2. Node-by-Node Audit

### System 1: Document Parser (`parse_node`)

| Aspect | Finding |
|--------|---------|
| Code | `compiler.py:17-63` — regex-based markdown split |
| LLM? | No — deterministic |
| Strengths | Fast, reliable. Link extraction (`re.findall(r"\[.*?\]\((.*?)\)"`) is correct. Section classification into PUBLIC/PRIVATE works. |
| Weaknesses | `_classify_section` uses hardcoded keyword lists. A markdown section titled "Salary Expectations" is correctly caught as PRIVATE; "Target Role" is caught. But "Compensation Philosophy" would miss the filter and become UNKNOWN. Edge case, not a blocker. |
| Hallucination risk | None — deterministic |
| Verdict | **Solid.** Extend the private-keyword list over time as new edge cases surface. |

### System 2: Preservation Contract (`contract_node`)

| Aspect | Finding |
|--------|---------|
| Code | `graph.py:73-80` — calls `ResumeCompiler.build_contract()` |
| LLM? | No — deterministic |
| Strengths | Produces a structured contract that governs what sections can be touched, order preserved, links preserved. Core differentiation. |
| Weaknesses | `build_contract()` is not shown in the 80 lines of `compiler.py` I read — check if it exists. The contract references `max_allowed_changes: int = 3` but I don't see how this is enforced downstream. |
| Hallucination risk | None — deterministic |
| Verdict | **Solid conceptually. Needs enforcement verification** — the contract must be *mechanically* enforced in `assembly_node`, not just passed as context to the LLM. |

### System 3: Company Intelligence (`company_intelligence_node`)

| Aspect | Finding |
|--------|---------|
| Code | `graph.py:84-93` — single LLM call with company + JD |
| LLM? | Yes — DeepSeek via `_call()` |
| Strengths | Structured output contract in `models.py` (CompanyIntelligence dataclass: summary, business_model, india_presence, maturity, hiring_urgency, culture_signals, red_flags, positioning_implications, interview_implications, confidence, missing_data). |
| Weaknesses | **CRITICAL:** The prompt is 2 lines: `"Analyze the target company. Do NOT invent facts. If unknown, say UNKNOWN."` — This is not a research engine. It's asking an LLM to recall training data about a company from memory, which means: (a) stale data, (b) hallucination risk despite the guard, (c) no web lookup, (d) no persistence to `company_memory`. The `CompanyIntelligence` dataclass has 11 fields but the system prompt has no schema — relies entirely on `complete_json()` magic. |
| Hallucination risk | **HIGH.** LLM is generating company facts from training data only. No grounding. |
| Verdict | **PLACEHOLDER.** This is the node that `company_intel.py` (the new module from the reuse audit) will replace. The output dataclass is well-designed; the input gatherer is not. Until `company_intel.py` exists, this node produces unreliable intelligence. |
| Action | Replace with `company_intel.py` → cache in `company_memory` → feed structured output into this node as pre-computed context, removing the raw LLM call. |

### System 4: Role Decoder (`role_decode_node`)

| Aspect | Finding |
|--------|---------|
| Code | `graph.py:98-123` — LLM call with JD + company intelligence |
| LLM? | Yes — DeepSeek |
| Strengths | Explicit JSON schema in the prompt (`normalized_title`, `seniority`, `must_haves`, `nice_to_haves`, `hidden_expectations`, `day_one_deliverables`, `screening_keywords`, `disqualifiers`, `confidence`). Schema matches `RoleDecode` dataclass exactly. |
| Weaknesses | Takes `company_intelligence` as input — which is the unreliable output from System 3. Contamination risk: role decode inherits bad company intel. The prompt does not separate "read from JD" vs "infer from market knowledge" — an LLM might hallucinate screening keywords not actually mentioned. |
| Hallucination risk | **MEDIUM.** Schema-constrained, but inherits bad upstream data + lacks grounding instruction for each field. |
| Verdict | **Good prompt, correct schema. Needs grounding discipline.** Add per-field attribution requirement: `"must_haves": [{"requirement": "...", "source": "JD line"}]`. This also feeds Truth Guard (System 7.5) with audit trail. |

### System 5: User Truth (`user_truth_node`)

| Aspect | Finding |
|--------|---------|
| Code | `graph.py:128-138` — LLM call with resume + role decode |
| LLM? | Yes — DeepSeek |
| Strengths | `UserTruth` dataclass is excellent: `confirmed_skills`, `weak_skills`, `evidence_bank`, `strongest_proof_points`, `claims_allowed`, `claims_not_allowed`, `private_constraints`. This is the core moat. The prompt locks seniority to "earliest professional date in resume" — good discipline. |
| Weaknesses | **CRITICAL:** The prompt has NO JSON schema. Relies on `complete_json()` to guess the structure. `claims_not_allowed` must be exact strings — if the LLM writes "7 years of AI experience" but the resume only supports 4, the string must match what SectionRewrites might generate. Subtle miss. |
| Hallucination risk | **HIGH.** This node can hallucinate `confirmed_skills` — if the resume says "familiar with Docker" and the LLM returns `confirmed_skills: [{"skill": "Docker", "years": 5, "evidence": "..."}]`, the next stages trust it. No mechanical cross-check against the parsed resume. |
| Verdict | **Highest-leverage node. Highest-risk node.** Needs: (1) explicit JSON schema in prompt, (2) mechanical cross-check against `canonical_resume` sections for every `confirmed_skill`, (3) `claims_not_allowed` should include approximate/fuzzy match patterns, not just exact strings. |

### System 6: Positioning Strategy (`positioning_node`)

| Aspect | Finding |
|--------|---------|
| Code | `graph.py:143-151` — LLM call with company intel + role decode + user truth |
| LLM? | Yes — DeepSeek |
| Strengths | `PositioningStrategy` dataclass is the correct abstraction: `one_line_positioning`, `narrative_angle`, `lead_strengths`, `proof_points_to_emphasize`, `things_to_downplay`, `tone_guidance`, `recruiter_first_impression_target`, `application_stance`. The stance enum (STRONG_PUSH/CAREFUL_PUSH/STRETCH/HOLD/SKIP) is exactly right. |
| Weaknesses | No JSON schema in prompt. The prompt is 2 lines: "Create the strategic narrative. Do NOT rewrite the resume. Decide on the application stance and angle." The LLM receives 3 upstream artifacts (company, role, user) with no instruction on how to weigh them. |
| Hallucination risk | **MEDIUM.** Less fact-heavy than User Truth, so hallucination risk is lower. Main risk: `proof_points_to_emphasize` referencing achievements the user doesn't actually have (inherited from System 5 hallucination). |
| Verdict | **Good abstraction, weak prompt.** Needs: (1) JSON schema in prompt, (2) explicit instruction to ONLY reference proof points from `evidence_bank` in User Truth output — no invention. |

### System 7: Section Rewrites (`section_rewrites_node`)

| Aspect | Finding |
|--------|---------|
| Code | `graph.py:156-170` — LLM call with resume + contract + strategy + user truth |
| LLM? | Yes — DeepSeek |
| Strengths | Prompt has explicit constraints: preserve links, no AI-slop, no unsupported claims, don't touch private sections. These are the right rules. |
| Weaknesses | **CRITICAL:** The prompt says "Rewrite only the allowed sections" but does not pass the list of allowed sections from the `PreservationContract`. The LLM has to infer which sections to touch from the contract JSON — and it often gets this wrong. Also: the prompt does not include the original section text in a structured way — it passes the full `canonical_resume` JSON which may confuse the LLM. |
| Hallucination risk | **HIGH.** This node can: (a) rewrite sections the contract said to exclude, (b) drop links despite the instruction, (c) add unsupported metrics ("increased revenue by 30%"), (d) change chronology. Truth Guard catches some of this but only after the fact. |
| Verdict | **Needs structured input.** Each section should be passed individually with a binary `allowed_to_edit: true/false` flag, not left to LLM interpretation of the contract. |

### System 7.5: Truth Guard (`truth_guard_node`)

| Aspect | Finding |
|--------|---------|
| Code | `graph.py:175-193` — deterministic string-match removal |
| LLM? | No — deterministic |
| Strengths | Correct approach: mechanical enforcement, not another LLM. Checks `claims_not_allowed` from User Truth against rewritten text. Removes matches with `re.sub`. |
| Weaknesses | **CRITICAL: Case-insensitive regex substitution is insufficient.** Example: User Truth says claims_not_allowed: ["7 years of AI experience"]. Truth Guard does `re.sub("7 years of AI experience", "", text, flags=re.IGNORECASE)`. But the rewrite might say "7+ years of AI / ML experience" — miss. Or "Seven years building AI systems" — miss. Or "over 7 years leading AI teams" — miss. This guard needs semantic or fuzzy matching, not exact substring. |
| Hallucination risk | **LOW for simple cases, HIGH for sophisticated LLM output.** The guard catches the exact string but LLMs paraphrase. |
| Verdict | **Needs upgrade to fuzzy/semantic matching.** At minimum: (1) normalize both claim and text (strip punctuation, lower, collapse whitespace), (2) extract year-claims with regex `(\d+)[\+]*\s*years?`, (3) add embedding similarity for non-numeric claims. |

### System 8: Safe Assembler (`assembly_node`)

| Aspect | Finding |
|--------|---------|
| Code | `graph.py:208-242` — deterministic assembly + 2 LLM calls for cover note + recruiter DM |
| LLM? | Partial — deterministic assembly, LLM for messages |
| Strengths | `ResumeCompiler.assemble()` is deterministic — good. The assembly produces `final_resume` markdown, quality report via `ResumeCompiler.generate_quality_report()`. |
| Weaknesses | **MAJOR: `cover_note` and `recruiter_message` generation have tiny prompts.** `_COVER_NOTE_SYSTEM` is 1 sentence. `_RECRUITER_DM_SYSTEM` is 1 sentence. Neither has context about the company, the role, or the positioning strategy — they get it via `user_prompt` but the system prompts are so minimal that the LLM defaults to generic template output. These are the "empty stubs" referenced in B3. |
| Hallucination risk | **HIGH for messages, LOW for assembly.** The cover note and recruiter DM will be generic or hallucinated because the prompts lack grounding in the actual resume and positioning. |
| Verdict | **Assembly logic is solid. Message generation needs full rewrite.** Outputs should go through the Humanizer. Cover note and recruiter DM should receive structured context: positioning angle + strongest proof point + 1 sentence about why this specific company. |

---

## 3. Cross-Cutting Issues

### 3.1 Prompt Quality — Systematic Weakness

5 of 6 LLM nodes lack explicit JSON schemas in their prompts:

| Node | Has JSON schema in prompt? | Risk |
|------|---------------------------|------|
| Company Intelligence | No (relies on `complete_json()` magic) | HIGH |
| Role Decode | **Yes** — explicit schema in prompt | — |
| User Truth | No | HIGH |
| Positioning | No | MEDIUM |
| Section Rewrites | No | HIGH |
| Assembly (messages) | Yes — small schemas for cover/DM | MEDIUM |

Every LLM node that produces structured output must have the expected JSON schema in the system prompt. `complete_json()` alone is not enough — the LLM needs the schema to know what fields to produce and what each field means.

### 3.2 No Chaining Discipline

The graph is linear but no node validates the output of the previous node. If System 3 produces bad company intel, Systems 4, 5, 6 all inherit it silently. Each node should validate its inputs against minimum quality thresholds and fail early on bad data.

### 3.3 No Persistence

Council output is ephemeral — it goes to JSON files in `output/` but does not write back to the ledger or `positioning_memory`. The user can't query "what was my positioning angle for the last 3 applications." Council results should write `application_pack` back to the ledger entry.

### 3.4 Leakage Guard Adequacy

The current leakage protection is:
1. `compiler.py` classifies sections as PUBLIC/PRIVATE (keyword-based)
2. `contract_node` excludes PRIVATE sections
3. `assembly_node` only includes contracted sections in final output

This is good but depends entirely on `_classify_section` keywords catching all private sections. A section titled "Compensation Philosophy" would leak through.

---

## 4. Output Contract — Current vs Required

### Current Output (`ApplicationPack.to_dict()`)

```
resume_markdown         ← assembled text (deterministic)
cover_note              ← LLM-generated (2-sentence prompt, generic)
recruiter_message       ← LLM-generated (1-sentence prompt, generic)
quality_report          ← deterministic (link count, section count, TOUCHED/FROZEN)
user_review_summary     ← hardcoded string
```

### Required Output (from architecture consolidation §2)

```
resume_markdown         ✅ exists
recruiter_message       ⚠️ exists but empty/generic
cover_note              ⚠️ exists but empty/generic
positioning_summary     ❌ NOT in output (exists in state as positioning_strategy but never included in pack)
user_review_summary     ⚠️ exists but hardcoded
quality_report          ✅ exists (basic: link/section counts)
preserved_links         ❌ NOT in output (must be verified + listed)
blocked_claims          ❌ NOT in output (Truth Guard errors exist in state.errors, not surfaced in pack)
```

**Gap: 4 of 8 required fields are missing or stubs.** `positioning_summary`, `preserved_links`, `blocked_claims` must be added. `cover_note` and `recruiter_message` must be properly generated with context and humanized.

---

## 5. Recommendation Matrix

| Node | Keep | Fix | Replace | Priority |
|------|------|-----|---------|----------|
| parse_node | ✅ | Expand private keywords | — | P3 |
| contract_node | ✅ | Verify `build_contract` enforcement | — | P2 |
| company_intelligence_node | — | — | Replace with `company_intel.py` | **P0** |
| role_decode_node | ✅ | Add source attribution per field | — | P2 |
| user_truth_node | ✅ | Add JSON schema + mechanical cross-check | — | **P1** |
| positioning_node | ✅ | Add JSON schema + proof-point grounding | — | P2 |
| section_rewrites_node | ✅ | Structured per-section input + allowed_to_edit flag | — | **P1** |
| truth_guard_node | ✅ | Fuzzy/semantic matching upgrade | — | **P1** |
| assembly_node | ✅ | Full rewrite of cover/DM generation + Humanizer pipe | — | **P0** |

### Immediate (this sprint)

1. **Humanizer layer** (`humanizer.py`) — post-process cover_note + recruiter_message + resume text
2. **Assembly node rewrite** — proper context for cover/DM, add `positioning_summary`, `preserved_links`, `blocked_claims` to output
3. **Truth Guard upgrade** — fuzzy matching for disallowed claims

### Next sprint

4. **Company Intelligence module** (`company_intel.py`) — replace System 3
5. **User Truth hardening** — JSON schema + mechanical cross-check
6. **Section Rewrites** — structured per-section editing

---

*End of council audit. All findings are grounded in code inspection of the files listed above.*
