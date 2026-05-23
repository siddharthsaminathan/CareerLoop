import subprocess
import os
from typing import Optional, Any
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END

from careerloop.council.graph import get_council_graph
from careerloop.session.states import UserState

# ── Tools Wrapping Phase 1 Scripts ──

@tool
def scan_jobs_tool(query: str = "") -> str:
    """Scans for new jobs using the legacy scan.mjs script."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cmd = ["node", "scan.mjs"]
    if query:
        cmd.extend(["--query", query])
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=root,
            timeout=120,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return "Error scanning jobs: command timed out after 120s."
    except subprocess.CalledProcessError as e:
        return f"Error scanning jobs: {e.stderr or e.stdout}"
    except Exception as e:
        return f"Error scanning jobs: {e}"

@tool
def check_liveness_tool(url: str) -> str:
    """Checks if a job URL is still active using check-liveness.mjs."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    try:
        result = subprocess.run(
            ["node", "check-liveness.mjs", url],
            capture_output=True,
            text=True,
            check=True,
            cwd=root,
            timeout=90,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return "Error checking liveness: command timed out after 90s."
    except subprocess.CalledProcessError as e:
        return f"Error checking liveness: {e.stderr or e.stdout}"
    except Exception as e:
        return f"Error checking liveness: {e}"

# ── State Definition ──

class ConversationState(TypedDict):
    user_id: str
    current_state: UserState
    pending_job_id: Optional[str]
    messages: list[BaseMessage]
    # State used to invoke the council graph
    council_state: Optional[dict]
    assistant_response: Optional[str]
    temp_profile_data: Optional[dict]

# ── Nodes ──

def intent_router(state: ConversationState) -> dict:
    """Classify free-form user messages against the current state."""
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_message = (
        messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
    )
    current_state = state.get("current_state", UserState.IDLE)

    if current_state == UserState.IDLE or current_state.name.startswith("ONBOARDING_"):
        import os
        from careerloop.session.session_store import SessionStore, Session
        from careerloop.memory.connection import DatabaseManager
        from careerloop.onboarding.onboarding_flow import OnboardingFlow
        
        db = DatabaseManager(os.getenv("DATABASE_URL"))
        store = SessionStore(db)
        
        # Ensure user exists before using SessionStore
        user_id = state.get("user_id", "unknown")
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO public.users (id, email) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING", (user_id, f"{user_id}@example.com"))
                conn.commit()
        except Exception:
            pass
            
        # Fetch the actual session from the Postgres database
        session = store.get_session(user_id)
        
        # Override the state if it was explicitly passed via LangGraph metadata
        if current_state != UserState.IDLE:
            session.state = current_state
            
        # Ensure we capture any new temp profile data passed from LangGraph
        graph_temp_data = state.get("temp_profile_data", {})
        if graph_temp_data:
            session.temp_profile_data = graph_temp_data
        
        flow = OnboardingFlow(store)
        reply, next_state = flow.handle_message(session, last_message)
        return {
            "current_state": next_state,
            "assistant_response": reply,
            "temp_profile_data": session.temp_profile_data,
        }

    if current_state == UserState.PACK_READY:
        normalized = last_message.strip().lower()
        if normalized == "approve & auto-apply":
            return {
                "current_state": UserState.AWAITING_APPLICATION_CONFIRMATION,
                "assistant_response": (
                    "Approval received for this job. Assisted execution is enabled for this single reviewed pack."
                ),
            }
        return {
            "current_state": UserState.REVIEWING_JOB,
            "assistant_response": (
                "I did not receive approval. I kept you in review mode. Type exactly 'Approve & Auto-Apply' to continue."
            ),
        }

    # For other states like DAILY_BRIEF_SENT, use Intent Agent or pass through
    if current_state == UserState.DAILY_BRIEF_SENT:
        from careerloop.llm_chat import ChatIntentAgent
        from careerloop.daily_runner import DailyRunner
        import os
        agent = ChatIntentAgent()
        profile_data = state.get("temp_profile_data", {})
        intent, reply = agent.process(last_message, profile_data)
        
        if intent == "SCAN_JOBS":
            from careerloop.tools.sync_profile import sync_profile_data
            sync_res = sync_profile_data(profile_data)
            
            reply += "\nTriggering job scan via DailyRunner..."
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            try:
                runner = DailyRunner(root)
                result = runner.run(do_scan=True)
                reply += f"\nScan complete! Found {result['new_jobs_found']} new raw jobs, {result['unique_added']} unique added, {result['scored']} scored."
            except Exception as e:
                reply += f"\nError running scan: {e}"
        
        return {
            "current_state": current_state,
            "assistant_response": reply
        }

    return {"current_state": current_state}

def pack_generating_node(state: ConversationState) -> dict:
    """Calls the Resume Council Subgraph."""
    council_state = state.get("council_state", {})

    if not isinstance(council_state, dict) or not council_state:
        return {
            "current_state": UserState.REVIEWING_JOB,
            "assistant_response": (
                "Cannot build a pack yet because council input is missing. Please select a job first."
            ),
        }

    council = get_council_graph()
    try:
        result = council.invoke(council_state)
    except Exception as e:
        return {
            "current_state": UserState.REVIEWING_JOB,
            "assistant_response": f"Pack generation failed safely: {e}",
        }

    return {
        "current_state": UserState.PACK_READY,
        "council_state": result,
        "assistant_response": "Application pack is ready for review.",
    }

# ── Graph Builder ──

def route_from_intent(state: ConversationState):
    """Conditional routing based on current conversation state."""
    curr = state.get("current_state", UserState.IDLE)
    if curr == UserState.PACK_GENERATING:
        return "pack_generation"
    return END

def build_supervisor_graph():
    builder = StateGraph(ConversationState)
    
    # Add nodes
    builder.add_node("router", intent_router)
    builder.add_node("pack_generation", pack_generating_node)
    
    # Connect graph
    builder.add_edge(START, "router")
    builder.add_conditional_edges("router", route_from_intent)
    builder.add_edge("pack_generation", END)
    
    return builder

# Get compiled graph
def get_supervisor_graph(checkpointer=None):
    """
    Returns the compiled LangGraph supervisor.
    The graph is compiled with the checkpointer to persist state across asynchronous transport boundaries.
    """
    builder = build_supervisor_graph()
    return builder.compile(checkpointer=checkpointer)
