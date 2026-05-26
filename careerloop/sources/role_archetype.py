"""
Role Archetype Engine — pre-retrieval intent constraint layer.

Input:  raw role string + ProfileManager
Output: RoleArchetype with must_have, avoid, preferred_company_types

Used by:
- SerpAPIDiscovery._build_queries() → shapes Phase A company discovery queries
- OnDemandSearch._board_search()    → shapes Phase B board query expansion
- RoleSimilarityFilter              → informs Phase E rejection signals

The archetype is derived from profile config, not hardcoded.
Profile keys used (all from profile_extended.yml or profile.yml):
  target_roles, archetypes, target_functions, rejected_roles,
  preferred_company_types, rejected_company_types, sector_preferences
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from careerloop.profile_manager import ProfileManager

logger = logging.getLogger(__name__)


@dataclass
class RoleArchetype:
    role: str
    must_have: list[str] = field(default_factory=list)   # tokens that MUST appear in query
    avoid: list[str] = field(default_factory=list)        # tokens to exclude
    preferred_company_types: list[str] = field(default_factory=list)
    function_hints: list[str] = field(default_factory=list)  # for query phrasing

    def to_query_constraint(self) -> str:
        """Return a short phrase suitable for embedding in a search query."""
        parts = [self.role]
        if self.function_hints:
            parts.append(self.function_hints[0])
        if self.preferred_company_types:
            parts.append(self.preferred_company_types[0])
        return " ".join(parts[:3])

    def reject_title(self, title: str) -> bool:
        """Return True if a job title should be rejected based on this archetype."""
        title_lc = title.lower()
        return any(a.lower() in title_lc for a in self.avoid)


class RoleArchetypeEngine:
    """
    Derives a RoleArchetype from the user's profile for a given role string.
    All signals come from ProfileManager — nothing is hardcoded here.
    """

    def __init__(self, profile: "ProfileManager"):
        self.profile = profile

    def get_archetype(self, role: str) -> RoleArchetype:
        """Build a RoleArchetype for the given role from profile config."""
        p = self.profile

        # must_have = target_functions + archetype names that overlap with role tokens
        role_lc = role.lower()
        role_tokens = set(role_lc.split())

        must_have = list(p.target_functions or [])

        # Add archetype-specific hints when archetype name overlaps with role
        for arch in (p.archetypes or []):
            arch_name = arch.get("name", "").lower()
            if any(t in arch_name for t in role_tokens):
                # Extract function words from archetype name (skip generic "engineer"/"manager")
                arch_tokens = [w for w in arch_name.split() if w not in {"engineer", "manager", "developer", "lead"}]
                must_have.extend(arch_tokens)

        # avoid = rejected_roles from profile
        avoid = list(p.rejected_roles or [])

        # preferred_company_types from profile
        preferred = list(p.extended.get("preferred_company_types", []) or [])

        # Deduplicate, preserve order
        must_have = list(dict.fromkeys(must_have))
        avoid = list(dict.fromkeys(avoid))

        archetype = RoleArchetype(
            role=role,
            must_have=must_have,
            avoid=avoid,
            preferred_company_types=preferred,
            function_hints=must_have[:3],
        )

        logger.debug(
            f"[Archetype] {role!r} → must_have={must_have[:5]}, "
            f"avoid={avoid[:5]}, preferred={preferred[:3]}"
        )
        return archetype
