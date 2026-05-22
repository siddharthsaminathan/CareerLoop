"""
S8.5 — Section Completeness Check

Runs after normalization, before rendering.

For each section that is EMPTY in the NormalizedResume:
  1. Ask LLM: "Is this section needed for this person/role?"
  2. If yes: "What should it contain, extracted ONLY from the original CV?"
  3. Populate or leave empty (renderer will skip empty sections).

This prevents two failure modes:
  A) Empty section headers rendering in HTML (Key Achievements with nothing inside)
  B) Missed content that exists in the CV but wasn't surfaced in the right section

Only checks sections that COULD be populated from the CV:
  - achievements (often buried in education/experience bullets)
  - projects (often part of experience or side-work)

Does NOT generate invented content. Every item returned must be grounded in
the original CV text.
"""

import json
from dataclasses import dataclass
from typing import Optional

from careerloop.rendering.resume_model import NormalizedResume


# ─── LLM call helper (matches graph.py pattern) ───────────────────────────────

def _call_llm(system: str, prompt: str, label: str) -> Optional[dict]:
    """Call DeepSeek via CouncilLLMClient. Returns parsed JSON or None on failure."""
    try:
        from careerloop.council.llm import CouncilLLMClient
        client = CouncilLLMClient(model_kind="writer")
        return client.complete_json(system_prompt=system, user_prompt=prompt, max_tokens=2000)
    except Exception as e:
        print(f"  !! Section completeness LLM error [{label}]: {e}")
        return None


# ─── System prompt ────────────────────────────────────────────────────────────

_COMPLETENESS_SYSTEM = """You are a resume quality auditor. Given:
- A list of EMPTY sections in a normalized resume
- The original CV text
- The target role and company

Your job: for each empty section, decide if it should be populated or suppressed.

RULES:
1. Only extract content that EXISTS in the original CV. Never invent.
2. Achievements buried in education bullets (awards, funding won, top rankings)
   and in experience bullets (0→451 users, secured ₹1L from IIT Madras) count.
3. If a section is genuinely not needed (content already covered elsewhere, or
   the person simply has nothing notable for it), set needed=false.
4. Be specific — use exact figures, names, and outcomes from the CV.
5. For achievements: 2-4 items max. Lead with the most impressive.
6. For projects: only include if they are distinct from experience entries.

Return ONLY a JSON object:
{
  "sections": [
    {
      "section_id": "achievements",
      "needed": true,
      "reason": "3 notable achievements buried in education + experience",
      "content": [
        "Achievement bullet 1 — specific, grounded in CV",
        "Achievement bullet 2"
      ]
    },
    {
      "section_id": "projects",
      "needed": false,
      "reason": "Projects are already covered under the Emote experience entry"
    }
  ]
}
"""


# ─── Main function ─────────────────────────────────────────────────────────────

@dataclass
class CompletenessAction:
    section_id: str
    decision: str          # "populated" | "suppressed"
    reason: str
    items_added: int = 0


def check_and_complete_sections(
    resume: NormalizedResume,
    original_cv_text: str,
    role: str,
    company: str,
) -> tuple[NormalizedResume, list[CompletenessAction]]:
    """
    Check empty sections in NormalizedResume and either populate or suppress them.

    Returns:
        (updated_resume, list_of_actions_taken)

    Actions are logged for the quality report. The resume object is mutated
    in-place (achievements, projects populated or left empty).
    """
    actions: list[CompletenessAction] = []

    # Determine which sections are empty and worth checking
    sections_to_check = []
    if not resume.achievements:
        sections_to_check.append("achievements")
    if not resume.projects:
        sections_to_check.append("projects")

    if not sections_to_check:
        return resume, actions  # Nothing to do

    print(f"  → S8.5 Section Completeness: checking {sections_to_check}")

    # Build context: what's already in the resume (so LLM doesn't double-count)
    existing_summary = []
    if resume.experience:
        for exp in resume.experience:
            existing_summary.append(
                f"{exp.role} @ {exp.company}: {len(exp.bullets)} bullets"
            )
    if resume.education:
        existing_summary.append(f"Education: {len(resume.education)} entries")

    prompt = json.dumps({
        "empty_sections": sections_to_check,
        "role": role,
        "company": company,
        "existing_resume_summary": existing_summary,
        "original_cv": original_cv_text[:6000],  # cap to avoid token overflow
    }, ensure_ascii=False)

    result = _call_llm(_COMPLETENESS_SYSTEM, prompt, label="S8.5 section completeness")
    if not result or "sections" not in result:
        print("  !! S8.5 completeness check failed — skipping, sections stay empty")
        return resume, actions

    for section_result in result.get("sections", []):
        sid = section_result.get("section_id", "")
        needed = section_result.get("needed", False)
        reason = section_result.get("reason", "")
        content = section_result.get("content", [])

        if sid not in sections_to_check:
            continue

        if needed and content:
            if sid == "achievements":
                resume.achievements = [
                    item.strip()
                    for item in content
                    if item.strip()
                ]
                action = CompletenessAction(
                    section_id=sid,
                    decision="populated",
                    reason=reason,
                    items_added=len(resume.achievements),
                )
                print(f"  → S8.5 [POPULATED] achievements: {len(resume.achievements)} items extracted from CV")
            elif sid == "projects":
                # Projects: store as achievements for now
                # TODO: wire to ProjectEntry once model supports it
                resume.achievements = resume.achievements + [
                    item.strip()
                    for item in content
                    if item.strip()
                ]
                action = CompletenessAction(
                    section_id=sid,
                    decision="populated",
                    reason=reason,
                    items_added=len(content),
                )
                print(f"  → S8.5 [POPULATED] projects: {len(content)} items as achievements")
        else:
            action = CompletenessAction(
                section_id=sid,
                decision="suppressed",
                reason=reason,
            )
            print(f"  → S8.5 [SUPPRESSED] {sid}: {reason}")

        actions.append(action)

    return resume, actions
