"""
CareerLoop Role Strategy — Generate search queries from user profile.

Input: user profile (target roles, adjacent roles, excluded roles, cities, prefs)
Output: 5-12 site-specific search queries for free search engines.
"""

from typing import Optional


# Indian job board domains for site-scoped searches
JOB_SITES = [
    "linkedin.com",
    "naukri.com",
    "cutshort.io",
    "instahyre.com",
]

# Broad search (no site scope) as fallback
BROAD_SUFFIXES = ["India", "Bangalore", "remote India"]


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

        # Strategy: primary roles × primary city × top 2 sites
        # Then: adjacent roles × primary city × 1 site
        # Then: primary roles × secondary cities × 1 site
        # Then: broad (no site scope) queries

        primary_city = cities[0] if cities else "Bangalore"
        secondary_cities = cities[1:3] if len(cities) > 1 else []

        # Phase 1: Primary roles on top sites
        for role_info in [r for r in all_roles if r["priority"] == 1]:
            role = role_info["role"]
            for site in JOB_SITES[:2]:  # LinkedIn + Naukri
                queries.append({
                    "query": f'site:{site} "{role}" {primary_city}',
                    "role": role,
                    "city": primary_city,
                    "site": site,
                    "priority": 1,
                })

        # Phase 2: Primary roles on secondary sites
        for role_info in [r for r in all_roles if r["priority"] == 1][:2]:
            role = role_info["role"]
            for site in JOB_SITES[2:]:  # cutshort, instahyre
                queries.append({
                    "query": f'site:{site} "{role}" India',
                    "role": role,
                    "city": "India",
                    "site": site,
                    "priority": 2,
                })

        # Phase 3: Adjacent roles on top site
        for role_info in [r for r in all_roles if r["priority"] == 2][:3]:
            role = role_info["role"]
            queries.append({
                "query": f'site:linkedin.com "{role}" {primary_city} jobs',
                "role": role,
                "city": primary_city,
                "site": "linkedin.com",
                "priority": 2,
            })

        # Phase 4: Primary roles in secondary cities
        for city in secondary_cities:
            for role_info in [r for r in all_roles if r["priority"] == 1][:2]:
                role = role_info["role"]
                queries.append({
                    "query": f'site:naukri.com "{role}" {city}',
                    "role": role,
                    "city": city,
                    "site": "naukri.com",
                    "priority": 3,
                })

        # Phase 5: Broad search (no site scope) for coverage
        for role_info in [r for r in all_roles if r["priority"] == 1][:2]:
            role = role_info["role"]
            queries.append({
                "query": f'"{role}" jobs {primary_city} India apply',
                "role": role,
                "city": primary_city,
                "site": "broad",
                "priority": 3,
            })

        # Startup-specific queries if tolerance is high
        if startup_tolerance >= 7:
            for role_info in [r for r in all_roles if r["priority"] == 1][:1]:
                role = role_info["role"]
                queries.append({
                    "query": f'site:wellfound.com "{role}" India',
                    "role": role,
                    "city": "India",
                    "site": "wellfound.com",
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

        # Cap at 12
        return unique_queries[:12]

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
