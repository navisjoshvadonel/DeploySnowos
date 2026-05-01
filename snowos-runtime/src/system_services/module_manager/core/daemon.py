import time
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from manifest_parser.parser import ManifestParser
from capability_issuer.issuer import CapabilityIssuer
from sandbox_runtime.python_sandbox import PythonSandbox

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ModuleManager")

class ModuleManagerDaemon:
    def __init__(self):
        self.parser = ManifestParser()
        self.issuer = CapabilityIssuer()
        self.sandbox = PythonSandbox()
        self.active_modules = {}

    def install_and_run(self, module_path):
        logger.info(f"--- Request to install module from: {module_path} ---")
        
        # 1. Parse Manifest
        manifest = self.parser.parse(module_path)
        if not manifest:
            logger.error("Installation aborted: Invalid manifest.")
            return False
            
        module_name = manifest["name"]
        
        # 2. Get Capability Token
        token = self.issuer.request_token(manifest)
        
        # 3. Spawn Sandbox
        process = self.sandbox.execute(module_path, manifest["entry_point"], token)
        if process:
            self.active_modules[module_name] = process
            logger.info(f"Module '{module_name}' running in sandbox (PID: {process.pid})")
            return True
        return False

    def kill_module(self, module_name, reason="Manual Termination"):
        """
        The Kill Switch. Instantly terminates a misbehaving module.
        """
        if module_name in self.active_modules:
            process = self.active_modules[module_name]
            logger.warning(f"KILL SWITCH ACTIVATED for '{module_name}'. Reason: {reason}")
            process.kill()
            del self.active_modules[module_name]
            # Alert SnowControl
            logger.info(f"Module '{module_name}' terminated.")
        else:
            logger.error(f"Cannot kill '{module_name}': Not running.")

if __name__ == "__main__":
    daemon = ModuleManagerDaemon()
    
    # Test execution flow
    module_dir = "/home/develop/snowos/modules/weather_agent"
    
    # Run the module
    success = daemon.install_and_run(module_dir)
    
    if success:
        logger.info("Monitoring active modules... (Simulating 3 seconds of runtime)")
        time.sleep(3)
        
        # Simulate AI Sentinel anomaly detection triggering the kill switch
        daemon.kill_module("weather_agent", reason="AI Sentinel detected anomalous outbound traffic")
