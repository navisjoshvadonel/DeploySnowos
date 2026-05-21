#!/usr/bin/env python3
"""
NyxVFS Healing Bridge — bridges sentinel crash events to Nyx's AI healing engine.

Listens on /run/snowos/nyx_heal.sock for crash reports from the Sentinel daemon.
Passes them to Nyx's HealingBroker and returns a structured HealingPlan.

Protocol:
  Request:  {"service": "name", "crash_log": "...", "unit_file": "..."}
  Response: {
      "action":    "restart" | "hotpatch" | "rollback" | "ignore",
      "patch_cmd": "shell command or null",
      "verify_cmd": "shell command or null",
      "btrfs_snapshot": true | false,
      "reason": "explanation"
  }
"""
import os, sys, json, socket, logging, signal, subprocess, threading, time

_AI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _AI_DIR)

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [HealingBridge] %(levelname)s %(message)s")
logger = logging.getLogger("HealingBridge")

RUNTIME_DIR = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
HEAL_SOCKET  = os.path.join(RUNTIME_DIR, "nyx_heal.sock")

# ─── BTRFS helpers ────────────────────────────────────────────────────────────
def _has_btrfs(path: str = "/") -> bool:
    try:
        result = subprocess.run(["stat", "-f", "-c", "%T", path],
            capture_output=True, text=True, timeout=3)
        return "btrfs" in result.stdout.lower()
    except Exception:
        return False

def _create_btrfs_snapshot(label: str) -> str | None:
    """Create a BTRFS snapshot and return its path, or None on failure."""
    snap_dir = f"/snapshots/heal_{label}_{int(time.time())}"
    try:
        subprocess.run(
            ["btrfs", "subvolume", "snapshot", "/", snap_dir],
            check=True, timeout=15, capture_output=True,
        )
        logger.info(f"HealingBridge: Snapshot created at {snap_dir}")
        return snap_dir
    except Exception as e:
        logger.warning(f"HealingBridge: BTRFS snapshot failed: {e}")
        return None

# ─── Healing Plan Analysis ─────────────────────────────────────────────────────
_KNOWN_PATTERNS = [
    {
        "keywords": ["ModuleNotFoundError", "ImportError", "No module named"],
        "action": "hotpatch",
        "patch_cmd": "pip3 install --user {module}",
        "reason": "Missing Python dependency detected",
    },
    {
        "keywords": ["FileNotFoundError", "No such file or directory", "cannot open"],
        "action": "hotpatch",
        "patch_cmd": "mkdir -p {path}",
        "reason": "Missing directory or file",
    },
    {
        "keywords": ["PermissionError", "Permission denied", "EACCES"],
        "action": "hotpatch",
        "patch_cmd": "chmod 755 {path}",
        "reason": "Permission error on path",
    },
    {
        "keywords": ["Address already in use", "EADDRINUSE", "bind: address already"],
        "action": "hotpatch",
        "patch_cmd": "fuser -k {port}/tcp 2>/dev/null || rm -f {socket}",
        "reason": "Socket/port conflict — releasing stale binding",
    },
    {
        "keywords": ["JSONDecodeError", "json.decoder", "Expecting value"],
        "action": "hotpatch",
        "patch_cmd": "python3 -c \"import json,shutil; shutil.copy('{conf}','{conf}.bak'); open('{conf}','w').write('{}')\"",
        "reason": "Corrupted JSON config — resetting to empty",
    },
    {
        "keywords": ["MemoryError", "Cannot allocate memory", "ENOMEM"],
        "action": "restart",
        "patch_cmd": "sync && echo 3 > /proc/sys/vm/drop_caches",
        "reason": "Memory pressure — clearing caches before restart",
    },
]

def _analyze_crash_log(service: str, crash_log: str) -> dict:
    """
    Rule-based crash analysis with optional Nyx LLM augmentation.
    Returns a HealingPlan dict.
    """
    for pattern in _KNOWN_PATTERNS:
        if any(kw.lower() in crash_log.lower() for kw in pattern["keywords"]):
            return {
                "action":         pattern["action"],
                "patch_cmd":      pattern["patch_cmd"],
                "verify_cmd":     f"systemctl is-active {service}",
                "btrfs_snapshot": pattern["action"] == "hotpatch",
                "reason":         pattern["reason"],
                "confidence":     "rule_based",
            }

    # Default: attempt clean restart
    return {
        "action":         "restart",
        "patch_cmd":      None,
        "verify_cmd":     f"systemctl is-active {service}",
        "btrfs_snapshot": False,
        "reason":         "Unknown crash pattern — performing clean restart",
        "confidence":     "fallback",
    }

def _try_nyx_analysis(service: str, crash_log: str) -> dict | None:
    """
    Optionally forward to Nyx via its broker for AI-augmented analysis.
    Returns a HealingPlan or None if unavailable.
    """
    broker_sock = os.path.join(RUNTIME_DIR, "broker.sock")
    if not os.path.exists(broker_sock):
        return None
    try:
        payload = json.dumps({
            "source_id": "sentinel",
            "target_resource": "nyx_heal",
            "action": "analyze_crash",
            "context": "healing",
            "crash_log": crash_log[:2048],
            "service": service,
        })
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(8.0)
        s.connect(broker_sock)
        s.sendall(payload.encode())
        resp_raw = s.recv(16384)
        s.close()
        resp = json.loads(resp_raw.decode())
        if resp.get("status") == "GRANTED":
            token = resp.get("token")
            logger.info(f"HealingBridge: Broker granted analysis token for {service}")
        return None  # full Nyx integration is async — use rule-based for now
    except Exception as e:
        logger.debug(f"HealingBridge: Nyx analysis unavailable: {e}")
        return None


# ─── Execute Healing Plan ──────────────────────────────────────────────────────
def _execute_healing_plan(service: str, plan: dict) -> bool:
    """Apply the healing plan and return True if service recovers."""
    snapshot_path = None

    # Step 1: Optionally create BTRFS snapshot before patching
    if plan.get("btrfs_snapshot") and _has_btrfs():
        snapshot_path = _create_btrfs_snapshot(service.replace("-", "_"))

    # Step 2: Apply patch command if provided
    if plan.get("patch_cmd"):
        try:
            cmd = plan["patch_cmd"]
            logger.info(f"HealingBridge: Applying patch: {cmd}")
            subprocess.run(cmd, shell=True, timeout=30, capture_output=True)
        except Exception as e:
            logger.error(f"HealingBridge: Patch command failed: {e}")

    # Step 3: Restart the service
    try:
        logger.info(f"HealingBridge: Restarting {service}...")
        subprocess.run(["systemctl", "restart", service],
            timeout=15, capture_output=True)
        time.sleep(3)
    except Exception as e:
        logger.error(f"HealingBridge: Restart failed: {e}")
        return False

    # Step 4: Verify recovery
    verify_cmd = plan.get("verify_cmd", f"systemctl is-active {service}")
    try:
        result = subprocess.run(
            verify_cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        recovered = result.returncode == 0
        if recovered:
            logger.info(f"HealingBridge: Service {service} recovered successfully.")
        else:
            logger.warning(f"HealingBridge: Service {service} still down after patch.")
        return recovered
    except Exception:
        return False


# ─── Healing Bridge Server ────────────────────────────────────────────────────
class NyxHealingServer:
    """Unix socket server receiving crash reports and returning healing plans."""

    def __init__(self):
        self._running = False
        self._server = None
        self._btrfs_available = _has_btrfs()

    def _setup_socket(self):
        os.makedirs(RUNTIME_DIR, mode=0o775, exist_ok=True)
        if os.path.exists(HEAL_SOCKET):
            os.remove(HEAL_SOCKET)
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(HEAL_SOCKET)
        os.chmod(HEAL_SOCKET, 0o660)
        self._server.listen(4)
        logger.info(f"HealingBridge listening on {HEAL_SOCKET}")

    def _handle(self, conn: socket.socket):
        try:
            data = conn.recv(32768)
            if not data:
                return
            payload = json.loads(data.decode("utf-8", errors="replace"))
            service = payload.get("service", "unknown")
            crash_log = payload.get("crash_log", "")
            logger.info(f"HealingBridge: Received crash for {service} ({len(crash_log)} chars)")

            # Analyze
            plan = _try_nyx_analysis(service, crash_log) or _analyze_crash_log(service, crash_log)
            logger.info(f"HealingBridge: Plan for {service}: {plan['action']} — {plan['reason']}")

            # Execute in background thread (don't block socket)
            def _bg():
                _execute_healing_plan(service, plan)
            threading.Thread(target=_bg, daemon=True).start()

            conn.sendall(json.dumps({"status": "ok", "plan": plan}).encode())
        except Exception as e:
            logger.error(f"HealingBridge: Handler error: {e}")
            try:
                conn.sendall(json.dumps({"status": "error", "reason": str(e)}).encode())
            except Exception:
                pass
        finally:
            conn.close()

    def run(self):
        self._setup_socket()
        self._running = True

        def _stop(sig, frame):
            self._running = False
            try:
                self._server.close()
            except Exception:
                pass
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

        logger.info(f"HealingBridge ready. BTRFS: {self._btrfs_available}")
        try:
            while self._running:
                try:
                    self._server.settimeout(1.0)
                    conn, _ = self._server.accept()
                    threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
                except socket.timeout:
                    continue
                except OSError:
                    break
        finally:
            if os.path.exists(HEAL_SOCKET):
                try:
                    os.remove(HEAL_SOCKET)
                except Exception:
                    pass
            logger.info("HealingBridge exited.")


# ─── Client helper (used by sentinel) ────────────────────────────────────────
def send_crash_report(service: str, crash_log: str, unit_file: str = "") -> dict | None:
    """
    Send a crash report to the healing bridge.
    Returns the healing plan dict or None on failure.
    """
    if not os.path.exists(HEAL_SOCKET):
        logger.warning("HealingBridge socket not available — skipping AI healing.")
        return None
    try:
        payload = json.dumps({
            "service": service,
            "crash_log": crash_log,
            "unit_file": unit_file,
        })
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(10.0)
        s.connect(HEAL_SOCKET)
        s.sendall(payload.encode())
        resp = s.recv(16384)
        s.close()
        return json.loads(resp.decode())
    except Exception as e:
        logger.error(f"send_crash_report: {e}")
        return None


if __name__ == "__main__":
    NyxHealingServer().run()
