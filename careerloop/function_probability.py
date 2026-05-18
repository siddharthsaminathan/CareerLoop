"""
Function Probability Engine — sector × function inference.

Answers: "Given this company's sector, how likely are they to hire for this function?"

Without this, a fashion buyer would get matched to AI labs, and ML engineers
to garment manufacturers. This is the Layer 3 of the Employer Discovery
Engine (PRD §18, breakdown-20-part Part 22).

Inference sources (in priority order):
1. company_functions table (cached probability per company × function)
2. Sector × Function correlation matrix (this file)
3. Job postings history (`jobs.title` aggregated by `company_id`)

Stored in `company_functions` table.
"""

import logging
import re
from datetime import datetime, timezone

from careerloop.memory.connection import get_db_manager

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# ── Sector × Function correlation matrix ─────────────────────────────────
# Rows = sectors (MECE taxonomy from PRD §18).
# Cols = function families. Values are base probabilities 0.0-1.0.
# Used when there's no employee/job-posting evidence yet.

SECTOR_FUNCTION_MATRIX = {
    "Technology & Software": {
        "engineering": 0.95, "product": 0.85, "data": 0.80, "ml_engineering": 0.70,
        "design": 0.65, "devops": 0.75, "security": 0.55, "customer_success": 0.50,
        "sales": 0.45, "marketing": 0.45, "finance": 0.30, "operations": 0.40,
        "buying": 0.05, "merchandising": 0.02, "clinical": 0.02,
    },
    "Financial Services": {
        "risk": 0.85, "compliance": 0.85, "finance": 0.95, "analytics": 0.70,
        "product": 0.55, "engineering": 0.55, "data": 0.65, "operations": 0.65,
        "sales": 0.55, "marketing": 0.40, "ml_engineering": 0.45,
        "buying": 0.02, "merchandising": 0.02, "clinical": 0.02,
    },
    "Consulting & Professional Services": {
        "consulting": 0.95, "business_analysis": 0.85, "pmo": 0.65, "finance": 0.60,
        "hr": 0.55, "legal": 0.55, "operations": 0.50,
        "engineering": 0.35, "product": 0.25, "ml_engineering": 0.30, "data": 0.50,
    },
    "Retail & Commerce": {
        "buying": 0.90, "merchandising": 0.90, "sourcing": 0.85, "category_management": 0.85,
        "inventory": 0.80, "growth": 0.75, "marketing": 0.80, "operations": 0.75,
        "data": 0.60, "engineering": 0.50, "product": 0.55, "ml_engineering": 0.40,
        "design": 0.55, "finance": 0.50,
    },
    "Manufacturing & Industrial": {
        "supply_chain": 0.90, "procurement": 0.85, "plant_operations": 0.85,
        "quality": 0.85, "industrial_engineering": 0.80, "operations": 0.80,
        "engineering": 0.55, "data": 0.40, "product": 0.20, "ml_engineering": 0.20,
    },
    "Healthcare & Life Sciences": {
        "clinical": 0.90, "pharma_sales": 0.75, "regulatory": 0.75, "research": 0.70,
        "healthcare_analytics": 0.65, "operations": 0.55, "data": 0.55,
        "engineering": 0.40, "product": 0.40, "ml_engineering": 0.40, "buying": 0.10,
    },
    "Media & Creative": {
        "design": 0.90, "content": 0.90, "branding": 0.85, "social_media": 0.85,
        "creative_strategy": 0.80, "production": 0.75, "marketing": 0.80,
        "engineering": 0.30, "product": 0.40, "data": 0.30, "ml_engineering": 0.20,
    },
    "Education": {
        "instruction": 0.85, "curriculum": 0.80, "learning_operations": 0.75,
        "admissions": 0.65, "growth": 0.65, "operations": 0.55,
        "engineering": 0.45, "product": 0.45, "data": 0.45, "ml_engineering": 0.35,
    },
    "Logistics & Mobility": {
        "fleet_operations": 0.85, "logistics_analytics": 0.80, "warehouse_operations": 0.80,
        "procurement": 0.70, "operations": 0.85,
        "engineering": 0.55, "product": 0.45, "data": 0.55, "ml_engineering": 0.45,
    },
    "Real Estate & Infra": {
        "project_management": 0.85, "procurement": 0.75, "operations": 0.75,
        "sales": 0.70, "finance": 0.55,
        "engineering": 0.35, "product": 0.30, "data": 0.30, "ml_engineering": 0.20,
    },
    "Energy & Utilities": {
        "engineering": 0.85, "operations": 0.80, "sustainability": 0.75,
        "project_management": 0.75, "finance": 0.50, "data": 0.40, "ml_engineering": 0.30,
    },
    "Government & Public Sector": {
        "administration": 0.85, "procurement": 0.75, "policy": 0.70,
        "technology": 0.50, "analytics": 0.50, "operations": 0.65,
        "engineering": 0.35, "product": 0.20, "data": 0.45, "ml_engineering": 0.25,
    },
    "Hospitality & Travel": {
        "operations": 0.85, "guest_experience": 0.80, "revenue_management": 0.75,
        "procurement": 0.65, "marketing": 0.65, "sales": 0.65,
        "engineering": 0.30, "product": 0.35, "data": 0.35, "ml_engineering": 0.25,
    },
    "Agriculture & Food": {
        "sourcing": 0.80, "supply_chain": 0.80, "quality": 0.75, "operations": 0.75,
        "engineering": 0.30, "data": 0.30, "ml_engineering": 0.20,
    },
    "Nonprofit & Social Impact": {
        "fundraising": 0.85, "operations": 0.75, "policy": 0.70, "research": 0.65,
        "marketing": 0.55, "engineering": 0.30, "product": 0.30, "data": 0.40,
    },
}


# ── Function name → canonical slug ───────────────────────────────────────

FUNCTION_ALIAS = {
    # engineering family
    "software engineer": "engineering", "developer": "engineering", "swe": "engineering",
    "engineering": "engineering",
    "backend": "engineering", "frontend": "engineering", "full stack": "engineering",
    "platform engineer": "engineering", "product engineer": "engineering",
    # ml
    "ml engineer": "ml_engineering", "machine learning": "ml_engineering",
    "ai engineer": "ml_engineering", "applied ai": "ml_engineering", "llm": "ml_engineering",
    "agent engineer": "ml_engineering",
    # data
    "data engineer": "data", "data scientist": "data", "analytics": "data",
    "data analyst": "data", "analyst": "analytics",
    "business analyst": "business_analysis",
    # product
    "product manager": "product", "pm": "product", "product": "product",
    # design
    "designer": "design", "ux": "design", "ui": "design",
    # retail/commerce
    "buyer": "buying", "fashion buyer": "buying", "merchandiser": "merchandising",
    "sourcing manager": "sourcing", "category manager": "category_management",
    # healthcare
    "doctor": "clinical", "nurse": "clinical", "clinician": "clinical",
    # ops
    "operations": "operations", "ops manager": "operations",
    "supply chain": "supply_chain", "logistics": "fleet_operations",
    "procurement": "procurement",
    # finance
    "finance manager": "finance", "accountant": "finance", "controller": "finance",
    # marketing
    "marketing manager": "marketing", "growth marketer": "growth", "growth": "growth",
    "content writer": "content", "social media": "social_media",
    # consulting
    "consultant": "consulting", "consulting": "consulting",
    # sales / cs
    "sales": "sales", "account executive": "sales",
    "customer success": "customer_success",
    # security / devops
    "security engineer": "security", "devops": "devops", "sre": "devops",
}


def canonical_function(role_or_function: str) -> str:
    """Map a role title or function name to a canonical function slug.
    Falls back to slugifying the input if no alias matches."""
    text = (role_or_function or "").lower().strip()
    if not text:
        return ""
    if text in FUNCTION_ALIAS:
        return FUNCTION_ALIAS[text]
    # Try substring match (longest first)
    for alias in sorted(FUNCTION_ALIAS.keys(), key=len, reverse=True):
        if alias in text:
            return FUNCTION_ALIAS[alias]
    return _slug(text)


# ── Engine ───────────────────────────────────────────────────────────────

class FunctionProbabilityEngine:
    """Inference for company × function probability."""

    PROBABILITY_THRESHOLD = 0.40  # below this → suppress as wrong-function match

    def __init__(self, career_ops_root: str = None):
        self.db = get_db_manager(career_ops_root)

    # ── Public API ────────────────────────────────────────────────────

    def probability(self, company_id: str, function: str, sector: str = "") -> float:
        """Return P(this company hires for this function) in [0,1]."""
        func_slug = canonical_function(function)
        if not func_slug or not company_id:
            return 0.5  # unknown → neutral

        cached = self._lookup(company_id, func_slug)
        if cached is not None:
            return cached

        # No cache → infer from sector
        if not sector:
            sector = self._sector_from_registry(company_id)
        prob = self._infer_from_sector(sector, func_slug)
        self._store(company_id, func_slug, prob, "sector_inference")
        return prob

    def should_surface(self, company_id: str, function: str, sector: str = "") -> bool:
        return self.probability(company_id, function, sector) >= self.PROBABILITY_THRESHOLD

    def update_from_job_posting(self, company_id: str, title: str):
        """Increment the probability for the function inferred from a posted title."""
        func_slug = canonical_function(title)
        if not func_slug or not company_id:
            return
        existing = self._lookup(company_id, func_slug)
        new_prob = min(1.0, (existing or 0.5) + 0.05)
        self._store(company_id, func_slug, new_prob, "historical_jobs")

    def list_for_company(self, company_id: str) -> dict:
        """All function probabilities for one company."""
        try:
            with self.db.get_connection() as conn:
                rows = conn.execute(
                    "SELECT function, probability, signal_source FROM company_functions WHERE company_id = ?",
                    [company_id],
                ).fetchall()
            return {r["function"]: {"probability": r["probability"], "source": r["signal_source"]} for r in rows}
        except Exception:
            return {}

    def companies_for_function(self, function: str, min_prob: float = 0.5, limit: int = 50) -> list[str]:
        """Return company_ids likely to hire for this function."""
        func_slug = canonical_function(function)
        if not func_slug:
            return []
        try:
            with self.db.get_connection() as conn:
                rows = conn.execute(
                    """SELECT company_id FROM company_functions
                       WHERE function = ? AND probability >= ?
                       ORDER BY probability DESC LIMIT ?""",
                    [func_slug, min_prob, limit],
                ).fetchall()
            return [r["company_id"] for r in rows]
        except Exception:
            return []

    # ── Internals ─────────────────────────────────────────────────────

    def _lookup(self, company_id: str, function: str):
        try:
            with self.db.get_connection() as conn:
                row = conn.execute(
                    "SELECT probability FROM company_functions WHERE company_id = ? AND function = ?",
                    [company_id, function],
                ).fetchone()
            return row["probability"] if row else None
        except Exception:
            return None

    def _store(self, company_id: str, function: str, probability: float, signal_source: str):
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """INSERT INTO company_functions (company_id, function, probability, signal_source, updated_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(company_id, function) DO UPDATE SET
                           probability = excluded.probability,
                           signal_source = excluded.signal_source,
                           updated_at = excluded.updated_at""",
                    [company_id, function, round(probability, 3), signal_source, _now()],
                )
        except Exception as e:
            logger.debug(f"[FunctionProb] store failed: {e}")

    def _sector_from_registry(self, company_id: str) -> str:
        try:
            with self.db.get_connection() as conn:
                row = conn.execute(
                    "SELECT sector FROM companies WHERE id = ?", [company_id]
                ).fetchone()
            return row["sector"] if row else ""
        except Exception:
            return ""

    def _infer_from_sector(self, sector: str, function: str) -> float:
        if not sector:
            return 0.5
        # Match sector name case-insensitively + allow prefix matching
        for sector_name, fn_probs in SECTOR_FUNCTION_MATRIX.items():
            if sector.lower() in sector_name.lower() or sector_name.lower() in sector.lower():
                if function in fn_probs:
                    return fn_probs[function]
                # Soft penalty if sector is known but function is uncommon
                return 0.25
        return 0.5  # unknown sector → neutral
