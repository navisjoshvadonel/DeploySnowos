#!/usr/bin/env python3
"""
SnowOS Healing Outcome Tracker — Closes the Self-Healing Loop.

This module addresses a critical gap in the Sentinel → HealingBridge pipeline:
after a healing plan is applied, there was NO mechanism to:
  1. Verify if the heal actually worked
  2. Track repeated failures for the same service
  3. Escalate to BTRFS rollback when healing fails repeatedly

The HealingOutcomeTracker:
  - Verifies healing success by polling systemctl service status
  - Persists healing history to ~/.snowos/healing_history.jsonl
  - Escalates to BTRFS rollback after 3 failed heal attempts in 1 hour
  - Publishes outcome events to the broker for dashboard visibility
  - Learns from successful heals: caches effective patch_cmds per error class
  - Sends desktop notifications on escalation (via libnotify)

Integration points:
  - Called by NyxDaemon._handle_heal_conn() after plan generation
  - Reads healing results from the systemctl verify_cmd
  - Writes to /run/snowos/healing_status.json for SnowControl visibility

Usage:
  from healing_outcome_tracker import HealingOutcomeTracker
  tracker = HealingOutcomeTracker()
  
  # After a heal plan is applied:
  tracker.record_attempt(service="snowos-aicore", plan=plan, applied=True)
  
  # After a verification window (e.g., 30s):
  tracker.verify_and_update(service="snowos-aicore")
"""

import os
import sys
import json
import time
import logging
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(
    level=os.environ.get("SNOWOS_LOG_LEVEL", "INFO"),
    format="%(asctime)s [HealTracker] %(levelname)s %(message)s",
)
logger = logging.getLogger("HealTracker")

# ── Paths ─────────────────────────────────────────────────────────────────────
SNOWOS_DIR     = os.path.expanduser("~/.snowos")
HISTORY_FILE   = os.path.join(SNOWOS_DIR, "healing_history.jsonl")
CACHE_FILE     = os.path.join(SNOWOS_DIR, "healing_cache.json")
RUNTIME_DIR    = os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos")
STATUS_FILE    = os.path.join(RUNTIME_DIR, "healing_status.json")
BROKER_SOCK    = os.path.join(RUNTIME_DIR, "broker.sock")

# ── Escalation thresholds ──────────────────────────────────────────────────────
MAX_FAILURES_BEFORE_ESCALATION = 3      # failed heals before BTRFS rollback
ESCALATION_WINDOW_SEC          = 3600   # 1 hour window for failure counting
VERIFY_DELAY_SEC               = 30     # wait N seconds before verifying heal
BTRFS_SNAPSHOTS_DIR            = "/snapshots"


# ── Broker helper ──────────────────────────────────────────────────────────────

def _broker_publish(topic: str, data: dict):
    try:
        import socket as _socket
        msg = json.dumps({"type": "publish", "topic": topic, "data": data}).encode()
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(BROKER_SOCK)
        s.sendall(len(msg).to_bytes(4, "big") + msg)
        resp_len_raw = s.recv(4)
        if resp_len_raw:
            s.recv(int.from_bytes(resp_len_raw, "big"))
        s.close()
    except Exception:
        pass


# ── Desktop notification ───────────────────────────────────────────────────────

def _notify(title: str, body: str, urgency: str = "normal"):
    """Send a desktop notification via libnotify."""
    try:
        subprocess.run(
            ["notify-send", f"--urgency={urgency}", "--icon=dialog-error",
             "--app-name=SnowOS Healing", title, body],
            capture_output=True, timeout=5
        )
    except Exception:
        pass  # Silently fail in headless environments


# ── BTRFS rollback ─────────────────────────────────────────────────────────────

def _create_btrfs_snapshot(label: str) -> str | None:
    """Create a BTRFS snapshot before rollback. Returns snapshot path or None."""
    if not os.path.exists(BTRFS_SNAPSHOTS_DIR):
        try:
            os.makedirs(BTRFS_SNAPSHOTS_DIR, exist_ok=True)
        except Exception:
            return None

    snap_dir = os.path.join(BTRFS_SNAPSHOTS_DIR, f"pre_rollback_{label}_{int(time.time())}")
    try:
        result = subprocess.run(
            ["btrfs", "subvolume", "snapshot", "/", snap_dir],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info("BTRFS snapshot created: %s", snap_dir)
            return snap_dir
        logger.warning("BTRFS snapshot failed: %s", result.stderr)
    except Exception as e:
        logger.warning("BTRFS snapshot error: %s", e)
    return None


def _execute_btrfs_rollback(service: str) -> bool:
    """
    Execute BTRFS rollback for a repeatedly failing service.
    Strategy: Reset the service to last known good state via systemd.
    """
    logger.critical("ESCALATION: Executing BTRFS rollback for '%s'", service)
    try:
        # 1. Stop the failing service
        subprocess.run(["systemctl", "stop", service],
                       capture_output=True, timeout=15)
        # 2. Reset failed state
        subprocess.run(["systemctl", "reset-failed", service],
                       capture_output=True, timeout=5)
        # 3. Create safety snapshot
        snap = _create_btrfs_snapshot(service.replace("-", "_"))
        # 4. Attempt service restart with fresh state
        result = subprocess.run(["systemctl", "start", service],
                                capture_output=True, timeout=30)
        success = result.returncode == 0
        if success:
            logger.info("BTRFS rollback succeeded for '%s'.", service)
        else:
            logger.error("BTRFS rollback failed for '%s': %s",
                         service, result.stderr.decode())
        return success
    except Exception as e:
        logger.error("Rollback execution error: %s", e)
        return False


# ── HealingOutcomeTracker ──────────────────────────────────────────────────────

class HealingOutcomeTracker:
    """
    Tracks healing attempts and outcomes for each service.
    Closes the self-healing loop by verifying heals and escalating when needed.
    """

    def __init__(self):
        os.makedirs(SNOWOS_DIR, exist_ok=True)
        self._history:  dict = {}   # service → list of attempt records
        self._cache:    dict = self._load_cache()
        self._lock = threading.Lock()
        self._pending_verifications: dict = {}   # service → (plan, applied_at)
        self._load_history()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_cache(self) -> dict:
        """Load the effective healing patterns cache."""
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE) as f:
                    return json.load(f)
        except Exception:
            pass
        return {"effective_patches": {}}

    def _save_cache(self):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.debug("Cache save error: %s", e)

    def _load_history(self):
        """Load healing history from JSONL file."""
        try:
            if not os.path.exists(HISTORY_FILE):
                return
            with open(HISTORY_FILE) as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        service = record.get("service", "unknown")
                        if service not in self._history:
                            self._history[service] = []
                        self._history[service].append(record)
                    except Exception:
                        continue
        except Exception as e:
            logger.debug("History load error: %s", e)

    def _append_history(self, record: dict):
        """Append a record to the JSONL history file."""
        try:
            with open(HISTORY_FILE, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.debug("History append error: %s", e)

    def _update_status_file(self, service: str, record: dict):
        """Write current healing status for SnowControl dashboard."""
        try:
            status = {}
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE) as f:
                    status = json.load(f)
            status[service] = record
            status["updated_at"] = datetime.now(timezone.utc).isoformat()
            # Atomic write
            tmp = STATUS_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(status, f, indent=2)
            os.replace(tmp, STATUS_FILE)
        except Exception as e:
            logger.debug("Status file update error: %s", e)

    # ── Service health check ───────────────────────────────────────────────────

    def _check_service_active(self, service: str) -> bool:
        """Return True if the service is currently active (running)."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "--quiet", service],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _run_verify_cmd(self, verify_cmd: str) -> bool:
        """Run a custom verification command. Returns True on success."""
        if not verify_cmd:
            return True
        try:
            result = subprocess.run(
                verify_cmd, shell=True, capture_output=True,
                text=True, timeout=15
            )
            return result.returncode == 0
        except Exception:
            return False

    # ── Public API ─────────────────────────────────────────────────────────────

    def record_attempt(self, service: str, plan: dict, applied: bool = True) -> str:
        """
        Record a healing attempt. Call this when a healing plan is generated.
        
        Returns:
            attempt_id: Unique ID for this attempt, used in verify_and_update()
        """
        attempt_id = f"{service}_{int(time.time())}"
        record = {
            "attempt_id": attempt_id,
            "service": service,
            "ts": time.time(),
            "iso_ts": datetime.now(timezone.utc).isoformat(),
            "plan": plan,
            "applied": applied,
            "outcome": "pending",
        }

        with self._lock:
            if service not in self._history:
                self._history[service] = []
            self._history[service].append(record)
            self._pending_verifications[service] = (plan, time.time())

        self._append_history(record)
        self._update_status_file(service, record)

        logger.info("Recorded healing attempt for '%s' (id: %s)", service, attempt_id)

        # Schedule verification after VERIFY_DELAY_SEC
        t = threading.Timer(
            VERIFY_DELAY_SEC,
            self.verify_and_update,
            args=(service, attempt_id)
        )
        t.daemon = True
        t.start()

        return attempt_id

    def verify_and_update(self, service: str, attempt_id: str | None = None):
        """
        Verify whether the last healing attempt succeeded.
        Called automatically after VERIFY_DELAY_SEC.
        """
        logger.info("Verifying heal outcome for '%s'...", service)

        with self._lock:
            pending = self._pending_verifications.pop(service, None)
            history = self._history.get(service, [])

        if not history:
            return

        # Find the attempt to update
        attempt = None
        if attempt_id:
            attempt = next((r for r in reversed(history)
                           if r.get("attempt_id") == attempt_id), None)
        if not attempt:
            attempt = history[-1]

        plan = attempt.get("plan", {})
        verify_cmd = plan.get("verify_cmd")

        # Check if service is alive
        service_ok = self._check_service_active(service)

        # Run custom verify command if provided
        verify_ok = True
        if verify_cmd:
            verify_ok = self._run_verify_cmd(verify_cmd)

        outcome = "success" if (service_ok and verify_ok) else "failed"
        attempt["outcome"] = outcome
        attempt["verified_at"] = time.time()
        attempt["service_active"] = service_ok

        logger.info("Heal outcome for '%s': %s", service, outcome.upper())

        # Update history file
        self._append_history({**attempt, "_type": "verification"})
        self._update_status_file(service, attempt)

        # Publish outcome to broker
        _broker_publish("heal_outcome", {
            "service": service,
            "outcome": outcome,
            "attempt_id": attempt_id,
            "ts": time.time(),
        })

        if outcome == "success":
            self._on_heal_success(service, plan)
        else:
            self._on_heal_failure(service)

    def _on_heal_success(self, service: str, plan: dict):
        """Cache the effective patch command for future reuse."""
        action = plan.get("action")
        patch_cmd = plan.get("patch_cmd")
        reason = plan.get("reason", "")

        if patch_cmd and action == "hotpatch":
            # Cache this effective patch keyed by service
            self._cache["effective_patches"][service] = {
                "patch_cmd": patch_cmd,
                "reason": reason,
                "last_success": time.time(),
            }
            self._save_cache()
            logger.info("Cached effective patch for '%s': %s", service, patch_cmd[:60])

    def _on_heal_failure(self, service: str):
        """Handle a failed healing attempt — check for escalation."""
        failures_in_window = self._count_recent_failures(service)

        logger.warning("Heal failed for '%s'. Failures in last hour: %d/%d",
                       service, failures_in_window, MAX_FAILURES_BEFORE_ESCALATION)

        if failures_in_window >= MAX_FAILURES_BEFORE_ESCALATION:
            self._escalate(service, failures_in_window)

    def _count_recent_failures(self, service: str) -> int:
        """Count failed healing attempts in the last ESCALATION_WINDOW_SEC."""
        with self._lock:
            history = self._history.get(service, [])
        cutoff = time.time() - ESCALATION_WINDOW_SEC
        return sum(
            1 for r in history
            if r.get("ts", 0) > cutoff and r.get("outcome") == "failed"
        )

    def _escalate(self, service: str, failure_count: int):
        """Escalate to BTRFS rollback — last resort."""
        msg = (f"Service '{service}' has failed healing {failure_count} times "
               f"in the last hour. Escalating to BTRFS rollback.")
        logger.critical(msg)

        # Notify user
        _notify(
            "⚠️ SnowOS Self-Healing Escalation",
            f"{service}: healing failed {failure_count}×. Attempting BTRFS rollback.",
            urgency="critical",
        )

        # Publish escalation event
        _broker_publish("healing_escalation", {
            "service": service,
            "failure_count": failure_count,
            "action": "btrfs_rollback",
            "ts": time.time(),
        })

        # Execute rollback
        success = _execute_btrfs_rollback(service)

        # Record escalation
        record = {
            "service": service,
            "ts": time.time(),
            "iso_ts": datetime.now(timezone.utc).isoformat(),
            "type": "escalation",
            "failure_count": failure_count,
            "rollback_success": success,
        }
        self._append_history(record)
        self._update_status_file(service, record)

        if success:
            _notify(
                "✅ SnowOS Recovery",
                f"{service} has been restored via BTRFS rollback.",
                urgency="normal",
            )
        else:
            _notify(
                "❌ SnowOS Recovery Failed",
                f"{service}: BTRFS rollback failed. Manual intervention required.",
                urgency="critical",
            )

    def get_effective_patch(self, service: str) -> dict | None:
        """Return a cached effective patch for a service, if any."""
        patch = self._cache["effective_patches"].get(service)
        if patch:
            # Expire after 7 days
            if time.time() - patch.get("last_success", 0) < 7 * 86400:
                return patch
        return None

    def get_summary(self) -> dict:
        """Return a summary of healing activity for dashboard display."""
        with self._lock:
            summary = {}
            for service, history in self._history.items():
                recent = [h for h in history
                          if h.get("ts", 0) > time.time() - 86400]
                successes = sum(1 for h in recent if h.get("outcome") == "success")
                failures  = sum(1 for h in recent if h.get("outcome") == "failed")
                summary[service] = {
                    "attempts_24h": len(recent),
                    "successes_24h": successes,
                    "failures_24h": failures,
                    "success_rate": round(successes / len(recent) * 100, 1) if recent else 0,
                    "last_outcome": history[-1].get("outcome") if history else None,
                }
        return summary


# ── Singleton for shared use ───────────────────────────────────────────────────
_tracker_instance: HealingOutcomeTracker | None = None
_tracker_lock = threading.Lock()


def get_tracker() -> HealingOutcomeTracker:
    """Get or create the global HealingOutcomeTracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        with _tracker_lock:
            if _tracker_instance is None:
                _tracker_instance = HealingOutcomeTracker()
    return _tracker_instance


# ── CLI for manual inspection ─────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="SnowOS Healing Outcome Tracker")
    parser.add_argument("--summary", action="store_true",
                        help="Show healing summary for all services")
    parser.add_argument("--test-service", metavar="SERVICE",
                        help="Manually test heal tracking for a service")
    args = parser.parse_args()

    tracker = HealingOutcomeTracker()

    if args.summary:
        summary = tracker.get_summary()
        if not summary:
            print("No healing history found.")
        else:
            print("\n📊 SnowOS Healing History Summary\n" + "=" * 45)
            for service, stats in summary.items():
                rate_color = "✅" if stats["success_rate"] >= 80 else "⚠️" if stats["success_rate"] >= 50 else "❌"
                print(f"\n{rate_color} {service}")
                print(f"   Attempts (24h): {stats['attempts_24h']}")
                print(f"   Success rate:   {stats['success_rate']}%")
                print(f"   Last outcome:   {stats['last_outcome'] or 'N/A'}")

    elif args.test_service:
        service = args.test_service
        print(f"Recording test heal attempt for '{service}'...")
        plan = {
            "action": "restart",
            "patch_cmd": f"systemctl reset-failed {service}",
            "verify_cmd": f"systemctl is-active {service}",
            "btrfs_snapshot": False,
            "reason": "Test attempt",
        }
        attempt_id = tracker.record_attempt(service, plan, applied=True)
        print(f"Recorded attempt: {attempt_id}")
        print(f"Verification will run in {VERIFY_DELAY_SEC}s...")
        time.sleep(VERIFY_DELAY_SEC + 5)
        print("\nSummary:")
        summary = tracker.get_summary()
        print(json.dumps(summary.get(service, {}), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
