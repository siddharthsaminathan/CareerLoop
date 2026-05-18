# CareerLoop Resume Council v3.0 — Technical Architecture (Deep Dive)

## 1. Executive Summary
Resume Council v3.0 is a **LangGraph-driven multi-agent orchestration system** designed to transform a static Master CV into a job-specific, humanized application pack. Unlike v1/v2 which relied on generative "full-file" hallucinations, v3.0 uses a **Surgical Compiler** architecture that preserves original metadata (links, structure) while rewriting content based on grounded "User Truth" and "Cope-Killer" humanization.

---

## 2. Core Modules & Data Flow

### A. The Input Layer
- **Master Profile (`cv.md`):** The ground truth. Markdown format containing full history and links.
- **User Config (`profile.yml`):** Internal search preferences and deal-breakers.
- **Target JD:** Scraped or manually provided job description.
- **System Date:** Injected dynamically (e.g., `May 2026`) to lock seniority calculations.

### B. The Intelligence Phase (Stages 1-5)
1. **S1: Company Intelligence:** Decodes the company's real status (funding, scale, culture) and identifies "Hidden Expectations" (e.g., "they say AI, but they mean internal BI").
2. **S2: Role Decode:** Translates the JD into "Must-Have" vs. "Nice-to-Have" signals and defines "Day 1 Deliverables."
3. **S3: User Truth Check:** **[CRITICAL]** The Auditor. It calculates total years of experience (e.g., 6.7 years) and maps evidence from the CV to the JD. It sets the `seniority_lock`.
4. **S4: Fit/Gap Analysis:** A cold-blooded hire/no-hire assessment. Assigns scores (0-100) and identifies recruiter objections.
5. **S5: Positioning Strategy:** Defines the "Narrative Thread." Decides if the candidate is a "Specialist," "Generalist," or "Founder-Type" for this specific role.

### C. The Execution Phase (Stages 6-8)
6. **S6: Resume Plan:** A bullet-by-bullet list of *what* to change. No writing happens here, only planning.
7. **S7: Section Writers:** The "Engineers." They execute the S6 plan. They are prompted to **preserve all Markdown URLs**.
8. **S8: Truth Guard:** **[THE GATEKEEPER]** Compares S7's output back against S3's "User Truth." 
   - *Failure Logic:* If S7 tries to "cope" (e.g., claiming Shopify experience when none exists), S8 flags `passed: false` and provides a `revision` block with the grounded truth.

### D. The Humanizer & Assembly Phase (Stages 9-12)
9. **S9: Cope-Killer Humanizer:** The "Editor." It takes the Truth Guard's corrected text and strips out AI-slop ("leveraged", "passionate") and defensive "cope" language. It applies this to the **Full Pack** (CV, Cover Note, DMs).
10. **S10: HR Reader:** A 10-second scan simulation to verify if the rewritten CV passes the "first impression" test.
11. **S11: Surgical Assembler:** **[NON-LLM NODE]** A Python module using Regex to swap sections of the original `cv.md` with the S9 humanized text. This prevents "Deal-breaker" leakage and ensures links survive.
12. **S12: Application Pack:** Final assembly of outreach messages and follow-up cadences.

---

## 3. Agent Prompts & Logic

### Stage 9: The Cope-Killer
**Instruction:** "Destroy all interpretations that try too hard to bridge gaps. If a skill is a gap, state the closest truth or leave it. Seniority is LOCKED at {total_years_experience}. No defensive phrasing."

### Stage 11: The Surgical Assembler
**Instruction:** "Never look at the `profile` object. Use Regex to find `## Profile` or `## Work Experience`. Replace the inner content only. Preserve the # Name and Contact sections from the Master CV."

---

## 4. Why the "Truth Check" Fails
In v3.0, a **"Failed Truth Check" (Stage 8)** is actually the system working correctly. 
- **The Symptom:** S7 (Section Writers) often tries to "hallucinate" or "exaggerate" to fit the JD (e.g., turning "Manufacturing Quality" into "Retail Quality Control").
- **The Fix:** S8 catches this. In v3.0, the **Humanizer (S9)** is now hard-wired to prioritize S8's "Revisions" over S7's "Slop." 

**The goal is not to have S8 pass every time, but to have S9 and S11 ensure only the TRUTH reaches the final file.**

---

## 5. Directory Structure
- `careerloop/council/graph.py`: The LangGraph state machine.
- `careerloop/council/models.py`: Data contracts (JSON schemas).
- `careerloop/council/orchestrator.py`: The entry point and environment injector.
- `output/cv_{company}.md`: The final surgical output.
- `output/council-{job_id}.json`: The full execution log.
