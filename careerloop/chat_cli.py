import os
import sys
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Support running as script (python careerloop/chat_cli.py) and module (-m careerloop.chat_cli)
if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from careerloop.session.session_store import SessionStore
from careerloop.session.states import UserState
from careerloop.transport.terminal_chat import TerminalChatAdapter
from careerloop.session.supervisor_graph import get_supervisor_graph
from careerloop.memory.checkpointer import get_checkpointer
from rich.console import Console
console = Console()

def authenticate_cli_user() -> str:
    """
    Mock authentication for the CLI that returns a UUID.
    In a full implementation, this uses supabase.auth.sign_in_with_password()
    and retrieves the user's UUID from the JWT.
    """
    console.print("[bold green]Welcome to CareerLoop Terminal Chat.[/bold green]")
    console.print("Please enter your email to login or sign up:")
    email = input("> ").strip()
    
    if not email:
        console.print("[bold red]Email is required.[/bold red]")
        sys.exit(1)
        
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
                    INSERT INTO public.users (id, email, full_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (user_uuid, email, email.split('@')[0]))
            conn.commit()
    except Exception as e:
        console.print(f"[bold yellow]Warning:[/bold yellow] Could not create user in Supabase: {e}")
        console.print("Make sure you ran the migration or schema script. Continuing in local-only mode.")

    return user_uuid

def main():
    # 1. Authenticate (returns UUID)
    user_id = authenticate_cli_user()

    # 2. Setup systems (session store + supervisor graph with Postgres checkpointer)
    session_store = SessionStore()
    session = session_store.get_session(user_id)  # ensure row exists

    try:
        with get_checkpointer() as checkpointer:
            supervisor = get_supervisor_graph(checkpointer=checkpointer)
            transport = TerminalChatAdapter(supervisor_graph=supervisor)
            using_checkpointer = True

            if session.state == UserState.IDLE:
                transport.send_text(
                    user_id,
                    "Welcome to CareerLoop. Paste your CV text to start onboarding.",
                )
            else:
                transport.send_text(user_id, f"Resuming session in state: {session.state.value}")

            # 3. Interactive Loop
            while True:
                user_input = transport.request_input(user_id)
                if user_input.lower() in ['exit', 'quit', '/quit']:
                    console.print("[bold cyan]Goodbye![/bold cyan]")
                    break

                payload = {
                    "user_id": user_id,
                    "text": user_input,
                    "metadata": {"current_state": session.state},
                }
                try:
                    response = transport.receive(payload)
                except Exception as e:
                    err = str(e).lower()
                    if using_checkpointer and "prepared statement" in err:
                        console.print(
                            "[bold yellow]Warning:[/bold yellow] Checkpointed invoke failed; switching to non-checkpointed supervisor for this session."
                        )
                        supervisor = get_supervisor_graph(checkpointer=None)
                        transport.supervisor_graph = supervisor
                        using_checkpointer = False
                        response = transport.receive(payload)
                    else:
                        raise

                # Persist current state from supervisor response into sessions table.
                if response and isinstance(response, dict):
                    next_state = response.get("current_state")
                    if isinstance(next_state, UserState):
                        session.state = next_state
                        session_store.save_session(session)
    except KeyboardInterrupt:
        console.print("\n[bold red]Exiting CareerLoop. Goodbye![/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]CLI startup failed:[/bold red] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
