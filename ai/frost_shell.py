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
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.formatted_text import HTML

try:
    from kernel.dbus_bridge import DBusBridge
    _DBUS_AVAIL = True
except ImportError:
    _DBUS_AVAIL = False

import threading
import subprocess

def _speak(text: str):
    """Vocal Ambient Companion: Synthesize speech natively."""
    def run_speak():
        try:
            subprocess.run(["spd-say", "-t", "female1", text], check=True, stderr=subprocess.DEVNULL)
        except Exception:
            try:
                subprocess.run(["espeak", "-v", "en+f3", text], check=True, stderr=subprocess.DEVNULL)
            except Exception:
                pass
    threading.Thread(target=run_speak, daemon=True).start()

class GhostAutoSuggest(AutoSuggest):
    def __init__(self, shell):
        self.shell = shell
        
    def get_suggestion(self, buffer, document):
        text = document.text
        if not text:
            return None
            
        suggestion = self.shell._get_ghost_suggestion(text)
        if suggestion and suggestion.startswith(text):
            return Suggestion(suggestion[len(text):])
        return None

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
            return ""
        
        # Simple history match
        for past in reversed(self.nyx.state.last_commands):
            if past.startswith(current_input) and past != current_input:
                return past
                
        # EMG match
        if hasattr(self.nyx, "emg") and self.nyx.emg:
            recent_nodes = list(self.nyx.emg.graph.get("nodes", {}).values())[-20:]
            for node in reversed(recent_nodes):
                if node.get("type") == "command":
                    cmd = node.get("metadata", {}).get("cmd", "")
                    if cmd.startswith(current_input) and cmd != current_input:
                        return cmd
                        
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

        session = PromptSession(auto_suggest=GhostAutoSuggest(self))

        while True:
            try:
                cwd = os.getcwd().replace(os.path.expanduser("~"), "~")
                tokens = self.nyx.ui_state.state.get("aesthetic_tokens", [])
                token_str = " | ".join(tokens)
                
                # Dynamic prompt based on tokens
                prompt_color = "cyan"
                if "high_stress" in tokens:
                    prompt_color = "red"
                elif "deep_freeze" in tokens:
                    prompt_color = "blue"

                prompt_html = HTML(f'<style bg="black" fg="white"> {token_str} </style> <{prompt_color}>{cwd}</{prompt_color}> <bold {prompt_color}>❯</bold> ')

                # Real-time suggestions via GhostAutoSuggest
                user_input = session.prompt(prompt_html)

                if user_input.lower() in ["exit", "quit", "shutdown"]:
                    self.console.print("[yellow]❄️  Freezing SnowOS state... Goodbye.[/yellow]")
                    break

                if not user_input.strip():
                    continue

                if "clean up my desktop" in user_input.lower() or "purge desktop" in user_input.lower():
                    self.console.print("[cyan]❄️  Frostbite: Checking access logs for Desktop purge...[/cyan]")
                    try:
                        import socket, json
                        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        s.connect("/run/snowos/nyxvfs.sock")
                        s.sendall(json.dumps({"action": "purge_desktop"}).encode())
                        data = s.recv(4096)
                        s.close()
                        resp = json.loads(data.decode())
                        stats = resp.get("data", {})
                        purged = stats.get("purged", 0)
                        kept = stats.get("kept", 0)
                        self.console.print(f"[green]✔ Swept {purged} stale files to Archive vault. Kept {kept} active files.[/green]")
                    except Exception as e:
                        self.console.print(f"[red]❌ Error contacting NyxVFS: {e}[/red]")
                    continue

                if "time to game" in user_input.lower() or "casual mode" in user_input.lower():
                    self.console.print("[cyan]❄️  Frostbite: Engaging Casual/Gaming Profile...[/cyan]")
                    try:
                        import socket, json
                        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        s.connect("/run/snowos/nyxvfs.sock")
                        s.sendall(json.dumps({"action": "switch_profile", "target_mode": "gaming"}).encode())
                        data = s.recv(4096)
                        s.close()
                        resp = json.loads(data.decode())
                        stashed = len(resp.get("data", {}).get("stashed_apps", []))
                        resumed = len(resp.get("data", {}).get("resumed_apps", []))
                        self.console.print(f"[green]✔ Gaming mode active. Stashed {stashed} dev apps. Restored {resumed} game apps.[/green]")
                        _speak("Switching to Gaming Mode. Pre-fetching assets and clearing memory caches.")
                    except Exception as e:
                        self.console.print(f"[red]❌ Error contacting NyxVFS: {e}[/red]")
                    continue

                if "let's work" in user_input.lower() or "student mode" in user_input.lower() or "dev mode" in user_input.lower():
                    self.console.print("[cyan]❄️  Frostbite: Engaging Student/Dev Profile...[/cyan]")
                    try:
                        import socket, json
                        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        s.connect("/run/snowos/nyxvfs.sock")
                        s.sendall(json.dumps({"action": "switch_profile", "target_mode": "student"}).encode())
                        data = s.recv(4096)
                        s.close()
                        resp = json.loads(data.decode())
                        stashed = len(resp.get("data", {}).get("stashed_apps", []))
                        resumed = len(resp.get("data", {}).get("resumed_apps", []))
                        self.console.print(f"[green]✔ Dev mode active. Stashed {stashed} game apps. Restored {resumed} dev apps.[/green]")
                        _speak("Welcome back to Dev Mode. Restoring development workspace.")
                    except Exception as e:
                        self.console.print(f"[red]❌ Error contacting NyxVFS: {e}[/red]")
                    continue

                # DBus Introspection & Control Triggers
                dbus_handled = False
                if _DBUS_AVAIL:
                    cmd_lower = user_input.lower().strip()
                    bridge = DBusBridge()
                    
                    if cmd_lower in ["pause music", "stop music", "mute player"]:
                        self.console.print("[cyan]❄️  Frostbite: Stopping active MPRIS media players via DBus...[/cyan]")
                        res = bridge.media_control("pause")
                        self.console.print(f"[green]✔ DBus response: {res}[/green]")
                        dbus_handled = True
                    elif cmd_lower in ["play music", "resume music", "start player"]:
                        self.console.print("[cyan]❄️  Frostbite: Starting active MPRIS media players via DBus...[/cyan]")
                        res = bridge.media_control("play")
                        self.console.print(f"[green]✔ DBus response: {res}[/green]")
                        dbus_handled = True
                    elif cmd_lower in ["next song", "next track"]:
                        self.console.print("[cyan]❄️  Frostbite: Next track...[/cyan]")
                        res = bridge.media_control("next")
                        self.console.print(f"[green]✔ DBus response: {res}[/green]")
                        dbus_handled = True
                    elif cmd_lower in ["prev song", "previous song", "prev track"]:
                        self.console.print("[cyan]❄️  Frostbite: Previous track...[/cyan]")
                        res = bridge.media_control("previous")
                        self.console.print(f"[green]✔ DBus response: {res}[/green]")
                        dbus_handled = True
                    elif cmd_lower in ["scan dbus", "discover apps", "list dbus services"]:
                        self.console.print("[cyan]❄️  Frostbite: Querying active session bus services...[/cyan]")
                        res = bridge.discover_services()
                        self.console.print(Panel(json.dumps(res, indent=2), title="DBus App Discovery"))
                        dbus_handled = True
                    elif cmd_lower.startswith("introspect dbus "):
                        srv = user_input.split("introspect dbus ")[-1].strip()
                        self.console.print(f"[cyan]❄️  Frostbite: Introspecting active interface on '{srv}'...[/cyan]")
                        res = bridge.introspect(srv)
                        self.console.print(Panel(json.dumps(res, indent=2), title="DBus Introspector"))
                        dbus_handled = True
                        
                if dbus_handled:
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
            except EOFError:
                break
            except Exception as e:
                self.console.print(f"[red]❌ Shell Error: {e}[/red]")

    def _status_display(self, msg: str):
        stress = self.nyx.ui_state.state.get("system_stress", 0.0)
        bar = "█" * int(stress * 10) + "░" * (10 - int(stress * 10))
        return Panel(
            f"[bold cyan]Nyx Brain:[/bold cyan] {msg}\n[dim]Stress: [{bar}] {stress*100:.1f}%[/dim]",
            border_style="dim"
        )
