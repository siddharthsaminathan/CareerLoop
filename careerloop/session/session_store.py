import os
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from careerloop.session.states import LEGACY_STATE_ALIASES, UserState, normalize_user_state
from careerloop.memory.connection import get_db_manager

logger = logging.getLogger("careerloop.session.session_store")

@dataclass
class Session:
    user_id: str
    state: UserState
    current_job_id: Optional[str] = None
    onboarding_step: int = 0
    temp_profile_data: Optional[Dict[str, Any]] = None

class SessionStore:
    def __init__(self, db_manager=None):
        self.db_manager = db_manager or get_db_manager()
        self._init_db()

    def _init_db(self):
        pass # Schema is initialized via connection.py and supabase_schema.sql

    def _tbl(self, name: str) -> str:
        """Returns schema-qualified table name for Postgres, bare name for SQLite.

        SQLite does not support schema-qualified identifiers (e.g. public.sessions),
        so the prefix is only applied when DATABASE_URL points at PostgreSQL.
        """
        if os.getenv("DATABASE_URL"):
            return f"public.{name}"
        return name

    def _parse_profile_prefs(self, raw_prefs: Any) -> dict:
        if isinstance(raw_prefs, dict):
            return raw_prefs
        if isinstance(raw_prefs, str) and raw_prefs.strip():
            try:
                parsed = json.loads(raw_prefs)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _load_profile_data(self, user_id: str) -> Dict[str, Any]:
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"SELECT master_cv_markdown, work_style_prefs FROM {self._tbl('users')} WHERE id = %s",
                        (user_id,),
                    )
                    row = cursor.fetchone()
            if not row:
                return {}
            prefs = self._parse_profile_prefs(row.get("work_style_prefs"))
            return {
                "cv_content": row.get("master_cv_markdown") or "",
                "target_roles": prefs.get("target_roles") or "",
                "target_cities": prefs.get("target_cities") or prefs.get("locations") or "",
                "salary_expectations": prefs.get("salary_expectations") or "",
                "notice_period": prefs.get("notice_period") or "",
                "aggressiveness": prefs.get("aggressiveness") or "",
            }
        except Exception as e:
            logger.error(f"Failed to load profile data for state recovery: {e}")
            return {}

    @staticmethod
    def _has_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            normalized = value.strip().lower()
            return bool(normalized) and normalized not in {"n/a", "na", "none", "null", "-"}
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return True

    def is_profile_complete(self, profile_data: Dict[str, Any]) -> bool:
        required = [
            "cv_content",
            "target_roles",
            "target_cities",
            "salary_expectations",
            "notice_period",
            "aggressiveness",
        ]
        return all(self._has_value(profile_data.get(key)) for key in required)

    def infer_onboarding_state(self, profile_data: Dict[str, Any]) -> UserState:
        if self.is_profile_complete(profile_data):
            return UserState.PROFILE_COMPLETE
        if not self._has_value(profile_data.get("cv_content")):
            return UserState.ONBOARDING_WAITING_CV
        return UserState.ONBOARDING_Q1_ROLES

    def _repair_session_state(self, user_id: str, state: UserState) -> None:
        try:
            self.update_state(user_id, state)
        except Exception as e:
            logger.error(f"Failed to repair session state for {user_id}: {e}")

    def get_session(self, user_id: str) -> Session:
        """Retrieves a session from the store. If not exists, initializes a default IDLE session."""
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"SELECT state, current_job_id, onboarding_step, temp_profile_data FROM {self._tbl('sessions')} WHERE user_id = %s",
                        (user_id,)
                    )
                    row = cursor.fetchone()
                
                if not row:
                    profile_data = self._load_profile_data(user_id)
                    default_state = (
                        self.infer_onboarding_state(profile_data)
                        if any(profile_data.values())
                        else UserState.IDLE
                    )
                    default_session = Session(
                        user_id=user_id,
                        state=default_state,
                        temp_profile_data=profile_data or None,
                    )
                    self.save_session(default_session)
                    return default_session

                state_str = row['state']
                current_job_id = row['current_job_id']
                onboarding_step = row['onboarding_step']
                temp_profile_str = row['temp_profile_data']
                
                state = normalize_user_state(state_str)
                if state_str in LEGACY_STATE_ALIASES:
                    logger.info(f"Migrating legacy state '{state_str}' to '{state.value}' for user {user_id}.")
                    self._repair_session_state(user_id, state)

                if state is None:
                    profile_data = self._load_profile_data(user_id)
                    state = self.infer_onboarding_state(profile_data)
                    logger.warning(
                        f"Unknown state '{state_str}' encountered in DB for user {user_id}. "
                        f"Recovered to {state.value} from persisted profile completeness."
                    )
                    self._repair_session_state(user_id, state)

                temp_profile_data = None
                if temp_profile_str:
                    if isinstance(temp_profile_str, dict):
                        temp_profile_data = temp_profile_str
                    elif isinstance(temp_profile_str, str):
                        try:
                            temp_profile_data = json.loads(temp_profile_str)
                        except Exception as e:
                            logger.error(f"Failed to deserialize temp_profile_data JSON: {e}")

                if not temp_profile_data and state == UserState.PROFILE_COMPLETE:
                    temp_profile_data = self._load_profile_data(user_id)

                return Session(
                    user_id=user_id,
                    state=state,
                    current_job_id=current_job_id,
                    onboarding_step=onboarding_step,
                    temp_profile_data=temp_profile_data
                )
        except Exception as e:
            logger.error(f"Failed to retrieve session for user {user_id}: {e}")
            return Session(user_id=user_id, state=UserState.IDLE)

    def save_session(self, session: Session) -> bool:
        """Saves or updates a full Session record in the database."""
        try:
            temp_profile_str = None
            if session.temp_profile_data is not None:
                temp_profile_str = json.dumps(session.temp_profile_data)

            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"""
                        INSERT INTO {self._tbl('users')} (id, email, full_name, created_at, updated_at)
                        VALUES (%s, %s, 'Unknown User', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO NOTHING;
                    """, (session.user_id, f"user_{session.user_id}@placeholder.com"))
                    cursor.execute(f"""
                        INSERT INTO {self._tbl('sessions')} (user_id, state, current_job_id, onboarding_step, temp_profile_data, updated_at)
                        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (user_id) DO UPDATE SET
                            state = EXCLUDED.state,
                            current_job_id = EXCLUDED.current_job_id,
                            onboarding_step = EXCLUDED.onboarding_step,
                            temp_profile_data = EXCLUDED.temp_profile_data,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (
                        session.user_id,
                        session.state.value,
                        session.current_job_id,
                        session.onboarding_step,
                        temp_profile_str
                    ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to save session for user {session.user_id}: {e}")
            return False

    def update_state(self, user_id: str, state: UserState) -> bool:
        """Helper to quickly update state only."""
        try:
            state = normalize_user_state(state) or UserState.IDLE
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {self._tbl('sessions')} SET state = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
                        (state.value, user_id)
                    )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update state to {state.value} for user {user_id}: {e}")
            return False

    def delete_session(self, user_id: str) -> bool:
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"DELETE FROM {self._tbl('sessions')} WHERE user_id = %s", (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to delete session for user {user_id}: {e}")
            return False
