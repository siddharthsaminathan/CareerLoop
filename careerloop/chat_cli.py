import os
import sys
import uuid
import logging
from dotenv import load_dotenv

# Support running as script (python careerloop/chat_cli.py) and module (-m careerloop.chat_cli)
if __package__ is None or __package__ == "":
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

# Load environment variables from .env file
load_dotenv()

from careerloop.logging_config import configure as _configure_logging
_configure_logging()
logger = logging.getLogger(__name__)

from careerloop.session.session_store import SessionStore
from careerloop.session.states import UserJourneyState
from careerloop.transport.terminal_chat import TerminalChatAdapter
from careerloop.session.supervisor_graph import get_supervisor_graph
from careerloop.memory.checkpointer import get_checkpointer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich import box
console = Console()

def authenticate_cli_user() -> str:
    """
    Mock authentication for the CLI that returns a UUID.
    In a full implementation, this uses supabase.auth.sign_in_with_password()
    and retrieves the user's UUID from the JWT.
    """
    session_file = os.path.join(os.path.expanduser("~"), ".careerloop_session")
    
    if os.path.exists(session_file):
        with open(session_file, 'r') as f:
            email = f.read().strip()
        console.print(f"[bold green]Welcome back to CareerLoop![/bold green] (Auto-logged in as: {email})")
    else:
        console.print("[bold green]Welcome to CareerLoop Terminal Chat.[/bold green]")
        console.print("Please enter your email to login or sign up:")
        email = input("> ").strip()
        
        if not email:
            console.print("[bold red]Email is required.[/bold red]")
            sys.exit(1)
            
        try:
            with open(session_file, 'w') as f:
                f.write(email)
        except Exception:
            pass
        
    # Generate a consistent UUID for this email to simulate Supabase auth
    NAMESPACE_CAREERLOOP = uuid.UUID('12345678-1234-5678-1234-567812345678')
    user_uuid = str(uuid.uuid5(NAMESPACE_CAREERLOOP, email))
    
    # Normally we would fetch the user from Supabase. We simulate upserting.
    try:
        from careerloop.memory.connection import get_db_manager
        db = get_db_manager()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO careerloop.users (id, email, full_name, created_at, updated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO NOTHING
                """, (user_uuid, email, email.split('@')[0]))
            conn.commit()
    except Exception as e:
        logger.warning(f"Could not create authenticated user row; continuing with existing/local session state: {e}")

    return user_uuid

def print_banner():
    banner = """
  ______ ___   ____  ______ ______ ____  __     ____   
 / ____//   | / __ \\/ ____// ____// __ \\/ /    / __ \\  
/ /    / /| |/ /_/ / __/  / __/  / /_/ / /    / / / /  
/ /___ / ___ / _, _/ /___ / /___ / ____/ /___ / /_/ /   
\\____//_/  |_/_/ |_/_____//_____/_/   /_____/ \\____/    
                                                        
            CO-PILOT CONSOLE v1.0                    
    """
    console.print(Panel(banner, border_style="bold green", title="CareerLoop Core Shell", box=box.DOUBLE))

def get_profile_data(session) -> dict:
    """
    Get profile data, falling back to persisted careerloop.users table if temp_profile_data is empty.
    """
    if session.temp_profile_data and any(session.temp_profile_data.values()):
        return session.temp_profile_data
    
    # Load from careerloop.users
    try:
        from careerloop.memory.connection import get_db_manager
        db = get_db_manager()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT master_cv_markdown, work_style_prefs
                    FROM careerloop.users
                    WHERE id = %s
                """, (session.user_id,))
                row = cur.fetchone()
        if row:
            prefs = row.get("work_style_prefs") or {}
            # Handle if prefs is a JSON string or dict
            if isinstance(prefs, str):
                import json
                try:
                    prefs = json.loads(prefs)
                except Exception:
                    prefs = {}
            data = {
                "cv_content": row.get("master_cv_markdown", ""),
                "target_roles": prefs.get("target_roles", ""),
                "target_cities": prefs.get("target_cities", ""),
                "salary_expectations": prefs.get("salary_expectations", ""),
                "notice_period": prefs.get("notice_period", ""),
                "aggressiveness": prefs.get("aggressiveness", ""),
                "current_ctc": prefs.get("current_ctc", ""),
                "current_company": prefs.get("current_company", ""),
                "current_title": prefs.get("current_title", ""),
                "linkedin_url": prefs.get("linkedin_url", ""),
            }
            return data
    except Exception as e:
        logger.error(f"Error loading persisted profile: {e}")
    
    return {}

def print_status_card(session):
    data = get_profile_data(session)
    table = Table(title="[bold green]Active Session Profile Card[/bold green]", box=box.ROUNDED, border_style="cyan")
    table.add_column("Attribute", style="bold yellow")
    table.add_column("Value", style="white")
    
    table.add_row("User ID (UUID)", session.user_id)
    table.add_row("State Node", session.state.name)
    table.add_row("Notice Period", str(data.get("notice_period", "N/A")) if data.get("notice_period") else "N/A")
    table.add_row("Salary Exp", str(data.get("salary_expectations", "N/A")) if data.get("salary_expectations") else "N/A")
    table.add_row("Target Roles", str(data.get("target_roles", "N/A")) if data.get("target_roles") else "N/A")
    table.add_row("Target Cities", str(data.get("target_cities", "N/A")) if data.get("target_cities") else "N/A")
    table.add_row("Aggressiveness", str(data.get("aggressiveness", "N/A")) if data.get("aggressiveness") else "N/A")
    console.print(table)

def print_help_panel():
    table = Table(title="[bold cyan]What You Can Ask Me[/bold cyan]", box=box.ROUNDED, border_style="cyan")
    table.add_column("Topic", style="bold green")
    table.add_column("Description", style="white")
    table.add_row("Scan for jobs", "Search job boards for roles matching your profile.")
    table.add_row("Show my pipeline", "Display recently crawled and scored jobs.")
    table.add_row("Show my brief", "Display today's daily job brief with recommendations.")
    table.add_row("Update my profile", "Change your target roles, cities, salary expectations, or CV.")
    table.add_row("Reset my session", "Clear your profile data and restart onboarding.")
    table.add_row("Exit / Quit", "End your CareerLoop session.")
    console.print(table)

def print_pipeline(db_manager):
    table = Table(title="[bold yellow]Scored Job Pipeline[/bold yellow]", box=box.ROUNDED, border_style="yellow")
    table.add_column("Job ID", style="cyan")
    table.add_column("Company ID", style="magenta")
    table.add_column("Title", style="bold white")
    table.add_column("Location", style="yellow")
    table.add_column("Source", style="green")
    
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, company_id, title, location, source_type FROM careerloop.job_cache LIMIT 15")
                rows = cur.fetchall()
        if not rows:
            console.print("[yellow]No jobs in the local cache yet. Want me to scan now?[/yellow]")
            return
        for row in rows:
            comp_id = row.get('company_id', '') or ''
            comp_id_display = comp_id[:8] + "..." if len(str(comp_id)) > 8 else (str(comp_id) or "N/A")
            table.add_row(
                row.get('id', '')[:8] + "...",
                comp_id_display,
                row.get('title', ''),
                row.get('location', '') or "N/A",
                row.get('source_type', '') or "N/A"
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error reading pipeline database: {e}[/red]")

def print_profile_details(session):
    data = get_profile_data(session)
    if not data or not any(data.values()):
        console.print("[yellow]No extracted profile data found yet. Start onboarding to set up your profile![/yellow]")
        return
    
    table = Table(title="[bold magenta]Extracted Profile Details[/bold magenta]", box=box.ROUNDED, border_style="magenta")
    table.add_column("Field", style="bold cyan")
    table.add_column("Value", style="white")
    
    for k, v in data.items():
        if k == 'cv_content':
            v = str(v)[:200] + "..." if len(str(v)) > 200 else str(v)
        table.add_row(k.replace('_', ' ').title(), str(v))
    console.print(table)

def _render_scan_events(user_id: str):
    """Poll run_events for the latest scan and render MATCH/REJECT cleanly."""
    try:
        from careerloop.memory.connection import get_db_manager

        db = get_db_manager()

        with db.get_connection() as conn:
            with conn.cursor() as cur:
                # Find the latest scan run for this user
                cur.execute(
                    "SELECT run_id, status FROM careerloop.background_runs "
                    "WHERE user_id = %s AND run_type = 'scan' "
                    "ORDER BY created_at DESC LIMIT 1",
                    (user_id,),
                )
                run = cur.fetchone()

                if not run:
                    return

                run_id = run["run_id"]

                # Get all events for this run
                cur.execute(
                    "SELECT event_type, message FROM careerloop.run_events "
                    "WHERE run_id = %s ORDER BY created_at ASC",
                    (run_id,),
                )
                events = cur.fetchall()

                if not events:
                    return

                console.print("\n[bold cyan]── Scan Progress ──[/bold cyan]")
                for e in events:
                    msg = e["message"]
                    etype = e.get("event_type", "info")

                    if "MATCH" in msg or etype == "CANDIDATE_MATCHED":
                        console.print(f"[green]{msg}[/green]")
                    elif "REJECT" in msg or etype == "CANDIDATE_REJECTED":
                        console.print(f"[red]{msg}[/red]")
                    elif "SOURCE" in etype or "Started" in msg or "Starting" in msg:
                        console.print(f"[dim]{msg}[/dim]")
                    elif "FILTER" in etype or "SUMMARY" in etype or "complete" in msg.lower():
                        console.print(f"[bold yellow]{msg}[/bold yellow]")
                    elif "ERROR" in msg or "FAILED" in msg:
                        console.print(f"[bold red]{msg}[/bold red]")
                    elif "BRIEF" in etype or "brief" in msg.lower():
                        console.print(f"[bold green]{msg}[/bold green]")
                    else:
                        console.print(f"[dim]{msg}[/dim]")

                console.print("[bold cyan]── End Scan Progress ──[/bold cyan]\n")
    except Exception as e:
        logger.debug(f"Scan event rendering skipped: {e}")


def main():
    # 1. Authenticate (returns UUID)
    user_id = authenticate_cli_user()

    # 1.5 Ensure background_runs table has required columns
    try:
        from careerloop.memory.connection import get_db_manager
        db = get_db_manager()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                for col, col_type in [("started_at", "TEXT DEFAULT (datetime('now'))"),
                                       ("completed_at", "TEXT")]:
                    try:
                        cur.execute(f"ALTER TABLE background_runs ADD COLUMN {col} {col_type}")
                    except Exception:
                        pass  # column already exists
    except Exception:
        pass

    # 2. Setup systems (session store + supervisor graph with Postgres checkpointer)
    session_store = SessionStore()
    session = session_store.get_session(user_id)  # ensure row exists
    if session.state == UserJourneyState.NEW_USER:
        profile_data = session_store._load_profile_data(user_id)
        is_complete = all(profile_data.get(f) for f in ["target_roles", "target_cities", "salary_expectations", "notice_period", "aggressiveness"]) and bool(profile_data.get("cv_content"))
        if is_complete:
            session.state = UserJourneyState.PROFILE_READY
            session.temp_profile_data = profile_data or session.temp_profile_data
            session_store.save_session(session)

    # Banner: session state
    console.print(f"[dim]user_id={user_id[:12]}... | journey_state={session.state.value}[/dim]")

    # Show latest brief if available
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, date_str FROM careerloop.daily_briefs WHERE user_id = %s ORDER BY date_str DESC LIMIT 1", (user_id,))
                brief = cur.fetchone()
        if brief:
            console.print(f"[dim]latest_brief_id={brief['id'][:12]}... | date={brief['date_str']}[/dim]")
        else:
            console.print(f"[dim]latest_brief_id=none[/dim]")

        # Show active_context from session
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT active_artifact_type, active_artifact_id, active_job_id FROM careerloop.sessions WHERE user_id = %s", (user_id,))
                ctx_row = cur.fetchone()
        if ctx_row and ctx_row.get("active_artifact_type"):
            console.print(f"[dim]active_context: {ctx_row['active_artifact_type']} | job={ctx_row.get('active_job_id', 'none')[:12] if ctx_row.get('active_job_id') else 'none'}[/dim]")
        else:
            console.print(f"[dim]active_context: none[/dim]")
    except Exception:
        pass

    checkpointer_cm = None
    using_checkpointer = False
    try:
        try:
            checkpointer_cm = get_checkpointer()
            checkpointer = checkpointer_cm.__enter__()
            using_checkpointer = True
        except Exception as e:
            logger.warning(f"Checkpointer unavailable; starting CLI without checkpoint persistence: {e}")
            checkpointer = None

        supervisor = get_supervisor_graph(checkpointer=checkpointer)
        transport = TerminalChatAdapter(supervisor_graph=supervisor)

        print_banner()

        # ── Supabase DB Banner ─────────────────────────────────────────
        db_url = os.getenv("DATABASE_URL", "")
        if db_url:
            host = "unknown"
            if "@" in db_url:
                host = db_url.split("@")[-1].split("/")[0]
            elif "://" in db_url:
                host = db_url.split("://")[1].split("/")[0]
            console.print(f"[dim]DB_MODE=supabase | HOST={host}[/dim]")
        else:
            console.print("[bold red]DATABASE_URL not set. CareerLoop requires Supabase.[/bold red]")
            sys.exit(1)

        print_status_card(session)

        if session.state == UserJourneyState.NEW_USER:
            transport.send_text(
                user_id,
                "Welcome to CareerLoop. Paste your CV text to start onboarding.",
            )
        else:
            transport.send_text(user_id, f"Resuming session in state: {session.state.value}")

        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        # 3. Interactive Loop
        while True:
            user_input = transport.request_input(user_id)
            if not user_input:
                continue

            # Check for exit commands
            if user_input.lower() in ['exit', 'quit', '/quit', '/exit']:
                console.print("[bold cyan]Goodbye![/bold cyan]")
                break



            payload = {
                "user_id": user_id,
                "text": user_input,
                "metadata": {
                    "current_state": session.state,
                    "temp_profile_data": get_profile_data(session),
                },
            }
            logger.info("User payload received from input.")
            logger.info(f"Passing payload to transport: {payload}")
            try:
                response = transport.receive(payload)
            except Exception as e:
                err = str(e).lower()
                if using_checkpointer and "prepared statement" in err:
                    console.print(
                        "[bold yellow]Warning:[/bold yellow] Checkpointed invoke failed; switching to non-checkpointed supervisor for this session."
                    )
                    logger.warning("Checkpointed invoke failed with prepared statement error. Falling back to non-checkpointed graph.")
                    supervisor = get_supervisor_graph(checkpointer=None)
                    transport.supervisor_graph = supervisor
                    using_checkpointer = False
                    response = transport.receive(payload)
                else:
                    raise

            # Persist current state from supervisor response into sessions table.
            if response and isinstance(response, dict):
                next_state = response.get("current_state")
                artifact_context = response.get("artifact_context", {})

                if "temp_profile_data" in response:
                    session.temp_profile_data = response.get("temp_profile_data")

                session.active_artifact_type = artifact_context.get("active_artifact_type", session.active_artifact_type)
                session.active_artifact_id = artifact_context.get("active_artifact_id", session.active_artifact_id)
                session.active_job_id = artifact_context.get("active_job_id", session.active_job_id)
                session.active_brief_id = artifact_context.get("active_brief_id", session.active_brief_id)
                session.active_pack_id = artifact_context.get("active_pack_id", session.active_pack_id)
                session.current_selection_index = artifact_context.get("current_selection_index", session.current_selection_index)

                if isinstance(next_state, UserJourneyState):
                    if session.state != next_state:
                        logger.info(f"State updated: {session.state} -> {next_state}")
                    session.state = next_state
                session_store.save_session(session)

            # ── Scan progress display ─────────────────────────────────
            if response and isinstance(response, dict):
                action_taken = response.get("action_taken")
                if action_taken and hasattr(action_taken, 'action_type') and action_taken.action_type.value == "START_SCAN":
                    _render_scan_events(user_id)
    except KeyboardInterrupt:
        console.print("\n[bold red]Exiting CareerLoop. Goodbye![/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]CLI startup failed:[/bold red] {e}")
        sys.exit(1)
    finally:
        if checkpointer_cm is not None and using_checkpointer:
            checkpointer_cm.__exit__(None, None, None)

if __name__ == "__main__":
    main()
