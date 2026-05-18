# Resume Council v3.0: The 8-System Application Compiler

## 1. Why Resume Council Exists
Resume Council is the intelligence layer that bridges the gap between a candidate's "Master CV" and a specific "Job Opportunity." Its purpose is to surgically adapt a professional identity to resonate with a specific company's needs without compromising the candidate's truth, seniority, or privacy. It transforms a generic application into a high-signal, high-alignment "Application Pack."

## 2. Why Single-Pass LLM Generation Fails
Current "generative" approaches (v1/v2) treat the resume like a blank page for an LLM to write. This fails for several reasons:
- **Structural Decay:** LLMs often lose markdown formatting, links, and specific section headers.
- **Privacy Leakage:** Internal search preferences (e.g., "deal-breakers," "salary floor") often leak into the final document.
- **Hallucination:** Without a "Truth Guard," agents frequently "bridge gaps" by inventing experience.
- **Inconsistency:** Seniority calculations and tone fluctuate across different parts of the document.
- **Untestability:** A single giant prompt is a "black box" that cannot be unit-tested for specific failures.

## 3. The 8 Systems Architecture

### System 1: Document Parser + Canonical Schema
**Purpose:** Converts any master resume (Markdown/Text) into a structured `canonical_resume.json`.
- **Inputs:** Raw Master CV.
- **Outputs:** `canonical_resume.json` (sections, titles, types, visibility classes).
- **Failure Prevented:** Silent dropping of custom sections or misclassification of content.

### System 2: Document Preservation + Structure Contract
**Purpose:** Sets a "lock" on what cannot be changed.
- **Inputs:** Canonical Resume + User Profile.
- **Outputs:** `preservation_contract.json` (required sections, link preservation rules, ordering).
- **Failure Prevented:** Deletion of education, loss of portfolio links, or inclusion of private metadata.

### System 3: Company Intelligence System (Lazy-Loaded)
**Purpose:** Provides strategic context for the target company.
- **Inputs:** Job Description + Company Name.
- **Outputs:** `company_intelligence.json` (business model, hiring urgency, culture signals).
- **Failure Prevented:** "Tone-deaf" applications that miss the company's real pain points.

### System 4: Role Decoder System
**Purpose:** Extracts the "Hidden JD" (what they *actually* want).
- **Inputs:** JD + Company Intelligence.
- **Outputs:** `role_decode.json` (must-haves, nice-to-haves, day-one deliverables).
- **Failure Prevented:** Over-indexing on generic JD fluff while missing core technical requirements.

### System 5: User Truth System
**Purpose:** Maps candidate evidence to role requirements.
- **Inputs:** Canonical Resume + Profile + Memory.
- **Outputs:** `user_truth.json` (confirmed skills, evidence bank, seniority lock).
- **Failure Prevented:** Seniority miscalculation (e.g., 6.7 yrs vs 2 yrs) and unsupported skill claims.

### System 6: Positioning Strategy System
**Purpose:** Defines the "Narrative Angle" for the application.
- **Inputs:** Role Decode + User Truth + Company Intel.
- **Outputs:** `positioning_strategy.json` (narrative thread, stance: PUSH/STRETCH/SKIP).
- **Failure Prevented:** Incoherent messaging or applying for roles with dangerous gaps.

### System 7: Section Rewrite System
**Purpose:** Surgically rewrites only the approved sections.
- **Inputs:** Canonical Resume + Contract + Positioning.
- **Outputs:** `section_rewrites.json` (original vs. rewritten text, change reasons).
- **Failure Prevented:** "Full-page" hallucinations; ensures only the Summary/Experience/Skills are touched.

### System 8: Truth Guard + Humanizer + Safe Assembler
**Purpose:** The final gatekeeper and deterministic compiler.
- **Inputs:** Rewritten Sections + Canonical Structure + Contract.
- **Outputs:** `final_application_pack/` (CV, Cover Note, Quality Report).
- **Failure Prevented:** AI-slop, "cope" language, and metadata leakage.

## 4. Separation of Private vs. Public Content
- **Private Metadata:** (Deal-breakers, salary, search preferences) is classified as `PRIVATE_STRATEGY_METADATA` in System 1. It is used as *input* for reasoning in Systems 3-6 but is **explicitly filtered out** of the `preservation_contract` and the `Safe Assembler`.
- **Public Content:** (Experience, Education, Links) is classified as `PUBLIC_APPLICATION_CONTENT`.

## 5. Failure Modes & Test Requirements
- **Leakage Test:** Assert that no string from `PRIVATE_STRATEGY_METADATA` appears in `final_resume.md`.
- **Preservation Test:** Assert that every `required` section in the contract exists in the final output.
- **Link Test:** Assert that all `[Text](URL)` patterns from the Master CV survive.
- **Truth Test:** Assert that no "unconfirmed" skills from System 5 appear as "Expert" in System 7.

## 6. What "Done" Means
The system is "Done" when:
1. It passes all 3 fixture resumes (Experienced, Fresher, Non-Technical).
2. It produces a `quality_report.md` explaining exactly what was changed and why.
3. It assembles the final document deterministically (Python-based regex/merging, not LLM generation).
4. No private metadata survives the compiler pass.
