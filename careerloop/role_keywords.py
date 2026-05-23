"""
Dynamic Keyword Generator — LLM-cached search keywords per role/function.

Replaces hardcoded keyword lists (`ai_signals`, `product_signals`, etc.)
that previously blocked the system from working with non-AI roles like
"fashion buyer", "supply chain analyst", "data engineer".

Flow:
    keywords = RoleKeywordCache().get("fashion buyer")
    # → DB hit? return cached
    # → DB miss? LLM generates → store → return

Stored in `role_keywords` table (see memory/schema.sql).
"""

import json
import logging
import re
from datetime import datetime, timezone

from careerloop.memory.connection import get_db_manager

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_role(role: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", role.lower()).strip()


# ── Fallback keywords for total LLM failure ──────────────────────────────

_FALLBACK_BY_TOKEN = {
    "engineer": ["engineering", "software", "developer", "programming", "technical"],
    "designer": ["design", "ux", "ui", "visual", "creative"],
    "manager": ["management", "leadership", "team", "stakeholder"],
    "analyst": ["analysis", "data", "reporting", "insights", "metrics"],
    "buyer": ["buying", "merchandising", "sourcing", "category", "vendor"],
    "consultant": ["consulting", "advisory", "client", "engagement"],
    "scientist": ["research", "modeling", "experimentation", "statistics"],
    "operations": ["ops", "operations", "process", "execution"],
    "product": ["product", "roadmap", "user research", "strategy"],  # engineer context overrides this
}


class RoleKeywordCache:
    """DB-backed keyword cache. LLM-fills on miss."""

    def __init__(self, career_ops_root: str = None):
        self.db = get_db_manager(career_ops_root)
        self._llm = None

    def _get_llm(self):
        # Kept for API compatibility — returns self since we do the HTTP call directly
        return self if self._api_key() else False

    def _api_key(self) -> str:
        import os
        return os.getenv("DEEPSEEK_API_KEY", "")

    # ── Public API ────────────────────────────────────────────────────

    def get(self, role: str, city: str = "") -> dict:
        """Return {keywords, search_queries, sector_hints} for role.
        Cache-on-miss via LLM. Never returns empty — falls back to token-based defaults."""
        if not role or not role.strip():
            return {"keywords": [], "search_queries": [], "sector_hints": []}

        role_norm = _normalize_role(role)
        cached = self._lookup(role_norm)
        if cached:
            self._bump_usage(role_norm)
            # Always re-derive city-specific queries — cache stores keywords only
            cached["search_queries"] = self._derive_queries(cached["keywords"], city)
            return cached

        generated = self._llm_generate(role_norm, city)
        if not generated.get("keywords"):
            generated = self._fallback(role_norm)

        # Materialize search queries (city-specific, not stored in cache)
        generated["search_queries"] = self._derive_queries(generated["keywords"], city)

        self._store(role_norm, generated)
        return generated

    # ── Internals ─────────────────────────────────────────────────────

    def _lookup(self, role_norm: str) -> dict | None:
        try:
            with self.db.get_connection() as conn:
                row = conn.execute(
                    "SELECT keywords, search_queries, sector_hints FROM role_keywords WHERE role_name = ?",
                    [role_norm],
                ).fetchone()
            if row:
                return {
                    "keywords": json.loads(row["keywords"]),
                    "search_queries": json.loads(row["search_queries"] or "[]"),
                    "sector_hints": json.loads(row["sector_hints"] or "[]"),
                }
        except Exception as e:
            logger.debug(f"[RoleKeywords] lookup failed: {e}")
        return None

    def _bump_usage(self, role_norm: str):
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    "UPDATE role_keywords SET usage_count = usage_count + 1, last_used_at = ? WHERE role_name = ?",
                    [_now(), role_norm],
                )
        except Exception:
            pass

    def _store(self, role_norm: str, data: dict):
        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """INSERT INTO role_keywords
                           (role_name, keywords, search_queries, sector_hints, generated_at, usage_count, last_used_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?)
                       ON CONFLICT(role_name) DO UPDATE SET
                           keywords = excluded.keywords,
                           search_queries = excluded.search_queries,
                           sector_hints = excluded.sector_hints,
                           last_used_at = excluded.last_used_at""",
                    [
                        role_norm,
                        json.dumps(data.get("keywords", [])),
                        json.dumps(data.get("search_queries", [])),
                        json.dumps(data.get("sector_hints", [])),
                        _now(),
                        _now(),
                    ],
                )
        except Exception as e:
            logger.warning(f"[RoleKeywords] store failed: {e}")

    def _llm_generate(self, role: str, city: str = "") -> dict:
        llm = self._get_llm()
        if not llm:
            return {}
        system = (
            "You are a job search strategist. Given a role/function name, you generate "
            "search keywords and ready-to-use search queries that maximize coverage of "
            "real job postings for that role in India. You output STRICT JSON only — no commentary."
        )
        prompt = f"""Generate search artifacts for the role: "{role}" (city: "{city or 'India'}").

Return STRICT JSON only:
{{
  "keywords": [10-20 keywords/aliases that recruiters or job titles use for this role],
  "search_queries": [6-10 site-scoped search queries, mixing job boards and company career pages],
  "sector_hints": [3-6 likely sector/industry names where this role exists]
}}

Rules:
- Include adjacent titles (e.g., "fashion buyer" → "merchandiser", "category manager", "sourcing manager")
- Include seniority variants ("senior", "lead") only if relevant
- For sector_hints, use real industry names like "Retail & Commerce", "Fintech", "Healthcare"
- Do NOT invent technical-AI keywords if the role is non-technical
- Output only the JSON object. No markdown fences."""

        try:
            import os, requests as _req
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
            resp = _req.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 400,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
                timeout=15,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            return {
                "keywords": list(data.get("keywords", []))[:20],
                "search_queries": list(data.get("search_queries", []))[:10],
                "sector_hints": list(data.get("sector_hints", []))[:6],
            }
        except Exception as e:
            logger.warning(f"[RoleKeywords] LLM generation failed: {e}")
            return {}

    def _fallback(self, role: str) -> dict:
        """Token-based fallback when LLM unavailable. Better than hardcoded AI bias."""
        tokens = role.split()
        is_engineering_role = any(t in tokens for t in ("engineer", "engineering", "developer", "architect", "programmer"))
        keywords = [role] + tokens
        for token in tokens:
            if token not in _FALLBACK_BY_TOKEN:
                continue
            expansions = _FALLBACK_BY_TOKEN[token]
            # Don't add PM-domain terms when the role is technical
            if is_engineering_role and token == "product":
                expansions = [e for e in expansions if e not in ("roadmap", "pm", "user research", "strategy")]
            keywords.extend(expansions)
        # Dedupe preserving order
        seen = set()
        deduped = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                deduped.append(kw)
        return {"keywords": deduped, "search_queries": [], "sector_hints": []}

    def _derive_queries(self, keywords: list, city: str) -> list:
        """Derive site-scoped queries from keywords when LLM didn't provide them."""
        if not keywords:
            return []
        loc = city or "India"
        head = keywords[0]
        return [
            f'"{head}" jobs in {loc}',
            f'"{head}" hiring {loc} site:linkedin.com/jobs/view',
            f'"{head}" {loc} site:naukri.com',
            f'"{head}" {loc} site:cutshort.io',
            f'"{head}" {loc} site:wellfound.com',
            f'"{head}" {loc} site:instahyre.com',
        ]

    def evict_stale(self, days: int = 30):
        """Remove cache entries unused for > N days."""
        try:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM role_keywords WHERE last_used_at < ?", [cutoff])
        except Exception:
            pass
