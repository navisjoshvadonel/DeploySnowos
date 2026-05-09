"""
SnowOS Runtime — ConfigManager
================================
Extracted from nyx.py (Stage 25).

Manages the Nyx runtime configuration file, providing typed get/set access
with persistent JSON storage and secure auto-generation of secrets.
"""

import os
import json
import secrets
import uuid


class ConfigManager:
    """
    Persistent runtime configuration with safe defaults.

    Secrets (api_key, node_id) are auto-generated on first run using
    cryptographically secure functions and persisted to config.json.
    """

    DEFAULT_CONFIG = {
        "max_workers": 3,
        "sandbox_enabled": True,
        "auto_improve": False,
        "api_enabled": False,
        "api_port": 8080,
        "api_key": None,   # Auto-generated on first run
        "node_id": None,   # Auto-generated on first run
    }

    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.config_path = os.path.join(config_dir, "config.json")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config = self._load()

        if not self.config.get("api_key"):
            self.config["api_key"] = secrets.token_urlsafe(24)
            self._save()

        if not self.config.get("node_id"):
            self.config["node_id"] = str(uuid.uuid4())
            self._save()

    def _load(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                    return {**self.DEFAULT_CONFIG, **data}
            except Exception:
                pass
        return dict(self.DEFAULT_CONFIG)

    def _save(self):
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value):
        self.config[key] = value
        self._save()
