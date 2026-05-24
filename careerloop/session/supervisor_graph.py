import subprocess
import os
from typing import Optional, Any, Annotated
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from careerloop.council.graph import get_council_graph
from careerloop.session.states import UserState, normalize_user_state

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
    messages: Annotated[list[BaseMessage], add_messages]
    # State used to invoke the council graph
    council_state: Optional[dict]
    assistant_response: Optional[str]
    temp_profile_data: Optional[dict]

# ── Nodes ──

def _hydrate_profile(state: dict) -> dict:
    """Reload temp_profile_data from DB if the graph state is empty."""
    profile_data = state.get("temp_profile_data") or {}
    if not profile_data:
        try:
            from careerloop.session.session_store import SessionStore
            from careerloop.memory.connection import DatabaseManager
            db = DatabaseManager(os.getenv("DATABASE_URL"))
            store = SessionStore(db)
            session = store.get_session(state.get("user_id", "unknown"))
            if session.temp_profile_data:
                profile_data = session.temp_profile_data
        except Exception:
            pass
    return profile_data


def _handle_active_state(state: dict, current_state: UserState, last_message: str) -> dict:
    """Shared handler for PROFILE_COMPLETE, SCAN_RUNNING, and BRIEF_AVAILABLE.

    Uses ChatIntentAgent to classify intent, then routes to SCAN_JOBS,
    SHOW_PIPELINE, or GENERAL_CHAT. Never auto-executes the pipeline.
    """
    from careerloop.llm_chat import ChatIntentAgent

    profile_data = _hydrate_profile(state)
    agent = ChatIntentAgent()
    intent, reply = agent.process(last_message, profile_data)

    if intent == "SCAN_JOBS":
        # Check if a brief already exists for today
        from datetime import datetime as _dt, timezone as _tz
        today_str = _dt.now(_tz.utc).date().isoformat()
        brief_path = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
            "output", "daily_briefs", f"{today_str}.md",
        )
        if os.path.exists(brief_path):
            reply = (
                "Today's brief is already ready! Type `/brief` to see it, "
                "or `/scan` to run a fresh search."
            )
        else:
            reply = (
                "Ready to scan for new jobs matching your profile. "
                "Type `/scan` to start -- this will search all configured job boards and score "
                "results against your fit criteria.\n\n"
                "Tip: `/scan` runs ~156 board queries and takes 60-120 seconds."
            )
    elif intent == "SHOW_PIPELINE":
        try:
            from careerloop.application_ledger import ApplicationLedger
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            ledger = ApplicationLedger(root)

            status_counts = {}
            for e in ledger.entries:
                s = e.get("status", "UNKNOWN")
                status_counts[s] = status_counts.get(s, 0) + 1

            top = ledger.get_top_scored(min_score=1, limit=5)

            reply = "**Your Pipeline**\n\n"
            reply += "**Status Summary:**\n"
            for status, count in sorted(status_counts.items()):
                reply += f"  - {status}: {count}\n"

            if top:
                reply += "\n**Top Matches:**\n"
                for i, job in enumerate(top, 1):
                    score = ledger._get_score(job) or 0
                    reply += f"  {i}. **{job.get('title','?')}** @ {job.get('company','?')} -- {score:.0f}/100\n"
            else:
                reply += "\nNo scored jobs yet. Type `/scan` to search for new opportunities."

            from datetime import datetime, timezone
            today_str = datetime.now(timezone.utc).date().isoformat()
            brief_path = os.path.join(root, "output", "daily_briefs", f"{today_str}.md")
            if os.path.exists(brief_path):
                reply += f"\n\nToday's brief is available at: {brief_path}"
        except Exception as e:
            reply = f"Could not load pipeline: {e}"

    # GENERAL_CHAT returns the ChatIntentAgent reply as-is

    return {
        "current_state": current_state,
        "assistant_response": reply,
        "messages": [AIMessage(content=reply)],
        "temp_profile_data": profile_data,
    }


def _intent_approve_or_reply(state: dict, current_state: UserState, last_message: str) -> dict:
    """Use ChatIntentAgent to check for APPROVE intent, else return the LLM reply."""
    from careerloop.llm_chat import ChatIntentAgent
    profile_data = _hydrate_profile(state)
    agent = ChatIntentAgent()
    intent, reply = agent.process(last_message, profile_data)
    return {
        "intent": intent,
        "reply": reply,
        "profile_data": profile_data,
    }


def intent_router(state: ConversationState) -> dict:
    """Classify free-form user messages against the current state.

    All 11 UserState values have an explicit handler path.
    Every return dict includes assistant_response.
    """
    import logging
    _logger = logging.getLogger("careerloop.session.supervisor_graph")

    messages = state.get("messages", [])
    if not messages:
        reply = "I didn't receive a message. How can I help?"
        return {
            "assistant_response": reply,
            "messages": [AIMessage(content=reply)],
        }

    last_message = (
        messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
    )
    current_state = normalize_user_state(state.get("current_state", UserState.IDLE)) or UserState.IDLE

    # ═══════════════════════════════════════════════════════════════
    # STATE 1-3: IDLE + ONBOARDING_WAITING_CV + ONBOARDING_COLLECTING
    # ═══════════════════════════════════════════════════════════════
    if current_state in (UserState.IDLE, UserState.ONBOARDING_WAITING_CV, UserState.ONBOARDING_COLLECTING):
        from careerloop.session.session_store import SessionStore, Session
        from careerloop.memory.connection import DatabaseManager
        from careerloop.onboarding.onboarding_flow import OnboardingFlow

        db = DatabaseManager(os.getenv("DATABASE_URL"))
        store = SessionStore(db)

        user_id = state.get("user_id", "unknown")
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO public.users (id, email) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                        (user_id, f"{user_id}@example.com"),
                    )
                conn.commit()
        except Exception:
            pass

        # Construct session from graph state — NOT from a second DB load
        session = Session(user_id=user_id, state=current_state)
        session.temp_profile_data = _hydrate_profile(state)

        flow = OnboardingFlow(store)
        reply, next_state = flow.handle_message(session, last_message)
        return {
            "current_state": next_state,
            "assistant_response": reply,
            "messages": [AIMessage(content=reply)],
            "temp_profile_data": session.temp_profile_data,
        }

    # ═══════════════════════════════════════════════════════════════
    # STATE 4-6, 11: PROFILE_COMPLETE + SCAN_RUNNING + BRIEF_AVAILABLE + APPLIED
    # ═══════════════════════════════════════════════════════════════
    if current_state in (UserState.PROFILE_COMPLETE, UserState.SCAN_RUNNING, UserState.BRIEF_AVAILABLE, UserState.APPLIED):
        return _handle_active_state(state, current_state, last_message)

    # ═══════════════════════════════════════════════════════════════
    # STATE 7: REVIEWING_JOB
    # ═══════════════════════════════════════════════════════════════
    if current_state == UserState.REVIEWING_JOB:
        result = _intent_approve_or_reply(state, current_state, last_message)
        if result["intent"] == "APPROVE":
            reply = result.get("reply") or "Approved! Generating your application pack now..."
            return {
                "current_state": UserState.PACK_GENERATING,
                "assistant_response": reply,
                "messages": [AIMessage(content=reply)],
                "temp_profile_data": result.get("profile_data", {}),
            }
        elif result["intent"] == "GENERAL_CHAT":
            return {
                "current_state": current_state,
                "assistant_response": result["reply"],
                "messages": [AIMessage(content=result["reply"])],
                "temp_profile_data": result.get("profile_data", {}),
            }
        else:
            reply = (
                result.get("reply")
                or "Would you like me to prepare an application pack for this job? "
                "Type 'yes' or 'approve' to proceed, or ask me any questions about the role."
            )
            return {
                "current_state": current_state,
                "assistant_response": reply,
                "messages": [AIMessage(content=reply)],
                "temp_profile_data": result.get("profile_data", {}),
            }

    # ═══════════════════════════════════════════════════════════════
    # STATE 8: PACK_GENERATING (transient -- route_from_intent sends
    #           this to the pack_generation node before user sees it)
    # ═══════════════════════════════════════════════════════════════
    if current_state == UserState.PACK_GENERATING:
        reply = "Your application pack is being generated. This may take a moment..."
        return {
            "current_state": current_state,
            "assistant_response": reply,
            "messages": [AIMessage(content=reply)],
        }

    # ═══════════════════════════════════════════════════════════════
    # STATE 9: PACK_READY
    # ═══════════════════════════════════════════════════════════════
    if current_state == UserState.PACK_READY:
        result = _intent_approve_or_reply(state, current_state, last_message)
        if result["intent"] == "APPROVE":
            reply = (
                result.get("reply")
                or "Approval received! Moving to application confirmation. "
                "Type 'submit' or 'approve' to confirm submission."
            )
            return {
                "current_state": UserState.AWAITING_APPLICATION_CONFIRMATION,
                "assistant_response": reply,
                "messages": [AIMessage(content=reply)],
                "temp_profile_data": result.get("profile_data", {}),
            }
        else:
            reply = (
                result.get("reply")
                or "Your application pack is ready for review. "
                "Type 'approve' to proceed with assisted application, or ask me any questions."
            )
            return {
                "current_state": current_state,
                "assistant_response": reply,
                "messages": [AIMessage(content=reply)],
                "temp_profile_data": result.get("profile_data", {}),
            }

    # ═══════════════════════════════════════════════════════════════
    # STATE 10: AWAITING_APPLICATION_CONFIRMATION
    # ═══════════════════════════════════════════════════════════════
    if current_state == UserState.AWAITING_APPLICATION_CONFIRMATION:
        result = _intent_approve_or_reply(state, current_state, last_message)
        if result["intent"] == "APPROVE":
            reply = (
                result.get("reply")
                or "Application submitted! Your application has been logged and is now being tracked."
            )
            return {
                "current_state": UserState.APPLIED,
                "assistant_response": reply,
                "messages": [AIMessage(content=reply)],
                "temp_profile_data": result.get("profile_data", {}),
            }
        else:
            reply = (
                result.get("reply")
                or "Ready to submit this application. Type 'approve' or 'submit' to confirm, "
                "or ask me any questions first."
            )
            return {
                "current_state": current_state,
                "assistant_response": reply,
                "messages": [AIMessage(content=reply)],
                "temp_profile_data": result.get("profile_data", {}),
            }

    # ═══════════════════════════════════════════════════════════════
    # FALLTHROUGH: unexpected state -- log warning, return safe message
    # ═══════════════════════════════════════════════════════════════
    _logger.warning(
        "intent_router fallthrough: unhandled state %s (type=%s). "
        "Returning safe fallback message.",
        current_state, type(current_state).__name__,
    )
    reply = (
        "I'm not sure what to do next. Type /help for available commands "
        "or /scan to search for new opportunities."
    )
    return {
        "current_state": current_state,
        "assistant_response": reply,
        "messages": [AIMessage(content=reply)],
    }

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

    import logging
    logger = logging.getLogger("careerloop.session.supervisor_graph")
    council = get_council_graph()
    try:
        result = council.invoke(council_state)
    except Exception as e:
        return {
            "current_state": UserState.REVIEWING_JOB,
            "assistant_response": f"Pack generation failed safely: {e}",
        }

    # ── Hook the Package Assembly layer ──
    try:
        from careerloop.package_assembly import PackageAssembler
        assembler = PackageAssembler()
        person_id = state.get("user_id") or "siddharth"
        job_id = state.get("pending_job_id") or result.get("job_id") or "unknown"
        assembly_res = assembler.assemble_package(
            person_id=person_id,
            job_id=job_id,
            council_state=result
        )
        msg = (
            f"✅ **Application pack compiled and assembled successfully!**\n\n"
            f"📁 **Location:** `{assembly_res['pack_dir']}`\n"
            f"📄 **Tailored Resume PDFs generated:**\n"
            + "\n".join(f"- `{os.path.basename(p)}`" for p in assembly_res['pdfs']) + "\n\n"
            f"Please review the `outreach_pack.md` in that folder and type 'approve' to proceed with the assisted execution."
        )
    except Exception as assembly_err:
        logger.error(f"Package assembly failed: {assembly_err}")
        msg = f"Application pack generated successfully but assembly failed: {assembly_err}"

    return {
        "current_state": UserState.PACK_READY,
        "council_state": result,
        "assistant_response": msg,
    }

# ── Graph Builder ──

def route_from_intent(state: ConversationState):
    """Conditional routing based on current conversation state.

    PACK_GENERATING -> pack_generation node (triggers Resume Council).
    All other states -> END (response is returned to the transport layer).
    """
    curr = normalize_user_state(state.get("current_state", UserState.IDLE)) or UserState.IDLE
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
