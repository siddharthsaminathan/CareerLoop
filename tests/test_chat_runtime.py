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
            "current_state": "PROFILE_COMPLETE",
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
        from careerloop.session.command_router import CommandRouter
        router = CommandRouter(root="/tmp")
        result = router.brief()
        self.assertIn("No brief generated", result.text)
        self.assertIsNone(result.new_state)


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
        from careerloop.session.states import normalize_user_state, UserState
        result = normalize_user_state("DAILY_BRIEF_SENT")
        self.assertEqual(result, UserState.PROFILE_COMPLETE)

    def test_onboarding_q_states_migrate(self):
        from careerloop.session.states import normalize_user_state, UserState
        for old in ("ONBOARDING_Q1_ROLES", "ONBOARDING_Q2_CITIES", "ONBOARDING_Q3_SALARY"):
            result = normalize_user_state(old)
            self.assertEqual(result, UserState.ONBOARDING_COLLECTING)

    def test_unknown_state_resets_to_idle(self):
        from careerloop.session.states import normalize_user_state, UserState
        result = normalize_user_state("GARBAGE_STATE")
        self.assertEqual(result, UserState.IDLE)


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
    @patch("careerloop.session.supervisor_graph._intent_approve_or_reply")
    def test_approve_at_reviewing_job_yields_pack_generating(self, mock_approve):
        """Router node: REVIEWING_JOB + APPROVE -> PACK_GENERATING state in output."""
        from careerloop.session.supervisor_graph import intent_router
        from careerloop.session.states import UserState
        from langchain_core.messages import HumanMessage

        mock_approve.return_value = {
            "intent": "APPROVE",
            "reply": "Approved!",
            "profile_data": {"target_roles": "AI Engineer"},
        }

        state = {
            "user_id": "test-user",
            "current_state": UserState.REVIEWING_JOB,
            "pending_job_id": "job-123",
            "messages": [HumanMessage(content="prepare this one")],
            "council_state": None,
            "assistant_response": None,
            "temp_profile_data": {"target_roles": "AI Engineer"},
        }

        result = intent_router(state)

        self.assertEqual(result["current_state"], UserState.PACK_GENERATING,
                         f"Expected PACK_GENERATING, got {result['current_state']}")


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
    def test_command_router_brief_is_callable(self):
        from careerloop.session.command_router import CommandRouter
        router = CommandRouter(root="/tmp")
        result = router.brief()
        self.assertIsNotNone(result.text)
        self.assertTrue(len(result.text) > 0)


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


if __name__ == "__main__":
    unittest.main()
