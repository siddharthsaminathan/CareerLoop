"""
Resume Council v3.0 (8-System Architecture) Data Models.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, List, Optional, Dict


class VisibilityClass(str, Enum):
    PUBLIC = "PUBLIC_APPLICATION_CONTENT"
    PRIVATE = "PRIVATE_STRATEGY_METADATA"
    UNKNOWN = "UNKNOWN"


@dataclass
class ResumeSection:
    section_id: str
    section_title: str
    normalized_type: str  # e.g. summary, contact, experience, skills, education, projects, custom
    visibility_class: VisibilityClass
    raw_text: str
    original_order: int = 0
    links: List[str] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CanonicalResume:
    person_id: str = "default"
    sections: List[ResumeSection] = field(default_factory=list)
    parse_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "person_id": self.person_id,
            "sections": [s.to_dict() for s in self.sections],
            "parse_warnings": self.parse_warnings
        }


@dataclass
class PreservationContract:
    required_public_sections: List[str] = field(default_factory=list)
    sections_to_exclude: List[str] = field(default_factory=list)
    unknown_sections_to_preserve: List[str] = field(default_factory=list)
    ordering_rules: List[str] = field(default_factory=list)
    link_preservation_rules: Dict[str, Any] = field(default_factory=dict)
    max_allowed_changes: int = 3

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CompanyIntelligence:
    summary: str = ""
    business_model: str = ""
    india_presence: str = "UNKNOWN"
    maturity: str = ""  # startup, growth, enterprise
    hiring_urgency: str = "MEDIUM"
    culture_signals: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    positioning_implications: str = ""
    interview_implications: str = ""
    confidence: float = 0.0
    missing_data: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RoleDecode:
    normalized_title: str = ""
    seniority: str = ""
    must_haves: List[str] = field(default_factory=list)
    nice_to_haves: List[str] = field(default_factory=list)
    hidden_expectations: List[str] = field(default_factory=list)
    day_one_deliverables: List[str] = field(default_factory=list)
    screening_keywords: List[str] = field(default_factory=list)
    disqualifiers: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UserTruth:
    total_years_experience: float = 0.0
    confirmed_skills: List[Dict[str, str]] = field(default_factory=list)
    weak_skills: List[str] = field(default_factory=list)
    evidence_bank: Dict[str, List[str]] = field(default_factory=dict)
    strongest_proof_points: List[str] = field(default_factory=list)
    claims_allowed: List[str] = field(default_factory=list)
    claims_not_allowed: List[str] = field(default_factory=list)
    private_constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PositioningStrategy:
    one_line_positioning: str = ""
    narrative_angle: str = ""
    lead_strengths: List[str] = field(default_factory=list)
    proof_points_to_emphasize: List[str] = field(default_factory=list)
    things_to_downplay: List[str] = field(default_factory=list)
    tone_guidance: str = ""
    recruiter_first_impression_target: str = ""
    application_stance: str = "HOLD"  # STRONG_PUSH, CAREFUL_PUSH, STRETCH, HOLD, SKIP
    reasoning: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SectionRewrite:
    section_id: str
    original_text: str
    rewritten_text: str
    change_type: str  # KEEP, LIGHT_EDIT, REWRITE, REMOVE_PRIVATE
    change_reason: str
    claims_added: List[str] = field(default_factory=list)
    claims_removed: List[str] = field(default_factory=list)
    evidence_used: List[str] = field(default_factory=list)
    risk_level: str = "low"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SectionRewrites:
    rewrites: Dict[str, SectionRewrite] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"rewrites": {k: v.to_dict() for k, v in self.rewrites.items()}}


class CouncilIntent(str, Enum):
    INTERESTED = "INTERESTED"
    APPLY = "APPLY"
    PREPARE_APPLICATION = "PREPARE_APPLICATION"


@dataclass
class CouncilContext:
    job_id: str
    intent: CouncilIntent
    user_profile: dict
    job: dict
    master_profile: str = ""
    previous_feedback: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["intent"] = self.intent.value
        return d


@dataclass
class QualityReport:
    what_changed: List[str] = field(default_factory=list)
    what_did_not_change: List[str] = field(default_factory=list)
    needs_user_review: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ApplicationPack:
    resume_markdown: str = ""
    cover_note: str = ""
    screening_answers: str = ""
    recruiter_message: str = ""
    follow_up_message: str = ""
    quality_report: Optional[QualityReport] = None
    user_review_summary: str = ""

    def to_dict(self) -> dict:
        return {
            "resume_markdown": self.resume_markdown,
            "cover_note": self.cover_note,
            "screening_answers": self.screening_answers,
            "recruiter_message": self.recruiter_message,
            "follow_up_message": self.follow_up_message,
            "quality_report": self.quality_report.to_dict() if self.quality_report else None,
            "user_review_summary": self.user_review_summary
        }


@dataclass
class CouncilResult:
    job_id: str
    allowed: bool = True
    reason: str = ""
    context: Optional[CouncilContext] = None
    person_id: str = "default"
    canonical_resume: Optional[CanonicalResume] = None
    preservation_contract: Optional[PreservationContract] = None
    company_intelligence: Optional[CompanyIntelligence] = None
    role_decode: Optional[RoleDecode] = None
    user_truth: Optional[UserTruth] = None
    positioning_strategy: Optional[PositioningStrategy] = None
    section_rewrites: Optional[SectionRewrites] = None
    application_pack: Optional[ApplicationPack] = None
    output_dir: str = ""

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "allowed": self.allowed,
            "reason": self.reason,
            "context": self.context.to_dict() if self.context else None,
            "person_id": self.person_id,
            "canonical_resume": self.canonical_resume.to_dict() if self.canonical_resume else None,
            "preservation_contract": self.preservation_contract.to_dict() if self.preservation_contract else None,
            "company_intelligence": self.company_intelligence.to_dict() if self.company_intelligence else None,
            "role_decode": self.role_decode.to_dict() if self.role_decode else None,
            "user_truth": self.user_truth.to_dict() if self.user_truth else None,
            "positioning_strategy": self.positioning_strategy.to_dict() if self.positioning_strategy else None,
            "section_rewrites": self.section_rewrites.to_dict() if self.section_rewrites else None,
            "application_pack": self.application_pack.to_dict() if self.application_pack else None,
            "output_dir": self.output_dir,
        }
