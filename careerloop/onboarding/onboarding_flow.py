import json
from typing import Tuple, Optional
from careerloop.session.states import UserState
from careerloop.session.session_store import SessionStore, Session
from careerloop.llm_chat import OnboardingAgent

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
        data = session.temp_profile_data or {}

        if state == UserState.IDLE:
            # Start onboarding
            session.state = UserState.ONBOARDING_WAITING_CV
            self.session_store.save_session(session)
            return (
                "Welcome to CareerLoop! I am your AI agent. I need to collect some details to set up your profile: your CV, target roles, target cities, salary expectations, notice period, and aggressiveness. To get started, please paste your full Resume/CV in text format, or provide a link to it, and tell me a bit about what you're looking for.",
                UserState.ONBOARDING_WAITING_CV
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
                session.state = UserState.DAILY_BRIEF_SENT
                self.session_store.save_session(session)
                
                return (
                    reply + "\n\nAwesome! Your profile is set up. I'll start monitoring jobs for you and send you daily briefs. You are now fully onboarded.",
                    UserState.DAILY_BRIEF_SENT
                )
            else:
                self.session_store.save_session(session)
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
        try:
            with self.session_store.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE public.users 
                        SET master_cv_markdown = %s,
                            work_style_prefs = %s,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (
                        profile_data.get('cv_content', ''),
                        json.dumps({
                            'target_roles': profile_data.get('target_roles', ''),
                            'target_cities': profile_data.get('target_cities', ''),
                            'salary_expectations': profile_data.get('salary_expectations', ''),
                            'notice_period': profile_data.get('notice_period', ''),
                            'aggressiveness': profile_data.get('aggressiveness', ''),
                        }),
                        user_id
                    ))
                conn.commit()
        except Exception as e:
            print(f"Error saving profile to DB: {e}")
