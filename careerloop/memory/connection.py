"""
CareerLoop Memory Connection Manager — Supabase PostgreSQL access layer.

Provides context-managed database sessions and automatically initializes schema.sql.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import threading
from contextlib import contextmanager
from typing import Generator, Optional


class DatabaseManager:
    """Manages thread-safe PostgreSQL database connectivity and schema lifecycle."""

    def __init__(self, db_url: Optional[str] = None, schema_path: Optional[str] = None):
        # Resolve project root assuming this file is in careerloop/memory/connection.py
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        
        # Default to Supabase instance from Shanthi beta 2
        self.db_url = db_url or os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is required")
        self.schema_path = schema_path or os.path.join(base_dir, "careerloop", "memory", "supabase_schema.sql")
        self._local = threading.local()
        
        # Initialize schema
        self.initialize_database()

    def initialize_database(self):
        """Executes canonical schema DDL to ensure entity structures exist."""
        if not os.path.exists(self.schema_path):
            raise FileNotFoundError(f"Canonical schema script missing at {self.schema_path}")

        with open(self.schema_path, "r") as f:
            ddl_script = f.read()

        # Execute schema
        try:
            commands = [cmd.strip() for cmd in ddl_script.split(';') if cmd.strip()]
            with psycopg2.connect(self.db_url) as conn:
                with conn.cursor() as cur:
                    # Serialize schema initialization across concurrent processes to avoid DDL deadlocks.
                    cur.execute("SELECT pg_advisory_lock(hashtext('careerloop_schema_init'))")
                    for cmd in commands:
                        try:
                            cur.execute("SAVEPOINT schema_cmd")
                            cur.execute(cmd)
                            cur.execute("RELEASE SAVEPOINT schema_cmd")
                        except Exception as cmd_e:
                            cur.execute("ROLLBACK TO SAVEPOINT schema_cmd")
                            if "already exists" not in str(cmd_e):
                                print(f"Schema command failed: {cmd_e}")
                    cur.execute("SELECT pg_advisory_unlock(hashtext('careerloop_schema_init'))")
                conn.commit()
        except Exception as e:
            print(f"Schema init skipped or failed: {e}")

    @contextmanager
    def get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """
        Context manager yielding a ready PostgreSQL connection.
        Automatically uses RealDictCursor for dict-like Row access.
        """
        conn = getattr(self._local, "connection", None)
        is_new_connection = False
        
        if conn is None:
            conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
            self._local.connection = conn
            is_new_connection = True

        try:
            yield conn
            if is_new_connection:
                conn.commit()
        except Exception:
            if is_new_connection:
                conn.rollback()
            raise
        finally:
            if is_new_connection:
                conn.close()
                self._local.connection = None


# Default singleton instance exported for module convenience
_default_manager: Optional[DatabaseManager] = None

def get_db_manager(career_ops_root: Optional[str] = None) -> DatabaseManager:
    """Returns the singleton DatabaseManager instance."""
    global _default_manager
    if _default_manager is None:
        schema_path = None
        if career_ops_root:
            schema_path = os.path.join(career_ops_root, "careerloop", "memory", "supabase_schema.sql")
        _default_manager = DatabaseManager(schema_path=schema_path)
    return _default_manager

@contextmanager
def get_connection(career_ops_root: Optional[str] = None) -> Generator[psycopg2.extensions.connection, None, None]:
    """Shorthand module access yielding a managed connection context."""
    manager = get_db_manager(career_ops_root)
    with manager.get_connection() as conn:
        yield conn
