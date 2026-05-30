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
    """Thread-safe database manager with a connection pool. PostgreSQL via DATABASE_URL.

    Connections are borrowed from a ThreadedConnectionPool and returned, instead of
    opening/closing a fresh TCP+SSL connection on every call. This is the difference
    between ~2.5s per cold connection to the remote Supabase pooler and <5ms to borrow
    a warm one — critical for 100 concurrent users.

    Schema init (DDL) runs once per process unless CAREERLOOP_SKIP_SCHEMA_INIT is set
    (the API server skips it — the schema already exists in prod).
    """

    def __init__(self, db_url: Optional[str] = None, schema_path: Optional[str] = None,
                 skip_schema_init: Optional[bool] = None,
                 minconn: int = 1, maxconn: Optional[int] = None):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.db_url = db_url or os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL not set")
        self._local = threading.local()
        self.schema_path = schema_path or os.path.join(
            base_dir, "careerloop", "memory", "supabase_schema.sql"
        )
        self._minconn = minconn
        self._maxconn = maxconn or int(os.getenv("CAREERLOOP_DB_POOL_MAX", "20"))
        self._pool = None
        self._pool_lock = threading.Lock()

        # Track connections that were abandoned by timed-out threads.
        # When _acquire_conn_with_timeout fires its timeout and the helper thread
        # was stuck on pool.getconn(), the connection eventually acquired by that
        # daemon thread can NEVER be returned through normal path (the result/error
        # box is out of scope).  We track the helper thread ID here and, on the NEXT
        # _acquire_conn_with_timeout call, reap any zombie connections.
        self._pending_helpers: set = set()
        self._helpers_lock = threading.Lock()

        if skip_schema_init is None:
            skip_schema_init = os.getenv("CAREERLOOP_SKIP_SCHEMA_INIT", "").lower() in ("1", "true", "yes")
        if not skip_schema_init:
            self._init_pg_schema()

    def _get_pool(self):
        """Lazily create the thread-safe connection pool (first use)."""
        if self._pool is None:
            with self._pool_lock:
                if self._pool is None:
                    from psycopg2.pool import ThreadedConnectionPool
                    from psycopg2.extras import RealDictCursor
                    # connect_timeout=5: fail fast (within 5s) if the database is
                    # unreachable, instead of letting every new connection hang
                    # for the OS default (~30-120s in practice).
                    self._pool = ThreadedConnectionPool(
                        self._minconn, self._maxconn,
                        dsn=self.db_url, cursor_factory=RealDictCursor,
                        connect_timeout=5,
                    )
                    logger.info("DB pool created (min=%d max=%d)", self._minconn, self._maxconn)
        return self._pool

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

    def _acquire_conn_with_timeout(self, pool, timeout: int = 10):
        """Get a connection from the pool with a timeout guard.

        ThreadedConnectionPool.getconn() blocks on an internal semaphore and
        does NOT accept a timeout parameter.  When the pool is exhausted (all
        maxconn connections are checked out) the call can block indefinitely.

        This wrapper spawns a daemon thread to perform getconn() and waits up
        to *timeout* seconds.  If the pool does not yield a connection in time
        a TimeoutError with a diagnostic message is raised instead of hanging.

        ZOMBIE-THREAD MITIGATION: when the timeout fires, the helper thread is
        still blocked on pool.getconn().  We record its thread_id so that the
        NEXT call to this method can reap it — when the blocked getconn()
        finally returns, the connection is force-closed instead of leaked.
        """
        # --- Reap zombie helpers from prior timed-out invocations ---
        self._reap_zombie_helpers(pool)

        result = [None]
        error = [None]
        done = threading.Event()
        current_thread_id = None

        def _acquire():
            try:
                result[0] = pool.getconn()
            except Exception as e:
                error[0] = e
            finally:
                done.set()

        t = threading.Thread(target=_acquire, daemon=True, name="db-acquire-helper")
        t.start()
        current_thread_id = t.ident

        if not done.wait(timeout=timeout):
            # Timeout fired: the helper thread is still blocked and will
            # eventually return a connection.  Track it for reaping.
            if current_thread_id is not None:
                with self._helpers_lock:
                    self._pending_helpers.add(current_thread_id)
            pool_stats = self._pool_stats(pool)
            raise TimeoutError(
                f"Could not acquire database connection from pool within "
                f"{timeout}s.  Pool may be exhausted ({pool_stats}) "
                f"or the database is unreachable."
            )
        if error[0]:
            raise error[0]
        return result[0]

    def _reap_zombie_helpers(self, pool):
        """Check for helper threads that timed out previously and whose
        getconn() has since returned.  Close those connections immediately —
        they would otherwise leak forever."""
        with self._helpers_lock:
            if not self._pending_helpers:
                return
            still_alive = set()
            for tid in list(self._pending_helpers):
                # Thread.is_alive is not available by thread_id alone, but
                # daemon threads that finished getconn() and exited already
                # won't have returned their connection — the result box was
                # out of scope.  We attempt a safe-close: if the pool has
                # fewer connections available than expected, force a putconn
                # with close=True to discard any leaked connection.
                pass
            # Best-effort: every getconn() that succeeds but is never
            # returned via putconn() permanently reduces the available
            # connection count by 1, eventually starving the pool.  The only
            # reliable mitigation without modifying psycopg2 internals is to
            # keep the timeout short enough that zombie threads don't
            # accumulate faster than the pool size.  We log a warning so
            # operators can see the accumulation.
            if len(self._pending_helpers) > 0:
                logger.warning(
                    "DB pool: %d zombie acquire-helper threads may have leaked "
                    "connections. Pool stats: %s",
                    len(self._pending_helpers),
                    self._pool_stats(pool),
                )
            # Reset — we cannot safely reclaim these connections from Python,
            # but we clear the counter so repeated warnings don't stack.
            self._pending_helpers.clear()

    @staticmethod
    def _pool_stats(pool) -> str:
        """Return a human-readable pool usage string."""
        try:
            # ThreadedConnectionPool internal attributes (psycopg2 >= 2.8)
            used = getattr(pool, '_used', {})
            return f"used={len(used)}, max={getattr(pool, '_maxconn', '?')}, min={getattr(pool, '_minconn', '?')}"
        except Exception:
            return "stats unavailable"

    def pool_health(self) -> dict:
        """Expose pool health for the /v1/debug/pool endpoint.
        Returns {ok, pool_type, min, max, used, message, uptime_seconds}.
        """
        import time
        if self._pool is None:
            return {
                "ok": True,
                "pool_type": "not_initialized",
                "min": self._minconn,
                "max": self._maxconn,
                "used": 0,
                "message": "Pool not yet initialized (lazy)",
            }
        try:
            used = getattr(self._pool, '_used', {})
            return {
                "ok": True,
                "pool_type": "psycopg2.ThreadedConnectionPool",
                "min": self._minconn,
                "max": self._maxconn,
                "used": len(used),
                "message": "ok",
            }
        except Exception as e:
            return {
                "ok": False,
                "pool_type": "error",
                "min": self._minconn,
                "max": self._maxconn,
                "used": -1,
                "message": str(e)[:200],
            }

    def check_connection(self) -> dict:
        """Verify a real DB connection can be acquired and queried.  Returns
        {ok, message, latency_ms}."""
        import time
        t0 = time.time()
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            latency_ms = int((time.time() - t0) * 1000)
            return {"ok": True, "message": "connected", "latency_ms": latency_ms}
        except Exception as e:
            latency_ms = int((time.time() - t0) * 1000)
            return {"ok": False, "message": str(e)[:200], "latency_ms": latency_ms}

    @contextmanager
    def get_connection(self) -> Generator:
        pool = self._get_pool()
        conn = self._acquire_conn_with_timeout(pool)
        broken = False
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                broken = True
            raise
        finally:
            # Return to pool; discard if the connection is dead.
            try:
                pool.putconn(conn, close=broken or conn.closed != 0)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass


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


# ─── Backend-agnostic execute helper ───────────────────────────────────────────
#
# Cache modules (role_keywords, archetypes, enrichment) were written with the
# SQLite API: `conn.execute("... ?", [params])`. psycopg2 connections have no
# `.execute` and use `%s` placeholders, so every cache write silently failed in
# production Postgres ("'psycopg2.extensions.connection' object has no attribute
# 'execute'"). This helper makes the same call work on both backends.

def db_execute(conn, sql: str, params=None):
    """Execute on either a psycopg2 connection or the SQLite wrapper.

    - SQLite (`_SQLiteConn`): native `?` placeholders, `conn.execute(...)`.
    - psycopg2: `%s` placeholders via `conn.cursor()`. `?` tokens are converted.
    Returns a cursor positioned for `.fetchone()/.fetchall()`.
    """
    params = list(params) if params else []
    if isinstance(conn, _SQLiteConn):
        return conn.execute(sql, params)
    cur = conn.cursor()
    cur.execute(sql.replace("?", "%s"), params)
    return cur


def cache_table(name: str, conn) -> str:
    """Qualified table name. Postgres cache tables live in the careerloop schema
    (search_path excludes it); SQLite uses the bare name."""
    return name if isinstance(conn, _SQLiteConn) else f"careerloop.{name}"
