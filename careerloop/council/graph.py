import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional, Dict

from typing_extensions import TypedDict

from langgraph.graph import END, StateGraph

from careerloop.council.llm import CouncilLLMClient
from careerloop.council.schemas import validate_payload, schema_instruction
from careerloop.council.company_research import CompanyResearchAdapter, quality_score
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
    truth_guard_report: Optional[Dict]

    errors: list


# ─── LLM client ───────────────────────────────────────────────────────────────

def _call(system: str, user: str, temperature: float = 0.2,
          max_tokens: int = None, label: str = "") -> NodeResult:
    """Call the LLM and return a structured NodeResult.

    NEVER raises — failures are captured in NodeResult.success=False.
    """
    client = CouncilLLMClient("strategy")
    client.temperature = temperature
    tag = f" [{label}]" if label else ""
    print(f"  ⟳ LLM call{tag}...", end=" ", flush=True)
    try:
        payload = client.complete_json(system, user, max_tokens=max_tokens)
        print("done")
        return NodeResult(success=True, confidence=0.8, payload=payload)
    except Exception as e:
        print(f"FAILED")
        print(f"  !! LLM Call error: {e}")
        return NodeResult(success=False, confidence=0.0, errors=[str(e)])


def _has_errors(state: CouncilState) -> bool:
    """Return True if any prior node accumulated errors."""
    return bool(state.get("errors"))


def _split_section_into_chunks(text: str, max_chunk_chars: int = 1500) -> list:
    """Split a long section into chunks at paragraph (double-newline) boundaries.

    Each chunk is at most max_chunk_chars characters.  Paragraphs that are
    themselves longer than the limit are kept as a single chunk — we never
    split mid-paragraph.

    Returns a list of non-empty chunk strings.  Falls back to [text] if
    splitting produces nothing useful.
    """
    paragraphs = [p for p in re.split(r'\n{2,}', text.strip()) if p.strip()]
    if not paragraphs:
        return [text]

    chunks = []
    current: list = []
    current_len = 0

    for para in paragraphs:
        plen = len(para)
        if current and current_len + plen > max_chunk_chars:
            chunks.append('\n\n'.join(current))
            current = [para]
            current_len = plen
        else:
            current.append(para)
            current_len += plen

    if current:
        chunks.append('\n\n'.join(current))

    return chunks if chunks else [text]


def _count_markdown_bullets(text: str) -> int:
    return len(re.findall(r"(?m)^\s*[-*]\s+\S", text or ""))


def _rewrite_preserves_section_structure(original: str, rewritten: str) -> tuple[bool, list[str]]:
    issues: list[str] = []

    original_bullets = _count_markdown_bullets(original)
    rewritten_bullets = _count_markdown_bullets(rewritten)
    if original_bullets and rewritten_bullets < original_bullets:
        issues.append(f"bullet_count_dropped:{original_bullets}->{rewritten_bullets}")

    if re.search(r"\.\s+[-*]\s+[A-Z0-9]", rewritten or ""):
        issues.append("collapsed_bullet_marker")

    stripped = (rewritten or "").strip()
    if stripped and not stripped.endswith((".", ")", "]", ":", "%")) and "\n- " not in stripped[-80:]:
        issues.append("possible_truncation")

    if len(stripped) < max(80, len((original or "").strip()) * 0.35):
        issues.append(f"rewrite_too_short:{len(stripped)}<{len((original or '').strip())}")

    return not issues, issues


def _rewrite_one_section(
    section: dict,
    tone: str,
    narrative_angle: str,
    things_to_downplay: list,
    role_keywords: list,
    hidden_expectations: list,
    day_one_deliverables: list,
    must_haves: list,
    proof_points: list,
    claims_allowed: list,
    claims_not_allowed: list,
) -> tuple:
    """Worker for parallel S7 execution.

    Handles both chunked (large experience sections) and standard rewrites.
    Returns (sid, rewrite_dict_or_None, skip_reason_or_None).
    Thread-safe: _call() creates a new CouncilLLMClient per invocation.
    """
    sid = section.get('section_id', '')
    stitle = section.get('section_title', sid)
    raw = section.get('raw_text', '')
    normalized_type = section.get('normalized_type', '')

    is_experience = normalized_type in {
        "experience", "work_experience", "professional_experience"
    }

    # ── Chunked path for large experience sections ─────────────────────────
    if is_experience and len(raw) > 1800:
        chunks = _split_section_into_chunks(raw, max_chunk_chars=1400)
        print(f"  → S7 chunked '{sid}' ({len(raw)} chars) → {len(chunks)} chunks")
        rewritten_chunks = []
        chunk_ok = True

        for ci, chunk in enumerate(chunks):
            chunk_prompt = json.dumps({
                "section_id": f"{sid}_chunk{ci + 1}",
                "section_title": stitle,
                "section_text": chunk,
                "tone_guidance": tone,
                "narrative_angle": narrative_angle,
                "role_keywords": role_keywords,
                "must_haves": must_haves,
                "hidden_expectations": hidden_expectations,
                "day_one_deliverables": day_one_deliverables,
                "things_to_downplay": things_to_downplay,
                "proof_points": proof_points,
                "claims_allowed": claims_allowed,
                "claims_not_allowed": claims_not_allowed,
            }, ensure_ascii=False)

            cresult = _call(
                _S7_PER_SECTION_SYSTEM, chunk_prompt,
                max_tokens=2500,
                label=f"S7 {sid} {ci + 1}/{len(chunks)}",
            )
            if not cresult.success:
                print(f"  !! S7 chunk {ci + 1} failed — aborting chunked rewrite for '{sid}'")
                chunk_ok = False
                break

            ctext = cresult.payload.get('rewritten_text', '').strip()
            if not ctext or len(ctext) < len(chunk) * 0.4:
                print(
                    f"  !! S7 chunk {ci + 1} truncated "
                    f"({len(ctext)} vs {len(chunk)} chars) — aborting"
                )
                chunk_ok = False
                break

            rewritten_chunks.append(ctext)

        if not chunk_ok or not rewritten_chunks:
            reason = "chunked_rewrite_failed"
            print(f"  !! S7 fallback '{sid}' → {reason} — keeping original")
            return sid, None, reason

        rewritten = '\n\n'.join(rewritten_chunks)
        rewritten = ResumeCompiler._preprocess_plaintext_cv(rewritten)
        rewrite_dict = {
            "section_id": sid,
            "original_text": raw,
            "rewritten_text": rewritten,
            "change_type": "REWRITE",
            "change_reason": f"Chunked rewrite ({len(chunks)} chunks, {len(raw)} → {len(rewritten)} chars)",
            "claims_added": [],
            "claims_removed": [],
            "evidence_used": [],
            "risk_level": "medium",
        }
        print(f"  → [CHUNKED] {stitle} ({len(rewritten)} chars from {len(chunks)} chunks)")
        return sid, rewrite_dict, None

    # ── Standard single-call rewrite ──────────────────────────────────────
    prompt = json.dumps({
        "section_id": sid,
        "section_title": stitle,
        "section_text": raw,
        "tone_guidance": tone,
        "narrative_angle": narrative_angle,
        "role_keywords": role_keywords,
        "must_haves": must_haves,
        "hidden_expectations": hidden_expectations,
        "day_one_deliverables": day_one_deliverables,
        "things_to_downplay": things_to_downplay,
        "proof_points": proof_points,
        "claims_allowed": claims_allowed,
        "claims_not_allowed": claims_not_allowed,
    }, ensure_ascii=False)

    result = _call(_S7_PER_SECTION_SYSTEM, prompt, max_tokens=4000, label=f"S7 {sid}")
    if not result.success:
        reason = f"llm_error:{result.errors}"
        print(f"  !! S7 fallback '{sid}' → {reason}")
        return sid, None, reason

    payload = result.payload
    rewritten = payload.get('rewritten_text', '').strip()
    if not rewritten:
        reason = "empty_rewrite"
        print(f"  !! S7 fallback '{sid}' → {reason} — keeping original")
        return sid, None, reason

    if len(rewritten) < len(raw) * 0.5:
        reason = f"truncation_suspected:rewrite={len(rewritten)}chars,original={len(raw)}chars"
        print(f"  !! S7 fallback '{sid}' → {reason} — keeping original")
        return sid, None, reason

    rewritten = ResumeCompiler._preprocess_plaintext_cv(rewritten)
    safe, issues = _rewrite_preserves_section_structure(raw, rewritten)
    if not safe:
        reason = f"structure_check_failed:{','.join(issues)}"
        print(f"  !! S7 fallback '{sid}' → {reason} — keeping original")
        return sid, None, reason

    rewrite_dict = {
        "section_id": sid,
        "original_text": raw,
        "rewritten_text": rewritten,
        "change_type": payload.get('change_type', 'REWRITE'),
        "change_reason": payload.get('change_reason', ''),
        "claims_added": payload.get('claims_added', []),
        "claims_removed": payload.get('claims_removed', []),
        "evidence_used": payload.get('evidence_used', []),
        "risk_level": payload.get('risk_level', 'low'),
    }
    print(f"  → [{payload.get('change_type','?')}] {stitle} ({len(rewritten)} chars)")
    return sid, rewrite_dict, None


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
        from careerloop.council.safe_model import safe_construct
        resume = safe_construct(CanonicalResume, state["canonical_resume"])
        resume.sections = [
            safe_construct(ResumeSection, s)
            for s in state["canonical_resume"]["sections"]
        ]
        contract = ResumeCompiler.build_contract(resume, state["profile"])
        return {**state, "preservation_contract": contract.to_dict()}
    except Exception as e:
        msg = f"Preservation Contract failed: {e}"
        print(f"  !! {msg}")
        state.setdefault("errors", []).append(msg)
        return state


# ─── System 3: Company Intelligence ───────────────────────────────────────────

_S3_SCHEMA = schema_instruction("company_intelligence")

_S3_SYSTEM = f"""You are a company researcher extracting signals from the job description and your knowledge.
CRITICAL: Distinguish JD-extracted facts from recalled knowledge.
NEVER invent funding amounts, employee counts, or revenue figures.
For facts the JD does NOT reveal, use UNKNOWN and add them to missing_data and gaps.

You will receive pre-gathered research snippets in the user prompt. Use them as grounding.
Set grounding_status to READY if web/search sources are present, PARTIAL if only JD/manual, UNGROUNDED if no external sources.
Always populate facts, inferences, sources, gaps, and role_implications lists.

{_S3_SCHEMA}"""


def company_intelligence_node(state: CouncilState) -> CouncilState:
    print("\n--- System 3: Company Intelligence ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state

    # Hard skip: set CAREERLOOP_SKIP_S3=1 to bypass the LLM call entirely.
    # S4 Role Decoder extracts everything needed from the JD directly.
    # Use this when DeepSeek is slow/rate-limited or S3 is blocking the run.
    if os.getenv("CAREERLOOP_SKIP_S3", "").lower() in {"1", "true", "yes"}:
        print("  → S3 SKIPPED (CAREERLOOP_SKIP_S3=1) — using JD-only stub")
        stub = {
            "company": state.get("company", ""),
            "summary": "Skipped — JD-only mode. S4 Role Decoder will extract role signals directly from JD.",
            "grounding_status": "SKIPPED",
            "facts": [],
            "inferences": [],
            "gaps": ["S3 skipped by CAREERLOOP_SKIP_S3=1"],
            "sources": [],
            "role_implications": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "confidence": 0.0,
        }
        return {**state, "company_intelligence": stub}

    jd = state['jd_text']
    company = state['company']
    job_url = state.get('job_url', '')
    fetched_at = datetime.now(timezone.utc).isoformat()

    # P0.8: gather grounded research before sending to LLM
    researcher = CompanyResearchAdapter()
    bundle = researcher.gather(company=company, website=job_url, jd_text=jd)
    q = quality_score(bundle)
    print(f"  → Company research: {q['status']} | sources={q['source_count']} | score={q['score']}")

    jd_snippet = jd[:2500] if len(jd) > 2500 else jd
    sources_block = "\n".join(
        f"[{s.source_type.upper()}] {s.title}: {s.snippet[:200]}"
        for s in bundle.sources
    ) or "No external sources available."

    prompt = (
        f"Company: {company}\n"
        f"Job URL: {job_url or 'unknown'}\n"
        f"Grounding status: {bundle.grounding_status}\n"
        f"Fetched at: {fetched_at}\n\n"
        f"RESEARCH SOURCES:\n{sources_block}\n\n"
        f"JD EXCERPT:\n{jd_snippet}\n\n"
        f"Extract company intelligence. Facts not present in sources or JD must go in gaps[] and missing_data[]."
    )
    result = _call(_S3_SYSTEM, prompt, label="S3 company intelligence")
    if not result.success:
        state.setdefault("errors", []).extend(result.errors)
        return state
    payload = result.payload

    # Schema validation (P0.5) - fill in grounding fields from research bundle
    payload.setdefault("grounding_status", bundle.grounding_status)
    payload.setdefault("fetched_at", fetched_at)
    payload.setdefault("facts", [])
    payload.setdefault("inferences", [])
    payload.setdefault("sources", [s.to_dict() for s in bundle.sources])
    payload.setdefault("gaps", bundle.gaps)
    payload.setdefault("role_implications", [])

    vresult = validate_payload("company_intelligence", payload)
    if not vresult.ok:
        for err in vresult.errors:
            print(f"  !! Schema warning: {err}")
    payload = vresult.payload

    if payload.get("grounding_status") == "UNGROUNDED":
        print(f"  !! Company intelligence is UNGROUNDED — model used training data only for {company}")

    confidence = payload.get("confidence", 0.2 if payload.get("grounding_status") == "UNGROUNDED" else 0.5)
    print(f"  → {payload.get('summary', '?')[:80]}... | confidence={confidence} | {payload.get('grounding_status', 'UNKNOWN')}")
    return {**state, "company_intelligence": payload}


# ─── System 4: Role Decoder ───────────────────────────────────────────────────

_S4_SYSTEM = """You are a master role decoder. Extract what the job actually wants from the JD.
Separate must-haves from nice-to-haves. Identify hidden expectations.
Output JSON matching the example format below.

EXAMPLE JSON OUTPUT:
{
  "normalized_title": "AI Product Engineer",
  "seniority": "mid-senior",
  "must_haves": ["Python", "LLM API experience", "SQL", "frontend skills"],
  "nice_to_haves": ["retail/e-commerce experience", "IIT/BITS/NIT"],
  "hidden_expectations": ["CEO-facing communication", "business-outcome thinking"],
  "day_one_deliverables": ["Customer personalization intelligence layer"],
  "screening_keywords": ["AI-native", "clienteling", "business intelligence"],
  "disqualifiers": ["no LLM experience", "no coding skills"],
  "confidence": 0.85
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
    result = _call(_S4_SYSTEM, prompt, label="S4 role decode")
    if not result.success:
        state.setdefault("errors", []).extend(result.errors)
        return state
    payload = result.payload
    vresult = validate_payload("role_decode", payload)
    if not vresult.ok:
        for err in vresult.errors:
            print(f"  !! Schema warning (role_decode): {err}")
    payload = vresult.payload
    print(
        f"  → {payload.get('normalized_title', '')} | "
        f"{payload.get('seniority', '')[:80]}"
    )
    return {**state, "role_decode": payload}


# ─── System 5: User Truth ─────────────────────────────────────────────────────

_S5_SYSTEM = """You are a rigorous auditor. Build a truthful evidence map in JSON.
Map candidate's experience to role requirements. Calculate seniority accurately.
Seniority is locked based on the earliest professional date in the resume.
Today is {today}.

EXAMPLE JSON OUTPUT:
{{
  "total_years_experience": 4.5,
  "confirmed_skills": [{{"skill": "Python", "years": 4, "evidence": "Built production AI systems"}}],
  "weak_skills": ["Kubernetes"],
  "evidence_bank": {{"Python": ["Built AI quality management system", "Multi-agent orchestration"]}},
  "strongest_proof_points": ["Shipped AI that automates enterprise workflows"],
  "claims_allowed": ["4+ years Python", "LLM API experience", "Agent architectures"],
  "claims_not_allowed": ["10 years AI experience", "Deep learning expert"],
  "private_constraints": ["min salary 25L", "Chennai location preferred"]
}}"""


_S5_SCHEMA = schema_instruction("user_truth")


def user_truth_node(state: CouncilState) -> CouncilState:
    print("\n--- System 5: User Truth ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state
    prompt = (
        f"Resume: {json.dumps(state['canonical_resume'])}\n"
        f"Role: {json.dumps(state['role_decode'])}"
    )
    ctx = get_runtime_context()
    today = state.get("today") or ctx["current_month"]
    system = _S5_SYSTEM.format(today=today) + f"\n\n{_S5_SCHEMA}"
    result = _call(system, prompt, label="S5 user truth")
    if not result.success:
        state.setdefault("errors", []).extend(result.errors)
        return state

    # P0.3 + P0.5: validate schema and strip private_constraints before it propagates
    payload = result.payload
    payload.pop("private_constraints", None)
    vresult = validate_payload("user_truth", payload)
    if not vresult.ok:
        for err in vresult.errors:
            print(f"  !! Schema warning (user_truth): {err}")
    return {**state, "user_truth": vresult.payload}


# ─── System 6: Positioning Strategy ───────────────────────────────────────────

_S6_SYSTEM = """You are a senior career strategist. Create the strategic narrative in JSON.
Do NOT rewrite the resume. Decide on the application stance and angle.
Base all proof points on evidence from User Truth evidence_bank only.

EXAMPLE JSON OUTPUT:
{
  "one_line_positioning": "AI Product Engineer who ships enterprise AI from concept to production",
  "narrative_angle": "Product-minded AI engineer with manufacturing quality digitization experience",
  "lead_strengths": ["LLM API production experience", "Multi-agent orchestration", "End-to-end shipping"],
  "proof_points_to_emphasize": ["Built AI quality management from scratch", "Real-time AI at scale"],
  "things_to_downplay": ["Academic research background", "Non-e-commerce experience"],
  "tone_guidance": "Direct, technical, business-outcome focused",
  "recruiter_first_impression_target": "Engineer who thinks in business outcomes, not just code",
  "application_stance": "CAREFUL_PUSH",
  "reasoning": "Strong AI engineering match; D2C retail domain is new but transferable"
}"""


_S6_SCHEMA = schema_instruction("positioning_strategy")


def positioning_node(state: CouncilState) -> CouncilState:
    print("\n--- System 6: Positioning Strategy ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state

    # Only send public user_truth fields to LLM (never private_constraints)
    user_truth_safe = {k: v for k, v in (state.get('user_truth') or {}).items()
                       if k != 'private_constraints'}
    prompt = (
        f"Company: {json.dumps(state['company_intelligence'])}\n"
        f"Role: {json.dumps(state['role_decode'])}\n"
        f"User: {json.dumps(user_truth_safe)}"
    )
    system = _S6_SYSTEM + f"\n\n{_S6_SCHEMA}"
    result = _call(system, prompt, label="S6 positioning")
    if not result.success:
        state.setdefault("errors", []).extend(result.errors)
        return state
    payload = result.payload
    vresult = validate_payload("positioning_strategy", payload)
    if not vresult.ok:
        for err in vresult.errors:
            print(f"  !! Schema warning (positioning): {err}")
    return {**state, "positioning_strategy": vresult.payload}


# ─── System 7: Section Rewrites ───────────────────────────────────────────────

_S7_PER_SECTION_SYSTEM = """You are a senior resume writer rewriting ONE section of a candidate's resume for a specific role.

CRITICAL RULES — follow every one:
1. Rewrite ONLY the text in "section_text". Preserve all [Text](URL) links exactly as-is.
2. Every metric, number, and date must come verbatim from the original section_text. NEVER invent figures.
3. Do NOT add claims from claims_not_allowed — these are explicitly forbidden by the evidence audit.
4. Keep the exact same bullet count. Do NOT merge or drop bullets.
5. Replace weak generic verbs (Analyzed, Supported, Assisted, Utilized, Collaborated) with stronger action verbs that match the role. Keep all metrics intact.
6. Weave in role_keywords and address hidden_expectations naturally — one keyword per bullet maximum. No keyword-stuffing.
7. The narrative_angle tells you HOW to position the candidate. Use it to choose which aspects of each bullet to lead with.
8. things_to_downplay should be de-emphasized — move them to the end of bullets or omit if redundant.
9. day_one_deliverables tell you what the hiring manager actually needs on day one — if a bullet is evidence of that capability, make it the lead bullet for the role.
10. NO AI-slop: no 'spearheaded', 'leveraged', 'synergy', 'passionate', 'results-driven'.

Return ONLY a JSON object with this exact shape (no markdown, no explanation):
{
  "section_id": "<same as input>",
  "rewritten_text": "<full rewritten markdown for this section>",
  "change_type": "KEEP|EXPAND|REWRITE|TRIM",
  "change_reason": "<one sentence explaining the positioning angle applied>",
  "claims_added": [],
  "claims_removed": [],
  "evidence_used": [],
  "risk_level": "low|medium|high"
}"""

_S7_SYSTEM = _S7_PER_SECTION_SYSTEM


def section_rewrites_node(state: CouncilState) -> CouncilState:
    print("\n--- System 7: Section Rewrites (per-section loop) ---")
    if _has_errors(state):
        print("  → SKIPPING (previous errors)")
        return state

    user_truth_safe = {k: v for k, v in (state.get('user_truth') or {}).items()
                       if k != 'private_constraints'}
    strategy = state.get('positioning_strategy') or {}
    role_decode = state.get('role_decode') or {}
    contract = state.get('preservation_contract') or {}
    exclude = set(contract.get('sections_to_exclude', []))
    canonical = state.get('canonical_resume') or {}

    tone = strategy.get('tone_guidance', '')
    narrative_angle = strategy.get('narrative_angle', '')
    things_to_downplay = strategy.get('things_to_downplay', [])[:5]
    role_keywords = role_decode.get('screening_keywords', [])[:10]
    hidden_expectations = role_decode.get('hidden_expectations', [])[:5]
    day_one_deliverables = role_decode.get('day_one_deliverables', [])[:3]
    must_haves = role_decode.get('must_haves', [])[:5]
    proof_points = user_truth_safe.get('strongest_proof_points', [])[:5]
    claims_allowed = user_truth_safe.get('claims_allowed', [])
    claims_not_allowed = user_truth_safe.get('claims_not_allowed', [])

    rewrites: dict = {}
    # skipped maps section_id → reason string for diagnostics
    skipped: dict = {}

    allowed_sections = [
        s for s in canonical.get('sections', [])
        if s.get('section_id') not in exclude
           and s.get('raw_text', '').strip()
    ]

    # ── Parallel execution: all sections run concurrently ─────────────────
    # Each section's LLM calls are independent — no cross-section state.
    # max_workers = number of sections so they all fire simultaneously.
    # Results are collected via futures and reassembled in original order.
    worker_kwargs = dict(
        tone=tone,
        narrative_angle=narrative_angle,
        things_to_downplay=things_to_downplay,
        role_keywords=role_keywords,
        hidden_expectations=hidden_expectations,
        day_one_deliverables=day_one_deliverables,
        must_haves=must_haves,
        proof_points=proof_points,
        claims_allowed=claims_allowed,
        claims_not_allowed=claims_not_allowed,
    )

    n_workers = max(1, len(allowed_sections))
    print(f"  → Launching {n_workers} parallel S7 workers...")

    # Map future → original section order so we can print results in order
    future_to_sid: dict = {}
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        for section in allowed_sections:
            fut = executor.submit(_rewrite_one_section, section, **worker_kwargs)
            future_to_sid[fut] = section.get('section_id', '')

        for fut in as_completed(future_to_sid):
            sid_result, rewrite_dict, skip_reason = fut.result()
            if rewrite_dict is not None:
                rewrites[sid_result] = rewrite_dict
            elif skip_reason is not None:
                skipped[sid_result] = skip_reason

    if skipped:
        print(f"  !! {len(skipped)}/{len(allowed_sections)} sections fell back to original:")
        for sid, reason in skipped.items():
            print(f"       {sid}: {reason}")
    print(f"  → Rewrote {len(rewrites)}/{len(allowed_sections)} sections")

    return {**state, "section_rewrites": {
        "rewrites": rewrites,
        "forbidden_edits": list(exclude),
        "skipped": list(skipped.keys()),
        "skipped_reasons": skipped,
    }}


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

    import dataclasses
    report_dict = dataclasses.asdict(report)

    return {
        **state,
        "section_rewrites": rewrites,
        "errors": errors,
        "truth_guard_report": report_dict,
    }


# ─── System 8: Safe Assembler ─────────────────────────────────────────────────

_COVER_NOTE_SYSTEM = """Write a 3-sentence cover note that compels a recruiter to interview. Lead with a concrete achievement from the candidate's strongest proof points — not "I am writing". Be specific. Use only confirmed experience from the proof points provided.

Use the candidate's actual role, company, and metrics from the input — never invent or recycle example names.

Return JSON with this exact shape:
{"cover_note": "<3-sentence cover note tailored to the specific role and company in the input>"}"""

_RECRUITER_DM_SYSTEM = """Write a 2-sentence LinkedIn DM to a recruiter in JSON.
One sentence on the role, one sentence on why the candidate fits. Under 250 chars. No fluff, no "I'm excited to apply".

Use the candidate's actual proof points from the input — never invent or recycle example names.

Return JSON with this exact shape:
{"recruiter_message": "<2-sentence DM tailored to the specific role in the input>"}"""


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
        # Reconstruct objects (safe — handles LLM extra/missing keys)
        from careerloop.council.safe_model import safe_construct

        resume = safe_construct(CanonicalResume, state["canonical_resume"])
        resume.sections = [
            safe_construct(ResumeSection, s)
            for s in state["canonical_resume"]["sections"]
        ]

        rewrites_data = state["section_rewrites"].get("rewrites", {})
        from careerloop.council.safe_model import safe_construct
        rewrites = SectionRewrites(
            rewrites={k: safe_construct(SectionRewrite, v) for k, v in rewrites_data.items()}
        )

        contract = safe_construct(PreservationContract, state["preservation_contract"])

        # Deterministic assembly (no LLM)
        final_resume = ResumeCompiler.assemble(resume, rewrites, contract)

        # Build rich context for cover note + recruiter DM
        user_truth = state.get("user_truth", {})
        top_proofs = user_truth.get("strongest_proof_points", [])[:3]
        user_prompt_parts = [
            f"Role: {state['job_title']}",
            f"Company: {state['company']}",
            f"Positioning Strategy: {json.dumps(state['positioning_strategy'])}",
        ]
        if top_proofs:
            user_prompt_parts.append(f"Strongest Proof Points: {json.dumps(top_proofs)}")
        user_prompt = "\n".join(user_prompt_parts)

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

        claims_not_allowed = (
            user_truth.get("claims_not_allowed", []) if user_truth else []
        )

        # ─── Humanizer: Anti-AI detection + human normalization ──────────
        company_intel = state.get("company_intelligence", {})
        company_type = (
            company_intel.get("maturity", "default")
            if company_intel else "default"
        )

        humanizer = Humanizer(llm_client=CouncilLLMClient("writer"))

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
            f"  → Humanizer (resume): {resume_result.changes_made} slop flags, "
            f"{len(resume_result.recruiter_concerns)} realism concerns"
        )
        print(
            f"  → Humanizer (cover): {cover_result.changes_made} slop flags, "
            f"{len(cover_result.recruiter_concerns)} realism concerns"
        )
        print(
            f"  → Humanizer (DM):   {dm_result_h.changes_made} slop flags, "
            f"{len(dm_result_h.recruiter_concerns)} realism concerns"
        )

        # ─── Post-Humanizer verification: check for surviving slop ────────
        _leftover_slop = 0
        for word in [
            "agentic", "multi-agent", "autonomous", "swarm",
            "AI revolution", "leverage", "spearheaded",
        ]:
            for label, text in [
                ("resume", resume_result.humanized_text),
                ("cover", cover_result.humanized_text),
                ("dm", dm_result_h.humanized_text),
            ]:
                count = text.lower().count(word.lower())
                if count > 0:
                    _leftover_slop += count
                    if count > 2 or word == "agentic":
                        print(f"  !! VERIFY: '{word}' survived Humanizer in {label} ({count}x)")
        if _leftover_slop == 0:
            print(f"  → Post-Humanizer verify: 0 surviving slop terms")
        else:
            print(f"  → Post-Humanizer verify: {_leftover_slop} surviving slop occurrences — review output manually")

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
