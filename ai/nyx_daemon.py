#!/usr/bin/env python3
"""
SnowOS NyxDaemon — Headless AI Core Service Wrapper.

This module wraps the full NyxAI engine into a production systemd service
that:
  1. Runs headlessly (no terminal REPL)
  2. Subscribes to the SnowOS broker for incoming commands
  3. Reads boot_status.json to initialize in the right persona/mode
  4. Reads /tmp/snowos_context.json every N seconds for real-time awareness
  5. Publishes responses and proactive events back via the broker
  6. Exposes a UNIX socket at /run/snowos/nyx.sock for direct queries
  7. Integrates healing bridge for crash-triggered AI repair
  8. Provides the heal socket at /run/snowos/nyx_heal.sock

Startup sequence:
  1. Read /run/snowos/boot-status.json → select persona + profile
  2. Initialize NyxAI(autonomous=True)
  3. Connect to broker.sock → subscribe to "nyx_command" topic
  4. Start background context poller (reads /tmp/snowos_context.json)
  5. Open nyx.sock for direct command queries
  6. Open nyx_heal.sock for healing requests from Sentinel
  7. Enter event loop (broker messages + direct socket + context poll)

Environment variables:
  NYX_API_KEY       — Gemini API key (required)
  SNOWOS_RUNTIME_DIR — /run/snowos (default)
  SNOWOS_LOG_LEVEL  — INFO (default)
"""

import os
import sys
import json
import socket
import logging
import signal
import threading
import time
import traceback
from pathlib import Path
import os
import sys
import json
import socket
import logging
import signal
import threading
import time
import traceback
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_AI_DIR   = Path(__file__).resolve().parents[3] / "ai"

# Add ai/ to path so NyxAI can be imported
if str(_AI_DIR) not in sys.path:
    sys.path.insert(0, str(_AI_DIR))
# Add snowos-runtime/src to path for runtime imports
_SRC_DIR = Path(__file__).resolve().parents[3] / "snowos-runtime" / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Add the ai/ directory itself (for siblings like flow_state_detector)
_SELF_DIR = Path(__file__).resolve().parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

logging.basicConfig(
    level=os.environ.get("SNOWOS_LOG_LEVEL", "INFO"),
    format="%(asctime)s [NyxDaemon] %(levelname)s %(message)s",
)
logger = logging.getLogger("NyxDaemon")

# ── Paths ─────────────────────────────────────────────────────────────────────
RUNTIME_DIR       = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
BOOT_STATUS_FILE  = os.path.join(RUNTIME_DIR, "boot-status.json")
CONTEXT_FILE      = "/tmp/snowos_context.json"
NYX_SOCK          = os.path.join(RUNTIME_DIR, "nyx.sock")
HEAL_SOCK         = os.path.join(RUNTIME_DIR, "nyx_heal.sock")
BROKER_SOCK       = os.path.join(RUNTIME_DIR, "broker.sock")
CONTEXT_POLL_SEC  = 5      # how often to read context.json
HEARTBEAT_SEC     = 60     # how often to emit a heartbeat to the broker
RECV_SIZE         = 65536

# ── Broker helpers ────────────────────────────────────────────────────────────

def _broker_send(msg: dict) -> dict | None:
    """Send a length-prefixed JSON message to the broker and return the response."""
    try:
        raw = json.dumps(msg).encode()
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect(BROKER_SOCK)
        s.sendall(len(raw).to_bytes(4, "big") + raw)
        # Read response
        raw_len = b""
        while len(raw_len) < 4:
            chunk = s.recv(4 - len(raw_len))
            if not chunk:
                return None
            raw_len += chunk
        resp_len = int.from_bytes(raw_len, "big")
        raw_resp = b""
        while len(raw_resp) < resp_len:
            chunk = s.recv(min(4096, resp_len - len(raw_resp)))
            if not chunk:
                break
            raw_resp += chunk
        s.close()
        return json.loads(raw_resp.decode())
    except Exception as e:
        logger.debug("Broker send error: %s", e)
        return None


def _broker_publish(topic: str, data: dict):
    _broker_send({"type": "publish", "topic": topic, "data": data})


# ── Boot context ──────────────────────────────────────────────────────────────

def _read_boot_status() -> dict:
    try:
        if os.path.exists(BOOT_STATUS_FILE):
            with open(BOOT_STATUS_FILE) as f:
                return json.load(f)
    except Exception as e:
        logger.warning("Could not read boot status: %s", e)
    return {"profile": "balanced", "status": "unknown", "trust_score": 75}


def _read_context() -> dict:
    try:
        if os.path.exists(CONTEXT_FILE):
            with open(CONTEXT_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


# ── NyxDaemon ────────────────────────────────────────────────────────────────

class NyxDaemon:
    """
    Headless SnowOS AI Core daemon.

    Wraps NyxAI and exposes it via:
      - UNIX socket (nyx.sock): direct command/query interface
      - UNIX socket (nyx_heal.sock): healing bridge for Sentinel
      - Broker subscription (nyx_command topic): async event-driven commands
    """

    def __init__(self):
        self._stop   = threading.Event()
        self.nyx     = None
        self._context: dict = {}
        self._context_lock  = threading.Lock()
        self._boot_status: dict = {}

    # ── Boot → persona ────────────────────────────────────────────────────────

    def _apply_boot_profile(self):
        """Apply boot profile to the AI personality."""
        profile    = self._boot_status.get("profile", "balanced")
        trust      = self._boot_status.get("trust_score", 99)
        boot_state = self._boot_status.get("status", "ready")

        logger.info("Boot profile: %s | trust: %s | state: %s",
                    profile, trust, boot_state)

        if self.nyx and hasattr(self.nyx, "personality"):
            self.nyx.personality.set_mode(profile)

        if trust < 50:
            logger.warning("Low trust score (%d) — forcing secure mode.", trust)
            if self.nyx and hasattr(self.nyx, "personality"):
                self.nyx.personality.set_mode("secure")

    # ── Context injection ─────────────────────────────────────────────────────

    def _context_poller(self):
        """Background thread: poll context.json and inject into Nyx planning."""
        while not self._stop.is_set():
            try:
                ctx = _read_context()
                if ctx:
                    with self._context_lock:
                        self._context = ctx
                    # Inject into Nyx's state if available
                    if self.nyx:
                        self._inject_context_into_nyx(ctx)
            except Exception as e:
                logger.debug("Context poll error: %s", e)
            self._stop.wait(CONTEXT_POLL_SEC)

    def _inject_context_into_nyx(self, ctx: dict):
        """
        Inject real-time context data into Nyx's memory and planning state.
        This bridges the gap: context_engine → NyxAI planner.
        """
        try:
            # Build context string for injection
            win_info  = ctx.get("active_window", {})
            telemetry = ctx.get("system", {})

            context_str = (
                f"[REAL-TIME SYSTEM CONTEXT]\n"
                f"Active Window: {win_info.get('title', 'Unknown')} "
                f"(class: {win_info.get('wm_class', '')})\n"
                f"CPU Load: {telemetry.get('load_1min', '?')} "
                f"| RAM Used: {telemetry.get('mem_used_pct', '?')}%"
            )
            battery = telemetry.get("battery", {})
            if battery:
                context_str += (
                    f" | Battery: {battery.get('capacity', '?')}% "
                    f"({battery.get('status', '?')})"
                )

            # Store in nyx's conversation memory as a system note
            # so it surfaces in generate_plan() prompts
            if hasattr(self.nyx, "memory"):
                self.nyx.memory["_live_context"] = context_str
                self.nyx.memory["_live_context_ts"] = time.time()

            # Publish context update to event bus
            if hasattr(self.nyx, "ui_state"):
                cpu_load = float(telemetry.get("load_1min", 0))
                if cpu_load > 3.0:
                    self.nyx.ui_state.state["user_intent"] = "high_load"
                elif win_info.get("wm_class", "").lower() in ("code", "vim", "nvim", "emacs"):
                    self.nyx.ui_state.state["user_intent"] = "coding"
                else:
                    self.nyx.ui_state.state["user_intent"] = "general"

        except Exception as e:
            logger.debug("Context injection error: %s", e)

    # ── Healing bridge socket ─────────────────────────────────────────────────

    def _run_heal_socket(self):
        """
        Listen on nyx_heal.sock for crash reports from the Sentinel.
        Each request: {service, crash_log, unit_file}
        Each response: {status, plan: {action, patch_cmd, reason, btrfs_snapshot}}
        """
        os.makedirs(RUNTIME_DIR, mode=0o775, exist_ok=True)
        if os.path.exists(HEAL_SOCK):
            os.remove(HEAL_SOCK)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(HEAL_SOCK)
        os.chmod(HEAL_SOCK, 0o660)
        srv.listen(8)
        srv.settimeout(1.0)
        logger.info("Heal socket listening on %s", HEAL_SOCK)

        while not self._stop.is_set():
            try:
                conn, _ = srv.accept()
                t = threading.Thread(
                    target=self._handle_heal_conn,
                    args=(conn,),
                    daemon=True,
                    name="HealConn",
                )
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break

        try:
            srv.close()
            os.remove(HEAL_SOCK)
        except Exception:
            pass

    def _handle_heal_conn(self, conn: socket.socket):
        try:
            data = conn.recv(RECV_SIZE)
            if not data:
                return
            payload = json.loads(data.decode("utf-8", errors="replace"))
            service   = payload.get("service", "unknown")
            crash_log = payload.get("crash_log", "")

            logger.info("Heal request for service: %s", service)

            plan = self._ai_healing_plan(service, crash_log)
            response = {"status": "ok", "plan": plan}
            conn.sendall(json.dumps(response).encode())

            # Record in healing history
            self._record_healing_attempt(service, plan)

        except Exception as e:
            logger.error("Heal socket error: %s", e)
            try:
                conn.sendall(json.dumps({"status": "error", "reason": str(e)}).encode())
            except Exception:
                pass
        finally:
            conn.close()

    def _ai_healing_plan(self, service: str, crash_log: str) -> dict:
        """Generate an AI-driven healing plan from the crash log."""
        # First try pattern matching (fast, no LLM needed)
        plan = self._pattern_match_heal(crash_log)
        if plan:
            return plan

        # Fall back to LLM analysis
        if self.nyx:
            try:
                prompt = (
                    f"You are the SnowOS Self-Healing Engine.\n"
                    f"A systemd service crashed. Analyze the crash log and return a healing plan.\n\n"
                    f"Service: {service}\n"
                    f"Crash Log (last 3000 chars):\n{crash_log[-3000:]}\n\n"
                    f"Return ONLY valid JSON (no markdown):\n"
                    f'{{"action": "restart|hotpatch|rollback|ignore", '
                    f'"patch_cmd": "shell_command_or_null", '
                    f'"verify_cmd": "shell_command_or_null", '
                    f'"btrfs_snapshot": true_or_false, '
                    f'"reason": "explanation"}}'
                )
                response = self.nyx._llm(prompt)
                if response:
                    # Strip markdown fences
                    r = response.strip()
                    for fence in ("```json", "```"):
                        if r.startswith(fence):
                            r = r[len(fence):]
                    if r.endswith("```"):
                        r = r[:-3]
                    return json.loads(r.strip())
            except Exception as e:
                logger.warning("LLM healing plan failed: %s", e)

        # Ultimate fallback
        return {
            "action": "restart",
            "patch_cmd": f"systemctl reset-failed {service}",
            "verify_cmd": f"systemctl is-active {service}",
            "btrfs_snapshot": False,
            "reason": "Pattern match and LLM unavailable — defaulting to restart.",
        }

    def _pattern_match_heal(self, crash_log: str) -> dict | None:
        """Quick pattern-based healing without LLM overhead."""
        patterns = [
            (["ModuleNotFoundError", "ImportError", "No module named"],
             "hotpatch", "pip3 install --user {module}", "Module import error"),
            (["FileNotFoundError", "No such file or directory"],
             "hotpatch", "mkdir -p /tmp/snowos_repair", "Missing file/directory"),
            (["PermissionError", "Permission denied", "EACCES"],
             "hotpatch", None, "Permission error — manual review needed"),
            (["Address already in use", "EADDRINUSE"],
             "hotpatch", "fuser -k {port}/tcp 2>/dev/null; rm -f {socket}", "Port/socket conflict"),
            (["OOMKilled", "out of memory", "Cannot allocate memory"],
             "restart", None, "OOM kill — restarting service"),
            (["SIGSEGV", "Segmentation fault", "core dumped"],
             "rollback", None, "Segfault — rollback recommended"),
        ]
        lower = crash_log.lower()
        for keywords, action, patch_cmd, reason in patterns:
            if any(k.lower() in lower for k in keywords):
                return {
                    "action": action,
                    "patch_cmd": patch_cmd,
                    "verify_cmd": None,
                    "btrfs_snapshot": action == "rollback",
                    "reason": reason,
                }
        return None

    # ── Healing outcome tracking ──────────────────────────────────────────────

    _heal_history: dict = {}  # service → list of {ts, plan, outcome}
    _heal_lock = threading.Lock()

    def _record_healing_attempt(self, service: str, plan: dict, outcome: str = "pending"):
        with self._heal_lock:
            if service not in self._heal_history:
                self._heal_history[service] = []
            self._heal_history[service].append({
                "ts": time.time(),
                "plan": plan,
                "outcome": outcome,
            })
            # Keep last 20 per service
            self._heal_history[service] = self._heal_history[service][-20:]

    def check_healing_escalation(self, service: str) -> bool:
        """
        Returns True if healing should escalate to BTRFS rollback.
        Triggers when the same service has failed 3+ times in the last hour
        without a successful heal.
        """
        with self._heal_lock:
            history = self._heal_history.get(service, [])
        one_hour_ago = time.time() - 3600
        recent = [h for h in history if h["ts"] > one_hour_ago]
        failures = [h for h in recent if h["outcome"] in ("failed", "pending")]
        if len(failures) >= 3:
            logger.critical(
                "ESCALATION: Service '%s' has failed healing %d times in 1 hour. "
                "Triggering BTRFS rollback.", service, len(failures)
            )
            self._broker_publish_escalation(service)
            return True
        return False

    def _broker_publish_escalation(self, service: str):
        _broker_publish("escalation", {
            "service": service,
            "action": "btrfs_rollback",
            "reason": "Repeated heal failure — 3+ attempts in 1 hour",
            "ts": time.time(),
        })

    # ── Direct command socket ─────────────────────────────────────────────────

    def _run_nyx_socket(self):
        """
        Listen on nyx.sock for direct command queries.
        Request: {"command": "...", "cwd": "..."}
        Response: {"status": "ok", "output": "..."}
        """
        os.makedirs(RUNTIME_DIR, mode=0o775, exist_ok=True)
        if os.path.exists(NYX_SOCK):
            os.remove(NYX_SOCK)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(NYX_SOCK)
        os.chmod(NYX_SOCK, 0o660)
        srv.listen(8)
        srv.settimeout(1.0)
        logger.info("Nyx command socket listening on %s", NYX_SOCK)

        while not self._stop.is_set():
            try:
                conn, _ = srv.accept()
                t = threading.Thread(
                    target=self._handle_nyx_conn,
                    args=(conn,),
                    daemon=True,
                    name="NyxCmd",
                )
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break

        try:
            srv.close()
            os.remove(NYX_SOCK)
        except Exception:
            pass

    def _handle_nyx_conn(self, conn: socket.socket):
        try:
            data = conn.recv(RECV_SIZE)
            if not data:
                return
            payload = json.loads(data.decode("utf-8", errors="replace"))
            command = payload.get("command", "")

            logger.info("Command received via socket: %s", command[:80])

            if not self.nyx or not command:
                conn.sendall(json.dumps({"status": "error",
                                         "output": "Nyx not ready."}).encode())
                return

            # Capture output
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            try:
                with redirect_stdout(buf):
                    self.nyx.process(command)
                output = buf.getvalue()
            except Exception as e:
                output = f"Error: {e}"

            conn.sendall(json.dumps({"status": "ok", "output": output}).encode())
        except Exception as e:
            logger.error("Nyx socket error: %s", e)
        finally:
            conn.close()

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    def _heartbeat_loop(self):
        while not self._stop.is_set():
            try:
                status = {
                    "service": "snowos-aicore",
                    "status": "healthy",
                    "ts": time.time(),
                    "nyx_ready": self.nyx is not None,
                }
                _broker_publish("heartbeat", status)
            except Exception:
                pass
            self._stop.wait(HEARTBEAT_SEC)

    # ── Main startup ──────────────────────────────────────────────────────────

    def start(self):
        logger.info("=== SnowOS NyxDaemon starting ===")

        # 1. Read boot status
        self._boot_status = _read_boot_status()
        logger.info("Boot profile: %s", self._boot_status.get("profile", "unknown"))

        # 2. Initialize NyxAI
        logger.info("Initializing NyxAI engine (autonomous=True)...")
        try:
            from nyx import NyxAI  # noqa: F401
            self.nyx = NyxAI(autonomous=True)
            logger.info("NyxAI engine initialized.")
        except Exception as e:
            logger.error("NyxAI init failed: %s\n%s", e, traceback.format_exc())
            logger.warning("Daemon will run in degraded mode (no LLM).")
            self.nyx = None

        # 3. Apply boot profile → personality
        self._apply_boot_profile()

        # 4. Initialize Flow State Detector
        try:
            from flow_state_detector import FlowStateDetector
            nyx_memory = self.nyx.memory if self.nyx else {}
            nyx_bus    = getattr(self.nyx, "learning_feedback", None) and \
                         __import__("runtime.event_bus", fromlist=["bus"]).bus \
                         if self.nyx else None
            self._flow_detector = FlowStateDetector(
                nyx_memory=nyx_memory,
                bus=nyx_bus,
            )
            self._flow_detector.start()
            logger.info("FlowStateDetector started.")
        except Exception as e:
            logger.warning("FlowStateDetector init failed: %s", e)
            self._flow_detector = None

        # 5. Initialize Healing Outcome Tracker
        try:
            from healing_outcome_tracker import get_tracker
            self._heal_tracker = get_tracker()
            logger.info("HealingOutcomeTracker initialized.")
        except Exception as e:
            logger.warning("HealingOutcomeTracker init failed: %s", e)
            self._heal_tracker = None

        # 6. Announce to broker
        _broker_publish("service_started", {
            "service": "snowos-aicore",
            "profile": self._boot_status.get("profile"),
            "flow_detector": self._flow_detector is not None,
            "heal_tracker": self._heal_tracker is not None,
            "ts": time.time(),
        })

        # 7. Start background threads
        threads = [
            threading.Thread(target=self._context_poller,  daemon=True, name="CtxPoller"),
            threading.Thread(target=self._run_heal_socket, daemon=True, name="HealSock"),
            threading.Thread(target=self._run_nyx_socket,  daemon=True, name="NyxSock"),
            threading.Thread(target=self._heartbeat_loop,  daemon=True, name="Heartbeat"),
        ]
        for t in threads:
            t.start()

        logger.info("NyxDaemon fully operational. Waiting for events...")

        # 8. Signal handling
        def _sigterm(_sig, _frame):
            logger.info("NyxDaemon: SIGTERM received — stopping.")
            self._stop.set()

        signal.signal(signal.SIGTERM, _sigterm)
        signal.signal(signal.SIGINT,  _sigterm)

        # 9. Block until stopped
        self._stop.wait()

        # 10. Cleanup
        if self._flow_detector:
            self._flow_detector.stop()
        logger.info("NyxDaemon stopped.")

    def stop(self):
        self._stop.set()

    def _handle_heal_conn(self, conn: socket.socket):
        """Override heal conn to integrate HealingOutcomeTracker."""
        try:
            data = conn.recv(RECV_SIZE)
            if not data:
                return
            payload = json.loads(data.decode("utf-8", errors="replace"))
            service   = payload.get("service", "unknown")
            crash_log = payload.get("crash_log", "")

            logger.info("Heal request for service: %s", service)

            # Check if we have a cached effective patch (skip LLM if so)
            plan = None
            if self._heal_tracker:
                cached = self._heal_tracker.get_effective_patch(service)
                if cached:
                    logger.info("Using cached effective patch for '%s'.", service)
                    plan = {
                        "action": "hotpatch",
                        "patch_cmd": cached["patch_cmd"],
                        "verify_cmd": f"systemctl is-active {service}",
                        "btrfs_snapshot": False,
                        "reason": f"Cached: {cached['reason']}",
                    }

            if plan is None:
                plan = self._ai_healing_plan(service, crash_log)

            response = {"status": "ok", "plan": plan}
            conn.sendall(json.dumps(response).encode())

            # Record attempt (triggers automatic verification after 30s)
            if self._heal_tracker:
                self._heal_tracker.record_attempt(service, plan, applied=True)

        except Exception as e:
            logger.error("Heal socket error: %s", e)
            try:
                conn.sendall(json.dumps({"status": "error", "reason": str(e)}).encode())
            except Exception:
                pass
        finally:
            conn.close()


def main():
    daemon = NyxDaemon()
    daemon.start()


if __name__ == "__main__":
    main()
