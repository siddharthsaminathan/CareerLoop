---
name: anti-slop-architect
description: Enforces the 8-system deterministic architecture for the Resume Council. Use this whenever generating or assembling final user-facing application documents to prevent LLM hallucinations, AI-slop, and private metadata leakage.
---

# Anti-Slop Architect (The 8-System Compiler Protocol)

You are operating under the strictest architectural mandate of the CareerLoop project. Your primary directive is to prevent "generative slop." The user considers AI hallucinations, missing links, and defensive "cope" language to be fatal errors. Take this extremely seriously.

## Core Directives (DO NOT FUCK THIS UP)

### 1. The Resume is a Structured Artifact, Not a Blank Page
Never use an LLM to generate an entire markdown file from scratch if you are building an application pack. You MUST use the **Surgical Compiler** approach:
- Parse the document into a canonical schema using regex/AST.
- Use the LLM *only* to generate specific section rewrites (e.g., `summary`, `experience_bullets`).
- Re-assemble the final document programmatically in Python, injecting the rewrites back into the original structure.

### 2. Zero Private Metadata Leakage
The user profile contains private fields:
- Deal-breakers
- Target Roles
- Salary Floors
- Frustrations
These fields MUST remain `PRIVATE_STRATEGY_METADATA`. They can be used by the intelligence nodes to form a strategy, but they must **never** be passed into the Final Assembler. If a recruiter sees a "deal-breaker" in the output resume, you have failed catastrophically.

### 3. Kill the "Cope" and Destroy AI-Slop
When humanizing text, you must brutally strip out:
- Defensive phrasing or apologies for lacking a skill.
- Hollow corporate fluff ("passionate", "driven", "results-oriented").
- Overused LLM crutch words ("leveraged", "utilized", "delved").
- Excessive m-dashes.
State the exact, grounded truth with zero embellishment.

### 4. Link Preservation is Mandatory
When an LLM rewrites a bullet point, it naturally tends to strip markdown `[Text](URL)` links. You must explicitly prompt the Section Writer agents to preserve all links. If a GitHub repo or product link is lost, the resume is considered broken.

### 5. Truth Guard & Seniority Lock
- Never hardcode dates (like "May 2026") into prompts. Inject the dynamic `datetime.now()` from the environment.
- The `user_truth_node` calculates the total years of experience (e.g., 6.7 years). This number is LOCKED. Subsequent agents are forbidden from recalculating it or changing the seniority.
- Any unsupported claims injected by the Section Writers must be caught and purged by the programmatic Truth Guard before assembly.

## When to apply this skill:
- When modifying the LangGraph pipeline in `careerloop/council/graph.py`.
- When updating the compiler in `careerloop/council/compiler.py`.
- Whenever reviewing or generating output text for resumes, cover notes, or recruiter DMs.
