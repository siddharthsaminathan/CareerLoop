"""Chat service — wraps the LangGraph supervisor graph (same path as the Telegram webhook).

Mirrors careerloop/transport/webhook_server.py::_route_to_supervisor, but returns a
structured payload for HTTP instead of pushing to Telegram.
"""

import logging

from careerloop_api.core.envelope import APIError
from careerloop.session.session_store import SessionStore
from careerloop.session.states import UserJourneyState

logger = logging.getLogger("careerloop_api.services.chat")


class ChatService:
    def __init__(self, db):
        self.db = db
        self.store = SessionStore(db)

    def message(self, user_id: str, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            raise APIError("Message text is required.", status_code=400, code="empty_message")

        session = self.store.get_session(user_id)

        # Onboarding users go through the onboarding flow, not the supervisor.
        if session.state == UserJourneyState.NEW_USER:
            from careerloop.onboarding.onboarding_flow import OnboardingFlow
            flow = OnboardingFlow(self.store)
            try:
                reply, _new_state = flow.handle_message(session, text)
            except Exception as e:
                logger.exception("Onboarding error for %s: %s", user_id[:12], e)
                raise APIError("Onboarding hit an issue. Your data is safe — try again.",
                               status_code=500, code="onboarding_error")
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
            from langchain_core.messages import HumanMessage
            from careerloop.session.supervisor_graph import get_supervisor_graph

            graph = get_supervisor_graph()
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
        except Exception as e:
            logger.exception("Supervisor graph error for %s: %s", user_id[:12], e)
            raise APIError("I hit an internal issue. Your data is safe — try again.",
                           status_code=500, code="graph_error")

        reply = result.get("assistant_response") or "Something went wrong. Try again."
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

    @staticmethod
    def _context(session) -> dict:
        return {
            "active_artifact_type": session.active_artifact_type,
            "active_job_id": session.active_job_id,
            "active_brief_id": session.active_brief_id,
            "active_pack_id": session.active_pack_id,
        }
