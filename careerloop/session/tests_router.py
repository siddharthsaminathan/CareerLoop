import os
import shutil
import unittest
import tempfile
from typing import List, Dict, Any, Optional
from careerloop.session.states import UserState
from careerloop.session.session_store import SessionStore, Session
from careerloop.session.user_registry import UserRegistry
from careerloop.session.message_router import MessageRouter
from careerloop.transport.base import TransportAdapter, IncomingMessage

class MockTransportAdapter(TransportAdapter):
    def __init__(self):
        self.sent_texts: List[Dict[str, Any]] = []
        self.sent_buttons: List[Dict[str, Any]] = []
        self.sent_documents: List[Dict[str, Any]] = []

    def send_text(self, user_id: str, text: str) -> bool:
        self.sent_texts.append({"user_id": user_id, "text": text})
        return True

    def send_buttons(self, user_id: str, text: str, buttons: List[Dict[str, str]]) -> bool:
        self.sent_buttons.append({"user_id": user_id, "text": text, "buttons": buttons})
        return True

    def send_document(self, user_id: str, file_path: str, caption: Optional[str] = None) -> bool:
        self.sent_documents.append({"user_id": user_id, "file_path": file_path, "caption": caption})
        return True

    def parse_webhook(self, payload: Dict[str, Any]) -> Optional[IncomingMessage]:
        return None

class TestConversationRouter(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_careerloop.db")
        self.registry_path = os.path.join(self.test_dir, "user_registry.json")
        
        self.session_store = SessionStore(db_path=self.db_path)
        self.registry = UserRegistry(registry_path=self.registry_path)
        self.transport = MockTransportAdapter()
        
        self.router = MessageRouter(self.transport, self.session_store, self.registry)
        
        # Monkey patch onboarding flow to bypass actual file download/pypdf and DeepSeek API call for test stability
        self.router.onboarding._extract_pdf_text = lambda path: "Summary\nSoftware Engineer with experience. " * 5
        self.router.onboarding._structure_cv_via_llm = lambda text: "## Summary\n\nSoftware Engineer.\n\n## Experience\n\n- Dev at CRED"

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        # Clean up profiles directory created in workspace for tests if any
        # (ProfileManager paths are relative to workspace, but we avoid hardcoding so testing stays self-contained)

    def test_routing_onboarding_lifecycle(self):
        user_id = "test_user_99"
        
        # 1. Assert initial state is IDLE
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.IDLE)
        
        # 2. Trigger /start and assert waiting for CV
        incoming = IncomingMessage(user_id=user_id, text="/start")
        self.router.route(incoming)
        
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.ONBOARDING_WAITING_CV)
        self.assertIn("Welcome to CareerLoop", self.transport.sent_texts[-1]["text"])
        
        # 3. Simulate CV upload (PDF)
        # Create a dummy pdf file first
        dummy_pdf = os.path.join(self.test_dir, "test_cv.pdf")
        with open(dummy_pdf, "w") as f:
            f.write("dummy pdf content")
            
        incoming = IncomingMessage(user_id=user_id, document_path=dummy_pdf, document_mime="application/pdf")
        self.router.route(incoming)
        
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.ONBOARDING_Q1_ROLES)
        self.assertIn("What professional roles", self.transport.sent_texts[-1]["text"])

        # 4. Answer Q1: Roles
        incoming = IncomingMessage(user_id=user_id, text="Python Platform Engineer, AI PM")
        self.router.route(incoming)
        
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.ONBOARDING_Q2_CITIES)
        self.assertEqual(session.temp_profile_data["target_roles"], ["Python Platform Engineer", "AI PM"])
        self.assertIn("Which cities in India", self.transport.sent_texts[-1]["text"])

        # 5. Answer Q2: Cities
        incoming = IncomingMessage(user_id=user_id, text="Bangalore, Noida")
        self.router.route(incoming)
        
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.ONBOARDING_Q3_SALARY)
        self.assertEqual(session.temp_profile_data["locations"], ["Bangalore", "Noida"])
        self.assertIn("salary floor", self.transport.sent_texts[-1]["text"])

        # 6. Answer Q3: Salary LPA (numeric checking)
        # Check invalid input first
        incoming = IncomingMessage(user_id=user_id, text="invalid salary text")
        self.router.route(incoming)
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.ONBOARDING_Q3_SALARY) # state unchanged
        
        # Send valid answer
        incoming = IncomingMessage(user_id=user_id, text="₹25 LPA")
        self.router.route(incoming)
        
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.ONBOARDING_Q4_NOTICE)
        self.assertEqual(session.temp_profile_data["salary_floor_lakhs"], 25)
        self.assertIn("notice period in", self.transport.sent_texts[-1]["text"])

        # 7. Answer Q4: Notice period days
        incoming = IncomingMessage(user_id=user_id, text="30 days")
        self.router.route(incoming)
        
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.ONBOARDING_Q5_MODE)
        self.assertEqual(session.temp_profile_data["notice_period_days"], 30)
        self.assertIn("Select your Job Search Mode", self.transport.sent_buttons[-1]["text"])

        # 8. Answer Q5: Career search mode via callback button
        incoming = IncomingMessage(user_id=user_id, callback_data="MODE_UPGRADE")
        self.router.route(incoming)
        
        # Verify onboarding completion details
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.IDLE)
        self.assertTrue(self.registry.is_registered(user_id))
        
        mapping = self.registry.get_user_mapping(user_id)
        self.assertEqual(mapping["person_id"], "user_test_user_99")
        self.assertIn("Profile set up complete", self.transport.sent_texts[-1]["text"])

    def test_brief_triage_routing_lifecycle(self):
        user_id = "test_onboarded_user"
        
        # 1. Establish session in IDLE state
        session = Session(user_id=user_id, state=UserState.IDLE)
        self.session_store.save_session(session)
        
        # 2. User requests brief
        incoming = IncomingMessage(user_id=user_id, text="/brief")
        self.router.route(incoming)
        
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.DAILY_BRIEF_SENT)
        self.assertIn("compressed Daily Brief", self.transport.sent_texts[-1]["text"])

        # 3. User selects job "1"
        incoming = IncomingMessage(user_id=user_id, text="1")
        self.router.route(incoming)
        
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.REVIEWING_JOB)
        self.assertEqual(session.current_job_id, "deloitte")
        self.assertIn("Triage Card: Deloitte", self.transport.sent_buttons[-1]["text"])

        # 4. User clicks "Compile Tailored Pack" callback
        incoming = IncomingMessage(user_id=user_id, callback_data="ACTION_APPLY")
        self.router.route(incoming)
        
        session = self.session_store.get_session(user_id)
        # Router executes simulated compiler run and transitions to PACK_READY
        self.assertEqual(session.state, UserState.PACK_READY)
        self.assertIn("Application Pack Compiled", self.transport.sent_buttons[-1]["text"])

        # 5. User clicks "Apply Now" (PACK_APPLY_URL)
        incoming = IncomingMessage(user_id=user_id, callback_data="PACK_APPLY_URL")
        self.router.route(incoming)
        
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.AWAITING_APPLICATION_CONFIRMATION)
        self.assertIn("Recruiter DM & Apply Link", self.transport.sent_buttons[-1]["text"])

        # 6. User clicks "Confirm Submission" (CONFIRM_SUBMIT)
        incoming = IncomingMessage(user_id=user_id, callback_data="CONFIRM_SUBMIT")
        self.router.route(incoming)
        
        session = self.session_store.get_session(user_id)
        self.assertEqual(session.state, UserState.IDLE) # transitions back to IDLE
        self.assertIn("Status updated to `APPLIED`", self.transport.sent_texts[-1]["text"])

if __name__ == "__main__":
    unittest.main()
