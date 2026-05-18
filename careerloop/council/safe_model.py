"""
Safe dataclass construction that strips unknown keys, logs warnings,
and validates required fields. Used by orchestrator to reconstruct
typed models from raw LangGraph state dicts.
"""

import dataclasses
import logging
from typing import Type, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


def safe_construct(cls: Type[T], data: dict) -> T:
    """Construct a dataclass from a dict, stripping unknown keys and logging warnings.

    Args:
        cls: The dataclass type to construct.
        data: Raw dict possibly containing extra keys not in the dataclass.

    Returns:
        An instance of cls constructed from the filtered dict.
        Required fields missing from data will use their defaults or raise TypeError.
    """
    valid_fields = {f.name for f in dataclasses.fields(cls)}
    unknown = {k for k in data if k not in valid_fields}

    if unknown:
        logger.warning(
            "safe_construct(%s): dropping unknown keys: %s", cls.__name__, unknown
        )

    filtered = {k: v for k, v in data.items() if k in valid_fields}

    # Check required fields (no default and no default_factory)
    required = {
        f.name
        for f in dataclasses.fields(cls)
        if f.default is dataclasses.MISSING
        and f.default_factory is dataclasses.MISSING
    }
    missing = required - set(filtered.keys())

    if missing:
        logger.warning(
            "safe_construct(%s): missing required fields: %s — will raise TypeError",
            cls.__name__,
            missing,
        )

    return cls(**filtered)
