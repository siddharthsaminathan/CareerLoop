import json
import logging
from typing import Tuple, Optional
from careerloop.session.states import UserJourneyState
from careerloop.session.session_store import SessionStore, Session
from careerloop.llm_chat import OnboardingAgent
from careerloop.sources.linkedin_scraper import LinkedInScraper

logger = logging.getLogger("careerloop.onboarding.onboarding_flow")

REQUIRED_FIELDS = [
    "target_roles", "target_cities", "salary_expectations",
    "notice_period", "aggressiveness",
]

STEP_IDLE = 0
STEP_IDENTIFYING = 1
STEP_PROFILE_CONFIRMATION = 2
STEP_WAITING_CV = 3
STEP_COLLECTING = 4

class OnboardingFlow:
    """
    Handles the state transitions for a new user through the questionnaire.
    Returns (ResponseText, NextState).
    """
    def __init__(self, session_store: SessionStore):
        self.session_store = session_store
        self.agent = OnboardingAgent()

    def handle_message(self, session: Session, text: str) -> Tuple[str, UserJourneyState]:
        state = session.state
        step = session.onboarding_step
        data = session.temp_profile_data or self.session_store._load_profile_data(session.user_id) or {}

        if state == UserJourneyState.PROFILE_READY:
            reply = (
                f"Your profile is already set up! You're targeting **{data.get('target_roles', 'N/A')}** roles "
                f"in **{data.get('target_cities', 'N/A')}**.\n\n"
                "What would you like to do? Just chat with me or ask for your daily briefing."
            )
            return (reply, UserJourneyState.PROFILE_READY)

        if step == STEP_IDLE:
            session.onboarding_step = STEP_IDENTIFYING
            session.temp_profile_data = data or {}
            if not self.session_store.save_session(session):
                raise RuntimeError("Failed to persist session state.")
            reply = "Welcome to CareerLoop! Let's get you set up in less than a minute. What is your full name?"
            return (reply, UserJourneyState.NEW_USER)

        if step == STEP_IDENTIFYING:
            text_clean = text.strip()
            # If the user pasted a direct LinkedIn URL instead of name
            if "linkedin.com" in text_clean.lower() and text_clean.startswith("http"):
                scraper = LinkedInScraper()
                try:
                    scraped = scraper.scrape_profile(text_clean)
                    session.temp_profile_data.update(scraped)
                    session.onboarding_step = STEP_WAITING_CV
                    if not self.session_store.save_session(session):
                        raise RuntimeError("Failed to persist session.")
                    self._commit_profile_to_db(session.user_id, session.temp_profile_data)
                    reply = (
                        f"Awesome! I scraped your LinkedIn profile directly.\n\n"
                        f"Prefilled details:\n"
                        f"• **Roles:** {scraped.get('target_roles', 'N/A')}\n"
                        f"• **Cities:** {scraped.get('target_cities', 'N/A')}\n"
                        f"• **Salary:** {scraped.get('salary_expectations', 'N/A')}\n"
                        f"• **Notice:** {scraped.get('notice_period', 'N/A')}\n\n"
                        f"Please upload your latest resume/CV text (or paste it here) to finalize your profile setup."
                    )
                    return (reply, UserJourneyState.NEW_USER)
                except Exception as e:
                    logger.error(f"LinkedIn URL scrape failed: {e}")

            # Normal name search
            scraper = LinkedInScraper()
            results = scraper.search_profiles(text_clean)
            if results:
                session.temp_profile_data["search_results"] = results
                session.temp_profile_data["full_name"] = text_clean
                session.onboarding_step = STEP_PROFILE_CONFIRMATION
                if not self.session_store.save_session(session):
                    raise RuntimeError("Failed to persist session.")
                
                profile = results[0]
                reply = (
                    f"I found a LinkedIn profile matching your name:\n\n"
                    f"💼 **{profile['name']}**\n"
                    f"📌 *{profile['headline']}*\n"
                    f"📍 {profile['location']}\n"
                    f"🏢 Current: {profile['current_company']}\n\n"
                    f"Is this you? Please reply with:\n"
                    f"**1** = Yes, that's me!\n"
                    f"**2** = No, that's not me\n"
                    f"**3** = Skip and enter details manually"
                )
                return (reply, UserJourneyState.NEW_USER)
            else:
                reply = f"I couldn't find any LinkedIn profiles matching '{text_clean}'. Please try typing your full name again, or paste your direct LinkedIn profile URL."
                return (reply, UserJourneyState.NEW_USER)

        if step == STEP_PROFILE_CONFIRMATION:
            choice = text.strip()
            if choice == "1" or "yes" in choice.lower():
                results = session.temp_profile_data.get("search_results", [])
                if not results:
                    reply = "No profiles found in search history. Let's do a manual setup. What roles are you targeting?"
                    session.onboarding_step = STEP_COLLECTING
                    if not self.session_store.save_session(session):
                        raise RuntimeError("Failed to save session.")
                    return (reply, UserJourneyState.NEW_USER)
                
                profile = results[0]
                scraper = LinkedInScraper()
                scraped = scraper.scrape_profile(profile["url"])
                
                session.temp_profile_data.update(scraped)
                session.onboarding_step = STEP_WAITING_CV
                if not self.session_store.save_session(session):
                    raise RuntimeError("Failed to save session.")
                
                self._commit_profile_to_db(session.user_id, session.temp_profile_data)
                
                reply = (
                    f"Awesome! I've prefilled your profile from your LinkedIn, {profile['name']}!\n\n"
                    f"• **Roles:** {scraped.get('target_roles')}\n"
                    f"• **Cities:** {scraped.get('target_cities')}\n"
                    f"• **Salary:** {scraped.get('salary_expectations')}\n"
                    f"• **Notice:** {scraped.get('notice_period')}\n\n"
                    f"Now, please upload your latest resume/CV text (paste it here) to finalize your profile setup."
                )
                return (reply, UserJourneyState.NEW_USER)
                
            elif choice == "2" or "no" in choice.lower():
                session.onboarding_step = STEP_IDENTIFYING
                if not self.session_store.save_session(session):
                    raise RuntimeError("Failed to save session.")
                reply = "Got it! Please paste your direct LinkedIn profile URL (e.g. https://linkedin.com/in/yourprofile) so I can pull the correct page."
                return (reply, UserJourneyState.NEW_USER)
                
            else: # Choice 3 or skip
                session.onboarding_step = STEP_COLLECTING
                if not self.session_store.save_session(session):
                    raise RuntimeError("Failed to save session.")
                reply = "Sure! Let's build your profile manually. Paste your LinkedIn profile, paste your CV text, or tell me: what roles are you targeting?"
                return (reply, UserJourneyState.NEW_USER)

        if step == STEP_WAITING_CV:
            # The input text is the CV content
            cv_text = text.strip()
            if len(cv_text) < 100:
                reply = "That CV text looks a bit too short. Please copy-paste your full CV/resume text here."
                return (reply, UserJourneyState.NEW_USER)
            
            session.temp_profile_data["cv_content"] = cv_text
            
            # Let's see if we have all required fields. Run LLM check if needed or just commit
            missing = [f for f in REQUIRED_FIELDS if not session.temp_profile_data.get(f)]
            if missing:
                session.onboarding_step = STEP_COLLECTING
                if not self.session_store.save_session(session):
                    raise RuntimeError("Failed to save session.")
                reply = f"Thank you for uploading your CV! I need a few more details to customize your target metrics: {', '.join(missing).replace('_', ' ')}. Could you tell me about those?"
                return (reply, UserJourneyState.NEW_USER)
            
            # All complete!
            self._commit_profile_to_db(session.user_id, session.temp_profile_data)
            self._update_portals_yml(session.temp_profile_data.get('target_roles', ''))
            
            full_name = session.temp_profile_data.get("full_name") or "User"
            session.temp_profile_data = None
            session.state = UserJourneyState.PROFILE_READY
            if not self.session_store.save_session(session):
                raise RuntimeError("Failed to save session.")
                
            reply = (
                f"Your profile is complete! Welcome to CareerLoop, {full_name}!\n"
                f"• **Roles:** {data.get('target_roles', 'N/A')}\n"
                f"• **Cities:** {data.get('target_cities', 'N/A')}\n"
                f"• **Salary:** {data.get('salary_expectations', 'N/A')}\n"
                f"• **Notice:** {data.get('notice_period', 'N/A')}\n"
                f"• **Mode:** {data.get('aggressiveness', 'N/A')}\n\n"
                f"You can now ask me for your daily briefing."
            )
            return (reply, UserJourneyState.PROFILE_READY)

        if step == STEP_COLLECTING:
            updated_data, reply, is_complete = self.agent.process(text, data)
            session.temp_profile_data = updated_data
            
            if is_complete:
                missing = [f for f in REQUIRED_FIELDS if not updated_data.get(f)]
                if missing:
                    reply = f"I still need a few more details: {', '.join(missing).replace('_', ' ')}. Could you share those?"
                    if not self.session_store.save_session(session):
                        raise RuntimeError(f"Failed to persist session state {session.state}.")
                    return (reply, state)

                self._commit_profile_to_db(session.user_id, updated_data)
                self._update_portals_yml(updated_data.get('target_roles', ''))

                session.temp_profile_data = None
                session.state = UserJourneyState.PROFILE_READY
                if not self.session_store.save_session(session):
                    raise RuntimeError(f"Failed to persist session state {session.state}. Check database connection.")

                reply = (
                    f"Your profile is complete! Here's a summary:\n"
                    f"• **Roles:** {updated_data.get('target_roles', 'N/A')}\n"
                    f"• **Cities:** {updated_data.get('target_cities', 'N/A')}\n"
                    f"• **Salary:** {updated_data.get('salary_expectations', 'N/A')}\n"
                    f"• **Notice:** {updated_data.get('notice_period', 'N/A')}\n"
                    f"• **Mode:** {updated_data.get('aggressiveness', 'N/A')}\n\n"
                    f"I'll now match you with relevant jobs. Ask me for your daily briefing."
                )
                return (reply, UserJourneyState.PROFILE_READY)
            else:
                if not self.session_store.save_session(session):
                    raise RuntimeError(f"Failed to persist session state {session.state}. Check database connection.")
                return (reply, state)

        return ("I didn't quite catch that. Could you rephrase? I'm collecting your profile details.", state)

    def _update_portals_yml(self, target_roles: str):
        import os, yaml
        portals_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "portals.yml"))
        templates_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "templates", "portals.example.yml"))
        source_path = portals_path if os.path.exists(portals_path) else templates_path
        if not os.path.exists(source_path):
            return
        with open(source_path, 'r') as f:
            config = yaml.safe_load(f)
        roles = [r.strip() for r in target_roles.split(',') if r.strip()]
        if roles and 'title_filter' in config:
            existing = set(config['title_filter'].get('positive', []))
            for r in roles:
                existing.add(r)
            config['title_filter']['positive'] = list(existing)
        with open(portals_path, 'w') as f:
            yaml.dump(config, f, sort_keys=False)

    def _commit_profile_to_db(self, user_id: str, profile_data: dict):
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
