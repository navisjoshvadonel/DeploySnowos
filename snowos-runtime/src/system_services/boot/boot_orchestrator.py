import json
import logging
import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = SCRIPT_DIR.parent.parent
LOCAL_CONFIG_DIR = SOURCE_ROOT.parent / "config"
LOCAL_SERVICES_DIR = SOURCE_ROOT.parent / "services"
RELIABILITY_ROOT = SCRIPT_DIR.parent / "reliability_manager"

if str(RELIABILITY_ROOT) not in sys.path:
    sys.path.append(str(RELIABILITY_ROOT))

from integrity_checker.trust_boot import TrustBoot  # noqa: E402
from snapshot_engine.snapshotter import SnapshotEngine  # noqa: E402

LOGGER = logging.getLogger("SnowBoot")
TRUE_VALUES = {"1", "true", "yes", "on"}

RUNTIME_DIR = Path(os.environ.get("SNOWOS_RUNTIME_DIR", "/run/snowos"))
STATE_DIR = Path(os.environ.get("SNOWOS_STATE_DIR", "/var/lib/snowos"))
LOG_DIR = Path(os.environ.get("SNOWOS_LOG_DIR", "/var/log/snowos"))
BOOT_STATUS_FILE = Path(os.environ.get("SNOWOS_BOOT_STATUS_FILE", str(RUNTIME_DIR / "boot-status.json")))
FEATURE_FLAGS_FILE = Path(
    os.environ.get("SNOWOS_FEATURE_FLAGS_FILE", str(RUNTIME_DIR / "feature-flags.json"))
)
BOOT_HISTORY_FILE = Path(
    os.environ.get("SNOWOS_BOOT_HISTORY_FILE", str(LOG_DIR / "boot-history.jsonl"))
)
WORKSPACE_STATE_FILE = os.environ.get("SNOWOS_WORKSPACE_STATE_FILE", str(STATE_DIR / "ui_state.json"))


def _resolve_json_path(env_name, system_path, local_path):
    env_value = os.environ.get(env_name)
    if env_value and os.path.exists(env_value):
        return Path(env_value)
    if os.path.exists(system_path):
        return Path(system_path)
    return Path(local_path)


BOOT_MANIFEST_FILE = _resolve_json_path(
    "SNOWOS_BOOT_MANIFEST_FILE",
    "/etc/snowos/boot_manifest.json",
    LOCAL_CONFIG_DIR / "boot_manifest.json",
)
AI_FEATURES_FILE = _resolve_json_path(
    "SNOWOS_AI_FEATURES_FILE",
    "/etc/snowos/ai_features.json",
    LOCAL_CONFIG_DIR / "ai_features.json",
)
BRAND_FILE = _resolve_json_path(
    "SNOWOS_BRAND_FILE",
    "/etc/snowos/brand.json",
    LOCAL_CONFIG_DIR / "brand.json",
)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _atomic_write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    os.replace(tmp_path, path)


def _append_jsonl(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _is_enabled(value):
    return str(value).strip().lower() in TRUE_VALUES


def _ensure_directory(path, mode, user=None):
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, mode)
        if user and os.getuid() == 0:
            import shutil
            from pwd import getpwnam
            uid = getpwnam(user).pw_uid
            gid = getpwnam(user).pw_gid
            os.chown(path, uid, gid)
    except Exception:
        LOGGER.debug("Skipping chmod/chown for %s", path)


def _load_boot_inputs():
    return _read_json(BOOT_MANIFEST_FILE), _read_json(AI_FEATURES_FILE), _read_json(BRAND_FILE)


def _resolve_profile(boot_manifest):
    requested = os.environ.get("SNOWOS_BOOT_PROFILE", boot_manifest.get("default_profile", "balanced"))
    if requested not in boot_manifest.get("profiles", {}):
        LOGGER.warning("Unknown SnowOS boot profile '%s'. Falling back to manifest default.", requested)
        return boot_manifest.get("default_profile", "balanced")
    return requested


def _profile_identity(profile_id, integrity_ok):
    identities = {
        "secure": {
            "persona": "Sentinel",
            "mood": "Fortified",
            "scene": "Ice Vault",
            "tagline": "Trust before speed.",
            "focus": "containment",
        },
        "balanced": {
            "persona": "Guide",
            "mood": "Calm Focus",
            "scene": "Glacier Deck",
            "tagline": "Ready for daily flow.",
            "focus": "steady flow",
        },
        "developer": {
            "persona": "Builder",
            "mood": "Sharp",
            "scene": "Workshop Aurora",
            "tagline": "Debug first, drift never.",
            "focus": "iteration",
        },
        "immersive": {
            "persona": "Muse",
            "mood": "Luminous",
            "scene": "Frozen Glass",
            "tagline": "Presence with polish.",
            "focus": "atmosphere",
        },
    }
    identity = identities.get(profile_id, identities["balanced"]).copy()
    if not integrity_ok:
        identity["persona"] = "Guarded Sentinel"
        identity["mood"] = "Contained"
        identity["tagline"] = "Integrity degraded. Proceed with caution."
    return identity


def _workspace_resume_state():
    candidates = [
        Path(WORKSPACE_STATE_FILE),
        STATE_DIR / "ui_state.json",
        Path.home() / ".snowos" / "ui_state.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return {"available": True, "path": str(candidate)}
    return {"available": False, "path": str(candidates[0])}


def _resource_forecast(profile_id):
    cpu_count = os.cpu_count() or 4
    base_profiles = {
        "secure": ("steady", "defer non-essential services"),
        "balanced": ("adaptive", "keep user-facing services responsive"),
        "developer": ("elevated", "favor diagnostics and AI assistance"),
        "immersive": ("visual", "favor branded ambience and shell polish"),
    }
    load_class, recommendation = base_profiles.get(profile_id, base_profiles["balanced"])
    return {
        "cpu_count": cpu_count,
        "load_class": load_class,
        "recommendation": recommendation,
    }


def _service_preflight(service_names):
    service_checks = []
    for service_name in service_names:
        deployed_path = Path("/etc/systemd/system") / service_name
        bundled_path = LOCAL_SERVICES_DIR / service_name
        service_checks.append(
            {
                "name": service_name,
                "unit_present": deployed_path.exists() or bundled_path.exists(),
                "unit_path": str(deployed_path if deployed_path.exists() else bundled_path),
            }
        )
    return service_checks


def _build_feature_payload(profile_id, enabled_feature_ids, feature_catalog, brand, integrity_report, service_checks):
    feature_index = {feature["id"]: feature for feature in feature_catalog.get("features", [])}
    identity = _profile_identity(profile_id, integrity_report["trusted"])
    workspace_state = _workspace_resume_state()
    resource_forecast = _resource_forecast(profile_id)
    failed_checks = [check for check in integrity_report["checks"] if check["status"] != "ok"]
    enabled_features = []
    feature_outputs = {}

    for feature_id in enabled_feature_ids:
        feature = feature_index.get(
            feature_id,
            {
                "id": feature_id,
                "name": feature_id.replace("_", " ").title(),
                "category": "unclassified",
                "summary": "No feature metadata is registered yet.",
            },
        )
        enabled_features.append(feature)

        if feature_id == "adaptive_boot_profile":
            feature_outputs[feature_id] = {
                "selected_profile": profile_id,
                "tagline": identity["tagline"],
            }
        elif feature_id == "integrity_pulse":
            feature_outputs[feature_id] = {
                "trusted": integrity_report["trusted"],
                "mode": integrity_report["mode"],
                "failed_checks": len(failed_checks),
            }
        elif feature_id == "service_preflight":
            feature_outputs[feature_id] = {"services": service_checks}
        elif feature_id == "secure_resume":
            feature_outputs[feature_id] = {
                "allowed": integrity_report["trusted"],
                "reason": "resume allowed" if integrity_report["trusted"] else "resume paused until trust is restored",
            }
        elif feature_id == "policy_guard":
            feature_outputs[feature_id] = {
                "tracked_assets": [check["path"] for check in integrity_report["checks"]],
            }
        elif feature_id == "threat_mirror":
            feature_outputs[feature_id] = {
                "posture": "contained" if integrity_report["trusted"] else "elevated",
            }
        elif feature_id == "workspace_resume":
            feature_outputs[feature_id] = workspace_state
        elif feature_id == "context_resume":
            feature_outputs[feature_id] = {
                "mode": "warm" if workspace_state["available"] else "cold",
                "source": workspace_state["path"],
            }
        elif feature_id == "resource_forecast":
            feature_outputs[feature_id] = resource_forecast
        elif feature_id == "snowcontrol_insights":
            feature_outputs[feature_id] = {
                "boot_status_file": str(BOOT_STATUS_FILE),
                "feature_flags_file": str(FEATURE_FLAGS_FILE),
            }
        elif feature_id in {"persona_seed", "persona_guard"}:
            feature_outputs[feature_id] = {
                "persona": identity["persona"],
                "mood": identity["mood"],
                "scene": identity["scene"],
            }
        elif feature_id == "error_whisperer":
            feature_outputs[feature_id] = {
                "hint": "Use SnowControl boot diagnostics first when a service comes up degraded.",
            }
        elif feature_id == "build_coach":
            feature_outputs[feature_id] = {
                "hint": "If AI core is offline, validate /etc/snowos and /run/snowos before touching code.",
            }
        elif feature_id == "plugin_scout":
            feature_outputs[feature_id] = {
                "hint": "Surface GNOME, Nyx, or SnowControl extensions that match the active profile.",
            }
        elif feature_id == "memory_compass":
            feature_outputs[feature_id] = {
                "workspace_state_present": workspace_state["available"],
                "state_path": workspace_state["path"],
            }
        elif feature_id == "focus_orchestrator":
            feature_outputs[feature_id] = {
                "focus": identity["focus"],
                "recommendation": resource_forecast["recommendation"],
            }
        elif feature_id == "intent_storyline":
            feature_outputs[feature_id] = {
                "summary": f"SnowOS selected the {profile_id} profile with the {identity['persona']} persona.",
            }
        elif feature_id == "offline_reasoning_cache":
            feature_outputs[feature_id] = {
                "cache_root": str(STATE_DIR / "nyx" / "cache"),
            }
        elif feature_id == "forensic_recap":
            feature_outputs[feature_id] = {
                "issues": failed_checks,
            }
        elif feature_id in {"mood_surface", "ambient_scene"}:
            feature_outputs[feature_id] = {
                "mood": identity["mood"],
                "scene": identity["scene"],
                "palette": brand.get("palette", {}),
            }
        elif feature_id == "ritual_boot_sequence":
            feature_outputs[feature_id] = {
                "banner": f"{brand.get('brand_name', 'SnowOS')} // {brand.get('brand_channel', 'NYX')}",
                "tagline": identity["tagline"],
            }

    return enabled_features, feature_outputs, identity, workspace_state, resource_forecast


def run_boot():
    boot_started_at = time.time()
    boot_manifest, feature_catalog, brand = _load_boot_inputs()
    profile_id = _resolve_profile(boot_manifest)
    strict_integrity = _is_enabled(os.environ.get("SNOWOS_BOOT_STRICT_INTEGRITY", "0"))
    take_snapshot = _is_enabled(os.environ.get("SNOWOS_BOOT_TAKE_SNAPSHOT", "1"))
    warnings = []
    phases = {}

    _ensure_directory(RUNTIME_DIR, 0o775, user="snowos-sys")
    _ensure_directory(STATE_DIR, 0o755)
    _ensure_directory(LOG_DIR, 0o755)
    _ensure_directory(STATE_DIR / "snapshots", 0o750)
    phases["prepare-runtime"] = "ok"

    integrity_report = TrustBoot().inspect_system_integrity()
    phases["integrity-check"] = "ok" if integrity_report["trusted"] else "degraded"
    if not integrity_report["trusted"]:
        warnings.append("SnowOS integrity drift detected during boot.")

    snapshot_path = None
    if take_snapshot:
        try:
            snapshot_path = SnapshotEngine().create_snapshot()
            phases["snapshot"] = "ok"
        except Exception as exc:
            LOGGER.warning("SnowOS snapshot creation failed: %s", exc)
            phases["snapshot"] = "error"
            warnings.append("SnowOS snapshot creation failed.")
    else:
        phases["snapshot"] = "skipped"

    profile_config = boot_manifest["profiles"][profile_id]
    enabled_feature_ids = profile_config.get("feature_flags", [])
    service_checks = _service_preflight(boot_manifest.get("managed_services", []))
    enabled_features, feature_outputs, identity, workspace_state, resource_forecast = _build_feature_payload(
        profile_id,
        enabled_feature_ids,
        feature_catalog,
        brand,
        integrity_report,
        service_checks,
    )
    phases["feature-flags"] = "ok"

    trust_score = 99 if integrity_report["trusted"] else 72
    trust_score = max(35, trust_score - (len(warnings) * 4))
    degraded = bool(warnings) or not integrity_report["trusted"]
    boot_state = "degraded" if degraded else "ready"
    boot_finished_at = time.time()
    generated_at = datetime.now(timezone.utc).isoformat()

    boot_status = {
        "schema": "snowos.boot.status.v1",
        "generated_at": generated_at,
        "brand": brand,
        "hostname": socket.gethostname(),
        "profile": profile_id,
        "profile_description": profile_config.get("description", ""),
        "status": boot_state,
        "strict_integrity": strict_integrity,
        "trust_score": trust_score,
        "boot_duration_ms": int((boot_finished_at - boot_started_at) * 1000),
        "identity": identity,
        "workspace_resume": workspace_state,
        "resource_forecast": resource_forecast,
        "integrity": integrity_report,
        "snapshot_path": snapshot_path,
        "managed_services": service_checks,
        "feature_count": len(enabled_features),
        "enabled_feature_ids": enabled_feature_ids,
        "feature_outputs": feature_outputs,
        "warnings": warnings,
        "phases": phases,
    }
    feature_flags = {
        "schema": "snowos.feature.flags.v1",
        "generated_at": generated_at,
        "profile": profile_id,
        "brand_name": brand.get("brand_name", "SnowOS"),
        "enabled": enabled_features,
        "feature_outputs": feature_outputs,
    }

    _atomic_write_json(BOOT_STATUS_FILE, boot_status)
    _atomic_write_json(FEATURE_FLAGS_FILE, feature_flags)
    phases["publish-status"] = "ok"
    boot_status["phases"] = phases
    _atomic_write_json(BOOT_STATUS_FILE, boot_status)

    _append_jsonl(
        BOOT_HISTORY_FILE,
        {
            "generated_at": generated_at,
            "hostname": boot_status["hostname"],
            "profile": profile_id,
            "status": boot_state,
            "trust_score": trust_score,
            "warnings": warnings,
        },
    )

    if strict_integrity and not integrity_report["trusted"]:
        raise RuntimeError("SnowOS strict integrity mode blocked the current boot posture.")

    return boot_status


def main():
    logging.basicConfig(
        level=os.environ.get("SNOWOS_BOOT_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    try:
        status = run_boot()
        LOGGER.info(
            "SnowOS boot profile '%s' prepared with %s enabled AI features.",
            status["profile"],
            status["feature_count"],
        )
        return 0
    except Exception as exc:
        LOGGER.exception("SnowOS boot orchestration failed: %s", exc)
        try:
            if BOOT_STATUS_FILE.exists():
                failure_payload = _read_json(BOOT_STATUS_FILE)
            else:
                failure_payload = {"schema": "snowos.boot.status.v1"}
            failure_payload["generated_at"] = datetime.now(timezone.utc).isoformat()
            failure_payload["status"] = "failed"
            failure_payload["error"] = str(exc)
            _atomic_write_json(BOOT_STATUS_FILE, failure_payload)
        except Exception:
            LOGGER.exception("Unable to write fallback SnowOS boot status file.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
