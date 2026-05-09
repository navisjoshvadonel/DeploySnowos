"""
SnowOS Runtime — PluginManager
================================
Extracted from nyx.py (Stage 25).

Discovers, validates, and loads plugins from a directory. Each plugin
is a subdirectory containing a plugin.json manifest and an optional main.py
entry point. Plugins can register intent patterns and inject logic into Nyx.
"""

import os
import sys
import importlib.util
import logging

logger = logging.getLogger("SnowOS.PluginManager")


class PluginManager:
    """
    Loads SnowOS plugins from a directory.

    Plugin contract:
        <plugin_name>/
            plugin.json   — required: {"name": "...", "intents": {...}, "permissions": [...]}
            main.py       — optional: must expose an init(nyx_agent) function
    """

    def __init__(self, plugins_dir: str, registry, nyx_agent):
        self.plugins_dir = plugins_dir
        self.registry = registry
        self.nyx = nyx_agent
        self.loaded_plugins: list[dict] = []
        os.makedirs(self.plugins_dir, exist_ok=True)

    def load_all(self):
        """Discover and load all valid plugins in the plugins directory."""
        for name in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, name)
            if os.path.isdir(plugin_path):
                self._load_plugin(plugin_path, name)

    def _load_plugin(self, path: str, name: str):
        import json
        config_path = os.path.join(path, "plugin.json")
        main_path = os.path.join(path, "main.py")

        if not os.path.exists(config_path):
            return

        try:
            with open(config_path) as f:
                meta = json.load(f)

            # Register intent patterns from the manifest
            intents = meta.get("intents", {})
            for module, mapping in intents.items():
                for pattern, cmd in mapping.items():
                    self.registry.register(f"plugin:{name}:{module}", pattern, cmd)

            self.loaded_plugins.append(meta)

            # Load dynamic logic module
            if os.path.exists(main_path):
                spec = importlib.util.spec_from_file_location(f"nyx.plugins.{name}", main_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"nyx.plugins.{name}"] = module
                spec.loader.exec_module(module)
                if hasattr(module, "init"):
                    module.init(self.nyx)

            logger.info("Loaded plugin: %s", name)

        except Exception as e:
            logger.error("Failed to load plugin %s: %s", name, e)
