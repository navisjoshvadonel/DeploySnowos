#!/usr/bin/env python3
"""
NyxVFS Healing Bridge — bridges sentinel crash events to Nyx's AI healing engine.

Listens on /run/snowos/nyx_heal.sock for crash reports from the Sentinel daemon.
Passes them to Nyx's HealingBroker and returns a structured HealingPlan.

Protocol (length-prefixed framing):
  All messages are prefixed with a 4-byte big-endian uint32 length header so
  that large crash logs (> one recv buffer) are received in full.

  Request:  {"service": "name", "crash_log": "...", "unit_file": "..."}
  Response: {
      "status": "ok" | "error",
      "plan": {
          "action":    "restart" | "hotpatch" | "rollback" | "ignore",
          "patch_cmd": "shell command or null",
          "verify_cmd": "shell command or null",
          "btrfs_snapshot": true | false,
          "reason": "explanation",
          "confidence": "rule_based" | "nyx_ai" | "fallback"
      }
  }
"""
import os, sys, json, socket, logging, signal, subprocess, threading, time, re

_AI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _AI_DIR)

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [HealingBridge] %(levelname)s %(message)s")
logger = logging.getLogger("HealingBridge")

RUNTIME_DIR = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
HEAL_SOCKET  = os.path.join(RUNTIME_DIR, "nyx_heal.sock")

# Optional systemd watchdog support
try:
    import sdnotify  # type: ignore
    _SD = sdnotify.SystemdNotifier()
except ImportError:
    _SD = None


def _sd_watchdog():
    """Ping the systemd watchdog. Called in the main loop each iteration."""
    if _SD:
        try:
            _SD.notify("WATCHDOG=1")
        except Exception:
            pass


# ─── Socket framing helpers ───────────────────────────────────────────────────

def _recv_framed(conn: socket.socket, max_bytes: int = 4 * 1024 * 1024) -> bytes:
    """
    Read a length-prefixed message from a Unix socket.
    Header: 4-byte big-endian uint32 carrying the payload length.
    Raises ValueError if the declared length exceeds max_bytes.
    """
    raw_len = _recv_exactly(conn, 4)
    msg_len = int.from_bytes(raw_len, "big")
    if msg_len > max_bytes:
        raise ValueError(f"Oversized message: {msg_len} > {max_bytes} bytes")
    return _recv_exactly(conn, msg_len)


def _recv_exactly(conn: socket.socket, n: int) -> bytes:
    """Read exactly n bytes, looping over partial reads."""
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed before full message received")
        buf.extend(chunk)
    return bytes(buf)


def _send_framed(conn: socket.socket, payload: bytes):
    """Send a length-prefixed message."""
    conn.sendall(len(payload).to_bytes(4, "big") + payload)


# ─── BTRFS helpers ────────────────────────────────────────────────────────────

def _get_btrfs_root_subvolume() -> str:
    """
    Detect the actual BTRFS subvolume that backs '/'.
    Snapshotting '/' directly via btrfs CLI operates on the mount, not the
    subvolume — so we must resolve the real subvolume path first.
    Falls back to '/' on non-BTRFS or detection failure.
    """
    try:
        result = subprocess.run(
            ["btrfs", "subvolume", "show", "/"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                stripped = line.strip()
                # First non-empty line that contains a '/' is the subvolume path
                if stripped and not stripped.startswith(("Name:", "UUID:", "Parent")):
                    if "/" in stripped:
                        # Try to find the BTRFS filesystem mount so we can
                        # build an absolute path like /mnt/btrfs-root/@root
                        fs_root = _find_btrfs_mount()
                        if fs_root:
                            candidate = os.path.join(fs_root, stripped.lstrip("/"))
                            if os.path.isdir(candidate):
                                return candidate
    except Exception as e:
        logger.debug("BTRFS subvolume detection error: %s", e)
    return "/"  # Conservative fallback — works on single-subvolume layouts


def _find_btrfs_mount() -> str | None:
    """Return the path where the BTRFS root filesystem is mounted, if any."""
    try:
        result = subprocess.run(
            ["findmnt", "-t", "btrfs", "-n", "-o", "TARGET", "--submounts"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            mounts = [m.strip() for m in result.stdout.splitlines() if m.strip()]
            # Prefer a mount that is NOT '/' — it's typically the raw FS root
            for m in mounts:
                if m != "/":
                    return m
    except Exception:
        pass
    return None


def _has_btrfs(path: str = "/") -> bool:
    try:
        result = subprocess.run(["stat", "-f", "-c", "%T", path],
            capture_output=True, text=True, timeout=3)
        return "btrfs" in result.stdout.lower()
    except Exception:
        return False


def _create_btrfs_snapshot(label: str) -> str | None:
    """Create a BTRFS snapshot of the correct root subvolume and return its path."""
    snap_dir = f"/snapshots/heal_{label}_{int(time.time())}"
    source   = _get_btrfs_root_subvolume()
    try:
        subprocess.run(
            ["btrfs", "subvolume", "snapshot", source, snap_dir],
            check=True, timeout=15, capture_output=True,
        )
        logger.info("HealingBridge: Snapshot created at %s (source: %s)", snap_dir, source)
        return snap_dir
    except Exception as e:
        logger.warning("HealingBridge: BTRFS snapshot failed: %s", e)
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
    Rule-based crash analysis — used when Nyx AI is unavailable.
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
    Forward crash data to Nyx via the broker for AI-augmented analysis.
    Uses length-prefixed framing to match the broker wire protocol.
    Returns a HealingPlan dict if the AI responds, or None if unavailable.
    """
    broker_sock = os.path.join(RUNTIME_DIR, "broker.sock")
    if not os.path.exists(broker_sock):
        return None

    try:
        # Step 1: Request a permission token from the broker
        request_payload = json.dumps({
            "source_id":       "sentinel",
            "target_resource": "nyx_heal",
            "action":          "analyze_crash",
            "context":         "healing",
            "crash_log":       crash_log[:4096],   # cap to avoid broker overload
            "service":         service,
        }).encode()

        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(10.0)
        s.connect(broker_sock)
        _send_framed(s, request_payload)

        resp_raw = _recv_framed(s, max_bytes=65536)
        s.close()
        resp = json.loads(resp_raw.decode())

        if resp.get("status") != "GRANTED":
            logger.debug("HealingBridge: Broker denied nyx_heal for %s: %s",
                         service, resp.get("reason", "no reason"))
            return None

        token = resp.get("token", "")
        logger.info("HealingBridge: Broker granted analysis token for %s", service)

        # Step 2: Forward crash log to the AICore nyx socket for LLM analysis
        nyx_sock_path = os.path.join(RUNTIME_DIR, "nyx.sock")
        if not os.path.exists(nyx_sock_path):
            logger.debug("HealingBridge: Nyx socket not available (%s)", nyx_sock_path)
            return None

        nyx_request = json.dumps({
            "type":      "heal_analyze",
            "token":     token,
            "service":   service,
            "crash_log": crash_log[:4096],
        }).encode()

        ns = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        ns.settimeout(30.0)   # LLM inference may take a moment
        ns.connect(nyx_sock_path)
        _send_framed(ns, nyx_request)

        nyx_raw = _recv_framed(ns, max_bytes=131072)
        ns.close()
        nyx_resp = json.loads(nyx_raw.decode())

        if nyx_resp.get("status") == "ok" and "plan" in nyx_resp:
            plan = nyx_resp["plan"]
            plan.setdefault("confidence", "nyx_ai")
            plan.setdefault("verify_cmd", f"systemctl is-active {service}")
            logger.info("HealingBridge: Nyx AI plan for %s: %s — %s",
                        service, plan.get("action"), plan.get("reason", ""))
            return plan

        logger.debug("HealingBridge: Nyx returned unexpected response: %s",
                     nyx_resp.get("status"))
        return None

    except Exception as e:
        logger.debug("HealingBridge: Nyx analysis unavailable: %s", e)
        return None


# ─── Execute Healing Plan ──────────────────────────────────────────────────────

_SAFE_UNIT_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def _execute_healing_plan(service: str, plan: dict) -> bool:
    """Apply the healing plan safely with zero arbitrary shell execution."""
    if not service or not _SAFE_UNIT_PATTERN.match(service):
        logger.error("HealingBridge: Rejected invalid/unsafe service name: %s", service)
        return False

    snapshot_path = None

    # Step 1: Optionally create BTRFS snapshot before patching
    if plan.get("btrfs_snapshot") and _has_btrfs():
        snapshot_path = _create_btrfs_snapshot(service.replace("-", "_"))

    # Step 2: Apply strictly vetted patch primitive (No arbitrary shell=True)
    action = plan.get("action", "restart")
    patch_cmd = plan.get("patch_cmd")

    # If the patch_cmd is specifically reset-failed, run safely without shell
    if patch_cmd and "reset-failed" in patch_cmd:
        try:
            logger.info("HealingBridge: Resetting failed state for %s", service)
            subprocess.run(["systemctl", "reset-failed", service],
                           shell=False, timeout=10, capture_output=True)
        except Exception as e:
            logger.error("HealingBridge: reset-failed command error: %s", e)

    # Step 3: Restart or reload the service using direct non-shell systemctl
    try:
        if action == "reload":
            logger.info("HealingBridge: Reloading %s...", service)
            subprocess.run(["systemctl", "reload", service],
                           shell=False, timeout=15, capture_output=True)
        else:
            logger.info("HealingBridge: Restarting %s...", service)
            subprocess.run(["systemctl", "restart", service],
                           shell=False, timeout=15, capture_output=True)
        time.sleep(2)
    except Exception as e:
        logger.error("HealingBridge: Service restart failed: %s", e)
        return False

    # Step 4: Verify recovery using strictly parameterized check
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            shell=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        recovered = (result.returncode == 0 and result.stdout.strip() == "active")
        if recovered:
            logger.info("HealingBridge: Service %s recovered successfully.", service)
        else:
            logger.warning(
                "HealingBridge: Service %s still down after restart (status: %s).",
                service, result.stdout.strip()
            )
        return recovered
    except Exception as e:
        logger.error("HealingBridge: Recovery verification check error: %s", e)
        return False


# ─── Healing Bridge Server ────────────────────────────────────────────────────

class NyxHealingServer:
    """Unix socket server receiving crash reports and returning healing plans."""

    def __init__(self):
        self._running = False
        self._server  = None
        self._btrfs_available = _has_btrfs()
        # Lazy-import tracker to avoid circular imports
        self._tracker = None

    def _get_tracker(self):
        if self._tracker is None:
            try:
                from healing_outcome_tracker import get_tracker  # type: ignore
                self._tracker = get_tracker()
            except Exception as e:
                logger.warning("HealingBridge: Tracker unavailable: %s", e)
        return self._tracker

    def _setup_socket(self):
        os.makedirs(RUNTIME_DIR, mode=0o775, exist_ok=True)
        if os.path.exists(HEAL_SOCKET):
            os.remove(HEAL_SOCKET)
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(HEAL_SOCKET)
        os.chmod(HEAL_SOCKET, 0o660)
        self._server.listen(4)
        logger.info("HealingBridge listening on %s", HEAL_SOCKET)

    def _handle(self, conn: socket.socket):
        try:
            # Use length-prefixed framing so large crash logs arrive complete
            data = _recv_framed(conn, max_bytes=4 * 1024 * 1024)
            if not data:
                return
            payload = json.loads(data.decode("utf-8", errors="replace"))
            service   = payload.get("service", "unknown")
            crash_log = payload.get("crash_log", "")
            logger.info(
                "HealingBridge: Received crash for %s (%d chars)",
                service, len(crash_log)
            )

            # Analyze — prefer Nyx AI, fall back to rule-based
            plan = _try_nyx_analysis(service, crash_log) \
                   or _analyze_crash_log(service, crash_log)
            logger.info(
                "HealingBridge: Plan for %s: %s — %s (confidence: %s)",
                service, plan["action"], plan["reason"], plan.get("confidence")
            )

            # Record attempt in the outcome tracker BEFORE dispatching heal
            tracker = self._get_tracker()
            attempt_id = None
            if tracker:
                try:
                    attempt_id = tracker.record_attempt(service, plan, applied=True)
                    logger.info(
                        "HealingBridge: Tracker recorded attempt %s for %s",
                        attempt_id, service
                    )
                except Exception as te:
                    logger.warning("HealingBridge: Tracker record failed: %s", te)

            # Execute healing in background (don't block socket response)
            def _bg():
                _execute_healing_plan(service, plan)

            threading.Thread(target=_bg, daemon=True).start()

            _send_framed(conn, json.dumps({"status": "ok", "plan": plan}).encode())

        except Exception as e:
            logger.error("HealingBridge: Handler error: %s", e)
            try:
                _send_framed(conn, json.dumps({"status": "error", "reason": str(e)}).encode())
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

        logger.info("HealingBridge ready. BTRFS: %s", self._btrfs_available)

        # Notify systemd that we are ready (if using Type=notify)
        if _SD:
            try:
                _SD.notify("READY=1")
            except Exception:
                pass

        try:
            while self._running:
                try:
                    self._server.settimeout(1.0)
                    conn, _ = self._server.accept()
                    threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
                except socket.timeout:
                    _sd_watchdog()   # ping watchdog every idle second
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
    Send a crash report to the healing bridge using length-prefixed framing.
    Returns the healing plan dict or None on failure.
    """
    if not os.path.exists(HEAL_SOCKET):
        logger.warning("HealingBridge socket not available — skipping AI healing.")
        return None
    try:
        payload = json.dumps({
            "service":   service,
            "crash_log": crash_log,
            "unit_file": unit_file,
        }).encode()
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(15.0)
        s.connect(HEAL_SOCKET)
        _send_framed(s, payload)
        resp_raw = _recv_framed(s, max_bytes=65536)
        s.close()
        return json.loads(resp_raw.decode())
    except Exception as e:
        logger.error("send_crash_report: %s", e)
        return None


if __name__ == "__main__":
    NyxHealingServer().run()
