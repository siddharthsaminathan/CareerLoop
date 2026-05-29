"""Job reads + user-job relationship writes against the live careerloop schema.

Live jobs table carries BOTH a v1 text `id` (e.g. 'loop-0122') and a v2 UUID
`job_id`. Brief items may reference either, so lookups match on both.
user_job_relationships.job_id is the UUID FK, so save/skip resolve to it.
"""

import logging
from typing import Optional

logger = logging.getLogger("careerloop_api.repositories.jobs")

# Job columns + company branding (logo/website/domain) via LEFT JOIN on company_id.
# Aliased so the serializer can build a logo URL even when companies.logo_url is null.
_JOB_SELECT = """
    j.id, j.job_id, j.title, j.company_name, j.company_id, j.location, j.location_raw,
    j.location_city, j.location_country, j.work_mode, j.salary_min, j.salary_max,
    j.salary_currency, j.source, j.source_url, j.apply_url, j.role_summary,
    j.is_india_role, j.verified_active, j.status, j.posted_at, j.scraped_at, j.jd_text,
    c.logo_url AS company_logo_url, c.website AS company_website,
    c.domain AS company_domain, c.linkedin_url AS company_linkedin_url
"""

_JOB_FROM = """
    FROM careerloop.jobs j
    LEFT JOIN careerloop.companies c ON c.id = j.company_id
"""


class JobsRepo:
    def __init__(self, db):
        self.db = db

    def get_by_any_id(self, ident: str) -> Optional[dict]:
        """Resolve a job by its UUID job_id OR its v1 text id, with company branding."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_JOB_SELECT} {_JOB_FROM} "
                    "WHERE j.id = %s OR j.job_id::text = %s LIMIT 1",
                    (ident, ident),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_relationship(self, user_id: str, job_uuid: str) -> Optional[dict]:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id, job_id, match_status, fit_score, fit_label,
                           route_recommendation, swiped_action, interest_level
                    FROM careerloop.user_job_relationships
                    WHERE user_id = %s AND job_id = %s
                    """,
                    (user_id, job_uuid),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def set_match_status(
        self,
        user_id: str,
        job_uuid: str,
        match_status: str,
        swiped_action: Optional[str] = None,
        fit_score: Optional[float] = None,
    ) -> bool:
        """Upsert user_job_relationships.match_status (save/skip). job_uuid must be the UUID FK."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO careerloop.user_job_relationships
                            (user_id, job_id, match_status, swiped_action, fit_score,
                             user_seen_at, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, NOW(), NOW(), NOW())
                        ON CONFLICT (user_id, job_id) DO UPDATE SET
                            match_status  = EXCLUDED.match_status,
                            swiped_action = EXCLUDED.swiped_action,
                            updated_at    = NOW()
                        """,
                        (user_id, job_uuid, match_status, swiped_action, fit_score),
                    )
            return True
        except Exception as e:
            logger.error("set_match_status failed: %s", e)
            return False
