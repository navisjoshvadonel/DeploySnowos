import subprocess
import os

class CgroupEnforcer:
    @staticmethod
    def wrap_command(cmd, task_id, limits):
        """
        Wraps a command with systemd-run to enforce resource limits.
        Example: systemd-run --user --scope -p CPUQuota=20% -p MemoryMax=512M ...
        """
        # We use --user because Nyx might not have root.
        # If it has root, we could use system slices.
        
        prefix = ["systemd-run", "--user", "--scope", f"--unit=nyx-task-{task_id}"]
        
        if "cpu_quota" in limits:
            prefix.append(f"-p")
            prefix.append(f"CPUQuota={limits['cpu_quota']}%")
            
        if "memory_limit" in limits:
            prefix.append(f"-p")
            prefix.append(f"MemoryMax={limits['memory_limit']}")
            
        # Add a property to ensure the task is cleaned up
        prefix.append("-p")
        prefix.append("CollectMode=inactive-or-failed")
        
        return " ".join(prefix) + " " + cmd

    @staticmethod
    def is_systemd_available():
        try:
            subprocess.run(["systemctl", "--user", "is-system-running"], 
                           capture_output=True, check=False)
            return True
        except FileNotFoundError:
            return False
