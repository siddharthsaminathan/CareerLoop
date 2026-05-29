"""Auth router.

The OAuth flow (Google sign-in) is handled entirely by Supabase on the client.
The backend has no login endpoint — it just validates the Supabase JWT.

POST /v1/auth/me
  Called by the frontend immediately after OAuth completes.
  Verifies the token, provisions the careerloop.users row (first call only),
  and returns the user profile. Equivalent to "complete signup / ensure registered."

This is the only endpoint the client needs to call after sign-in.
"""

from fastapi import APIRouter, Depends

from careerloop_api.core.envelope import ok
from careerloop_api.deps.auth import get_current_user
from careerloop_api.deps.db import get_db
from careerloop_api.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/me")
def provision_and_get_me(user_id: str = Depends(get_current_user), db=Depends(get_db)):
    """Provision user on first call, return profile. Frontend calls this after OAuth."""
    return ok(UserService(db).me(user_id))
