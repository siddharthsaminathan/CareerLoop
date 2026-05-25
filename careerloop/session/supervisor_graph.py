import os
import logging
from typing import Optional, Any, Annotated, Dict
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from careerloop.session.states import UserJourneyState, normalize_user_state
from careerloop.session.models import Action, ResponseEnvelope
from careerloop.session.action_resolver import ActionResolver
from careerloop.session.tool_registry import ToolRegistry

logger = logging.getLogger("careerloop.session.supervisor_graph")

class ConversationState(TypedDict):
    user_id: str
    current_state: UserJourneyState
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Context
    temp_profile_data: Optional[dict]
    artifact_context: Dict[str, Any]
    
    # Outputs
    action_taken: Optional[Action]
    response_envelope: Optional[ResponseEnvelope]
    assistant_response: Optional[str] # legacy/convenience


def action_routing_node(state: ConversationState) -> dict:
    """Invokes the ActionResolver to determine the user's intent."""
    user_id = state.get("user_id", "unknown")
    messages = state.get("messages", [])
    
    if not messages:
        return {"assistant_response": "I didn't receive a message. How can I help?"}
        
    last_message = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
    current_state = normalize_user_state(state.get("current_state"))
    artifact_context = state.get("artifact_context") or {}

    resolver = ActionResolver()
    action = resolver.resolve(
        user_message=last_message,
        user_id=user_id,
        state=current_state,
        artifact_context=artifact_context,
        messages=messages
    )
    
    logger.info(f"Action resolved: {action.action_type.value} (confidence: {action.confidence})")
    return {"action_taken": action}


def execute_action_node(state: ConversationState) -> dict:
    """Executes the resolved action using the ToolRegistry and formats the response."""
    action = state.get("action_taken")
    if not action:
        return {"assistant_response": "Internal error: No action resolved."}

    user_id = state.get("user_id", "unknown")
    current_state = normalize_user_state(state.get("current_state"))
    artifact_context = state.get("artifact_context") or {}

    # Initialize DB and Tool Registry
    from careerloop.memory.connection import DatabaseManager
    from careerloop.session.session_store import SessionStore
    db = DatabaseManager(os.getenv("DATABASE_URL"))
    store = SessionStore(db)

    registry = ToolRegistry(db, store)
    envelope = registry.execute(action, current_state, artifact_context)

    # Update Context & State
    new_context = dict(artifact_context)
    new_context.update(envelope.artifact_context_updates)

    next_state = current_state
    if "state" in envelope.state_updates:
        next_state = envelope.state_updates["state"]

    # Format response naturally from envelope data
    response_text = _format_envelope(envelope)

    # For GENERAL_CHAT with empty tool output, call LLM for conversational response
    if action.action_type.value == "GENERAL_CHAT" and not response_text.strip():
        response_text = _generate_chat_reply(
            state.get("messages", []),
            user_id=state.get("user_id", ""),
            artifact_context=new_context,
        )

    # Persist user + assistant messages to careerloop.messages for restart continuity
    try:
        import uuid as _uuid, json as _json
        _persist_messages = state.get("messages", [])
        if _persist_messages:
            with db.get_connection() as _mconn:
                with _mconn.cursor() as _mcur:
                    _mcur.execute(
                        "SELECT id FROM careerloop.conversations WHERE user_id = %s AND transport = 'cli' AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                        (user_id,))
                    _crow = _mcur.fetchone()
                    if _crow:
                        conv_id = _crow["id"]
                    else:
                        conv_id = str(_uuid.uuid4())
                        _mcur.execute(
                            "INSERT INTO careerloop.conversations (id, user_id, transport) VALUES (%s, %s, 'cli')",
                            (conv_id, user_id))
                    last_user_msg = _persist_messages[-1]
                    user_content = last_user_msg.content if hasattr(last_user_msg, "content") else str(last_user_msg)
                    _mcur.execute(
                        "INSERT INTO careerloop.messages (id, conversation_id, user_id, role, content, action_type, action_confidence, artifact_context) "
                        "VALUES (%s, %s, %s, 'user', %s, %s, %s, %s)",
                        (str(_uuid.uuid4()), conv_id, user_id, user_content,
                         action.action_type.value if action else None,
                         action.confidence if action else None,
                         _json.dumps(new_context) if new_context else None))
                    _mcur.execute(
                        "INSERT INTO careerloop.messages (id, conversation_id, user_id, role, content, response_envelope) "
                        "VALUES (%s, %s, %s, 'assistant', %s, %s)",
                        (str(_uuid.uuid4()), conv_id, user_id, response_text,
                         _json.dumps({"response_type": envelope.response_type, "cards_count": len(envelope.cards)} if envelope else {})))
    except Exception as _me:
        logger.debug(f"Message persistence skipped: {_me}")

    return {
        "response_envelope": envelope,
        "assistant_response": response_text,
        "current_state": next_state,
        "artifact_context": new_context,
        "messages": [AIMessage(content=response_text)],
    }


def _format_envelope(envelope: ResponseEnvelope) -> str:
    """Format a ResponseEnvelope into a readable markdown string."""
    if envelope.response_type == "error":
        return f"⚠️ {envelope.text}" if envelope.text else "Something went wrong."

    parts = []
    if envelope.text:
        parts.append(envelope.text)

    if envelope.cards:
        lines = []
        for c in envelope.cards:
            label = c.get("label") or c.get("command") or c.get("name", "")
            value = c.get("value") or c.get("description") or c.get("status", "")
            if label and value is not None:
                lines.append(f"**{label}:** {value}")
            elif label:
                lines.append(f"**{label}**")
        if lines:
            parts.append("\n".join(lines))

    return "\n\n".join(parts) if parts else ""


def _generate_chat_reply(messages: list, user_id: str = "", artifact_context: dict = None) -> str:
    """Generate a conversational reply when no tool handles the input."""
    try:
        from careerloop.llm_chat import LLMChatAgent
        agent = LLMChatAgent()
        history_parts = []
        for m in (messages or [])[-8:]:
            content = m.content if hasattr(m, "content") else str(m)
            history_parts.append(content)
        context = "\n".join(history_parts) if history_parts else "(no prior messages)"

        # Load user profile for context
        profile_note = ""
        if user_id:
            try:
                import os as _os, json as _json
                import psycopg2
                _conn = psycopg2.connect(_os.getenv("DATABASE_URL", ""))
                _cur = _conn.cursor()
                _cur.execute(
                    "SELECT u.full_name, up.target_roles, up.target_cities, up.aggressiveness "
                    "FROM careerloop.users u LEFT JOIN careerloop.user_preferences up ON u.id = up.user_id WHERE u.id = %s",
                    (user_id,))
                _row = _cur.fetchone()
                if _row:
                    name = _row[0] or "User"
                    roles = _row[1] or []; cities = _row[2] or []
                    if isinstance(roles, str): roles = [r.strip() for r in roles.split(",") if r.strip()]
                    if isinstance(cities, str): cities = [c.strip() for c in cities.split(",") if c.strip()]
                    profile_note = f"You are talking to {name}. They target {', '.join(roles[:3])} roles in {', '.join(cities[:3])}."
                _cur.close(); _conn.close()
            except Exception:
                pass

        ctx_note = ""
        if artifact_context:
            atype = artifact_context.get("active_artifact_type", "")
            if atype == "daily_brief": ctx_note = "The user is looking at their daily job brief."
            elif atype == "job_card": ctx_note = "The user is reviewing a specific job."
            elif atype == "scan_running": ctx_note = "A job scan is running in the background."

        system = (
            "You are CareerLoop, a career execution assistant for Indian professionals. "
            "Be helpful, concise, and conversational. Keep responses to 2-3 sentences. "
            "Never output JSON — always respond in natural English. "
            "If the user's pipeline is empty, suggest running a scan. "
            "If the user seems confused, suggest they ask for their daily brief or pipeline status."
        )
        if profile_note: system += f" {profile_note}"
        if ctx_note: system += f" {ctx_note}"

        user = f"Recent conversation:\n{context}\n\nRespond naturally to the last user message."
        raw = agent._call_api(system, user)

        text = (raw or "").strip()
        if text.startswith("{") and text.endswith("}"):
            import json as _json
            try:
                parsed = _json.loads(text)
                text = parsed.get("reply") or parsed.get("text") or parsed.get("reasoning") or ""
            except Exception:
                pass
        return text if text else "How can I help with your job search today?"
    except Exception:
        return "I'm here to help with your job search. Ask me for your daily brief, pipeline, or to scan for new jobs!"


def build_supervisor_graph():
    builder = StateGraph(ConversationState)
    
    builder.add_node("action_routing", action_routing_node)
    builder.add_node("execute_action", execute_action_node)
    
    builder.add_edge(START, "action_routing")
    builder.add_edge("action_routing", "execute_action")
    builder.add_edge("execute_action", END)
    
    return builder


def get_supervisor_graph(checkpointer=None):
    """
    Returns the compiled LangGraph supervisor.
    """
    builder = build_supervisor_graph()
    return builder.compile(checkpointer=checkpointer)
