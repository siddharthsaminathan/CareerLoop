"""Map live DB rows → stable API response shapes.

Keeps the HTTP contract decoupled from the v1/v2 column naming drift in the DB.
"""

import re
from typing import Optional
from urllib.parse import quote, urlparse


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _route_badge(route: Optional[str]) -> Optional[str]:
    if not route:
        return None
    return route.strip().upper()


def _domain_from_url(url: Optional[str]) -> Optional[str]:
    """Extract a bare domain (no www) from a URL. Returns None if not a real host."""
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None
    if "://" not in u:
        u = "https://" + u
    try:
        host = urlparse(u).netloc.lower()
    except Exception:
        return None
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    # Reject aggregator domains — their logo isn't the company's logo.
    if not host or host in {"cutshort.io", "linkedin.com", "naukri.com", "indeed.com"}:
        return None
    return host if "." in host else None


def company_logo(row: dict, company_name: Optional[str]) -> Optional[str]:
    """Best-effort logo URL for a company card.

    Priority:
      1. companies.logo_url (if backfilled)
      2. Clearbit logo derived from the company's own website/domain
      3. Initials avatar generated from the company name (always renders)

    This is a deterministic rendering helper, not stored company data — so the
    frontend always has something to show even before logo backfill lands.
    """
    explicit = row.get("company_logo_url")
    if explicit:
        return explicit

    domain = _domain_from_url(row.get("company_website")) or row.get("company_domain")
    if domain and "." in str(domain):
        return f"https://logo.clearbit.com/{str(domain).strip().lower()}"

    name = (company_name or row.get("company") or row.get("company_name") or "").strip()
    if name:
        return (
            "https://ui-avatars.com/api/"
            f"?name={quote(name)}&background=0D8ABC&color=fff&bold=true&size=128"
        )
    return None


def description_snippet(row: dict, max_len: int = 280) -> Optional[str]:
    """A short job description for the card, from role_summary / raw_jd_text / jd_text."""
    text = (
        row.get("role_summary")
        or row.get("raw_jd_text")
        or row.get("jd_text")
        or ""
    ).strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "…"


def fit_tier(score) -> Optional[str]:
    """Frontend color tier from fit_score (0-100)."""
    if score is None:
        return None
    try:
        s = float(score)
    except (TypeError, ValueError):
        return None
    if s >= 80:
        return "strong"   # emerald
    if s >= 60:
        return "good"     # amber
    return "weak"         # red


def brief_item(row: dict) -> dict:
    """daily_brief_items row → BriefItem card."""
    score = row.get("fit_score")
    company = row.get("company") or row.get("job_company_name") or row.get("company_name") or ""
    return {
        "item_index": row.get("item_index"),
        "job_id": str(row.get("job_id")) if row.get("job_id") is not None else None,
        "title": row.get("title") or "",
        "company": company,
        "logo_url": company_logo(row, company),
        "location": row.get("location") or "",
        "work_mode": row.get("work_mode"),
        "salary_min": float(row["salary_min"]) if row.get("salary_min") is not None else None,
        "salary_max": float(row["salary_max"]) if row.get("salary_max") is not None else None,
        "salary_currency": row.get("salary_currency") or "INR",
        "description": description_snippet(row),
        "fit_score": float(score) if score is not None else None,
        "fit_tier": fit_tier(score),
        "recommendation_reason": row.get("recommendation_reason"),
        "risk_summary": row.get("risk_summary"),
        "route_recommendation": _route_badge(row.get("route_recommendation")),
        "apply_url": row.get("apply_url") or None,
    }


def brief(brief_row: dict, items: list) -> dict:
    return {
        "brief_id": str(brief_row.get("id")),
        "date_str": brief_row.get("date_str"),
        "summary": brief_row.get("summary"),
        "created_at": _iso(brief_row.get("created_at")),
        "item_count": len(items),
        "items": [brief_item(i) for i in items],
    }


def job_detail(row: dict, relationship: Optional[dict] = None) -> dict:
    score = row.get("fit_score") if relationship is None else relationship.get("fit_score")
    out = {
        "job_id": str(row.get("job_id")) if row.get("job_id") is not None else None,
        "legacy_id": row.get("id"),
        "title": row.get("title") or "",
        "company_name": row.get("company_name") or "",
        "logo_url": company_logo(row, row.get("company_name")),
        "location": row.get("location") or row.get("location_raw") or "",
        "location_city": row.get("location_city"),
        "work_mode": row.get("work_mode"),
        "salary_min": float(row["salary_min"]) if row.get("salary_min") is not None else None,
        "salary_max": float(row["salary_max"]) if row.get("salary_max") is not None else None,
        "salary_currency": row.get("salary_currency") or "INR",
        "source": row.get("source"),
        "source_url": row.get("source_url"),
        "apply_url": row.get("apply_url"),
        "role_summary": row.get("role_summary"),
        "raw_jd_text": row.get("raw_jd_text"),
        "responsibilities": row.get("responsibilities"),
        "requirements": row.get("requirements"),
        "benefits": row.get("benefits"),
        "description": description_snippet(row, max_len=1200),
        "is_india_role": row.get("is_india_role"),
        "verified_active": bool(row.get("verified_active")),
        "status": row.get("status") or "unknown",
        "posted_at": _iso(row.get("posted_at")),
    }
    if relationship:
        out["match_status"] = relationship.get("match_status")
        out["fit_score"] = float(score) if score is not None else None
        out["fit_tier"] = fit_tier(score)
        out["route_recommendation"] = _route_badge(relationship.get("route_recommendation"))
    return out


def user_public(row: dict) -> dict:
    return {
        "id": str(row.get("id")),
        "email": row.get("email"),
        "full_name": row.get("full_name"),
        "linkedin_url": row.get("linkedin_url"),
        "telegram_chat_id": row.get("telegram_chat_id"),
        "onboarding_complete": bool(row.get("onboarding_complete")),
        "career_mode": row.get("career_mode"),
        "has_cv": bool(row.get("master_cv_markdown")),
        "created_at": _iso(row.get("created_at")),
        "last_active_at": _iso(row.get("last_active_at")),
    }
