"""User + preferences reads against the live careerloop schema."""

import json
import logging
from typing import Optional

logger = logging.getLogger("careerloop_api.repositories.users")


class UsersRepo:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, user_id: str) -> Optional[dict]:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, email, full_name, linkedin_url, telegram_chat_id,
                           onboarding_complete, career_mode, master_cv_markdown,
                           created_at, last_active_at
                    FROM careerloop.users WHERE id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_by_email(self, email: str) -> Optional[dict]:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, email, full_name FROM careerloop.users WHERE email = %s",
                    (email,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_preferences(self, user_id: str) -> dict:
        """Prefer the dedicated user_preferences row; fall back to columns on users."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT target_roles, target_cities, salary_min, salary_max,
                           notice_period, work_mode, avoid_companies,
                           avoid_role_types, aggressiveness
                    FROM careerloop.user_preferences WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                if row:
                    return self._normalize_prefs(dict(row))

                # Fallback: legacy columns stored directly on the users row.
                cur.execute(
                    """
                    SELECT target_roles, target_cities, salary_expectations,
                           notice_period, career_mode, work_style_prefs
                    FROM careerloop.users WHERE id = %s
                    """,
                    (user_id,),
                )
                urow = cur.fetchone()
                if not urow:
                    return {}
                u = dict(urow)
                return {
                    "target_roles": self._as_list(u.get("target_roles")),
                    "target_cities": self._as_list(u.get("target_cities")),
                    "salary_expectations": u.get("salary_expectations"),
                    "notice_period": u.get("notice_period"),
                    "work_mode": None,
                    "aggressiveness": None,
                    "source": "users_fallback",
                }

    @staticmethod
    def _as_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return []
            try:
                parsed = json.loads(s)
                return parsed if isinstance(parsed, list) else [s]
            except Exception:
                return [p.strip() for p in s.split(",") if p.strip()]
        return [value]

    def _normalize_prefs(self, row: dict) -> dict:
        row["target_roles"] = self._as_list(row.get("target_roles"))
        row["target_cities"] = self._as_list(row.get("target_cities"))
        row["avoid_companies"] = self._as_list(row.get("avoid_companies"))
        row["avoid_role_types"] = self._as_list(row.get("avoid_role_types"))
        row["source"] = "user_preferences"
        return row
