from careerloop.transport.base import TransportAdapter, UserEvent
from prompt_toolkit import prompt
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich import box
import sys
import logging

logger = logging.getLogger(__name__)

class TerminalChatAdapter(TransportAdapter):
    def __init__(self, supervisor_graph=None):
        super().__init__(supervisor_graph)
        self.console = Console()

    def parse_payload(self, raw_payload: dict) -> UserEvent:
        """
        CLI sends raw_payload as a dict: {"user_id": "...", "text": "..."}
        """
        logger.info(f"TerminalChatAdapter parsing raw payload: {raw_payload}")
        user_text = raw_payload.get("text", "")
        logger.info(f"USER: {user_text}")
        return UserEvent(
            user_id=raw_payload.get("user_id", "unknown"),
            text=user_text,
            platform="cli",
            metadata=raw_payload.get("metadata", {})
        )

    def send_text(self, user_id: str, text: str) -> bool:
        if "[SYSTEM_CMD_TRIGGER_SCAN]" in text:
            text = text.replace("[SYSTEM_CMD_TRIGGER_SCAN]", "")
            
        logger.info(f"ASSISTANT: {text}")

        # We print bot messages wrapped in a premium panel with markdown support
        self.console.print(Panel(
            Markdown(text),
            title="🤖 [bold cyan]CareerLoop Assistant[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED
        ))
        
        return True

    def request_input(self, user_id: str, prompt_text: str = "") -> str:
        if prompt_text:
            self.console.print(Panel(
                prompt_text,
                title="🤖 [bold cyan]CareerLoop Prompt[/bold cyan]",
                border_style="cyan",
                box=box.ROUNDED
            ))

        # Non-interactive smoke tests (stdin pipe)
        if not sys.stdin.isatty():
            return input("> ").strip()
            
        self.console.print("\n[dim]> (Type your query and press Enter. For multiline paste, paste your text and press Enter.)[/dim]")
        
        from prompt_toolkit.key_binding import KeyBindings
        kb = KeyBindings()
        
        @kb.add("enter")
        def _(event):
            # Enter immediately submits the query
            event.current_buffer.validate_and_handle()
            
        @kb.add("escape", "enter")
        def _(event):
            # Alt+Enter or Esc+Enter manually inserts a newline
            event.current_buffer.insert_text("\n")
            
        try:
            return prompt("> ", multiline=True, key_bindings=kb).strip()
        except (KeyboardInterrupt, EOFError):
            return "exit"

    def start_loop(self, user_id: str):
        """Helper to run the CLI loop directly routing to the LangGraph Supervisor."""
        self.console.print("[bold green]Welcome to CareerLoop Terminal Chat (LangGraph Orchestrated).[/bold green]")
        try:
            while True:
                user_input = self.request_input(user_id)
                if user_input.lower() in ['exit', 'quit', '/quit']:
                    self.console.print("[bold cyan]Goodbye![/bold cyan]")
                    break
                
                logger.info(f"User payload received: {user_input}")
                payload = {"user_id": user_id, "text": user_input}
                logger.info(f"Passing payload to transport: {payload}")
                # Route message to supervisor via receive
                self.receive(payload)
        except KeyboardInterrupt:
            self.console.print("\n[bold red]Exiting CareerLoop. Goodbye![/bold red]")
