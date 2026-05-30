import os
import sys
import time
import json
from typing import Tuple
from unittest.mock import MagicMock

# Insert careerloop root into python path
sys.path.insert(0, "/Users/siddharthsaminathan/projects/CareerLoop")

from careerloop.session.states import UserJourneyState
from careerloop.session.session_store import Session, SessionStore
from careerloop.onboarding.onboarding_flow import (
    OnboardingFlow, STEP_IDLE, STEP_WAITING_CV, STEP_CONFIRMING,
    STEP_COLLECTING, STEP_IDENTIFYING, STEP_PROFILE_CONFIRMATION
)
from careerloop.sources.identity_provider import ProfileCandidate

class TraceStore(SessionStore):
    """Trace SessionStore that records SQL mutations and updates."""
    def __init__(self):
        super().__init__()
        self._sessions = {}
        self._users = {}
        self.mutations = []

    def get_or_create_user(self, telegram_chat_id: int, first_name: str = "", username: str = "") -> str:
        uid = f"user_{telegram_chat_id}"
        if uid not in self._users:
            self._users[uid] = {
                "id": uid,
                "email": f"user_{telegram_chat_id}@careerloop.internal",
                "full_name": first_name or "User",
                "onboarding_complete": False,
                "onboarding_status": "new",
            }
            self.mutations.append({
                "table": "careerloop.users",
                "column": "id, email, full_name, onboarding_status",
                "old": "None",
                "new": f"{uid}, email, {first_name}, 'new'"
            })
        return uid

    def get_session(self, user_id: str) -> Session:
        if user_id not in self._sessions:
            session = Session(user_id=user_id, state=UserJourneyState.NEW_USER, onboarding_step=0)
            self._sessions[user_id] = session
            return session
        return self._sessions[user_id]

    def save_session(self, session: Session) -> bool:
        user_id = session.user_id
        old_session = self._sessions.get(user_id)
        old_step = old_session.onboarding_step if old_session else 0
        old_state = old_session.state if old_session else UserJourneyState.NEW_USER
        
        self._sessions[user_id] = session
        
        self.mutations.append({
            "table": "careerloop.sessions",
            "column": "state, onboarding_step",
            "old": f"{old_state.value if hasattr(old_state, 'value') else old_state}, step={old_step}",
            "new": f"{session.state.value if hasattr(session.state, 'value') else session.state}, step={session.onboarding_step}"
        })
        return True

    def save_message(self, user_id: str, conversation_id: str, role: str, content: str, **kwargs) -> bool:
        self.mutations.append({
            "table": "careerloop.messages",
            "column": "conversation_id, role, content",
            "old": "None",
            "new": f"{conversation_id}, {role}, '{content[:60]}...'"
        })
        return True

    def write_profile(self, user_id: str, profile_data: dict):
        if user_id in self._users:
            self._users[user_id].update({
                "master_cv_markdown": profile_data.get("cv_content"),
                "target_roles": profile_data.get("target_roles"),
                "target_cities": profile_data.get("target_cities"),
                "salary_expectations": profile_data.get("salary_expectations"),
                "notice_period": profile_data.get("notice_period"),
                "onboarding_complete": True,
            })
            self.mutations.append({
                "table": "careerloop.users",
                "column": "master_cv_markdown, onboarding_complete",
                "old": "onboarding_complete=False",
                "new": "master_cv_markdown stashed, onboarding_complete=TRUE"
            })

# ── Mock DeepSeek LLM for deterministic simulation outputs ─────────────────────

def mock_extract(self_agent, text: str) -> dict:
    text_lower = text.lower()
    if "arjun" in text_lower:
        return {
            "target_roles": "Senior ML Engineer",
            "target_cities": "Bangalore",
            "salary_expectations": "45 LPA",
            "notice_period": "30 days",
            "current_ctc": "35 LPA",
        }
    elif "priya" in text_lower:
        return {
            "target_roles": "Product Manager",
            "target_cities": "Chennai",
            "salary_expectations": "35 LPA",
            "notice_period": "60 days",
            "current_ctc": "25 LPA",
        }
    elif "rahul" in text_lower:
        return {
            "target_roles": "MLOps Engineer",
            "target_cities": "Hyderabad",
            "salary_expectations": "28 LPA",
            "notice_period": "Immediate",
            "current_ctc": "20 LPA",
        }
    elif "ananya" in text_lower:
        return {
            "target_roles": "Data Scientist",
            "target_cities": "Bangalore",
            "salary_expectations": "22 LPA",
            "notice_period": "90 days",
            "current_ctc": "15 LPA",
        }
    elif "karthik" in text_lower:
        return {
            "target_roles": "AI Engineer",
            "target_cities": "Pune",
            "salary_expectations": "55 LPA",
            "notice_period": "45 days",
            "current_ctc": "40 LPA",
        }
    elif "meera" in text_lower:
        return {
            "target_roles": "Growth Product Manager",
            "target_cities": "Mumbai",
            "salary_expectations": "40 LPA",
            "notice_period": "30 days",
            "current_ctc": "30 LPA",
        }
    return {}

from careerloop.llm_chat import CVExtractionAgent
CVExtractionAgent.extract = mock_extract

def run_simulation(user_def):
    name = user_def["name"]
    chat_id = user_def["chat_id"]
    flow_def = user_def["flow"]
    
    print(f"\n======================================================================")
    print(f"SIMULATING USER: {name} (Flow: {user_def['flow_name']})")
    print(f"======================================================================")
    
    store = TraceStore()
    flow = OnboardingFlow(store)
    
    # Setup stubs for LinkedIn lookups
    if user_def.get("linkedin_valid"):
        cand = ProfileCandidate(
            full_name=name,
            headline=f"Senior Staff Engineer at Razorpay",
            current_company="Razorpay",
            location=user_def.get("location", "Bangalore"),
            linkedin_url=f"https://linkedin.com/in/{name.lower().replace(' ', '')}"
        )
        flow.identity.find_by_name = MagicMock(return_value=cand)
    elif user_def.get("linkedin_mismatch"):
        cand = ProfileCandidate(
            full_name="Ananya Krishnan (Finance Consultant)",
            headline="Finance Consultant at ICICI Bank",
            current_company="ICICI Bank",
            location="Chennai",
            linkedin_url="https://linkedin.com/in/ananyakrishnan-finance"
        )
        flow.identity.find_by_name = MagicMock(return_value=cand)
    else:
        flow.identity.find_by_name = MagicMock(return_value=None)

    # Patch OnboardingFlow._commit_profile_to_db to write to store directly
    OnboardingFlow._commit_profile_to_db = lambda self_flow, uid, data: store.write_profile(uid, data)
    OnboardingFlow._seed_welcome_brief = lambda self_flow, uid: None

    uid = store.get_or_create_user(chat_id, first_name=name, username=name.lower().replace(' ', ''))
    session = store.get_session(uid)
    conv_id = f"conv_{chat_id}"
    
    # Store conversation ID in temp_profile_data to mirror ChatService
    session.temp_profile_data = {"_active_conversation_id": conv_id}
    store.save_session(session)
    
    turn_num = 1
    for msg in flow_def:
        state_before = session.state.value if hasattr(session.state, 'value') else str(session.state)
        step_before = session.onboarding_step
        
        print(f"\n--- TURN {turn_num} ---")
        print(f"STATE BEFORE: conv_id={conv_id}, session.state={state_before}, onboarding_step={step_before}")
        print(f"USER MESSAGE: \"{msg}\"")
        
        # Clear mutations list to track only this turn
        store.mutations.clear()
        
        # Router Decision (Simulates ChatService)
        router_decision = ""
        if session.state == UserJourneyState.NEW_USER:
            router_decision = "ChatService: NEW_USER -> OnboardingFlow"
        else:
            router_decision = "ChatService: PROFILE_READY -> LangGraph Supervisor"
            
        print(f"ROUTER DECISION: {router_decision}")
        
        # Handler selected inside OnboardingFlow
        handler_selected = ""
        if session.onboarding_step == STEP_IDLE:
            handler_selected = "OnboardingFlow: _handle_idle"
        elif session.onboarding_step == STEP_WAITING_CV:
            handler_selected = "OnboardingFlow: _handle_waiting_cv"
        elif session.onboarding_step == STEP_CONFIRMING:
            handler_selected = "OnboardingFlow: _handle_confirming"
        elif session.onboarding_step == STEP_COLLECTING:
            handler_selected = "OnboardingFlow: _handle_collecting"
        elif session.onboarding_step == STEP_IDENTIFYING:
            handler_selected = "OnboardingFlow: _handle_identifying"
        elif session.onboarding_step == STEP_PROFILE_CONFIRMATION:
            handler_selected = "OnboardingFlow: _handle_profile_confirmation"
            
        print(f"HANDLER SELECTED: {handler_selected}")
        
        # Process message
        try:
            reply, state = flow.handle_message(session, msg)
        except Exception as e:
            reply = f"Error in Onboarding Engine execution: {e}"
            print(f"CRASH: {e}")
            break
            
        state_after = session.state.value if hasattr(session.state, 'value') else str(session.state)
        step_after = session.onboarding_step
        
        print(f"ASSISTANT RESPONSE:\n{reply}")
        print(f"STATE AFTER: conv_id={conv_id}, session.state={state_after}, onboarding_step={step_after}")
        
        print(f"DB MUTATIONS:")
        if store.mutations:
            for m in store.mutations:
                print(f"  * Table: {m['table']}, Column: {m['column']}, Old: {m['old']}, New: {m['new']}")
        else:
            print("  * None")
            
        turn_num += 1
        
    print(f"\nFinal Journey Status: {'✅ SUCCESS - PROFILE_READY REACHED' if session.state == UserJourneyState.PROFILE_READY else '❌ FAILED - TRAPPED IN STEP ' + str(session.onboarding_step)}")

# Definition of the 6 Users & Flows for the Patched Codebase

USERS = [
    {
        "name": "Arjun Raman",
        "chat_id": 1001,
        "flow_name": "Flow A (LinkedIn Success Path)",
        "linkedin_valid": True,
        "location": "Bangalore",
        "flow": [
            "hello",                   # Greet -> Transition to IDENTIFYING (10)
            "Arjun Raman",             # Send Name -> Transition to CONFIRMATION (11)
            "YES",                     # Confirm LinkedIn -> Transition to WAITING_CV (1)
            "Arjun Raman\nSenior ML Engineer | Bangalore\narjun@email.com\nRazorpay Senior ML Engineer 2022-present\nAmazon ML Engineer 2019-2022\nExpected salary: 45 LPA | Notice: 30 days", 
            "YES"                      # Confirm extraction summary -> PROFILE_READY
        ]
    },
    {
        "name": "Priya Menon",
        "chat_id": 1002,
        "flow_name": "Flow B (Frustration wtf Recovery and Name Collection Success)",
        "linkedin_valid": False,
        "flow": [
            "hello",                   # Greet -> Transition to IDENTIFYING (10)
            "wtf",                     # User sends "wtf" inside IDENTIFYING -> Filtered! Step remains 10.
            "Priya Menon",             # User enters full name -> Searches LinkedIn (fails) -> Transition to WAITING_CV (1)
            "Priya Menon\nProduct Manager | Chennai\npriya@email.com\nFreshworks PM 2021-Now\nZoho APM 2019-2021\nExpected salary: 35 LPA | Notice: 60 days", # Paste CV
            "YES"
        ]
    },
    {
        "name": "Rahul Sharma",
        "chat_id": 1003,
        "flow_name": "Flow D (Direct Resume Skip-Name Path)",
        "linkedin_valid": True,
        "flow": [
            "hello",                   # Greet -> Transition to IDENTIFYING (10)
            # Send CV directly (>= 80 characters) inside IDENTIFYING -> Directly processes CV! Transition to CONFIRMING (2)
            "Rahul Sharma\nMLOps Engineer | Hyderabad\nrahul@email.com\nVertex AI, Kubeflow, Terraform, Docker, GCP\nExpected salary: 28 LPA | Notice: Immediate",
            "YES"
        ]
    },
    {
        "name": "Ananya Krishnan",
        "chat_id": 1004,
        "flow_name": "Flow C (LinkedIn Profile Rejection Fallback)",
        "linkedin_mismatch": True,
        "flow": [
            "hello",                   # Greet -> Transition to IDENTIFYING (10)
            "Ananya Krishnan",         # Send Name -> Matches wrong candidate -> Transition to PROFILE_CONFIRMATION (11)
            "NO",                      # Rejects matching -> Transition to WAITING_CV (1)
            # Paste manual CV (>= 80 characters)
            "Ananya Krishnan\nData Scientist | Bangalore\nananya@email.com\nPython, Pandas, NLP, Deep Learning\nExpected salary: 22 LPA | Notice: 90 days",
            "YES"
        ]
    },
    {
        "name": "Karthik Iyer",
        "chat_id": 1005,
        "flow_name": "Flow E (Short Resume Retry and Reset Recovery)",
        "linkedin_valid": False,
        "flow": [
            "hello",                   # Greet -> Transition to IDENTIFYING (10)
            "Karthik Iyer",            # Name -> Lookup fails -> Transition to WAITING_CV (1)
            "wtf",                     # wtf inside WAITING_CV -> Conversational escape hatch! Step remains 1
            "restart",                 # Triggers reset -> Step resets to 0 (IDLE)
            "Karthik Iyer\nAI Engineer | Pune\nkarthik@email.com\nLangGraph, FastAPI, RAG, Postgres, Agents\nExpected salary: 55 LPA | Notice: 45 days", # Direct CV upload
            "YES"
        ]
    },
    {
        "name": "Meera Nair",
        "chat_id": 1006,
        "flow_name": "Flow A (LinkedIn Success Path)",
        "linkedin_valid": True,
        "location": "Mumbai",
        "flow": [
            "hello",
            "Meera Nair",
            "YES",
            "Meera Nair\nGrowth Product Manager | Mumbai\nmeera@email.com\nGrowth, Product Analytics, Amplitude, SQL, Experimentation\nExpected salary: 40 LPA | Notice: 30 days",
            "YES"
        ]
    }
]

def main():
    print("--- CAREERLOOP ONBOARDING WAR GAME RUNNER ---")
    print("Executing simulations against PATCHED codebase...\n")
    
    for u in USERS:
        run_simulation(u)

if __name__ == "__main__":
    main()
