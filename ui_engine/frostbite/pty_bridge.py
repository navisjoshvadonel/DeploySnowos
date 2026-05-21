#!/usr/bin/env python3
"""
Frostbite PTY Bridge — Autonomous pseudo-terminal for dev environment setup.

Spawns a hidden pty, executes commands, handles prompts autonomously,
streams progress to a callback, and notifies on completion.
"""
import os
import pty
import select
import subprocess
import threading
import time
import re
import logging
from typing import Callable, Optional

logger = logging.getLogger("FrostbitePTY")

# Patterns that need autonomous answers
_AUTO_ANSWERS = [
    (re.compile(r"\[y/n\]|\[yes/no\]|\(y/n\)|\(yes/no\)", re.I), "y\n"),
    (re.compile(r"do you want to continue\?",                re.I), "y\n"),
    (re.compile(r"proceed\?|confirm\?|ok\?",                 re.I), "y\n"),
    (re.compile(r"password for|enter password|sudo password", re.I), None),  # skip — cannot auto-answer
]

# Progress bar patterns for parsing
_PROGRESS_PATTERNS = [
    re.compile(r"(\d+)%"),          # any percentage
    re.compile(r"(\d+)/(\d+)"),     # n/m progress
    re.compile(r"downloading",  re.I),
    re.compile(r"installing",   re.I),
    re.compile(r"unpacking",    re.I),
    re.compile(r"setting up",   re.I),
    re.compile(r"processing",   re.I),
]


class PseudoTerminalBridge:
    """
    Runs a command in a hidden pty, capturing output,
    answering prompts automatically, and streaming progress.

    Usage:
        bridge = PseudoTerminalBridge()
        bridge.run_command(
            "sudo apt-get install -y vim git curl",
            on_progress=lambda line, pct: print(f"[{pct}%] {line}"),
            on_complete=lambda success, output: print("Done!" if success else "Failed!")
        )
    """

    def __init__(self):
        self._lock = threading.Lock()

    def _parse_progress(self, line: str) -> int:
        """Extract progress percentage from a line, or return -1."""
        for pat in _PROGRESS_PATTERNS:
            m = pat.search(line)
            if m:
                if m.lastindex and m.lastindex >= 1:
                    try:
                        return min(99, int(m.group(1)))
                    except Exception:
                        pass
                return 0  # progress detected, but no percentage
        return -1

    def _check_auto_answer(self, line: str) -> Optional[str]:
        """Return an auto-answer string if this line is a known prompt."""
        for pattern, answer in _AUTO_ANSWERS:
            if pattern.search(line):
                return answer
        return None

    def run_command(
        self,
        command: str,
        cwd: str = None,
        timeout: int = 300,
        on_progress: Callable[[str, int], None] = None,
        on_complete: Callable[[bool, str], None] = None,
    ) -> threading.Thread:
        """
        Run command in a background pty thread.
        Returns the thread immediately (non-blocking).

        Args:
            command:     Shell command to execute
            cwd:         Working directory
            timeout:     Max seconds before force-kill
            on_progress: Callback(line, pct) for each output line
            on_complete: Callback(success, full_output) on finish
        """
        t = threading.Thread(
            target=self._pty_runner,
            args=(command, cwd, timeout, on_progress, on_complete),
            daemon=True,
            name="FrostbitePTY",
        )
        t.start()
        return t

    def _pty_runner(
        self,
        command: str,
        cwd: Optional[str],
        timeout: int,
        on_progress: Optional[Callable],
        on_complete: Optional[Callable],
    ):
        """Internal PTY execution loop."""
        master_fd, slave_fd = pty.openpty()
        full_output = []
        success = False
        proc = None

        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=cwd,
                close_fds=True,
                preexec_fn=os.setsid,
            )
            os.close(slave_fd)  # close slave in parent

            start_time = time.time()
            buffer = b""

            while proc.poll() is None:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    logger.warning(f"PTY: Command timed out after {timeout}s — killing.")
                    try:
                        os.killpg(os.getpgid(proc.pid), 9)
                    except Exception:
                        proc.kill()
                    break

                ready, _, _ = select.select([master_fd], [], [], 0.5)
                if not ready:
                    continue

                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    break

                buffer += chunk
                # Process complete lines
                while b"\n" in buffer:
                    line_bytes, buffer = buffer.split(b"\n", 1)
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue

                    full_output.append(line)
                    pct = self._parse_progress(line)

                    if on_progress:
                        try:
                            on_progress(line, pct)
                        except Exception:
                            pass

                    # Auto-answer prompts
                    answer = self._check_auto_answer(line)
                    if answer:
                        try:
                            os.write(master_fd, answer.encode())
                        except Exception:
                            pass

            success = proc.returncode == 0 if proc.poll() is not None else False

        except Exception as e:
            logger.error(f"PTY runner error: {e}")
            full_output.append(f"ERROR: {e}")
        finally:
            try:
                os.close(master_fd)
            except Exception:
                pass
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass

        if on_complete:
            try:
                on_complete(success, "\n".join(full_output))
            except Exception as e:
                logger.error(f"on_complete callback error: {e}")

    def run_sync(self, command: str, cwd: str = None, timeout: int = 60) -> tuple:
        """
        Blocking variant. Returns (success: bool, output: str).
        Suitable for simple commands.
        """
        result = {"success": False, "output": ""}
        done = threading.Event()

        def _complete(success, output):
            result["success"] = success
            result["output"]  = output
            done.set()

        self.run_command(command, cwd=cwd, timeout=timeout, on_complete=_complete)
        done.wait(timeout + 5)
        return result["success"], result["output"]


# ─── Desktop Notification ──────────────────────────────────────────────────────
def notify(title: str, body: str, icon: str = "dialog-information"):
    """Send a desktop notification via libnotify."""
    try:
        subprocess.Popen(
            ["notify-send", "--icon", icon, "--expire-time", "8000", title, body],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.debug(f"Notification failed: {e}")
