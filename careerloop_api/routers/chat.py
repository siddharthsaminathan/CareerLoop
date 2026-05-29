"""Chat router — /chat/message."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from careerloop_api.core.envelope import ok
from careerloop_api.deps.auth import get_current_user
from careerloop_api.deps.db import get_db
from careerloop_api.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    text: str
    conversation_id: Optional[str] = None


@router.post("/message")
def message(body: ChatMessage, user_id: str = Depends(get_current_user), db=Depends(get_db)):
    return ok(ChatService(db).message(user_id, body.text))


@router.get("/history")
def history(user_id: str = Depends(get_current_user), db=Depends(get_db)):
    """Return the user's recent chat history so the frontend can restore it on login."""
    return ok(ChatService(db).get_history(user_id))
