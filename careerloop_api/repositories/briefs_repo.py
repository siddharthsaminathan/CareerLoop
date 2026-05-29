"""Daily brief + brief item reads against the live careerloop schema.

Live schema (v1):
  daily_briefs(id, user_id, date_str, run_id, summary, created_at)
  daily_brief_items(id, brief_id, item_index, job_id, title, company, location,
                    fit_score, recommendation_reason, risk_summary, route_recommendation)
"""

import logging
from typing import Optional, List

logger = logging.getLogger("careerloop_api.repositories.briefs")

# Brief item columns + enrichment from jobs (description, salary, urls) and
# companies (logo/website/domain). The item's job_id may be a text v1 id
# (e.g. 'loop-0122') or a UUID, so the JOIN matches both forms.
_ITEM_SELECT = """
    bi.id, bi.brief_id, bi.item_index, bi.job_id, bi.title, bi.company, bi.location,
    bi.fit_score, bi.recommendation_reason, bi.risk_summary, bi.route_recommendation,
    j.company_name AS job_company_name,
    j.role_summary, j.jd_text, j.work_mode, j.salary_min, j.salary_max,
    j.salary_currency, j.apply_url, j.source_url,
    c.logo_url AS company_logo_url, c.website AS company_website, c.domain AS company_domain
"""

_ITEM_FROM = """
    FROM careerloop.daily_brief_items bi
    LEFT JOIN careerloop.jobs j
        ON (j.id = bi.job_id OR j.job_id::text = bi.job_id)
    LEFT JOIN careerloop.companies c ON c.id = j.company_id
"""


class BriefsRepo:
    def __init__(self, db):
        self.db = db

    def get_latest_brief(self, user_id: str) -> Optional[dict]:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, date_str, run_id, summary, created_at
                    FROM careerloop.daily_briefs
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_brief_by_id(self, brief_id: str, user_id: str) -> Optional[dict]:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, date_str, run_id, summary, created_at
                    FROM careerloop.daily_briefs
                    WHERE id = %s AND user_id = %s
                    """,
                    (brief_id, user_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_items(self, brief_id: str) -> List[dict]:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_ITEM_SELECT} {_ITEM_FROM} "
                    "WHERE bi.brief_id = %s ORDER BY bi.item_index ASC",
                    (brief_id,),
                )
                return [dict(r) for r in cur.fetchall()]

    def get_item_at_index(self, brief_id: str, item_index: int) -> Optional[dict]:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_ITEM_SELECT} {_ITEM_FROM} "
                    "WHERE bi.brief_id = %s AND bi.item_index = %s",
                    (brief_id, item_index),
                )
                row = cur.fetchone()
                return dict(row) if row else None
