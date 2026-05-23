"""
CareerLoop Application Ledger — Lifecycle tracker for every job.

JSON-based ledger with CareerLoop lifecycle states.
Each job gets a unique ID, status history, and full audit trail.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from careerloop.config import (
    LEDGER_STATUSES,
    DORMANT_STATUSES,
    ACTIVE_STATUSES,
    ACTION_REQUIRED_STATUSES,
    FOLLOW_UP_SCHEDULE,
)


class ApplicationLedger:
    """
    JSON-based job lifecycle tracker.

    File: careerloop/ledger.json

    Each entry:
    {
        "job_id": "loop-001",
        "title": "...",
        "company": "...",
        "location": "...",
        "source": "greenhouse-api",
        "source_url": "...",
        "status": "DISCOVERED",
        "status_history": [{"status": "DISCOVERED", "date": "...", "reason": "scan.mjs"}],
        "fit_score": null,
        "fit_breakdown": null,
        "user_decision": null,
        "decision_reason": null,
        "follow_up_dates": [],
        "recruiter_name": null,
        "recruiter_linkedin": null,
        "recruiter_email": null,
        "notes": "",
        "created_at": "...",
        "updated_at": "..."
    }
    """

    def __init__(self, career_ops_root: str):
        self.root = career_ops_root
        self.path = os.path.join(career_ops_root, "careerloop", "ledger.json")
        self.entries: list[dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path) as f:
                self.entries = json.load(f)
        else:
            self.entries = []
            self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(self.entries, f, indent=2, default=str)
        os.replace(tmp_path, self.path)

    # ── CRUD ─────────────────────────────────────────────────────────

    def add_job(self, job: dict, source: str = "unknown") -> str:
        """Add a newly discovered job. Returns job_id."""
        job_id = f"loop-{len(self.entries) + 1:04d}"
        now = datetime.now(timezone.utc).isoformat()

        entry = {
            "job_id": job_id,
            "title": job.get("role_title") or job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "source": source,
            "source_url": job.get("url") or job.get("source_url", ""),
            "application_url": job.get("application_url") or job.get("apply_url", ""),
            "raw_description": job.get("raw_description") or job.get("description") or job.get("jd_text", ""),
            "description": job.get("description") or job.get("raw_description") or job.get("jd_text", ""),
            "work_mode": job.get("work_mode", ""),
            "salary_range": job.get("salary_range") or job.get("salary", ""),
            "skills_required": job.get("skills_required") or job.get("skills", []),
            "status": "DISCOVERED",
            "status_history": [
                {"status": "DISCOVERED", "date": now, "reason": f"Discovered via {source}"}
            ],
            "fit_score": None,
            "fit_breakdown": None,
            "user_decision": None,
            "decision_reason": None,
            "follow_up_dates": [],
            "recruiter_name": None,
            "recruiter_linkedin": None,
            "recruiter_email": None,
            "notes": "",
            "created_at": now,
            "updated_at": now,
        }
        self.entries.append(entry)
        self._save()
        return job_id

    def get_job(self, job_id: str) -> Optional[dict]:
        for e in self.entries:
            if e["job_id"] == job_id:
                return e
        return None

    def find_by_url(self, url: str) -> Optional[dict]:
        for e in self.entries:
            if e.get("source_url") == url:
                return e
        return None

    def find_by_company_role(self, company: str, title: str) -> Optional[dict]:
        cl = company.lower().strip()
        tl = title.lower().strip()
        for e in self.entries:
            if e["company"].lower().strip() == cl and e["title"].lower().strip() == tl:
                return e
        return None

    def transition(self, job_id: str, new_status: str, reason: str = ""):
        """Update job status with audit trail."""
        if new_status not in LEDGER_STATUSES:
            raise ValueError(f"Invalid status: {new_status}. Valid: {LEDGER_STATUSES}")

        entry = self.get_job(job_id)
        if not entry:
            raise ValueError(f"Job {job_id} not found")

        entry["status"] = new_status
        entry["status_history"].append({
            "status": new_status,
            "date": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        })
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Auto-schedule follow-ups when status becomes APPLIED
        if new_status == "APPLIED":
            from datetime import timedelta
            applied_date = datetime.now(timezone.utc)
            entry["follow_up_dates"] = [
                (applied_date + timedelta(days=d)).isoformat()
                for d in FOLLOW_UP_SCHEDULE
            ]

        # When follow-up is done, mark as done
        if new_status == "FOLLOW_UP_DUE":
            # Remove the first pending follow-up date
            if entry.get("follow_up_dates"):
                entry["follow_up_dates"].pop(0)

        self._save()

    def set_fit_score(self, job_id: str, score: float, breakdown: dict):
        entry = self.get_job(job_id)
        if entry:
            entry["fit_score"] = score
            entry["fit_breakdown"] = breakdown
            entry["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save()

    # ── Queries ──────────────────────────────────────────────────────

    def get_active_jobs(self) -> list[dict]:
        """Jobs in active pipeline (not dormant)."""
        return [e for e in self.entries if e["status"] not in DORMANT_STATUSES]

    def get_jobs_needing_action(self) -> list[dict]:
        """Jobs that need user action today."""
        return [e for e in self.entries if e["status"] in ACTION_REQUIRED_STATUSES]

    def get_follow_ups_due(self) -> list[dict]:
        """Jobs where follow-up is due or overdue."""
        now = datetime.now(timezone.utc)
        due = []
        for e in self.entries:
            if e["status"] in ("APPLIED", "FOLLOW_UP_DUE"):
                for fud in e.get("follow_up_dates", []):
                    if isinstance(fud, str):
                        fud_dt = datetime.fromisoformat(fud)
                    else:
                        fud_dt = fud
                    if fud_dt <= now and fud_dt > now.replace(hour=0, minute=0, second=0):
                        due.append(e)
                        break
        return due

    def get_by_status(self, status: str) -> list[dict]:
        return [e for e in self.entries if e["status"] == status]

    def get_top_scored(self, min_score: float = 60, limit: int = 10) -> list[dict]:
        """Top scored jobs that haven't been shown yet."""
        candidates = [
            e for e in self.entries
            if e["status"] in ("DISCOVERED", "SHORTLISTED")
            and e.get("fit_score") is not None
            and e["fit_score"] >= min_score
        ]
        candidates.sort(key=lambda x: x.get("fit_score", 0), reverse=True)
        return candidates[:limit]

    def is_duplicate(self, url: str = "", company: str = "", title: str = "") -> bool:
        """Check if this job already exists in the ledger."""
        if url:
            if self.find_by_url(url):
                return True
        if company and title:
            if self.find_by_company_role(company, title):
                return True
        return False

    # ── Stats ────────────────────────────────────────────────────────

    def stats(self) -> dict:
        counts = {s: 0 for s in LEDGER_STATUSES}
        for e in self.entries:
            counts[e["status"]] = counts.get(e["status"], 0) + 1

        scored = [e for e in self.entries if e.get("fit_score") is not None]
        avg_score = sum(e["fit_score"] for e in scored) / len(scored) if scored else 0

        return {
            "total_jobs": len(self.entries),
            "by_status": counts,
            "active_count": len(self.get_active_jobs()),
            "scored_count": len(scored),
            "avg_fit_score": round(avg_score, 1),
            "follow_ups_due": len(self.get_follow_ups_due()),
        }
