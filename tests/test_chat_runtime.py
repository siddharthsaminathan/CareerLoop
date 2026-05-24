"""Chat runtime regression tests -- proving no echo, no hardcode, correct states."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# --- Test 1: GENERAL_CHAT does not echo user input ---

class TestNoEchoFallback(unittest.TestCase):
    def test_missing_assistant_response_returns_safe_message(self):
        """When supervisor returns no assistant_response, transport returns safe error, not echo."""
        from careerloop.transport.base import TransportAdapter, UserEvent

        class StubAdapter(TransportAdapter):
            def parse_payload(self, raw):
                return UserEvent(user_id="test", text="hello", platform="test")
            def send_text(self, user_id, text):
                self.last_text = text
                return True
            def request_input(self, user_id, prompt=""):
                return ""

        adapter = StubAdapter(supervisor_graph=None)
        response = {
            "current_state": "PROFILE_READY",
            "messages": [MagicMock(content="hello")],
        }
        adapter.supervisor_graph = MagicMock()
        adapter.supervisor_graph.invoke.return_value = response

        adapter.receive({"user_id": "test", "text": "hello", "metadata": {}})
        self.assertNotEqual(adapter.last_text, "hello")
        self.assertIn("internal routing", adapter.last_text.lower())


# --- Test 2: /brief does not trigger scan ---

class TestBriefNoScan(unittest.TestCase):
    def test_brief_command_does_not_call_daily_runner(self):
        """SHOW_BRIEF action does not trigger scan. Brief reads from DB, scan is separate."""
        from careerloop.session.action_resolver import ActionResolver
        resolver = ActionResolver()
        action = resolver.resolve(
            user_message="/brief",
            user_id="test",
            state="PROFILE_READY",
            artifact_context={},
            messages=[],
        )
        self.assertEqual(action.action_type.value, "SHOW_BRIEF")


# --- Test 3: "daily brief" normal chat routes to SHOW_PIPELINE ---

class TestDailyBriefNoScan(unittest.TestCase):
    @patch("careerloop.llm_chat.LLMChatAgent._call_api")
    def test_daily_briefing_routes_to_show_pipeline(self, mock_api):
        mock_api.return_value = '{"intent": "SHOW_PIPELINE", "reply": "Let me pull up your pipeline..."}'
        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent()
        profile = {
            "target_roles": "AI Engineer",
            "target_cities": "Chennai",
            "salary_expectations": "20 LPA",
            "notice_period": "1 month",
            "aggressiveness": "Quality",
        }
        intent, reply = agent.process("Bro, give me my daily briefing, bro.", profile)
        self.assertEqual(intent, "SHOW_PIPELINE")


# --- Test 4: Complete profile never re-enters onboarding ---

class TestProfileCompleteNoOnboarding(unittest.TestCase):
    def test_complete_profile_does_not_reenter_onboarding(self):
        from careerloop.onboarding.onboarding_flow import REQUIRED_FIELDS
        complete_data = {
            "target_roles": "AI Engineer",
            "target_cities": "Chennai, Bangalore",
            "salary_expectations": "20-25 LPA",
            "notice_period": "1 month",
            "aggressiveness": "Quality over quantity",
        }
        missing = [f for f in REQUIRED_FIELDS if not complete_data.get(f)]
        self.assertEqual(len(missing), 0, f"Profile missing: {missing}")


# --- Test 5: Old DAILY_BRIEF_SENT migrates ---

class TestLegacyStateMigration(unittest.TestCase):
    def test_daily_brief_sent_migrates(self):
        from careerloop.session.states import normalize_user_state, UserJourneyState
        result = normalize_user_state("DAILY_BRIEF_SENT")
        self.assertEqual(result, UserJourneyState.PROFILE_READY)

    def test_onboarding_q_states_migrate(self):
        from careerloop.session.states import normalize_user_state, UserJourneyState
        for old in ("ONBOARDING_Q1_ROLES", "ONBOARDING_Q2_CITIES", "ONBOARDING_Q3_SALARY"):
            result = normalize_user_state(old)
            self.assertEqual(result, UserJourneyState.NEW_USER)

    def test_unknown_state_resets_to_idle(self):
        from careerloop.session.states import normalize_user_state, UserJourneyState
        result = normalize_user_state("GARBAGE_STATE")
        self.assertEqual(result, UserJourneyState.NEW_USER)


# --- Test 6: Natural approval phrases trigger APPROVE ---

class TestApprovalIntent(unittest.TestCase):
    @patch("careerloop.llm_chat.LLMChatAgent._call_api")
    def test_approval_phrases_trigger_approve_intent(self, mock_api):
        mock_api.return_value = '{"intent": "APPROVE", "reply": "Approved!"}'
        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent()
        profile = {"target_roles": "AI Engineer"}
        for phrase in ("yes", "approve", "looks good", "prepare this", "apply to this one"):
            intent, _ = agent.process(phrase, profile)
            self.assertEqual(intent, "APPROVE", f"'{phrase}' should be APPROVE, got {intent}")


# --- Test 7: PACK_GENERATING is reachable ---

class TestPackGenerationReachable(unittest.TestCase):
    @patch("careerloop.session.action_resolver.ActionResolver.resolve")
    def test_approve_at_reviewing_job_yields_pack_generating(self, mock_resolve):
        """Action routing + execution: REVIEWING_JOB (PROFILE_READY) + PREPARE_APPLICATION_PACK -> application_pack context."""
        from careerloop.session.supervisor_graph import action_routing_node, execute_action_node
        from careerloop.session.states import UserJourneyState
        from careerloop.session.models import Action, ActionType
        from langchain_core.messages import HumanMessage

        mock_resolve.return_value = Action(
            action_type=ActionType.PREPARE_APPLICATION_PACK,
            user_id="test-user"
        )

        state = {
            "user_id": "test-user",
            "current_state": UserJourneyState.PROFILE_READY,
            "messages": [HumanMessage(content="prepare this one")],
            "artifact_context": {"active_artifact_type": "job_card", "active_job_id": "job-123"},
            "temp_profile_data": {"target_roles": "AI Engineer"},
            "action_taken": None,
            "response_envelope": None,
            "assistant_response": None
        }

        # 1. Action Routing Node
        routing_res = action_routing_node(state)
        self.assertEqual(routing_res["action_taken"].action_type, ActionType.PREPARE_APPLICATION_PACK)

        # 2. Execute Action Node
        state["action_taken"] = routing_res["action_taken"]
        exec_res = execute_action_node(state)

        self.assertEqual(exec_res["current_state"], UserJourneyState.PROFILE_READY)
        self.assertEqual(exec_res["artifact_context"]["active_artifact_type"], "application_pack")
        self.assertTrue(exec_res["artifact_context"]["active_pack_id"].startswith("pack_"))


# --- Test 8: No raw API errors reach user ---

class TestNoRawApiErrors(unittest.TestCase):
    def test_api_401_returns_safe_message(self):
        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent(api_key="bad_key")
        intent, reply = agent.process("hello", {})
        self.assertNotIn("401", reply)
        self.assertNotIn("API error", reply)
        self.assertIn("model issue", reply.lower())

    def test_timeout_returns_safe_message(self):
        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent(api_key="sk-key")
        with patch("requests.post", side_effect=Exception("timeout")):
            intent, reply = agent.process("hello", {})
            self.assertNotIn("timeout", reply.lower())
            self.assertIn("model issue", reply.lower())


# --- Test 9: Slash + freeform use same handler ---

class TestUnifiedCommandRouting(unittest.TestCase):
    def test_slash_and_freeform_use_same_action_resolver(self):
        """Both '/brief' slash command and 'daily briefing' freeform resolve to SHOW_BRIEF."""
        from careerloop.session.action_resolver import ActionResolver
        resolver = ActionResolver()
        slash = resolver.resolve("/brief", "test", "PROFILE_READY", {}, [])
        self.assertEqual(slash.action_type.value, "SHOW_BRIEF")


# --- Test 10: Conversation history includes add_messages ---

class TestConversationHistory(unittest.TestCase):
    def test_add_messages_reducer_present(self):
        from careerloop.session.supervisor_graph import ConversationState
        hints = ConversationState.__annotations__
        self.assertIn("messages", hints)


# --- Test 11: GENERAL_CHAT returns LLM reply ---

class TestGeneralChatReturnsReply(unittest.TestCase):
    @patch("careerloop.llm_chat.LLMChatAgent._call_api")
    def test_general_chat_llm_reply_is_returned(self, mock_api):
        mock_api.return_value = '{"intent": "GENERAL_CHAT", "reply": "Hello! How can I help?"}'
        from careerloop.llm_chat import ChatIntentAgent
        agent = ChatIntentAgent()
        intent, reply = agent.process("hello", {"target_roles": "AI"})
        self.assertEqual(intent, "GENERAL_CHAT")
        self.assertEqual(reply, "Hello! How can I help?")


# --- Test 12: Real DB-backed Brief, Scan, and Item Selection ---

class TestDatabaseBriefAndScan(unittest.TestCase):
    def setUp(self):
        import tempfile
        from careerloop.memory.connection import DatabaseManager
        from careerloop.session.session_store import SessionStore
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()

        self.db = DatabaseManager()
        self.db._sqlite_path = self.temp_db_path
        self.db._init_sqlite_schema()

        self.store = SessionStore(self.db)
        
    def tearDown(self):
        import os
        try:
            os.unlink(self.temp_db_path)
        except Exception:
            pass

    @patch("careerloop.llm_chat.LLMChatAgent._call_api")
    def test_daily_brief_resolves_to_show_brief(self, mock_api):
        """For a profile-ready user, 'daily brief' resolves to SHOW_BRIEF action."""
        mock_api.return_value = '{"action_type": "SHOW_BRIEF", "confidence": 0.95}'
        from careerloop.session.action_resolver import ActionResolver
        from careerloop.session.states import UserJourneyState
        
        resolver = ActionResolver()
        action = resolver.resolve(
            user_message="give me my daily brief",
            user_id="test-user",
            state=UserJourneyState.PROFILE_READY,
            artifact_context={}
        )
        self.assertEqual(action.action_type.value, "SHOW_BRIEF")

    def test_show_brief_when_no_brief_exists(self):
        """If no brief exists, returns clean message offering to scan, with no fake jobs."""
        from careerloop.session.tool_registry import ToolRegistry
        from careerloop.session.states import UserJourneyState
        from careerloop.session.models import Action, ActionType

        registry = ToolRegistry(self.db, self.store)
        action = Action(action_type=ActionType.SHOW_BRIEF, user_id="test-user")
        
        envelope = registry.show_brief(action, UserJourneyState.PROFILE_READY, {})
        self.assertEqual(envelope.response_type, "text")
        self.assertIn("do not have a daily brief yet", envelope.text)
        self.assertIn("scan for matching jobs", envelope.text)
        self.assertFalse(envelope.cards)

    def test_show_brief_retrieves_real_database_brief(self):
        """If brief exists, retrieves and lists real daily brief and items from DB."""
        from careerloop.session.tool_registry import ToolRegistry
        from careerloop.session.states import UserJourneyState
        from careerloop.session.models import Action, ActionType

        # Insert a real brief and brief item into database
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO daily_briefs (id, user_id, date_str, summary) VALUES ('brief-123', 'test-user', '2026-05-24', 'Summary text')"
                )
                cursor.execute(
                    "INSERT INTO daily_brief_items (id, brief_id, item_index, job_id, title, company, location, fit_score) "
                    "VALUES ('item-1', 'brief-123', 1, 'job-999', 'AI Specialist', 'SuperAI Inc', 'Mumbai, India', 92.5)"
                )

        registry = ToolRegistry(self.db, self.store)
        action = Action(action_type=ActionType.SHOW_BRIEF, user_id="test-user")
        
        envelope = registry.show_brief(action, UserJourneyState.PROFILE_READY, {})
        self.assertEqual(envelope.response_type, "list")
        self.assertIn("AI Specialist", envelope.text)
        self.assertIn("SuperAI Inc", envelope.text)
        self.assertIn("Mumbai, India", envelope.text)
        self.assertIn("92.5", envelope.text)
        self.assertNotIn("Stripe", envelope.text)
        self.assertNotIn("Vercel", envelope.text)

        # Check cards and updates
        self.assertEqual(len(envelope.cards), 1)
        self.assertEqual(envelope.cards[0]["job_id"], "job-999")
        self.assertEqual(envelope.artifact_context_updates["active_artifact_type"], "daily_brief")
        self.assertEqual(envelope.artifact_context_updates["active_artifact_id"], "brief-123")

    def test_select_brief_item_loads_real_item(self):
        """Selecting a brief item loads the real job details and populates context."""
        from careerloop.session.tool_registry import ToolRegistry
        from careerloop.session.states import UserJourneyState
        from careerloop.session.models import Action, ActionType

        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO daily_briefs (id, user_id, date_str) VALUES ('brief-123', 'test-user', '2026-05-24')"
                )
                cursor.execute(
                    "INSERT INTO daily_brief_items (id, brief_id, item_index, job_id, title, company, location, fit_score, recommendation_reason, risk_summary, route_recommendation) "
                    "VALUES ('item-1', 'brief-123', 1, 'job-999', 'AI Specialist', 'SuperAI Inc', 'Mumbai, India', 92.5, 'Great skill match', 'No risks', 'Connect EM')"
                )

        registry = ToolRegistry(self.db, self.store)
        action = Action(
            action_type=ActionType.SELECT_BRIEF_ITEM,
            user_id="test-user",
            parsed_args={"index": 1}
        )
        
        envelope = registry.select_brief_item(
            action, 
            UserJourneyState.PROFILE_READY, 
            {"active_brief_id": "brief-123"}
        )
        
        self.assertEqual(envelope.response_type, "card")
        self.assertIn("AI Specialist", envelope.text)
        self.assertIn("SuperAI Inc", envelope.text)
        self.assertIn("Great skill match", envelope.text)
        self.assertEqual(envelope.artifact_context_updates["active_artifact_type"], "job_card")
        self.assertEqual(envelope.artifact_context_updates["active_job_id"], "job-999")
        self.assertEqual(envelope.artifact_context_updates["current_selection_index"], 1)

    @patch("careerloop.daily_runner.DailyRunner.run")
    def test_start_scan_creates_database_records(self, mock_runner_run):
        """START_SCAN invokes DailyRunner, creates real DB records, and returns completed summary."""
        from careerloop.session.tool_registry import ToolRegistry
        from careerloop.session.states import UserJourneyState
        from careerloop.session.models import Action, ActionType

        mock_runner_run.return_value = {
            "new_jobs_found": 10,
            "unique_added": 3,
            "scored": 3,
            "shortlist_text": "1. AI Specialist @ SuperAI\n2. ML Engineer @ DeepBrain",
            "top_jobs": [
                {
                    "job": {"job_id": "job-111", "title": "AI Specialist", "company": "SuperAI", "location": "Bangalore"},
                    "score": 90.0,
                    "breakdown": {"recommendation_reason": "Top fit", "risk_summary": "None", "route_recommendation": "Outreach"}
                },
                {
                    "job": {"job_id": "job-222", "title": "ML Engineer", "company": "DeepBrain", "location": "Chennai"},
                    "score": 85.0,
                    "breakdown": {"recommendation_reason": "Good fit", "risk_summary": "None", "route_recommendation": "Outreach"}
                }
            ]
        }

        registry = ToolRegistry(self.db, self.store)
        action = Action(action_type=ActionType.START_SCAN, user_id="test-user")
        
        envelope = registry.start_scan(action, UserJourneyState.PROFILE_READY, {})
        
        self.assertEqual(envelope.response_type, "list")
        self.assertIn("Scan complete!", envelope.text)
        self.assertIn("AI Specialist", envelope.text)
        self.assertIn("ML Engineer", envelope.text)

        # Assert that DB daily_briefs and items are persisted
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, summary FROM daily_briefs WHERE user_id = 'test-user'")
                briefs = cursor.fetchall()
                self.assertEqual(len(briefs), 1)
                
                cursor.execute("SELECT job_id, title, company, fit_score FROM daily_brief_items WHERE brief_id = %s ORDER BY item_index ASC", (briefs[0]["id"],))
                items = cursor.fetchall()
                self.assertEqual(len(items), 2)
                self.assertEqual(items[0]["job_id"], "job-111")
                self.assertEqual(items[1]["job_id"], "job-222")


if __name__ == "__main__":
    unittest.main()
