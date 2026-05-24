"""
CareerLoop Data Repository V2
==============================
Centralized data access layer. All DB writes go through here.
Supabase PostgreSQL only. No SQLite.

Every function uses psycopg2 parameterized queries (%s placeholders)
with RealDictCursor via DatabaseManager.get_connection().
"""

import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from careerloop.memory.connection import DatabaseManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# JobRepository — Global job cache
# ============================================================================

class JobRepository:
    """Global job cache operations."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    # -- jobs ----------------------------------------------------------------

    def upsert_job(self, job_data: dict) -> str:
        """Insert or update a global job. Returns job_id."""
        job_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.jobs (
                            job_id, source, title, company_name,
                            location_raw, content_fingerprint, jd_text,
                            raw_payload, apply_url, posted_at, status
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, 'active'
                        )
                        ON CONFLICT (content_fingerprint) DO UPDATE SET
                            title          = EXCLUDED.title,
                            company_name   = EXCLUDED.company_name,
                            location_raw   = EXCLUDED.location_raw,
                            jd_text        = EXCLUDED.jd_text,
                            raw_payload    = EXCLUDED.raw_payload,
                            apply_url      = EXCLUDED.apply_url,
                            posted_at      = EXCLUDED.posted_at,
                            last_seen_at   = NOW(),
                            updated_at     = NOW()
                        RETURNING job_id
                        """,
                        (
                            job_id,
                            job_data.get("source", "unknown"),
                            job_data.get("title", ""),
                            job_data.get("company", ""),
                            job_data.get("location", ""),
                            job_data.get("fingerprint", job_id),
                            job_data.get("jd_text", ""),
                            json.dumps(job_data.get("raw", {})),
                            job_data.get("apply_url", ""),
                            job_data.get("posted_at", ""),
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["job_id"])
            return job_id
        except Exception as e:
            logger.error(f"upsert_job failed: {e}")
            return job_id

    def find_by_fingerprint(self, fingerprint: str) -> Optional[dict]:
        """Check if a job already exists by content fingerprint."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM public.jobs WHERE content_fingerprint = %s",
                        (fingerprint,),
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"find_by_fingerprint failed: {e}")
            return None

    def touch_last_seen(self, job_id: str) -> None:
        """Update last_seen_at for a job."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.jobs SET last_seen_at = NOW(), updated_at = NOW() WHERE job_id = %s",
                        (job_id,),
                    )
        except Exception as e:
            logger.error(f"touch_last_seen failed: {e}")

    def expire_stale_jobs(self, days: int = 60) -> int:
        """Mark jobs unseen for N days as expired. Returns count."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE public.jobs
                        SET status = 'expired', updated_at = NOW()
                        WHERE status = 'active'
                          AND last_seen_at < NOW() - INTERVAL '%s days'
                        """,
                        (str(days),),
                    )
                    return cur.rowcount
        except Exception as e:
            logger.error(f"expire_stale_jobs failed: {e}")
            return 0

    # -- companies -----------------------------------------------------------

    def upsert_company(self, company_data: dict) -> str:
        """Insert or update a company. Returns company_id."""
        company_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.companies (
                            company_id, domain_slug, name, domain,
                            city, sector, subsector, ats_provider,
                            career_page_url, employee_estimate, crawl_status,
                            is_active, source
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, 'pending',
                            1, %s
                        )
                        ON CONFLICT (domain_slug) DO UPDATE SET
                            name               = EXCLUDED.name,
                            domain             = EXCLUDED.domain,
                            city               = EXCLUDED.city,
                            sector             = EXCLUDED.sector,
                            subsector          = EXCLUDED.subsector,
                            ats_provider       = EXCLUDED.ats_provider,
                            career_page_url    = EXCLUDED.career_page_url,
                            employee_estimate  = EXCLUDED.employee_estimate,
                            source             = EXCLUDED.source,
                            updated_at         = NOW()
                        RETURNING company_id
                        """,
                        (
                            company_id,
                            company_data.get("domain_slug", company_id),
                            company_data.get("name", ""),
                            company_data.get("domain", ""),
                            company_data.get("city", ""),
                            company_data.get("sector", ""),
                            company_data.get("subsector", ""),
                            company_data.get("ats_provider", "unknown"),
                            company_data.get("career_page_url", ""),
                            company_data.get("employee_estimate", 0),
                            company_data.get("source", ""),
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["company_id"])
            return company_id
        except Exception as e:
            logger.error(f"upsert_company failed: {e}")
            return company_id


# ============================================================================
# DiscoveryRepository — Raw candidates + background runs
# ============================================================================

class DiscoveryRepository:
    """Raw candidates + background runs."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    # -- background runs -----------------------------------------------------

    def create_background_run(
        self,
        run_type: str,
        user_id: Optional[str] = None,
        params: Optional[dict] = None,
    ) -> str:
        """Create a background_run row. Returns run_id."""
        run_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.background_runs (
                            run_id, user_id, run_type, status, params
                        ) VALUES (
                            %s, %s, %s, 'QUEUED', %s
                        )
                        RETURNING run_id
                        """,
                        (
                            run_id,
                            user_id,
                            run_type,
                            json.dumps(params or {}),
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["run_id"])
            return run_id
        except Exception as e:
            logger.error(f"create_background_run failed: {e}")
            return run_id

    def update_background_run(
        self,
        run_id: str,
        status: str,
        stats: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update status/stats/error on a background run."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE public.background_runs
                        SET status     = %s,
                            stats      = COALESCE(%s, stats),
                            error      = COALESCE(%s, error),
                            updated_at = NOW()
                        WHERE run_id = %s
                        """,
                        (
                            status,
                            json.dumps(stats) if stats else None,
                            error,
                            run_id,
                        ),
                    )
        except Exception as e:
            logger.error(f"update_background_run failed: {e}")

    # -- run events ----------------------------------------------------------

    def append_run_event(
        self,
        run_id: str,
        event_type: str,
        message: str,
        payload: Optional[dict] = None,
    ) -> str:
        """Append a run_event. Returns event_id."""
        event_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.run_events (
                            event_id, run_id, event_type, message, payload
                        ) VALUES (
                            %s, %s, %s, %s, %s
                        )
                        RETURNING event_id
                        """,
                        (
                            event_id,
                            run_id,
                            event_type,
                            message,
                            json.dumps(payload) if payload else None,
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["event_id"])
            return event_id
        except Exception as e:
            logger.error(f"append_run_event failed: {e}")
            return event_id

    def get_run_events(self, run_id: str, limit: int = 100) -> List[dict]:
        """Get all events for a run (for CLI streaming)."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT * FROM public.run_events
                        WHERE run_id = %s
                        ORDER BY timestamp ASC
                        LIMIT %s
                        """,
                        (run_id, limit),
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"get_run_events failed: {e}")
            return []

    # -- job candidates ------------------------------------------------------

    def create_job_candidate(self, run_id: str, candidate: dict) -> str:
        """Store a raw discovery candidate. Returns candidate_id."""
        candidate_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.job_candidates (
                            candidate_id, run_id, title, company, location,
                            source_url, apply_url, jd_text, raw_payload, stage
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, 'discovered'
                        )
                        RETURNING candidate_id
                        """,
                        (
                            candidate_id,
                            run_id,
                            candidate.get("title", ""),
                            candidate.get("company", ""),
                            candidate.get("location", ""),
                            candidate.get("source_url", ""),
                            candidate.get("apply_url", ""),
                            candidate.get("jd_text", ""),
                            json.dumps(candidate.get("raw", {})),
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["candidate_id"])
            return candidate_id
        except Exception as e:
            logger.error(f"create_job_candidate failed: {e}")
            return candidate_id

    def mark_candidate_rejected(
        self, candidate_id: str, stage: str, reason: str
    ) -> None:
        """Mark a candidate as rejected with stage+reason."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE public.job_candidates
                        SET stage            = %s,
                            rejection_reason = %s
                        WHERE candidate_id = %s
                        """,
                        (stage, reason, candidate_id),
                    )
        except Exception as e:
            logger.error(f"mark_candidate_rejected failed: {e}")

    def mark_candidate_matched(self, candidate_id: str, job_id: str) -> None:
        """Link a candidate to a matched job."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE public.job_candidates
                        SET stage          = 'matched',
                            matched_job_id = %s
                        WHERE candidate_id = %s
                        """,
                        (job_id, candidate_id),
                    )
        except Exception as e:
            logger.error(f"mark_candidate_matched failed: {e}")


# ============================================================================
# UserJobRepository — User-job relationships (personalization layer)
# ============================================================================

class UserJobRepository:
    """User-job relationships (personalization layer)."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def create_relationship(
        self,
        user_id: str,
        job_id: str,
        match_status: str = "matched",
        fit_score: Optional[float] = None,
        route: Optional[str] = None,
    ) -> None:
        """Create or update user_job_relationships row."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.user_job_relationships (
                            user_id, job_id, match_status, fit_score, route
                        ) VALUES (
                            %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (user_id, job_id) DO UPDATE SET
                            match_status = EXCLUDED.match_status,
                            fit_score    = EXCLUDED.fit_score,
                            route        = EXCLUDED.route,
                            updated_at   = NOW()
                        """,
                        (user_id, job_id, match_status, fit_score, route),
                    )
        except Exception as e:
            logger.error(f"create_relationship failed: {e}")

    def get_relationship(self, user_id: str, job_id: str) -> Optional[dict]:
        """Get a user's relationship to a specific job."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT * FROM public.user_job_relationships
                        WHERE user_id = %s AND job_id = %s
                        """,
                        (user_id, job_id),
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_relationship failed: {e}")
            return None

    def get_matches_for_user(
        self, user_id: str, status: str = "matched", limit: int = 50
    ) -> List[dict]:
        """Get matched jobs for a user (relationship + job data)."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT r.*, j.title, j.company_name, j.location_raw,
                               j.apply_url, j.jd_text, j.posted_at
                        FROM public.user_job_relationships r
                        JOIN public.jobs j ON j.job_id = r.job_id
                        WHERE r.user_id = %s AND r.match_status = %s
                        ORDER BY r.fit_score DESC NULLS LAST
                        LIMIT %s
                        """,
                        (user_id, status, limit),
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"get_matches_for_user failed: {e}")
            return []


# ============================================================================
# BriefRepository — Daily brief + brief items
# ============================================================================

class BriefRepository:
    """Daily brief + brief items."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def create_brief(
        self,
        user_id: str,
        run_id: str,
        date_str: str,
        summary: str,
        stats: Optional[dict] = None,
    ) -> str:
        """Create a daily_brief row. Returns brief_id."""
        brief_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.daily_briefs (
                            brief_id, user_id, run_id, date_str, summary, stats
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (user_id, date_str) DO UPDATE SET
                            run_id  = EXCLUDED.run_id,
                            summary = EXCLUDED.summary,
                            stats   = EXCLUDED.stats
                        RETURNING brief_id
                        """,
                        (
                            brief_id,
                            user_id,
                            run_id,
                            date_str,
                            summary,
                            json.dumps(stats) if stats else None,
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["brief_id"])
            return brief_id
        except Exception as e:
            logger.error(f"create_brief failed: {e}")
            return brief_id

    def create_brief_item(
        self,
        brief_id: str,
        index: int,
        job_id: str,
        fit_score: float,
        title: str,
        company: str,
        location: str,
        reason: Optional[str] = None,
        risk: Optional[str] = None,
        route: Optional[str] = None,
        display: Optional[dict] = None,
    ) -> str:
        """Create a daily_brief_item. Returns item_id."""
        item_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.daily_brief_items (
                            item_id, brief_id, item_index, job_id, fit_score,
                            title, company, location, reason, risk, route, display
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (brief_id, item_index) DO UPDATE SET
                            job_id    = EXCLUDED.job_id,
                            fit_score = EXCLUDED.fit_score,
                            title     = EXCLUDED.title,
                            company   = EXCLUDED.company,
                            location  = EXCLUDED.location,
                            reason    = EXCLUDED.reason,
                            risk      = EXCLUDED.risk,
                            route     = EXCLUDED.route,
                            display   = EXCLUDED.display
                        RETURNING item_id
                        """,
                        (
                            item_id,
                            brief_id,
                            index,
                            job_id,
                            fit_score,
                            title,
                            company,
                            location,
                            reason,
                            risk,
                            route,
                            json.dumps(display) if display else None,
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["item_id"])
            return item_id
        except Exception as e:
            logger.error(f"create_brief_item failed: {e}")
            return item_id

    def get_latest_brief(self, user_id: str) -> Optional[dict]:
        """Get the most recent brief for a user."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT * FROM public.daily_briefs
                        WHERE user_id = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (user_id,),
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_latest_brief failed: {e}")
            return None

    def get_brief_items(self, brief_id: str) -> List[dict]:
        """Get all items for a brief, ordered by item_index."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT * FROM public.daily_brief_items
                        WHERE brief_id = %s
                        ORDER BY item_index ASC
                        """,
                        (brief_id,),
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"get_brief_items failed: {e}")
            return []

    def get_brief_item_at_index(
        self, brief_id: str, index: int
    ) -> Optional[dict]:
        """Get a specific brief item by index."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT * FROM public.daily_brief_items
                        WHERE brief_id = %s AND item_index = %s
                        """,
                        (brief_id, index),
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_brief_item_at_index failed: {e}")
            return None


# ============================================================================
# ApplicationRepository — Applications + packs + followups
# ============================================================================

class ApplicationRepository:
    """Applications + packs + followups."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    # -- applications --------------------------------------------------------

    def create_application(
        self,
        user_id: str,
        job_id: str,
        pack_id: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> str:
        """Create an application row. Returns application_id."""
        application_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.applications (
                            application_id, user_id, job_id, pack_id, channel, status
                        ) VALUES (
                            %s, %s, %s, %s, %s, 'applied'
                        )
                        RETURNING application_id
                        """,
                        (application_id, user_id, job_id, pack_id, channel),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["application_id"])
            return application_id
        except Exception as e:
            logger.error(f"create_application failed: {e}")
            return application_id

    def update_status(
        self,
        application_id: str,
        status: str,
        notes: Optional[str] = None,
    ) -> None:
        """Update application status."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE public.applications
                        SET status     = %s,
                            notes      = COALESCE(%s, notes),
                            updated_at = NOW()
                        WHERE application_id = %s
                        """,
                        (status, notes, application_id),
                    )
        except Exception as e:
            logger.error(f"update_status failed: {e}")

    # -- packs ---------------------------------------------------------------

    def create_pack(
        self, user_id: str, job_id: str, run_id: str
    ) -> str:
        """Create an application_pack row. Returns pack_id."""
        pack_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.application_packs (
                            pack_id, user_id, job_id, run_id
                        ) VALUES (
                            %s, %s, %s, %s
                        )
                        RETURNING pack_id
                        """,
                        (pack_id, user_id, job_id, run_id),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["pack_id"])
            return pack_id
        except Exception as e:
            logger.error(f"create_pack failed: {e}")
            return pack_id

    # -- followups -----------------------------------------------------------

    def create_followup(
        self,
        user_id: str,
        application_id: str,
        due_at: str,
        draft: Optional[str] = None,
    ) -> str:
        """Create a followup. Returns followup_id."""
        followup_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.followups (
                            followup_id, user_id, application_id, due_at, draft, status
                        ) VALUES (
                            %s, %s, %s, %s, %s, 'pending'
                        )
                        RETURNING followup_id
                        """,
                        (followup_id, user_id, application_id, due_at, draft),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["followup_id"])
            return followup_id
        except Exception as e:
            logger.error(f"create_followup failed: {e}")
            return followup_id

    def get_due_followups(self, user_id: str) -> List[dict]:
        """Get all pending followups for a user that are past due."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT f.*, a.job_id, a.status AS application_status
                        FROM public.followups f
                        JOIN public.applications a ON a.application_id = f.application_id
                        WHERE f.user_id = %s
                          AND f.status = 'pending'
                          AND f.due_at <= NOW()
                        ORDER BY f.due_at ASC
                        """,
                        (user_id,),
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"get_due_followups failed: {e}")
            return []


# ============================================================================
# PeopleRepository — People + outreach
# ============================================================================

class PeopleRepository:
    """People + outreach."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def upsert_person(self, person_data: dict) -> str:
        """Insert or update a person_to_reach. Returns person_id."""
        person_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.people_to_reach (
                            person_id, company_id, name, title,
                            linkedin_url, email, notes
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s
                        )
                        ON CONFLICT (company_id, linkedin_url) DO UPDATE SET
                            name   = EXCLUDED.name,
                            title  = EXCLUDED.title,
                            email  = EXCLUDED.email,
                            notes  = EXCLUDED.notes,
                            updated_at = NOW()
                        RETURNING person_id
                        """,
                        (
                            person_id,
                            person_data.get("company_id"),
                            person_data.get("name", ""),
                            person_data.get("title", ""),
                            person_data.get("linkedin_url", ""),
                            person_data.get("email", ""),
                            person_data.get("notes", ""),
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["person_id"])
            return person_id
        except Exception as e:
            logger.error(f"upsert_person failed: {e}")
            return person_id

    def get_people_for_company(self, company_id: str) -> List[dict]:
        """Get known people at a company."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT * FROM public.people_to_reach
                        WHERE company_id = %s
                        ORDER BY created_at DESC
                        """,
                        (company_id,),
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"get_people_for_company failed: {e}")
            return []

    def create_outreach(
        self,
        user_id: str,
        person_id: str,
        job_id: str,
        msg_type: str,
        body: str,
    ) -> str:
        """Create an outreach message. Returns message_id."""
        message_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.outreach_messages (
                            message_id, user_id, person_id, job_id, msg_type, body, status
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, 'draft'
                        )
                        RETURNING message_id
                        """,
                        (message_id, user_id, person_id, job_id, msg_type, body),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["message_id"])
            return message_id
        except Exception as e:
            logger.error(f"create_outreach failed: {e}")
            return message_id


# ============================================================================
# EvidenceRepository — User evidence + preferences + outcomes
# ============================================================================

class EvidenceRepository:
    """User evidence + preferences + outcomes."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    # -- evidence ------------------------------------------------------------

    def upsert_evidence(self, evidence_data: dict) -> str:
        """Insert or update user_evidence. Returns evidence_id."""
        evidence_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.user_evidence (
                            evidence_id, user_id, evidence_type, content, source
                        ) VALUES (
                            %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (user_id, evidence_type) DO UPDATE SET
                            content    = EXCLUDED.content,
                            source     = EXCLUDED.source,
                            updated_at = NOW()
                        RETURNING evidence_id
                        """,
                        (
                            evidence_id,
                            evidence_data.get("user_id", ""),
                            evidence_data.get("evidence_type", ""),
                            json.dumps(evidence_data.get("content", {})),
                            evidence_data.get("source", ""),
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["evidence_id"])
            return evidence_id
        except Exception as e:
            logger.error(f"upsert_evidence failed: {e}")
            return evidence_id

    # -- preferences ---------------------------------------------------------

    def get_preferences(self, user_id: str) -> Optional[dict]:
        """Get user_preferences row."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM public.user_preferences WHERE user_id = %s",
                        (user_id,),
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_preferences failed: {e}")
            return None

    def update_preferences(self, user_id: str, prefs: dict) -> None:
        """Update or insert user_preferences."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.user_preferences (user_id, prefs)
                        VALUES (%s, %s)
                        ON CONFLICT (user_id) DO UPDATE SET
                            prefs      = EXCLUDED.prefs,
                            updated_at = NOW()
                        """,
                        (user_id, json.dumps(prefs)),
                    )
        except Exception as e:
            logger.error(f"update_preferences failed: {e}")

    # -- outcomes ------------------------------------------------------------

    def record_outcome(
        self,
        user_id: str,
        event_type: str,
        job_id: Optional[str] = None,
        application_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> str:
        """Record an outcome_event. Returns outcome_id."""
        outcome_id = str(uuid.uuid4())
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.outcome_events (
                            outcome_id, user_id, event_type, job_id,
                            application_id, payload
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s
                        )
                        RETURNING outcome_id
                        """,
                        (
                            outcome_id,
                            user_id,
                            event_type,
                            job_id,
                            application_id,
                            json.dumps(payload) if payload else None,
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["outcome_id"])
            return outcome_id
        except Exception as e:
            logger.error(f"record_outcome failed: {e}")
            return outcome_id
