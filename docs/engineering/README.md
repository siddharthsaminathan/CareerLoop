# CareerLoop Engineering Documentation Directory

This directory houses the technical specifications, locked system architectures, data models/schemas, AST template normalizers, and micro-system specifications for developers.

## File Registry

### 📄 [CANONICAL_ARCHITECTURE.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/engineering/CANONICAL_ARCHITECTURE.md)
* **Purpose:** The locked technical reference architecture for the 8-system Resume Council plus the Phase 0 delivery layer. Establishes programmatic data contracts, state variables, execution rules, transport boundaries, supervisor orchestration, and assisted-apply safety constraints.

### 📄 [MVP_SPRINT_PLAN.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/engineering/MVP_SPRINT_PLAN.md)
* **Purpose:** Delivery Foundation implementation plan: transport abstraction, conversational state, onboarding, daily brief, pack delivery, resume editor, follow-ups, Gmail/calendar, and interview memory.

### 📄 [breakdown-20-part.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/engineering/breakdown-20-part.md)
* **Purpose:** Detailed architectural breakdown covering the data flow from parsed plaintext CVs through LLM rewriting sections, up to post-render PDF generation.

### 📄 [resume-council-vision.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/engineering/resume-council-vision.md)
* **Purpose:** Initial technical draft outlining the 8 systems of the Resume Council (Truth Guard, Humanizer, Preprocessors, Normalizers).

### 📄 [MODELS.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/engineering/MODELS.md)
* **Purpose:** Master list of routing models (`deepseek-v4-pro` vs `deepseek-chat`) mapped per system node.

### 📄 [pipeline_graph.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/engineering/pipeline_graph.md)
* **Purpose:** Mermaid diagram visualizing the exact node flow inside the LangGraph orchestrator.

### 📂 [specs/](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/engineering/specs/)
* **Purpose:** Contains highly granular, programmatic engineering specs:
  * **[company-intel-design.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/engineering/specs/company-intel-design.md):** Target constraints, TTL-based caching, and web search integration for S3.
  * **[humanizer-design.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/engineering/specs/humanizer-design.md):** The 5-stage humanization pipeline (Markdown preserving, verb correction).
  * **[deepseek-tool-calling-audit.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/engineering/specs/deepseek-tool-calling-audit.md):** Functional analysis of structured output schemas.

---
> [!IMPORTANT]
> Any modifications targeting LangGraph nodes or schemas must conform strictly to the programmatic contracts in **[CANONICAL_ARCHITECTURE.md](file:///Users/siddharthsaminathan/Projects/CareerLoop/docs/engineering/CANONICAL_ARCHITECTURE.md)**.
