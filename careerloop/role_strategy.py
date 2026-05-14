"""
CareerLoop Role Strategy — Generate search queries from user profile.

Input: user profile (target roles, adjacent roles, excluded roles, cities, prefs)
Output: 5-12 site-specific search queries for free search engines.
"""

from typing import Optional


# India-only job board sites for site-scoped search queries
# These are the ONLY sources. No greenhouse, no lever, no global ATS.
INDIA_JOB_SITES = [
    # Tier 1 — highest India AI job volume
    {"site": "linkedin.com/jobs",   "label": "LinkedIn",    "tier": 1},
    {"site": "naukri.com",          "label": "Naukri",      "tier": 1},
    {"site": "cutshort.io",         "label": "Cutshort",   "tier": 1},
    # Tier 2 — high-quality India tech boards
    {"site": "instahyre.com",       "label": "Instahyre",  "tier": 2},
    {"site": "hirist.tech",         "label": "Hirist",     "tier": 2},
    {"site": "iimjobs.com",         "label": "IIMJobs",    "tier": 2},
    {"site": "foundit.in",          "label": "Foundit",    "tier": 2},
    # Tier 3 — startup-focused India boards
    {"site": "wellfound.com",       "label": "Wellfound",  "tier": 3},
]

# India city / location suffixes to append to broad queries
INDIA_LOCATIONS = ["Bangalore", "Hyderabad", "Mumbai", "Pune", "Chennai", "Gurugram", "Remote India"]


class RoleStrategyGenerator:
    """Generate search queries from user profile for India job discovery."""

    def __init__(self, profile: dict):
        self.profile = profile

    def generate_queries(self) -> list[dict]:
        """
        Generate 5-12 search queries with site scoping.

        Returns list of:
        {
            "query": "site:linkedin.com/jobs \"data analyst\" Bangalore",
            "role": "data analyst",
            "city": "Bangalore",
            "site": "linkedin.com/jobs",
            "priority": 1-3
        }
        """
        target_roles = self.profile.get("target_roles", [])
        adjacent_roles = self.profile.get("adjacent_roles", [])
        excluded_roles = [r.lower() for r in self.profile.get("rejected_roles", [])]
        cities = self._get_cities()
        startup_tolerance = self.profile.get("startup_tolerance", 5)
        preferred_types = self.profile.get("preferred_company_types", [])

        all_roles = []

        # Primary target roles
        for role in target_roles:
            if role.lower() not in excluded_roles:
                all_roles.append({"role": role, "priority": 1})

        # Adjacent roles
        for role in adjacent_roles:
            if role.lower() not in excluded_roles:
                all_roles.append({"role": role, "priority": 2})

        # Auto-generate adjacent roles if none specified
        if not adjacent_roles and target_roles:
            generated = self._generate_adjacent_roles(target_roles, excluded_roles)
            for role in generated:
                all_roles.append({"role": role, "priority": 2})

        if not all_roles:
            # Absolute fallback: generic tech roles
            all_roles = [
                {"role": "software engineer", "priority": 3},
                {"role": "backend engineer", "priority": 3},
            ]

        queries = []

        tier1_sites = [s for s in INDIA_JOB_SITES if s["tier"] == 1]  # LinkedIn, Naukri, Cutshort
        tier2_sites = [s for s in INDIA_JOB_SITES if s["tier"] == 2]  # Instahyre, Hirist, IIMJobs, Foundit
        tier3_sites = [s for s in INDIA_JOB_SITES if s["tier"] == 3]  # Wellfound

        primary_city = cities[0] if cities else "Bangalore"
        secondary_cities = cities[1:3] if len(cities) > 1 else []

        primary_roles = [r for r in all_roles if r["priority"] == 1]
        adjacent_roles_list = [r for r in all_roles if r["priority"] == 2]

        # Phase 1: Primary roles × Tier 1 sites × primary city
        # e.g. site:linkedin.com/jobs "AI Engineer" Bangalore
        for role_info in primary_roles:
            role = role_info["role"]
            for s in tier1_sites:
                queries.append({
                    "query": f'site:{s["site"]} "{role}" {primary_city}',
                    "role": role,
                    "city": primary_city,
                    "site": s["site"],
                    "priority": 1,
                })

        # Phase 2: Primary roles × Tier 1 sites × secondary cities
        for city in secondary_cities:
            for role_info in primary_roles[:2]:
                role = role_info["role"]
                for s in tier1_sites[:2]:  # LinkedIn + Naukri only
                    queries.append({
                        "query": f'site:{s["site"]} "{role}" {city}',
                        "role": role,
                        "city": city,
                        "site": s["site"],
                        "priority": 1,
                    })

        # Phase 3: Primary roles × Tier 2 India boards (no city needed, board is India-only)
        # e.g. site:cutshort.io "AI Engineer"  |  site:hirist.tech "ML Engineer"
        for role_info in primary_roles[:2]:
            role = role_info["role"]
            for s in tier2_sites:
                queries.append({
                    "query": f'site:{s["site"]} "{role}"',
                    "role": role,
                    "city": "India",
                    "site": s["site"],
                    "priority": 2,
                })

        # Phase 4: Adjacent roles × Tier 1 sites × primary city
        for role_info in adjacent_roles_list[:3]:
            role = role_info["role"]
            for s in tier1_sites[:2]:
                queries.append({
                    "query": f'site:{s["site"]} "{role}" {primary_city}',
                    "role": role,
                    "city": primary_city,
                    "site": s["site"],
                    "priority": 2,
                })

        # Phase 5: Startup-focused (Wellfound) if user is startup-tolerant
        if startup_tolerance >= 6:
            for role_info in primary_roles[:2]:
                role = role_info["role"]
                for s in tier3_sites:
                    queries.append({
                        "query": f'site:{s["site"]} "{role}" India',
                        "role": role,
                        "city": "India",
                        "site": s["site"],
                        "priority": 3,
                    })

        # Deduplicate
        seen = set()
        unique_queries = []
        for q in queries:
            key = q["query"]
            if key not in seen:
                seen.add(key)
                unique_queries.append(q)

        # Cap at 20 (8 India boards × roles, respects DDG rate limits)
        return unique_queries[:20]

    def _get_cities(self) -> list[str]:
        """Extract preferred cities from profile."""
        city = self.profile.get("city", self.profile.get("location_city", ""))
        relocation = self.profile.get("relocation_cities", [])

        cities = []
        if city:
            cities.append(self._canonical_city(city))

        for c in relocation:
            canonical = self._canonical_city(c)
            if canonical and canonical not in cities:
                cities.append(canonical)

        # Add remote if user prefers it
        location_flex = self.profile.get("location_flexibility", "")
        if "remote" in str(location_flex).lower():
            if "Remote India" not in cities:
                cities.append("Remote India")

        if not cities:
            cities = ["Bangalore"]  # Default tech hub

        return cities

    def _canonical_city(self, city: str) -> str:
        """Map city variants to canonical names."""
        mappings = {
            "bengaluru": "Bangalore",
            "blr": "Bangalore",
            "gurgaon": "Gurugram",
            "ncr": "Delhi NCR",
            "new delhi": "Delhi",
            "bombay": "Mumbai",
            "madras": "Chennai",
            "cochin": "Kochi",
            "calcutta": "Kolkata",
        }
        lower = city.lower().strip()
        return mappings.get(lower, city.strip().title())

    def _generate_adjacent_roles(
        self, target_roles: list[str], excluded: list[str]
    ) -> list[str]:
        """Auto-generate adjacent roles from target roles."""
        adjacency_map = {
            "ai product engineer": [
                "applied ai engineer",
                "ml engineer",
                "ai engineer",
            ],
            "applied ai engineer": [
                "ai product engineer",
                "ml engineer",
                "llm engineer",
            ],
            "data analyst": [
                "product analyst",
                "business analyst",
                "analytics engineer",
            ],
            "product analyst": [
                "data analyst",
                "business analyst",
                "growth analyst",
            ],
            "backend engineer": [
                "software engineer",
                "platform engineer",
                "api engineer",
            ],
            "software engineer": [
                "backend engineer",
                "platform engineer",
                "full stack engineer",
            ],
            "ml engineer": [
                "data scientist",
                "ai engineer",
                "applied scientist",
            ],
            "data engineer": [
                "analytics engineer",
                "etl developer",
                "data platform engineer",
            ],
        }

        adjacent = []
        for role in target_roles:
            key = role.lower().strip()
            candidates = adjacency_map.get(key, [])
            for c in candidates:
                if c not in excluded and c not in adjacent:
                    adjacent.append(c)

        return adjacent[:4]
