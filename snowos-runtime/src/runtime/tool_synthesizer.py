#!/usr/bin/env python3
"""
SnowOS Self-Synthesizing Tool Compiler.

When Nyx encounters a task with no matching tool in the ToolRegistry,
it autonomously generates a purpose-built Python script, executes it
in a sandboxed directory, and archives the code for future reuse.

Sandbox: /run/snowos/dynamic_tools/
Archive: ~/.snowos/tool_archive/
"""
import os
import sys
import json
import time
import uuid
import logging
import subprocess
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ToolSynthesizer] %(levelname)s %(message)s",
)
logger = logging.getLogger("ToolSynthesizer")

SANDBOX_DIR = "/run/snowos/dynamic_tools"
ARCHIVE_DIR = os.path.expanduser("~/.snowos/tool_archive")
MANIFEST_FILE = os.path.join(ARCHIVE_DIR, "manifest.json")


class ToolSynthesizer:
    """
    Generates, executes, and archives transient Python scripts
    to handle tasks that have no pre-existing tool mapping.
    """

    def __init__(self, llm_fn=None):
        """
        Args:
            llm_fn: Callable that takes a prompt string and returns generated text.
                    This is typically nyx.llm() or nyx.generate_content().
        """
        self.llm_fn = llm_fn
        self._manifest: dict = self._load_manifest()
        os.makedirs(SANDBOX_DIR, exist_ok=True)
        os.makedirs(ARCHIVE_DIR, exist_ok=True)

    # ── Manifest Persistence ──────────────────────────────────────────────────
    def _load_manifest(self) -> dict:
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        if os.path.exists(MANIFEST_FILE):
            try:
                with open(MANIFEST_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"tools": {}}

    def _save_manifest(self):
        try:
            with open(MANIFEST_FILE, "w") as f:
                json.dump(self._manifest, f, indent=2)
        except Exception as e:
            logger.error(f"Manifest save failed: {e}")

    # ── Cache Lookup ──────────────────────────────────────────────────────────
    def _task_hash(self, description: str) -> str:
        """Generate a stable hash for a task description for cache matching."""
        normalized = description.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def find_cached_tool(self, description: str) -> str | None:
        """Check if a previously synthesized tool matches this task."""
        task_hash = self._task_hash(description)
        entry = self._manifest["tools"].get(task_hash)
        if entry and os.path.exists(entry.get("archive_path", "")):
            logger.info(f"Cache hit for task '{description[:40]}...' → {entry['archive_path']}")
            return entry["archive_path"]
        return None

    # ── Synthesis ─────────────────────────────────────────────────────────────
    def synthesize(self, task_description: str, context: dict = None) -> dict:
        """
        Generate, execute, and archive a tool for the given task.

        Returns:
            {
                "status": "success" | "error",
                "output": str,
                "script_path": str,
                "cached": bool,
            }
        """
        # 1. Check cache
        cached_path = self.find_cached_tool(task_description)
        if cached_path:
            return self._execute_script(cached_path, task_description, cached=True)

        # 2. Generate code via LLM
        if not self.llm_fn:
            return {"status": "error", "reason": "No LLM function configured.", "cached": False}

        prompt = self._build_synthesis_prompt(task_description, context)
        try:
            raw_code = self.llm_fn(prompt)
        except Exception as e:
            return {"status": "error", "reason": f"LLM generation failed: {e}", "cached": False}

        code = self._extract_python(raw_code)
        if not code:
            return {"status": "error", "reason": "LLM did not produce valid Python.", "cached": False}

        # 3. Write to sandbox
        tool_id = str(uuid.uuid4())[:8]
        script_path = os.path.join(SANDBOX_DIR, f"tool_{tool_id}.py")
        try:
            with open(script_path, "w") as f:
                f.write(code)
        except Exception as e:
            return {"status": "error", "reason": f"Failed to write script: {e}", "cached": False}

        # 4. Execute
        result = self._execute_script(script_path, task_description, cached=False)

        # 5. Archive on success
        if result["status"] == "success":
            self._archive_tool(tool_id, task_description, script_path, code)

        return result

    def _build_synthesis_prompt(self, task: str, context: dict = None) -> str:
        ctx_str = ""
        if context:
            ctx_str = f"\nCurrent context:\n{json.dumps(context, indent=2)}\n"

        return (
            "You are SnowOS Nyx — an AI operating system agent. "
            "Generate a standalone Python 3 script that accomplishes the following task. "
            "The script must be self-contained, use only standard library modules "
            "(or commonly available packages like sqlite3, csv, json), "
            "print its results to stdout, and exit cleanly.\n\n"
            f"Task: {task}\n"
            f"{ctx_str}\n"
            "Output ONLY the Python code. No explanations, no markdown fences."
        )

    def _extract_python(self, raw: str) -> str:
        """Extract clean Python code from LLM output."""
        if not raw:
            return ""
        # Strip markdown fences if present
        lines = raw.strip().splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        code = "\n".join(lines).strip()
        # Basic validation: must contain at least one Python statement
        if not code or ("import" not in code and "print" not in code and "def " not in code):
            return ""
        return code

    def _execute_script(self, script_path: str, description: str, cached: bool) -> dict:
        """Execute a Python script in the sandbox with timeout."""
        logger.info(f"Executing {'cached' if cached else 'synthesized'} tool: {script_path}")
        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=SANDBOX_DIR,
                env={**os.environ, "SNOWOS_TOOL_SANDBOX": "1"},
            )
            if result.returncode == 0:
                return {
                    "status": "success",
                    "output": result.stdout.strip(),
                    "script_path": script_path,
                    "cached": cached,
                }
            else:
                return {
                    "status": "error",
                    "reason": f"Script exited with code {result.returncode}",
                    "stderr": result.stderr.strip(),
                    "script_path": script_path,
                    "cached": cached,
                }
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "reason": "Script execution timed out (30s).",
                "script_path": script_path,
                "cached": cached,
            }
        except Exception as e:
            return {
                "status": "error",
                "reason": str(e),
                "script_path": script_path,
                "cached": cached,
            }

    def _archive_tool(self, tool_id: str, description: str, script_path: str, code: str):
        """Archive a successfully executed tool for future reuse."""
        archive_path = os.path.join(ARCHIVE_DIR, f"tool_{tool_id}.py")
        try:
            with open(archive_path, "w") as f:
                f.write(f"# SnowOS Synthesized Tool\n# Task: {description}\n# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(code)

            task_hash = self._task_hash(description)
            self._manifest["tools"][task_hash] = {
                "id": tool_id,
                "description": description,
                "archive_path": archive_path,
                "created": time.time(),
            }
            self._save_manifest()
            logger.info(f"Archived tool {tool_id} → {archive_path}")
        except Exception as e:
            logger.error(f"Archival failed: {e}")

    # ── Stats ─────────────────────────────────────────────────────────────────
    def stats(self) -> dict:
        return {
            "cached_tools": len(self._manifest.get("tools", {})),
            "sandbox_dir": SANDBOX_DIR,
            "archive_dir": ARCHIVE_DIR,
        }
