import json
import os
import logging

logger = logging.getLogger("ManifestParser")

class ManifestParser:
    @staticmethod
    def parse(module_path):
        manifest_path = os.path.join(module_path, "manifest.json")
        if not os.path.exists(manifest_path):
            logger.error(f"Missing manifest.json in {module_path}")
            return None
            
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                
            required_keys = ["name", "version", "permissions", "entry_point"]
            for key in required_keys:
                if key not in manifest:
                    logger.error(f"Invalid manifest in {module_path}: Missing '{key}'")
                    return None
                    
            logger.info(f"Successfully parsed manifest for module: {manifest['name']}")
            return manifest
            
        except Exception as e:
            logger.error(f"Failed to parse manifest: {e}")
            return None
