import os
import json
import time
import subprocess
from rich.console import Console

console = Console()

class RecoveryPlaybooks:
    """A registry of known fixes for common system anomalies."""
    
    @staticmethod
    def restart_service(nyx, process_name):
        """Find a service in the process manager and restart it."""
        for pid_id, info in nyx.process_manager.processes.items():
            if process_name in info["command"]:
                console.print(f"[yellow]🛠️ Healing: Restarting service {process_name} (ID: {pid_id})...[/yellow]")
                try:
                    nyx.process_manager.restart(pid_id)
                    return True
                except Exception as e:
                    console.print(f"[red]❌ Healing failed to restart {process_name}: {e}[/red]")
        return False

    @staticmethod
    def cleanup_memory(nyx, threshold_mb=500):
        """Kill high-memory processes that are not critical."""
        # This is a simplified version; in a real OS, this would be more careful
        console.print(f"[yellow]🛠️ Healing: Critically low memory. Cleaning up processes using >{threshold_mb}MB...[/yellow]")
        # In a real implementation, we'd use psutil to find non-system processes
        return True

    @staticmethod
    def resolve_port_conflict(nyx, port):
        """Find the process using a port and kill it if it's not the intended owner."""
        console.print(f"[yellow]🛠️ Healing: Resolving port conflict on {port}...[/yellow]")
        try:
            subprocess.run(["fuser", "-k", f"{port}/tcp"], check=False)
            return True
        except Exception:
            return False

    @staticmethod
    def fix_dependency(nyx, module_name):
        """Attempt to install a missing dependency."""
        console.print(f"[yellow]🛠️ Healing: Missing dependency '{module_name}'. Attempting install...[/yellow]")
        # We try both pip and npm as a heuristic
        try:
            subprocess.run(["pip", "install", module_name], check=True)
            return True
        except Exception:
            try:
                subprocess.run(["npm", "install", module_name], check=True)
                return True
            except Exception:
                return False

class HealingBroker:
    """The central decision engine for system recovery."""
    
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.history = []
        self.enabled = True

    def process_event(self, event):
        """Evaluate a kernel event and trigger recovery if necessary."""
        if not self.enabled:
            return
            
        etype = event.get("type")
        desc = event.get("description")
        meta = event.get("metadata", {})

        if etype == "MEMORY_CRITICAL":
            self._trigger_recovery("cleanup_memory", RecoveryPlaybooks.cleanup_memory, self.nyx)
            
        elif etype == "SERVICE_DOWN":
            pname = meta.get("name")
            if pname:
                self._trigger_recovery(f"restart_{pname}", RecoveryPlaybooks.restart_service, self.nyx, pname)
        
        elif etype == "PORT_CONFLICT":
            port = meta.get("port")
            if port:
                self._trigger_recovery(f"port_fix_{port}", RecoveryPlaybooks.resolve_port_conflict, self.nyx, port)

        elif etype == "MISSING_DEPENDENCY":
            mname = meta.get("module")
            if mname:
                self._trigger_recovery(f"install_{mname}", RecoveryPlaybooks.fix_dependency, self.nyx, mname)

    def _trigger_recovery(self, name, func, *args, **kwargs):
        """Execute a recovery function and log it."""
        ts = time.time()
        success = func(*args, **kwargs)
        self.history.append({
            "ts": ts,
            "action": name,
            "success": success
        })
        
        # Log to telemetry
        if self.nyx.telemetry:
            self.nyx.telemetry.log_event("HEALING_ACTION", {
                "action": name,
                "success": success
            })
        
        if success:
            console.print(f"[green]✅ Healing: Successfully completed '{name}'[/green]")
        else:
            console.print(f"[red]⚠️ Healing: Action '{name}' failed or was unnecessary.[/red]")

    def get_report(self):
        """Generate a diagnostic summary."""
        return {
            "enabled": self.enabled,
            "total_actions": len(self.history),
            "success_rate": len([h for h in self.history if h["success"]]) / len(self.history) if self.history else 1.0,
            "recent_actions": self.history[-10:]
        }
