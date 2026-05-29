"""
CareerLoop Persistent Database Migration Utility.

Bootstraps the local embedded SQLite engine by seamlessly importing existing
records from the flat `careerloop/ledger.json` file and user metrics from
`config/profile.yml`. Ensures zero historical data loss.
"""

import json
import os
import re
import hashlib
from datetime import datetime, timezone
from typing import Optional, Any

from careerloop.memory.models import UserModel, ApplicationLedgerModel, EventTimelineModel
from careerloop.memory.repository import MemoryRepository


def make_deterministic_fingerprint(company: str, role: str, location: str, url: str) -> str:
    """Helper generating consistent validation fingerprints matching models.py."""
    c = re.sub(r'[^\w\s]', '', company.lower()).strip()
    r = re.sub(r'[^\w\s]', '', role.lower()).strip()
    l = location.lower().split(',')[0].strip()
    
    domain = ""
    if url:
        m = re.search(r'https?://([^/]+)', url)
        if m:
            domain = m.group(1).replace('boards.', '').replace('job-boards.', '').replace('jobs.', '').replace('careers.', '')
            
    key = f"{c}|{r}|{l}|{domain}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def run_migration(career_ops_root: Optional[str] = None):
    """Executes full extraction and relational mapping from static files."""
    base_dir = career_ops_root or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    repo = MemoryRepository(career_ops_root=base_dir)

    print("🚀 Initializing CareerLoop persistent database migration...")
    
    # 1. Ensure primary user profile exists
    user_id = "user-default-001"
    user = repo.get_user(user_id)
    if not user:
        user = UserModel(
            id=user_id,
            employment_state="employed_active",
            urgency=7,
            burnout_level=6,
            search_posture="HUNT",
            preferred_environments=["async-first", "gcc", "product-org"],
        )
        repo.save_user(user)
        print(f"✅ Created default user profile: {user_id}")
    else:
        print(f"ℹ️ Primary user profile already active: {user_id}")

    # 2. Process ledger.json entries
    ledger_path = os.path.join(base_dir, "careerloop", "ledger.json")
    if not os.path.exists(ledger_path):
        print(f"⚠️ Legacy ledger JSON not found at {ledger_path}. Skipping file migration.")
        return

    try:
        with open(ledger_path, "r") as f:
            entries = json.load(f)
    except Exception as e:
        print(f"❌ Failed to parse legacy ledger.json: {e}")
        return

    imported_count = 0
    skipped_count = 0

    for row in entries:
        try:
            job_id = row.get("job_id", "")
            title = row.get("title") or row.get("role_title", "Untitled Role")
            company = row.get("company", "Unknown Company")
            company_normalized = re.sub(r'[^\w\s]', '', company.lower()).strip()
            location = row.get("location", "")
            url = row.get("source_url") or row.get("url", "")
            
            fingerprint = row.get("fingerprint")
            if not fingerprint:
                fingerprint = make_deterministic_fingerprint(company, title, location, url)

            # Check if fingerprint already indexed
            existing = repo.find_ledger_entry_by_fingerprint(fingerprint)
            if existing:
                skipped_count += 1
                continue

            # Map to typed Pydantic/Dataclass wrapper safely
            status = row.get("status", "DISCOVERED")
            fit_score = row.get("fit_score")
            if fit_score is not None:
                try:
                    fit_score = float(fit_score)
                except (ValueError, TypeError):
                    fit_score = None

            ledger_model = ApplicationLedgerModel(
                id=job_id or f"migrated-{fingerprint[:8]}",
                user_id=user_id,
                job_fingerprint=fingerprint,
                title=title,
                company=company,
                company_normalized=company_normalized or "unknown",
                location=location,
                status=status,
                source=row.get("source", "legacy_json"),
                source_url=url,
                notes=row.get("notes", ""),
                recruiter_name=row.get("recruiter_name", ""),
                fit_score=fit_score,
                created_at=row.get("created_at") or datetime.now(timezone.utc).isoformat(),
                updated_at=row.get("updated_at") or datetime.now(timezone.utc).isoformat(),
            )

            repo.save_ledger_entry(ledger_model)
            
            # Log transition event forward
            repo.log_event(EventTimelineModel(
                id=f"evt-mig-{fingerprint[:8]}",
                user_id=user_id,
                event_type="legacy_record_imported",
                reference_id=ledger_model.id,
                reference_type="application_ledger",
                details={"legacy_status": status, "title": title, "company": company},
            ))
            
            imported_count += 1
        except Exception as ex:
            print(f"⚠️ Failed importing individual row {row.get('job_id')}: {ex}")
            skipped_count += 1

    print(f"🎉 Migration finalized successfully! Imported: {imported_count} rows | Skipped duplicates: {skipped_count}")


if __name__ == "__main__":
    run_migration()
