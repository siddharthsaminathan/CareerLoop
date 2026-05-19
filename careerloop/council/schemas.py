"""
Schema enforcement for Resume Council LLM node outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


NODE_SCHEMAS: dict[str, dict[str, Any]] = {
    "company_intelligence": {
        "required": {
            "company_name": str,
            "company_summary": str,
            "grounding_status": str,
            "confidence": (int, float),
            "unknowns": list,
        },
        "strongly_recommended": [
            "business_model", "india_presence", "hiring_urgency",
            "culture_signals", "red_flags", "positioning_implications",
            "s7_rewrite_context", "s6_positioning_context",
            "language_to_use", "language_to_avoid",
            "generated_at", "ttl_days",
        ],
        "enums": {"grounding_status": {"READY", "PARTIAL", "JD_ONLY", "UNGROUNDED"}},
        "confidence_fields": ["confidence"],
    },
    "role_decode": {
        "required": {
            "normalized_title": str,
            "seniority": str,
            "must_haves": list,
            "nice_to_haves": list,
            "hidden_expectations": list,
            "day_one_deliverables": list,
            "screening_keywords": list,
            "disqualifiers": list,
            "confidence": (int, float),
        },
        "confidence_fields": ["confidence"],
    },
    "user_truth": {
        "required": {
            "total_years_experience": (int, float),
            "confirmed_skills": list,
            "weak_skills": list,
            "evidence_bank": dict,
            "strongest_proof_points": list,
            "claims_allowed": list,
            "claims_not_allowed": list,
        },
        "forbidden": ["private_constraints"],
    },
    "positioning_strategy": {
        "required": {
            "one_line_positioning": str,
            "narrative_angle": str,
            "lead_strengths": list,
            "proof_points_to_emphasize": list,
            "things_to_downplay": list,
            "tone_guidance": str,
            "recruiter_first_impression_target": str,
            "application_stance": str,
            "reasoning": str,
        },
        "enums": {"application_stance": {"STRONG_PUSH", "CAREFUL_PUSH", "STRETCH", "HOLD", "SKIP"}},
    },
    "section_rewrites": {
        "required": {"rewrites": dict, "forbidden_edits": list},
    },
    "cover_note": {
        "required": {"cover_note": str},
    },
    "recruiter_message": {
        "required": {"recruiter_message": str},
    },
}


def schema_instruction(node_name: str) -> str:
    schema = NODE_SCHEMAS[node_name]
    required = schema.get("required", {})
    lines = ["Return ONLY a JSON object with this exact contract:"]
    lines.append("{")
    for key, expected in required.items():
        lines.append(f'  "{key}": {type_label(expected)},')
    lines.append("}")
    if schema.get("forbidden"):
        lines.append("Forbidden keys: " + ", ".join(schema["forbidden"]))
    if schema.get("enums"):
        for key, allowed in schema["enums"].items():
            lines.append(f"{key} must be one of: {', '.join(sorted(allowed))}")
    return "\n".join(lines)


def type_label(expected: Any) -> str:
    if expected is str:
        return '"string"'
    if expected is list:
        return "[]"
    if expected is dict:
        return "{}"
    if expected in (int, float) or expected == (int, float):
        return "0.0"
    return '"value"'


def validate_payload(node_name: str, payload: Any) -> SchemaValidationResult:
    if not isinstance(payload, dict):
        return SchemaValidationResult(False, [f"{node_name}: payload is not an object"], {})

    schema = NODE_SCHEMAS[node_name]
    errors: list[str] = []
    normalized = dict(payload)

    for key in schema.get("forbidden", []):
        if key in normalized:
            normalized.pop(key, None)

    for key, expected_type in schema.get("required", {}).items():
        if key not in normalized:
            errors.append(f"{node_name}: missing required key '{key}'")
            continue
        if not isinstance(normalized[key], expected_type):
            errors.append(
                f"{node_name}: key '{key}' expected {expected_type}, got {type(normalized[key]).__name__}"
            )

    for key in schema.get("strongly_recommended", []):
        if key not in normalized:
            errors.append(f"{node_name}: strongly recommended key '{key}' is missing")

    for key, allowed in schema.get("enums", {}).items():
        if key in normalized and normalized[key] not in allowed:
            errors.append(f"{node_name}: key '{key}' has invalid value '{normalized[key]}'")

    for key in schema.get("confidence_fields", []):
        if key in normalized and isinstance(normalized[key], (int, float)):
            if normalized[key] < 0 or normalized[key] > 1:
                errors.append(f"{node_name}: confidence field '{key}' must be 0..1")

    return SchemaValidationResult(ok=not errors, errors=errors, payload=normalized)
