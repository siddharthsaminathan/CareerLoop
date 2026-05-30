"""LangGraph checkpointer factory.

Returns a PostgresSaver (production) or MemorySaver (local dev / fallback).
Called once per session by chat_service.py and cached via lru_cache on
get_supervisor_graph().
"""

import logging
import os
import threading

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

# Process-wide singleton. CRITICAL: get_checkpointer() is called once per chat
# turn (chat_service.message); without caching, each call built a NEW
# psycopg_pool.ConnectionPool (min_size=4 conns + worker/scheduler threads) that
# was never closed — a connection+thread leak that exhausted the DB and the
# threadpool after a few hours of uptime. One pool per process is correct because
# DATABASE_URL is constant for the process lifetime.
_checkpointer_singleton = None
_checkpointer_lock = threading.Lock()


def get_checkpointer():
    """Return the process-wide BaseCheckpointSaver singleton (lazy, thread-safe).

    PostgresSaver if DATABASE_URL is set and reachable,
    MemorySaver otherwise (in-memory, no persistence across restarts).
    """
    global _checkpointer_singleton
    if _checkpointer_singleton is not None:
        return _checkpointer_singleton
    with _checkpointer_lock:
        if _checkpointer_singleton is not None:
            return _checkpointer_singleton
        _checkpointer_singleton = _build_checkpointer()
        return _checkpointer_singleton


def _build_checkpointer():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.warning("checkpointer: DATABASE_URL not set — using MemorySaver (in-memory)")
        return MemorySaver()

    try:
        pool = ConnectionPool(
            conninfo=db_url,
            kwargs={"autocommit": True, "prepare_threshold": None},
            timeout=3,
        )
        checkpointer = PostgresSaver(pool)
        try:
            checkpointer.setup()
        except Exception as e:
            msg = str(e).lower()
            if "already exists" not in msg:
                raise
        logger.info("checkpointer: PostgresSaver connected successfully")
        return checkpointer
    except Exception as e:
        logger.error("checkpointer: Postgres connection failed: %s", e)
        logger.warning("checkpointer: falling back to MemorySaver (in-memory)")
        return MemorySaver()
