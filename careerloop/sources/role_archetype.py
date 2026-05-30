"""
Role Archetype Engine — pre-retrieval intent constraint layer.

Input:  raw role string + ProfileManager
Output: RoleArchetype with must_have, avoid, preferred_company_types,
        function_type, market_type

Architecture (per ChatGPT audit 2026-05-26):
  The system must understand WHAT TYPE of role, not just keyword-match.
  For "AI Product Engineer":
    must_have  = ["product", "platform", "customer-facing", "applied AI"]
    avoid      = ["research ML", "hardware", "pure infra", "generic SWE"]
    company    = ["B2B AI SaaS", "AI product startup"]
    function   = "product engineering"
    market     = "B2B enterprise"

  This constrains Phase A discovery, Phase B query expansion,
  Phase E ontology filter, Phase F scoring.

LLM generates archetype from role + profile context.
SQLite caches result (role_archetypes table).
Zero hardcoding — all signals from profile config.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from careerloop.profile_manager import ProfileManager

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(role: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", role.lower()).strip()


_ARCHETYPE_TABLE_READY = False


def _ensure_archetype_table(conn):
    """Idempotently create the role_archetypes cache table (careerloop schema on PG).

    Previously defined only in _SQLITE_INIT (connection.py) — never existed in
    production Postgres, so every cache lookup/store silently failed.
    CREATE TABLE IF NOT EXISTS is cheap and runs at most once per process.
    """
    global _ARCHETYPE_TABLE_READY
    if _ARCHETYPE_TABLE_READY:
        return
    from careerloop.memory.connection import db_execute, cache_table
    tbl = cache_table("role_archetypes", conn)
    db_execute(conn, f"""
        CREATE TABLE IF NOT EXISTS {tbl} (
            role_norm               TEXT PRIMARY KEY,
            must_have               TEXT NOT NULL DEFAULT '[]',
            avoid                   TEXT NOT NULL DEFAULT '[]',
            preferred_company_types TEXT NOT NULL DEFAULT '[]',
            function_type           TEXT DEFAULT '',
            market_type             TEXT DEFAULT '',
            generated_at            TEXT
        )
    """)
    _ARCHETYPE_TABLE_READY = True


@dataclass
class RoleArchetype:
    role: str
    must_have: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    preferred_company_types: list[str] = field(default_factory=list)
    function_type: str = ""   # e.g. "product engineering", "sales", "data science"
    market_type: str = ""     # e.g. "B2B enterprise", "B2C consumer"

    def to_query_constraint(self) -> str:
        """Short phrase for embedding in board search queries."""
        parts = [self.role]
        if self.function_type:
            parts.append(self.function_type)
        if self.preferred_company_types:
            parts.append(self.preferred_company_types[0])
        return " ".join(parts[:3])

    def reject_title(self, title: str) -> bool:
        title_lc = title.lower()
        return any(a.lower() in title_lc for a in self.avoid)


class RoleArchetypeEngine:
    """
    LLM-powered archetype generator with SQLite cache.
    Profile context informs the LLM prompt — zero hardcoding.
    """

    def __init__(self, profile: "ProfileManager"):
        self.profile = profile

    def get_archetype(self, role: str) -> RoleArchetype:
        """Return RoleArchetype for role. Cache-on-miss via LLM."""
        role_norm = _normalize(role)

        cached = self._lookup(role_norm)
        if cached:
            return cached

        generated = self._llm_generate(role, role_norm)
        self._store(role_norm, generated)
        return generated

    # ── Cache ─────────────────────────────────────────────────────────

    def _lookup(self, role_norm: str) -> RoleArchetype | None:
        try:
            from careerloop.memory.connection import get_db_manager, db_execute, cache_table
            db = get_db_manager()
            with db.get_connection() as conn:
                _ensure_archetype_table(conn)
                tbl = cache_table("role_archetypes", conn)
                row = db_execute(
                    conn,
                    f"SELECT * FROM {tbl} WHERE role_norm = ?",
                    [role_norm],
                ).fetchone()
            if row:
                d = dict(row)
                return RoleArchetype(
                    role=role_norm,
                    must_have=json.loads(d.get("must_have") or "[]"),
                    avoid=json.loads(d.get("avoid") or "[]"),
                    preferred_company_types=json.loads(d.get("preferred_company_types") or "[]"),
                    function_type=d.get("function_type") or "",
                    market_type=d.get("market_type") or "",
                )
        except Exception as e:
            logger.debug(f"[Archetype] cache lookup failed: {e}")
        return None

    def _store(self, role_norm: str, arch: RoleArchetype):
        try:
            from careerloop.memory.connection import get_db_manager, db_execute, cache_table
            db = get_db_manager()
            with db.get_connection() as conn:
                _ensure_archetype_table(conn)
                tbl = cache_table("role_archetypes", conn)
                db_execute(
                    conn,
                    f"""INSERT INTO {tbl}
                       (role_norm, must_have, avoid, preferred_company_types,
                        function_type, market_type, generated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(role_norm) DO UPDATE SET
                           must_have = excluded.must_have,
                           avoid = excluded.avoid,
                           preferred_company_types = excluded.preferred_company_types,
                           function_type = excluded.function_type,
                           market_type = excluded.market_type,
                           generated_at = excluded.generated_at""",
                    [
                        role_norm,
                        json.dumps(arch.must_have),
                        json.dumps(arch.avoid),
                        json.dumps(arch.preferred_company_types),
                        arch.function_type,
                        arch.market_type,
                        _now(),
                    ],
                )
        except Exception as e:
            logger.warning(f"[Archetype] cache store failed: {e}")

    # ── LLM generation ────────────────────────────────────────────────

    def _llm_generate(self, role: str, role_norm: str) -> RoleArchetype:
        p = self.profile
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

        if api_key:
            prompt = f"""You are a labor market ontology expert. Given a job role and a candidate's profile, generate a structured role archetype for precise job retrieval.

Role: "{role}"

Candidate context:
- Target functions: {p.target_functions}
- Confirmed skills: {(p.confirmed_skills or [])[:10]}
- Sector preferences: {p.sector_preferences}
- Preferred company types: {p.extended.get('preferred_company_types', [])}
- Rejected roles: {(p.rejected_roles or [])[:15]}

Generate a JSON archetype that captures:
- must_have: 4-8 SHORT semantic tokens/phrases that MUST appear in relevant job descriptions (e.g. "product", "platform", "customer-facing", "applied AI", "cross-functional"). NOT full sentences. NOT the role name itself.
- avoid: 4-8 SHORT tokens/phrases that signal this is the WRONG type of role (e.g. "research", "hardware", "infra only", "generic SWE")
- preferred_company_types: 2-4 company type strings (e.g. "B2B AI SaaS", "AI product startup", "platform company")
- function_type: 2-4 word phrase for the function (e.g. "product engineering", "applied AI")
- market_type: market context (e.g. "B2B enterprise", "B2C consumer", "developer tools")

Return ONLY valid JSON, no commentary:
{{
  "must_have": [...],
  "avoid": [...],
  "preferred_company_types": [...],
  "function_type": "...",
  "market_type": "..."
}}"""

            try:
                import requests
                resp = requests.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}",
                             "Content-Type": "application/json"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                        "max_tokens": 300,
                    },
                    timeout=15,
                )
                content = resp.json()["choices"][0]["message"]["content"].strip()
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                    arch = RoleArchetype(
                        role=role,
                        must_have=data.get("must_have", []),
                        avoid=data.get("avoid", []) + list(p.rejected_roles or []),
                        preferred_company_types=data.get("preferred_company_types", []),
                        function_type=data.get("function_type", ""),
                        market_type=data.get("market_type", ""),
                    )
                    # Deduplicate avoid list
                    arch.avoid = list(dict.fromkeys(arch.avoid))
                    logger.info(f"[Archetype] LLM generated for '{role}': must_have={arch.must_have}")
                    return arch
            except Exception as e:
                logger.warning(f"[Archetype] LLM generation failed: {e}")

        # Fallback: role tokens + profile signals (no hardcoding)
        return RoleArchetype(
            role=role,
            must_have=list(role_norm.split()),
            avoid=list(p.rejected_roles or []),
            preferred_company_types=list(p.extended.get("preferred_company_types", []) or []),
            function_type="",
            market_type="",
        )
