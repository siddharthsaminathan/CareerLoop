from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class BulletPoint:
    original: str
    tailored: str
    is_metric_heavy: bool = False
    verification_status: str = "PENDING" # PENDING, VERIFIED, UNSUPPORTED

@dataclass
class ExperienceEntity:
    company: str
    role: str
    location: str
    dates: str
    bullets: List[BulletPoint] = field(default_factory=list)
    summary_override: Optional[str] = None

@dataclass
class SkillCategory:
    label: str
    items: List[str] = field(default_factory=list)

@dataclass
class CandidateGraph:
    """The canonical structured identity for CareerLoop Resume Council."""
    name: str
    email: str
    phone: str
    links: List[Dict[str, str]] = field(default_factory=list) # [{label, url}]
    
    profile_summary: str = ""
    target_role_title: str = ""
    
    experience: List[ExperienceEntity] = field(default_factory=list)
    education: List[Dict[str, str]] = field(default_factory=list)
    skills: List[SkillCategory] = field(default_factory=list)
    achievements: List[str] = field(default_factory=list)
    
    # Metadata for downstream synthesis
    metric_vault: List[str] = field(default_factory=list)
    private_constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        import dataclasses
        return asdict_custom(self)

def asdict_custom(obj):
    import dataclasses
    if dataclasses.is_dataclass(obj):
        result = {}
        for f in dataclasses.fields(obj):
            value = getattr(obj, f.name)
            result[f.name] = asdict_custom(value)
        return result
    elif isinstance(obj, list):
        return [asdict_custom(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: asdict_custom(v) for k, v in obj.items()}
    else:
        return obj
