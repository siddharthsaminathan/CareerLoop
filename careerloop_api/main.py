"""CareerLoop REST API — FastAPI entry point.

Start:
    uvicorn careerloop_api.main:app --host 0.0.0.0 --port 8001 --reload

All routes are mounted under /v1.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from careerloop_api.core.config import settings
from careerloop_api.core.envelope import APIError, err
from careerloop_api.routers import auth, users, briefs, jobs, chat, scans

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("careerloop_api")

app = FastAPI(title=settings.API_TITLE, version=settings.API_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Error handling ─────────────────────────────────────────────────────────────

@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    return err(exc.message, status_code=exc.status_code, code=exc.code)


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s: %s", request.url.path, exc)
    return err("Internal server error.", status_code=500, code="internal_error")


# ── Routers (mounted under /v1) ─────────────────────────────────────────────────

API_PREFIX = "/v1"
for r in (auth.router, users.router, briefs.router, jobs.router, chat.router, scans.router):
    app.include_router(r, prefix=API_PREFIX)


@app.get("/health")
def health():
    return {"status": "ok", "service": "careerloop-api", "version": settings.API_VERSION}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("careerloop_api.main:app", host="0.0.0.0", port=8001, reload=False)
