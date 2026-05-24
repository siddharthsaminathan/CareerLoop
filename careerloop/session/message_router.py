import os
from careerloop.session.session_store import SessionStore
from careerloop.session.states import UserJourneyState
from careerloop.transport.base import TransportAdapter
from careerloop.onboarding.onboarding_flow import OnboardingFlow
from careerloop.llm_chat import ChatIntentAgent

class MessageRouter:
    """
    Central dispatcher. Reads user session state and routes incoming
    messages to the correct flow (Onboarding, Triage, Interview Prep).
    """
    def __init__(self, session_store: SessionStore, transport: TransportAdapter):
        self.session_store = session_store
        self.transport = transport
        self.onboarding = OnboardingFlow(session_store)
        self.intent_agent = ChatIntentAgent()
        self.career_ops_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def handle_incoming(self, user_id: str, text: str):
        # 1. Load Session
        session = self.session_store.get_session(user_id)
        current_state = session.state

        # 2. Route based on state
        if current_state.name.startswith("ONBOARDING_") or current_state == UserJourneyState.NEW_USER:
            reply, next_state = self.onboarding.handle_message(session, text)
            
            # Save new state
            session.state = next_state
            self.session_store.save_session(session)
            
            # Send reply
            self.transport.send_text(user_id, reply)
            return

        elif current_state == UserJourneyState.PROFILE_READY:
            # Post-onboarding intent detection
            profile_data = session.temp_profile_data or {}
            intent, reply = self.intent_agent.process(text, profile_data)

            if intent == "SCAN_JOBS":
                reply = "Ready to scan. Type `/scan` to start a job search."

            self.transport.send_text(user_id, reply)
            
            return

        else:
            reply = f"I am currently in {current_state.name} mode. I heard: {text}"
            self.transport.send_text(user_id, reply)
            return
