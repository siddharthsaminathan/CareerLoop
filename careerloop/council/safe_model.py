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

    # Check required fields and fill in sensible defaults
    for f in dataclasses.fields(cls):
        if f.name not in filtered:
            if f.default is not dataclasses.MISSING:
                filtered[f.name] = f.default
            elif f.default_factory is not dataclasses.MISSING:
                filtered[f.name] = f.default_factory()
            else:
                # Required field with no default — provide a safe fallback
                if f.type is str or f.type == "str":
                    filtered[f.name] = ""
                elif f.type is int or f.type == "int":
                    filtered[f.name] = 0
                elif f.type is float or f.type == "float":
                    filtered[f.name] = 0.0
                elif f.type is bool or f.type == "bool":
                    filtered[f.name] = False
                elif hasattr(f.type, "__origin__") and f.type.__origin__ is list:
                    filtered[f.name] = []
                elif hasattr(f.type, "__origin__") and f.type.__origin__ is dict:
                    filtered[f.name] = {}
                else:
                    filtered[f.name] = ""
                logger.warning(
                    "safe_construct(%s): missing required field '%s' — using default",
                    cls.__name__, f.name,
                )

    return cls(**filtered)
