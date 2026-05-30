"""Debug / runtime-observability router — GET /v1/debug/runtime.

Read-only introspection of live in-memory runtime state. Built for the
backend-stability investigation: surfaces the resources that leak over uptime
(connection pools, threads, SSE streams, scan guards) so degradation is visible
*before* the server hangs, and so a leak can be confirmed by watching a number
climb across requests instead of guessing.

No auth: this is a localhost operational endpoint. If exposed publicly, gate it
behind get_current_user or an ops token.
"""

import gc
import os
import threading
import time

from fastapi import APIRouter

router = APIRouter(prefix="/debug", tags=["debug"])

_BOOT_TS = time.time()


def _count_pg_pools():
    """Count live psycopg_pool.ConnectionPool objects (LangGraph checkpointer pools).

    A healthy server has ONE. A climbing number proves the per-chat-turn
    checkpointer pool leak (get_checkpointer() builds a new pool each call).
    """
    pools = []
    try:
        import psycopg_pool
        for obj in gc.get_objects():
            try:
                if isinstance(obj, psycopg_pool.ConnectionPool):
                    info = {"name": getattr(obj, "name", None)}
                    try:
                        s = obj.get_stats()
                        info["size"] = s.get("pool_size")
                        info["available"] = s.get("pool_available")
                        info["requests_waiting"] = s.get("requests_waiting")
                    except Exception:
                        pass
                    pools.append(info)
            except ReferenceError:
                continue
    except Exception as e:
        return {"error": str(e), "count": None}
    return {"count": len(pools), "pools": pools}


def _psycopg2_pool_status():
    """Introspect the shared DatabaseManager ThreadedConnectionPool (psycopg2)."""
    try:
        from careerloop.memory.connection import get_db_manager
        mgr = get_db_manager()
        pool = getattr(mgr, "_pool", None)
        out = {
            "maxconn": getattr(mgr, "_maxconn", None),
            "minconn": getattr(mgr, "_minconn", None),
            "initialized": pool is not None,
        }
        if pool is not None:
            # psycopg2.pool.AbstractConnectionPool internals
            free = getattr(pool, "_pool", None)
            used = getattr(pool, "_used", None)
            out["free"] = len(free) if free is not None else None
            out["in_use"] = len(used) if used is not None else None
        return out
    except Exception as e:
        return {"error": str(e)}


def _memory():
    out = {}
    try:
        import resource
        ru = resource.getrusage(resource.RUSAGE_SELF)
        # macOS reports ru_maxrss in bytes; Linux in KiB. Normalize to MB.
        rss = ru.ru_maxrss
        out["max_rss_mb"] = round(rss / (1024 * 1024), 1) if rss > 10_000_000 else round(rss / 1024, 1)
    except Exception:
        pass
    try:
        import psutil  # type: ignore
        p = psutil.Process()
        out["rss_mb"] = round(p.memory_info().rss / (1024 * 1024), 1)
        out["num_fds"] = p.num_fds()
        out["num_threads_psutil"] = p.num_threads()
    except Exception:
        pass
    return out


def _threads():
    threads = threading.enumerate()
    buckets: dict = {}
    for t in threads:
        name = t.name
        # Bucket by family so leak-y pools/workers are visible at a glance.
        if name.startswith("pool-") or "ConnectionPool" in name or name.startswith("psycopg"):
            key = "psycopg_pool_worker"
        elif name.startswith("ThreadPoolExecutor") or name.startswith("anyio"):
            key = "anyio_worker"
        elif name.startswith("Thread-"):
            key = "anonymous_thread"
        else:
            key = name
        buckets[key] = buckets.get(key, 0) + 1
    return {"total": len(threads), "by_family": buckets}


@router.get("/runtime")
def runtime():
    """Live runtime-state snapshot. Poll this across requests to watch for leaks."""
    from careerloop_api.services.scan_service import runtime_snapshot

    return {
        "ok": True,
        "uptime_s": round(time.time() - _BOOT_TS, 1),
        "pid": os.getpid(),
        "threads": _threads(),
        "memory": _memory(),
        "db_pool_psycopg2": _psycopg2_pool_status(),
        "checkpointer_pools_psycopg3": _count_pg_pools(),
        "scans_and_streams": runtime_snapshot(),
    }


@router.get("/db-check")
def db_check():
    """Verify a real DB connection can be acquired and queried.
    Returns latency_ms.  If ok=False, the pool is exhausted or the DB is down."""
    from careerloop.memory.connection import get_db_manager
    mgr = get_db_manager()
    result = mgr.check_connection()
    return {"ok": result["ok"], **result}


@router.get("/pool")
def pool_health():
    """Detailed connection pool health."""
    from careerloop.memory.connection import get_db_manager
    mgr = get_db_manager()
    result = mgr.pool_health()
    # Add a direct connection check
    check = mgr.check_connection()
    result["connection_check"] = check
    result["uptime_s"] = round(time.time() - _BOOT_TS, 1)
    return result
