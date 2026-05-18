"""
Runtime datetime context for Resume Council prompts.
NEVER hardcode dates in prompts — inject this instead.
"""

from datetime import datetime, timezone


def get_runtime_context() -> dict:
    """Return runtime context for prompt injection.

    Usage in graph nodes:
        ctx = get_runtime_context()
        prompt = f"Today is {ctx['current_month']}."
    """
    now = datetime.now(timezone.utc)
    return {
        "current_datetime": now.isoformat(),
        "timezone": "UTC",
        "current_year": now.year,
        "current_month": now.strftime("%B %Y"),
        "elapsed_years": lambda start_year: now.year - start_year,
    }
