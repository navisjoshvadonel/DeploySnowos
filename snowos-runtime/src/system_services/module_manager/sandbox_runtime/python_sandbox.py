import subprocess
import os
import logging

logger = logging.getLogger("PythonSandbox")

class PythonSandbox:
    def __init__(self):
        pass

    def execute(self, module_path, entry_point, token):
        """
        Executes the module in an isolated subprocess.
        Passes the capability token as the ONLY environment variable.
        """
        script_path = os.path.join(module_path, entry_point)
        
        # Isolation: Provide only the specific token, drop PATH and standard env vars
        # In a real environment, we'd also restrict network namespaces and drop privileges.
        env = {
            "SNOWOS_TOKEN": token
        }
        
        logger.info(f"Spawning sandboxed process for {script_path}")
        
        try:
            # We use Popen so we don't block the daemon and can manage the lifecycle
            process = subprocess.Popen(
                ["python3", script_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return process
        except Exception as e:
            logger.error(f"Failed to spawn module sandbox: {e}")
            return None
