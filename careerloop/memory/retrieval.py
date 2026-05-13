"""
CareerLoop Memory Retrieval Layer — Multi-table context synthesis.

Provides high-level synchronous database queries to assemble complete
operational representations for the Daily Triage briefing and collaborative
chat interfaces, enforcing lazy loading for downstream systems.
"""

from typing import Optional, Any

from careerloop.memory.models import (
    UserModel,
    StrategicTrackModel,
    ApplicationLedgerModel,
    CompanyMemoryModel,
    PositioningMemoryModel,
    EventTimelineModel,
)
from careerloop.memory.repository import MemoryRepository


class MemoryRetrievalService:
    """Provides aggregated contextual briefings combining data from multiple entities."""

    def __init__(self, repository: MemoryRepository):
        self.repo = repository

    def get_triage_context_for_user(self, user_id: str) -> dict[str, Any]:
        """
        Assembles a uniform operational context packet to drive the 2-minute
        morning standup logic securely.
        """
        user = self.repo.get_user(user_id)
        if not user:
            # Create default state profile if completely missing
            user = UserModel(id=user_id)
            self.repo.save_user(user)

        tracks = self.repo.list_tracks_for_user(user_id)
        
        # Retrieve non-dormant jobs for active triage categorization
        all_jobs = self.repo.list_ledger_entries(user_id)
        active_jobs = [j for j in all_jobs if j.status not in ("ARCHIVED", "REJECTED")]
        
        # Determine actionable check-ins
        actionable_jobs = [j for j in all_jobs if j.status in ("SENT_TO_USER", "APPROVED", "FOLLOW_UP_DUE")]
        
        # Load immediate historical timeline
        recent_events = self.repo.list_recent_events(user_id, limit=30)
        
        # Extract normalized company tokens to prepare lazy-loaded intelligence keys
        company_names = {j.company_normalized for j in active_jobs if j.company_normalized}
        companies_memory = {}
        for cname in company_names:
            cm = self.repo.get_company_memory(cname)
            if cm:
                companies_memory[cname] = cm.to_dict()

        return {
            "user": user.to_dict(),
            "strategic_tracks": [t.to_dict() for t in tracks],
            "active_jobs_count": len(active_jobs),
            "actionable_jobs_count": len(actionable_jobs),
            "active_jobs": [j.to_dict() for j in active_jobs],
            "actionable_jobs": [j.to_dict() for j in actionable_jobs],
            "companies_memory": companies_memory,
            "recent_events": [e.to_dict() for e in recent_events],
        }

    def get_job_memory_card(self, job_fingerprint: str) -> Optional[dict[str, Any]]:
        """
        Retrieves a fully resolved composite data block serving as the immediate
        context card for collaborative chat interrogation queries.
        """
        job = self.repo.find_ledger_entry_by_fingerprint(job_fingerprint)
        if not job:
            return None

        track = None
        if job.track_id:
            track = self.repo.get_track(job.track_id)

        company_mem = self.repo.get_company_memory(job.company_normalized)
        
        positioning_history = self.repo.list_positioning_for_company(job.company_normalized)

        return {
            "job": job.to_dict(),
            "strategic_track": track.to_dict() if track else None,
            "company_memory": company_mem.to_dict() if company_mem else None,
            "positioning_history": [p.to_dict() for p in positioning_history],
            "is_lazy_loaded": company_mem is not None and bool(company_mem.company_intelligence),
        }
