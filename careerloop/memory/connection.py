"""
CareerLoop Memory Connection Manager.

Production: PostgreSQL via DATABASE_URL.
Local dev:  SQLite at careerloop_local.db when DATABASE_URL not set.
"""

import os
import sqlite3
import threading
import logging
from contextlib import contextmanager
from typing import Generator, Optional

logger = logging.getLogger("careerloop.memory.connection")

_SQLITE_INIT = """
CREATE TABLE IF NOT EXISTS role_keywords (
    role_name      TEXT PRIMARY KEY,
    keywords       TEXT NOT NULL DEFAULT '[]',
    search_queries TEXT NOT NULL DEFAULT '[]',
    sector_hints   TEXT NOT NULL DEFAULT '[]',
    generated_at   TEXT,
    usage_count    INTEGER NOT NULL DEFAULT 0,
    last_used_at   TEXT
);
CREATE TABLE IF NOT EXISTS companies (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    domain            TEXT DEFAULT '',
    city              TEXT DEFAULT '',
    sector            TEXT DEFAULT '',
    subsector         TEXT DEFAULT '',
    ats_provider      TEXT DEFAULT 'unknown',
    ats_url           TEXT DEFAULT '',
    career_page_url   TEXT DEFAULT '',
    linkedin_url      TEXT DEFAULT '',
    employee_estimate INTEGER DEFAULT 0,
    crawl_status      TEXT DEFAULT 'pending',
    last_crawled_at   TEXT,
    last_job_count    INTEGER DEFAULT 0,
    source            TEXT DEFAULT '',
    is_active         INTEGER DEFAULT 1,
    score             REAL DEFAULT 50.0,
    created_at        TEXT,
    updated_at        TEXT
);
CREATE TABLE IF NOT EXISTS role_archetypes (
    role_norm         TEXT PRIMARY KEY,
    must_have         TEXT NOT NULL DEFAULT '[]',
    avoid             TEXT NOT NULL DEFAULT '[]',
    preferred_company_types TEXT NOT NULL DEFAULT '[]',
    function_type     TEXT DEFAULT '',
    market_type       TEXT DEFAULT '',
    generated_at      TEXT
);
CREATE TABLE IF NOT EXISTS company_sources (
    company_id    TEXT NOT NULL,
    source_type   TEXT NOT NULL,
    crawl_url     TEXT,
    last_crawled_at TEXT,
    is_active     INTEGER DEFAULT 1,
    PRIMARY KEY (company_id, source_type)
);
CREATE TABLE IF NOT EXISTS company_functions (
    company_id   TEXT NOT NULL,
    function     TEXT NOT NULL,
    probability  REAL DEFAULT 0.5,
    is_active    INTEGER DEFAULT 1,
    PRIMARY KEY (company_id, function)
);
"""


# ─── SQLite dict-row wrapper ───────────────────────────────────────────────────

class _SQLiteConn:
    """Wraps sqlite3 connection to support dict-like row access (mirrors psycopg2 RealDictCursor)."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def execute(self, sql: str, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params or [])
        return cur

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


class _SQLiteManager:
    """SQLite-backed manager for local dev. Thread-safe via per-call connections."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_schema()
        logger.info(f"[DB] SQLite local dev: {db_path}")

    def _init_schema(self):
        conn = sqlite3.connect(self.db_path)
        conn.executescript(_SQLITE_INIT)
        conn.commit()
        conn.close()

    @contextmanager
    def get_connection(self) -> Generator:
        raw = sqlite3.connect(self.db_path, check_same_thread=False)
        conn = _SQLiteConn(raw)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# ─── PostgreSQL connection ─────────────────────────────────────────────────

def _get_pg_connection(db_url: str):
    import psycopg2
    from psycopg2.extras import RealDictCursor
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)


class DatabaseManager:
    """Thread-safe database manager. PostgreSQL via DATABASE_URL."""

    def __init__(self, db_url: Optional[str] = None, schema_path: Optional[str] = None):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.db_url = db_url or os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL not set")
        self._local = threading.local()
        self.schema_path = schema_path or os.path.join(
            base_dir, "careerloop", "memory", "supabase_schema.sql"
        )
        self._init_pg_schema()

    def _init_pg_schema(self):
        if not os.path.exists(self.schema_path):
            return
        with open(self.schema_path) as f:
            ddl_script = f.read()
        try:
            import psycopg2
            commands = [c.strip() for c in ddl_script.split(";") if c.strip()]
            with psycopg2.connect(self.db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_lock(hashtext('careerloop_schema_init'))")
                    for cmd in commands:
                        try:
                            cur.execute("SAVEPOINT schema_cmd")
                            cur.execute(cmd)
                            cur.execute("RELEASE SAVEPOINT schema_cmd")
                        except Exception as e:
                            cur.execute("ROLLBACK TO SAVEPOINT schema_cmd")
                            if "already exists" not in str(e):
                                logger.warning(f"Schema cmd warning: {e}")
                    cur.execute("SELECT pg_advisory_unlock(hashtext('careerloop_schema_init'))")
                conn.commit()
        except Exception as e:
            logger.warning(f"PG schema init warning: {e}")

    @contextmanager
    def get_connection(self) -> Generator:
        conn = _get_pg_connection(self.db_url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# ─── Module-level singleton ───────────────────────────────────────────────────

_default_manager = None
_manager_lock = threading.Lock()


def get_db_manager(career_ops_root: Optional[str] = None):
    global _default_manager
    with _manager_lock:
        if _default_manager is None:
            db_url = os.getenv("DATABASE_URL")
            if db_url:
                schema_path = None
                if career_ops_root:
                    schema_path = os.path.join(
                        career_ops_root, "careerloop", "memory", "supabase_schema.sql"
                    )
                _default_manager = DatabaseManager(db_url=db_url, schema_path=schema_path)
            else:
                # Local dev — SQLite fallback
                root = career_ops_root or os.getcwd()
                db_path = os.path.join(root, "test data", "output", "careerloop_local.db")
                _default_manager = _SQLiteManager(db_path)
    return _default_manager


@contextmanager
def get_connection(career_ops_root: Optional[str] = None) -> Generator:
    manager = get_db_manager(career_ops_root)
    with manager.get_connection() as conn:
        yield conn
