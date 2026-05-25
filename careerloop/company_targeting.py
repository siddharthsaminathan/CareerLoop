"""
Top-N Company Targeting — rank companies for a given function + city.

Picks the N companies most likely to hire for the user's function in their
geography, instead of crawling everything. Supports "show me more" expansion
by paging through the ranked list.

Ranking formula:
    score = function_probability * 40
          + ats_score * 15           (greenhouse/lever/ashby > unknown)
          + crawl_freshness * 10     (active > warm > cold)
          + employee_signal * 15     (log-scaled headcount)
          + memory_brand_bump * 10   (company_memory.company_maturity)
          + hiring_velocity * 10     (recent last_job_count)

Each input is normalized 0-1 before the weight multiply.
"""

import logging
import math
from dataclasses import dataclass

from careerloop.company_registry import CompanyRecord, CompanyRegistry
from careerloop.function_probability import FunctionProbabilityEngine, canonical_function

logger = logging.getLogger(__name__)


ATS_SCORE = {
    "greenhouse": 1.0, "lever": 1.0, "ashby": 1.0,
    "workday": 0.8, "smartrecruiters": 0.8,
    "custom": 0.5, "unknown": 0.2, "none": 0.1, "": 0.2,
}

CRAWL_STATUS_SCORE = {"active": 1.0, "warm": 0.7, "pending": 0.5, "cold": 0.2, "dead": 0.0}

MATURITY_BUMP = {
    "public": 1.0, "ipo": 1.0,
    "unicorn": 0.85, "late stage": 0.8,
    "growth": 0.7, "series d": 0.7, "series c": 0.65,
    "series b": 0.55, "series a": 0.45,
    "seed": 0.3, "early": 0.3,
    "": 0.4,
}


@dataclass
class RankedCompany:
    company: CompanyRecord
    score: float
    function_probability: float
    rank_breakdown: dict


class CompanyTargeting:
    def __init__(self, career_ops_root: str = None):
        self.registry = CompanyRegistry(career_ops_root)
        self.func_prob = FunctionProbabilityEngine(career_ops_root)

    def top_n(
        self,
        function: str,
        city: str = "",
        sector: str = "",
        n: int = 0,
        offset: int = 0,
        min_function_probability: float = 0.4,
        min_score: float = 50.0,
    ) -> list[RankedCompany]:
        """Return all companies above min_score threshold (n=0 means no cap).
        Sorted descending by score."""
        candidates = self.registry.list_by_city_sector(
            city=city, sector=sector,
            crawl_status=["pending", "active", "warm"],
            limit=2000,
        )

        ranked: list[RankedCompany] = []
        func_slug = canonical_function(function)

        for company in candidates:
            fn_prob = self.func_prob.probability(company.id, func_slug, company.sector)
            if fn_prob < min_function_probability:
                continue

            ats = ATS_SCORE.get(company.ats_provider, 0.2)
            crawl = CRAWL_STATUS_SCORE.get(company.crawl_status, 0.5)

            # log-scaled employee estimate (capped at 10k)
            emp_est = min(max(company.employee_estimate, 1), 10000)
            employee_signal = math.log10(emp_est) / 4.0  # 0..1

            # maturity bump from company_memory
            maturity = self._lookup_maturity(company.id)
            brand_bump = MATURITY_BUMP.get(maturity.lower(), 0.4)

            # hiring velocity: normalize last_job_count (cap 20)
            velocity = min(company.last_job_count, 20) / 20.0

            score = (
                fn_prob * 40.0 +
                ats * 15.0 +
                crawl * 10.0 +
                employee_signal * 15.0 +
                brand_bump * 10.0 +
                velocity * 10.0
            )

            ranked.append(RankedCompany(
                company=company,
                score=round(score, 2),
                function_probability=round(fn_prob, 3),
                rank_breakdown={
                    "function_probability": round(fn_prob, 3),
                    "ats": ats,
                    "crawl": crawl,
                    "employee_signal": round(employee_signal, 3),
                    "brand": brand_bump,
                    "velocity": round(velocity, 2),
                },
            ))

        ranked.sort(key=lambda r: r.score, reverse=True)
        # Filter by min_score threshold
        ranked = [r for r in ranked if r.score >= min_score]
        # n=0 means no cap — return everything above threshold
        if n == 0:
            return ranked[offset:]
        return ranked[offset:offset + n]

    def expand(self, function: str, city: str, current_count: int, batch: int = 30, **kwargs) -> list[RankedCompany]:
        """Convenience: 'show me 30 more' after the user has seen `current_count`."""
        return self.top_n(function, city, offset=current_count, n=batch, **kwargs)

    def _lookup_maturity(self, company_id: str) -> str:
        try:
            from careerloop.memory.connection import get_db_manager
            db = get_db_manager()
            with db.get_connection() as conn:
                row = conn.execute(
                    """SELECT cm.company_maturity FROM careerloop.company_memory cm
                       JOIN companies c ON c.name = cm.company_normalized OR c.id = ?
                       WHERE c.id = ?""",
                    [company_id, company_id],
                ).fetchone()
            return (row["company_maturity"] or "") if row else ""
        except Exception:
            return ""
