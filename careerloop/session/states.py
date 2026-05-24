"""CareerLoop session user states.

Only 11 reachable states. Every state has at least one setter path
and at least one handler path in supervisor_graph.py.
"""

from enum import Enum


class UserState(str, Enum):
    # ── Onboarding ────────────────────────────────────────────
    IDLE = "IDLE"
    ONBOARDING_WAITING_CV = "ONBOARDING_WAITING_CV"
    ONBOARDING_COLLECTING = "ONBOARDING_COLLECTING"

    # ── Active use ────────────────────────────────────────────
    PROFILE_COMPLETE = "PROFILE_COMPLETE"
    SCAN_RUNNING = "SCAN_RUNNING"
    BRIEF_AVAILABLE = "BRIEF_AVAILABLE"

    # ── Job review → pack → apply ─────────────────────────────
    REVIEWING_JOB = "REVIEWING_JOB"
    PACK_GENERATING = "PACK_GENERATING"
    PACK_READY = "PACK_READY"
    AWAITING_APPLICATION_CONFIRMATION = "AWAITING_APPLICATION_CONFIRMATION"
    APPLIED = "APPLIED"


# ── Legacy state migration ───────────────────────────────────
# Old persisted rows may carry renamed or removed states.
# Map them to the nearest current equivalent. Never reset to IDLE.

_LEGACY_MAP: dict[str, str] = {
    "DAILY_BRIEF_SENT": UserState.PROFILE_COMPLETE.value,
    "ONBOARDING_Q1_ROLES": UserState.ONBOARDING_COLLECTING.value,
    "ONBOARDING_Q2_CITIES": UserState.ONBOARDING_COLLECTING.value,
    "ONBOARDING_Q3_SALARY": UserState.ONBOARDING_COLLECTING.value,
    "ONBOARDING_Q4_NOTICE": UserState.ONBOARDING_COLLECTING.value,
    "ONBOARDING_Q5_MODE": UserState.ONBOARDING_COLLECTING.value,
    "FOLLOWUP_DUE": UserState.BRIEF_AVAILABLE.value,
    "INTERVIEW_SCHEDULED": UserState.APPLIED.value,
    "INTERVIEW_PREP_READY": UserState.APPLIED.value,
    "POST_INTERVIEW_DEBRIEF": UserState.APPLIED.value,
}


def normalize_user_state(raw: str | UserState | None) -> UserState:
    """Coerce any raw state value into a valid current UserState.

    Handles:
    - Already-valid UserState enum members
    - Current string values
    - Legacy/renamed states via _LEGACY_MAP
    - Unknown/unexpected values -> IDLE (with logged warning)
    - None / empty -> IDLE
    """
    if raw is None:
        return UserState.IDLE

    # Already a UserState member
    if isinstance(raw, UserState):
        return raw

    # Try current enum values first
    try:
        return UserState(raw)
    except ValueError:
        pass

    # Try legacy migration
    migrated = _LEGACY_MAP.get(raw)
    if migrated is not None:
        import logging
        logging.getLogger("careerloop.session.states").info(
            "Migrating legacy state '%s' -> '%s'", raw, migrated
        )
        return UserState(migrated)

    # Unknown -- reset to IDLE with warning
    import logging
    logging.getLogger("careerloop.session.states").warning(
        "Unknown state '%s' encountered. Resetting to IDLE.", raw
    )
    return UserState.IDLE
