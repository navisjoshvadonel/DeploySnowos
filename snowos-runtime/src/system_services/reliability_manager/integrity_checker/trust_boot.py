import hashlib
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("TrustBoot")

CAPABILITIES_FILE = os.environ.get("SNOWOS_CAPABILITIES_FILE", "/etc/snowos/capabilities.json")
BOOT_MANIFEST_FILE = os.environ.get("SNOWOS_BOOT_MANIFEST_FILE", "/etc/snowos/boot_manifest.json")
AI_FEATURES_FILE = os.environ.get("SNOWOS_AI_FEATURES_FILE", "/etc/snowos/ai_features.json")
BRAND_FILE = os.environ.get("SNOWOS_BRAND_FILE", "/etc/snowos/brand.json")
INTEGRITY_MANIFEST_FILE = os.environ.get(
    "SNOWOS_INTEGRITY_MANIFEST_FILE",
    "/etc/snowos/integrity_manifest.json",
)
DEFAULT_TRACKED_FILES = [
    CAPABILITIES_FILE,
    BOOT_MANIFEST_FILE,
    AI_FEATURES_FILE,
    BRAND_FILE,
]


class TrustBoot:
    def _hash_file(self, file_path):
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as handle:
                hasher.update(handle.read())
        except FileNotFoundError:
            return None
        return hasher.hexdigest()

    def _load_integrity_manifest(self):
        if not os.path.exists(INTEGRITY_MANIFEST_FILE):
            return None

        try:
            with open(INTEGRITY_MANIFEST_FILE, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load integrity manifest %s: %s", INTEGRITY_MANIFEST_FILE, exc)
            return None

    def inspect_system_integrity(self):
        """
        Returns a structured integrity report for the current SnowOS boot state.
        """
        logger.info("Initiating Trust Boot Integrity Check...")

        manifest = self._load_integrity_manifest()
        checks = []
        trusted = True

        if manifest and manifest.get("tracked_files"):
            mode = "hash"
            tracked_files = manifest["tracked_files"]
        else:
            mode = "presence"
            tracked_files = [{"path": path} for path in DEFAULT_TRACKED_FILES]
            logger.warning(
                "Integrity manifest missing or unreadable. Falling back to presence checks for SnowOS boot."
            )

        for entry in tracked_files:
            file_path = entry.get("path")
            expected_hash = entry.get("sha256")
            actual_hash = self._hash_file(file_path)

            if not actual_hash:
                checks.append(
                    {
                        "path": file_path,
                        "status": "missing",
                        "expected_hash": expected_hash,
                        "actual_hash": None,
                    }
                )
                logger.error("Integrity Check Failed: Missing critical file %s", file_path)
                trusted = False
                continue

            if expected_hash and actual_hash != expected_hash:
                checks.append(
                    {
                        "path": file_path,
                        "status": "mismatch",
                        "expected_hash": expected_hash,
                        "actual_hash": actual_hash,
                    }
                )
                logger.critical("INTEGRITY VIOLATION: %s has drifted from the expected baseline.", file_path)
                trusted = False
                continue

            checks.append(
                {
                    "path": file_path,
                    "status": "ok",
                    "expected_hash": expected_hash,
                    "actual_hash": actual_hash,
                }
            )

        report = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "trusted": trusted,
            "mode": mode,
            "manifest_path": INTEGRITY_MANIFEST_FILE,
            "manifest_loaded": bool(manifest and manifest.get("tracked_files")),
            "checks": checks,
        }

        if trusted:
            logger.info("Integrity Check Passed. System safe to boot.")
        return report

    def verify_system_integrity(self):
        return self.inspect_system_integrity()["trusted"]
