"""
CareerLoop Memory Domain Models — Typed representations for local SQLite persistence.

Maps raw database rows to strongly typed dataclasses supporting JSON field
serialization/deserialization automatically.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Any


@dataclass
class UserModel:
    id: str
    employment_state: str = "employed_passive"
    urgency: int = 5
    burnout_level: int = 5
    preferred_environments: list[str] = field(default_factory=list)
    startup_tolerance: int = 5
    compensation_floor_lakhs: float = 0.0
    compensation_target_lakhs: float = 0.0
    work_style_prefs: dict[str, Any] = field(default_factory=dict)
    emotional_constraints: dict[str, Any] = field(default_factory=dict)
    interview_tolerance: str = "standard"
    remote_pref: str = "hybrid"
    search_posture: str = "EXPLORE"
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @classmethod
    def from_row(cls, row: dict) -> "UserModel":
        return cls(
            id=row["id"],
            employment_state=row["employment_state"],
            urgency=row["urgency"],
            burnout_level=row["burnout_level"],
            preferred_environments=json.loads(row["preferred_environments"]) if row["preferred_environments"] else [],
            startup_tolerance=row["startup_tolerance"],
            compensation_floor_lakhs=row["compensation_floor_lakhs"],
            compensation_target_lakhs=row["compensation_target_lakhs"],
            work_style_prefs=json.loads(row["work_style_prefs"]) if row["work_style_prefs"] else {},
            emotional_constraints=json.loads(row["emotional_constraints"]) if row["emotional_constraints"] else {},
            interview_tolerance=row["interview_tolerance"],
            remote_pref=row["remote_pref"],
            search_posture=row["search_posture"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["preferred_environments"] = json.dumps(self.preferred_environments)
        d["work_style_prefs"] = json.dumps(self.work_style_prefs)
        d["emotional_constraints"] = json.dumps(self.emotional_constraints)
        return d


@dataclass
class StrategicTrackModel:
    id: str
    user_id: str
    track_identity: str
    positioning_strategy: str = ""
    resume_variant_id: str = ""
    outreach_style: str = ""
    success_metrics: dict[str, Any] = field(default_factory=dict)
    recruiter_response_patterns: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @classmethod
    def from_row(cls, row: dict) -> "StrategicTrackModel":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            track_identity=row["track_identity"],
            positioning_strategy=row["positioning_strategy"],
            resume_variant_id=row["resume_variant_id"],
            outreach_style=row["outreach_style"],
            success_metrics=json.loads(row["success_metrics"]) if row["success_metrics"] else {},
            recruiter_response_patterns=json.loads(row["recruiter_response_patterns"]) if row["recruiter_response_patterns"] else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["success_metrics"] = json.dumps(self.success_metrics)
        d["recruiter_response_patterns"] = json.dumps(self.recruiter_response_patterns)
        return d


@dataclass
class ApplicationLedgerModel:
    id: str
    user_id: str
    job_fingerprint: str
    title: str
    company: str
    company_normalized: str
    track_id: Optional[str] = None
    location: str = ""
    work_mode: str = ""
    status: str = "DISCOVERED"
    application_url: str = ""
    source: str = "unknown"
    source_url: str = ""
    notes: str = ""
    recruiter_name: str = ""
    recruiter_contacted: bool = False
    follow_up_due_at: Optional[str] = None
    interview_stage: str = ""
    interview_outcomes: dict[str, Any] = field(default_factory=dict)
    fit_score: Optional[float] = None
    fit_breakdown: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @classmethod
    def from_row(cls, row: dict) -> "ApplicationLedgerModel":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            track_id=row["track_id"],
            job_fingerprint=row["job_fingerprint"],
            title=row["title"],
            company=row["company"],
            company_normalized=row["company_normalized"],
            location=row["location"],
            work_mode=row["work_mode"],
            status=row["status"],
            application_url=row["application_url"],
            source=row["source"],
            source_url=row["source_url"],
            notes=row["notes"],
            recruiter_name=row["recruiter_name"],
            recruiter_contacted=bool(row["recruiter_contacted"]),
            follow_up_due_at=row["follow_up_due_at"],
            interview_stage=row["interview_stage"],
            interview_outcomes=json.loads(row["interview_outcomes"]) if row["interview_outcomes"] else {},
            fit_score=row["fit_score"],
            fit_breakdown=json.loads(row["fit_breakdown"]) if row["fit_breakdown"] else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["recruiter_contacted"] = int(self.recruiter_contacted)
        d["interview_outcomes"] = json.dumps(self.interview_outcomes)
        d["fit_breakdown"] = json.dumps(self.fit_breakdown)
        return d


@dataclass
class CompanyMemoryModel:
    id: str
    company_normalized: str
    company_intelligence: str = ""
    compensation_analysis: str = ""
    hiring_urgency: str = ""
    recruiter_insights: str = ""
    glassdoor_synthesis: str = ""
    company_maturity: str = ""
    org_structure_patterns: str = ""
    startup_risk: float = 5.0
    work_culture_patterns: str = ""
    known_interview_loops: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @classmethod
    def from_row(cls, row: dict) -> "CompanyMemoryModel":
        return cls(
            id=row["id"],
            company_normalized=row["company_normalized"],
            company_intelligence=row["company_intelligence"],
            compensation_analysis=row["compensation_analysis"],
            hiring_urgency=row["hiring_urgency"],
            recruiter_insights=row["recruiter_insights"],
            glassdoor_synthesis=row["glassdoor_synthesis"],
            company_maturity=row["company_maturity"],
            org_structure_patterns=row["org_structure_patterns"],
            startup_risk=row["startup_risk"],
            work_culture_patterns=row["work_culture_patterns"],
            known_interview_loops=row["known_interview_loops"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PositioningMemoryModel:
    id: str
    user_id: str
    track_id: str
    company_normalized: str
    generated_narrative: str
    framing_strategy: str = ""
    successful_tone: str = ""
    rejected_tone: str = ""
    recruiter_positive_patterns: dict[str, Any] = field(default_factory=dict)
    converted: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @classmethod
    def from_row(cls, row: dict) -> "PositioningMemoryModel":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            track_id=row["track_id"],
            company_normalized=row["company_normalized"],
            generated_narrative=row["generated_narrative"],
            framing_strategy=row["framing_strategy"],
            successful_tone=row["successful_tone"],
            rejected_tone=row["rejected_tone"],
            recruiter_positive_patterns=json.loads(row["recruiter_positive_patterns"]) if row["recruiter_positive_patterns"] else {},
            converted=bool(row["converted"]),
            created_at=row["created_at"],
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["converted"] = int(self.converted)
        d["recruiter_positive_patterns"] = json.dumps(self.recruiter_positive_patterns)
        return d


@dataclass
class EventTimelineModel:
    id: str
    user_id: str
    event_type: str
    reference_id: str = ""
    reference_type: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @classmethod
    def from_row(cls, row: dict) -> "EventTimelineModel":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            event_type=row["event_type"],
            reference_id=row["reference_id"],
            reference_type=row["reference_type"],
            details=json.loads(row["details"]) if row["details"] else {},
            created_at=row["created_at"],
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["details"] = json.dumps(self.details)
        return d
