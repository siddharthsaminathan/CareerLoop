"""
CareerLoop Follow-Up Queue — Track and surface due follow-ups.

Auto-schedules follow-up dates on APPLY.
Shows due follow-ups in daily brief.
Drafts follow-up messages.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional


class FollowUpQueue:
    """Manages application follow-ups."""

    FOLLOW_UP_DAYS = [5, 10, 17, 25]  # Days after application

    def __init__(self, ledger):
        self.ledger = ledger

    def schedule(self, job_id: str) -> list[str]:
        """Schedule follow-up dates for an APPLIED job."""
        entry = self.ledger.get_job(job_id)
        if not entry:
            return []

        now = datetime.now(timezone.utc)
        dates = [(now + timedelta(days=d)).isoformat() for d in self.FOLLOW_UP_DAYS]
        entry["follow_up_dates"] = dates
        self.ledger._save()
        return dates

    def get_due(self) -> list[dict]:
        """Get all follow-ups due today or overdue."""
        now = datetime.now(timezone.utc)
        due = []

        for entry in self.ledger.entries:
            status = entry.get("status", "")
            if status not in ("APPLIED", "FOLLOW_UP_DUE", "APPROVED"):
                continue

            dates = entry.get("follow_up_dates", [])
            for i, date_str in enumerate(dates):
                try:
                    due_date = datetime.fromisoformat(date_str)
                except (ValueError, TypeError):
                    continue

                if due_date <= now:
                    days_applied = (now - due_date + timedelta(days=self.FOLLOW_UP_DAYS[i])).days
                    due.append({
                        "job_id": entry.get("job_id", ""),
                        "company": entry.get("company", ""),
                        "role_title": entry.get("title", entry.get("role_title", "")),
                        "source_url": entry.get("source_url", ""),
                        "days_since_applied": days_applied,
                        "follow_up_date": date_str,
                        "follow_up_index": i + 1,
                        "suggested_message": self.draft_message(entry, i + 1),
                        "recruiter_name": entry.get("recruiter_name", "unknown"),
                        "recruiter_linkedin": entry.get("recruiter_linkedin", ""),
                    })
                    break  # Only show first due follow-up per job

        return due

    def draft_message(self, entry: dict, follow_up_number: int) -> str:
        """Draft a follow-up message."""
        company = entry.get("company", "the company")
        title = entry.get("title", entry.get("role_title", "the role"))
        recruiter = entry.get("recruiter_name", "Hiring Team")

        if follow_up_number == 1:
            return (
                f"Hi {recruiter},\n\n"
                f"I applied for the {title} role at {company} about a week ago "
                f"and wanted to follow up. I'm very interested and would love "
                f"to discuss how my experience could contribute.\n\n"
                f"Would you have time for a brief conversation this week?\n\n"
                f"Best,\nSiddharth"
            )
        elif follow_up_number == 2:
            return (
                f"Hi {recruiter},\n\n"
                f"I wanted to check in again regarding my application for the "
                f"{title} position at {company}. I remain very interested and "
                f"would appreciate any update on the hiring process.\n\n"
                f"Thank you for your time.\n\n"
                f"Best,\nSiddharth"
            )
        else:
            return (
                f"Hi {recruiter},\n\n"
                f"I'm following up one more time on my application for {title} "
                f"at {company}. If the position has been filled, I'd appreciate "
                f"knowing. If not, I'd love to discuss how I can contribute.\n\n"
                f"Thanks again for considering my application.\n\n"
                f"Best,\nSiddharth"
            )

    def mark_done(self, job_id: str) -> dict:
        """Mark the current follow-up as done."""
        entry = self.ledger.get_job(job_id)
        if not entry:
            return {"error": f"Job {job_id} not found"}

        dates = entry.get("follow_up_dates", [])
        if dates:
            dates.pop(0)  # Remove first (current) follow-up

        if dates:
            self.ledger.transition(job_id, "FOLLOW_UP_DUE", "Follow-up sent")
        else:
            self.ledger.transition(job_id, "APPLIED", "All follow-ups completed")

        self.ledger._save()
        return {"status": "ok", "remaining_follow_ups": len(dates)}

    def stats(self) -> dict:
        """Follow-up statistics."""
        due = self.get_due()
        all_due = 0
        for entry in self.ledger.entries:
            if entry.get("status") in ("APPLIED", "FOLLOW_UP_DUE") and entry.get("follow_up_dates"):
                all_due += 1

        return {
            "due_today": len(due),
            "total_with_follow_ups": all_due,
        }
