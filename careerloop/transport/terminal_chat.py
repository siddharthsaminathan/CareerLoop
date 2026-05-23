from careerloop.transport.base import TransportAdapter, UserEvent
from prompt_toolkit import prompt
from rich.console import Console
from rich.markdown import Markdown
import sys

class TerminalChatAdapter(TransportAdapter):
    def __init__(self, supervisor_graph=None):
        super().__init__(supervisor_graph)
        self.console = Console()

    def parse_payload(self, raw_payload: dict) -> UserEvent:
        """
        CLI sends raw_payload as a dict: {"user_id": "...", "text": "..."}
        """
        return UserEvent(
            user_id=raw_payload.get("user_id", "unknown"),
            text=raw_payload.get("text", ""),
            platform="cli",
            metadata={}
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

        self.console.print("\n[dim]> (Type your text and press Enter)[/dim]")
        # Non-interactive smoke tests (stdin pipe) are not compatible with prompt_toolkit.
        if not sys.stdin.isatty():
            return input("> ").strip()
        return prompt("> ", multiline=False).strip()

    def start_loop(self, user_id: str):
        """Helper to run the CLI loop directly routing to the LangGraph Supervisor."""
        self.console.print("[bold green]Welcome to CareerLoop Terminal Chat (LangGraph Orchestrated).[/bold green]")
        try:
            while True:
                user_input = self.request_input(user_id)
                if user_input.lower() in ['exit', 'quit', '/quit']:
                    self.console.print("[bold cyan]Goodbye![/bold cyan]")
                    break
                
                # Route message to supervisor via receive
                self.receive({"user_id": user_id, "text": user_input})
        except KeyboardInterrupt:
            self.console.print("\n[bold red]Exiting CareerLoop. Goodbye![/bold red]")
