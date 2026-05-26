import json
import logging
import uuid
from typing import Optional, Dict, Any
from dataclasses import dataclass
from careerloop.session.states import UserJourneyState, normalize_user_state
from careerloop.memory.connection import get_db_manager

logger = logging.getLogger("careerloop.session.session_store")

@dataclass
class Session:
    user_id: str
    state: UserJourneyState
    current_job_id: Optional[str] = None
    onboarding_step: int = 0
    temp_profile_data: Optional[Dict[str, Any]] = None
    active_artifact_type: Optional[str] = None
    active_artifact_id: Optional[str] = None
    active_job_id: Optional[str] = None
    active_brief_id: Optional[str] = None
    active_pack_id: Optional[str] = None
    current_selection_index: Optional[int] = None

class SessionStore:
    def __init__(self, db_manager=None):
        self.db_manager = db_manager or get_db_manager()
        self._init_db()

    def _init_db(self):
        pass # Schema is initialized via connection.py and supabase_schema.sql

    def _tbl(self, name: str) -> str:
        """Returns schema-qualified table name.
        All CareerLoop tables (including users) live in careerloop."""
        if name == "users":
            return "careerloop.users"
        return f"careerloop.{name}"

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

    # infer_onboarding_state and _repair_session_state removed (orchestration logic should live in resolvers)

    def get_or_create_user(self, telegram_chat_id: int, first_name: str = "", username: str = "") -> str:
        """
        Resolve or create a careerloop.users row for a Telegram user.
        Returns a stable user_id (UUID string) derived from telegram_chat_id.

        Identity anchor: telegram_chat_id is Telegram-guaranteed unique and stable.
        UUID is deterministic: uuid5(DNS, "telegram:{chat_id}") — reversible, collision-free.
        """
        deterministic_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"telegram:{telegram_chat_id}"))
        email = f"telegram_{telegram_chat_id}@careerloop.internal"
        full_name = (first_name or username or "User").strip()[:100]

        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    # Fast path: look up by telegram_chat_id
                    cur.execute(
                        f"SELECT id FROM {self._tbl('users')} WHERE telegram_chat_id = %s",
                        (telegram_chat_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        return str(row["id"])

                    # New user: insert with deterministic UUID
                    cur.execute(f"""
                        INSERT INTO {self._tbl('users')}
                            (id, email, full_name, telegram_chat_id, handle, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET
                            telegram_chat_id = EXCLUDED.telegram_chat_id,
                            handle = EXCLUDED.handle,
                            updated_at = CURRENT_TIMESTAMP
                    """, (deterministic_id, email, full_name, telegram_chat_id, username or None))
                conn.commit()
            logger.info("Created/resolved user %s for telegram_chat_id=%s", deterministic_id[:12], telegram_chat_id)
            return deterministic_id
        except Exception as e:
            logger.error("get_or_create_user failed: %s", e)
            # Deterministic fallback — still stable, just not DB-backed
            return deterministic_id

    def get_session(self, user_id: str) -> Session:
        """Retrieves a session from the store. If not exists, initializes a default IDLE session."""
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"SELECT state, current_job_id, onboarding_step, temp_profile_data, "
                        f"active_artifact_type, active_artifact_id, active_job_id, active_brief_id, active_pack_id, current_selection_index "
                        f"FROM {self._tbl('sessions')} WHERE user_id = %s",
                        (user_id,)
                    )
                    row = cursor.fetchone()
                
                if not row:
                    profile_data = self._load_profile_data(user_id)
                    default_state = UserJourneyState.NEW_USER
                    temp_profile_data = profile_data or None

                    # Profile recovery: if user has a complete profile in users table
                    # but no sessions row, upgrade to PROFILE_READY
                    if default_state == UserJourneyState.NEW_USER and profile_data:
                        try:
                            cv = (profile_data.get("cv_content") or "").strip()
                            if cv and len(cv) > 50:  # Has a real CV
                                logger.info(f"Profile recovery: user {user_id[:12]}... has CV ({len(cv)} chars), upgrading to PROFILE_READY")
                                default_state = UserJourneyState.PROFILE_READY
                                temp_profile_data = profile_data
                        except Exception as e:
                            logger.error(f"Profile recovery check failed: {e}")

                    default_session = Session(
                        user_id=user_id,
                        state=default_state,
                        temp_profile_data=temp_profile_data,
                    )
                    self.save_session(default_session)
                    return default_session

                state_str = row['state']
                current_job_id = row['current_job_id']
                onboarding_step = row['onboarding_step']
                temp_profile_str = row['temp_profile_data']
                active_artifact_type = row.get('active_artifact_type')
                active_artifact_id = row.get('active_artifact_id')
                active_job_id = row.get('active_job_id')
                active_brief_id = row.get('active_brief_id')
                active_pack_id = row.get('active_pack_id')
                current_selection_index = row.get('current_selection_index')
                
                state = normalize_user_state(state_str)

                # Session state recovery logic was moved to orchestrator

                temp_profile_data = None
                if temp_profile_str:
                    if isinstance(temp_profile_str, dict):
                        temp_profile_data = temp_profile_str
                    elif isinstance(temp_profile_str, str):
                        try:
                            temp_profile_data = json.loads(temp_profile_str)
                        except Exception as e:
                            logger.error(f"Failed to deserialize temp_profile_data JSON: {e}")

                if not temp_profile_data and state == UserJourneyState.PROFILE_READY:
                    temp_profile_data = self._load_profile_data(user_id)

                return Session(
                    user_id=user_id,
                    state=state,
                    current_job_id=current_job_id,
                    onboarding_step=onboarding_step,
                    temp_profile_data=temp_profile_data,
                    active_artifact_type=active_artifact_type,
                    active_artifact_id=active_artifact_id,
                    active_job_id=active_job_id,
                    active_brief_id=active_brief_id,
                    active_pack_id=active_pack_id,
                    current_selection_index=current_selection_index
                )
        except Exception as e:
            logger.error(f"Failed to retrieve session for user {user_id}: {e}")
            # Attempt profile recovery even when session query fails
            try:
                profile_data = self._load_profile_data(user_id)
                if profile_data:
                    cv = (profile_data.get("cv_content") or "").strip()
                    if cv and len(cv) > 50:
                        logger.info(f"Exception-path profile recovery: user {user_id[:12]}... has CV ({len(cv)} chars)")
                        return Session(user_id=user_id, state=UserJourneyState.PROFILE_READY, temp_profile_data=profile_data)
            except Exception:
                pass
            return Session(user_id=user_id, state=UserJourneyState.NEW_USER)

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
                    """, (session.user_id, f"user_{session.user_id}@careerloop.internal"))
                    cursor.execute(f"""
                        INSERT INTO {self._tbl('sessions')} (
                            user_id, state, current_job_id, onboarding_step, temp_profile_data, 
                            active_artifact_type, active_artifact_id, active_job_id, active_brief_id, active_pack_id, current_selection_index, 
                            updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (user_id) DO UPDATE SET
                            state = EXCLUDED.state,
                            current_job_id = EXCLUDED.current_job_id,
                            onboarding_step = EXCLUDED.onboarding_step,
                            temp_profile_data = EXCLUDED.temp_profile_data,
                            active_artifact_type = EXCLUDED.active_artifact_type,
                            active_artifact_id = EXCLUDED.active_artifact_id,
                            active_job_id = EXCLUDED.active_job_id,
                            active_brief_id = EXCLUDED.active_brief_id,
                            active_pack_id = EXCLUDED.active_pack_id,
                            current_selection_index = EXCLUDED.current_selection_index,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (
                        session.user_id,
                        session.state.value,
                        session.current_job_id,
                        session.onboarding_step,
                        temp_profile_str,
                        session.active_artifact_type,
                        session.active_artifact_id,
                        session.active_job_id,
                        session.active_brief_id,
                        session.active_pack_id,
                        session.current_selection_index
                    ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to save session for user {session.user_id}: {e}")
            return False

    def update_state(self, user_id: str, state: UserJourneyState) -> bool:
        """Helper to quickly update state only."""
        try:
            state = normalize_user_state(state) or UserJourneyState.NEW_USER
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
