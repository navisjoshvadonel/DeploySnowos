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

            if not isinstance(manifest["name"], str) or not manifest["name"].strip():
                logger.error("Invalid manifest in %s: invalid module name", module_path)
                return None
            if not isinstance(manifest["permissions"], dict):
                logger.error("Invalid manifest in %s: permissions must be an object", module_path)
                return None
            entry_point = manifest["entry_point"]
            if not isinstance(entry_point, str) or os.path.isabs(entry_point):
                logger.error("Invalid manifest in %s: entry point must be relative", module_path)
                return None
            module_root = os.path.realpath(module_path)
            entry_path = os.path.realpath(os.path.join(module_root, entry_point))
            if os.path.commonpath([module_root, entry_path]) != module_root or not os.path.isfile(entry_path):
                logger.error("Invalid manifest in %s: entry point is not a module file", module_path)
                return None
                    
            logger.info(f"Successfully parsed manifest for module: {manifest['name']}")
            return manifest
            
        except Exception as e:
            logger.error(f"Failed to parse manifest: {e}")
            return None
