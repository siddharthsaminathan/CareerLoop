import json
import logging
from typing import Tuple, Optional
from careerloop.session.states import UserState
from careerloop.session.session_store import SessionStore, Session
from careerloop.llm_chat import OnboardingAgent

logger = logging.getLogger("careerloop.onboarding.onboarding_flow")

class OnboardingFlow:
    """
    Handles the state transitions for a new user through the questionnaire.
    Returns (ResponseText, NextState).
    """
    def __init__(self, session_store: SessionStore):
        self.session_store = session_store
        self.agent = OnboardingAgent()

    def handle_message(self, session: Session, text: str) -> Tuple[str, UserState]:
        state = session.state
        data = session.temp_profile_data or self.session_store._load_profile_data(session.user_id)

        if state == UserState.IDLE:
            state = self.session_store.infer_onboarding_state(data)
            session.state = state
            session.temp_profile_data = data or None
            if not self.session_store.save_session(session):
                raise RuntimeError(f"Failed to persist session state {session.state}. Check database connection.")

        if state == UserState.PROFILE_COMPLETE:
            return (
                "Your profile is already set up. Type `/status` to review it, `/brief` to see today's brief, or `/scan` to search for new jobs.",
                UserState.PROFILE_COMPLETE,
            )

        if state.name.startswith("ONBOARDING_"):
            updated_data, reply, is_complete = self.agent.process(text, data)
            session.temp_profile_data = updated_data
            
            if is_complete:
                # 1. Save final profile to public.users table in DB
                self._commit_profile_to_db(session.user_id, updated_data)
                
                # 2. Update portals.yml with target roles
                self._update_portals_yml(updated_data.get('target_roles', ''))
                
                # Clean up temp data
                session.temp_profile_data = None
                session.state = UserState.PROFILE_COMPLETE
                if not self.session_store.save_session(session):
                    raise RuntimeError(f"Failed to persist session state {session.state}. Check database connection.")

                return (
                    reply + "\n\nAwesome! Your profile is set up. Type `/scan` when you want me to search for matching jobs.",
                    UserState.PROFILE_COMPLETE
                )
            else:
                if not self.session_store.save_session(session):
                    raise RuntimeError(f"Failed to persist session state {session.state}. Check database connection.")
                return (reply, state)

        return ("I'm not sure how to handle that right now.", state)

    def _update_portals_yml(self, target_roles: str):
        """Parse target roles and inject them into portals.yml."""
        import os, yaml
        portals_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "portals.yml"))
        templates_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "templates", "portals.example.yml"))
        
        # If portals.yml doesn't exist, use the template
        source_path = portals_path if os.path.exists(portals_path) else templates_path
        if not os.path.exists(source_path):
            return

        with open(source_path, 'r') as f:
            config = yaml.safe_load(f)

        # Basic parsing of the roles string (comma separated)
        roles = [r.strip() for r in target_roles.split(',') if r.strip()]
        if roles and 'title_filter' in config:
            # Append to positive filters instead of replacing, to keep the robust default structure.
            existing = set(config['title_filter'].get('positive', []))
            for r in roles:
                existing.add(r)
            config['title_filter']['positive'] = list(existing)

        with open(portals_path, 'w') as f:
            yaml.dump(config, f, sort_keys=False)

    def _commit_profile_to_db(self, user_id: str, profile_data: dict):
        """Update the users table with the collected preferences."""
        def clean(value):
            if value is None:
                return None
            if isinstance(value, str):
                stripped = value.strip()
                if not stripped or stripped.lower() in {"n/a", "na", "none", "null", "-"}:
                    return None
                return stripped
            return value

        try:
            with self.session_store.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT master_cv_markdown, work_style_prefs FROM {self.session_store._tbl('users')} WHERE id = %s",
                        (user_id,),
                    )
                    existing = cur.fetchone() or {}
                    existing_prefs = self.session_store._parse_profile_prefs(existing.get("work_style_prefs"))

                    cv_content = clean(profile_data.get("cv_content")) or existing.get("master_cv_markdown") or ""
                    merged_prefs = dict(existing_prefs)
                    for key in [
                        "target_roles",
                        "target_cities",
                        "salary_expectations",
                        "notice_period",
                        "aggressiveness",
                    ]:
                        next_value = clean(profile_data.get(key))
                        if next_value is not None:
                            merged_prefs[key] = next_value

                    cur.execute(f"""
                        INSERT INTO {self.session_store._tbl('users')} (id, email, full_name, created_at, updated_at)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO NOTHING
                    """, (user_id, f"user_{user_id}@placeholder.com", "Unknown User"))
                    cur.execute(f"""
                        UPDATE {self.session_store._tbl('users')}
                        SET master_cv_markdown = %s,
                            work_style_prefs = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (
                        cv_content,
                        json.dumps(merged_prefs),
                        user_id
                    ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving profile to DB: {e}")
