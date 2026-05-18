import json
import os
from datetime import datetime
from typing import Any, Optional, Dict, List
from typing_extensions import TypedDict

from langgraph.graph import END, StateGraph

from careerloop.council.llm import CouncilLLMClient
from careerloop.council.models import (
    CanonicalResume,
    ResumeSection,
    PreservationContract,
    CompanyIntelligence,
    RoleDecode,
    UserTruth,
    PositioningStrategy,
    SectionRewrites,
    SectionRewrite,
    ApplicationPack,
    QualityReport
)
from careerloop.council.compiler import ResumeCompiler

# ─── State ────────────────────────────────────────────────────────────────────

class CouncilState(TypedDict):
    # Inputs
    job_id: str
    person_id: str
    job_title: str
    company: str
    job_url: str
    jd_text: str
    master_cv: str
    profile: dict
    today: str

    # Artifacts (The 8 Systems)
    canonical_resume: Optional[Dict]
    preservation_contract: Optional[Dict]
    company_intelligence: Optional[Dict]
    role_decode: Optional[Dict]
    user_truth: Optional[Dict]
    positioning_strategy: Optional[Dict]
    section_rewrites: Optional[Dict]
    application_pack: Optional[Dict]

    errors: list


# ─── LLM client ───────────────────────────────────────────────────────────────

def _call(system: str, user: str, temperature: float = 0.2) -> dict:
    client = CouncilLLMClient("strategy")
    client.temperature = temperature
    try:
        return client.complete_json(system, user)
    except Exception as e:
        print(f"  !! LLM Call error: {e}")
        return {"error": str(e)}


# ─── System 1: Document Parser ───────────────────────────────────────────────

def parse_node(state: CouncilState) -> CouncilState:
    print("\n--- System 1: Document Parser ---")
    resume = ResumeCompiler.parse_markdown(state["master_cv"])
    return {**state, "canonical_resume": resume.to_dict()}


# ─── System 2: Preservation Contract ──────────────────────────────────────────

def contract_node(state: CouncilState) -> CouncilState:
    print("\n--- System 2: Preservation Contract ---")
    resume = CanonicalResume(**state["canonical_resume"])
    # Convert list of dicts to ResumeSection objects
    resume.sections = [ResumeSection(**s) for s in state["canonical_resume"]["sections"]]
    contract = ResumeCompiler.build_contract(resume, state["profile"])
    return {**state, "preservation_contract": contract.to_dict()}


# ─── System 3: Company Intelligence ───────────────────────────────────────────

_S3_SYSTEM = """You are a senior company researcher. Analyze the target company.
Do NOT invent facts. If unknown, say UNKNOWN.
Output ONLY valid JSON."""

def company_intelligence_node(state: CouncilState) -> CouncilState:
    print("\n--- System 3: Company Intelligence ---")
    prompt = f"Company: {state['company']}\nJD: {state['jd_text']}"
    result = _call(_S3_SYSTEM, prompt)
    return {**state, "company_intelligence": result}


# ─── System 4: Role Decoder ───────────────────────────────────────────────────

_S4_SYSTEM = """You are a master role decoder. Extract what the job actually wants.
Separate must-haves from nice-to-haves. Identify hidden expectations.
Output ONLY valid JSON.

Required JSON schema:
{
  "normalized_title": "...",
  "seniority": "...",
  "must_haves": ["..."],
  "nice_to_haves": ["..."],
  "hidden_expectations": ["..."],
  "day_one_deliverables": ["..."],
  "screening_keywords": ["..."],
  "disqualifiers": ["..."],
  "confidence": 0.9
}"""

def role_decode_node(state: CouncilState) -> CouncilState:
    print("\n--- System 4: Role Decoder ---")
    prompt = f"JD: {state['jd_text']}\nCompany Context: {json.dumps(state['company_intelligence'])}"
    result = _call(_S4_SYSTEM, prompt)
    if "error" in result:
        print(f"  → ERROR: {result['error']}")
    else:
        print(f"  → {result.get('normalized_title', '')} | {result.get('seniority', '')[:80]}")
    return {**state, "role_decode": result}


# ─── System 5: User Truth ─────────────────────────────────────────────────────

_S5_SYSTEM = """You are a rigorous auditor. Build a truthful evidence map.
Map candidate's experience to role requirements. Calculate seniority accurately.
Seniority is locked based on the earliest professional date in the resume.
Today is {today}.
Output ONLY valid JSON."""

def user_truth_node(state: CouncilState) -> CouncilState:
    print("\n--- System 5: User Truth ---")
    prompt = f"Resume: {json.dumps(state['canonical_resume'])}\nRole: {json.dumps(state['role_decode'])}"
    result = _call(_S5_SYSTEM.format(today=state["today"]), prompt)
    return {**state, "user_truth": result}


# ─── System 6: Positioning Strategy ───────────────────────────────────────────

_S6_SYSTEM = """You are a senior career strategist. Create the strategic narrative.
Do NOT rewrite the resume. Decide on the application stance and angle.
Output ONLY valid JSON."""

def positioning_node(state: CouncilState) -> CouncilState:
    print("\n--- System 6: Positioning Strategy ---")
    prompt = f"Company: {json.dumps(state['company_intelligence'])}\nRole: {json.dumps(state['role_decode'])}\nUser: {json.dumps(state['user_truth'])}"
    result = _call(_S6_SYSTEM, prompt)
    return {**state, "positioning_strategy": result}


# ─── System 7: Section Rewrites ───────────────────────────────────────────────

_S7_SYSTEM = """You are a senior technical writer. Rewrite only the allowed sections.
CRITICAL:
1. Preserve all links [Text](URL).
2. No 'cope' language or AI-slop.
3. No unsupported claims.
4. Do NOT touch private strategy metadata sections.
Output ONLY valid JSON."""

def section_rewrites_node(state: CouncilState) -> CouncilState:
    print("\n--- System 7: Section Rewrites ---")
    prompt = f"Resume: {json.dumps(state['canonical_resume'])}\nContract: {json.dumps(state['preservation_contract'])}\nStrategy: {json.dumps(state['positioning_strategy'])}\nUser Truth: {json.dumps(state['user_truth'])}"
    result = _call(_S7_SYSTEM, prompt)
    rewrites = result.get('rewrites', {})
    print(f"  → Rewrote {len(rewrites)} sections: {', '.join(list(rewrites.keys()))}")
    return {**state, "section_rewrites": result}


# ─── System 7.5: Truth Guard ──────────────────────────────────────────────────

def truth_guard_node(state: CouncilState) -> CouncilState:
    print("\n--- System 7.5: Truth Guard ---")
    import re
    rewrites = state.get("section_rewrites", {})
    user_truth = state.get("user_truth", {})
    not_allowed = user_truth.get("claims_not_allowed", []) if user_truth else []
    errors = state.get("errors", [])

    if not_allowed and rewrites and "rewrites" in rewrites:
        for section_id, rewrite in rewrites["rewrites"].items():
            text = rewrite.get("rewritten_text", "")
            for claim in not_allowed:
                if claim and claim.lower() in text.lower():
                    print(f"  !! Truth Guard caught violation: '{claim}' in {section_id}")
                    errors.append(f"Truth Guard removed disallowed claim: {claim}")
                    text = re.sub(re.escape(claim), "", text, flags=re.IGNORECASE)
                    rewrites["rewrites"][section_id]["rewritten_text"] = text
                    
    return {**state, "section_rewrites": rewrites, "errors": errors}


# ─── System 8: Safe Assembler ─────────────────────────────────────────────────

_COVER_NOTE_SYSTEM = """Write a 3-sentence cover note for a job application. Be direct and specific. No AI-slop. Use only confirmed experience.
Output ONLY valid JSON.
Required JSON schema:
{"cover_note": "..."}"""

_RECRUITER_DM_SYSTEM = """Write a 2-sentence LinkedIn DM to a recruiter. One sentence on the role, one sentence on why the candidate fits. No fluff.
Output ONLY valid JSON.
Required JSON schema:
{"recruiter_message": "..."}"""

def assembly_node(state: CouncilState) -> CouncilState:
    print("\n--- System 8: Safe Assembler ---")
    # Reconstruct objects
    resume = CanonicalResume(**state["canonical_resume"])
    resume.sections = [ResumeSection(**s) for s in state["canonical_resume"]["sections"]]
    
    rewrites_data = state["section_rewrites"].get("rewrites", {})
    rewrites = SectionRewrites(rewrites={k: SectionRewrite(**v) for k, v in rewrites_data.items()})
    
    contract = PreservationContract(**state["preservation_contract"])
    
    # Deterministic assembly
    final_resume = ResumeCompiler.assemble(resume, rewrites, contract)
    
    # Generate messages
    user_prompt = f"Role: {state['job_title']}\nCompany: {state['company']}\nPositioning Strategy: {json.dumps(state['positioning_strategy'])}"
    
    cover_note_result = _call(_COVER_NOTE_SYSTEM, user_prompt)
    cover_note = cover_note_result.get("cover_note", "")

    dm_result = _call(_RECRUITER_DM_SYSTEM, user_prompt)
    recruiter_message = dm_result.get("recruiter_message", "")
    
    user_truth = state.get("user_truth", {})
    claims_not_allowed = user_truth.get("claims_not_allowed", []) if user_truth else []

    pack = ApplicationPack(
        resume_markdown=final_resume,
        cover_note=cover_note,
        recruiter_message=recruiter_message,
        quality_report=ResumeCompiler.generate_quality_report(resume, rewrites, contract, claims_not_allowed),
        user_review_summary="Check your new resume. 8-system architecture ensured zero metadata leakage."
    )
    
    return {**state, "application_pack": pack.to_dict()}


# ─── Build & Compile Graph ─────────────────────────────────────────────────────

def build_council_graph():
    g = StateGraph(CouncilState)

    g.add_node("parse", parse_node)
    g.add_node("contract", contract_node)
    g.add_node("intelligence", company_intelligence_node)
    g.add_node("decode", role_decode_node)
    g.add_node("truth", user_truth_node)
    g.add_node("strategy", positioning_node)
    g.add_node("rewrites", section_rewrites_node)
    g.add_node("truth_guard", truth_guard_node)
    g.add_node("assembly", assembly_node)

    g.set_entry_point("parse")
    g.add_edge("parse", "contract")
    g.add_edge("contract", "intelligence")
    g.add_edge("intelligence", "decode")
    g.add_edge("decode", "truth")
    g.add_edge("truth", "strategy")
    g.add_edge("strategy", "rewrites")
    g.add_edge("rewrites", "truth_guard")
    g.add_edge("truth_guard", "assembly")
    g.add_edge("assembly", END)

    return g.compile()


_GRAPH = None

def get_council_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_council_graph()
    return _GRAPH
