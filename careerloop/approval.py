"""
CareerLoop Approval Workflow — APPLY / SKIP / MAYBE / NEXT / DETAILS.

Updates ledger. Captures skip reasons. Generates application pack for APPLY.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from careerloop.models import Decision


class ApprovalWorkflow:
    """Handles user decisions on shortlisted jobs."""

    def __init__(self, ledger):
        self.ledger = ledger

    def approve(self, job_id: str) -> dict:
        """User wants to apply. Transition to APPROVED."""
        entry = self.ledger.get_job(job_id)
        if not entry:
            return {"error": f"Job {job_id} not found"}

        self.ledger.transition(job_id, "APPROVED", "User approved for application")

        # Set follow-up schedule: 5, 10, 17, 25 days from now
        now = datetime.now(timezone.utc)
        entry = self.ledger.get_job(job_id)
        entry["follow_up_dates"] = [
            (now + timedelta(days=d)).isoformat() for d in [5, 10, 17, 25]
        ]
        self.ledger._save()

        return {
            "status": "APPROVED",
            "job_id": job_id,
            "resume_needed": True,
            "application_url": entry.get("source_url") or entry.get("application_url", ""),
            "why_apply": entry.get("fit_result", {}).get("why_user_might_like_it", ""),
            "risks": entry.get("fit_result", {}).get("risks", []),
            "next_action": "Prepare resume and apply",
            "follow_up_at": entry["follow_up_dates"][0],
        }

    def skip(self, job_id: str, reason: str = "") -> dict:
        """User wants to skip. Capture reason if available."""
        entry = self.ledger.get_job(job_id)
        if not entry:
            return {"error": f"Job {job_id} not found"}

        reason_text = reason or "No reason provided"
        self.ledger.transition(job_id, "SKIPPED", f"User skipped: {reason_text}")

        # Store skip reason for learning
        entry = self.ledger.get_job(job_id)
        entry["skip_reason"] = reason_text
        self.ledger._save()

        return {
            "status": "SKIPPED",
            "job_id": job_id,
            "reason": reason_text,
        }

    def maybe(self, job_id: str, note: str = "") -> dict:
        """User bookmarked for later. Store concern."""
        entry = self.ledger.get_job(job_id)
        if not entry:
            return {"error": f"Job {job_id} not found"}

        self.ledger.transition(job_id, "MAYBE", f"User bookmarked: {note}" if note else "User bookmarked")

        entry = self.ledger.get_job(job_id)
        entry["maybe_note"] = note
        self.ledger._save()

        return {
            "status": "MAYBE",
            "job_id": job_id,
            "note": note,
        }

    def process_decision(self, job_id: str, decision: str, reason: str = "") -> dict:
        """Route user decision to correct handler."""
        decision = decision.upper().strip()

        if decision in ("APPLY", "1"):
            return self.approve(job_id)
        elif decision in ("SKIP", "2"):
            return self.skip(job_id, reason)
        elif decision in ("MAYBE", "3"):
            return self.maybe(job_id, reason)
        else:
            return {"error": f"Unknown decision: {decision}. Use APPLY, SKIP, or MAYBE."}
