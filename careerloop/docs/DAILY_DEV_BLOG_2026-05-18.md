# CareerLoop — Daily Dev Blog: 2026-05-18

**Session duration:** ~8 hours  
**Workstreams:** Claude (architecture + stabilization) + Gemini (discovery pipeline)  
**Commits:** 10+  
**Agents dispatched:** 12+ sub-agents across the session

---

## Timeline

### Morning — Career-Ops Upgrade + Council Unblock
- `career-ops` upgraded v1.3.0 → v1.8.0
- Resume Council v3 pipeline unblocked: `_safe_init()` helper added to `orchestrator.py`
- All 3 fixture tests pass (experienced / fresher / business profiles)
- Leakage guard and link preservation verified

### Mid-Day — Architecture Consolidation
- Master PRD created from 16-part vision (careerloop/docs/PRD.md)
- Product Engineering Tracker created (careerloop/docs/TRACKER.md)
- `careerloop-product-lead` cross-agent skill deployed
- 14 stale docs deleted; docs/ moved to careerloop/docs/
- Career-Ops reuse audit: 17 capabilities classified (Reuse/Wrap/Rewrite/Ignore/Future)
- Canonical Architecture locked (CANONICAL_ARCHITECTURE.md)
- Resume Council deep audit: 8 nodes analyzed, hallucination points identified
- 8 vision amendments proposed and applied

### Afternoon — Council Stabilization
- 6 LLM prompts updated with DeepSeek JSON examples
- Compiler upgraded: regex → mistune AST parser, deterministic assembly
- Truth Guard rewritten: exact-string deletion → semantic claim validation
- Humanizer implemented: 4-phase pipeline, 28 banned words, tone profiles
- `safe_model.py`, `runtime_context.py`, `node_result.py` created
- API key rotated; MODELS.md documenting full LLM architecture
- Nicobar golden run with `cv.md`: 13 sections, 22 bullets, cover note + DM

### Evening — Resume Renderer Fix (4 Agents)
- Structure Agent: NormalizedResume data model + normalizer (1,020 lines)
- Parser Agent: collapsed bullets, arrow replacement, em dash sanitizer
- Frontend Agent: 9 templates with flex job headers, skills grid, print CSS
- Validator Agent: 10 validation rules, CI-ready test runner
- 7 Gemini templates regenerated with populated content

### Late Evening — 6-Agent Architecture Stabilization
- Data Model Architect: NormalizedResume enforced across both renderers
- Markdown Parser Debugger: `_sanitize_text()` at normalizer level
- Template Reviewer: `**bold**` converter, CSS fallbacks for all 9 templates
- Humanizer/Sanitizer: Phase 5 sanitizer, "agentic" banned, post-Humanizer verification
- Validator QA: 10 rules, 94.4% pass rate (36/36 clean renders)
- Regression Tester: 4 resumes × 9 templates = 50 outputs, QA report

---

## Files Created (37)

### Council Pipeline
| File | Purpose |
|------|---------|
| `careerloop/council/humanizer.py` | 5-phase anti-AI detection pipeline |
| `careerloop/council/humanizer_rules.py` | 28 banned words, 12 banned phrases, 3 tone profiles |
| `careerloop/council/humanizer_prompts.py` | Structured LLM prompts for slop detection, realism, humanization |
| `careerloop/council/humanizer_tests.py` | 22 deterministic tests |
| `careerloop/council/truth_guard.py` | Semantic claim validation (VERIFIED/WEAK/UNSUPPORTED/EXAGGERATED/FABRICATED) |
| `careerloop/council/safe_model.py` | Safe dataclass construction with defaults |
| `careerloop/council/runtime_context.py` | Dynamic datetime injection (no hardcoded dates) |
| `careerloop/council/node_result.py` | Structured error handling for Council nodes |

### Rendering Pipeline
| File | Purpose |
|------|---------|
| `careerloop/rendering/resume_model.py` | NormalizedResume dataclass (HeaderInfo, ExperienceEntry, SkillRow, etc.) |
| `careerloop/rendering/normalizer.py` | MD→NormalizedResume converter (476 lines, 10 tests) |
| `careerloop/rendering/validator.py` | 10 validation rules, CI-ready |
| `careerloop/rendering/regression_test.py` | Multi-resume regression test runner |
| `careerloop/rendering/test_validator.py` | Test runner with --all, --strict, --json modes |
| `fill-template.py` | v5: consumes NormalizedResume, structured formatters |

### Documentation
| File | Purpose |
|------|---------|
| `careerloop/docs/PRD.md` | Canonical 16-section vision PRD |
| `careerloop/docs/TRACKER.md` | Rolling session log + system status + blockers |
| `careerloop/docs/CANONICAL_ARCHITECTURE.md` | Final architecture with ownership, deprecation, lifecycle |
| `careerloop/docs/CAREERLOOP_REUSE_AUDIT.md` | 17-capability Career-Ops reuse audit |
| `careerloop/docs/CAREERLOOP_MASTER_VISION_AMENDMENTS.md` | 8 vision amendments (all applied) |
| `careerloop/docs/CAREERLOOP_COUNCIL_AUDIT.md` | Deep node-by-node Council analysis |
| `careerloop/docs/COMPANY_INTELLIGENCE_VISION.md` | Company Intelligence product vision v1 |
| `careerloop/docs/MODELS.md` | Full LLM model architecture + per-node cost estimates |
| `careerloop/docs/FUCKUPS.md` | 8 honest mistakes documented |
| `careerloop/docs/REGRESSION_QA_REPORT.md` | Cross-template regression test results |
| `careerloop/docs/DAILY_DEV_BLOG_2026-05-18.md` | This file |
| `careerloop/docs/specs/humanizer-design.md` | Humanizer design spec |
| `careerloop/docs/specs/company-intel-design.md` | Company Intelligence implementation spec |
| `careerloop/docs/specs/deepseek-tool-calling-audit.md` | DeepSeek Tool Calling vs json_object audit |

### Templates
| File | Purpose |
|------|---------|
| `templates/cv-template-v2.html` | Industrial Editorial template (Crimson Pro + Atkinson Hyperlegible) |
| `careerloop/rendering/templates/*.html` | 7 Gemini templates (classic-ats through founder-operator) |

### Config
| File | Purpose |
|------|---------|
| `config/models.yml` | V4 Pro (strategy) + V3 (writer), 10000 max_tokens |
| `.env` | New API key `sk-5e3258...` (gitignored) |

---

## Bugs Fixed (15+)

| # | Bug | Root Cause | Fix |
|---|-----|-----------|-----|
| 1 | LLM JSON truncated at ~12.8K chars | DeepSeek `json_object` mode without example JSON | JSON examples added to all 6 prompts |
| 2 | Council assembly refused on Truth Guard findings | Truth Guard wrote to `state["errors"]` | Moved to `state["warnings"]` |
| 3 | Resume "truncated" | Humanizer `_adapt_tone()` destroyed all `\n\n` with `" ".join()` | Paragraph-aware processing |
| 4 | `re.sub(r'\s{2,}', ' ', text)` destroyed all newlines | `\s` matches `\n` | Changed to `[^\S\n]{2,}` |
| 5 | `**bold**` appearing in final HTML | Renderer injected raw NormalizedResume text without `_inline_md()` | `_inline_md()` on all text paths |
| 6 | Em dashes `—` everywhere | Normalizer never sanitized text | `_sanitize_text()` at normalizer level |
| 7 | Arrows `→` in output | Same as #6 | Arrow→" to " replacement in normalizer |
| 8 | Humanizer not catching "agentic" | Not in BANNED_WORDS | Added + "multi-agent", "autonomous", "swarm" |
| 9 | Post-LLM artifacts (smart quotes) | No sanitization after LLM phases | Phase 5 `_sanitize_output()` |
| 10 | Collapsed bullets ("text1 - text2 - text3") | LLM writes multiple bullets on one line | `split_collapsed_bullets()` in parser |
| 11 | Gemini 7 templates empty | `render_all_templates.py` mapped by `normalized_type="experience"` (empty) | NormalizedResume consumption |
| 12 | Hardcoded dates in prompts | `Today is May 2026` literal | `runtime_context.py` with `datetime.now()` |
| 13 | Stale Python .pyc cache | Python 3.14 vs venv 3.9 mismatch | Clear `__pycache__` before runs |
| 14 | Company intel = LLM memory recall | No web search, no scraping, no grounding | Prompt restructured to extract from JD; full spec written |
| 15 | `max_tokens: 3000` too low for 6.4KB CV | Council section rewrites produce >3K tokens | Bumped to 10000 |

---

## Architecture Decisions (11 locked)

See `TRACKER.md` for full table. Key additions this session:
- A10: NormalizedResume is the SINGLE data contract for ALL renderers
- A11: Post-render validation FAILS HARD on `**`, `—`, `→` in final HTML

---

## Outputs

```
output/council/siddharth/nicobar-final/     ← Nicobar golden run
output/resume_templates/siddharth/latest/   ← All 9 template renders
output/regression_test/                      ← Regression test results
```

---

## Metrics

| Metric | Value |
|--------|-------|
| Council runs executed | 8+ |
| Resume renders generated | 50+ |
| Templates fixed | 9 |
| Validation rules | 10 |
| Regression pass rate | 94.4% (36/36 clean) |
| Em dashes in final output | 0 |
| Arrows in final output | 0 |
| Raw markdown in final output | 0 |
| Tailoring delta (base vs Nicobar) | 3.6% (improvement needed) |
| Sub-agents dispatched | 12+ |
| Files created/modified | 169+ |

---

## Next Session Priorities

1. **P0:** Fix tailoring delta (3.6% → 15%+) — Council S6/S7 prompt engineering
2. **P1:** Build `company_intel.py` (structured web-sourced company research)
3. **P1:** Run Nicobar golden test with all fixes → final deliverable PDFs

---

*End of 2026-05-18 sessions.*

---

# CareerLoop — Daily Dev Blog: 2026-05-19

**Session focus:** Discovery pipeline debugging — Varsha dry run (fashion buyer/merchandiser, Bangalore/Chennai)  
**What was attempted:** Get real jobs from company career portals for Indian fashion companies  
**Net result:** Spire AI adapter works (Myntra 14 jobs). Everything else still broken.

---

## What Was Done

### Lever Slug Bug Fixed
Regex `r"lever\.co/([a-z0-9_-]+)"` was extracting "v0" from `api.lever.co/v0/postings/meesho`. Fixed to match the full path. Now Meesho (45 jobs), Paytm (116), CRED, Freshworks all fetch correctly.

### Sector → Function Probability Fixed
Finance & Fintech companies (Paytm, Razorpay) were getting fn_prob=0.5 (neutral) for fashion buying because "Finance & Fintech" didn't match any key in the sector matrix. Added explicit `_SECTOR_ALIASES` mapping + Fashion & Retail / Apparel & Textiles sectors. Paytm now scores fn_prob=0.02 for buying → correctly excluded from Varsha's fashion pipeline.

### Role Relevance Filter De-hardcoded
Replaced hardcoded `HARD_REJECT_TITLES` and `ENGINEER_SIGNALS` lists with profile-driven logic. `rejected_roles` comes from `profile.yml`. Domain signal tokens derived from `target_functions` with generic business words ("manager", "senior", "associate", "lead", "director", etc.) stripped from the set to prevent false positives like "Engineering Manager Backend" matching a fashion buyer search.

### Spire AI Adapter (NEW — `careerloop/sources/spireai_adapter.py`)
Discovered that `jobs.myntra.com` is a Flutter SPA powered by Spire AI (`spire2grow.com`). The platform exposes a clean REST API:
- `GET /ies/v1/p/workspaceId?domain={domain}` → workspace ID discovery (no auth)
- `GET /ies/v1/p/requisition/_search` with `workspaceid` header → paginated job list

Implemented adapter. Wired into `_scrape_targeted_companies` as first attempt before `CareerPageCrawler`. Result: Myntra 14 jobs including "Principal Associate - Buying & Merchandising", "Lead Associate - Category Management (Women's Ethnic Wear)".

Tested other fashion companies (Nykaa, Fabindia, Ajio) — all return 404 from workspace lookup. Only Myntra confirmed on Spire AI.

### Career Page URLs Seeded for 16 Fashion Companies
16 fashion/retail companies (Myntra, Nykaa, Fabindia, Arvind, Bliss Club, etc.) now have `career_page_url` in the DB. Most return 0 jobs because their pages are JS-heavy SPAs or Shopify-based with no structured listings.

### Varsha Dry Run — Results
- fashion buyer / Bangalore: 39 jobs after dedup (95 raw)
- fashion buyer / Chennai: 6 jobs
- fashion merchandiser / Bangalore: running
- fashion merchandiser / Chennai: running
- Top genuine matches: Myntra buying/merchandising roles (SpireAI), Bene Kleed Senior Buyer (LinkedIn), Arvind Lifestyle Brands Retail Planning (Cutshort)
- Main contamination source: Meesho Lever board (45 jobs, all functions) — Analytics Manager, Engineering Manager, HR roles all passing role filter due to "category" matching

## What Didn't Work / Still Broken

- **15/16 fashion company portals: 0 jobs.** Bliss Club, Snitch = Shopify stores. Fabindia, Arvind = custom SPAs. Nykaa, Ajio = different platform than Spire AI. `CareerPageCrawler` gets empty HTML shells from all of them.
- **ATS detection wasted ~45 minutes.** Ran `detect_ats_pass.py` on all 62 companies. Fashion companies returned "no ATS detected" because none use Lever/Greenhouse/Ashby. Wrong approach — should have gone straight to Spire AI discovery.
- **Meesho contamination.** 45 Lever jobs from Meesho flood every Bangalore search. Role filter is not tight enough post-ATS-fetch.
- **Workday: still 0 jobs.** BrowserStack, Uniphore detected but no adapter.
- **Score compression.** Without full JD, scores cluster 47-67. No discrimination.
- **Profile bleed in dry run.** `target_roles` and `archetypes` come from Hayagreev's `config/profile.yml` even during Varsha's dry run — inflates role_fit scores for tech roles.

## Discovery Pipeline Status Updated
`careerloop/docs/DISCOVERY_PIPELINE_STATUS_20260518.md` fully rewritten with current state, module-by-module status, and remaining problems.

---

*This session did not move the overall product maturity needle. Discovery pipeline is still at ~75% and mostly broken for company portal layer.*
