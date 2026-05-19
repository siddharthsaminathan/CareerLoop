# DeepSeek Tool Calling Audit

**Date:** 2026-05-18  
**Auditor:** Claude Code  
**Scope:** CareerLoop Resume Council v3.0 — `careerloop/council/llm.py`, `careerloop/council/graph.py`, `careerloop/council/orchestrator.py`

---

## 1. Are we currently using DeepSeek Tool Calling or just JSON mode?

**Answer: JSON mode only. Tool Calling is not used anywhere.**

The evidence is in `careerloop/council/llm.py` line 73:

```python
"response_format": {"type": "json_object"},
```

This is the standard `json_object` mode (formerly called JSON mode), not the `tools`/`tool_choice` parameter. Every LLM call in the Council goes through the same `CouncilLLMClient.complete_json()` method (llm.py lines 56-94), which sends a single system+user message pair with `response_format: {"type": "json_object"}`.

The 6 nodes that call the LLM (all via the `_call()` helper in graph.py line 58):

| Node | Graph.py line | System prompt variable |
|------|---------------|----------------------|
| S3: Company Intelligence | 143 | `_S3_SYSTEM` (line 118) |
| S4: Role Decoder | 179 | `_S4_SYSTEM` (line 152) |
| S5: User Truth | 224 | `_S5_SYSTEM` (line 193) |
| S6: Positioning Strategy | 261 | `_S6_SYSTEM` (line 233) |
| S7: Section Rewrites | 308 | `_S7_SYSTEM` (line 270) |
| S8: Cover Note | 472 | `_COVER_NOTE_SYSTEM` (line 397) |
| S8: Recruiter DM | 479 | `_RECRUITER_DM_SYSTEM` (line 403) |

Plus System 1 (Document Parser, line 86) and System 2 (Preservation Contract, line 107) are local Python — no LLM call.

**No `tools`, `tool_choice`, or `strict` parameter appears anywhere in the codebase.**

---

## 2. What would Tool Calling give us that `json_object` mode does not?

### Structured output reliability

`json_object` mode guarantees the response will be parseable JSON, but it does NOT guarantee the JSON will match any particular schema. The model picks its own keys and types based on the system prompt's example JSON. By contrast, Tool Calling accepts a formal JSON Schema (`parameters`) and the model MUST emit exactly that schema. This eliminates:

- **Extra/missing keys.** Currently handled reactively by `safe_construct()` in `orchestrator.py` lines 16-53, which drops unknown keys and silently fills in defaults for missing ones. With Tool Calling, the model would never output unexpected keys or omit required ones.
- **Wrong types.** `json_object` mode can produce `"seniority": 4` instead of `"seniority": "mid-senior"`. Tool Calling enforces types at generation time.

### Schema enforcement

| Property | `json_object` (current) | Tool Calling |
|----------|-----------------------|--------------|
| Output is valid JSON | Yes (API enforced) | Yes (API enforced) |
| Output matches schema | No (prompt-hinted only) | Yes (API enforced) |
| Nested objects validated | No | Yes |
| Array element types enforced | No | Yes |
| Enum values constrained | No | Yes (tool calling) / Yes (strict mode) |
| Unknown keys rejected | No | No (without strict) / Yes (with strict) |

### Recursive/nested objects

The current approach relies on prompt examples with nested structures (e.g., `_S5_SYSTEM` at graph.py line 198-208 has `"confirmed_skills": [{"skill": "...", "years": 4, "evidence": "..."}]`). `json_object` mode does not validate the nesting or the inner types. Tool Calling would enforce that `confirmed_skills` is an array of objects each containing exactly `skill` (string), `years` (integer), `evidence` (string).

**Key concern:** SectionRewrite contains `claims_added` (list of strings), `evidence_used` (list of strings), and nested under `rewrites: Dict[str, SectionRewrite]` in SectionRewrites. This is the most complex schema — Tool Calling would be most valuable here.

### Error handling

Current error handling (`llm.py` lines 80-148) has three layers:
1. Direct `json.loads()` parse (line 82)
2. `_repair_truncated_json()` — heuristic bracket/string closure (lines 96-122)
3. `_extract_partial_json()` — regex fallback to salvage what it can (lines 125-148)

This is fragile and can silently produce corrupted data. With Tool Calling, the API either returns valid schema-compliant JSON or an error — no recovery needed. The error path becomes: retry or fail, no guesswork.

---

## 3. Should we switch to strict mode tool calling (`strict: true`)?

**Yes, but only after due diligence on DeepSeek's beta support.**

### What strict mode adds

Strict mode (`base_url="https://api.deepseek.com/beta"`, `strict: true` in the tool definition) enables:

- **JSON Schema validation server-side.** The API validates the model's output against the schema before returning it. Guarantees the response matches exactly.
- **Enum constraint enforcement.** Values like `change_type` = `"KEEP"`, `"LIGHT_EDIT"`, `"REWRITE"`, `"REMOVE_PRIVATE"` would be enforced at generation time rather than trusted post-hoc.
- **`additionalProperties: false` by default.** Any key not in the schema causes the request to fail, preventing silent data leakage — critical for a Resume Council where PRIVATE_STRATEGY_METADATA must not leak into output.

### Risks

1. **Beta URL.** `https://api.deepseek.com/beta` is not guaranteed stable. We would need to monitor for breaking changes.
2. **Schema compilation overhead.** Each tool definition is a full JSON Schema document (~100-200 lines per node). We would need to define 6-7 tool schemas.
3. **Thinking mode compatibility.** DeepSeek supports thinking mode with tools, but the interaction between thinking budget, strict mode, and `json_object` is less mature than OpenAI's implementation. Need to test.
4. **Error surface area.** Instead of "parse output" errors, we get "schema validation" errors. If the schema is wrong, every call fails.

### Recommendation

Wait on strict mode until we have a working non-strict Tool Calling implementation first. The beta URL and potential instability make it a second-phase improvement. Start with regular `tools` + `tool_choice: "any"` and only add `strict: true` after confirming it works reliably in our 7-node setup.

---

## 4. Should we add `additionalProperties: false` in `json_object` mode?

**No — `json_object` mode does not support this.**

The `response_format` parameter with `"type": "json_object"` accepts only one configuration key: the type. You cannot pass `additionalProperties`, `schema`, or any JSON Schema keywords in standard `json_object` mode.

DeepSeek (like OpenAI) reserves schema-level constraints for the Tool Calling path. In `json_object` mode, the only way to constrain the output is through the prompt itself (example JSON, explicit instructions like "do NOT output extra keys"), which is what we already do.

**Current mitigation:** The `safe_construct()` function in `careerloop/council/safe_model.py` (lines 16-53) handles unknown keys by stripping them with a warning. Missing keys use dataclass defaults. This is a reasonable post-hoc safety net for `json_object` mode, but it means corrupted data silently passes through rather than causing a retry.

A pragmatic improvement without switching to Tool Calling: add explicit "output EXACTLY these keys, no more, no less" instructions to each system prompt, and validate the output keyset in `_call()` before returning success. Re-try on schema mismatch.

---

## 5. Recommended approach for our 6 Council nodes

Each node has a distinct schema. Here are the schemas and their complexity level:

### S3 — Company Intelligence (graph.py line 118)
```
Fields: summary, business_model, india_presence, maturity, hiring_urgency,
        culture_signals[], red_flags[], positioning_implications,
        interview_implications, confidence, missing_data[]
Risk: Low. Flat structure, enums for maturity/hiring_urgency.
```

### S4 — Role Decoder (graph.py line 152)
```
Fields: normalized_title, seniority, must_haves[], nice_to_haves[],
        hidden_expectations[], day_one_deliverables[], screening_keywords[],
        disqualifiers[], confidence
Risk: Low. Flat structure.
```

### S5 — User Truth (graph.py line 193)
```
Fields: total_years_experience, confirmed_skills[{skill, years, evidence}],
        weak_skills[], evidence_bank{skill: [evidence_str]},
        strongest_proof_points[], claims_allowed[], claims_not_allowed[],
        private_constraints[]
Risk: Medium. Nested objects (confirmed_skills item), dictionary-type field (evidence_bank).
      The evidence_bank is a dict of string → array of strings — tricky in JSON Schema.
```

### S6 — Positioning Strategy (graph.py line 233)
```
Fields: one_line_positioning, narrative_angle, lead_strengths[],
        proof_points_to_emphasize[], things_to_downplay[], tone_guidance,
        recruiter_first_impression_target, application_stance (enum),
        reasoning
Risk: Low. One enum (application_stance: STRONG_PUSH, CAREFUL_PUSH, STRETCH, HOLD, SKIP).
```

### S7 — Section Rewrites (graph.py line 270)
```
Fields: rewrites{section_id: {section_id, original_text, rewritten_text,
        change_type (enum), change_reason, claims_added[], claims_removed[],
        evidence_used[], risk_level}}
Risk: High. Nested dict items, each item is a complex object with enums and arrays.
```

### S8 — Cover Note / Recruiter DM (graph.py lines 397, 403)
```
Cover: {cover_note: string}
DM:    {recruiter_message: string}
Risk: Very Low. Single string field.
```

### Recommendation per node:

| Node | Recommend Tools? | Reason |
|------|----------------|--------|
| S3 Company Intelligence | Yes | Schema stability matters for downstream |
| S4 Role Decoder | Yes | Must-haves/nice-to-haves typing matters |
| S5 User Truth | Yes | Nested objects + dict field — biggest win |
| S6 Positioning Strategy | Yes | Enum enforcement for application_stance |
| S7 Section Rewrites | Yes | Most complex schema, biggest risk today |
| S8 Cover Note / DM | No | Single string field, tool calling is overkill |

For S8, keep `json_object` mode or even switch to plain text with `response_format: none`. Tool Calling adds complexity for zero marginal gain on a single string field.

---

## 6. API compatibility issues

### No fundamental compatibility issues.

Our current client (`llm.py` lines 59-76) uses raw `requests.post()` to `https://api.deepseek.com/v1/chat/completions`. The Tool Calling API uses the same endpoint with the same authentication headers. The only change is the request body:

**Current body (llm.py lines 65-74):**
```python
json={
    "model": self.model,
    "messages": [{"role": "system", ...}, {"role": "user", ...}],
    "temperature": self.temperature,
    "max_tokens": self.max_tokens,
    "response_format": {"type": "json_object"},
}
```

**Tool Calling body (would change to):**
```python
json={
    "model": self.model,
    "messages": [{"role": "system", ...}, {"role": "user", ...}],
    "temperature": self.temperature,
    "max_tokens": self.max_tokens,
    "tools": [{"type": "function", "function": {...schema...}}],
    "tool_choice": {"type": "function", "function": {"name": "output"}},
}
```

### One subtle issue: `tool_choice: "required"` vs `tool_choice: {"type": "function", ...}`

DeepSeek's Tool Calling API uses `tool_choice: "required"` to force a tool call (like OpenAI's `"any"`). We should use `tool_choice: {"type": "function", "function": {"name": "output"}}` to pin the exact function — otherwise "required" could theoretically call any defined tool.

### JSON Schema compilation

The schemas in `models.py` are Python dataclasses. We currently serialize their structure into prompt examples. For Tool Calling, we would need to write JSON Schema dictionaries for each schema. This can be automated (there are libraries and helpers for `dataclass → JSON Schema`), but it is new code, not a simple config change.

### Strict mode endpoint

If we pursue strict mode, the base URL changes from `https://api.deepseek.com/v1` to `https://api.deepseek.com/beta`. This means the `base_url` environment variable (`DEEPSEEK_BASE_URL`, llm.py line 47) would need a different value, or we would add a separate config. The API contract is otherwise identical — same authentication, same rate limits.

---

## 7. Concrete recommendation

### Recommendation: Migrate to Tool Calling (without strict mode initially)

**Rationale:**

The currently-fixed "JSON truncation" bug (where raw JSON output was being cut off, requiring `_repair_truncated_json` and `_extract_partial_json` fallbacks in llm.py lines 95-148) is a symptom of relying on `json_object` mode without schema enforcement. The model produces valid-at-generation-time JSON that sometimes gets truncated or slightly malformed because nothing binds it to a specific shape. Adding example JSON to prompts (as you just did) helps but does not eliminate the failure mode.

Tool Calling addresses this at the API level: the model must call the function, and the function must match the schema. No truncation repair, no regex fallback, no silent data corruption.

### Migration plan (effort estimate: 2-3 days)

**Phase 1 — Schema definitions (0.5 day)**
Write a Python function that converts a dataclass to a JSON Schema dictionary. Test with each of the 5 complex schemas (S3-S7). Place in a new file `careerloop/council/tool_schemas.py`.

**Phase 2 — Update LLM client (0.5 day)**
Modify `CouncilLLMClient` to add a `complete_tool()` method alongside (not replacing) `complete_json()`. This method sends `tools`, `tool_choice`, and parses the response's `tool_calls` array instead of `content`. Keep `complete_json()` for S8 cover/DM nodes.

**Phase 3 — Wire up nodes (0.5 day)**
Change the 5 strategy nodes (S3-S7) to call `complete_tool()` instead of `complete_json()`. S8 stays on `json_object` or switches to plain text.

**Phase 4 — Error handling (0.5 day)**
Replace the three-layer JSON repair fallback (llm.py lines 80-148) with a clean retry loop: if the Tool Calling response fails schema validation or returns an error, retry once with a lower temperature. If that fails, surface the error to the node, which already handles it (graph.py `_call()` returns `NodeResult(success=False)`).

**Phase 5 — Test & evaluate (0.5 day)**
Run a full council pipeline on 3-5 test JDs. Compare output quality, parse reliability, and error rate against the current `json_object` approach. Validate that response latency is within acceptable range (Tool Calling may add slight overhead for schema processing server-side).

### What we keep as-is

- **S1/S2 (Document Parser, Preservation Contract):** No LLM call — these are local Python logic. Unchanged.
- **S8 Cover Note / Recruiter DM:** Keep on `json_object` or switch to plain text. Single-string output does not benefit from Tool Calling.
- **`safe_construct()`:** Keep as a defense-in-depth layer even after migration. It protects against schema drift if we add fields to models but forget to update the tool schemas.
- **`Humanizer`:** No change needed — it operates post-LLM on already-parsed text.

### Risk matrix

| Risk | Severity | Mitigation |
|------|----------|------------|
| DeepSeek Tool Calling has different behavior than documented | Medium | Test with current model before full migration. Run A/B comparisons. |
| Schema compilation errors cause all calls to fail | High | Unit-test every tool schema against its corresponding Pydantic/dataclass model. |
| Response latency increases | Low | Tool Calling adds ~50-100ms server-side schema validation. Acceptable. |
| Strict mode beta endpoint changes | Low | Do not use strict mode in Phase 1. Add it only after it graduates from beta. |
| Tool Calling output differs from `json_object` output | Low | The model should produce equivalent JSON. If it does not, adjust system prompts to compensate. |

### If we stay on `json_object`

If migration is deferred, the following improvements would reduce pain:

1. **Post-call key validation in `_call()`** (graph.py line 58). After `payload = client.complete_json(system, user)`, validate that the payload contains exactly the expected keys for that node. Re-try if wrong.
2. **Type coercion in `safe_construct()`.** For example, if `confidence` comes back as `"0.8"` (string) instead of `0.8` (float), coerce it rather than silently dropping or raising.
3. **Use `_S5_SYSTEM`'s `{today}` template injection as a pattern for all prompts** — add an `{expected_keys}` instruction that lists the exact field names and types. This makes the prompt more explicit without changing the API layer.
4. **Log the raw LLM output when `safe_construct` strips unknown keys** — currently logged at WARNING level, but many setups suppress Python logging. Add a `print()` or explicit counter to the system tracker so engineers can monitor schema drift.

---

## Summary

| Dimension | Current (`json_object`) | Proposed (Tool Calling) |
|-----------|------------------------|-------------------------|
| Schema enforcement | None (prompt-only) | API-enforced |
| Error handling | Heuristic repair + fallback | Clean retry or fail |
| Extra keys | Silently stripped | Rejected/retried |
| Wrong types | Dataclass default used silently | Schema validation error |
| Implementation complexity | Low | Medium (new schema files) |
| Runtime overhead | None | ~50-100ms per call |
| Strict mode ready | No | Yes (with beta URL) |

**Bottom line:** Migrate S3-S7 to Tool Calling. Keep S8 on `json_object`. Skip strict mode until DeepSeek graduates it from beta. This eliminates the JSON truncation/repair problem at its root and gives us API-level schema enforcement for the Council's most complex structured outputs.
