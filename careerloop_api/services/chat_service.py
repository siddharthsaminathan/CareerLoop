"""Chat service — wraps the LangGraph supervisor graph (same path as the Telegram webhook).

Mirrors careerloop/transport/webhook_server.py::_route_to_supervisor, but returns a
structured payload for HTTP instead of pushing to Telegram.
"""

import logging
import threading
import uuid

from careerloop_api.core.envelope import APIError
from careerloop.session.session_store import SessionStore
from careerloop.session.states import UserJourneyState

logger = logging.getLogger("careerloop_api.services.chat")

_CHAT_TIMEOUT = 120  # seconds — hard limit for any single chat turn


def _run_with_timeout(fn, timeout=_CHAT_TIMEOUT, label="Chat turn"):
    """Run fn() in a daemon thread with a hard timeout.

    If the LLM call hangs (DeepSeek slow, DB pool exhausted), we don't leave
    the HTTP request hanging forever — the user gets a clean error after 120s.
    """
    result = [None]
    error = [None]
    done = threading.Event()

    def worker():
        try:
            result[0] = fn()
        except Exception as e:
            error[0] = e
        finally:
            done.set()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    ok = done.wait(timeout=timeout)
    if not ok:
        raise TimeoutError(f"{label} timed out after {timeout}s — LLM or DB hang.")
    if error[0]:
        raise error[0]
    return result[0]


class ChatService:
    def __init__(self, db):
        self.db = db
        self.store = SessionStore(db)

    def message(self, user_id: str, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            raise APIError("Message text is required.", status_code=400, code="empty_message")

        session = self.store.get_session(user_id)

        # P0-01: Persist the user's message
        conv_id = self._ensure_conversation(user_id)
        self.store.save_message(
            user_id=user_id,
            conversation_id=conv_id,
            role="user",
            content=text,
        )

        # Onboarding users go through the onboarding flow, not the supervisor.
        if session.state == UserJourneyState.NEW_USER:
            from careerloop.onboarding.onboarding_flow import OnboardingFlow
            flow = OnboardingFlow(self.store)
            try:
                # P0-03: Wrap onboarding with a hard timeout to prevent 330-minute hangs
                reply, _new_state = _run_with_timeout(
                    lambda: flow.handle_message(session, text),
                    timeout=_CHAT_TIMEOUT,
                    label="Onboarding",
                )
            except TimeoutError:
                logger.error("Onboarding timeout after %ss for %s", _CHAT_TIMEOUT, user_id[:12])
                raise APIError(
                    "CV processing timed out. Please try again or paste a shorter CV.",
                    status_code=504, code="onboarding_timeout",
                )
            except Exception as e:
                logger.exception("Onboarding error for %s: %s", user_id[:12], e)
                raise APIError("Onboarding hit an issue. Your data is safe — try again.",
                               status_code=500, code="onboarding_error")

            # P0-01: Persist the assistant's onboarding reply
            self.store.save_message(
                user_id=user_id,
                conversation_id=conv_id,
                role="assistant",
                content=reply,
            )

            # Surface the "Is this you?" LinkedIn identity card if the flow staged one.
            cards = []
            response_type = "text"
            updated = self.store.get_session(user_id)
            identity_card = (updated.temp_profile_data or {}).get("_identity_card")
            if identity_card:
                cards = [{"type": "identity_confirmation", **identity_card}]
                response_type = "card"
            return {
                "message": reply,
                "response_type": response_type,
                "cards": cards,
                "actions": [],
                "active_context": self._context(updated),
                "state": updated.state.value if hasattr(updated.state, "value") else str(updated.state),
            }

        # PROFILE_READY+ → supervisor graph.
        try:
            from langchain_core.messages import HumanMessage, AIMessage
            from careerloop.session.supervisor_graph import get_supervisor_graph
            from careerloop.memory.checkpointer import get_checkpointer

            # P0-02: Wire PostgresSaver checkpointer so conversation history survives
            # across API calls. Falls back to MemorySaver if DATABASE_URL is not set.
            checkpointer = get_checkpointer()
            graph = get_supervisor_graph(checkpointer=checkpointer)

            # P1-02: Load previous conversation history from DB and inject into
            # graph's messages array so the LLM has full context.
            history_messages = self._load_conversation_history(user_id, conv_id)

            # Build the message list: history (from DB) + current message
            all_messages = history_messages + [HumanMessage(content=text)]
            graph_input = {
                "user_id": user_id,
                "current_state": session.state,
                "messages": all_messages,
                "temp_profile_data": session.temp_profile_data or {},
                "artifact_context": {
                    "active_artifact_type": session.active_artifact_type,
                    "active_artifact_id": session.active_artifact_id,
                    "active_job_id": session.active_job_id,
                    "active_brief_id": session.active_brief_id,
                },
            }
            config = {"configurable": {"thread_id": user_id}}
            # Run with a hard 120s timeout — never hang forever
            result = _run_with_timeout(
                lambda: graph.invoke(graph_input, config=config),
                timeout=_CHAT_TIMEOUT,
                label="Chat turn",
            )

            # P1-03: Persist artifact context updates from the graph result back to
            # the DB session so active_context survives between turns.
            result_context = result.get("artifact_context")
            if result_context:
                try:
                    fresh = self.store.get_session(user_id)
                    dirty = False
                    for field in (
                        "active_artifact_type", "active_artifact_id",
                        "active_job_id", "active_brief_id", "active_pack_id",
                    ):
                        new_val = result_context.get(field)
                        if new_val is not None and getattr(fresh, field, None) != new_val:
                            setattr(fresh, field, new_val)
                            dirty = True
                    if dirty:
                        self.store.save_session(fresh)
                except Exception:
                    logger.warning(
                        "Failed to persist artifact context for %s", user_id[:12],
                        exc_info=True,
                    )
        except TimeoutError:
            logger.error("Chat turn TIMEOUT after %ss for user %s", _CHAT_TIMEOUT, user_id[:12])
            raise APIError(
                "The AI is taking too long to respond. Please try again in a moment.",
                status_code=504, code="chat_timeout",
            )
        except Exception as e:
            logger.exception("Supervisor graph error for %s: %s", user_id[:12], e)
            raise APIError("I hit an internal issue. Your data is safe — try again.",
                           status_code=500, code="graph_error")

        reply = result.get("assistant_response") or "Something went wrong. Try again."

        # P0-01: Persist the assistant's reply
        self.store.save_message(
            user_id=user_id,
            conversation_id=conv_id,
            role="assistant",
            content=reply,
            action_type=result.get("action_taken", {}).get("action_type") if hasattr(result.get("action_taken", {}), "get") else None,
        )

        # Re-read the session for the updated active context after the turn.
        updated = self.store.get_session(user_id)
        return {
            "message": reply,
            "response_type": result.get("response_type", "text"),
            "cards": result.get("cards", []),
            "actions": result.get("actions", []),
            "active_context": self._context(updated),
            "state": updated.state.value if hasattr(updated.state, "value") else str(updated.state),
        }

    def _ensure_conversation(self, user_id: str) -> str:
        """Get or create an active conversation for this user.

        Uses a single conversation per user session (stored on the session object).
        Creates one if it doesn't exist yet.
        """
        session = self.store.get_session(user_id)
        # Reuse existing conversation_id from session if available
        existing = (session.temp_profile_data or {}).get("_active_conversation_id") if session.temp_profile_data else None
        if existing:
            return existing

        conv_id = str(uuid.uuid4())
        # Persist the conversation row
        self.store.save_conversation(user_id=user_id, conversation_id=conv_id)
        # Stash on session for reuse
        tp = session.temp_profile_data or {}
        tp["_active_conversation_id"] = conv_id
        session.temp_profile_data = tp
        self.store.save_session(session)
        return conv_id

    def _load_conversation_history(self, user_id: str, conversation_id: str) -> list:
        """Load previous messages from careerloop.messages for LLM context.

        Returns a list of HumanMessage/AIMessage objects suitable for the LangGraph
        messages array. Limits to last 20 messages to avoid context overflow.
        """
        from langchain_core.messages import HumanMessage, AIMessage
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT role, content FROM careerloop.messages "
                        "WHERE conversation_id = %s AND user_id = %s "
                        "ORDER BY created_at ASC LIMIT 20",
                        (conversation_id, user_id),
                    )
                    rows = cur.fetchall()
            messages = []
            for row in (rows or []):
                role = row.get("role", "")
                content = row.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
            return messages
        except Exception:
            logger.debug("No conversation history loaded for %s", user_id[:12])
            return []

    @staticmethod
    def _context(session) -> dict:
        return {
            "active_artifact_type": session.active_artifact_type,
            "active_job_id": session.active_job_id,
            "active_brief_id": session.active_brief_id,
            "active_pack_id": session.active_pack_id,
        }
