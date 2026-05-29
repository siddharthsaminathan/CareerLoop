"""Auth dependency — verifies Supabase JWT and auto-provisions careerloop.users.

Every protected endpoint calls get_current_user().
On the first request from a new Google/OAuth user:
  - Supabase has already created auth.users row (auth schema, not ours)
  - We create a matching careerloop.users row using the same UUID as the id
  - Subsequent requests hit the DO NOTHING path (fast)

This is universal across web, iOS, and Android — all clients issue the same
Supabase JWT, so auth is transport-agnostic.
"""

import logging
import threading
import time
from typing import Optional

from fastapi import Depends, Header

from careerloop_api.core.envelope import APIError
from careerloop_api.core.security import extract_user_info, verify_supabase_jwt
from careerloop_api.deps.db import get_db

logger = logging.getLogger("careerloop_api.deps.auth")

# In-process cache of provisioned user_ids → last-provisioned epoch.
# Avoids a DB write on EVERY authenticated request (was an INSERT...ON CONFLICT
# DO UPDATE per call). We re-touch last_active_at at most once per TTL window.
_PROVISION_TTL = 300  # seconds
_provisioned: dict = {}
_provision_lock = threading.Lock()


def _provision_user(db, user_id: str, email: str, full_name: str, provider: str) -> None:
    """Ensure careerloop.users row exists for this Supabase user. Idempotent.

    Raises the database exception if the insert/update fails.
    """
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO careerloop.users (
                    id, email, full_name, signup_source,
                    onboarding_complete, created_at, updated_at, last_active_at
                ) VALUES (
                    %s, %s, %s, %s,
                    false, NOW(), NOW(), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    last_active_at = NOW(),
                    email          = EXCLUDED.email
                """,
                (user_id, email, full_name or email, provider or "web"),
            )


def get_current_user(
    authorization: Optional[str] = Header(None),
    db=Depends(get_db),
) -> str:
    """Verify Supabase JWT, provision user if new, return user_id (UUID string)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise APIError(
            "Missing or malformed Authorization header. Expected: Bearer <supabase_access_token>",
            status_code=401,
            code="unauthorized",
        )

    token = authorization.split(" ", 1)[1].strip()

    try:
        payload = verify_supabase_jwt(token)
    except ValueError as e:
        raise APIError(str(e), status_code=401, code="unauthorized")

    info = extract_user_info(payload)
    user_id = info["user_id"]

    if not user_id:
        raise APIError("Token is missing subject (sub) claim.", status_code=401, code="unauthorized")

    # Only hit the DB if this user hasn't been provisioned recently (TTL window).
    now = time.time()
    last = _provisioned.get(user_id, 0)
    if now - last > _PROVISION_TTL:
        try:
            _provision_user(
                db,
                user_id=user_id,
                email=info["email"],
                full_name=info["full_name"],
                provider=info["provider"],
            )
            with _provision_lock:
                _provisioned[user_id] = now
        except Exception as e:
            logger.error("User provisioning failed for %s: %s", user_id[:8], e)
            raise APIError(
                f"Failed to provision user profile: {str(e)}",
                status_code=500,
                code="internal_error",
            )

    return user_id
