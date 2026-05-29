import os
import json
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

# P1-07: Module-level singleton — created ONCE and reused across all graph invocations
# so we don't exhaust the connection pool. Initialized lazily on first use.
_db_singleton: Any = None
_db_singleton_lock = None  # threading.Lock, initialized lazily


def _get_db():
    """Return the module-level DatabaseManager singleton (lazy-init, thread-safe)."""
    global _db_singleton, _db_singleton_lock
    if _db_singleton is not None:
        return _db_singleton
    import threading
    if _db_singleton_lock is None:
        _db_singleton_lock = threading.Lock()
    with _db_singleton_lock:
        if _db_singleton is not None:
            return _db_singleton
        from careerloop.memory.connection import DatabaseManager
        _db_singleton = DatabaseManager(os.getenv("DATABASE_URL"))
        logger.info("DatabaseManager singleton initialized")
        return _db_singleton

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

    # P1-07: Use module-level DatabaseManager singleton instead of
    # creating a new connection pool on every graph invocation.
    # SessionStore is cheap — just wraps the shared db singleton.
    from careerloop.session.session_store import SessionStore
    db = _get_db()
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
        # Load user profile for context to avoid hallucinating about missing CV/profile
        profile_summary = ""
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT email, full_name, master_cv_markdown, onboarding_complete, work_style_prefs FROM careerloop.users WHERE id = %s",
                        (user_id,)
                    )
                    user_row = cur.fetchone()
                    if user_row:
                        has_cv = bool(user_row.get("master_cv_markdown"))
                        full_name = user_row.get("full_name") or "User"
                        email = user_row.get("email") or ""
                        prefs = {}
                        if user_row.get("work_style_prefs"):
                            try:
                                prefs = json.loads(user_row["work_style_prefs"]) if isinstance(user_row["work_style_prefs"], str) else user_row["work_style_prefs"]
                            except Exception:
                                pass
                        profile_summary = (
                            f"User Info:\n"
                            f"- Name: {full_name}\n"
                            f"- Email: {email}\n"
                            f"- Has CV/Resume uploaded: {has_cv}\n"
                            f"- Onboarding Complete: {user_row.get('onboarding_complete')}\n"
                            f"- Target Roles: {prefs.get('target_roles', 'N/A')}\n"
                            f"- Target Cities: {prefs.get('target_cities', 'N/A')}\n"
                        )
        except Exception as pe:
            logger.warning(f"Failed to load profile summary for general chat: {pe}")

        response_text = _generate_chat_reply(state.get("messages", []), profile_summary=profile_summary)

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


def _generate_chat_reply(messages: list, profile_summary: str = "") -> str:
    """Generate a conversational reply when no tool handles the input."""
    try:
        from careerloop.llm_chat import LLMChatAgent
        import json as _json
        agent = LLMChatAgent()
        # Build conversation context from last 6 messages
        history_parts = []
        for m in (messages or [])[-6:]:
            content = m.content if hasattr(m, "content") else str(m)
            history_parts.append(content)
        context = "\n".join(history_parts) if history_parts else "(no prior messages)"

        system = (
            "You are CareerLoop, a career execution assistant for Indian professionals. "
            "Be helpful, concise, and conversational. Keep responses to 2-3 sentences. "
            "Never output JSON — always respond in natural English."
        )
        user = ""
        if profile_summary:
            user += f"{profile_summary}\n\n"
        user += f"Conversation:\n{context}\n\nRespond naturally to the last message."
        raw = agent._call_api(system, user)

        # Strip JSON if the model accidentally returned structured output
        text = (raw or "").strip()
        if text.startswith("{") and text.endswith("}"):
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


import functools


@functools.lru_cache(maxsize=2)
def get_supervisor_graph(checkpointer=None):
    """
    Returns the compiled LangGraph supervisor.

    Cached: graph compilation is CPU-bound (50–200ms) and the result is reusable.
    Without this, every chat request rebuilt + recompiled the whole graph.
    The API always calls with checkpointer=None, so the cache key is stable.
    """
    builder = build_supervisor_graph()
    return builder.compile(checkpointer=checkpointer)
