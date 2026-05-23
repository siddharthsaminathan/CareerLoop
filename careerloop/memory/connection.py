"""
CareerLoop Memory Connection Manager — dual-mode database access layer.

Mode 1 (production/Supabase): DATABASE_URL set → PostgreSQL via psycopg2
Mode 2 (local dev): DATABASE_URL absent → SQLite via careerloop/careerloop.db

All callers use get_connection() context manager and get dict-like rows either way.
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Generator, Optional

# ─── SQLite compatibility shim ────────────────────────────────────────────────

class _DictRow(dict):
    """sqlite3.Row wrapper that behaves like a dict (compatible with psycopg2 RealDictRow)."""
    pass


def _sqlite_row_factory(cursor, row):
    return _DictRow(zip([d[0] for d in cursor.description], row))


class _SQLiteCursor:
    """Thin wrapper so callers can use cursor.execute() / fetchall() / fetchone()."""
    def __init__(self, conn):
        self._conn = conn
        self._cur = conn.cursor()

    def execute(self, sql, params=()):
        # PostgreSQL-style %s → SQLite-style ?
        sql = sql.replace("%s", "?")
        self._cur.execute(sql, params)
        return self

    def executemany(self, sql, params_seq):
        sql = sql.replace("%s", "?")
        self._cur.executemany(sql, params_seq)
        return self

    def fetchall(self):
        return self._cur.fetchall()

    def fetchone(self):
        return self._cur.fetchone()

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class _SQLiteConn:
    """Wraps sqlite3 connection to behave like psycopg2 connection for our usage patterns."""
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = _sqlite_row_factory
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def cursor(self):
        return _SQLiteCursor(self._conn)

    def execute(self, sql, params=()):
        sql = sql.replace("%s", "?")
        return self._conn.execute(sql, params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self.rollback()
        else:
            self.commit()


# ─── PostgreSQL path (only imported when DATABASE_URL is set) ─────────────────

def _get_pg_connection(db_url: str):
    import psycopg2
    from psycopg2.extras import RealDictCursor
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)


# ─── DatabaseManager ──────────────────────────────────────────────────────────

class DatabaseManager:
    """
    Thread-safe database manager.
    Auto-selects PostgreSQL (Supabase) or SQLite based on DATABASE_URL presence.
    """

    def __init__(self, db_url: Optional[str] = None, schema_path: Optional[str] = None):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self._use_sqlite = not bool(self.db_url)
        self._local = threading.local()

        if self._use_sqlite:
            self._sqlite_path = os.path.join(base_dir, "careerloop", "careerloop.db")
            self._init_sqlite_schema()
        else:
            self.schema_path = schema_path or os.path.join(
                base_dir, "careerloop", "memory", "supabase_schema.sql"
            )
            self._init_pg_schema()

    def _init_sqlite_schema(self):
        """Bootstrap minimal SQLite tables needed by the search pipeline."""
        ddl = """
        CREATE TABLE IF NOT EXISTS companies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            domain TEXT,
            city TEXT,
            sector TEXT,
            description TEXT,
            career_page_url TEXT,
            ats_provider TEXT,
            ats_url TEXT,
            ats_slug TEXT,
            linkedin_url TEXT,
            employee_count INTEGER,
            funding_stage TEXT,
            function_probability REAL DEFAULT 0.5,
            targeting_score REAL DEFAULT 50.0,
            crawl_status TEXT DEFAULT 'pending',
            last_crawled_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS company_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            crawl_url TEXT,
            last_crawled_at TEXT,
            is_active INTEGER DEFAULT 1,
            UNIQUE(company_id, source_type)
        );
        CREATE TABLE IF NOT EXISTS role_keywords (
            role_key TEXT PRIMARY KEY,
            keywords TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS job_cache (
            id TEXT PRIMARY KEY,
            company_id TEXT,
            title TEXT,
            description TEXT,
            apply_url TEXT,
            location TEXT,
            department TEXT,
            source_type TEXT,
            raw_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """
        conn = _SQLiteConn(self._sqlite_path)
        for stmt in ddl.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    conn.execute(stmt)
                except Exception:
                    pass
        conn.commit()
        conn.close()

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
                                print(f"Schema cmd warning: {e}")
                    cur.execute("SELECT pg_advisory_unlock(hashtext('careerloop_schema_init'))")
                conn.commit()
        except Exception as e:
            print(f"PG schema init warning: {e}")

    @contextmanager
    def get_connection(self) -> Generator:
        if self._use_sqlite:
            conn = _SQLiteConn(self._sqlite_path)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        else:
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

_default_manager: Optional[DatabaseManager] = None
_manager_lock = threading.Lock()


def get_db_manager(career_ops_root: Optional[str] = None) -> DatabaseManager:
    global _default_manager
    with _manager_lock:
        if _default_manager is None:
            schema_path = None
            if career_ops_root:
                schema_path = os.path.join(
                    career_ops_root, "careerloop", "memory", "supabase_schema.sql"
                )
            _default_manager = DatabaseManager(schema_path=schema_path)
    return _default_manager


@contextmanager
def get_connection(career_ops_root: Optional[str] = None) -> Generator:
    manager = get_db_manager(career_ops_root)
    with manager.get_connection() as conn:
        yield conn
