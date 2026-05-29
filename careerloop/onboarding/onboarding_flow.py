import json
import logging
from datetime import date
from typing import Tuple, Optional
from careerloop.session.states import UserJourneyState
from careerloop.session.session_store import SessionStore, Session
from careerloop.llm_chat import OnboardingAgent, CVExtractionAgent
from careerloop.sources.identity_provider import LinkedInIdentityProvider

logger = logging.getLogger("careerloop.onboarding.onboarding_flow")

REQUIRED_FIELDS = [
    "target_roles", "target_cities", "salary_expectations",
    "notice_period", "aggressiveness",
]

# Step constants — stored in sessions.onboarding_step
STEP_IDLE         = 0   # First message — greet (LinkedIn-first if configured, else CV)
STEP_WAITING_CV   = 1   # Waiting for CV text or file
STEP_CONFIRMING   = 2   # Showing extracted summary — waiting for YES/correction
STEP_COLLECTING   = 3   # Conversational gap-fill for missing fields
# LinkedIn-first steps (active when SERPAPI_KEY is configured)
STEP_IDENTIFYING          = 10  # Waiting for the user's name to look up on LinkedIn
STEP_PROFILE_CONFIRMATION = 11  # Showing "Is this you?" card — waiting YES/NO


class OnboardingFlow:
    """
    Handles new-user onboarding from first message through PROFILE_READY.

    LinkedIn-first path (when SERPAPI_KEY is configured):
        IDLE → ask name → IDENTIFYING → SerpAPI search + name-match filter →
        PROFILE_CONFIRMATION ("Is this you?") → confirm → WAITING_CV → ... → PROFILE_READY

    CV-first path (fallback when SerpAPI not configured, or no LinkedIn match):
        IDLE → ask for CV → WAITING_CV → extract → CONFIRMING → confirm → PROFILE_READY
        Gap-fill loop via COLLECTING if any required field is missing.

    Key design decisions:
    - portals.yml is NEVER mutated here (multi-user unsafe)
    - All profile data is written to careerloop.users columns + work_style_prefs JSONB
    - User confirms extracted data before PROFILE_READY transition
    - Resume: reconnecting mid-flow re-emits the last contextual prompt
    """

    def __init__(self, session_store: SessionStore):
        self.session_store = session_store
        self.extraction_agent = CVExtractionAgent()
        self.onboarding_agent = OnboardingAgent()
        self.identity = LinkedInIdentityProvider()

    # ── Main entry point ──────────────────────────────────────────────────────

    def handle_message(self, session: Session, text: str) -> Tuple[str, UserJourneyState]:
        state  = session.state
        step   = session.onboarding_step
        data   = session.temp_profile_data or {}

        if state == UserJourneyState.PROFILE_READY:
            return self._already_complete(data), UserJourneyState.PROFILE_READY

        # Route by step
        if step == STEP_IDLE:
            return self._handle_idle(session)
        if step == STEP_WAITING_CV:
            return self._handle_waiting_cv(session, text, data)
        if step == STEP_CONFIRMING:
            return self._handle_confirming(session, text, data)
        if step == STEP_COLLECTING:
            return self._handle_collecting(session, text, data)

        # LinkedIn-first steps (active when SerpAPI configured)
        if step == STEP_IDENTIFYING:
            return self._handle_identifying(session, text, data)
        if step == STEP_PROFILE_CONFIRMATION:
            return self._handle_profile_confirmation(session, text, data)

        return ("I didn't quite catch that. Could you rephrase?", state)

    # ── Step handlers ─────────────────────────────────────────────────────────

    def _handle_idle(self, session: Session) -> Tuple[str, UserJourneyState]:
        session.temp_profile_data = {}
        # LinkedIn-first when SerpAPI is configured; CV-first otherwise.
        if self.identity.is_configured:
            session.onboarding_step = STEP_IDENTIFYING
            self._save(session)
            reply = (
                "Welcome to CareerLoop! I'm your AI career execution partner.\n\n"
                "Let's get you set up in under a minute. **What's your full name?** "
                "I'll find your LinkedIn profile and pre-fill everything.\n\n"
                "_(Prefer to skip? Just paste your CV/resume text instead.)_"
            )
            return reply, UserJourneyState.NEW_USER

        session.onboarding_step = STEP_WAITING_CV
        self._save(session)
        reply = (
            "Welcome to CareerLoop! I'm your AI career execution partner.\n\n"
            "Let's get your profile set up in under a minute.\n\n"
            "Please paste your CV/resume text here, or upload it as a PDF or DOCX file. "
            "I'll extract your details automatically."
        )
        return reply, UserJourneyState.NEW_USER

    def _handle_waiting_cv(self, session: Session, text: str, data: dict) -> Tuple[str, UserJourneyState]:
        # Allow skipping the CV when we already hydrated from LinkedIn.
        if text.strip().lower() in {"skip", "no", "later"} and data.get("cv_content"):
            return self._proceed_after_linkedin(session, data)

        if len(text.strip()) < 80:
            return (
                "That looks too short to be a full CV. Please paste your complete resume text, "
                "or upload a PDF/DOCX file.",
                UserJourneyState.NEW_USER,
            )

        # Extract structured fields from CV using LLM
        extracted = self.extraction_agent.extract(text)
        data.update({"cv_content": text.strip()})
        for k, v in extracted.items():
            if v and str(v).strip().lower() not in {"null", "none", "n/a", "na", "-", ""}:
                data[k] = v

        session.temp_profile_data = data
        session.onboarding_step = STEP_CONFIRMING
        self._save(session)

        return self._build_confirmation_prompt(data, extracted), UserJourneyState.NEW_USER

    def _handle_confirming(self, session: Session, text: str, data: dict) -> Tuple[str, UserJourneyState]:
        text_lower = text.strip().lower()
        affirmative = {"yes", "y", "yep", "yeah", "yup", "correct", "confirmed", "ok", "okay", "looks good", "good", "right", "perfect", "done", "proceed", "go", "confirm"}

        if text_lower in affirmative or text_lower.startswith("yes"):
            missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
            if missing:
                session.onboarding_step = STEP_COLLECTING
                self._save(session)
                field_names = ", ".join(f.replace("_", " ") for f in missing)
                return (
                    f"Almost there! I still need a few details: **{field_names}**.\n\n"
                    "Could you share those?",
                    UserJourneyState.NEW_USER,
                )
            return self._complete_onboarding(session, data)

        # User wants to correct something — feed correction into OnboardingAgent
        updated_data, reply, is_complete = self.onboarding_agent.process(text, data)
        session.temp_profile_data = updated_data
        if is_complete:
            missing = [f for f in REQUIRED_FIELDS if not updated_data.get(f)]
            if not missing:
                return self._complete_onboarding(session, updated_data)

        # Re-show summary after correction
        session.onboarding_step = STEP_CONFIRMING
        self._save(session)
        correction_prompt = self._build_confirmation_prompt(updated_data, updated_data)
        return f"{reply}\n\n{correction_prompt}", UserJourneyState.NEW_USER

    def _handle_collecting(self, session: Session, text: str, data: dict) -> Tuple[str, UserJourneyState]:
        updated_data, reply, is_complete = self.onboarding_agent.process(text, data)
        session.temp_profile_data = updated_data

        if is_complete:
            missing = [f for f in REQUIRED_FIELDS if not updated_data.get(f)]
            if missing:
                self._save(session)
                return (
                    f"I still need: {', '.join(f.replace('_', ' ') for f in missing)}. Could you share those?",
                    UserJourneyState.NEW_USER,
                )
            return self._complete_onboarding(session, updated_data)

        self._save(session)
        return reply, UserJourneyState.NEW_USER

    # ── LinkedIn-first handlers (active when SerpAPI is configured) ───────────

    def _handle_identifying(self, session: Session, text: str, data: dict) -> Tuple[str, UserJourneyState]:
        """User sent their name (or pasted a CV). Resolve their LinkedIn profile."""
        cleaned = text.strip()

        # If they pasted a CV instead of a name, switch to the CV path.
        if len(cleaned) >= 80:
            session.onboarding_step = STEP_WAITING_CV
            self._save(session)
            return self._handle_waiting_cv(session, cleaned, data)

        candidate = None
        try:
            candidate = self.identity.find_by_name(cleaned)
        except Exception as e:
            logger.warning("LinkedIn lookup failed for %r: %s", cleaned, e)

        if not candidate:
            # No match (or lookup failed) → fall back to CV-first gracefully.
            session.onboarding_step = STEP_WAITING_CV
            self._save(session)
            return (
                f"I couldn't find a confident LinkedIn match for **{cleaned}**.\n\n"
                "No problem — please paste your CV/resume text or upload a PDF/DOCX "
                "and I'll set you up from that.",
                UserJourneyState.NEW_USER,
            )

        # Stash candidate + render an "Is this you?" card.
        data["_identity_candidate"] = {
            "full_name": candidate.full_name,
            "target_roles": candidate.target_roles,
            "target_cities": candidate.target_cities,
            "cv_content": candidate.cv_content,
        }
        data["_identity_card"] = candidate.to_card()
        if candidate.full_name:
            data["full_name"] = candidate.full_name
        session.temp_profile_data = data
        session.onboarding_step = STEP_PROFILE_CONFIRMATION
        self._save(session)

        c = candidate
        return (
            "I found this profile — **is this you?**\n\n"
            f"• **{c.full_name}**\n"
            f"• {c.headline}\n"
            f"• {c.current_company}\n"
            f"• {c.location}\n"
            f"• {c.linkedin_url}\n\n"
            "Reply **YES** to use this, or **NO** to enter your details manually.",
            UserJourneyState.NEW_USER,
        )

    def _handle_profile_confirmation(self, session: Session, text: str, data: dict) -> Tuple[str, UserJourneyState]:
        """User confirms (or rejects) the resolved LinkedIn profile."""
        text_lower = text.strip().lower()
        affirmative = {"yes", "y", "yep", "yeah", "yup", "correct", "that's me", "thats me", "1", "confirm", "ok", "okay"}

        if text_lower in affirmative or text_lower.startswith("yes"):
            candidate = data.pop("_identity_candidate", {}) or {}
            data.pop("_identity_card", None)
            # Hydrate from the LinkedIn profile
            for k in ("full_name", "target_roles", "target_cities", "cv_content"):
                if candidate.get(k):
                    data[k] = candidate[k]
            session.temp_profile_data = data
            session.onboarding_step = STEP_WAITING_CV
            self._save(session)
            return (
                f"Great — I've pre-filled your profile from LinkedIn, {data.get('full_name', 'there')}!\n\n"
                "To sharpen your applications, **paste your CV/resume** (or upload a PDF/DOCX). "
                "If you'd rather skip, just reply **skip** and I'll continue with what I have.",
                UserJourneyState.NEW_USER,
            )

        if text_lower in {"skip"}:
            return self._proceed_after_linkedin(session, data)

        # Rejected → manual CV path
        data.pop("_identity_candidate", None)
        data.pop("_identity_card", None)
        session.temp_profile_data = data
        session.onboarding_step = STEP_WAITING_CV
        self._save(session)
        return (
            "No problem. Please paste your CV/resume text or upload a PDF/DOCX, "
            "and I'll set up your profile from that.",
            UserJourneyState.NEW_USER,
        )

    def _proceed_after_linkedin(self, session: Session, data: dict) -> Tuple[str, UserJourneyState]:
        """After LinkedIn hydration, either finish or gap-fill missing required fields."""
        missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
        if not missing:
            return self._complete_onboarding(session, data)
        session.onboarding_step = STEP_COLLECTING
        session.temp_profile_data = data
        self._save(session)
        field_names = ", ".join(f.replace("_", " ") for f in missing)
        return (
            f"Almost there! I still need a few details: **{field_names}**.\n\nCould you share those?",
            UserJourneyState.NEW_USER,
        )

    # ── Resume-from-step ─────────────────────────────────────────────────────

    def resume_prompt(self, session: Session) -> str:
        """Return a context-aware re-entry prompt for users reconnecting mid-flow."""
        step = session.onboarding_step
        data = session.temp_profile_data or {}

        if step == STEP_WAITING_CV:
            return (
                "Welcome back! We were setting up your profile.\n\n"
                "Please paste your CV/resume text or upload it as a PDF/DOCX to continue."
            )
        if step == STEP_CONFIRMING:
            return self._build_confirmation_prompt(data, data)
        if step == STEP_COLLECTING:
            missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
            field_names = ", ".join(f.replace("_", " ") for f in missing) if missing else "a few remaining details"
            return f"Welcome back! I still need: **{field_names}**. Could you share those?"
        # Default: restart
        return "Welcome back to CareerLoop! Please paste your CV text to get started."

    # ── Completion ────────────────────────────────────────────────────────────

    def _complete_onboarding(self, session: Session, data: dict) -> Tuple[str, UserJourneyState]:
        self._commit_profile_to_db(session.user_id, data)
        self._seed_welcome_brief(session.user_id)
        full_name = data.get("full_name") or "there"
        # P1-06: Preserve profile data (strip internal fields — keep real profile fields).
        # Clearing this to None breaks DAILY_BRIEF_SENT handler and general chat which
        # rely on temp_profile_data for CV context, roles, and salary target.
        data.pop("_identity_card", None)
        data.pop("_identity_candidate", None)
        data.pop("_active_conversation_id", None)
        session.temp_profile_data = data
        session.state = UserJourneyState.PROFILE_READY
        session.onboarding_step = 0
        self._save(session)
        reply = (
            f"Your profile is complete! Welcome to CareerLoop, {full_name}!\n\n"
            f"Here's what I've got:\n"
            f"• **Roles:** {data.get('target_roles', 'N/A')}\n"
            f"• **Cities:** {data.get('target_cities', 'N/A')}\n"
            f"• **Salary:** {data.get('salary_expectations', 'N/A')}\n"
            f"• **Notice:** {data.get('notice_period', 'N/A')}\n"
            f"• **Mode:** {data.get('aggressiveness', 'N/A')}\n\n"
            "You're all set! Ask me for your daily briefing or type /scan to find new roles."
        )
        return reply, UserJourneyState.PROFILE_READY

    def _already_complete(self, data: dict) -> str:
        return (
            f"Your profile is already set up! You're targeting "
            f"**{data.get('target_roles', 'your saved roles')}** in "
            f"**{data.get('target_cities', 'your saved cities')}**.\n\n"
            "What would you like to do? Ask for your daily briefing or type /scan."
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_confirmation_prompt(self, data: dict, extracted: dict) -> str:
        lines = ["Here's what I extracted from your CV:\n"]
        field_labels = {
            "target_roles": "Roles",
            "target_cities": "Cities",
            "salary_expectations": "Salary",
            "notice_period": "Notice",
            "aggressiveness": "Mode",
        }
        for field, label in field_labels.items():
            val = data.get(field) or extracted.get(field) or "—"
            lines.append(f"• **{label}:** {val}")

        lines.append(
            "\nReply **YES** to confirm, or tell me what needs to be corrected."
        )
        return "\n".join(lines)

    def _save(self, session: Session):
        if not self.session_store.save_session(session):
            raise RuntimeError(f"Failed to persist session for user {session.user_id}")

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
                    for key in ["target_roles", "target_cities", "salary_expectations", "notice_period", "aggressiveness"]:
                        next_value = clean(profile_data.get(key))
                        if next_value is not None:
                            merged_prefs[key] = next_value

                    # Ensure user row exists (no placeholder emails)
                    cur.execute(f"""
                        INSERT INTO {self.session_store._tbl('users')} (id, email, full_name, created_at, updated_at)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO NOTHING
                    """, (user_id, f"user_{user_id}@careerloop.internal", clean(profile_data.get("full_name")) or "User"))

                    # Write to both canonical columns AND work_style_prefs JSONB
                    cur.execute(f"""
                        UPDATE {self.session_store._tbl('users')}
                        SET master_cv_markdown   = %s,
                            work_style_prefs     = %s,
                            target_roles         = %s,
                            target_cities        = %s,
                            salary_expectations  = %s,
                            notice_period        = %s,
                            career_mode          = %s,
                            onboarding_complete  = TRUE,
                            full_name            = COALESCE(NULLIF(full_name, 'Unknown User'), NULLIF(full_name, 'User'), %s, full_name),
                            updated_at           = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (
                        cv_content,
                        json.dumps(merged_prefs),
                        clean(profile_data.get("target_roles")),
                        clean(profile_data.get("target_cities")),
                        clean(profile_data.get("salary_expectations")),
                        clean(profile_data.get("notice_period")),
                        clean(profile_data.get("aggressiveness")),
                        clean(profile_data.get("full_name")),
                        user_id,
                    ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving profile to DB: {e}")
            raise

    def _seed_welcome_brief(self, user_id: str):
        """Seed a welcome daily brief so GET /v1/briefs/latest doesn't 404.

        Uses v1 schema: daily_briefs(id, user_id, date_str, run_id, summary,
        created_at).  run_id is nullable TEXT, so no background_run FK required.
        ON CONFLICT (user_id, date_str) DO NOTHING makes this safe to re-run.
        """
        today = date.today().isoformat()
        summary = (
            "Welcome to CareerLoop! Your profile is set up and you're ready to go. "
            "Run your first scan to discover matching jobs tailored to your profile."
        )
        try:
            with self.session_store.db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO careerloop.daily_briefs (user_id, date_str, summary)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, date_str) DO NOTHING
                        """,
                        (user_id, today, summary),
                    )
                conn.commit()
            logger.info("Welcome brief seeded for user %s (date=%s)", user_id[:12], today)
        except Exception as e:
            logger.warning("Failed to seed welcome brief for %s: %s", user_id[:12], e)
