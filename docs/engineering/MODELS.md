# CareerLoop — LLM Model Architecture

**Date:** 2026-05-18  
**API Key:** Single DeepSeek key in `.env` → `DEEPSEEK_API_KEY`  
**Base URL:** `https://api.deepseek.com/v1`

---

## 1. Model Selection

| Use Case | Model | Why |
|----------|-------|-----|
| **Resume Council: Strategy** (S3-S6) | `deepseek-v4-pro` | Complex reasoning — company intel, role decode, user truth, positioning |
| **Resume Council: Writing** (S7-S8) | `deepseek-chat` (V3) | Faster, cheaper for section rewrites and message generation |
| **Fit Scoring** (`india_fit_llm.py`) | `deepseek-chat` (V3) | Fast, cheap — 14-dimension heuristic scoring |
| **Job Extraction** (`scrapegraph_adapter.py`) | `deepseek-chat` (V3) | Structured extraction from raw HTML |

**Configuration file:** `config/models.yml`  
**Overrides:** Environment variables in `.env`

---

## 2. API Architecture

```
┌──────────────────────────────────────────────────────┐
│                   .env                              │
│  DEEPSEEK_API_KEY=sk-...                            │
│  DEEPSEEK_BASE_URL=https://api.deepseek.com/v1      │
└──────────────────┬───────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────┐
│              config/models.yml                      │
│  resume_council.strategy_model: deepseek-v4-pro     │
│  resume_council.writer_model: deepseek-chat          │
│  fit_engine.model: deepseek-chat                     │
│  scrape_engine.model: deepseek/deepseek-chat         │
└──────────────────┬───────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────┐
│              careerloop/council/llm.py               │
│  CouncilLLMClient(model_kind)                        │
│    - "strategy" → deepseek-v4-pro                    │
│    - "writer"   → deepseek-chat                      │
│                                                      │
│  complete_json(system_prompt, user_prompt)           │
│    → POST /v1/chat/completions                       │
│    → response_format: {"type": "json_object"}         │
│    → Returns parsed JSON dict                        │
└──────────────────────────────────────────────────────┘
```

---

## 3. Resume Council — Per-Node Model Usage

All LLM calls go through `CouncilLLMClient` in `careerloop/council/llm.py`.

| Node | Graph Function | Model Kind | Tokens (est.) | Cost (est.) |
|------|---------------|------------|---------------|-------------|
| S1: Document Parser | `parse_node` | **None** (deterministic) | 0 | $0 |
| S2: Preservation Contract | `contract_node` | **None** (deterministic) | 0 | $0 |
| S3: Company Intelligence | `company_intelligence_node` | `strategy` (V4 Pro) | ~2K in, ~500 out | ~$0.003 |
| S4: Role Decoder | `role_decode_node` | `strategy` (V4 Pro) | ~3K in, ~500 out | ~$0.004 |
| S5: User Truth | `user_truth_node` | `strategy` (V4 Pro) | ~5K in, ~1K out | ~$0.008 |
| S6: Positioning Strategy | `positioning_node` | `strategy` (V4 Pro) | ~4K in, ~500 out | ~$0.005 |
| S7: Section Rewrites | `section_rewrites_node` | `writer` (V3) | ~8K in, ~4K out | ~$0.006 |
| S7.5: Truth Guard | `truth_guard_node` | **None** (deterministic) | 0 | $0 |
| S8: Assembly + Cover + DM | `assembly_node` | `writer` (V3) × 2 | ~2K in, ~200 out × 2 | ~$0.002 |

**Total per Council run: ~$0.03** (7 LLM calls across 8 systems)

---

## 4. Non-Council LLM Usage

| Module | File | Model | Purpose | Cost/Run |
|--------|------|-------|---------|----------|
| India Fit LLM | `careerloop/india_fit_llm.py` | `deepseek-chat` (V3) | LLM-based job scoring (alternative to heuristic) | ~$0.002 |
| ScrapeGraph AI | `careerloop/sources/scrapegraph_adapter.py` | `deepseek-chat` (V3) | Extract job data from URLs | ~$0.005 |

---

## 5. DeepSeek API Features Used

| Feature | Status | Notes |
|---------|--------|-------|
| `response_format: json_object` | ✅ Active | All Council nodes use this |
| Tool Calling (`tools` param) | ❌ Not used | Audited in `specs/deepseek-tool-calling-audit.md` |
| Strict Mode (`strict: true`) | ❌ Beta | Wait for GA, requires `/beta` base URL |
| Thinking Mode | ❌ Not used | Available on V3.2+, may improve positioning |

---

## 6. Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEEPSEEK_API_KEY` | (required) | Single key for all LLM calls |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | API endpoint |
| `CAREERLOOP_COUNCIL_STRATEGY_MODEL` | `deepseek-v4-pro` | Override Council strategy model |
| `CAREERLOOP_COUNCIL_WRITER_MODEL` | `deepseek-chat` | Override Council writer model |
| `CAREERLOOP_FIT_MODEL` | `deepseek-chat` | Override fit scoring model |

---

## 7. JSON Output — Critical Rules

Per DeepSeek API docs, `json_object` mode requires:
1. `response_format: {"type": "json_object"}` ✅ (llm.py line 73)
2. Include the word "json" in the prompt ✅ (all 6 prompts updated 2026-05-18)
3. Provide example JSON format ✅ (all 6 prompts have `EXAMPLE JSON OUTPUT`)
4. `max_tokens` set high enough ✅ (10000 for Council, 2000-4000 for others)

All Council prompts follow this format. See `careerloop/council/graph.py` — `_S3_SYSTEM` through `_RECRUITER_DM_SYSTEM`.

---

## 8. Cost Estimates

| Operation | Model | Input | Output | Cost |
|-----------|-------|-------|--------|------|
| Single Council run | V4 Pro + V3 | ~24K tokens | ~7K tokens | ~$0.03 |
| Fit scoring (per job) | V3 | ~2K tokens | ~500 tokens | ~$0.001 |
| Job extraction (per URL) | V3 | ~4K tokens | ~1K tokens | ~$0.003 |

**Monthly estimate (50 Council runs + 200 fit scores): ~$2-3**

---

## 9. Changing Models

To switch strategy model from V4 Pro to V3:
```bash
export CAREERLOOP_COUNCIL_STRATEGY_MODEL=deepseek-chat
```

Or edit `config/models.yml`:
```yaml
resume_council:
  strategy_model: deepseek-chat
```

To switch to OpenAI (requires `OPENAI_API_KEY` in `.env`):
```yaml
resume_council:
  strategy_model: gpt-4o
  writer_model: gpt-4o-mini
```
And update `careerloop/council/llm.py` `base_url` and auth header accordingly.

---

*End of model documentation. Last updated 2026-05-18.*
