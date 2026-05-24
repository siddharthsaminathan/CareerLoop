"""
CareerLoop Memory Connection Manager -- Supabase PostgreSQL only.

All DB access goes through psycopg2/PostgreSQL via DATABASE_URL.
"""

import os
import threading
import logging
from contextlib import contextmanager
from typing import Generator, Optional

logger = logging.getLogger("careerloop.memory.connection")


# ─── PostgreSQL connection ─────────────────────────────────────────────────

def _get_pg_connection(db_url: str):
    import psycopg2
    from psycopg2.extras import RealDictCursor
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)


# ─── DatabaseManager ──────────────────────────────────────────────────────────

class DatabaseManager:
    """Thread-safe database manager. Supabase PostgreSQL only."""

    def __init__(self, db_url: Optional[str] = None, schema_path: Optional[str] = None):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.db_url = db_url or os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError(
                "DATABASE_URL is required. CareerLoop runs on Supabase PostgreSQL only. "
                "Set DATABASE_URL in your .env file or environment."
            )
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
                    cur.execute("UPDATE public.sessions SET state = 'PROFILE_COMPLETE' WHERE state = 'DAILY_BRIEF_SENT'")
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

_default_manager: Optional[DatabaseManager] = None
_manager_lock = threading.Lock()


def get_db_manager(career_ops_root: Optional[str] = None) -> DatabaseManager:
    global _default_manager
    with _manager_lock:
        if _default_manager is None:
            if not os.getenv("DATABASE_URL"):
                raise ValueError(
                    "DATABASE_URL is required. CareerLoop runs on Supabase PostgreSQL only. "
                    "Set DATABASE_URL in your .env file or environment."
                )
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
