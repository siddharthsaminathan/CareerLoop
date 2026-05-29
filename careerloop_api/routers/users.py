"""User router — /me, /me/preferences."""

from fastapi import APIRouter, Depends

from careerloop_api.core.envelope import ok
from careerloop_api.deps.auth import get_current_user
from careerloop_api.deps.db import get_db
from careerloop_api.services.user_service import UserService

router = APIRouter(tags=["users"])


@router.get("/me")
def me(user_id: str = Depends(get_current_user), db=Depends(get_db)):
    return ok(UserService(db).me(user_id))


@router.get("/me/preferences")
def preferences(user_id: str = Depends(get_current_user), db=Depends(get_db)):
    return ok(UserService(db).preferences(user_id))
