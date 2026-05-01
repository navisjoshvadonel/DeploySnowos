import os
import psutil
from rich.console import Console

console = Console()

class ResourceArbitrator:
    """Manages system resource prioritization based on user intent."""
    
    PERSONAS = {
        "coding": {
            "priority_names": ["python", "node", "gcc", "g++", "make", "docker", "code"],
            "nice_value": -5,
            "io_class": psutil.IOPRIO_CLASS_RT
        },
        "browsing": {
            "priority_names": ["chrome", "firefox", "brave"],
            "nice_value": -2,
            "io_class": psutil.IOPRIO_CLASS_BE
        },
        "media": {
            "priority_names": ["vlc", "mpv", "spotify"],
            "nice_value": -10, # Very high for no stutter
            "io_class": psutil.IOPRIO_CLASS_RT
        },
        "idle": {
            "priority_names": [],
            "nice_value": 0,
            "io_class": psutil.IOPRIO_CLASS_BE
        }
    }

    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.current_persona = "idle"

    def apply_persona(self, intent):
        """Apply a resource persona to the system."""
        if intent not in self.PERSONAS:
            intent = "idle"
            
        if intent == self.current_persona:
            return
            
        self.current_persona = intent
        console.print(f"[bold cyan]⚖️ Arbitration: Applying '{intent}' persona to system resources...[/bold cyan]")
        
        persona = self.PERSONAS[intent]
        
        # 1. Update Niceness for relevant processes
        for proc in psutil.process_iter(['name', 'nice']):
            try:
                name = proc.info['name'].lower()
                for target in persona["priority_names"]:
                    if target in name:
                        # Set high priority
                        proc.nice(persona["nice_value"])
                        # Set IO priority if possible
                        try:
                            proc.ionice(persona["io_class"])
                        except Exception: pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        # 2. Throttling non-essential Nyx tasks if in power save (future)
        
        self.nyx.telemetry.log_event("ARBITRATION_PERSONA_SWITCH", {"persona": intent})

    def rebalance(self):
        """Periodic check to ensure priorities are still correct."""
        # In a real OS, this would ensure no process stays at high priority too long
        pass
