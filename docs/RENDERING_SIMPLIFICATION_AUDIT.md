# Rendering Simplification Audit — CareerLoop Resume Council

## TL;DR

The current parsing and rendering architecture is substantially more complex than the transformation it performs. The core job — split a resume into sections, rewrite each section for a target role, reassemble in order — could be expressed with a fixed schema and a simple loop. The actual implementation layers a mistune AST renderer (18 node types handled), a plaintext normalization preprocessor (4 regex passes, 10 ALLCAPS header patterns, 30 location tokens), a 5-key dynamic schema with an `original_order` sort to maintain a sequence that was never shuffled, 5 separate LLM rewrites sending the same context payload multiple times, a regex-based Truth Guard running 6 compiled patterns and a 5-tier classification tree, and a post-assembly humanizer pass. Several of these layers exist to repair damage introduced by upstream stages rather than to add net value. The architecture is not disproportionate in ambition but is disproportionate in implementation surface area relative to verifiable output quality gains.

---

## 1. Parser Complexity Audit

### Parsing chain

`ResumeCompiler.parse_markdown()` is the entry point. The full chain is:

1. **Preprocessing** (`_preprocess_plaintext_cv`): runs two independent passes over the raw text string before any AST parsing occurs.
   - Pass A: if no `##` headings exist, injects `\n\n## HEADING\n\n` via regex for 10 hardcoded ALL-CAPS header strings.
   - Pass B (always): normalizes bullet characters (•●▸▶◆◦∙) to `\n- `; splits run-on text at `Present`/`Currently` + uppercase; splits at `\b\d{4}` + uppercase; loops over 30 location token strings and splits on each.

2. **AST parsing**: `mistune.create_markdown(renderer="ast")(text)` — produces a list of typed dictionaries.

3. **AST walk**: a single linear for-loop over AST nodes, tracking `current_heading` and accumulating `current_body`. Three flush conditions: first heading encountered (flushes pre-heading body as a synthetic `intro` section), each subsequent heading (flushes previous section), end of document.

4. **Section building** (`_build_section_from_ast`): renders heading and body nodes back to markdown strings via `_MarkdownRenderer.render()`. Calls `_classify_section()` on the title string.

5. **Classification** (`_classify_section`): two linear scans over two hardcoded keyword lists (8 private keywords, 14 public keywords). Returns `(normalized_type, VisibilityClass)`.

### Code paths for section detection

There are **three distinct code paths** for detecting section boundaries:

| Path | Trigger | Mechanism |
|------|---------|-----------|
| AST heading path | Input has `#`/`##` markdown headers | mistune emits `heading` node; walk flushes on each |
| ALL-CAPS injection path | Input has no `##` headers | Pass A regex injects them before AST parse |
| No-heading fallback | Entire document has no headings after preprocessing | Single `intro` section wrapping all content |

The ALL-CAPS injection path means the code internally converts a plaintext CV into markdown, then parses that markdown back into an AST, then renders the AST back into markdown — a round-trip that introduces the risk of compound-word artifacts at injection boundaries.

### Special cases and if-branches

`compiler.py` contains **43 `if` branches and 27 `elif` branches** (70 total conditional branches across 609 lines).

Specific special cases worth noting:

- `_render_node` handles 18 distinct AST node types (`text`, `link`, `image`, `paragraph`, `heading`, `blank_line`, `list`, `list_item`, `block_code`, `codespan`, `emphasis`, `strong`, `block_quote`, `thematic_break`, `line_break`, `softbreak`, `html`, `block_html`, `table`, `table_row`, `table_cell`, `footnote_ref`, `footnote_def`) with individual elif branches, plus a children fallback.
- `_build_section_from_ast` has no special cases itself but calls into `_classify_section` which applies 22 distinct keyword checks.
- `assemble()` has a special case for `section_id == "intro"` to suppress the heading output.
- `list_item` rendering reads `node.get("attrs", {}).get("bullet", "-")` — the `"ordered vs unordered"` detection comment is present but the field `bullet` is not reliably populated by mistune 3.x, so all list items receive `-`.

### Output schema

The parser outputs a `CanonicalResume` object with a `sections: List[ResumeSection]` field. Each `ResumeSection` contains:

```
section_id: str           (slugified title, e.g. "professional_experience")
section_title: str        (raw title text, e.g. "PROFESSIONAL EXPERIENCE")
normalized_type: str      (e.g. "experience", "contact", "unknown")
visibility_class: str     (PUBLIC_APPLICATION_CONTENT, PRIVATE, UNKNOWN)
raw_text: str             (body content re-rendered from AST)
original_order: int       (integer index of section appearance)
links: List[str]          (extracted URLs)
confidence: float         (hardcoded to 1.0 in every call path)
```

The schema is **fixed** — every field is present on every section object regardless of content type. The `confidence` field is always 1.0. The `links` field is empty in the Varsha sample because the source PDF had no hyperlinks, making the link audit machinery a no-op for that run.

### Minimum viable schema

The downstream nodes use: `section_id`, `section_title`, `normalized_type`, `visibility_class`, `raw_text`, `original_order`. A schema of:

```json
{"section_id": "...", "section_title": "...", "normalized_type": "...", "visibility_class": "...", "raw_text": "...", "original_order": 0}
```

would satisfy all downstream consumption patterns observed in `graph.py`.

---

## 2. Schema Analysis

### Keys present in `01_canonical_resume.json` (Varsha sample)

```
person_id, sections[].section_id, sections[].section_title,
sections[].normalized_type, sections[].visibility_class,
sections[].raw_text, sections[].original_order,
sections[].links, sections[].confidence, parse_warnings
```

**10 distinct keys** at the section level plus 2 at the top level.

### Which keys are consumed by downstream nodes (S2–S8)

| Key | Consumed by | How |
|-----|-------------|-----|
| `section_id` | S2, S7, S8 | Section exclusion lists, rewrite dict keys, assembly loop |
| `section_title` | S7, S8 | Sent in per-section prompt; used for `## heading` output |
| `normalized_type` | S2, S7 | Contract classification; S7 skip logic for long experience sections |
| `visibility_class` | S2 | Contract building (`sections_to_exclude`) |
| `raw_text` | S5, S7, S8 | S5 receives full `canonical_resume` JSON; S7 per-section prompt; S8 fallback |
| `original_order` | S8 | `sorted(resume.sections, key=lambda s: s.original_order)` |
| `links` | S8 | Link audit in `_verify_links_preserved` |
| `confidence` | Not consumed | No node reads this field after parsing |
| `parse_warnings` | Not consumed | No node reads this field |
| `person_id` | Not consumed downstream | Present in input, never used in any node logic |

**`confidence`, `parse_warnings`, and `person_id` are produced but never read by any downstream node.**

### Dynamic vs fixed schema verdict

The schema is already fixed in practice — `ResumeSection` is a dataclass. The issue is that three fields (`confidence`, `parse_warnings`, `person_id`) are produced but have no consumers.

---

## 3. LLM Rewrite Surface Area

### LLM-calling nodes and their I/O

| Node | System ID | Input | Output | Max tokens |
|------|-----------|-------|--------|-----------|
| S3: Company Intelligence | `company_intelligence_node` | JD text (up to 2500 chars), company name, URL, research sources | `company_intelligence` dict | default |
| S4: Role Decoder | `role_decode_node` | Full JD text + `company_intelligence` JSON | `role_decode` dict | default |
| S5: User Truth | `user_truth_node` | Full `canonical_resume` JSON + `role_decode` JSON | `user_truth` dict | default |
| S6: Positioning Strategy | `positioning_node` | `company_intelligence` + `role_decode` + `user_truth` (public fields) | `positioning_strategy` dict | default |
| S7: Section Rewrites | `section_rewrites_node` | Per-section loop — one call per section | One `SectionRewrite` per call | 4000 |
| S8: Cover Note | `assembly_node` | `job_title`, `company`, `positioning_strategy`, top 3 proof points | `cover_note` string | default |
| S8: Recruiter DM | `assembly_node` | Same as cover note | `recruiter_message` string | default |
| Humanizer (resume) | `assembly_node` | Assembled `final_resume` + `company_type` | Humanized resume text | unspecified |
| Humanizer (cover) | `assembly_node` | `cover_note` + `company_type` | Humanized cover note | unspecified |
| Humanizer (DM) | `assembly_node` | `recruiter_message` + `company_type` | Humanized DM | unspecified |

`graph.py` contains **8 explicit `_call()` invocations** plus 3 additional `humanizer.humanize()` calls inside `assembly_node`, for a total of **11 LLM calls per run**.

For a 5-section resume like Varsha's, S7 makes **5 per-section calls**, so the total is: 1 (S3) + 1 (S4) + 1 (S5) + 1 (S6) + 5 (S7) + 2 (S8 cover/DM) + 3 (Humanizer) = **14 LLM calls per resume run**.

### Redundant data transmission

**S4 receives `company_intelligence` which contains all JD-derived facts already extracted.** S4 also receives the full JD text. There is structural overlap: S3 extracts facts from the JD; S4 re-reads the JD plus S3's output.

**S5 receives the full `canonical_resume` JSON**, which includes `section_title`, `normalized_type`, `visibility_class`, `original_order`, `links`, `confidence` — fields that are irrelevant to the truthfulness audit. S5 only needs `raw_text` per section.

**S7 per-section prompt** sends `tone_guidance`, `role_keywords`, `proof_points`, `claims_allowed` on every section call. These are constant across all 5 sections. For a 5-section resume, this context block is duplicated 5 times.

**S8 cover note and DM** both receive an identical `user_prompt` string (`job_title`, `company`, `positioning_strategy`, `top_proofs`). The only difference is the system prompt. This is two calls for two very short outputs that could be combined.

### Token estimate (Varsha-sized resume)

Varsha's `professional_experience` section `raw_text` is approximately 2,950 characters (~740 tokens). The full `canonical_resume` JSON passed to S5 serializes to approximately 6,000 characters (~1,500 tokens). The `company_intelligence` dict serializes to approximately 2,400 characters (~600 tokens). The S7 experience section prompt (section text ~2,950 chars + context ~500 chars) is approximately 3,450 characters (~870 tokens) — below the 3,500-char skip threshold by 50 characters; a longer resume would skip this section and fall back to the original.

Estimated total input tokens across all 14 calls for a Varsha-sized resume: approximately **12,000–18,000 tokens**.

---

## 4. Reassembly Complexity

### How S8 assembles the final resume

`ResumeCompiler.assemble()` in `compiler.py` (lines 441–482):

1. Sorts `resume.sections` by `original_order` (integer index set at parse time).
2. Iterates sorted sections. Skips sections where `section_id` is in `contract.sections_to_exclude`.
3. For non-`intro` sections, appends `f"## {section.section_title}"` as a heading.
4. Checks if `section_id` is in `rewrites.rewrites`. If yes and `rewritten_text` is non-empty, uses that; otherwise falls back to `raw_text`.
5. Joins all parts with `"\n\n".join(output_parts).strip() + "\n"`.

The `intro` section is a special case: its heading is suppressed (the name/contact block should appear without a `##` heading). This is the only branching logic in the assembler.

### How section order is decided

Order is determined entirely by `original_order`, which is set to `len(sections)` at the moment each section is appended during the parse walk. Since the parse walk reads sections top-to-bottom, `original_order` is effectively the line-position order of headings in the input. No LLM node reorders sections; `contract.ordering_rules` contains the same order but is not actually used in `assemble()` — the sort is on `original_order` directly.

### Observed failure modes

**From `10_final_resume.md` and `07_section_rewrites.json` (Varsha run):**

1. **Truncated professional experience section**: The S7 rewrite for `professional_experience` ends mid-sentence: `"Go Colors (Go Fashion India Ltd.) | Assistant Fashion Manager | Chennai, India | Sept 2020 – June 2023\nSupported buying and mer"`. The 4000-token output limit was hit. The assembler fell back to `raw_text` for this section (the final resume at `10_final_resume.md` contains the complete Go Colors entry), but the `07_section_rewrites.json` file records the truncated string in `rewritten_text`. The assembler's fallback to `raw_text` is the correct safety behavior, but the condition that triggers fallback is `if rw:` (non-empty check) — a truncated rewrite passes this check and would be used as-is. It appears the `_rewrite_preserves_section_structure` check in `section_rewrites_node` caught the `possible_truncation` issue and rejected the rewrite, causing the section to be skipped and thus the original to be used in final assembly.

2. **Contact block run-on survives into assembler**: `01_canonical_resume.json` shows `"VARSHA SATHYANARAYANANthisisvarshasathya@gmail.com"` — the preprocessor's location-token split did not catch this because `VARSHA` is not in `_LOCATION_TOKENS`. The compound-word was passed to S7 which repaired it in the rewrite. The assembler used the S7 rewrite, so the final output is correct. However, the root issue (name concatenated with email in PDF-extracted text) was repaired by LLM rather than the deterministic preprocessor.

3. **Humanizer introduces bullet collapse**: In `application_pack.resume_markdown` (inside `17_council_run_log.json`), the SuperK experience block shows: `"- Improved product margins from 22% to 35% while sustaining competitive pricing by negotiating vendor pricing, MOQs, and. Sourcing terms."` — a period and capitalization artifact (`and. Sourcing`) was introduced by the Humanizer. This artifact does not appear in the S7 rewrite text or the assembled `10_final_resume.md`; it is present only in `application_pack.resume_markdown`. The Humanizer pass produced a regression that the final `.md` file output avoided (it appears the `10_final_resume.md` is written from a different output path than `application_pack.resume_markdown`).

4. **Heading format change during assembly**: `assemble()` always emits `## {section.section_title}`. If the original resume used `###` headings or no headings, they are emitted as `##`. This is a silent normalization, not configurable.

5. **Intro section heading suppression is hardcoded**: Only `section_id == "intro"` suppresses the heading. If a resume has pre-header content that does not match the synthetic ID assignment, this special case may silently emit an unwanted `## Intro/Contact` heading.

---

## 5. Truth Guard Integration Complexity

### Regex patterns

`truth_guard.py` defines **6 compiled regex patterns** as class-level attributes:

| Pattern name | Claim type | Notable complexity |
|---|---|---|
| `YEAR_PATTERN` | `year_experience` | 5-line verbose pattern with lookahead for 6 boundary words |
| `PERCENT_PATTERN` | `percentage` | 2-line pattern matching ~10 outcome verbs |
| `SKILL_ASSERT_PATTERN` | `skill_assertion` | 3-line pattern matching 8 qualifier words + knowledge phrases |
| `OWNERSHIP_PATTERN` | `ownership` | 3-line pattern matching 10 ownership verbs, negative lookbehind |
| `QUANTIFIED_PATTERN` | `quantified_achievement` | 2-line pattern matching 7 delivery verbs + currency amounts |
| `LEAD_IN_PATTERN` | used in year classification | 2-line pattern for 7 approximation phrases |

`truth_guard.py` contains **67 `if` branches and 14 `elif` branches** (81 total) across 813 lines.

### Transformation steps on flagged text

For a claim that reaches the repair path, the steps are:

1. `validate()` calls `_extract_claims()` → produces `List[Claim]` with byte positions.
2. Each claim is passed to `_classify_claim()`, which routes to one of four type-specific classifiers: `_classify_year_claim`, `_classify_skill_claim`, `_classify_evidence_claim`, `_classify_generic`.
3. Claims with `risk_level in ("UNSUPPORTED", "EXAGGERATED", "FABRICATED")` go to `repair()`.
4. `repair()` sorts flagged claims by `start_pos` descending and loops, calling `_find_claim_span()` then `_generate_repair()` per claim.
5. `_find_claim_span()` has **three fallback strategies**: exact position check with token overlap, case-insensitive substring search, loose token-based search.
6. `_generate_repair()` routes to `_repair_year_claim`, `_repair_skill_claim`, `_repair_evidence_claim`, or `_repair_fallback`.
7. After all repairs, `_cleanup_artifacts()` applies 5 more regex substitutions (double spaces, space-before-punctuation, doubled punctuation, empty bullet lines, 3+ newlines, trailing-whitespace-per-line).

### Failure modes of regex-based claim extraction on LLM-generated text

**From the Varsha Truth Guard report (`08_truth_guard_report.json`):**

- `total_claims: 3`, `verified: 0`, `weak: 1`, `unsupported: 2`.
- The two `UNSUPPORTED` claims are `"managed end-to-end sourcing"` and `"Built a custom Excel WIP tracker"` — both are directly evidenced in the original resume. They scored UNSUPPORTED because `_classify_evidence_claim` uses Jaccard token overlap against the LLM-paraphrased `evidence_bank` strings. The Jaccard overlap between `"Built a custom Excel WIP tracker"` and the evidence bank string `"Built WIP trackers, dashboards using VLOOKUP and pivot tables"` is below the 0.3 threshold due to vocabulary differences between the LLM's paraphrase in S5 and the LLM's rewrite in S7.

- The `OWNERSHIP_PATTERN` has a negative lookbehind `(?<![-\w])` to avoid firing on hyphenated compounds. This lookbehind does not handle Unicode hyphens (–, —) which appear in the resume text (`Nov 2025 – Present`), producing potential false boundary matches.

- The `YEAR_PATTERN` classified `"3+ years of experience owning P&L"` as WEAK (confidence 0.6) because `claimed_years (3) <= total_years (4.1)` but the `+` modifier triggers the puffery branch. This is a correct classification but the repair was not applied (WEAK claims are not repaired), so the technically conservative `3+ years` claim survived while the truthful claim would be `4+ years`.

- `_cleanup_artifacts()` runs string substitutions on already-repaired markdown text, including `re.sub(r'\s+([,.;:!?)])', r'\1', text)` which removes spaces before closing parentheses. This pattern can corrupt markdown link syntax `](url)` if a space appears before `]`.

---

## 6. Current Model vs Simpler Model (Observation)

### What the current model uniquely provides

- **Mixed-format resume handling**: The preprocessor handles PDF-extracted text with concatenated words, Unicode bullet characters, and run-on date/location boundaries. A fixed 6-section schema would require clean input.
- **PRIVATE section detection and exclusion**: The `_classify_section` private-keyword scan and `PreservationContract` machinery strips internal metadata sections (deal-breakers, salary) from the output. A simpler model with user-controlled input could rely on the user to not include private sections.
- **Per-section fallback on LLM failure**: If S7 fails or produces a truncated rewrite for one section, the assembler uses the original for that section while using rewrites for others. A monolithic single-prompt approach would fail the entire resume.
- **Link preservation audit**: The `_verify_links_preserved` cross-check catches LLM-dropped hyperlinks. Relevant for resumes with portfolio links.
- **Truth Guard claim classification**: Provides a machine-readable risk report for each output (VERIFIED/WEAK/UNSUPPORTED/EXAGGERATED/FABRICATED per claim). No equivalent exists in a template-fill approach.
- **Schema validation on LLM outputs**: `validate_payload()` calls in S3, S5, S6 catch malformed JSON from LLM and fill defaults.

### What complexity has unclear ROI

- **`_MarkdownRenderer` with 18+ node type handlers**: The renderer handles tables, block quotes, footnotes, code blocks, images, and thematic breaks. None of these node types appear in any of the sample resume data. The renderer exists to round-trip the AST faithfully but the round-trip introduces render fidelity risk (e.g., the `list_item` bullet detection issue).

- **`original_order` sort in assembler**: The sections are parsed in document order and appended in document order. The `original_order` integer exists solely to re-sort them into the same order they were already in. No node ever reorders sections. The sort is a no-op that adds a field and a sort call.

- **`contract.ordering_rules`**: Built in S2 and stored in state, but `assemble()` does not use it. `ordering_rules` is computed but never consumed.

- **`confidence` field on ResumeSection**: Hardcoded to `1.0` on every section. Not read by any downstream node.

- **`parse_warnings` on CanonicalResume**: Initialized as an empty list and never populated. Not read by any downstream node.

- **`person_id` on CanonicalResume**: Set to `"default"` in all parse calls. Not used in any node logic after parsing.

- **Pass A location-token loop in preprocessor** (30 tokens, each triggering a `re.sub` loop): Runs on every resume regardless of whether it was PDF-extracted. Adds 30 regex substitution calls to every parse. The Varsha run shows that the most important concatenation (name + email: `VARSHAthisisvarshasathya`) was not caught by this mechanism because `VARSHA` is not a location token.

- **S4 receiving full JD text when S3 already extracted it**: S3 extracts all facts, inferences, and implications from the JD. S4 then receives both S3's output and the raw JD again. S4 could receive only S3's `facts` and `role_implications` lists.

- **Separate cover note and recruiter DM LLM calls**: Both receive identical user context. Both produce short texts (3 sentences and 2 sentences respectively). These are two separate network round-trips.

- **Post-Humanizer slop verification loop**: Hard-coded word list (`"agentic"`, `"multi-agent"`, `"autonomous"`, `"swarm"`, `"AI revolution"`, `"leverage"`, `"spearheaded"`) checked after a Humanizer pass that was already supposed to remove them. The check exists because the Humanizer is not reliable; the check's existence is evidence of a reliability gap in the Humanizer, not a complexity that adds value.

- **`SectionRewrite.claims_added` and `claims_removed` fields**: These are populated by S7 but never validated against `claims_not_allowed` by the assembler. The Truth Guard does post-hoc validation but does not reference these lists. The fields are present in state but have no downstream consumer.

---

## 7. Complexity Inventory

| Component | Lines of code | Conditional branches (if/elif) | Observed failure modes | Complexity verdict |
|-----------|--------------|-------------------------------|----------------------|--------------------|
| `_MarkdownRenderer` | ~115 | 24 elif (node type dispatch) | list_item bullet type unreliable; round-trip introduces render artifacts | High surface area; 15+ node types exist in code with no sample evidence of use |
| `_preprocess_plaintext_cv` | ~55 | 2 | Name+email concatenation not caught; location-loop runs on clean input | 30-token loop runs unconditionally; catches subset of PDF artifacts |
| `parse_markdown` (AST walk) | ~80 | 8 | pre-heading body synthetic section edge case | Reasonable complexity for the job |
| `_classify_section` | ~25 | 2 scans × 22 keywords = ~22 path variants | "unknown" classification for non-standard headers | Keyword lists are hardcoded; no fallback inference |
| `build_contract` (S2) | ~30 | 3 | `ordering_rules` computed but unused | `ordering_rules` field is dead code |
| `assemble` (S8) | ~30 | 3 | `intro` heading suppression hardcoded; assembler uses `original_order`, ignores `ordering_rules` | Simple and correct; intro special-case is narrow |
| `_verify_links_preserved` | ~55 | 4 | Per-section final link counts are approximate (global scan, not section-scoped) | Reasonable for link-heavy resumes; no-op on Varsha sample |
| S3 `company_intelligence_node` | ~60 | 5 | UNGROUNDED path produces low-confidence output silently used downstream | Correct to warn; grounding_status propagation is reasonable |
| S4 `role_decode_node` | ~20 | 2 | Receives redundant JD text already processed by S3 | Redundant input; minor |
| S5 `user_truth_node` | ~30 | 4 | Receives full canonical_resume JSON including unused fields | Serializes ~1,500 tokens of schema overhead per call |
| S6 `positioning_node` | ~25 | 3 | Correctly strips `private_constraints`; schema validation present | Reasonable |
| S7 `section_rewrites_node` | ~90 | 10 | Truncation at 4000 tokens; `_rewrite_preserves_section_structure` rejects truncated output and falls back | Per-section loop with 5 duplicate context blocks; truncation fallback works |
| `_rewrite_preserves_section_structure` | ~20 | 5 | `possible_truncation` heuristic (trailing character check) is fragile | Fragile heuristic; correct in Varsha case |
| `truth_guard.TruthGuard` | ~400 | 81 | UNSUPPORTED false positives on ownership claims; `_cleanup_artifacts` can corrupt markdown links | Evidence bank Jaccard matching produces false positives; 6 patterns with lookaheads |
| Humanizer (assembly_node) | 3 calls, code in separate file | — | Introduced `"and. Sourcing"` artifact in cover note path | Humanizer output in `application_pack` diverges from `10_final_resume.md` output |
| Post-Humanizer slop check | ~15 | 3 | Existence of this check documents Humanizer unreliability | Diagnostic value only; does not repair |
