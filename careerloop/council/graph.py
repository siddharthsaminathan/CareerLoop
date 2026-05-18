import json
from typing import Optional, Dict

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
    QualityReport,
    LinkAudit,
)
from careerloop.council.compiler import ResumeCompiler
from careerloop.council.humanizer import Humanizer
from careerloop.council.node_result import NodeResult
from careerloop.council.runtime_context import get_runtime_context


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

def _call(system: str, user: str, temperature: float = 0.2) -> NodeResult:
    """Call the LLM and return a structured NodeResult.

    NEVER raises — failures are captured in NodeResult.success=False.
    """
    client = CouncilLLMClient("strategy")
    client.temperature = temperature
    try:
        payload = client.complete_json(system, user)
        return NodeResult(success=True, confidence=0.8, payload=payload)
    except Exception as e:
        print(f"  !! LLM Call error: {e}")
        return NodeResult(success=False, confidence=0.0, errors=[str(e)])


def _has_errors(state: CouncilState) -> bool:
    """Return True if any prior node accumulated errors."""
    return bool(state.get("errors"))


# ─── System 1: Document Parser ───────────────────────────────────────────────

def parse_node(state: CouncilState) -> CouncilState:
    print("\n--- System 1: Document Parser ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state
    try:
        resume = ResumeCompiler.parse_markdown(state["master_cv"])
        return {**state, "canonical_resume": resume.to_dict()}
    except Exception as e:
        msg = f"Document Parser failed: {e}"
        print(f"  !! {msg}")
        state.setdefault("errors", []).append(msg)
        return state


# ─── System 2: Preservation Contract ──────────────────────────────────────────

def contract_node(state: CouncilState) -> CouncilState:
    print("\n--- System 2: Preservation Contract ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state
    try:
        resume = CanonicalResume(**state["canonical_resume"])
        resume.sections = [
            ResumeSection(**s) for s in state["canonical_resume"]["sections"]
        ]
        contract = ResumeCompiler.build_contract(resume, state["profile"])
        return {**state, "preservation_contract": contract.to_dict()}
    except Exception as e:
        msg = f"Preservation Contract failed: {e}"
        print(f"  !! {msg}")
        state.setdefault("errors", []).append(msg)
        return state


# ─── System 3: Company Intelligence ───────────────────────────────────────────

_S3_SYSTEM = """You are a senior company researcher. Analyze the target company.
Do NOT invent facts. If unknown, say UNKNOWN.
Output ONLY valid JSON."""


def company_intelligence_node(state: CouncilState) -> CouncilState:
    print("\n--- System 3: Company Intelligence ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state
    prompt = f"Company: {state['company']}\nJD: {state['jd_text']}"
    result = _call(_S3_SYSTEM, prompt)
    if not result.success:
        state.setdefault("errors", []).extend(result.errors)
        return state
    return {**state, "company_intelligence": result.payload}


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
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state
    prompt = (
        f"JD: {state['jd_text']}\n"
        f"Company Context: {json.dumps(state['company_intelligence'])}"
    )
    result = _call(_S4_SYSTEM, prompt)
    if not result.success:
        state.setdefault("errors", []).extend(result.errors)
        return state
    payload = result.payload
    print(
        f"  → {payload.get('normalized_title', '')} | "
        f"{payload.get('seniority', '')[:80]}"
    )
    return {**state, "role_decode": payload}


# ─── System 5: User Truth ─────────────────────────────────────────────────────

_S5_SYSTEM = """You are a rigorous auditor. Build a truthful evidence map.
Map candidate's experience to role requirements. Calculate seniority accurately.
Seniority is locked based on the earliest professional date in the resume.
Today is {today}.
Output ONLY valid JSON."""


def user_truth_node(state: CouncilState) -> CouncilState:
    print("\n--- System 5: User Truth ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state
    prompt = (
        f"Resume: {json.dumps(state['canonical_resume'])}\n"
        f"Role: {json.dumps(state['role_decode'])}"
    )
    # Inject runtime context — never hardcode dates
    ctx = get_runtime_context()
    today = state.get("today") or ctx["current_month"]
    system = _S5_SYSTEM.format(today=today)
    result = _call(system, prompt)
    if not result.success:
        state.setdefault("errors", []).extend(result.errors)
        return state
    return {**state, "user_truth": result.payload}


# ─── System 6: Positioning Strategy ───────────────────────────────────────────

_S6_SYSTEM = """You are a senior career strategist. Create the strategic narrative.
Do NOT rewrite the resume. Decide on the application stance and angle.
Output ONLY valid JSON."""


def positioning_node(state: CouncilState) -> CouncilState:
    print("\n--- System 6: Positioning Strategy ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state
    prompt = (
        f"Company: {json.dumps(state['company_intelligence'])}\n"
        f"Role: {json.dumps(state['role_decode'])}\n"
        f"User: {json.dumps(state['user_truth'])}"
    )
    result = _call(_S6_SYSTEM, prompt)
    if not result.success:
        state.setdefault("errors", []).extend(result.errors)
        return state
    return {**state, "positioning_strategy": result.payload}


# ─── System 7: Section Rewrites ───────────────────────────────────────────────

_S7_SYSTEM = """You are a senior technical writer. Rewrite only the allowed sections.
CRITICAL:
1. Preserve all links [Text](URL).
2. No 'cope' language or AI-slop.
3. No unsupported claims.
4. Do NOT touch private strategy metadata sections.
Only rewrite sections whose section_id appears in preservation_contract.ordering_rules
and are NOT in preservation_contract.sections_to_exclude.
Output ONLY valid JSON.

Required JSON schema:
{
  "rewrites": {
    "section_id": {
      "section_id": "...",
      "original_text": "...",
      "rewritten_text": "...",
      "change_type": "KEEP",
      "change_reason": "...",
      "claims_added": ["..."],
      "claims_removed": ["..."],
      "evidence_used": ["..."],
      "risk_level": "low"
    }
  }
}"""


def section_rewrites_node(state: CouncilState) -> CouncilState:
    print("\n--- System 7: Section Rewrites ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state
    prompt = (
        f"Resume: {json.dumps(state['canonical_resume'])}\n"
        f"Contract: {json.dumps(state['preservation_contract'])}\n"
        f"Strategy: {json.dumps(state['positioning_strategy'])}\n"
        f"User Truth: {json.dumps(state['user_truth'])}"
    )
    result = _call(_S7_SYSTEM, prompt)
    if not result.success:
        state.setdefault("errors", []).extend(result.errors)
        return state
    payload = result.payload
    rewrites = payload.get("rewrites", {})
    print(
        f"  → Rewrote {len(rewrites)} sections: "
        f"{', '.join(list(rewrites.keys()))}"
    )
    return {**state, "section_rewrites": payload}


# ─── System 7.5: Truth Guard ──────────────────────────────────────────────────

def truth_guard_node(state: CouncilState) -> CouncilState:
    print("\n--- System 7.5: Truth Guard ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state

    from careerloop.council.truth_guard import TruthGuard

    guard = TruthGuard()
    rewrites = state.get("section_rewrites", {})
    user_truth = state.get("user_truth", {})
    evidence_bank = user_truth.get("evidence_bank", {}) if user_truth else {}
    claims_not_allowed = (
        user_truth.get("claims_not_allowed", []) if user_truth else []
    )
    errors = state.get("errors", [])
    all_claims = []

    if rewrites and "rewrites" in rewrites:
        for section_id, rewrite in rewrites["rewrites"].items():
            text = rewrite.get("rewritten_text", "")

            # Validate every claim in the text
            claims = guard.validate(
                text, user_truth, evidence_bank, claims_not_allowed
            )
            all_claims.extend(claims)

            # Only repair if there are issues beyond VERIFIED/WEAK
            flagged = [
                c for c in claims
                if c.risk_level in ("UNSUPPORTED", "EXAGGERATED", "FABRICATED")
            ]
            if flagged:
                repaired = guard.repair(text, claims)
                rewrites["rewrites"][section_id]["rewritten_text"] = repaired
                print(
                    f"  → Truth Guard repaired {section_id}: "
                    f"{len(flagged)} claims flagged"
                )

            # Log issues at EXAGGERATED and FABRICATED level — warn, don't block pipeline
            for claim in claims:
                if claim.risk_level in ("EXAGGERATED", "FABRICATED"):
                    msg = (
                        f"Truth Guard [{claim.risk_level}]: "
                        f"'{claim.text[:60]}...' → "
                        f"{claim.repair_suggestion or 'minimized'}"
                    )
                    state.setdefault("warnings", []).append(msg)
                    print(f"  ⚠️ {msg}")

    state.setdefault("truth_guard_flags", []).extend(all_claims)
    report = guard.generate_report(all_claims)
    verified_pct = (
        (report.verified / max(1, report.total_claims)) * 100
    )
    print(
        f"  → Truth Guard report: {report.total_claims} claims — "
        f"{report.verified} verified ({verified_pct:.0f}%), "
        f"{report.weak} weak, {report.unsupported} unsupported, "
        f"{report.exaggerated} exaggerated, {report.fabricated} fabricated"
    )

    return {
        **state,
        "section_rewrites": rewrites,
        "errors": errors,
        "truth_guard_report": report,
    }


# ─── System 8: Safe Assembler ─────────────────────────────────────────────────

_COVER_NOTE_SYSTEM = """Write a 3-sentence cover note for a job application.
Be direct and specific. No AI-slop. Use only confirmed experience.
Output ONLY valid JSON.
Required JSON schema:
{"cover_note": "..."}"""

_RECRUITER_DM_SYSTEM = """Write a 2-sentence LinkedIn DM to a recruiter.
One sentence on the role, one sentence on why the candidate fits. No fluff.
Output ONLY valid JSON.
Required JSON schema:
{"recruiter_message": "..."}"""


def assembly_node(state: CouncilState) -> CouncilState:
    print("\n--- System 8: Safe Assembler ---")

    # If errors accumulated from upstream nodes, refuse assembly
    if _has_errors(state):
        print(
            f"  !! REFUSING assembly — {len(state['errors'])} error(s) from "
            f"upstream nodes. Writing failure report."
        )
        ctx = get_runtime_context()
        failure_report = (
            f"# Resume Council Failure Report\n\n"
            f"**Generated:** {ctx['current_datetime']}\n"
            f"**Job:** {state['job_title']} at {state['company']}\n\n"
            f"## Errors ({len(state['errors'])})\n\n"
        )
        for i, err in enumerate(state["errors"], 1):
            failure_report += f"{i}. {err}\n"
        failure_report += (
            "\n## Next Steps\n\n"
            "1. Fix the underlying issue (API key, model config, input data).\n"
            "2. Re-run the council for this job.\n"
        )
        pack = ApplicationPack(
            resume_markdown="",
            cover_note="",
            recruiter_message="",
            quality_report=None,
            user_review_summary=(
                f"FAILURE: Council stopped with {len(state['errors'])} error(s). "
                f"See failure_report.md in output directory."
            ),
        )
        pack_dict = pack.to_dict()
        pack_dict["failure_report"] = failure_report
        return {**state, "application_pack": pack_dict}

    try:
        # Reconstruct objects
        resume = CanonicalResume(**state["canonical_resume"])
        resume.sections = [
            ResumeSection(**s)
            for s in state["canonical_resume"]["sections"]
        ]

        rewrites_data = state["section_rewrites"].get("rewrites", {})
        rewrites = SectionRewrites(
            rewrites={k: SectionRewrite(**v) for k, v in rewrites_data.items()}
        )

        contract = PreservationContract(**state["preservation_contract"])

        # Deterministic assembly (no LLM)
        final_resume = ResumeCompiler.assemble(resume, rewrites, contract)

        # Generate messages
        user_prompt = (
            f"Role: {state['job_title']}\n"
            f"Company: {state['company']}\n"
            f"Positioning Strategy: {json.dumps(state['positioning_strategy'])}"
        )

        cover_result = _call(_COVER_NOTE_SYSTEM, user_prompt)
        cover_note = (
            cover_result.payload.get("cover_note", "")
            if cover_result.success
            else ""
        )

        dm_result = _call(_RECRUITER_DM_SYSTEM, user_prompt)
        recruiter_message = (
            dm_result.payload.get("recruiter_message", "")
            if dm_result.success
            else ""
        )

        user_truth = state.get("user_truth", {})
        claims_not_allowed = (
            user_truth.get("claims_not_allowed", []) if user_truth else []
        )

        # ─── Humanizer: Anti-AI detection + human normalization ──────────
        company_intel = state.get("company_intelligence", {})
        company_type = (
            company_intel.get("maturity", "default")
            if company_intel else "default"
        )

        humanizer = Humanizer(llm_client=None)

        resume_result = humanizer.humanize(
            final_resume, mode="resume",
            context={"company_type": company_type},
        )
        cover_result = humanizer.humanize(
            cover_note, mode="cover_note",
            context={"company_type": company_type},
        )
        dm_result_h = humanizer.humanize(
            recruiter_message, mode="recruiter_message",
            context={"company_type": company_type},
        )

        print(
            f"  → Humanizer: {resume_result.changes_made} slop flags, "
            f"{len(resume_result.recruiter_concerns)} realism concerns"
        )

        # Link preservation audit (on humanized output — the actual deliverable)
        link_audit = ResumeCompiler._verify_links_preserved(
            resume, resume_result.humanized_text, contract
        )
        preserved_links = ResumeCompiler.extract_links_from_text(
            resume_result.humanized_text
        )

        # Log warnings from link audit
        for warning in link_audit.warnings:
            print(f"  !! {warning}")

        pack = ApplicationPack(
            resume_markdown=resume_result.humanized_text,
            cover_note=cover_result.humanized_text,
            recruiter_message=dm_result_h.humanized_text,
            quality_report=ResumeCompiler.generate_quality_report(
                resume, rewrites, contract, claims_not_allowed
            ),
            preserved_links=preserved_links,
            link_audit=link_audit,
            user_review_summary=(
                "Check your new resume. "
                "8-system architecture ensured zero metadata leakage."
            ),
        )

        return {**state, "application_pack": pack.to_dict()}

    except Exception as e:
        msg = f"Safe Assembler failed: {e}"
        print(f"  !! {msg}")
        state.setdefault("errors", []).append(msg)
        ctx = get_runtime_context()
        failure_report = (
            f"# Resume Council Failure Report\n\n"
            f"**Generated:** {ctx['current_datetime']}\n"
            f"**Job:** {state['job_title']} at {state['company']}\n\n"
            f"## Fatal Error\n\n{msg}\n"
        )
        pack = ApplicationPack(
            resume_markdown="",
            cover_note="",
            recruiter_message="",
            quality_report=None,
            user_review_summary=f"FAILURE: Assembly error — {msg}",
        )
        pack_dict = pack.to_dict()
        pack_dict["failure_report"] = failure_report
        return {**state, "application_pack": pack_dict}


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
