"""LangGraph Resume Council — 7-stage state machine with real LLM calls."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict


# ─── State ────────────────────────────────────────────────────────────────────

class CouncilState(TypedDict):
    # Inputs
    job_id: str
    intent: str
    job_title: str
    company: str
    job_url: str
    jd_text: str
    cv_text: str
    profile: dict

    # Stage outputs
    company_intelligence: Optional[dict]
    role_decode: Optional[dict]
    user_truth: Optional[dict]
    fit_gap: Optional[dict]
    positioning: Optional[dict]
    resume_plan: Optional[dict]
    application_pack: Optional[dict]

    errors: list


# ─── LLM client ───────────────────────────────────────────────────────────────

def _llm(temperature: float = 0.2) -> ChatOpenAI:
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        temperature=temperature,
        max_tokens=3000,
    )


def _call(system: str, user: str, temperature: float = 0.2) -> dict:
    """Call DeepSeek and parse JSON response, stripping markdown fences if present."""
    resp = _llm(temperature).invoke([
        SystemMessage(content=system),
        HumanMessage(content=user),
    ])
    raw = resp.content.strip()

    # Strip ```json ... ``` or ``` ... ``` fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        inner = []
        inside = False
        for line in lines:
            if line.startswith("```") and not inside:
                inside = True
                continue
            if line.startswith("```") and inside:
                break
            if inside:
                inner.append(line)
        raw = "\n".join(inner)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


# ─── Stage 1: Company Intelligence ────────────────────────────────────────────

_S1_SYSTEM = """\
You are a senior tech recruiter and company intelligence analyst.
Given a company name and job description, produce a structured intelligence brief.
Output ONLY valid JSON, no markdown fences, no explanation outside the JSON.

Required JSON schema:
{
  "verdict": "one-line TL;DR of what this company is actually looking for",
  "company_snapshot": "2-3 sentences: what the company does, stage, size",
  "hiring_context": "why they are likely hiring now and what problem this role solves",
  "screening_filters": ["hard filters recruiters will screen on first pass"],
  "culture_signals": ["3-5 signals about team culture from the JD language"],
  "red_flags": ["any red flags, vague language, or warning signs in the JD"],
  "what_they_actually_want": "the real person they want, beyond the JD boilerplate"
}"""


def company_intelligence_node(state: CouncilState) -> CouncilState:
    print("\n--- Stage 1/7: Company Intelligence ---")
    result = _call(_S1_SYSTEM, f"Company: {state['company']}\n\nJD:\n{state['jd_text']}")
    print(f"  → {result.get('verdict', result.get('raw', ''))[:120]}")
    return {**state, "company_intelligence": result}


# ─── Stage 2: Role Decode ──────────────────────────────────────────────────────

_S2_SYSTEM = """\
You are a senior AI hiring manager who decodes job descriptions precisely.
Separate what the role ACTUALLY requires from JD boilerplate.
Output ONLY valid JSON, no markdown fences.

Required JSON schema:
{
  "verdict": "one-line summary of what this role really is",
  "actual_seniority": "real seniority based on responsibilities, not title",
  "must_have_skills": ["hard requirements — no-hire if missing"],
  "nice_to_have_skills": ["preferred but not blockers"],
  "hidden_expectations": ["things implied but never stated explicitly in the JD"],
  "day_1_deliverables": ["what this person is expected to do in first 30-90 days"],
  "red_line_requirements": ["anything that immediately disqualifies a candidate"],
  "stack_reality": "the actual tech stack this person will use daily",
  "stakeholder_load": "who this person interfaces with and how much",
  "growth_path": "likely career trajectory from this role"
}"""


def role_decode_node(state: CouncilState) -> CouncilState:
    print("\n--- Stage 2/7: Role Decode ---")
    result = _call(_S2_SYSTEM, (
        f"Job Title: {state['job_title']}\n"
        f"Company: {state['company']}\n\n"
        f"Company Intel:\n{json.dumps(state['company_intelligence'], indent=2)}\n\n"
        f"JD:\n{state['jd_text']}"
    ))
    print(f"  → {result.get('verdict', result.get('raw', ''))[:120]}")
    return {**state, "role_decode": result}


# ─── Stage 3: User Truth ───────────────────────────────────────────────────────

_S3_SYSTEM = """\
You are a rigorous career coach and resume auditor.
Map which candidate claims are provable from their CV, which are weak, and what is missing.
Be honest and evidence-based — do not inflate or deflate.
Output ONLY valid JSON, no markdown fences.

Required JSON schema:
{
  "verdict": "one-line honest assessment of candidate fit for this role",
  "confirmed_skills": [
    {"skill": "name", "evidence": "specific proof from CV", "strength": "strong|medium"}
  ],
  "weak_claims": [
    {"skill": "name", "issue": "why weak or unproven", "fix": "how to strengthen"}
  ],
  "gaps": [
    {"requirement": "what JD wants", "gap_severity": "dealbreaker|important|minor", "mitigation": "how to address"}
  ],
  "standout_assets": ["things genuinely rare or impressive about this candidate"],
  "honest_fit_score": 0,
  "honest_summary": "2-3 sentences: strengths, weak spots, bottom line"
}"""


def user_truth_node(state: CouncilState) -> CouncilState:
    print("\n--- Stage 3/7: User Truth Check ---")
    result = _call(_S3_SYSTEM, (
        f"CANDIDATE CV:\n{state['cv_text']}\n\n"
        f"ROLE REQUIREMENTS (decoded):\n{json.dumps(state['role_decode'], indent=2)}\n\n"
        "Map the candidate's skills against these requirements with specific evidence from the CV."
    ))
    print(f"  → {result.get('verdict', result.get('raw', ''))[:120]}")
    return {**state, "user_truth": result}


# ─── Stage 4: Fit / Gap Analysis ──────────────────────────────────────────────

_S4_SYSTEM = """\
You are a senior talent acquisition lead making a hire/no-hire recommendation.
Given truth-checked candidate data, produce a final fit/gap analysis.
Output ONLY valid JSON, no markdown fences.

Required JSON schema:
{
  "verdict": "APPLY | APPLY_WITH_CAUTION | STRETCH | SKIP — plus one-line reason",
  "overall_fit_score": 0,
  "fit_breakdown": {
    "technical_fit": 0,
    "experience_fit": 0,
    "seniority_fit": 0,
    "culture_fit": 0
  },
  "top_strengths": ["3-4 things that make this candidate genuinely competitive here"],
  "recruiter_objections": ["exact objections a recruiter or hiring manager will raise"],
  "objection_responses": {"objection text": "pre-emptive response to weave into application"},
  "application_stance": "how aggressive or conservative to pitch",
  "application_risk": "low|medium|high"
}"""


def fit_gap_node(state: CouncilState) -> CouncilState:
    print("\n--- Stage 4/7: Fit / Gap Analysis ---")
    result = _call(_S4_SYSTEM, (
        f"COMPANY INTEL:\n{json.dumps(state['company_intelligence'], indent=2)}\n\n"
        f"ROLE DECODE:\n{json.dumps(state['role_decode'], indent=2)}\n\n"
        f"USER TRUTH:\n{json.dumps(state['user_truth'], indent=2)}\n\n"
        "Produce final fit analysis and application recommendation."
    ))
    print(f"  → {result.get('verdict', result.get('raw', ''))[:120]}")
    return {**state, "fit_gap": result}


# ─── Stage 5: Positioning Strategy ────────────────────────────────────────────

_S5_SYSTEM = """\
You are a senior executive recruiter and personal branding strategist.
Craft a precise positioning strategy for THIS candidate at THIS company.
Output ONLY valid JSON, no markdown fences.

Required JSON schema:
{
  "verdict": "the single most powerful angle for this candidate at this company",
  "positioning_angle": "who this candidate IS for this role — one sentence",
  "lead_story": "the one project or achievement from their CV to lead with, and why",
  "headline_rewrite": "rewritten resume headline optimised for this role",
  "tone": "aggressive|confident|balanced|conservative",
  "company_specific_hook": "something specific about this company that connects to candidate experience",
  "keywords_to_weave_in": ["JD keywords that should appear naturally in resume and cover letter"],
  "what_NOT_to_lead_with": ["things that would hurt this application — de-emphasise these"],
  "narrative_thread": "2-3 sentence story arc that should run through the whole application"
}"""


def positioning_node(state: CouncilState) -> CouncilState:
    print("\n--- Stage 5/7: Positioning Strategy ---")
    profile = state["profile"]
    candidate = profile.get("candidate", {})
    narrative = profile.get("narrative", {})
    result = _call(_S5_SYSTEM, (
        f"CANDIDATE CV:\n{state['cv_text']}\n\n"
        f"Name: {candidate.get('full_name', 'Siddharth Saminathan')}\n"
        f"Current headline: {narrative.get('headline', '')}\n\n"
        f"FIT/GAP:\n{json.dumps(state['fit_gap'], indent=2)}\n\n"
        f"COMPANY INTEL:\n{json.dumps(state['company_intelligence'], indent=2)}\n\n"
        "Craft the positioning strategy."
    ), temperature=0.3)
    print(f"  → {result.get('verdict', result.get('raw', ''))[:120]}")
    return {**state, "positioning": result}


# ─── Stage 6: Resume Plan ──────────────────────────────────────────────────────

_S6_SYSTEM = """\
You are a senior resume writer specialising in AI/ML engineering roles.
Produce a precise, specific resume editing plan. Reference actual bullets from the CV.
Do NOT invent experience. Only propose changes that are truthful.
Output ONLY valid JSON, no markdown fences.

Required JSON schema:
{
  "verdict": "what changes will have the highest impact for this application",
  "headline_change": {"current": "...", "proposed": "...", "reason": "..."},
  "summary_rewrite": "rewritten professional summary (3-4 sentences) for this role",
  "bullets_to_rewrite": [
    {"job": "job title", "original": "original bullet text", "rewritten": "improved bullet", "reason": "why"}
  ],
  "bullets_to_promote": ["bullets already strong that should be placed higher or first"],
  "skills_to_add": ["skills to add to skills section — must be provable from CV"],
  "skills_to_remove": ["skills to remove or de-emphasise for this application"],
  "risky_claims": ["claims that need softening or supporting evidence before including"],
  "ats_keywords_missing": ["JD keywords not yet in resume that can be added truthfully"]
}"""


def resume_plan_node(state: CouncilState) -> CouncilState:
    print("\n--- Stage 6/7: Resume Plan ---")
    result = _call(_S6_SYSTEM, (
        f"CURRENT CV:\n{state['cv_text']}\n\n"
        f"POSITIONING STRATEGY:\n{json.dumps(state['positioning'], indent=2)}\n\n"
        f"USER TRUTH:\n{json.dumps(state['user_truth'], indent=2)}\n\n"
        f"TARGET: {state['job_title']} at {state['company']}\n\n"
        "Produce a specific, actionable resume editing plan using only real CV content."
    ))
    print(f"  → {result.get('verdict', result.get('raw', ''))[:120]}")
    return {**state, "resume_plan": result}


# ─── Stage 7: Application Pack ─────────────────────────────────────────────────

_S7_SYSTEM = """\
You are a senior career strategist assembling a final application pack.
This pack is for candidate REVIEW — they decide whether to send it.
Be specific to this candidate and this role. No generic templates.
Output ONLY valid JSON, no markdown fences.

Required JSON schema:
{
  "verdict": "quality score and recommendation — is this application competitive?",
  "cover_note": "3-paragraph cover letter, specific to candidate and role, professional not generic",
  "recruiter_message": "150-word LinkedIn or email outreach to a recruiter at this company",
  "follow_up_message": "follow-up to send 5-7 days after applying",
  "application_quality_score": 0,
  "competitiveness_assessment": "honest 2-3 sentence assessment vs other applicants",
  "final_warnings": ["last-minute things to double-check before applying"],
  "green_lights": ["things that genuinely work in candidate favour for this specific role"]
}"""


def application_pack_node(state: CouncilState) -> CouncilState:
    print("\n--- Stage 7/7: Application Pack ---")
    profile = state["profile"]
    candidate = profile.get("candidate", {})
    result = _call(_S7_SYSTEM, (
        f"CANDIDATE: {candidate.get('full_name', 'Siddharth Saminathan')}\n"
        f"ROLE: {state['job_title']} at {state['company']}\n"
        f"URL: {state['job_url']}\n\n"
        f"POSITIONING:\n{json.dumps(state['positioning'], indent=2)}\n\n"
        f"RESUME PLAN:\n{json.dumps(state['resume_plan'], indent=2)}\n\n"
        f"FIT/GAP:\n{json.dumps(state['fit_gap'], indent=2)}\n\n"
        f"COMPANY INTEL:\n{json.dumps(state['company_intelligence'], indent=2)}\n\n"
        "Produce the final application pack."
    ), temperature=0.4)
    print(f"  → {result.get('verdict', result.get('raw', ''))[:120]}")
    return {**state, "application_pack": result}


# ─── Build & Compile Graph ─────────────────────────────────────────────────────

def build_council_graph():
    g = StateGraph(CouncilState)

    g.add_node("company_intelligence", company_intelligence_node)
    g.add_node("role_decode", role_decode_node)
    g.add_node("user_truth", user_truth_node)
    g.add_node("fit_gap", fit_gap_node)
    g.add_node("positioning", positioning_node)
    g.add_node("resume_plan", resume_plan_node)
    g.add_node("application_pack", application_pack_node)

    g.set_entry_point("company_intelligence")
    g.add_edge("company_intelligence", "role_decode")
    g.add_edge("role_decode", "user_truth")
    g.add_edge("user_truth", "fit_gap")
    g.add_edge("fit_gap", "positioning")
    g.add_edge("positioning", "resume_plan")
    g.add_edge("resume_plan", "application_pack")
    g.add_edge("application_pack", END)

    return g.compile()


_GRAPH = None


def get_council_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_council_graph()
    return _GRAPH
