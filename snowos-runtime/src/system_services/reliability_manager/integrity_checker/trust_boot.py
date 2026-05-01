import hashlib
import json
import logging
import os

logger = logging.getLogger("TrustBoot")

# Simulated manifest of known-good hashes
MANIFEST = {
    "/home/develop/snowos/system_services/permission_broker/capabilities.json": "EXPECTED_HASH_PLACEHOLDER"
}

class TrustBoot:
    def __init__(self):
        # We will dynamically calculate the good hash for the prototype
        if os.path.exists(list(MANIFEST.keys())[0]):
            MANIFEST[list(MANIFEST.keys())[0]] = self._hash_file(list(MANIFEST.keys())[0])

    def _hash_file(self, file_path):
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                buf = f.read()
                hasher.update(buf)
            return hasher.hexdigest()
        except FileNotFoundError:
            return None

    def verify_system_integrity(self):
        """
        Hashes core configuration and daemons. If any fail, returns False.
        """
        logger.info("Initiating Trust Boot Integrity Check...")
        
        for file_path, expected_hash in MANIFEST.items():
            actual_hash = self._hash_file(file_path)
            
            if not actual_hash:
                logger.error(f"Integrity Check Failed: Missing critical file {file_path}")
                return False
                
            if actual_hash != expected_hash:
                logger.critical(f"INTEGRITY VIOLATION: {file_path} has been tampered with or corrupted.")
                logger.debug(f"Expected: {expected_hash} | Actual: {actual_hash}")
                return False
                
        logger.info("Integrity Check Passed. System safe to boot.")
        return True
