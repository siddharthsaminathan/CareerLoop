"""
CareerLoop Company Registry — Employer graph CRUD.

Persistent store for the employer universe. Shared across users.
Source of truth for: company career pages, ATS providers, crawl status.
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

from careerloop.memory.connection import get_db_manager, db_execute, cache_table

logger = logging.getLogger(__name__)


def _normalize_id(domain_or_name: str) -> str:
    """Stable slug from domain or company name."""
    s = re.sub(r"\.(com|in|io|co|net|org|ai)$", "", domain_or_name.lower().strip())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CompanyRecord:
    id: str  # domain-or-name-slug
    name: str
    domain: str = ""
    city: str = ""
    sector: str = ""
    employee_estimate: Optional[int] = None
    crawl_status: str = "pending"  # pending / active / warm / failed / blocklist
    career_url: str = ""
    ats_provider: str = ""  # greenhouse / lever / ashby / workday / custom
    ats_url: str = ""
    last_crawled_at: Optional[str] = None
    last_job_count: int = 0
    is_active: bool = True
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @classmethod
    def from_row(cls, row) -> "CompanyRecord":
        d = dict(row)
        d["is_active"] = bool(d.get("is_active", 1))
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in cls.__dataclass_fields__.values()}})

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_active"] = int(self.is_active)
        return d


@dataclass
class CompanySourceRecord:
    company_id: str
    source_type: str  # career-page / LinkedIn / Wellfound / Crunchbase
    crawl_url: str
    last_crawled_at: Optional[str] = None
    last_job_count: int = 0
    is_active: bool = True

    @classmethod
    def from_row(cls, row) -> "CompanySourceRecord":
        d = dict(row)
        d["is_active"] = bool(d.get("is_active", 1))
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in cls.__dataclass_fields__.values()}})

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_active"] = int(self.is_active)
        return d


class CompanyRegistry:
    """CRUD layer for the employer graph (companies + company_sources tables)."""

    def __init__(self, career_ops_root: str = None):
        self.db = get_db_manager(career_ops_root)

    # ── Companies ────────────────────────────────────────────────────

    def upsert(self, company: CompanyRecord) -> CompanyRecord:
        """Insert or update a company record. Returns the stored record."""
        company.updated_at = _now()
        d = company.to_dict()
        cols = list(d.keys())
        placeholders = ", ".join(["?" for _ in cols])
        updates = ", ".join([f"{c} = excluded.{c}" for c in cols if c != "id"])

        with self.db.get_connection() as conn:
            tbl = cache_table("companies", conn)
            sql = f"""
                INSERT INTO {tbl} ({", ".join(cols)})
                VALUES ({placeholders})
                ON CONFLICT(id) DO UPDATE SET {updates}
            """
            db_execute(conn, sql, [d[c] for c in cols])
        return company

    def get(self, company_id: str) -> Optional[CompanyRecord]:
        with self.db.get_connection() as conn:
            tbl = cache_table("companies", conn)
            row = db_execute(
                conn, f"SELECT * FROM {tbl} WHERE id = ?", [company_id]
            ).fetchone()
        return CompanyRecord.from_row(row) if row else None

    def get_by_domain(self, domain: str) -> Optional[CompanyRecord]:
        with self.db.get_connection() as conn:
            tbl = cache_table("companies", conn)
            row = db_execute(
                conn, f"SELECT * FROM {tbl} WHERE domain = ?", [domain.lower()]
            ).fetchone()
        return CompanyRecord.from_row(row) if row else None

    def find_or_create(self, name: str, domain: str = "", **kwargs) -> CompanyRecord:
        """Return existing company by domain or name-slug, creating if absent."""
        if domain:
            existing = self.get_by_domain(domain)
            if existing:
                return existing
        slug = _normalize_id(domain or name)
        existing = self.get(slug)
        if existing:
            return existing
        record = CompanyRecord(id=slug, name=name, domain=domain or "", **kwargs)
        return self.upsert(record)

    def list_by_city_sector(
        self,
        city: str,
        sector: str = "",
        crawl_status: list[str] = None,
        limit: int = 50,
    ) -> list[CompanyRecord]:
        conditions = ["is_active = 1"]
        params: list = []
        if city:
            conditions.append("LOWER(city) = LOWER(?)")
            params.append(city)
        if sector:
            conditions.append("LOWER(sector) = LOWER(?)")
            params.append(sector)
        if crawl_status:
            placeholders = ", ".join(["?" for _ in crawl_status])
            conditions.append(f"crawl_status IN ({placeholders})")
            params.extend(crawl_status)
        params.append(limit)

        with self.db.get_connection() as conn:
            tbl = cache_table("companies", conn)
            sql = f"""
                SELECT * FROM {tbl}
                WHERE {" AND ".join(conditions)}
                ORDER BY last_job_count DESC, employee_estimate DESC
                LIMIT ?
            """
            rows = db_execute(conn, sql, params).fetchall()
        return [CompanyRecord.from_row(r) for r in rows]

    def list_pending_crawl(self, limit: int = 30) -> list[CompanyRecord]:
        """Companies that need their career pages crawled."""
        with self.db.get_connection() as conn:
            tbl = cache_table("companies", conn)
            rows = db_execute(
                conn,
                f"""SELECT * FROM {tbl}
                   WHERE crawl_status IN ('pending', 'active', 'warm')
                   AND is_active = 1
                   ORDER BY
                     CASE crawl_status WHEN 'active' THEN 0 WHEN 'warm' THEN 1 ELSE 2 END,
                     last_job_count DESC
                   LIMIT ?""",
                [limit],
            ).fetchall()
        return [CompanyRecord.from_row(r) for r in rows]

    def mark_crawled(self, company_id: str, job_count: int):
        with self.db.get_connection() as conn:
            tbl = cache_table("companies", conn)
            db_execute(
                conn,
                f"""UPDATE {tbl}
                   SET last_crawled_at = ?, last_job_count = ?,
                       crawl_status = CASE WHEN ? > 0 THEN 'active' ELSE 'warm' END,
                       updated_at = ?
                   WHERE id = ?""",
                [_now(), job_count, job_count, _now(), company_id],
            )

    def set_ats(self, company_id: str, ats_provider: str, ats_url: str):
        with self.db.get_connection() as conn:
            tbl = cache_table("companies", conn)
            db_execute(
                conn,
                f"UPDATE {tbl} SET ats_provider = ?, ats_url = ?, updated_at = ? WHERE id = ?",
                [ats_provider, ats_url, _now(), company_id],
            )

    # ── Company Sources ───────────────────────────────────────────────

    def upsert_source(self, source: CompanySourceRecord):
        d = source.to_dict()
        with self.db.get_connection() as conn:
            tbl = cache_table("company_sources", conn)
            db_execute(
                conn,
                f"""INSERT INTO {tbl}
                       (company_id, source_type, crawl_url, last_crawled_at, last_job_count, is_active)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(company_id, source_type) DO UPDATE SET
                       crawl_url = excluded.crawl_url,
                       last_crawled_at = excluded.last_crawled_at,
                       last_job_count = excluded.last_job_count,
                       is_active = excluded.is_active""",
                [d["company_id"], d["source_type"], d["crawl_url"],
                 d["last_crawled_at"], d["last_job_count"], d["is_active"]],
            )

    def get_sources(self, company_id: str) -> list[CompanySourceRecord]:
        with self.db.get_connection() as conn:
            tbl = cache_table("company_sources", conn)
            rows = db_execute(
                conn,
                f"SELECT * FROM {tbl} WHERE company_id = ? AND is_active = 1",
                [company_id],
            ).fetchall()
        return [CompanySourceRecord.from_row(r) for r in rows]

    def count(self) -> int:
        with self.db.get_connection() as conn:
            tbl = cache_table("companies", conn)
            return db_execute(conn, f"SELECT COUNT(*) FROM {tbl} WHERE is_active = 1").fetchone()[0]
