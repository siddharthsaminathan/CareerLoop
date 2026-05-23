# CareerLoop Learnings Directory

This directory acts as our engineering memory. It stores detailed retrospectives on bugs, codebase audits, delta metric evaluations proving tailoring depths, regression reports, and a day-by-day developer blog.

## File Registry

### 📄 [FUCKUPS.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/FUCKUPS.md)
* **Purpose:** A compilation of honest mistakes made during development, their underlying root causes, and explicit strategies implemented to prevent them from recurring. **Crucial reading to prevent regressions.**

### 📄 [CAREERLOOP_REUSE_AUDIT.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/CAREERLOOP_REUSE_AUDIT.md)
* **Purpose:** A deep audit of 15 capabilities, exploring standard skill structures, reuse probability, and platform dependencies.

### 📄 [CAREERLOOP_COUNCIL_AUDIT.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/CAREERLOOP_COUNCIL_AUDIT.md)
* **Purpose:** Initial audit pinpointing failure vectors in the S7 rewriting node (collapsed bullets, JSON parsing).

### 📄 [CAREERLOOP_MASTER_VISION_AMENDMENTS.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/CAREERLOOP_MASTER_VISION_AMENDMENTS.md)
* **Purpose:** Log of amendments expanding Section 5 (Employer Discovery) and Section 19 (Referral/Outreach Path).

### 📄 [20_PART_ARCHITECTURAL_AUDIT.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/20_PART_ARCHITECTURAL_AUDIT.md)
* **Purpose:** Exhaustive 20-part analysis contrasting theoretical Resume Council specs with live repository implementations.

### 📄 [RESUME_DELTA_FORENSICS.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/RESUME_DELTA_FORENSICS.md)
* **Purpose:** Evaluates tailoring depth by analyzing changed keywords and token changes between original and compiled resumes.

### 📄 [S3_S7_ROOT_CAUSE_AUDIT.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/S3_S7_ROOT_CAUSE_AUDIT.md)
* **Purpose:** Root-cause analysis of early S3 (Company Intelligence) and S7 (Surgical rewrites) failures.

### 📄 [RENDERING_SIMPLIFICATION_AUDIT.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/RENDERING_SIMPLIFICATION_AUDIT.md)
* **Purpose:** Deep review of standard template normalizations (PDF-preamble handling, Markdown table flattening).

### 📄 [REGRESSION_QA_REPORT.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/REGRESSION_QA_REPORT.md)
* **Purpose:** Results of E2E compiler runs against test fixtures (Hayagreev, Varsha), recording success rates.

### 📄 [FUNCTIONAL_STABILIZATION_REPORT.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/FUNCTIONAL_STABILIZATION_REPORT.md)
* **Purpose:** Narrative log chronicling the structural stabilization pass (TruthGuard repair, Windows-1252 garble fixes).

### 📄 [DISCOVERY_PIPELINE_STATUS_20260518.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/DISCOVERY_PIPELINE_STATUS_20260518.md)
* **Purpose:** Status log tracking discovery bugs (Lever slug bugs, sector filters, SpireAI integration).

### 📄 [PROMPT_AUDIT.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/PROMPT_AUDIT.md)
* **Purpose:** Massive 74KB analysis auditing the exact system prompts across all LLM nodes.

### 📂 [dev-blog/](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/dev-blog/)
* **Purpose:** Programmatic chronicles documenting daily sprints and structural milestones:
  * **[2026-05-18-onboarding.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/dev-blog/2026-05-18-onboarding.md):** Onboarding tasks, models yml creation, and repository configuration.
  * **[2026-05-19-resume-council-structural-stabilization.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/dev-blog/2026-05-19-resume-council-structural-stabilization.md):** Preprocessing, S7 loop stabilization, normalizer overrides.
  * **[2026-05-20-deep-delta-humanizer-renderer-fixes.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/dev-blog/2026-05-20-deep-delta-humanizer-renderer-fixes.md):** Humanizer assertiveness adjustments, subtitle parsing.
  * **[2026-05-23-delivery-orchestration-scaffold.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/dev-blog/2026-05-23-delivery-orchestration-scaffold.md):** Delivery orchestration scaffold reconciliation: supervisor graph, transports, PostgresSaver, and assisted apply guardrails.

---
> [!TIP]
> Before modifying key parsers or re-architecting prompts, review the retrospectives in **[FUCKUPS.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/learnings/FUCKUPS.md)** to prevent duplicating past architectural mistakes.
