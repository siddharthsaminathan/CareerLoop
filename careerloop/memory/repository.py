"""
CareerLoop Memory Repository — Uniform data persistence adapter.

Abstracts standard database operations (insert, update, select, list) for
the 6 canonical entities, utilizing the connection manager context safely.
"""

import json
from datetime import datetime, timezone
from typing import Optional, Any

from careerloop.memory.connection import get_connection
from careerloop.memory.models import (
    UserModel,
    StrategicTrackModel,
    ApplicationLedgerModel,
    CompanyMemoryModel,
    PositioningMemoryModel,
    EventTimelineModel,
)


class MemoryRepository:
    """Provides pure persistence interaction methods over SQLite tables."""

    def __init__(self, career_ops_root: Optional[str] = None):
        self.root = career_ops_root

    # ── USERS Repository ──────────────────────────────────────────────────

    def save_user(self, user: UserModel) -> UserModel:
        now = datetime.now(timezone.utc).isoformat()
        user.updated_at = now
        d = user.to_dict()

        with get_connection(self.root) as conn:
            conn.execute(
                """
                INSERT INTO users (
                    id, employment_state, urgency, burnout_level, preferred_environments,
                    startup_tolerance, compensation_floor_lakhs, compensation_target_lakhs,
                    work_style_prefs, emotional_constraints, interview_tolerance,
                    remote_pref, search_posture, created_at, updated_at
                ) VALUES (
                    :id, :employment_state, :urgency, :burnout_level, :preferred_environments,
                    :startup_tolerance, :compensation_floor_lakhs, :compensation_target_lakhs,
                    :work_style_prefs, :emotional_constraints, :interview_tolerance,
                    :remote_pref, :search_posture, :created_at, :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    employment_state=excluded.employment_state,
                    urgency=excluded.urgency,
                    burnout_level=excluded.burnout_level,
                    preferred_environments=excluded.preferred_environments,
                    startup_tolerance=excluded.startup_tolerance,
                    compensation_floor_lakhs=excluded.compensation_floor_lakhs,
                    compensation_target_lakhs=excluded.compensation_target_lakhs,
                    work_style_prefs=excluded.work_style_prefs,
                    emotional_constraints=excluded.emotional_constraints,
                    interview_tolerance=excluded.interview_tolerance,
                    remote_pref=excluded.remote_pref,
                    search_posture=excluded.search_posture,
                    updated_at=excluded.updated_at
                """,
                d,
            )
        return user

    def get_user(self, user_id: str) -> Optional[UserModel]:
        with get_connection(self.root) as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                return UserModel.from_row(dict(row))
        return None

    # ── STRATEGIC_TRACKS Repository ───────────────────────────────────────

    def save_track(self, track: StrategicTrackModel) -> StrategicTrackModel:
        now = datetime.now(timezone.utc).isoformat()
        track.updated_at = now
        d = track.to_dict()

        with get_connection(self.root) as conn:
            conn.execute(
                """
                INSERT INTO strategic_tracks (
                    id, user_id, track_identity, positioning_strategy,
                    resume_variant_id, outreach_style, success_metrics,
                    recruiter_response_patterns, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :track_identity, :positioning_strategy,
                    :resume_variant_id, :outreach_style, :success_metrics,
                    :recruiter_response_patterns, :created_at, :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    track_identity=excluded.track_identity,
                    positioning_strategy=excluded.positioning_strategy,
                    resume_variant_id=excluded.resume_variant_id,
                    outreach_style=excluded.outreach_style,
                    success_metrics=excluded.success_metrics,
                    recruiter_response_patterns=excluded.recruiter_response_patterns,
                    updated_at=excluded.updated_at
                """,
                d,
            )
        return track

    def get_track(self, track_id: str) -> Optional[StrategicTrackModel]:
        with get_connection(self.root) as conn:
            row = conn.execute("SELECT * FROM strategic_tracks WHERE id = ?", (track_id,)).fetchone()
            if row:
                return StrategicTrackModel.from_row(dict(row))
        return None

    def list_tracks_for_user(self, user_id: str) -> list[StrategicTrackModel]:
        with get_connection(self.root) as conn:
            rows = conn.execute("SELECT * FROM strategic_tracks WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
            return [StrategicTrackModel.from_row(dict(r)) for r in rows]

    # ── APPLICATION_LEDGER Repository ─────────────────────────────────────

    def save_ledger_entry(self, entry: ApplicationLedgerModel) -> ApplicationLedgerModel:
        now = datetime.now(timezone.utc).isoformat()
        entry.updated_at = now
        d = entry.to_dict()

        with get_connection(self.root) as conn:
            conn.execute(
                """
                INSERT INTO application_ledger (
                    id, user_id, track_id, job_fingerprint, title, company,
                    company_normalized, location, work_mode, status, application_url,
                    source, source_url, notes, recruiter_name, recruiter_contacted,
                    follow_up_due_at, interview_stage, interview_outcomes, fit_score,
                    fit_breakdown, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :track_id, :job_fingerprint, :title, :company,
                    :company_normalized, :location, :work_mode, :status, :application_url,
                    :source, :source_url, :notes, :recruiter_name, :recruiter_contacted,
                    :follow_up_due_at, :interview_stage, :interview_outcomes, :fit_score,
                    :fit_breakdown, :created_at, :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    track_id=excluded.track_id,
                    job_fingerprint=excluded.job_fingerprint,
                    title=excluded.title,
                    company=excluded.company,
                    company_normalized=excluded.company_normalized,
                    location=excluded.location,
                    work_mode=excluded.work_mode,
                    status=excluded.status,
                    application_url=excluded.application_url,
                    source=excluded.source,
                    source_url=excluded.source_url,
                    notes=excluded.notes,
                    recruiter_name=excluded.recruiter_name,
                    recruiter_contacted=excluded.recruiter_contacted,
                    follow_up_due_at=excluded.follow_up_due_at,
                    interview_stage=excluded.interview_stage,
                    interview_outcomes=excluded.interview_outcomes,
                    fit_score=excluded.fit_score,
                    fit_breakdown=excluded.fit_breakdown,
                    updated_at=excluded.updated_at
                """,
                d,
            )
        return entry

    def get_ledger_entry(self, entry_id: str) -> Optional[ApplicationLedgerModel]:
        with get_connection(self.root) as conn:
            row = conn.execute("SELECT * FROM application_ledger WHERE id = ?", (entry_id,)).fetchone()
            if row:
                return ApplicationLedgerModel.from_row(dict(row))
        return None

    def find_ledger_entry_by_fingerprint(self, fingerprint: str) -> Optional[ApplicationLedgerModel]:
        with get_connection(self.root) as conn:
            row = conn.execute("SELECT * FROM application_ledger WHERE job_fingerprint = ?", (fingerprint,)).fetchone()
            if row:
                return ApplicationLedgerModel.from_row(dict(row))
        return None

    def list_ledger_entries(self, user_id: str, status: Optional[str] = None) -> list[ApplicationLedgerModel]:
        sql = "SELECT * FROM application_ledger WHERE user_id = ?"
        params: list[Any] = [user_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC"

        with get_connection(self.root) as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [ApplicationLedgerModel.from_row(dict(r)) for r in rows]

    # ── COMPANY_MEMORY Repository ─────────────────────────────────────────

    def save_company_memory(self, memory: CompanyMemoryModel) -> CompanyMemoryModel:
        now = datetime.now(timezone.utc).isoformat()
        memory.updated_at = now
        d = memory.to_dict()

        with get_connection(self.root) as conn:
            conn.execute(
                """
                INSERT INTO company_memory (
                    id, company_normalized, company_intelligence, compensation_analysis,
                    hiring_urgency, recruiter_insights, glassdoor_synthesis,
                    company_maturity, org_structure_patterns, startup_risk,
                    work_culture_patterns, known_interview_loops, created_at, updated_at
                ) VALUES (
                    :id, :company_normalized, :company_intelligence, :compensation_analysis,
                    :hiring_urgency, :recruiter_insights, :glassdoor_synthesis,
                    :company_maturity, :org_structure_patterns, :startup_risk,
                    :work_culture_patterns, :known_interview_loops, :created_at, :updated_at
                )
                ON CONFLICT(company_normalized) DO UPDATE SET
                    company_intelligence=excluded.company_intelligence,
                    compensation_analysis=excluded.compensation_analysis,
                    hiring_urgency=excluded.hiring_urgency,
                    recruiter_insights=excluded.recruiter_insights,
                    glassdoor_synthesis=excluded.glassdoor_synthesis,
                    company_maturity=excluded.company_maturity,
                    org_structure_patterns=excluded.org_structure_patterns,
                    startup_risk=excluded.startup_risk,
                    work_culture_patterns=excluded.work_culture_patterns,
                    known_interview_loops=excluded.known_interview_loops,
                    updated_at=excluded.updated_at
                """,
                d,
            )
        return memory

    def get_company_memory(self, company_normalized: str) -> Optional[CompanyMemoryModel]:
        with get_connection(self.root) as conn:
            row = conn.execute("SELECT * FROM company_memory WHERE company_normalized = ?", (company_normalized,)).fetchone()
            if row:
                return CompanyMemoryModel.from_row(dict(row))
        return None

    # ── POSITIONING_MEMORY Repository ─────────────────────────────────────

    def save_positioning_memory(self, positioning: PositioningMemoryModel) -> PositioningMemoryModel:
        d = positioning.to_dict()
        with get_connection(self.root) as conn:
            conn.execute(
                """
                INSERT INTO positioning_memory (
                    id, user_id, track_id, company_normalized, generated_narrative,
                    framing_strategy, successful_tone, rejected_tone,
                    recruiter_positive_patterns, converted, created_at
                ) VALUES (
                    :id, :user_id, :track_id, :company_normalized, :generated_narrative,
                    :framing_strategy, :successful_tone, :rejected_tone,
                    :recruiter_positive_patterns, :converted, :created_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    generated_narrative=excluded.generated_narrative,
                    framing_strategy=excluded.framing_strategy,
                    successful_tone=excluded.successful_tone,
                    rejected_tone=excluded.rejected_tone,
                    recruiter_positive_patterns=excluded.recruiter_positive_patterns,
                    converted=excluded.converted
                """,
                d,
            )
        return positioning

    def list_positioning_for_company(self, company_normalized: str) -> list[PositioningMemoryModel]:
        with get_connection(self.root) as conn:
            rows = conn.execute(
                "SELECT * FROM positioning_memory WHERE company_normalized = ? ORDER BY created_at DESC",
                (company_normalized,),
            ).fetchall()
            return [PositioningMemoryModel.from_row(dict(r)) for r in rows]

    # ── EVENT_TIMELINE Repository ─────────────────────────────────────────

    def log_event(self, event: EventTimelineModel) -> EventTimelineModel:
        d = event.to_dict()
        with get_connection(self.root) as conn:
            conn.execute(
                """
                INSERT INTO event_timeline (
                    id, user_id, event_type, reference_id, reference_type, details, created_at
                ) VALUES (
                    :id, :user_id, :event_type, :reference_id, :reference_type, :details, :created_at
                )
                """,
                d,
            )
        return event

    def list_recent_events(self, user_id: str, limit: int = 50) -> list[EventTimelineModel]:
        with get_connection(self.root) as conn:
            rows = conn.execute(
                "SELECT * FROM event_timeline WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [EventTimelineModel.from_row(dict(r)) for r in rows]
