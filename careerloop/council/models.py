"""
Resume Council data contracts for one-job application intelligence.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class CouncilIntent(str, Enum):
    INTERESTED = "INTERESTED"
    APPLY = "APPLY"
    PREPARE_APPLICATION = "PREPARE_APPLICATION"


@dataclass
class CompanyIntelligence:
    company_summary: str = ""
    why_this_role_exists: str = ""
    company_maturity: str = ""
    hiring_urgency: str = ""
    likely_screening_filters: list[str] = field(default_factory=list)
    culture_signals: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    positioning_implications: list[str] = field(default_factory=list)
    interview_implications: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RoleDecode:
    must_have_skills: list[str] = field(default_factory=list)
    nice_to_have_skills: list[str] = field(default_factory=list)
    hidden_expectations: list[str] = field(default_factory=list)
    seniority_level: str = ""
    stakeholder_load: str = ""
    technical_depth: str = ""
    likely_screening_keywords: list[str] = field(default_factory=list)
    likely_interview_topics: list[str] = field(default_factory=list)
    application_risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UserTruth:
    confirmed_skills: list[str] = field(default_factory=list)
    weak_skills: list[str] = field(default_factory=list)
    unverified_skills: list[str] = field(default_factory=list)
    evidence_bank: list[str] = field(default_factory=list)
    strong_proof_points: list[str] = field(default_factory=list)
    claims_not_allowed: list[str] = field(default_factory=list)
    claims_to_soften: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FitGapAnalysis:
    strongest_matches: list[str] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)
    risky_claims: list[str] = field(default_factory=list)
    interview_risks: list[str] = field(default_factory=list)
    gaps_to_soften: list[str] = field(default_factory=list)
    gaps_to_avoid: list[str] = field(default_factory=list)
    likely_recruiter_objections: list[str] = field(default_factory=list)
    application_stance: str = "CAREFUL_POSITIONING"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PositioningStrategy:
    one_line_positioning: str = ""
    narrative_angle: str = ""
    lead_strengths: list[str] = field(default_factory=list)
    downplay: list[str] = field(default_factory=list)
    tone: str = "grounded, clear, specific"
    recruiter_first_impression: str = ""
    company_specific_angle: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResumePlan:
    sections_to_change: list[str] = field(default_factory=list)
    sections_to_keep: list[str] = field(default_factory=list)
    skills_to_prioritize: list[str] = field(default_factory=list)
    bullets_to_rewrite: list[str] = field(default_factory=list)
    risky_claims: list[str] = field(default_factory=list)
    company_keywords: list[str] = field(default_factory=list)
    do_not_touch: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ApplicationPack:
    job_id: str
    company: str
    role: str
    positioning: str
    cover_note: str = ""
    why_this_company: str = ""
    why_this_role: str = ""
    relevant_experience_answer: str = ""
    notice_period_answer: str = ""
    salary_expectation_placeholder: str = ""
    recruiter_message: str = ""
    follow_up_message: str = ""
    quality_report: dict[str, Any] = field(default_factory=dict)
    whatsapp_review_summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CouncilContext:
    job_id: str
    intent: CouncilIntent
    user_profile: dict[str, Any]
    job: dict[str, Any]
    master_profile: str = ""
    previous_feedback: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["intent"] = self.intent.value
        return d


@dataclass
class CouncilResult:
    allowed: bool
    reason: str
    context: Optional[CouncilContext] = None
    company_intelligence: Optional[CompanyIntelligence] = None
    role_decode: Optional[RoleDecode] = None
    user_truth: Optional[UserTruth] = None
    fit_gap_analysis: Optional[FitGapAnalysis] = None
    positioning_strategy: Optional[PositioningStrategy] = None
    resume_plan: Optional[ResumePlan] = None
    application_pack: Optional[ApplicationPack] = None

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "context": self.context.to_dict() if self.context else None,
            "company_intelligence": self.company_intelligence.to_dict() if self.company_intelligence else None,
            "role_decode": self.role_decode.to_dict() if self.role_decode else None,
            "user_truth": self.user_truth.to_dict() if self.user_truth else None,
            "fit_gap_analysis": self.fit_gap_analysis.to_dict() if self.fit_gap_analysis else None,
            "positioning_strategy": self.positioning_strategy.to_dict() if self.positioning_strategy else None,
            "resume_plan": self.resume_plan.to_dict() if self.resume_plan else None,
            "application_pack": self.application_pack.to_dict() if self.application_pack else None,
        }
