from enum import Enum

class UserState(Enum):
    # Onboarding States
    IDLE = "IDLE"
    ONBOARDING_WAITING_CV = "ONBOARDING_WAITING_CV"
    ONBOARDING_Q1_ROLES = "ONBOARDING_Q1_ROLES"
    ONBOARDING_Q2_CITIES = "ONBOARDING_Q2_CITIES"
    ONBOARDING_Q3_SALARY = "ONBOARDING_Q3_SALARY"
    ONBOARDING_Q4_NOTICE = "ONBOARDING_Q4_NOTICE"
    ONBOARDING_Q5_MODE = "ONBOARDING_Q5_MODE"

    # Active Triage States
    PROFILE_COMPLETE = "PROFILE_COMPLETE"
    DAILY_BRIEF_SENT = "PROFILE_COMPLETE"
    REVIEWING_JOB = "REVIEWING_JOB"
    
    # Compilation & Action States
    PACK_GENERATING = "PACK_GENERATING"
    PACK_READY = "PACK_READY"
    AWAITING_RESUME_REVIEW = "AWAITING_RESUME_REVIEW"
    AWAITING_APPLICATION_CONFIRMATION = "AWAITING_APPLICATION_CONFIRMATION"
    APPLIED = "APPLIED"

    # Feedback & Interview States
    FOLLOWUP_DUE = "FOLLOWUP_DUE"
    INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED"
    INTERVIEW_PREP_READY = "INTERVIEW_PREP_READY"
    POST_INTERVIEW_DEBRIEF = "POST_INTERVIEW_DEBRIEF"


LEGACY_STATE_ALIASES = {
    "DAILY_BRIEF_SENT": UserState.PROFILE_COMPLETE,
}


def normalize_user_state(raw_state) -> UserState | None:
    """Normalize persisted/checkpointed state names into the canonical enum."""
    if isinstance(raw_state, UserState):
        return UserState.PROFILE_COMPLETE if raw_state.name == "DAILY_BRIEF_SENT" else raw_state

    state_str = str(raw_state or "").strip()
    if not state_str:
        return None

    if state_str.startswith("UserState."):
        state_str = state_str.split(".", 1)[1]

    if state_str in LEGACY_STATE_ALIASES:
        return LEGACY_STATE_ALIASES[state_str]

    try:
        return UserState(state_str)
    except ValueError:
        try:
            return UserState[state_str]
        except KeyError:
            return None
