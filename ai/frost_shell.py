import os
import sys
import time
import json
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.markdown import Markdown

class FrostShell:
    """The AI-Native Shell for SnowOS.
    Features: Semantic understanding, Ghost suggestions, and Ambient Awareness.
    """
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.console = Console()
        self.history = []

    def _get_ghost_suggestion(self, current_input: str) -> str:
        """Heuristic for next-step suggestions based on history and EMG."""
        if not current_input:
            # Suggest based on current intent
            intent = self.nyx.ui_state.state.get("user_intent", "idle")
            if intent == "coding":
                return "list files"
            return "system status"
        
        # Simple history match
        for past in reversed(self.nyx.state.last_commands):
            if past.startswith(current_input) and past != current_input:
                return past
        return ""

    def run(self):
        self.console.clear()
        self.console.print(Panel(
            Text.assemble(
                ("❄️  FrostShell ", "bold cyan"),
                ("v1.0.0-sentient", "dim cyan"),
                ("\nThe OS that thinks with you.", "italic white")
            ),
            border_style="cyan",
            padding=(1, 2)
        ))

        # Show Behavioral Insights
        suggestions = self.nyx.memory_engine.get_suggestions()
        if suggestions:
            self.console.print("\n[bold magenta]🧠 Nyx Insight:[/bold magenta]")
            for s in suggestions:
                # Analyze trust/confidence
                raw_cmd = s.replace("Resume ", "").replace("Run ", "").replace("?", "")
                analysis = self.nyx.trust.analyze_prediction(raw_cmd)
                conf_pct = int(analysis.get('confidence', 0) * 100)
                
                self.console.print(f"  [italic]→ {s}[/italic] [dim]({conf_pct}% confidence)[/dim]")
                self.console.print(f"    [dim]Reason: {analysis.get('reason')}[/dim]")
            self.console.print("")

        while True:
            try:
                cwd = os.getcwd().replace(os.path.expanduser("~"), "~")
                tokens = self.nyx.ui_state.state.get("aesthetic_tokens", [])
                token_str = " | ".join(tokens)
                
                # Dynamic prompt based on tokens
                prompt_style = "bold cyan"
                if "high_stress" in tokens:
                    prompt_style = "bold red"
                elif "deep_freeze" in tokens:
                    prompt_style = "bold blue"

                prompt = Text.assemble(
                    (f" {token_str} ", "dim white on black"),
                    (" ", ""),
                    (f"{cwd}", "blue"),
                    (" ❯ ", prompt_style)
                )

                # Real-time suggestions (simulated for now)
                user_input = Prompt.ask(prompt)

                if user_input.lower() in ["exit", "quit", "shutdown"]:
                    self.console.print("[yellow]❄️  Freezing SnowOS state... Goodbye.[/yellow]")
                    break

                if not user_input.strip():
                    continue

                # Process command through Nyx (the AI core)
                with Live(self._status_display("Thinking..."), refresh_per_second=4) as live:
                    # In a real shell, this would be the primary way to run commands
                    # Nyx.process handles natural language vs shell commands
                    self.nyx.process(user_input)
                    live.update(self._status_display("Ready."))

            except KeyboardInterrupt:
                print()
                continue
            except Exception as e:
                self.console.print(f"[red]❌ Shell Error: {e}[/red]")

    def _status_display(self, msg: str):
        stress = self.nyx.ui_state.state.get("system_stress", 0.0)
        bar = "█" * int(stress * 10) + "░" * (10 - int(stress * 10))
        return Panel(
            f"[bold cyan]Nyx Brain:[/bold cyan] {msg}\n[dim]Stress: [{bar}] {stress*100:.1f}%[/dim]",
            border_style="dim"
        )
