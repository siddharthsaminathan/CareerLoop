from careerloop.transport.base import TransportAdapter, UserEvent
from prompt_toolkit import prompt
from rich.console import Console
from rich.markdown import Markdown
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
        return UserEvent(
            user_id=raw_payload.get("user_id", "unknown"),
            text=raw_payload.get("text", ""),
            platform="cli",
            metadata=raw_payload.get("metadata", {})
        )

    def send_text(self, user_id: str, text: str) -> bool:
        if "[SYSTEM_CMD_TRIGGER_SCAN]" in text:
            text = text.replace("[SYSTEM_CMD_TRIGGER_SCAN]", "")
            
        # We print bot messages with a distinctive prefix and markdown support
        self.console.print("\n🤖 [bold cyan]CareerLoop:[/bold cyan]")
        self.console.print(Markdown(text))
        
        return True

    def request_input(self, user_id: str, prompt_text: str = "") -> str:
        if prompt_text:
            self.console.print(f"\n🤖 [bold cyan]CareerLoop:[/bold cyan] {prompt_text}")

        self.console.print("\n[dim]> (Type or paste your text. Press Enter TWICE to submit)[/dim]")
        
        # Non-interactive smoke tests (stdin pipe)
        if not sys.stdin.isatty():
            return input("> ").strip()
            
        lines = []
        while True:
            try:
                line = input("> " if not lines else "... ")
                if not line and lines:
                    break # empty line signifies end of input
                lines.append(line)
                # If they only typed one short line and want to submit, they must hit enter again.
                # But for single-line questions, maybe it's annoying. 
                # Still, it's foolproof for pasting.
            except EOFError:
                break
        return "\n".join(lines).strip()

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
