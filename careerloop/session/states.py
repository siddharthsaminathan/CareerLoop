"""CareerLoop session user states (V2 Architecture).

Implements the 3-Layer State Architecture:
1. User Journey State (Long-term workflow status)
2. Active Context (Managed as JSON/DB fields, not enums)
3. Background Work State (Async execution status)
"""

from enum import Enum


class UserJourneyState(str, Enum):
    NEW_USER = "NEW_USER"               # Equivalent to Onboarding
    PROFILE_READY = "PROFILE_READY"     # Equivalent to Profile Complete
    APPLICATION_PENDING = "APPLICATION_PENDING"
    INTERVIEW_ACTIVE = "INTERVIEW_ACTIVE"


class BackgroundWorkStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# ── Legacy state migration ───────────────────────────────────
# Old persisted rows carry V1 states. Map them to the nearest V2 equivalent.

_LEGACY_MAP: dict[str, str] = {
    # V1 Onboarding states -> V2 NEW_USER
    "IDLE": UserJourneyState.NEW_USER.value,
    "ONBOARDING": UserJourneyState.NEW_USER.value,
    "ONBOARDING_IDENTIFYING": UserJourneyState.NEW_USER.value,
    "ONBOARDING_PROFILE_CONFIRMATION": UserJourneyState.NEW_USER.value,
    "ONBOARDING_WAITING_CV": UserJourneyState.NEW_USER.value,
    "ONBOARDING_COLLECTING": UserJourneyState.NEW_USER.value,
    "ONBOARDING_Q1_ROLES": UserJourneyState.NEW_USER.value,
    "ONBOARDING_Q2_CITIES": UserJourneyState.NEW_USER.value,
    "ONBOARDING_Q3_SALARY": UserJourneyState.NEW_USER.value,
    "ONBOARDING_Q4_NOTICE": UserJourneyState.NEW_USER.value,
    "ONBOARDING_Q5_MODE": UserJourneyState.NEW_USER.value,
    
    # V1 Artifact & Job states -> V2 PROFILE_READY
    "PROFILE_COMPLETE": UserJourneyState.PROFILE_READY.value,
    "SCAN_RUNNING": UserJourneyState.PROFILE_READY.value,
    "REVIEWING_BRIEF": UserJourneyState.PROFILE_READY.value,
    "BRIEF_AVAILABLE": UserJourneyState.PROFILE_READY.value,
    "REVIEWING_JOB": UserJourneyState.PROFILE_READY.value,
    "RESEARCHING_COMPANY": UserJourneyState.PROFILE_READY.value,
    "PACK_GENERATING": UserJourneyState.PROFILE_READY.value,
    "REVIEWING_PACK": UserJourneyState.PROFILE_READY.value,
    "PACK_READY": UserJourneyState.PROFILE_READY.value,
    "DAILY_BRIEF_SENT": UserJourneyState.PROFILE_READY.value,
    "FOLLOWUP_DUE": UserJourneyState.PROFILE_READY.value,
    
    # V1 Application states -> V2 APPLICATION_PENDING
    "APPLICATION_PENDING_CONFIRMATION": UserJourneyState.APPLICATION_PENDING.value,
    "AWAITING_APPLICATION_CONFIRMATION": UserJourneyState.APPLICATION_PENDING.value,
    "APPLIED": UserJourneyState.APPLICATION_PENDING.value,
    
    # V1 Interview states -> V2 INTERVIEW_ACTIVE
    "INTERVIEW_SCHEDULED": UserJourneyState.INTERVIEW_ACTIVE.value,
    "INTERVIEW_PREP_READY": UserJourneyState.INTERVIEW_ACTIVE.value,
    "POST_INTERVIEW_DEBRIEF": UserJourneyState.INTERVIEW_ACTIVE.value,
}


def normalize_user_state(raw: str | UserJourneyState | None) -> UserJourneyState:
    """Coerce any raw state value into a valid current UserJourneyState.

    Handles:
    - Already-valid UserJourneyState enum members
    - Current string values
    - Legacy/renamed states via _LEGACY_MAP
    - Unknown/unexpected values -> NEW_USER (with logged warning)
    - None / empty -> NEW_USER
    """
    if raw is None:
        return UserJourneyState.NEW_USER

    # Already a UserJourneyState member
    if isinstance(raw, UserJourneyState):
        return raw

    # Try current enum values first
    try:
        return UserJourneyState(raw)
    except ValueError:
        pass

    # Try legacy migration
    migrated = _LEGACY_MAP.get(raw)
    if migrated is not None:
        import logging
        logging.getLogger("careerloop.session.states").info(
            "Migrating legacy state '%s' -> '%s'", raw, migrated
        )
        return UserJourneyState(migrated)

    # Unknown -- reset to NEW_USER with warning
    import logging
    logging.getLogger("careerloop.session.states").warning(
        "Unknown state '%s' encountered. Resetting to NEW_USER.", raw
    )
    return UserJourneyState.NEW_USER
