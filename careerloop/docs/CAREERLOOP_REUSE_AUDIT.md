# CareerLoop Reuse Audit — Career-Ops Capability Map

**Author:** Product Architect (audit pass)
**Date:** 2026-05-18
**Status:** Read-only audit. No code changed.
**Source of truth audited against:** `careerloop/docs/PRD.md` v1.0
**Scope:** Every Career-Ops capability + the new CareerLoop modules

---

## 0. How to read this document

This document answers one question for every existing piece of work:

> *Does this still belong in CareerLoop, and if so — how?*

Each capability gets:
1. **What it does** — purpose, files, IO, mutation footprint
2. **CLI-only or reusable as a module?** — can CareerLoop import it
3. **Quality (1–5★)** — honest assessment with the reason
4. **Decision** — A. Reuse / B. Wrap / C. Rewrite / D. Ignore / E. Future
5. **Integration point** — where it plugs into the CareerLoop core loop

The CareerLoop core loop (from PRD §4):

```
Discover → Verify → Filter → Decide → Research → Position → Prepare → Apply → Follow up → Interview → Learn
```

---

## TASK 1 + TASK 2 — Capability Map (with classification)

### 1.1 `/career-ops-pipeline` (modes/pipeline.md)

| Field | Value |
|---|---|
| **Purpose** | Read pending URLs from `data/pipeline.md`, evaluate each one via auto-pipeline, mark as processed |
| **Files** | `modes/pipeline.md`, `data/pipeline.md`, indirectly `modes/auto-pipeline.md`, `modes/oferta.md` |
| **Inputs** | Markdown checklist of URLs (`- [ ] url | company | role`) |
| **Outputs** | Reports in `reports/`, PDFs in `output/`, rows in `data/applications.md` |
| **Data mutated** | `data/pipeline.md` (moves entries Pending → Processed), `reports/`, `output/`, `data/applications.md`, `batch/tracker-additions/` |
| **Reusable?** | CLI-only — the inbox is markdown, the orchestration is in-agent only. Logic is implicit in a prompt. |
| **Quality** | 3★ — Works. But the URL inbox is Markdown, not a queryable structure. Status transitions are textual. No machine guarantee of dedup or completion. |
| **Decision** | **C. REWRITE** — Concept is right (a pending-URL inbox), implementation is a poor fit for an India-volume pipeline (50+ jobs/day). |
| **Integration** | The CareerLoop ledger already represents this better (`DISCOVERED` → `SHORTLISTED` → `SENT_TO_USER`). Markdown pipeline becomes obsolete. |

---

### 1.2 `/career-ops-evaluate` (modes/oferta.md + modes/_shared.md)

| Field | Value |
|---|---|
| **Purpose** | Deep evaluation of one job posting — Blocks A through G (Role, Match, Level, Comp, Customization, Interview Plan, Posting Legitimacy) |
| **Files** | `modes/oferta.md`, `modes/_shared.md`, `cv.md`, `article-digest.md`, `config/profile.yml`, `modes/_profile.md` |
| **Inputs** | JD text or URL, candidate CV + profile, archetype detection |
| **Outputs** | Markdown report `reports/{###}-{slug}-{date}.md` with 7 blocks + draft application answers + keywords |
| **Data mutated** | New report file, tracker row, optional STAR story bank append |
| **Reusable?** | The framework (A–G structure) is reusable as a *prompt schema*. The execution is agent-bound. |
| **Quality** | 4★ — Strong evaluation framework. A–G is genuinely thoughtful: archetype-aware, gap-aware, includes interview plan + legitimacy in one pass. Block G (legitimacy) overlaps with `careerloop/verification.py` but covers more ground. |
| **Decision** | **B. REUSABLE WITH WRAPPER** — The A–G blocks become the *Deep Evaluation Layer* invoked **after** the India Fit Engine pre-filter. Do NOT run A–G on 50 jobs; run it only on the ≤10 jobs the user expresses interest in. |
| **Integration** | Sits at PRD §6 (Opportunity Intelligence — deep tier) and §9 (Company Intelligence — partial). Triggered lazily, gated by ledger status `APPROVED` or `INTERESTED`. |

---

### 1.3 `/career-ops-compare` (modes/ofertas.md)

| Field | Value |
|---|---|
| **Purpose** | Side-by-side ranking of 2+ already-evaluated offers across 10 weighted dimensions |
| **Files** | `modes/ofertas.md` |
| **Inputs** | Multiple jobs (text/URL/tracker refs) |
| **Outputs** | Ranking table + recommendation |
| **Data mutated** | None directly — consumes evaluations |
| **Reusable?** | The 10-dimension weighting is a stable schema. Could be ported to Python easily. |
| **Quality** | 3★ — Good schema, but partially redundant with India Fit Engine's 14 dimensions. The "time-to-offer speed" + "growth trajectory" dimensions are unique. |
| **Decision** | **B. REUSABLE WITH WRAPPER** — Keep as the *decision compression* surface (PRD §7). Use this to rank the daily 5 vs save 3 vs ignore the rest. Later: also use to compare *received* offers. |
| **Integration** | PRD §7 (Decision Compression) and §13 (Application Execution — offer comparison subphase). |

---

### 1.4 `/career-ops-contact` (modes/contacto.md)

| Field | Value |
|---|---|
| **Purpose** | Generate 3-sentence LinkedIn outreach messages (Recruiter / Hiring Manager / Peer / Interviewer) under 300 chars |
| **Files** | `modes/contacto.md`, `cv.md`, `config/profile.yml` |
| **Inputs** | Company, role, contact type, evaluated report (optional) |
| **Outputs** | Draft messages in chat |
| **Data mutated** | None |
| **Reusable?** | Prompt-only. No code dependencies. Easy to port. |
| **Quality** | 3.5★ — Good 3-sentence framework with role-type specialization. Lacks Humanizer layer pass — outputs can still feel templated. Hard rule "draft only, never auto-send" is already enforced by being prompt-only. |
| **Decision** | **B. REUSABLE WITH WRAPPER** — Wrap in Humanizer + recruiter/referral layer. The framework stays. |
| **Integration** | PRD §13 (Application Execution — recruiter/referral) and depends on §12 (Humanizer). |

---

### 1.5 `/career-ops-deep` (modes/deep.md)

| Field | Value |
|---|---|
| **Purpose** | Generate a structured 6-axis research *prompt* (AI strategy, recent moves, eng culture, challenges, competitors, candidate angle) the user takes to Perplexity/Claude |
| **Files** | `modes/deep.md` |
| **Inputs** | Company, role |
| **Outputs** | A prompt — not actual research |
| **Data mutated** | None |
| **Reusable?** | It's just a prompt template. |
| **Quality** | 2★ — This is **not** company intelligence. It is a *prompt to generate company intelligence elsewhere*. Outputs the user a question, not an answer. Does not answer: "Should this user want this company? What is hiring urgency? What is realistic comp here?" |
| **Decision** | **C. REWRITE** — Concept matches PRD §9 but execution is a placeholder. CareerLoop needs an actual Company Intelligence module that writes to the `company_memory` table (Vision v1.6 §5). |
| **Integration** | PRD §9. Triggered lazily after user shortlists a job (per Vision v1.6 §4 "Lazy-Loaded Deep Intelligence"). Should produce structured output, not a prompt. |

---

### 1.6 `/career-ops-pdf` (modes/pdf.md + generate-pdf.mjs + templates/cv-template.html)

| Field | Value |
|---|---|
| **Purpose** | Render a tailored ATS-clean PDF from CV + JD-driven content rewrites |
| **Files** | `modes/pdf.md` (generation), `templates/cv-template.html`, `templates/cv-template.tex`, `generate-pdf.mjs` (renderer), `generate-latex.mjs` |
| **Inputs** | `cv.md`, JD text, `config/profile.yml`, archetype |
| **Outputs** | `output/cv-{candidate}-{company}-{date}.pdf` |
| **Data mutated** | `output/`, tracker PDF column flips ❌ → ✅ |
| **Reusable?** | `generate-pdf.mjs` is **excellent and pure**: takes an HTML file, normalizes Unicode for ATS, emits a clean PDF. Zero coupling to anything. Same for the LaTeX path. |
| **Quality** | Renderer (`generate-pdf.mjs`): **5★** — Drop-in clean. ATS normalization (em-dash → -, smart quotes → ", zero-width strip) is genuinely valuable. Letter/A4 detection, font self-hosting, all there. Content generator (`modes/pdf.md`): **3★** — Generates content AND renders. Conflates two responsibilities. Resume Council should own content; this should only render. |
| **Decision** | **A. REUSABLE AS-IS (renderer only)** + **D. IGNORE (the content-generation part)** — `generate-pdf.mjs` + `templates/cv-template.html` become the **final renderer** for Resume Council. The `modes/pdf.md` content pipeline is replaced by `careerloop/council/`. |
| **Integration** | PRD §11. Council writes structured Markdown → a compiler step renders to HTML using the template → `generate-pdf.mjs` produces the final PDF. Council never invents content; renderer never invents content either. |

---

### 1.7 `/career-ops-training` (modes/training.md) and 1.8 `/career-ops-project` (modes/project.md)

| Field | Value |
|---|---|
| **Purpose** | Evaluate whether a course/cert (training) or a portfolio project (project) is worth the user's time |
| **Files** | `modes/training.md`, `modes/project.md` |
| **Outputs** | Recommendation report |
| **Quality** | 3★ — Useful as career coaching but not in the core hire-loop. |
| **Decision** | **E. FUTURE PHASE** — Phase 4+. Not core to CareerLoop's discover→apply→learn loop. Park them. |
| **Integration** | Eventually: PRD §15 (Persistent Career Memory) — feeds into long-term skill graph. |

---

### 1.9 `/career-ops-tracker` (modes/tracker.md)

| Field | Value |
|---|---|
| **Purpose** | Read/display/update `data/applications.md` Markdown tracker |
| **Files** | `modes/tracker.md`, `data/applications.md`, `templates/states.yml` |
| **Inputs** | Markdown table |
| **Outputs** | Chat display + status edits |
| **Data mutated** | `data/applications.md` (cell edits on existing rows only) |
| **Reusable?** | The states.yml taxonomy is reusable. The Markdown tracker is NOT reusable as a primary store. |
| **Quality** | 2★ as a **store** (Markdown breaks at 100+ jobs, no atomic writes, no joins, no audit trail). 4★ as a **human-readable view**. |
| **Decision** | **C. REWRITE (the store)** + **A. REUSE (as a UI)** — CareerLoop's `application_ledger.py` (JSON, soon SQLite per Vision v1.6 §5) becomes the source of truth. The Markdown tracker becomes a generated *view* over the ledger. |
| **Integration** | PRD §15 (Persistent Career Memory). One DB, many views. |

---

### 1.10 `/career-ops-apply` (modes/apply.md)

| Field | Value |
|---|---|
| **Purpose** | Live application assistant — reads the active Chrome tab, matches it to existing report, drafts answers for visible form questions |
| **Files** | `modes/apply.md`, `reports/`, `cv.md` |
| **Inputs** | Active page (via Playwright or screenshot), prior evaluation report |
| **Outputs** | Per-question draft responses |
| **Data mutated** | Updates `applications.md` status on confirmation |
| **Reusable?** | Workflow logic transfers. Form-question generation is a wrappable prompt. |
| **Quality** | 4★ — Cleanly designed. Detects role-change vs evaluation, suggests re-evaluate, never submits. Already aligns with "user remains in control" (PRD §13). |
| **Decision** | **B. REUSABLE WITH WRAPPER** — This is the *seed* of CareerLoop's Chrome extension (Vision v1.6 §12). Today it requires Playwright; the extension will hook into the DOM directly. |
| **Integration** | PRD §13 (Application Execution Layer — Chrome extension future). |

---

### 1.11 `/career-ops-scan` (modes/scan.md + scan.mjs)

| Field | Value |
|---|---|
| **Purpose** | Discover new jobs by hitting ATS APIs (Greenhouse/Ashby/Lever/BambooHR/Teamtailor/Workday) and Playwright/WebSearch fallbacks |
| **Files** | `modes/scan.md` (agent flow), `scan.mjs` (zero-token API scanner), `portals.yml`, `data/scan-history.tsv` |
| **Inputs** | `portals.yml` (companies + queries), scan history |
| **Outputs** | Appends to `data/pipeline.md`, `data/scan-history.tsv` |
| **Data mutated** | `data/pipeline.md`, `data/scan-history.tsv` |
| **Reusable?** | `scan.mjs` is pure Node — fully reusable. The ATS adapter logic is gold for any India scanner targeting global ATS-hosted India jobs. |
| **Quality** | `scan.mjs`: **4★** — Zero-LLM, fast, deduped, multi-ATS. The Workday/Ashby/Greenhouse adapters work. Weakness: Western-portal centric, doesn't cover Naukri/Instahyre/Cutshort/Hirist/IIMJobs/Foundit (the India-first sources PRD §5 requires). `modes/scan.md`: **3★** — Useful as a manual fallback. |
| **Decision** | **A. REUSE AS-IS (`scan.mjs` for ATS-hosted India roles)** + **C. REWRITE (India-first portals)** — Keep `scan.mjs` for the ~30% of the India market that lives on Greenhouse/Lever/Ashby. CareerLoop must build separate adapters for Naukri/Instahyre/etc. (PRD §5). The agent-driven `modes/scan.md` flow is partly redundant once CareerLoop's `discovery.py` matures. |
| **Integration** | PRD §5 (Discovery Engine — global ATS slice). Feeds the ledger via `add_job(source="greenhouse-api")`. |

---

### 1.12 `/career-ops-batch` (modes/batch.md + batch/)

| Field | Value |
|---|---|
| **Purpose** | Mass-process a list of URLs through evaluation in parallel headless workers |
| **Files** | `modes/batch.md`, `batch/batch-runner.sh`, `batch/batch-prompt.md`, `batch/batch-state.tsv` |
| **Inputs** | TSV of URLs |
| **Outputs** | Reports + PDFs + tracker rows |
| **Data mutated** | `batch/batch-state.tsv`, `batch/tracker-additions/`, `reports/`, `output/`, eventually `data/applications.md` |
| **Reusable?** | The orchestration pattern (state file + headless workers + resumability) is reusable. The actual prompt is heavy. |
| **Quality** | 3★ — Works. But it doubles every job's LLM cost (deep A–G on everything), which is exactly what Vision v1.6 §4 ("Lazy-Loaded Deep Intelligence") tells us NOT to do. |
| **Decision** | **D. IGNORE (the batch pattern)** + **E. FUTURE (re-imagined)** — Do not batch A–G across 50 jobs. The India Fit Engine already replaces this: cheap pre-filter on all 50, Council only on the few the user shortlists. The resumable state-file pattern itself might be reused later for the daily Hunt-mode application queue. |
| **Integration** | None in Phase 1.5/1.6. Possibly Phase 2 if Hunt-mode auto-generation needs a similar harness. |

---

### 1.13 `/career-ops-patterns` (modes/patterns.md + analyze-patterns.mjs)

| Field | Value |
|---|---|
| **Purpose** | Mine `data/applications.md` for rejection/conversion patterns. Outputs JSON with archetype performance, blockers, remote policy, score-threshold recommendation |
| **Files** | `modes/patterns.md`, `analyze-patterns.mjs`, `data/applications.md`, `reports/` |
| **Inputs** | Tracker history + reports |
| **Outputs** | JSON dashboard + `reports/pattern-analysis-{date}.md` |
| **Data mutated** | Can modify `portals.yml`, `modes/_profile.md`, `config/profile.yml` (with user consent) |
| **Reusable?** | `analyze-patterns.mjs` is pure Node — fully reusable. The recommendations engine is the only useful piece in CareerLoop. |
| **Quality** | 4★ — Genuinely smart. The "no positive outcomes below 4.2/5 → that's your floor" pattern is exactly the learning loop PRD §14 asks for. |
| **Decision** | **B. REUSABLE WITH WRAPPER** — Port to read from CareerLoop ledger (`application_ledger.py`) instead of `applications.md`. The 4 analysis dimensions (archetype, blockers, remote policy, score threshold) become the seed of the Learning Loop (PRD §14). |
| **Integration** | PRD §14 (Interview Memory + Learning Loop). |

---

### 1.14 `/career-ops-followup` (modes/followup.md + followup-cadence.mjs)

| Field | Value |
|---|---|
| **Purpose** | Compute who needs a follow-up today (7d / 3d / 1d cadences) and draft the message |
| **Files** | `modes/followup.md`, `followup-cadence.mjs`, `data/applications.md`, `data/follow-ups.md`, `reports/`, `cv.md` |
| **Inputs** | Tracker + reports |
| **Outputs** | Dashboard + drafts in chat |
| **Data mutated** | `data/follow-ups.md`, `data/applications.md` notes column |
| **Reusable?** | `followup-cadence.mjs` is pure Node. CareerLoop's `ApplicationLedger.transition()` already auto-schedules `follow_up_dates` on `APPLIED` (config.py: `FOLLOW_UP_SCHEDULE = [5, 10, 17, 25]`). Two systems, same intent. |
| **Quality** | 3★ — Cadence rules sound. Drafting prompt is decent but lacks Humanizer. The hard rule ("only record what the user confirms") is already correct. |
| **Decision** | **C. REWRITE** — CareerLoop owns follow-ups end-to-end via the ledger. The Markdown-based `data/follow-ups.md` is replaced by ledger entries. Keep the cadence schema (intervals + max-attempts) and the draft framework. |
| **Integration** | PRD §13 (Apply → Follow up) and §15 (Memory). Ledger already has the column. |

---

### 1.15 `/careerloop-product-lead` (the new skill)

| Field | Value |
|---|---|
| **Purpose** | Cross-agent skill (Claude/Codex/Gemini/OpenCode). Two modes: session-start silent 3-bullet alignment summary, and on-demand full product engineering review. Reads PRD + TRACKER, runs git log, updates tracker. |
| **Files** | `.claude/skills/careerloop-product-lead/SKILL.md`, `.gemini/commands/careerloop-product-lead.toml`, `careerloop/docs/PRD.md`, `careerloop/docs/TRACKER.md` |
| **Inputs** | git history, vision PRD, tracker |
| **Outputs** | Chat summary; tracker session-log appends |
| **Data mutated** | `careerloop/docs/TRACKER.md`, `careerloop/docs/PRD.md` §17 |
| **Reusable?** | Self-contained skill. Already cross-agent. |
| **Quality** | 5★ — Right tool for the job. Exactly what a 16-system, multi-month build needs to stay aligned. Silent default + full on-demand is the correct UX. |
| **Decision** | **A. REUSE AS-IS** — Keep. Improve over time as the tracker entities grow. |
| **Integration** | Meta-layer. Cross-cuts everything. |

---

### 1.16 `/career-ops-interview-prep` (modes/interview-prep.md)

| Field | Value |
|---|---|
| **Purpose** | Generate a structured, evidence-backed interview preparation report for a specific company+role. Research-based: Glassdoor, Blind, LeetCode Discuss, company engineering blog. Produces round-by-round breakdown, question bank with source attribution, story-bank mapping, technical prep checklist, company signals (vocabulary, values, anti-patterns). |
| **Files** | `modes/interview-prep.md`, `interview-prep/story-bank.md`, `reports/`, `cv.md`, `article-digest.md`, `config/profile.yml`, `modes/_profile.md` |
| **Inputs** | Company + role, existing evaluation report (optional), candidate CV + story bank |
| **Outputs** | `interview-prep/{company-slug}-{role-slug}.md` with 7-step structured report: Process Overview, Round-by-Round Breakdown, Likely Questions (Technical/Behavioral/Role-Specific/Background Red Flags), Story Bank Mapping, Technical Prep Checklist, Company Signals, Gap Analysis |
| **Data mutated** | New file in `interview-prep/`; optionally appends to `story-bank.md` if user drafts gap stories |
| **Reusable?** | Prompt-only — structured question taxonomy + source-attribution rules + story-bank mapping schema are the reusable assets. |
| **Quality** | 4★ — Well-structured with hard rules against fabrication (every question must have source or `[inferred from JD]` label). Story-bank gap analysis (strong/partial/none) is genuinely useful. Weakness: executes live WebSearch per invocation rather than caching company intel. |
| **Decision** | **B. REUSABLE WITH WRAPPER** — The 7-step framework + question taxonomy + story-bank mapping are directly reusable. Should integrate with Company Intelligence (`company_intel.py`, Phase 2) so interview loops and common questions are cached per company and don't require re-searching. The "company signals" vocabulary/values extraction from Step 7 overlaps with Company Intelligence `culture_signals`. |
| **Integration** | PRD §14 (Interview Memory). After Company Intelligence is built (Phase 2), `interview-prep` should read cached company intel rather than web-searching from scratch. Story-bank mapping feeds the Learning Loop (which archetypes produce the best story coverage). |

---

### 1.17 `/career-ops-latex` (modes/latex.md + generate-latex.mjs + templates/cv-template.tex)

| Field | Value |
|---|---|
| **Purpose** | Export a tailored, ATS-optimized CV as a `.tex` file and compile to PDF via `pdflatex`. Alternative renderer to the HTML→PDF path. Uses `templates/cv-template.tex` with `{{PLACEHOLDER}}` syntax. |
| **Files** | `modes/latex.md`, `generate-latex.mjs`, `templates/cv-template.tex` |
| **Inputs** | `cv.md`, `config/profile.yml`, JD text, archetype |
| **Outputs** | `output/cv-{candidate}-{company}-{YYYY-MM-DD}.tex` + `.pdf` |
| **Data mutated** | `output/` |
| **Reusable?** | `generate-latex.mjs` is pure Node (validates + compiles via `pdflatex`). `templates/cv-template.tex` is a structured LaTeX template. Both are drop-in reusable. |
| **Quality** | Renderer: 4★ — Clean LaTeX compilation with validation. Requires `pdflatex` on PATH (MiKTeX or TeX Live), which limits portability vs the HTML path. Content generator: 3★ — Same conflation problem as `modes/pdf.md`: mixes content generation with rendering. |
| **Decision** | **A. REUSE AS-IS (renderer only)** + **D. IGNORE (content generation part)** — Same pattern as 1.6. The LaTeX renderer + template become an alternative output format for Resume Council (some users prefer Overleaf-ready `.tex`). Council owns content; `generate-latex.mjs` only renders. Keep as secondary renderer behind the HTML→PDF primary path. |
| **Integration** | PRD §11 (Resume Council output). Council emits Markdown → compiler can target either `cv-template.html` (for `generate-pdf.mjs`) or `cv-template.tex` (for `generate-latex.mjs`). LaTeX path is user-opt-in, not mandatory. |

---

## TASK 3 — Pipeline Inbox Audit

**Files:** `data/pipeline.md`, `modes/pipeline.md`, `modes/auto-pipeline.md`, `batch/`, `scan.mjs`.

### Findings

1. **Today's pipeline inbox is a Markdown file.** URLs sit as `- [ ]` checklist items in `data/pipeline.md`. The current repo has `data/imports/jobs/` (CSV imports landing zone) but `data/pipeline.md` itself is **absent** — the file referenced everywhere in modes does not exist on disk right now. The system has already drifted away from it.
2. **`scan.mjs` appends to `data/pipeline.md`** when run. But CareerLoop's `runner.py` + `discovery.py` write to the **ledger** (`careerloop/ledger.json`), not pipeline.md. Two write paths, two formats, no sync.
3. **The ledger is strictly richer.** A `DISCOVERED` ledger entry has: `job_id`, `status_history`, `fit_score`, `fit_breakdown`, `apply_route`, `recruiter_*`, `follow_up_dates`, `created_at`, `updated_at`. A pipeline.md row has: `url | company | role`. There is no comparison.

### Recommendation

**REPLACE the Markdown pipeline with the ledger as the sole inbox.**

- **Single source of truth for pending/discovered jobs:** `application_ledger.py` (JSON today, SQLite per Vision v1.6 §5 next).
- **Pending URLs become `DISCOVERED` ledger entries.** They naturally inherit `fit_score`, `fit_breakdown`, lifecycle, audit trail.
- **`scan.mjs` should call `add_job()` on the ledger** instead of appending to `data/pipeline.md`. Concretely: wrap the existing scanner in a small Python entry that imports `ApplicationLedger` and adds each discovered posting (or write a thin Node→Python bridge, but native Python is cleaner).
- **`modes/pipeline.md` and `modes/auto-pipeline.md` become obsolete** as user-facing commands. Replace with a `/careerloop daily` standup that reads the ledger and presents the §9 daily decision ritual.
- **The Markdown view CAN survive as a generated artifact** for users who like seeing it as a checklist — but it is derived, not source.

### Migration cost

Trivial. The ledger already exists. `scan.mjs` writes one file. One adapter call replaces one `appendFileSync`.

---

## TASK 4 — A–G Offer Evaluation vs India Fit Engine

### A–G dimensions (from `modes/oferta.md` + `_shared.md`)

| Block | What it measures |
|---|---|
| A | Role Summary — archetype, domain, seniority, remote, team size |
| B | Match with CV — per-requirement mapping to CV lines, gaps + mitigation |
| C | Level & Strategy — "sell senior without lying" plan, downlevel plan |
| D | Comp & Demand — web-researched comp, demand trend |
| E | Customization Plan — top 5 CV changes, top 5 LinkedIn changes |
| F | Interview Plan — 6–10 STAR+R stories mapped to JD, red-flag prep |
| G | Posting Legitimacy — freshness + description quality + layoff signals + repost pattern → 3-tier verdict |

Global score 1–5 across: Match-CV, North-Star, Comp, Cultural signals, Red flags.

### India Fit Engine 14 dimensions (from `careerloop/india_fit_engine.py`)

`role_fit, skill_fit, salary_fit, location_fit, work_mode_fit, notice_period_fit, company_stability, startup_risk, brand_value, commute_risk, assignment_burden, interview_difficulty, response_likelihood, career_trajectory` → 0–100 score.

### Overlap analysis

| A–G block | India Fit overlap | Verdict |
|---|---|---|
| A (Role Summary) | `role_fit` | India Fit covers structurally; A–G adds qualitative archetype framing. |
| B (CV Match) | `skill_fit` (heuristic) | India Fit is heuristic + lookup; B is line-by-line. **Not duplicates** — B is far deeper. |
| C (Level & Strategy) | None | **Unique to A–G.** |
| D (Comp & Demand) | `salary_fit` | India Fit is numeric vs floor; D is market context + Glassdoor. **Complementary.** |
| E (Customization) | None | **Unique to A–G.** Resume Council subsumes E. |
| F (Interview Plan) | `interview_difficulty` (1 dim) | F is interview *prep*, India Fit is interview *cost estimation*. **Not duplicates.** |
| G (Legitimacy) | `response_likelihood`, partial overlap with `verification.py` | All measure "is this real and active." **Consolidate** into one layered legitimacy signal. |
| — | `location_fit`, `work_mode_fit`, `notice_period_fit`, `company_stability`, `startup_risk`, `brand_value`, `commute_risk`, `assignment_burden`, `career_trajectory` | All India-specific. **Unique to India Fit.** A–G has nothing equivalent. |

### Decision

**Keep BOTH. Two-layer evaluation:**

```
50+ discovered jobs
   ↓
[Layer 1: India Fit Engine — 0–100, zero LLM, runs on all 50]
   ↓ (top scorers + user marks INTERESTED)
≤10 candidates
   ↓
[Layer 2: A–G Deep Evaluation — Markdown report, LLM-driven, runs only on shortlist]
   ↓
User decides → Resume Council activates
```

This is exactly the **lazy-loaded deep intelligence** principle in Vision v1.6 §4. India Fit is the cheap pre-filter (PRD §6 — Opportunity Intelligence), A–G is the deep evaluation (also §6 + slices of §10 Positioning). A–G output also feeds Resume Council's `role_decode` and `user_truth` nodes — there is already strong overlap between Block B and `user_truth_node` in `careerloop/council/graph.py`.

**Integration point:** A–G runs *after* the user marks a job `INTERESTED` (ledger transition) and *before* Resume Council. Block G (legitimacy) should be hoisted out of A–G and run earlier, alongside `careerloop/verification.py`, because legitimacy is a filter, not a deep dimension.

---

## TASK 5 — Multi-Offer Compare Audit

**File:** `modes/ofertas.md`. 10 weighted dimensions, simple weighted-sum ranking.

### Reuse decision

**B. REUSABLE WITH WRAPPER.** Three integration points:

1. **Daily decision compression (PRD §7).** Vision v1.6 §9 shows the daily ritual: *"Found 57 jobs. Only 8 clear your threshold. Apply to 5 today. Save 3. Ignore the rest."* `modes/ofertas.md`'s weighted-dimension comparison is the right shape to surface *why* job 1 beats job 3.
2. **Shortlist ranking.** When India Fit returns ≥10 candidates with scores 60–80, the user needs to choose 5. Multi-offer compare ranks them on dimensions the user can interrogate ("Why job 2 over job 7?" → "Job 2 wins on growth-trajectory and remote-quality").
3. **Received-offer comparison.** When the user has 2+ live offers, this same matrix compares them (overlap with the future negotiation phase).

### What to change

- Replace the 10-dimension prompt schema with the India Fit Engine's 14-dimension breakdown so the comparison uses the *same* numbers as discovery (single scoring rubric across the entire pipeline).
- Add "received offer" mode where dimensions shift to comp, ramp-time, learning, exit-options.

---

## TASK 6 — LinkedIn Outreach Audit

**File:** `modes/contacto.md`. 4 contact archetypes (Recruiter, Hiring Manager, Peer, Interviewer), 3-sentence framework, 300-char limit.

### Findings

| Question | Answer |
|---|---|
| Output human enough? | **No.** The frameworks are good but outputs still read as templates without a Humanizer pass. PRD §12 bar: "looks like a thoughtful human wrote this." Current outputs feel competent but identifiable. |
| Supports recruiter/referral? | Yes — all 4 types are covered. |
| Needs Humanizer? | **Yes** — mandatory. This is one of the highest-leverage places for the Humanizer wedge. |
| Hard rule (draft only)? | Already enforced — outputs to chat, never auto-sends. Good. |

### Decision

**B. REUSABLE WITH WRAPPER.** The 4-archetype framework is the right surface area. Add:

1. **Humanizer pass after generation** — strip "passionate", "leverage", "spearheaded" (already partly listed in `_shared.md` cliché list), enforce sentence-length variance, kill rhetorical questions if user's writing style avoids them.
2. **Writing-style calibration** — `_shared.md` already specifies writing-samples extraction. Honor `## Writing Style` from `_profile.md` for outbound text.
3. **Recruiter intelligence layer** — store recruiter LinkedIn + email in the ledger (`recruiter_name`, `recruiter_linkedin`, `recruiter_email` fields already exist on the ledger). After first message, log it.

---

## TASK 7 — Deep Company Research Audit

**File:** `modes/deep.md`.

### Findings

1. **It is a prompt generator, not a research engine.** Output is a 6-axis question template the user takes elsewhere.
2. **Does not answer the questions PRD §9 demands:**
   - "Should this user want this company?" → No.
   - "How should they position?" → No.
   - "What are red flags?" → No (asks the user to ask Perplexity).
   - "What is hiring urgency?" → No.
3. **Output is generic.** Six sections (AI strategy, recent moves, eng culture, challenges, competitors, candidate angle) are sensible but not strategic. They are the questions Glassdoor would already answer.
4. **No lazy-load discipline.** Today there is no gating; the user just calls `/career-ops deep` whenever. CareerLoop needs it to be triggered *only after a user shortlists* (Vision v1.6 §4).

### Decision

**C. REWRITE.** Build a real Company Intelligence module:

- Module: `careerloop/company_intel.py` (new file in the next phase).
- Trigger: ledger transition `SHORTLISTED → SENT_TO_USER → APPROVED` (i.e., lazy).
- Persists to: `company_memory` table (Vision v1.6 §5 — one of the 6 SQLite entities).
- Inputs: company name, role, JD text, user profile.
- Outputs (structured):
  - `business_model`
  - `hiring_intent_signals` (hiring page activity, recent posting velocity, Levels.fyi presence)
  - `stability_signals` (funding round, layoffs, glassdoor sentiment)
  - `culture_signals`
  - `realistic_comp_range_inr`
  - `interview_loop_pattern`
  - `red_flags`
  - `positioning_hint` (1–2 sentences: "this user should lead with X")
  - `confidence`
- `modes/deep.md` becomes a fallback CLI for manual research; the real intelligence is the module.

### Integration point

PRD §9 (Company Intelligence). Should be the **first** lazy node after the user expresses interest, and its output feeds Resume Council's existing `company_intelligence_node` in `careerloop/council/graph.py` (which today just calls an LLM with the JD — it does not consult any stored intelligence).

---

## TASK 8 — ATS CV Generation Audit

**Files:** `modes/pdf.md`, `generate-pdf.mjs`, `templates/cv-template.html`.

### Findings (per question)

| Question | Answer |
|---|---|
| Final renderer for Council output? | **Yes — perfect fit.** `generate-pdf.mjs` is a pure HTML→PDF renderer with ATS Unicode normalization. Zero coupling to Career-Ops logic. |
| Preserves links/structure? | Yes. Anchors render as clickable PDF links by Chromium default. Template uses semantic HTML. |
| Section-level input from Council? | Yes — `cv-template.html` has placeholders (`{{SUMMARY_TEXT}}`, `{{EXPERIENCE}}`, `{{PROJECTS}}`, etc.) that map 1:1 to Council's `SectionRewrites` output. A small compiler step (Council's `compiler.py` already exists with 170 lines) can fill the template. |
| Private metadata leakage safe? | The renderer never sees private metadata. Safety is upstream in Council's `preservation_contract`. Today: yes, safe. |
| Renders only, or generates content? | **`generate-pdf.mjs` renders only.** `modes/pdf.md` *also* generates content — that's the conflated part. |

### Decision

**A. REUSE AS-IS (`generate-pdf.mjs` + `templates/cv-template.html`).** Resume Council pipes into this for the final PDF.

**Pipeline shape:**

```
[Council: parse → contract → intelligence → decode → truth →
 strategy → rewrites → truth_guard → assembly]
    ↓ (Markdown application_pack.resume_markdown)
[md → HTML template fill]
    ↓
generate-pdf.mjs → output/cv-{candidate}-{company}-{date}.pdf
```

**modes/pdf.md (content-generation half) is retired** — it duplicates Council. Keep `modes/pdf.md` only as a manual fallback for non-Council CV generation (e.g., a quick generic CV).

---

## TASK 9 — Live Application Assistant Audit

**File:** `modes/apply.md`.

### Findings

1. **What it does:** Detects the active Chrome tab via Playwright, identifies company+role, matches it to an existing report in `reports/`, reads all form questions, drafts personalized answers, presents for copy-paste. Updates tracker on user confirmation.
2. **Suitable for Chrome extension?** Yes — the workflow is exactly what a Chrome extension would automate. Today it requires Playwright session + agent; tomorrow's extension hooks the same DOM directly without an external browser process.
3. **Stops before submit?** **Yes.** Step 6 explicitly waits for user confirmation. Even tracker update is gated on confirmation.
4. **Hard rule satisfied?** Yes. "NEVER submit applications on behalf of the candidate" (`_shared.md` global rule) is enforced.

### Decision

**B. REUSABLE WITH WRAPPER.** This is the **prototype of the CareerLoop Chrome extension** (Vision v1.6 §12 — Real-World Portal Execution).

### Mapping to CareerLoop

- **Today:** `/career-ops apply` with Playwright = manual prototype.
- **Phase 3 (extension):** Same workflow as a browser extension. Hooks the form DOM, asks the CareerLoop backend for cached answers + on-the-fly generation, presents drop-in autofill, user reviews and submits manually.
- **Backend support needed:**
  - Pre-cached answers per (user, company, role) — stored in `positioning_memory` table (Vision v1.6 §5).
  - Same `application_pack` Council produces, plus a per-question Q&A bank.
  - Status transition `APPROVED → APPLIED` triggered by extension on user submit (gated by extension event, not auto-detection).

---

## TASK 10 — Tracker + Followup + Patterns Audit

**Files:** `modes/tracker.md`, `modes/followup.md`, `modes/patterns.md`, `data/applications.md`, `templates/states.yml`.

### Question-by-question

**Q: Is the current tracker better than `careerloop/application_ledger.py`?**

No — and it isn't close.

| Capability | `applications.md` | `application_ledger.py` |
|---|---|---|
| Atomic writes | No (text edit) | Yes (JSON dump) |
| Audit trail | No | `status_history[]` with reason + date |
| Queryable | grep | `find_by_url`, `find_by_company_role`, `get_by_status`, `get_jobs_needing_action`, `get_follow_ups_due` |
| Status taxonomy | 8 states (states.yml) | 13 states (config.py LEDGER_STATUSES) |
| Score | 1 number (X/5) | Total + per-dim breakdown |
| Apply URL routing | No | `application_url` separate from `source_url` |
| Follow-up scheduling | External script | Auto-scheduled on `APPLIED` transition |
| Recruiter intel | Notes column | First-class fields |
| Concurrency safe | No | JSON read-write is safe under single-process; SQLite (next phase) is multi-process safe |

**Q: Can `states.yml` map to CareerLoop lifecycle?**

Mostly yes. Mapping:

| states.yml | LEDGER_STATUSES |
|---|---|
| evaluated | (no direct equivalent — implies report exists; closest: `SHORTLISTED`) |
| applied | APPLIED |
| responded | (no direct; closest: status_history annotation) |
| interview | INTERVIEW |
| offer | OFFER |
| rejected | REJECTED |
| discarded | ARCHIVED or SKIPPED |
| skip | SKIPPED |

`LEDGER_STATUSES` adds: `DISCOVERED`, `SHORTLISTED`, `SENT_TO_USER`, `MAYBE`, `APPROVED`, `RESUME_READY`, `FOLLOW_UP_DUE`. These are the *pre-application* states the Markdown tracker doesn't model — exactly the lifecycle CareerLoop needs.

**Q: Can rejection patterns feed the learning loop (PRD §14)?**

Yes — `analyze-patterns.mjs` is already shaped right. Three actions:

1. Repoint it from `data/applications.md` to `careerloop/ledger.json` (or, once migrated, SQLite).
2. Promote its 4 analyses (archetype performance, blockers, remote policy, score-threshold) into the `event_timeline` entity (Vision v1.6 §5).
3. Recompute weekly; surface in the daily standup as "this week's learning."

**Q: Can the tracker be a UI view over CareerLoop DB?**

Yes — and it should be. The Markdown tracker becomes a read-only generated artifact from the ledger (one-way dump on a schedule or on `/careerloop tracker view`).

### Recommended architecture

**Single source of truth: CareerLoop ledger (JSON now → SQLite per Vision v1.6 §5).**

- `application_ledger.py` already does CRUD + lifecycle + auto follow-up scheduling.
- Migrate `states.yml` aliases into a canonical-status mapping table (so both Markdown imports and external display can keep working).
- Drop `modes/tracker.md` as a writer. Keep it as a view-only summary command.
- Rewrite `analyze-patterns.mjs` and `followup-cadence.mjs` to read the ledger (preferably reimplement in Python alongside `application_ledger.py` so they share the same data model).

---

## TASK 11 — Reuse Matrix

| Capability | Existing Files | Quality | CareerLoop Need | Decision | Phase | Integration Notes |
|---|---|---|---|---|---|---|
| `/career-ops-pipeline` | modes/pipeline.md, data/pipeline.md | 3★ | Replaced by ledger | **Rewrite** | Phase 1.5 | Markdown inbox → ledger. Discovered jobs land as `DISCOVERED` entries. |
| `/career-ops-evaluate` (A–G) | modes/oferta.md, modes/_shared.md | 4★ | Deep eval after pre-filter | **Wrap** | Phase 1.5 / Phase 2 | Triggered only after `INTERESTED`. Blocks A–F feed Council role_decode & user_truth. Block G hoists to verification layer. |
| `/career-ops-compare` | modes/ofertas.md | 3★ | Decision compression (PRD §7) | **Wrap** | Phase 1.5 | Use India Fit dims, not 10 ad-hoc dims. Drives daily standup + offer comparison. |
| `/career-ops-contact` | modes/contacto.md | 3.5★ | Recruiter/referral outreach | **Wrap** | Phase 2 | Add Humanizer + writing-style. Persist contacts in ledger. |
| `/career-ops-deep` | modes/deep.md | 2★ | Real Company Intelligence (PRD §9) | **Rewrite** | Phase 2 | New `company_intel.py`. Lazy. Writes to `company_memory`. Feeds Council `company_intelligence_node`. |
| `/career-ops-pdf` (renderer) | generate-pdf.mjs, cv-template.html, fonts/ | 5★ | Council final renderer | **Reuse as-is** | Phase 2 | Council emits Markdown → template fill → PDF. |
| `/career-ops-pdf` (content gen) | modes/pdf.md | 3★ | Replaced by Council | **Ignore** | — | Resume Council subsumes content generation. |
| `/career-ops-training` | modes/training.md | 3★ | Career coaching extension | **Future** | Phase 4 | Tie into Persistent Career Memory. |
| `/career-ops-project` | modes/project.md | 3★ | Career coaching extension | **Future** | Phase 4 | Same. |
| `/career-ops-tracker` (data) | data/applications.md | 2★ | Replaced by ledger | **Rewrite** | Phase 1.5 | Source of truth = `application_ledger.py`. |
| `/career-ops-tracker` (UI) | modes/tracker.md, states.yml | 4★ | Human-readable view | **Reuse** | Phase 1.5 | Become a generated view over the ledger. |
| `/career-ops-apply` | modes/apply.md | 4★ | Prototype for Chrome extension | **Wrap** | Phase 3 | Same workflow, DOM hooks instead of Playwright. |
| `/career-ops-scan` (ATS APIs) | scan.mjs | 4★ | Discovery (Western ATS slice of India) | **Reuse as-is** | Phase 1 | Adapt to write to ledger instead of `pipeline.md`. |
| `/career-ops-scan` (India portals) | (none — gap) | — | Discovery (Naukri/Instahyre/...) | **Rewrite (build new)** | Phase 1 | Closes B4 blocker. India-first adapters. |
| `/career-ops-batch` | batch/, modes/batch.md | 3★ | Lazy-load principle says no | **Ignore** | — | Replaced by Fit Engine pre-filter + selective Council. State-file harness MAY be reused later for Hunt-mode queues. |
| `/career-ops-patterns` | analyze-patterns.mjs, modes/patterns.md | 4★ | Learning loop (PRD §14) | **Wrap** | Phase 2 | Read ledger. Feed `event_timeline`. Surface in daily standup. |
| `/career-ops-followup` | followup-cadence.mjs, modes/followup.md | 3★ | Replaced by ledger auto-schedule | **Rewrite** | Phase 2 | Keep cadence schema + draft framework. Ledger owns the data. |
| `/career-ops-interview-prep` | modes/interview-prep.md, story-bank.md | 4★ | Interview prep + story bank mapping | **Wrap** | Phase 2 | Feed from cached Company Intelligence. Story-bank gap analysis feeds Learning Loop. |
| `/career-ops-latex` (renderer) | generate-latex.mjs, cv-template.tex | 4★ | Alternative Council output format | **Reuse as-is** | Phase 2 | Secondary renderer (Overleaf-ready). Opt-in. Council owns content. |
| `/career-ops-latex` (content gen) | modes/latex.md | 3★ | Replaced by Council | **Ignore** | — | Same conflation as modes/pdf.md. Council subsumes. |
| `/careerloop-product-lead` | .claude/skills/, .gemini/commands/ | 5★ | Cross-agent product oversight | **Reuse as-is** | Phase 1 | Ongoing. |
| Resume Council v3 | careerloop/council/ | 4★ | PRD §11 core | **Reuse as-is (active development)** | Phase 2 (in progress) | Truth Guard exists (good). Humanizer missing. cover_note/recruiter_message are stubs. |
| India Fit Engine | careerloop/india_fit_engine.py | 4★ | PRD §6 pre-filter | **Reuse as-is** | Phase 1 (built) | Heuristic-only today; LLM hybrid coming (`india_fit_llm.py`). |
| Application Ledger | careerloop/application_ledger.py | 4★ | PRD §15 single source of truth | **Reuse as-is** | Phase 1 (built) | JSON today, SQLite next per Vision v1.6 §5. |
| Discovery Engine | careerloop/discovery.py | 3★ | PRD §5 | **Wrap** | Phase 1 (in progress) | Add Naukri/Instahyre/Cutshort. Add company-career-page scraper (closes B4). |
| Verification | careerloop/verification.py | 3★ | PRD §5 verification | **Wrap** | Phase 1 | Merge with A–G Block G. One legitimacy signal. |
| Apply Route Resolver | careerloop/apply_route.py | 4★ | Cross-source dedup | **Reuse as-is** | Phase 1 (built) | Pure logic, clean priorities. |
| Profile Manager | careerloop/profile_manager.py | — | Read user profile | **Reuse as-is** | Phase 1 (built) | — |
| WhatsApp UX | careerloop/whatsapp_ux.py | 3★ | PRD daily ritual (Vision v1.6 §9) | **Wrap** | Phase 1.5 | Connect to real ledger; finalize §9 daily standup format. |

---

## TASK 12 — Canonical Architecture After Audit

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CAREERLOOP CANONICAL ARCHITECTURE                     │
│                       (post-audit, no duplication)                          │
└─────────────────────────────────────────────────────────────────────────────┘

DISCOVERY (PRD §5)
├── careerloop/discovery.py            ← CareerLoop owns
├── careerloop/sources/search_adapter.py, scrapegraph_adapter.py, jobspy_adapter.py
├── scan.mjs                           ← Reused (ATS slice). Adapter writes to ledger.
└── [Phase 1 build] Naukri/Instahyre/Cutshort/Hirist adapters (closes B4)

VERIFICATION (PRD §5)
├── careerloop/verification.py         ← CareerLoop owns
└── A–G Block G logic                  ← Merged in. One legitimacy signal.

PRE-FILTER (PRD §6 — cheap layer)
└── careerloop/india_fit_engine.py     ← CareerLoop owns. Runs on every discovered job.

LEDGER / MEMORY (PRD §15, Vision v1.6 §5)
├── careerloop/application_ledger.py   ← SINGLE SOURCE OF TRUTH for jobs & applications
├── careerloop/ledger.json (→ SQLite)  ← Persistent
└── Future: 6-entity SQLite schema (users, strategic_tracks, application_ledger,
    company_memory, positioning_memory, event_timeline)

DECISION COMPRESSION (PRD §7)
├── careerloop/shortlist_formatter.py  ← Daily standup
├── careerloop/whatsapp_ux.py          ← Output channel
└── modes/ofertas.md (wrapped)         ← Why job X beats job Y

DEEP EVALUATION (PRD §6, lazy)
├── modes/oferta.md (wrapped)          ← A–F blocks, runs after INTERESTED
└── Feeds Council role_decode + user_truth

COMPANY INTELLIGENCE (PRD §9)
├── [Phase 2 build] careerloop/company_intel.py   ← REWRITE
├── Persists to company_memory table
└── Replaces modes/deep.md as the real research engine.
    modes/deep.md kept ONLY as manual fallback prompt template.

POSITIONING (PRD §10)
└── careerloop/council/graph.py: positioning_node ← Already exists. Strengthen.

RESUME COUNCIL / APPLICATION PACK (PRD §11)
├── careerloop/council/                ← CareerLoop owns
│   ├── graph.py (8 systems)
│   ├── orchestrator.py
│   ├── compiler.py
│   ├── models.py
│   ├── context.py
│   └── llm.py
└── Outputs application_pack: resume_markdown, cover_note, recruiter_message

HUMANIZER (PRD §12)
└── [Phase 2 build] careerloop/council/humanizer.py  ← REWRITE
    Dedicated pass over every candidate-facing text (resume, cover, DM, follow-up).

FINAL RENDERER (PRD §11 output)
├── careerloop/council/compiler.py     ← Council output → template fill
├── templates/cv-template.html         ← REUSED AS-IS (primary HTML→PDF path)
├── templates/cv-template.tex          ← REUSED AS-IS (secondary LaTeX→PDF path, opt-in)
├── generate-pdf.mjs                   ← REUSED AS-IS (ATS Unicode normalization)
├── generate-latex.mjs                 ← REUSED AS-IS (Overleaf-ready .tex compilation)
└── fonts/                             ← REUSED AS-IS

APPLICATION ASSIST (PRD §13)
├── modes/apply.md (wrapped)           ← Prototype today (Playwright)
└── Future: Chrome extension           ← Same workflow, DOM hooks
    Backend: positioning_memory cache + on-the-fly answer gen

FOLLOW-UP (PRD §13)
├── careerloop/followup.py             ← CareerLoop owns
└── Ledger auto-schedules on APPLIED. followup-cadence.mjs retired.

LEARNING LOOP (PRD §14)
├── [Phase 2 port] analyze-patterns.mjs → careerloop/learning.py
└── Writes to event_timeline; surfaces in daily standup.

INTERVIEW PREP (PRD §14 — Interview Memory)
├── modes/interview-prep.md (wrapped)          ← 7-step framework, question taxonomy, story-bank mapping
├── interview-prep/story-bank.md               ← STAR+R story accumulation
├── [Phase 2 integration] Read from company_memory for cached interview loops + common questions
└── Story gaps feed Learning Loop (archetypes with best story coverage)

RECRUITER / REFERRAL OUTREACH (PRD §13)
└── modes/contacto.md (wrapped + Humanizer)

META
└── .claude/skills/careerloop-product-lead/  ← REUSED AS-IS, cross-agent
```

### 12.1 What remains from Career-Ops UNCHANGED

- `generate-pdf.mjs` (primary renderer)
- `generate-latex.mjs` (secondary renderer, Overleaf-ready)
- `templates/cv-template.html` + `templates/cv-template.tex` + `fonts/`
- `scan.mjs` (Western ATS slice — output adapter swapped)
- `interview-prep/story-bank.md` (STAR+R story accumulation)
- `.claude/skills/careerloop-product-lead/` + `.gemini/commands/careerloop-product-lead.toml`
- `cv.md`, `config/profile.yml`, `modes/_profile.md`, `article-digest.md` (user-layer files per DATA_CONTRACT.md)

### 12.2 What CareerLoop owns EXCLUSIVELY

- All of `careerloop/` (discovery, verification, india_fit_engine, ledger, council, profile_manager, apply_route, dedupe, role_strategy, daily_runner, audit, followup, whatsapp_ux, india_fit_llm, india_filter, shortlist_formatter)
- `careerloop/ledger.json` (→ SQLite)
- `careerloop/profile_extended.yml`
- `careerloop/docs/PRD.md`, `careerloop/docs/TRACKER.md`, `careerloop/docs/vision.md`

### 12.3 Shared infrastructure

- `cv.md` (user CV — read by both Career-Ops modes and CareerLoop Council)
- `config/profile.yml` + `modes/_profile.md` (user identity & customization)
- `generate-pdf.mjs` + `templates/cv-template.html` + `fonts/` (rendering)
- `.claude/skills/`, `.gemini/commands/` (cross-agent skill manifests)

### 12.4 Deprecated (do not extend, plan removal)

- `data/pipeline.md` (replaced by ledger)
- `data/applications.md` (replaced by ledger; kept as generated view only)
- `data/follow-ups.md` (replaced by ledger)
- `batch/` directory (lazy-load principle obsoletes this; revisit only if Hunt-mode needs it later)
- `modes/batch.md`, `modes/pipeline.md`, `modes/auto-pipeline.md` as primary entry points

### 12.5 Future Chrome extension

- `modes/apply.md` (workflow blueprint)
- `positioning_memory` (Vision v1.6 §5) caches per-(user, company, role) answers
- Ledger transitions on submit event
- Council pre-generates resume + Q&A bank when status flips `APPROVED`

### 12.6 Resume Council input / output

**Inputs:**
- `cv.md` (parsed → CanonicalResume)
- `config/profile.yml`
- A ledger entry (`DISCOVERED`+ status) with: title, company, source_url, raw_description (the JD)
- Output of `careerloop/company_intel.py` (when built — Phase 2)
- Output of A–G Block B match analysis (optional cross-feed)

**Outputs:**
- `application_pack`:
  - `resume_markdown` — section-rewritten resume, link-preserving, claim-validated
  - `cover_note` — 3-sentence cover
  - `recruiter_message` — 2-sentence LinkedIn DM
  - `quality_report` — what changed, what was blocked
  - `user_review_summary`
- Pipes into `compiler.py` → HTML fill → `generate-pdf.mjs` → final PDF

### 12.7 Single source of truth — JOBS / APPLICATIONS

**`careerloop/application_ledger.py` + `careerloop/ledger.json` (→ SQLite per Vision v1.6 §5).**

Everything else (Markdown trackers, pipeline.md, follow-ups.md) is either derived view or retired.

### 12.8 Single source of truth — COMPANY RESEARCH

**`company_memory` table (planned, Vision v1.6 §5) populated by `careerloop/company_intel.py` (to be built, Phase 2).**

Until built, no system holds this. `modes/deep.md` only writes prompts the user takes elsewhere; that data does not persist.

---

## TL;DR — Build Next

### Reuse immediately
- `careerloop/application_ledger.py` (ledger + lifecycle)
- `careerloop/india_fit_engine.py` (14-dim pre-filter)
- `careerloop/council/` (Resume Council v3, in active development)
- `generate-pdf.mjs` + `templates/cv-template.html` + `fonts/` (final renderer)
- `scan.mjs` (Western ATS slice; rewire output to ledger)
- `.claude/skills/careerloop-product-lead/` (cross-agent oversight)
- `careerloop/apply_route.py` (apply URL routing + cross-source merge)
- `careerloop/verification.py` (URL liveness)
- `cv.md`, `config/profile.yml`, `modes/_profile.md`, `article-digest.md` (user layer — unchanged per DATA_CONTRACT.md)
- `generate-latex.mjs` + `templates/cv-template.tex` (secondary LaTeX renderer, Overleaf-ready, opt-in)
- `interview-prep/story-bank.md` (STAR+R story bank)

### Wrap (useful logic + needs CareerLoop integration)
- `modes/oferta.md` — A–G evaluation → triggered after `INTERESTED`, feeds Council
- `modes/ofertas.md` — multi-offer compare → daily standup decision compression
- `modes/contacto.md` — LinkedIn outreach → add Humanizer + writing-style
- `modes/apply.md` — live application assistant → blueprint for Chrome extension
- `analyze-patterns.mjs` — pattern miner → repoint to ledger, feed `event_timeline`
- `modes/tracker.md` — generated view over the ledger
- `careerloop/discovery.py` — extend with India-first sources
- `modes/interview-prep.md` — interview prep framework → integrate with Company Intelligence cache, feed Learning Loop

### Rewrite (concept right, implementation wrong)
- `modes/deep.md` → `careerloop/company_intel.py` (real Company Intelligence, lazy, structured output, persists to `company_memory`)
- `data/pipeline.md` → ledger `DISCOVERED` entries
- `data/applications.md` (as a writer) → ledger
- `followup-cadence.mjs` → `careerloop/followup.py` reading the ledger
- India-first portal adapters (Naukri/Instahyre/Cutshort/Hirist/IIMJobs/Foundit) — currently absent

### Secretly already built
- **Full job lifecycle state machine** — `careerloop/config.py` LEDGER_STATUSES + `application_ledger.transition()` with status history. This is the canonical state machine the Markdown tracker never had.
- **Auto follow-up scheduling** — ledger triggers `follow_up_dates` on `APPLIED` using `FOLLOW_UP_SCHEDULE = [5, 10, 17, 25]`. Not surfaced anywhere yet.
- **Truth Guard scaffolding** — `careerloop/council/graph.py:truth_guard_node` exists and matches `claims_not_allowed` against rewrites. Not the full strength PRD §11 demands, but it is wired in.
- **Apply-route resolver with priority order** — `careerloop/apply_route.py` (company_site > greenhouse/lever/ashby/workday > naukri/instahyre > linkedin) — already done.
- **Cross-source merge** — `apply_route.merge_cross_source` handles the same job on multiple portals. Not used widely yet.
- **Cross-agent product oversight** — `careerloop-product-lead` skill works across Claude / Codex / Gemini / OpenCode.

### Not usable (do not invest further)
- `modes/batch.md` + `batch/batch-runner.sh` + `batch/batch-prompt.md` — violates lazy-load principle.
- `data/pipeline.md` as a primary store — Markdown checklists don't scale to 50+ jobs/day.
- `modes/deep.md` as-is — prompt generator, not research engine.
- `data/applications.md` as a writer — replaced by ledger.

### Phase 2 candidates
- Real Company Intelligence module (`company_intel.py`) — PRD §9
- Dedicated Humanizer pass (`council/humanizer.py`) — PRD §12 (B2 blocker)
- A–G evaluation wrapper triggered post-INTERESTED — PRD §6 (deep layer)
- Multi-offer compare integrated as decision-compression surface — PRD §7
- Council polish: cover_note / recruiter_message currently stubbed — PRD §11 (B3 blocker)
- Learning loop port: `analyze-patterns.mjs` → `careerloop/learning.py` reading the ledger — PRD §14
- Interview prep integration: wire `modes/interview-prep.md` to read from `company_memory` (cached interview loops) instead of live WebSearch — PRD §14
- LaTeX renderer integration: wire Council output to `cv-template.tex` → `generate-latex.mjs` as opt-in alternative format — PRD §11

### Phase 3 candidates
- Chrome extension based on `modes/apply.md` workflow — PRD §13, Vision v1.6 §12
- Recruiter outreach memory (`positioning_memory`, recruiter contact graph) — PRD §13
- Interview Memory (transcripts, rounds, outcomes) — PRD §14
- WhatsApp transport completion — Vision v1.6 §4

### Future Chrome extension fuel
- `modes/apply.md` (full workflow blueprint already exists)
- `positioning_memory` table (cached answers per company+role)
- Ledger `APPROVED → APPLIED` transitions triggered by extension submit event
- Council application_pack pre-generation on `APPROVED`
- Per-question Q&A bank stored against the ledger entry

### Single source of truth — JOBS / APPLICATIONS
**`careerloop/application_ledger.py` backed by `careerloop/ledger.json` today, SQLite per Vision v1.6 §5 next.**

### Single source of truth — COMPANY RESEARCH
**Not yet built.** Will be `careerloop/company_intel.py` writing to the `company_memory` table (Vision v1.6 §5). Today's `modes/deep.md` only emits prompts and persists nothing — fixing this is the highest-leverage Phase 2 build for PRD §9.

### Top 3 next actions

1. **Implement dedicated Humanizer pass** (`careerloop/council/humanizer.py`) — closes Tracker B2 + B3, advances PRD §12. Highest unblocking value. Council quality currently capped by AI-slop and stubbed `cover_note`/`recruiter_message`. (PRD §12)

2. **Build Company Intelligence module** (`careerloop/company_intel.py`) — closes the §9 gap. Replace `modes/deep.md`'s prompt-generator with a real research engine that persists structured intel to `company_memory`. Feeds Council `company_intelligence_node`. (PRD §9)

3. **Migrate to single ledger source of truth** — wire `scan.mjs` to call `ApplicationLedger.add_job()` instead of `pipeline.md`; deprecate `data/pipeline.md` and `data/applications.md` as writers; generate them as derived views only. Closes the dual-write problem before it gets worse. (PRD §15)

---

*End of audit. No code was modified during this pass. All findings are documentation-only.*
