"""Brief router — /briefs/latest, select item."""

from fastapi import APIRouter, Depends

from careerloop_api.core.envelope import ok
from careerloop_api.deps.auth import get_current_user
from careerloop_api.deps.db import get_db
from careerloop_api.services.brief_service import BriefService

router = APIRouter(prefix="/briefs", tags=["briefs"])


@router.get("/latest")
def latest(
    offset: int = 0,
    user_id: str = Depends(get_current_user),
    db=Depends(get_db),
):
    return ok(BriefService(db).latest(user_id, offset=offset))


@router.post("/{brief_id}/items/{item_index}/select")
def select_item(
    brief_id: str,
    item_index: int,
    user_id: str = Depends(get_current_user),
    db=Depends(get_db),
):
    return ok(BriefService(db).select_item(user_id, brief_id, item_index))
