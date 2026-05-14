"""
Deterministic Resume Council stage fallbacks.
"""

import re

from careerloop.council.models import (
    ApplicationPack,
    CompanyIntelligence,
    CouncilContext,
    FitGapAnalysis,
    PositioningStrategy,
    ResumePlan,
    RoleDecode,
    UserTruth,
)


AI_KEYWORDS = [
    "python", "machine learning", "ml", "ai", "gen ai", "genai", "llm", "rag",
    "prompt", "pytorch", "tensorflow", "nlp", "mlops", "aws", "gcp", "azure",
    "fastapi", "kubernetes", "docker", "sql", "vector", "langchain",
]


def build_company_intelligence(context: CouncilContext) -> CompanyIntelligence:
    job = context.job
    company = job.get("company", "") or "Unknown company"
    title = job.get("title", job.get("role_title", ""))
    location = job.get("location", "")
    return CompanyIntelligence(
        company_summary=f"{company} is being evaluated for a specific {title} opportunity in {location}.",
        why_this_role_exists="Likely hiring to strengthen AI/ML delivery capacity based on the role title and job source.",
        company_maturity="Unknown from current verified job data; needs deeper user-approved research.",
        hiring_urgency="Unknown; treat as moderate until company signals are researched.",
        likely_screening_filters=_extract_keywords(title + " " + _job_text(job)),
        culture_signals=[],
        red_flags=["Company intelligence not deeply researched yet."],
        positioning_implications=["Use grounded, evidence-backed AI delivery positioning rather than broad claims."],
        interview_implications=["Prepare to defend practical AI/ML implementation experience."],
    )


def decode_role(context: CouncilContext) -> RoleDecode:
    text = (context.job.get("title", "") + " " + _job_text(context.job)).lower()
    keywords = _extract_keywords(text)
    hidden = []
    if "cross-functional" in text:
        hidden.append("Stakeholder communication across functions")
    if "fast-paced" in text:
        hidden.append("Ambiguity tolerance and speed")
    if "genai" in text or "gen ai" in text or "llm" in text:
        hidden.append("Practical LLM implementation, not only research ML")
    return RoleDecode(
        must_have_skills=keywords[:8],
        nice_to_have_skills=keywords[8:14],
        hidden_expectations=hidden,
        seniority_level=_infer_seniority(context.job.get("title", "")),
        stakeholder_load="Unknown; infer during company research or JD review.",
        technical_depth="Applied engineering depth" if any(k in keywords for k in ["python", "llm", "mlops", "rag"]) else "Unknown",
        likely_screening_keywords=keywords,
        likely_interview_topics=[f"Defend experience with {k}" for k in keywords[:5]],
        application_risks=["JD detail may be incomplete; avoid over-specific claims."],
    )


def check_user_truth(context: CouncilContext, role_decode: RoleDecode) -> UserTruth:
    profile = context.user_profile
    confirmed = profile.get("confirmed_skills", []) or []
    weak = profile.get("weak_skills", []) or []
    master = context.master_profile.lower()
    unverified = []
    for skill in role_decode.must_have_skills:
        if not _skill_supported(skill, confirmed, master):
            unverified.append(skill)
    return UserTruth(
        confirmed_skills=confirmed,
        weak_skills=weak,
        unverified_skills=unverified,
        evidence_bank=_build_evidence_bank(profile, context.master_profile),
        strong_proof_points=confirmed[:8],
        claims_not_allowed=[f"Do not claim strong {s} ownership without evidence." for s in unverified],
        claims_to_soften=[f"Soften {s}; present as exposure or adjacent experience if true." for s in weak],
    )


def analyze_fit_gap(role_decode: RoleDecode, user_truth: UserTruth, job: dict) -> FitGapAnalysis:
    confirmed_l = [s.lower() for s in user_truth.confirmed_skills]
    matches = [s for s in role_decode.must_have_skills if s.lower() in confirmed_l]
    missing = [s for s in role_decode.must_have_skills if s not in matches]
    fit_score = job.get("fit_score") or 0
    stance = "STRONG_PUSH" if fit_score >= 75 and len(missing) <= 2 else "CAREFUL_POSITIONING"
    if fit_score < 50:
        stance = "SKIP_AFTER_INTEREST"
    elif fit_score < 60:
        stance = "STRETCH_APPLICATION"
    return FitGapAnalysis(
        strongest_matches=matches,
        missing_requirements=missing,
        risky_claims=user_truth.claims_not_allowed,
        interview_risks=[f"Interview may probe {s}." for s in missing[:5]],
        gaps_to_soften=user_truth.claims_to_soften,
        gaps_to_avoid=user_truth.claims_not_allowed,
        likely_recruiter_objections=_recruiter_objections(job, missing),
        application_stance=stance,
    )


def build_positioning(context: CouncilContext, company: CompanyIntelligence, role: RoleDecode, truth: UserTruth, gaps: FitGapAnalysis) -> PositioningStrategy:
    job = context.job
    title = job.get("title", job.get("role_title", "role"))
    company_name = job.get("company", "the company") or "the company"
    lead = truth.strong_proof_points[:4] or role.must_have_skills[:4]
    one_line = f"Practical AI/ML builder positioning for {title} at {company_name}."
    if any(k in role.likely_screening_keywords for k in ["llm", "rag", "gen ai", "genai"]):
        one_line = f"Practical AI systems engineer who can ship LLM workflows for {company_name}."
    return PositioningStrategy(
        one_line_positioning=one_line,
        narrative_angle="Lead with shipped/practical AI implementation, then show reliability and interview-defensible evidence.",
        lead_strengths=lead,
        downplay=gaps.missing_requirements[:5],
        tone=context.user_profile.get("resume_tone", "grounded, clear, specific"),
        recruiter_first_impression="Relevant AI/ML candidate with practical delivery orientation, not inflated research-heavy positioning.",
        company_specific_angle=company.positioning_implications[0] if company.positioning_implications else "Keep company-specific angle conservative until deeper research.",
    )


def build_resume_plan(role: RoleDecode, gaps: FitGapAnalysis, positioning: PositioningStrategy) -> ResumePlan:
    return ResumePlan(
        sections_to_change=["headline", "summary", "skills", "most relevant experience bullets"],
        sections_to_keep=["education", "chronology", "employer names", "dates"],
        skills_to_prioritize=role.likely_screening_keywords[:10],
        bullets_to_rewrite=["Rewrite only bullets with direct evidence for role requirements."],
        risky_claims=gaps.risky_claims,
        company_keywords=role.likely_screening_keywords[:8],
        do_not_touch=["Do not add unsupported metrics.", "Do not inflate seniority.", "Do not claim ownership that cannot be defended."],
    )


def assemble_application_pack(context: CouncilContext, positioning: PositioningStrategy, gaps: FitGapAnalysis, plan: ResumePlan) -> ApplicationPack:
    job = context.job
    company = job.get("company", "")
    role = job.get("title", job.get("role_title", ""))
    notice = context.user_profile.get("notice_period_days", "")
    salary_floor = context.user_profile.get("salary_floor_lakhs", "")
    summary = _review_summary(company, role, positioning, plan, gaps)
    return ApplicationPack(
        job_id=context.job_id,
        company=company,
        role=role,
        positioning=positioning.one_line_positioning,
        cover_note=f"I’m interested in {role} at {company} because it aligns with practical AI/ML implementation work.",
        why_this_company="Needs deeper company intelligence before final wording.",
        why_this_role="The role appears aligned with the user’s AI/ML target direction and should be positioned around practical delivery.",
        relevant_experience_answer="Use confirmed AI/ML evidence only; avoid unsupported claims flagged in the quality report.",
        notice_period_answer=f"Notice period: {notice} days. User must review before submission.",
        salary_expectation_placeholder=f"Expected compensation: discuss based on role scope; floor appears to be {salary_floor} LPA if current profile is accurate. User must review.",
        recruiter_message=f"Hi, I’m interested in the {role} role at {company}. My background is strongest where practical AI/ML engineering meets product delivery.",
        follow_up_message=f"Hi, following up on my application for {role}. Happy to share more context on my AI/ML implementation experience.",
        quality_report={
            "positioning": positioning.one_line_positioning,
            "main_risk": gaps.likely_recruiter_objections[0] if gaps.likely_recruiter_objections else "Insufficient company/JD detail.",
            "user_must_review": ["salary expectation", "notice period", "unsupported or softened skills"],
            "confidence": 65 if gaps.application_stance == "CAREFUL_POSITIONING" else 50,
            "application_stance": gaps.application_stance,
        },
        whatsapp_review_summary=summary,
    )


def _job_text(job: dict) -> str:
    return job.get("raw_description") or job.get("description") or job.get("jd_text") or ""


def _extract_keywords(text: str) -> list[str]:
    lower = text.lower()
    found = [k for k in AI_KEYWORDS if re.search(rf"\b{re.escape(k)}\b", lower)]
    return list(dict.fromkeys(found))


def _skill_supported(skill: str, confirmed: list[str], master_profile: str) -> bool:
    aliases = {
        "ai": ["artificial intelligence", "ai", "genai", "gen ai", "llm"],
        "ml": ["machine learning", "ml", "pytorch", "tensorflow"],
        "gen ai": ["genai", "generative ai", "llm"],
        "genai": ["gen ai", "generative ai", "llm"],
        "rag": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
        "llm": ["llm", "large language model", "large language models"],
    }
    haystack = " ".join(confirmed).lower() + " " + master_profile
    candidates = aliases.get(skill.lower(), [skill.lower()])
    return any(candidate in haystack for candidate in candidates)


def _infer_seniority(title: str) -> str:
    lower = title.lower()
    if any(k in lower for k in ["staff", "principal", "lead", "architect"]):
        return "senior/staff"
    if any(k in lower for k in ["senior", "sr.", "sr "]):
        return "senior"
    if any(k in lower for k in ["intern", "trainee"]):
        return "entry/intern"
    return "mid-level or unspecified"


def _build_evidence_bank(profile: dict, master_profile: str) -> list[str]:
    evidence = []
    for skill in profile.get("confirmed_skills", [])[:10]:
        evidence.append(f"Profile confirms: {skill}")
    if master_profile:
        evidence.append("Master profile/CV is available for section-level evidence checks.")
    else:
        evidence.append("No master CV found; council must stay conservative and use profile evidence only.")
    return evidence


def _recruiter_objections(job: dict, missing: list[str]) -> list[str]:
    objections = []
    if not job.get("raw_description") and not job.get("description"):
        objections.append("JD detail is thin; recruiter fit may be hard to prove in the first scan.")
    if not job.get("company"):
        objections.append("Company name missing; company-specific positioning is limited.")
    objections.extend([f"Potential gap: {s}" for s in missing[:3]])
    return objections


def _review_summary(company: str, role: str, positioning: PositioningStrategy, plan: ResumePlan, gaps: FitGapAnalysis) -> str:
    changed = "\n".join(f"- {s}" for s in plan.sections_to_change[:5])
    risks = "\n".join(f"- {r}" for r in (gaps.likely_recruiter_objections + gaps.gaps_to_soften)[:4])
    return (
        "Application pack ready.\n"
        f"Role: {role} — {company}\n\n"
        "Positioning:\n"
        f"{positioning.one_line_positioning}\n\n"
        "Changed:\n"
        f"{changed}\n\n"
        "Risks:\n"
        f"{risks}\n\n"
        "Reply:\n"
        "approve\nshow summary\nshow changes\nmake safer\nmake stronger"
    )
