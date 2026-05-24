# CareerLoop Documentation Portal

Welcome to the CareerLoop documentation portal. All product documents, engineering designs, sprint/backlog artifacts, and retrospective learnings are organized into exactly four specialized directories. This index explains what each directory and document is for.

---

## 📂 Product (`docs/product/`) — 10 documents

> High-level strategy, target personas (ICP), feature lists, canonical vision documents, ROI/UX thesis, and competitive positioning. Read these when aligning on business objectives, user states, or product roadmap decisions.

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **[PRD.md](docs/product/PRD.md)** | Canonical Product Requirements Document v1.0 — single source of truth for CareerLoop. Covers the 16 core systems, Employer Discovery Engine (§18), Human Pipeline Layer (§19), ROI & UX Architecture (§20), and Delivery Orchestration addenda (§21-§23). Updated by the `careerloop-product-lead` skill each session. | Starting any session. Understanding what to build and why. |
| **[ROI_UX_PRODUCT_VISION.md](docs/product/ROI_UX_PRODUCT_VISION.md)** | Complete ROI thesis, UX philosophy, 12-workflow ROI map, four user entry points, metric hierarchy, competitor map by workflow, monetization strategy, and brutal prioritization framework. Core principle: _Intelligence is the product. Automation is the UX._ | Making product decisions, prioritizing features, designing UX flows, evaluating monetization. |
| **[TECH_ROADMAP.md](docs/product/TECH_ROADMAP.md)** | Phased MECE roadmap including Phase 0 Delivery Foundation, Decision Compression, Resume Council, execution, memory, and consumer UX. | Planning implementation order and sprint scope. |
| **[DECISION_COMPRESSION_VISION.md](docs/product/DECISION_COMPRESSION_VISION.md)** | CEO Phase 1.5 spec for reducing job-search overload into daily choices, modes, tracks, and briefs. | Designing triage, daily brief, and decision UX. |
| **[COMPANY_INTELLIGENCE_VISION.md](docs/product/COMPANY_INTELLIGENCE_VISION.md)** | Product vision for the Company Intelligence compiler block (System 3). Defines why deep signals matter more than generic internet summaries and how intelligence informs positioning. | Designing or modifying the company research pipeline. |
| **[SEARCH_VISION.md](docs/product/SEARCH_VISION.md)** | Three-layer browser portal scraper architecture, Greenhouse/Ashby/Lever API integrations, sector-to-function scoring logic, and cross-source deduplication strategy. | Extending discovery capabilities, adding new job sources, modifying scoring heuristics. |
| **[COMPETITIVE_POSITIONING.md](docs/product/COMPETITIVE_POSITIONING.md)** | Positioning and competitor framing for CareerLoop's market category. | Messaging, pricing, and external narrative work. |
| **[MASTER_LANDING_PAGE_VISION.md](docs/product/MASTER_LANDING_PAGE_VISION.md)** | Vision for CareerLoop's public-facing landing page and onboarding flow. Covers positioning, messaging, and conversion funnel design. | Working on marketing, landing page, or user acquisition. |
| **[vision_v1.6_historical.md](docs/product/vision_v1.6_historical.md)** | Historical CareerLoop vision v1.6 — retained purely for archival reference. | Historical context only. Do not use for active engineering requirements. |
| **[README.md](docs/product/README.md)** | Subdirectory index for the product docs directory. | Quick navigation within product docs. |

---

## 📂 Engineering (`docs/engineering/`) — 7 documents

> Locked system architecture specifications, micro-system designs, model routing configurations, AST template normalizers, and programmatic schemas. Read these when modifying LangGraph orchestrations, adding LLM schemas, or updating template parsers.

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **[CANONICAL_ARCHITECTURE.md](docs/engineering/CANONICAL_ARCHITECTURE.md)** | The locked technical reference architecture for the 8-system Resume Council. Establishes programmatic data contracts, state variables, execution rules, and inter-system protocols. This is the engineering source of truth. | Any modification to the Resume Council pipeline, LangGraph nodes, or system contracts. |
| **[breakdown-20-part.md](docs/engineering/breakdown-20-part.md)** | Detailed architectural breakdown covering the complete data flow: parsed plaintext CVs → LLM section rewriting → post-render PDF generation. Maps all 20 subsystems. | Understanding the full pipeline topology and data flow dependencies. |
| **[resume-council-vision.md](docs/engineering/resume-council-vision.md)** | Initial technical draft outlining the 8 systems of the Resume Council: Truth Guard, Humanizer, Preprocessors, Normalizers, Rewriters, Validators, Renderers, and Compilers. | Designing new Council subsystems or refactoring existing ones. |
| **[MODELS.md](docs/engineering/MODELS.md)** | Master routing table mapping LLM models (`deepseek-v4-pro`, `deepseek-chat`, etc.) to each system node, with rationale for model selection per node. | Changing model assignments, evaluating model performance per node, adding new LLM endpoints. |
| **[pipeline_graph.md](docs/engineering/pipeline_graph.md)** | Mermaid diagram visualizing the exact node flow inside the LangGraph orchestrator, including conditional branches, parallel nodes, and merge points. | Understanding execution order, debugging pipeline deadlocks, adding new nodes. |
| **[specs/](docs/engineering/specs/)** | Granular, programmatic engineering specs for individual subsystems: `company-intel-design.md` (S3 caching and web search), `humanizer-design.md` (5-stage humanization pipeline), `deepseek-tool-calling-audit.md` (structured output schema analysis), `MECE_COMPANY_INTEL_PLAN.md` (MECE-compliant company intelligence architecture). | Implementing or modifying a specific subsystem. Read the corresponding spec first. |
| **[MVP_SPRINT_PLAN.md](docs/engineering/MVP_SPRINT_PLAN.md)** | Full Sprint 0–7 implementation plan for the delivery foundation. Transport layer, state machine, onboarding, pack delivery, resume editor, ATS validator, follow-up engine, Gmail/calendar, interview memory. | Starting any Sprint 0–7 work. Read before touching transport, session, packs, or integrations. |
| **[README.md](docs/engineering/README.md)** | Subdirectory index for the engineering docs directory. | Quick navigation within engineering docs. |

---

## 📂 Tech Backlog (`docs/tech-backlog/`) — 7 documents

> Sprint logs, active engineering trackers, checklist metrics, blocker registers, redesign blueprints, and implementation planning artifacts. Read these when starting a new session, checking blockers, or planning work.

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **[TRACKER.md](docs/tech-backlog/TRACKER.md)** | Live Product Engineering Tracker. Contains current sprint focus, system status percentages, session logs, open blockers, and locked architecture decisions. Programmatically read and updated by the `careerloop-product-lead` skill. | Every session start. Checking what's blocked, what's current, what to work on next. |
| **[chrome_extension_implementation_plan.md](docs/tech-backlog/chrome_extension_implementation_plan.md)** | Chrome browser extension implementation plan detailing the Manifest V3 sidepanel architecture and CDP debugger trusted inputs. | Planning the co-pilot auto-filler implementation. |
| **[delivery_ui_implementation_plan.md](docs/tech-backlog/delivery_ui_implementation_plan.md)** | Delivery & UI Implementation Plan detailing the Telegram bot transport and the weekly Momentum Dashboard. | Planning the Telegram bot integration and weekly dashboard metrics. |
| **[memory_systems_vision.md](docs/tech-backlog/memory_systems_vision.md)** | Exhaustive MECE Memory Systems Vision & Implementation Plan detailing the 4 core dimensions, Supabase Postgres schemas, and job state transitions. | Designing or scaling the central Supabase/SQLite memory database. |
| **[cli_redesign_implementation_plan.md](docs/tech-backlog/cli_redesign_implementation_plan.md)** | Premium cyberpunk terminal redesign blueprint utilizing Rich and Prompt Toolkit. Establishes live status cards, layout frames, and slash command integrations. | Designing or modifying the CareerLoop terminal interface. |
| **[DELIVERY_ORCHESTRATION_HANDOFF_2026-05-23.md](docs/tech-backlog/DELIVERY_ORCHESTRATION_HANDOFF_2026-05-23.md)** | Concrete next-agent handoff for the LangGraph Supervisor, transport abstraction, PostgresSaver, and assisted apply scaffold. | Continuing the May 23 delivery architecture work without reconstructing context from diffs. |
| **[8-PIPELINE-CHECKLIST.md](docs/tech-backlog/8-PIPELINE-CHECKLIST.md)** | Structured, sequential verification checklist for the Resume Council compiler nodes. Step-by-step validation to ensure no bugs ship. | Before merging any Council pipeline changes. Run the checklist. |
| **[COUNCIL_REDESIGN_PLAN.md](docs/tech-backlog/COUNCIL_REDESIGN_PLAN.md)** | Initial architectural redesign plan targeting markdown failures, formatting errors, and missing metrics discovered in early Council iterations. | Understanding the history of Council fixes and what was learned. |
| **[CAREERLOOP_REDESIGN_IMPLEMENTATION_PLAN.md](docs/tech-backlog/CAREERLOOP_REDESIGN_IMPLEMENTATION_PLAN.md)** | Deep masterplan for the v3 orchestrator. Details LangGraph structures, NormalizedResume schemas, the 16-part data quality audit strategy, and data contracts. | Major refactoring of the orchestrator or schema layer. |
| **[MINIMAL_REFACTOR_PLAN.md](docs/tech-backlog/MINIMAL_REFACTOR_PLAN.md)** | Practical checklist of quick stabilization refactors for the rendering pipeline. Low-risk, high-impact fixes. | Quick rendering bug fixes, stabilization passes. |
| **[README.md](docs/tech-backlog/README.md)** | Subdirectory index for the tech backlog directory. | Quick navigation within backlog docs. |

---

## 📂 Learnings (`docs/learnings/`) — 13 documents + 5 dev-blog entries

> Engineering memory: detailed code quality audits, daily dev blogs, retrospective fuckups, delta forensics, root-cause analyses, regression reports, and discovery pipeline status logs. Read these when conducting code reviews, investigating bugs, or understanding past design failures.

### Audit & Analysis Documents

| Document | Purpose | When to Read |
|----------|---------|--------------|
| **[orchestration_audit_report.md](docs/tech-backlog/orchestration_audit_report.md)** | Exhaustive first-principles audit detailing multiline CV paste truncation, state schema conflicts, PgBouncer savers, and state override bugs. | Debugging CLI, transport, onboarding, and orchestrator issues. |
| **[FUCKUPS.md](docs/learnings/FUCKUPS.md)** | Honest compilation of mistakes, root causes, and prevention strategies. **Crucial reading to prevent regressions.** | Before any major code change. Know what broke before. |
| **[CAREERLOOP_REUSE_AUDIT.md](docs/learnings/CAREERLOOP_REUSE_AUDIT.md)** | Deep audit of 15 capabilities across standard skill structures, reuse probability, and platform dependencies. | Designing new skills or capabilities. Check what's reusable. |
| **[CAREERLOOP_COUNCIL_AUDIT.md](docs/learnings/CAREERLOOP_COUNCIL_AUDIT.md)** | Initial audit pinpointing failure vectors in the S7 rewriting node: collapsed bullets, JSON parsing failures. | Debugging S7 rewrite issues. |
| **[CAREERLOOP_MASTER_VISION_AMENDMENTS.md](docs/learnings/CAREERLOOP_MASTER_VISION_AMENDMENTS.md)** | Log of amendments expanding PRD §5 (Employer Discovery) and §19 (Referral/Outreach Path). | Understanding how the vision evolved and why these sections were added. |
| **[20_PART_ARCHITECTURAL_AUDIT.md](docs/learnings/20_PART_ARCHITECTURAL_AUDIT.md)** | Exhaustive 20-part analysis contrasting theoretical Resume Council specifications with live repository implementations. Gap analysis. | Understanding where the codebase diverges from the spec. |
| **[RESUME_DELTA_FORENSICS.md](docs/learnings/RESUME_DELTA_FORENSICS.md)** | Evaluates tailoring depth by analyzing changed keywords and token changes between original and compiled resumes. Quantifies how much the Council actually changes. | Assessing Council effectiveness, tuning tailoring aggressiveness. |
| **[S3_S7_ROOT_CAUSE_AUDIT.md](docs/learnings/S3_S7_ROOT_CAUSE_AUDIT.md)** | Root-cause analysis of early S3 (Company Intelligence) and S7 (Surgical Rewrites) failures. | Debugging S3 or S7 issues that resemble early failure patterns. |
| **[RENDERING_SIMPLIFICATION_AUDIT.md](docs/learnings/RENDERING_SIMPLIFICATION_AUDIT.md)** | Deep review of template normalization: PDF-preamble handling, Markdown table flattening, structure preservation. | Modifying rendering templates or normalizers. |
| **[REGRESSION_QA_REPORT.md](docs/learnings/REGRESSION_QA_REPORT.md)** | Results of end-to-end compiler runs against test fixtures (Hayagreev, Varsha), recording success rates and failure cases. | Verifying that changes don't break known-good outputs. |
| **[FUNCTIONAL_STABILIZATION_REPORT.md](docs/learnings/FUNCTIONAL_STABILIZATION_REPORT.md)** | Narrative log of the structural stabilization pass: TruthGuard repair, Windows-1252 garble fixes, validator hardening. | Understanding the stabilization history and what was patched. |
| **[DISCOVERY_PIPELINE_STATUS_20260518.md](docs/learnings/DISCOVERY_PIPELINE_STATUS_20260518.md)** | Status log tracking discovery bugs: Lever slug bugs, sector filters, SpireAI integration issues. | Debugging discovery pipeline problems. |
| **[PROMPT_AUDIT.md](docs/learnings/PROMPT_AUDIT.md)** | Massive 74KB analysis auditing the exact system prompts across all LLM nodes. | Changing any LLM prompt. Know what the current prompts say first. |

### Dev Blog (`docs/learnings/dev-blog/`)

Daily chronicles documenting significant sessions and structural milestones:

| Entry | Date | Summary |
|-------|------|---------|
| **[2026-05-18-onboarding.md](docs/learnings/dev-blog/2026-05-18-onboarding.md)** | 2026-05-18 | Onboarding tasks, models.yml creation, and repository configuration |
| **[2026-05-19-resume-council-structural-stabilization.md](docs/learnings/dev-blog/2026-05-19-resume-council-structural-stabilization.md)** | 2026-05-19 | Preprocessing, S7 loop stabilization, normalizer overrides |
| **[2026-05-20-deep-delta-humanizer-renderer-fixes.md](docs/learnings/dev-blog/2026-05-20-deep-delta-humanizer-renderer-fixes.md)** | 2026-05-20 | Humanizer assertiveness adjustments, subtitle parsing fixes |
| **[2026-05-23-delivery-orchestration-scaffold.md](docs/learnings/dev-blog/2026-05-23-delivery-orchestration-scaffold.md)** | 2026-05-23 | LangGraph Supervisor, transport, checkpointer, and assisted apply scaffold reconciliation |

New dev-blog entries are created by the `careerloop-product-lead` skill for significant sessions using the format `YYYY-MM-DD-{slug}.md`.

| Document | Purpose |
|----------|---------|
| **[README.md](docs/learnings/README.md)** | Subdirectory index for the learnings directory. |

---

## 🔗 Quick Reference — Key Fast-Access Assets

| # | Document | Category | Why Read |
|---|----------|----------|----------|
| 1 | [PRD.md](docs/product/PRD.md) | Product | Canonical product vision — source of truth for all engineering |
| 2 | [ROI_UX_PRODUCT_VISION.md](docs/product/ROI_UX_PRODUCT_VISION.md) | Product | ROI thesis, UX philosophy, metrics, prioritization framework |
| 3 | [CANONICAL_ARCHITECTURE.md](docs/engineering/CANONICAL_ARCHITECTURE.md) | Engineering | Locked 8-system Resume Council architecture |
| 4 | [TRACKER.md](docs/tech-backlog/TRACKER.md) | Tech Backlog | Live sprint status, system completion %, open blockers |
| 5 | [FUCKUPS.md](docs/learnings/FUCKUPS.md) | Learnings | Past mistakes and prevention strategies |

---

> [!NOTE]
> All active custom skills in `.agents/skills/`, `.claude/skills/`, and `.gemini/` are synchronized with this taxonomy. The `careerloop-product-lead` skill reads from and writes to multiple documents across these directories each session.
