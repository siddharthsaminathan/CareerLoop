"""Standard response envelope. Every endpoint returns this shape."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi.responses import JSONResponse


def _meta() -> dict:
    return {
        "request_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def ok(data: Any = None) -> dict:
    return {"ok": True, "data": data, "error": None, "meta": _meta()}


def err(message: str, status_code: int = 400, code: Optional[str] = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "data": None,
            "error": {"message": message, "code": code or f"http_{status_code}"},
            "meta": _meta(),
        },
    )


class APIError(Exception):
    """Raise inside services/routers to produce a clean error envelope."""

    def __init__(self, message: str, status_code: int = 400, code: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)
