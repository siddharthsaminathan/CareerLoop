"""CareerLoop Shared Policies — single source of truth for business rules.

Every scan path (DailyRunner, scan_more, build_from_cache) MUST use
these shared policies. No duplicated business logic anywhere.
"""

from careerloop.policies.location_policy import is_india_location, filter_india_jobs

__all__ = ["is_india_location", "filter_india_jobs"]
