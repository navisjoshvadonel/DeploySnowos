import json
import os
from datetime import datetime, timezone
import http.server
from pathlib import Path
import socketserver

HOST = os.environ.get("SNOWOS_CONTROL_HOST", "127.0.0.1")
PORT = int(os.environ.get("SNOWOS_CONTROL_PORT", "8000"))
BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
LOCAL_CONFIG_DIR = BACKEND_DIR.parents[3] / "config"
RUNTIME_DIR = Path(os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos"))
BOOT_STATUS_FILE = Path(os.environ.get("SNOWOS_BOOT_STATUS_FILE", str(RUNTIME_DIR / "boot-status.json")))
FEATURE_FLAGS_FILE = Path(
    os.environ.get("SNOWOS_FEATURE_FLAGS_FILE", str(RUNTIME_DIR / "feature-flags.json"))
)
AI_FEATURES_FILE = Path(
    os.environ.get("SNOWOS_AI_FEATURES_FILE", "/etc/snowos/ai_features.json")
)
BRAND_FILE = Path(os.environ.get("SNOWOS_BRAND_FILE", "/etc/snowos/brand.json"))

if not AI_FEATURES_FILE.exists():
    AI_FEATURES_FILE = LOCAL_CONFIG_DIR / "ai_features.json"

if not BRAND_FILE.exists():
    BRAND_FILE = LOCAL_CONFIG_DIR / "brand.json"

mock_events = [
    {"id": 1, "time": "10:24:01", "source": "app.browser", "action": "network.wan", "status": "GRANTED", "type": "broker"},
    {"id": 2, "time": "10:24:05", "source": "app.mock_app", "action": "display.surface", "status": "GRANTED", "type": "broker"},
    {"id": 3, "time": "10:24:06", "source": "app.mock_app", "action": "hardware.keyboard", "status": "DENIED", "type": "broker"},
    {"id": 4, "time": "10:24:07", "source": "app.mock_app", "action": "keylogger prevention", "status": "CRITICAL", "type": "sentinel"},
]


def _read_json_file(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def _format_cpu():
    try:
        load_avg = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 4
        return f"{min(100, round((load_avg / cpu_count) * 100))}%"
    except OSError:
        return "--"


def _format_ram():
    try:
        meminfo = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, value = line.split(":", 1)
                meminfo[key] = int(value.strip().split()[0])
        used_kb = meminfo["MemTotal"] - meminfo["MemAvailable"]
        return f"{used_kb / 1024 / 1024:.1f} GB"
    except (OSError, KeyError, ValueError):
        return "--"


def _load_brand():
    return _read_json_file(
        BRAND_FILE,
        {
            "brand_name": "SnowOS",
            "brand_channel": "NYX",
            "control_plane_name": "SnowControl",
        },
    )


def _load_boot_status():
    return _read_json_file(
        BOOT_STATUS_FILE,
        {
            "status": "unknown",
            "profile": "balanced",
            "trust_score": 88,
            "identity": {"persona": "Guide", "mood": "Calm Focus", "scene": "Glacier Deck"},
            "feature_count": 0,
            "warnings": ["SnowOS boot status has not been published yet."],
            "managed_services": [],
            "boot_duration_ms": 0,
        },
    )


def _load_feature_flags():
    return _read_json_file(
        FEATURE_FLAGS_FILE,
        {
            "profile": "balanced",
            "enabled": [],
            "feature_outputs": {},
        },
    )


def _build_system_state(boot_status):
    agents_active = len(boot_status.get("enabled_feature_ids", [])) or boot_status.get("feature_count", 0)
    return {
        "cpu": _format_cpu(),
        "ram": _format_ram(),
        "agents_active": agents_active,
        "trust_score": boot_status.get("trust_score", 88),
        "boot_profile": boot_status.get("profile", "balanced"),
        "boot_state": boot_status.get("status", "unknown"),
        "persona": boot_status.get("identity", {}).get("persona", "Guide"),
        "mood": boot_status.get("identity", {}).get("mood", "Calm Focus"),
        "feature_count": boot_status.get("feature_count", 0),
        "boot_duration_ms": boot_status.get("boot_duration_ms", 0),
    }


def _build_events(boot_status, feature_flags):
    now_stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    events = [
        {
            "id": 100,
            "time": now_stamp,
            "source": "snowos.boot",
            "action": f"profile::{boot_status.get('profile', 'balanced')}",
            "status": "READY" if boot_status.get("status") == "ready" else "DEGRADED",
            "type": "boot",
        }
    ]

    for offset, warning in enumerate(boot_status.get("warnings", []), start=1):
        events.append(
            {
                "id": 100 + offset,
                "time": now_stamp,
                "source": "snowos.guard",
                "action": warning,
                "status": "CRITICAL",
                "type": "sentinel",
            }
        )

    for offset, feature in enumerate(feature_flags.get("enabled", [])[:4], start=10):
        events.append(
            {
                "id": 100 + offset,
                "time": now_stamp,
                "source": "nyx.boot",
                "action": feature.get("name", feature.get("id", "feature")),
                "status": "ACTIVE",
                "type": "ai",
            }
        )

    return events + mock_events


class SnowControlHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self):
        request_path = self.path.split("?", 1)[0]
        boot_status = _load_boot_status()
        feature_flags = _load_feature_flags()
        brand = _load_brand()

        if request_path == "/api/events":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(_build_events(boot_status, feature_flags)).encode())
        elif request_path == "/api/system_state":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(_build_system_state(boot_status)).encode())
        elif request_path == "/api/boot/status":
            payload = boot_status.copy()
            payload["brand"] = brand
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
        elif request_path == "/api/ai/features":
            catalog = _read_json_file(AI_FEATURES_FILE, {"features": []})
            enabled_ids = {feature.get("id") for feature in feature_flags.get("enabled", [])}
            payload = {
                "profile": feature_flags.get("profile", boot_status.get("profile", "balanced")),
                "brand": brand,
                "available_count": len(catalog.get("features", [])),
                "enabled_count": len(feature_flags.get("enabled", [])),
                "enabled": feature_flags.get("enabled", []),
                "feature_outputs": feature_flags.get("feature_outputs", {}),
            }
            payload["available"] = [
                {
                    **feature,
                    "enabled": feature.get("id") in enabled_ids,
                }
                for feature in catalog.get("features", [])
            ]
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
        else:
            super().do_GET()


def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((HOST, PORT), SnowControlHandler) as httpd:
        print(f"SnowControl Backend active at http://{HOST}:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
