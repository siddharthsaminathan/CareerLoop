"""LangGraph checkpointer factory.

Returns a PostgresSaver (production) or MemorySaver (local dev / fallback).
Called once per session by chat_service.py and cached via lru_cache on
get_supervisor_graph().
"""

import logging
import os

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


def get_checkpointer():
    """Return a BaseCheckpointSaver instance.

    PostgresSaver if DATABASE_URL is set and reachable,
    MemorySaver otherwise (in-memory, no persistence across restarts).
    """
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
