import os
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from careerloop.session.states import UserState
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

    def get_session(self, user_id: str) -> Session:
        """Retrieves a session from the store. If not exists, initializes a default IDLE session."""
        try:
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT state, current_job_id, onboarding_step, temp_profile_data FROM public.sessions WHERE user_id = %s",
                        (user_id,)
                    )
                    row = cursor.fetchone()
                
                if not row:
                    # Initialize default session in IDLE state if it does not exist
                    default_session = Session(user_id=user_id, state=UserState.IDLE)
                    self.save_session(default_session)
                    return default_session

                state_str = row['state']
                current_job_id = row['current_job_id']
                onboarding_step = row['onboarding_step']
                temp_profile_str = row['temp_profile_data']
                
                # Safe fallback for enum mapping
                try:
                    state = UserState(state_str)
                except ValueError:
                    logger.warning(f"Unknown state '{state_str}' encountered in DB for user {user_id}. Resetting to IDLE.")
                    state = UserState.IDLE

                temp_profile_data = None
                if temp_profile_str:
                    if isinstance(temp_profile_str, dict):
                        temp_profile_data = temp_profile_str
                    elif isinstance(temp_profile_str, str):
                        try:
                            temp_profile_data = json.loads(temp_profile_str)
                        except Exception as e:
                            logger.error(f"Failed to deserialize temp_profile_data JSON: {e}")

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
                    cursor.execute("""
                        INSERT INTO public.users (id, email, full_name)
                        VALUES (%s, %s, 'Unknown User')
                        ON CONFLICT (id) DO NOTHING;
                    """, (session.user_id, f"user_{session.user_id}@placeholder.com"))
                    cursor.execute("""
                        INSERT INTO public.sessions (user_id, state, current_job_id, onboarding_step, temp_profile_data, updated_at)
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
            with self.db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE public.sessions SET state = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
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
                    cursor.execute("DELETE FROM public.sessions WHERE user_id = %s", (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to delete session for user {user_id}: {e}")
            return False
