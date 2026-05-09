import json
import os

SYSTEM_CAPABILITIES_FILE = os.environ.get("SNOWOS_CAPABILITIES_FILE", "/etc/snowos/capabilities.json")
LOCAL_CAPABILITIES_FILE = os.path.join(os.path.dirname(__file__), "capabilities.json")

class PolicyEngine:
    def __init__(self):
        self.capabilities = self._load_capabilities()

    def _load_capabilities(self):
        capabilities_file = SYSTEM_CAPABILITIES_FILE if os.path.exists(SYSTEM_CAPABILITIES_FILE) else LOCAL_CAPABILITIES_FILE
        if not os.path.exists(capabilities_file):
            return {}
        with open(capabilities_file, "r") as f:
            return json.load(f)

    def reload(self):
        self.capabilities = self._load_capabilities()

    def evaluate(self, source_id, target_resource, action):
        """
        Evaluate if source_id is allowed to perform action on target_resource.
        """
        app_caps = self.capabilities.get(source_id)
        if not app_caps:
            return False
        
        resource_caps = app_caps.get(target_resource)
        if not resource_caps:
            return False
            
        if action in resource_caps or "*" in resource_caps:
            return True
            
        return False
