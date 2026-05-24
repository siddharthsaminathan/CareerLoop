from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from langchain_core.messages import HumanMessage
from careerloop.session.states import UserJourneyState, normalize_user_state

@dataclass
class UserEvent:
    user_id: str
    text: str
    platform: str
    metadata: Optional[Dict[str, Any]] = None

class TransportAdapter(ABC):
    def __init__(self, supervisor_graph=None):
        self.supervisor_graph = supervisor_graph

    def _event_to_state(self, event: UserEvent) -> Dict[str, Any]:
        """
        Normalize a transport-level UserEvent into the supervisor graph state contract.
        """
        metadata = event.metadata or {}
        current_state_raw = metadata.get("current_state", UserJourneyState.NEW_USER)
        current_state = normalize_user_state(current_state_raw) or UserJourneyState.NEW_USER

        return {
            "user_id": event.user_id,
            "current_state": current_state,
            "pending_job_id": metadata.get("pending_job_id"),
            "messages": [HumanMessage(content=event.text)],
            "council_state": metadata.get("council_state"),
            "temp_profile_data": metadata.get("temp_profile_data"),
        }

    def receive(self, raw_payload: Any) -> Optional[Dict[str, Any]]:
        """Convert raw payload to UserEvent and invoke the supervisor graph."""
        event = self.parse_payload(raw_payload)
        if self.supervisor_graph and event:
            config = {"configurable": {"thread_id": event.user_id}}

            # Flow: TransportAdapter -> UserEvent -> ConversationState -> SupervisorGraph
            graph_input = self._event_to_state(event)
            response = self.supervisor_graph.invoke(graph_input, config=config)

            if response and hasattr(response, "get"):
                assistant_response = response.get("assistant_response")
                if assistant_response:
                    self.send_text(event.user_id, str(assistant_response))
                    return response

                # CRITICAL: no assistant_response — graph node returned incomplete state.
                # NEVER echo the user's message back. Log and return safe error.
                import logging
                _log = logging.getLogger("careerloop.transport.base")
                _log.critical(
                    "supervisor_graph returned no assistant_response. "
                    "state=%s user_id=%s",
                    response.get("current_state"),
                    event.user_id,
                )
                self.send_text(
                    event.user_id,
                    "I hit an internal routing issue. Your data is safe — try again or type /help.",
                )
                return response

            # Backward-compatible fallback: message list — only used when
            # assistant_response is absent but messages were explicitly set by the graph.
            messages = response.get("messages", [])
            if messages:
                last_msg = messages[-1]
                content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                self.send_text(event.user_id, content)
            return response
        return None

    @abstractmethod
    def parse_payload(self, raw_payload: Any) -> Optional[UserEvent]:
        """Convert the platform-specific raw payload into a standard UserEvent."""
        pass

    @abstractmethod
    def send_text(self, user_id: str, text: str) -> bool:
        pass

    @abstractmethod
    def request_input(self, user_id: str, prompt_text: str = "") -> str:
        pass
