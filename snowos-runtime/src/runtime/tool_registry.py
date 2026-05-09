"""
SnowOS Runtime — ToolRegistry
================================
Extracted from nyx.py (Stage 18).

Maps natural-language intent patterns (regex) to Snow CLI commands.
Supports built-in defaults and runtime plugin registration.
"""

import re
import json
import os
import logging

logger = logging.getLogger("SnowOS.ToolRegistry")


class ToolRegistry:
    """
    Maps natural-language intent patterns (regex) to Snow CLI commands.

    Patterns are grouped by module (e.g., "files", "dev", "system").
    Both built-in and plugin-registered patterns are supported.
    """

    DEFAULT_TOOLS: dict[str, dict[str, str]] = {
        "files": {
            r"^(?:list|show) files?$": "snow files list",
            r"^find file (.+)$": "snow files find '{0}'",
        },
        "dev": {
            r"^create python project$": "snow dev python",
            r"^setup python environment$": "snow dev python",
            r"^init git$": "snow dev git",
        },
        "system": {
            r"^(?:system|show) status$": "snow status",
        },
    }

    def __init__(self, tools_file: str):
        self.tools: dict[str, dict[str, str]] = {k: dict(v) for k, v in self.DEFAULT_TOOLS.items()}
        self._load_extra(tools_file)

    def _load_extra(self, tools_file: str):
        if not os.path.exists(tools_file):
            return
        try:
            with open(tools_file) as f:
                extra = json.load(f)
            for module, intents in extra.items():
                self.tools.setdefault(module, {}).update(intents)
            logger.debug("ToolRegistry: Loaded extra tools from %s", tools_file)
        except Exception as exc:
            logger.warning("ToolRegistry: Could not load tools file: %s", exc)

    def register(self, module: str, pattern: str, command: str):
        """Register a new intent pattern for a module."""
        self.tools.setdefault(module, {})[pattern] = command

    def match(self, text: str) -> str | None:
        """Return the first matching command template for a given text, or None."""
        for _, intents in self.tools.items():
            for pattern, template in intents.items():
                m = re.match(pattern, text)
                if m:
                    return template.format(*m.groups()) if m.groups() else template
        return None
