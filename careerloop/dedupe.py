"""
CareerLoop Dedupe Engine — Fingerprint-based deduplication with merge support.

Rules:
- Same fingerprint → same job (merge sources, DON'T duplicate)
- APPLIED jobs → never shown as new
- SKIPPED jobs → not shown again unless user asks
- Reposts → marked as REPOSTED, not NEW
- Stale jobs → flagged if older than threshold
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from careerloop.models import JobPosting


class DedupeEngine:
    """
    Fingerprint-based deduplication engine.

    Maintains a set of seen fingerprints across all sources.
    Merges alternate sources when same job found in multiple places.
    """

    def __init__(self, stale_days: int = 30):
        self._seen_fingerprints: dict[str, str] = {}  # fp → job_id
        self._applied_fingerprints: set[str] = set()
        self._skipped_fingerprints: set[str] = set()
        self._archived_fingerprints: set[str] = set()
        self.stale_days = stale_days

    def load_from_ledger(self, ledger_entries: list[dict]):
        """Load existing fingerprints from the application ledger."""
        for entry in ledger_entries:
            fp = entry.get("fingerprint") or entry.get("job", {}).get("fingerprint", "")
            if not fp:
                continue
            job_id = entry.get("job_id", "")
            status = entry.get("status", "")

            self._seen_fingerprints[fp] = job_id

            if status == "APPLIED":
                self._applied_fingerprints.add(fp)
            elif status == "SKIPPED":
                self._skipped_fingerprints.add(fp)
            elif status in ("ARCHIVED", "REJECTED", "OFFER"):
                self._archived_fingerprints.add(fp)

    # ── Dedup Logic ──────────────────────────────────────────────

    def process_new_jobs(self, jobs: list[JobPosting]) -> tuple[list[JobPosting], list[dict]]:
        """
        Process a batch of newly discovered jobs.
        Returns: (unique_new_jobs, merge_events)
        """
        unique = []
        merges = []

        for job in jobs:
            fp = job.fingerprint

            if fp in self._applied_fingerprints:
                continue  # APPLIED → suppress
            if fp in self._skipped_fingerprints:
                continue  # SKIPPED → suppress
            if fp in self._archived_fingerprints:
                continue  # ARCHIVED → suppress

            if fp in self._seen_fingerprints:
                # Same job from different source → merge
                existing_id = self._seen_fingerprints[fp]
                merges.append({
                    "fingerprint": fp,
                    "existing_job_id": existing_id,
                    "new_source": job.source,
                    "new_source_url": job.source_url,
                })
                continue

            # New job
            self._seen_fingerprints[fp] = ""  # temp, assigned by ledger
            unique.append(job)

        return unique, merges

    def check_repost(self, fp: str, existing_entry: dict) -> bool:
        """Check if this fingerprint is a repost of an existing job."""
        existing_fp = existing_entry.get("fingerprint", "")
        if fp == existing_fp:
            # Check if posted_at is newer
            return True
        return False

    def is_stale(self, job: JobPosting) -> bool:
        """Check if a job posting is stale (older than threshold)."""
        if not job.posted_at:
            return False
        try:
            posted = datetime.fromisoformat(job.posted_at[:10])
            age = (datetime.now(timezone.utc) - posted).days
            return age > self.stale_days
        except (ValueError, TypeError):
            return False

    def get_suppression_stats(self) -> dict:
        """Return suppression statistics."""
        return {
            "applied_suppressed": len(self._applied_fingerprints),
            "skipped_suppressed": len(self._skipped_fingerprints),
            "archived_suppressed": len(self._archived_fingerprints),
            "total_seen": len(self._seen_fingerprints),
        }
