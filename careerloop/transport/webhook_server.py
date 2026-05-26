"""
CareerLoop Telegram Webhook Server.

Receives Telegram updates and routes them through the onboarding flow or
the LangGraph supervisor. Single entry point for all multi-user traffic.

Start:
    uvicorn careerloop.transport.webhook_server:app --host 0.0.0.0 --port 8000
"""

import os
import io
import logging
import tempfile
from typing import Optional

import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from careerloop.memory.connection import get_db_manager
from careerloop.session.session_store import SessionStore
from careerloop.session.states import UserJourneyState
from careerloop.onboarding.onboarding_flow import OnboardingFlow
from careerloop.transport.telegram import TelegramAdapter

logger = logging.getLogger("careerloop.transport.webhook_server")

# ── Singleton init ─────────────────────────────────────────────────────────────

def _build_components():
    db = get_db_manager()
    store = SessionStore(db)
    transport = TelegramAdapter()
    flow = OnboardingFlow(store)
    return store, transport, flow

_store: Optional[SessionStore] = None
_transport: Optional[TelegramAdapter] = None
_flow: Optional[OnboardingFlow] = None

app = FastAPI(title="CareerLoop Telegram Webhook")

@app.on_event("startup")
def startup():
    global _store, _transport, _flow
    _validate_env()
    _store, _transport, _flow = _build_components()
    logger.info("CareerLoop webhook server started.")


def _validate_env():
    missing = []
    for var in ("TELEGRAM_BOT_TOKEN", "DATABASE_URL", "DEEPSEEK_API_KEY"):
        if not os.getenv(var):
            missing.append(var)
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")


# ── Main webhook handler ───────────────────────────────────────────────────────

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Telegram sends either message or callback_query
    message = update.get("message") or update.get("callback_query", {}).get("message")
    if not message:
        return JSONResponse({"ok": True})

    from_data = message.get("from") or update.get("callback_query", {}).get("from") or {}
    chat_id = str(message.get("chat", {}).get("id", ""))
    if not chat_id:
        return JSONResponse({"ok": True})

    first_name = from_data.get("first_name", "")
    username = from_data.get("username", "")
    callback_data = update.get("callback_query", {}).get("data")

    # Resolve stable user_id from telegram_chat_id
    try:
        user_id = _store.get_or_create_user(
            telegram_chat_id=int(chat_id),
            first_name=first_name,
            username=username,
        )
    except Exception as e:
        logger.error("get_or_create_user failed for chat_id=%s: %s", chat_id, e)
        _transport.send_text(chat_id, "Sorry, I had trouble recognising you. Please try again.")
        return JSONResponse({"ok": True})

    # Resolve text: callback button, plain text, or file download
    if callback_data:
        text = callback_data
    elif "document" in message:
        text = _download_and_extract_document(message["document"])
        if text is None:
            _transport.send_text(chat_id, "I couldn't read that file. Please send a PDF or DOCX, or paste your CV as plain text.")
            return JSONResponse({"ok": True})
    else:
        text = (message.get("text") or "").strip()

    if not text:
        return JSONResponse({"ok": True})

    # Route: NEW_USER → onboarding flow; others → supervisor graph
    session = _store.get_session(user_id)

    if session.state == UserJourneyState.NEW_USER:
        # If user reconnects mid-flow (onboarding_step > 0) without sending text,
        # re-emit the contextual resume prompt so they know where they left off.
        if not text.strip() or (session.onboarding_step > 0 and text.strip().lower() in {"hi", "hello", "hey", "start", "back"}):
            resume_msg = _flow.resume_prompt(session)
            _transport.send_text(chat_id, resume_msg)
            return JSONResponse({"ok": True})
        try:
            reply, _new_state = _flow.handle_message(session, text)
        except Exception as e:
            logger.exception("OnboardingFlow error for user %s: %s", user_id[:12], e)
            reply = "Something went wrong during setup. Your data is safe — please try again."
        _transport.send_text(chat_id, reply)
    else:
        _route_to_supervisor(user_id, chat_id, text, session)

    return JSONResponse({"ok": True})


def _route_to_supervisor(user_id: str, chat_id: str, text: str, session):
    """Hand off to the LangGraph supervisor graph for PROFILE_READY users."""
    try:
        from langchain_core.messages import HumanMessage
        from careerloop.session.supervisor_graph import build_supervisor_graph

        graph = build_supervisor_graph()
        graph_input = {
            "user_id": user_id,
            "current_state": session.state,
            "messages": [HumanMessage(content=text)],
            "temp_profile_data": session.temp_profile_data or {},
            "artifact_context": {
                "active_artifact_type": session.active_artifact_type,
                "active_artifact_id": session.active_artifact_id,
                "active_job_id": session.active_job_id,
                "active_brief_id": session.active_brief_id,
            },
        }
        config = {"configurable": {"thread_id": user_id}}
        result = graph.invoke(graph_input, config=config)
        reply = result.get("assistant_response") or "Something went wrong. Try again."
        _transport.send_text(chat_id, reply)
    except Exception as e:
        logger.exception("Supervisor graph error for user %s: %s", user_id[:12], e)
        _transport.send_text(chat_id, "I hit an internal issue. Your data is safe — try again.")


# ── Document extraction ────────────────────────────────────────────────────────

def _download_and_extract_document(doc_meta: dict) -> Optional[str]:
    """Download a Telegram document and extract plain text from PDF or DOCX."""
    file_id = doc_meta.get("file_id")
    mime = doc_meta.get("mime_type", "")
    if not file_id:
        return None

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getFile",
            params={"file_id": file_id},
            timeout=10,
        )
        file_path = r.json()["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        content = requests.get(file_url, timeout=30).content
    except Exception as e:
        logger.error("Failed to download Telegram file: %s", e)
        return None

    return _extract_text(content, mime)


def _extract_text(content: bytes, mime: str) -> Optional[str]:
    if "pdf" in mime:
        return _extract_pdf(content)
    if "word" in mime or "docx" in mime or "openxmlformats" in mime:
        return _extract_docx(content)
    # Plain text fallback
    try:
        return content.decode("utf-8", errors="replace")
    except Exception:
        return None


def _extract_pdf(content: bytes) -> Optional[str]:
    try:
        from careerloop.onboarding.cv_extractor import extract_pdf_text
        return extract_pdf_text(content)
    except ImportError:
        pass
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        return None


def _extract_docx(content: bytes) -> Optional[str]:
    try:
        from careerloop.onboarding.cv_extractor import extract_docx_text
        return extract_docx_text(content)
    except ImportError:
        pass
    try:
        import docx
        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        logger.error("DOCX extraction failed: %s", e)
        return None


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "careerloop-webhook"}


# ── Webhook registration helper ────────────────────────────────────────────────

def register_webhook(public_url: str):
    """Call once to register the Telegram webhook. public_url must be HTTPS."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")
    url = f"https://api.telegram.org/bot{token}/setWebhook"
    payload = {"url": f"{public_url.rstrip('/')}/telegram/webhook"}
    r = requests.post(url, json=payload, timeout=10)
    print(r.json())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("careerloop.transport.webhook_server:app", host="0.0.0.0", port=8000, reload=False)
