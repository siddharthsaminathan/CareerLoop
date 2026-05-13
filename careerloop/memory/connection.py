"""
CareerLoop Memory Connection Manager — Local embedded SQLite access layer.

Provides context-managed database sessions, ensures foreign key enforcement,
supports dict-like Row access, and automatically initializes schema.sql.
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Generator, Optional


class DatabaseManager:
    """Manages thread-safe SQLite database connectivity and schema lifecycle."""

    def __init__(self, db_path: Optional[str] = None, schema_path: Optional[str] = None):
        # Resolve project root assuming this file is in careerloop/memory/connection.py
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        
        self.db_path = db_path or os.path.join(base_dir, "careerloop", "careerloop.db")
        self.schema_path = schema_path or os.path.join(base_dir, "careerloop", "memory", "schema.sql")
        self._local = threading.local()
        
        # Ensure base directories exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.initialize_database()

    def initialize_database(self):
        """Executes canonical schema DDL to ensure entity structures exist."""
        if not os.path.exists(self.schema_path):
            raise FileNotFoundError(f"Canonical schema script missing at {self.schema_path}")

        with open(self.schema_path, "r") as f:
            ddl_script = f.read()

        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.executescript(ddl_script)
            conn.commit()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager yielding a ready SQLite connection.
        Automatically enforces foreign keys and row factory mappings.
        """
        conn = getattr(self._local, "connection", None)
        is_new_connection = False
        
        if conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
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
        db_path = None
        schema_path = None
        if career_ops_root:
            db_path = os.path.join(career_ops_root, "careerloop", "careerloop.db")
            schema_path = os.path.join(career_ops_root, "careerloop", "memory", "schema.sql")
        _default_manager = DatabaseManager(db_path=db_path, schema_path=schema_path)
    return _default_manager

@contextmanager
def get_connection(career_ops_root: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Shorthand module access yielding a managed connection context."""
    manager = get_db_manager(career_ops_root)
    with manager.get_connection() as conn:
        yield conn
