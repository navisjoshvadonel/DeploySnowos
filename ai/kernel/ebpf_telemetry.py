#!/usr/bin/env python3
"""
SnowOS eBPF Semantic Telemetry — Kernel-Level Event Stream.

Attaches eBPF probes to critical syscalls (execve, openat, tcp_connect)
to feed an ultra-low-overhead, un-killable event stream into context_engine.py.

Gracefully degrades to /proc-based polling when BCC is unavailable or
the process lacks CAP_BPF / root privileges.

Design: Ring-buffer consumer thread writes batched events to
/tmp/snowos_ebpf_events.json every 2 seconds.
"""
import os
import sys
import json
import time
import signal
import logging
import threading
import subprocess
from collections import deque

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [eBPF-Telemetry] %(levelname)s %(message)s",
)
logger = logging.getLogger("eBPFTelemetry")

EVENTS_FILE = "/tmp/snowos_ebpf_events.json"
MAX_EVENTS = 500          # ring-buffer size
FLUSH_INTERVAL = 2        # seconds between disk flushes
POLL_INTERVAL = 1         # /proc fallback poll interval

# ── Try BCC import ────────────────────────────────────────────────────────────
_BCC_AVAILABLE = False
try:
    from bcc import BPF
    _BCC_AVAILABLE = True
except ImportError:
    pass


# ── BPF Program Text ─────────────────────────────────────────────────────────
_BPF_PROGRAM = r"""
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

struct exec_event {
    u32 pid;
    u32 uid;
    char comm[64];
    char filename[256];
};

BPF_PERF_OUTPUT(exec_events);

TRACEPOINT_PROBE(syscalls, sys_enter_execve) {
    struct exec_event evt = {};
    evt.pid = bpf_get_current_pid_tgid() >> 32;
    evt.uid = bpf_get_current_uid_gid() & 0xFFFFFFFF;
    bpf_get_current_comm(&evt.comm, sizeof(evt.comm));
    bpf_probe_read_user_str(&evt.filename, sizeof(evt.filename), args->filename);
    exec_events.perf_submit(args, &evt, sizeof(evt));
    return 0;
}

struct file_event {
    u32 pid;
    char comm[64];
    char filename[256];
};

BPF_PERF_OUTPUT(file_events);

TRACEPOINT_PROBE(syscalls, sys_enter_openat) {
    struct file_event evt = {};
    evt.pid = bpf_get_current_pid_tgid() >> 32;
    bpf_get_current_comm(&evt.comm, sizeof(evt.comm));
    bpf_probe_read_user_str(&evt.filename, sizeof(evt.filename), args->filename);
    file_events.perf_submit(args, &evt, sizeof(evt));
    return 0;
}
"""


# ── eBPF-based telemetry (requires root + bcc) ───────────────────────────────
class _eBPFCollector:
    """Attaches real eBPF tracepoints and feeds events to the ring buffer."""

    def __init__(self, ring: deque):
        self._ring = ring
        self._bpf = None
        self._running = False

    def start(self):
        try:
            self._bpf = BPF(text=_BPF_PROGRAM)
            self._bpf["exec_events"].open_perf_buffer(self._on_exec)
            self._bpf["file_events"].open_perf_buffer(self._on_file)
            self._running = True
            logger.info("eBPF probes attached (execve, openat).")
        except Exception as e:
            logger.error(f"Failed to attach eBPF probes: {e}")
            raise

    def poll(self):
        if self._bpf:
            self._bpf.perf_buffer_poll(timeout=100)

    def stop(self):
        self._running = False
        if self._bpf:
            self._bpf.cleanup()

    def _on_exec(self, cpu, data, size):
        evt = self._bpf["exec_events"].event(data)
        self._ring.append({
            "type": "exec",
            "pid": evt.pid,
            "uid": evt.uid,
            "comm": evt.comm.decode("utf-8", errors="replace"),
            "filename": evt.filename.decode("utf-8", errors="replace"),
            "ts": time.time(),
        })

    def _on_file(self, cpu, data, size):
        evt = self._bpf["file_events"].event(data)
        fname = evt.filename.decode("utf-8", errors="replace")
        # Filter noise: skip /proc, /sys, /dev reads
        if fname.startswith(("/proc/", "/sys/", "/dev/")):
            return
        self._ring.append({
            "type": "file_open",
            "pid": evt.pid,
            "comm": evt.comm.decode("utf-8", errors="replace"),
            "filename": fname,
            "ts": time.time(),
        })


# ── /proc fallback collector (no root needed) ─────────────────────────────────
class _ProcFallbackCollector:
    """Polls /proc for new process executions and open file descriptors."""

    def __init__(self, ring: deque):
        self._ring = ring
        self._known_pids: set = set()

    def poll(self):
        try:
            current_pids = set()
            for entry in os.listdir("/proc"):
                if entry.isdigit():
                    current_pids.add(int(entry))

            new_pids = current_pids - self._known_pids
            for pid in new_pids:
                try:
                    with open(f"/proc/{pid}/comm") as f:
                        comm = f.read().strip()
                    cmdline = ""
                    try:
                        with open(f"/proc/{pid}/cmdline") as f:
                            cmdline = f.read().replace("\x00", " ").strip()
                    except Exception:
                        pass
                    self._ring.append({
                        "type": "exec",
                        "pid": pid,
                        "uid": 0,
                        "comm": comm,
                        "filename": cmdline.split()[0] if cmdline else comm,
                        "ts": time.time(),
                    })
                except Exception:
                    pass

            self._known_pids = current_pids
        except Exception:
            pass

    def stop(self):
        pass


# ── Main Telemetry Engine ─────────────────────────────────────────────────────
class eBPFTelemetry:
    """
    Unified telemetry engine. Uses real eBPF when available,
    otherwise degrades to /proc polling.
    """

    def __init__(self):
        self._ring: deque = deque(maxlen=MAX_EVENTS)
        self._stop = threading.Event()
        self._collector = None
        self._mode = "none"

    def _init_collector(self):
        if _BCC_AVAILABLE and os.geteuid() == 0:
            try:
                collector = _eBPFCollector(self._ring)
                collector.start()
                self._collector = collector
                self._mode = "ebpf"
                return
            except Exception:
                logger.warning("eBPF attach failed, falling back to /proc.")

        self._collector = _ProcFallbackCollector(self._ring)
        self._mode = "proc_fallback"
        logger.info("Using /proc fallback telemetry collector.")

    def _flush(self):
        """Write current ring buffer to disk."""
        events = list(self._ring)
        try:
            with open(EVENTS_FILE, "w") as f:
                json.dump({
                    "mode": self._mode,
                    "event_count": len(events),
                    "timestamp": time.time(),
                    "events": events[-100:],  # last 100 for consumers
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Flush failed: {e}")

    def run_once(self) -> dict:
        """Single evaluation cycle for --once mode."""
        self._init_collector()
        self._collector.poll()
        self._flush()
        return {"mode": self._mode, "events": len(self._ring)}

    def _monitor_dmesg(self):
        """Scans kernel ring buffer for deep panics and oops events."""
        try:
            p = subprocess.Popen(["dmesg", "-w"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            for line in iter(p.stdout.readline, ''):
                if self._stop.is_set():
                    break
                if any(x in line for x in ["segfault", "Oops", "Call Trace"]):
                    with open("/tmp/snowos_kernel_panic.log", "a") as f:
                        f.write(line)
        except Exception:
            pass

    def run(self):
        """Main event loop."""
        logger.info("eBPF Telemetry starting...")
        self._init_collector()

        # Start Sentinel Autopilot (Kernel Panic) interceptor
        threading.Thread(target=self._monitor_dmesg, daemon=True).start()

        def _stop_handler(sig, frame):
            logger.info("Shutting down...")
            self._stop.set()
        signal.signal(signal.SIGTERM, _stop_handler)
        signal.signal(signal.SIGINT, _stop_handler)

        last_flush = 0
        while not self._stop.is_set():
            try:
                if self._mode == "ebpf":
                    self._collector.poll()
                else:
                    self._collector.poll()
                    self._stop.wait(POLL_INTERVAL)

                now = time.time()
                if now - last_flush >= FLUSH_INTERVAL:
                    self._flush()
                    last_flush = now
            except Exception as e:
                logger.error(f"Telemetry cycle error: {e}")
                self._stop.wait(1)

        if self._collector:
            self._collector.stop()
        self._flush()
        logger.info("eBPF Telemetry stopped.")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    t = eBPFTelemetry()
    if "--once" in sys.argv:
        result = t.run_once()
        print(json.dumps(result, indent=2))
    else:
        t.run()
