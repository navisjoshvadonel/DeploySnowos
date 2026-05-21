#!/usr/bin/env python3
"""
SnowOS Dynamic DBus Bridge — Runtime App Introspection & Control.

Gives Nyx the ability to discover and control any DBus-enabled application
on the session and system buses without hardcoded plugins.

Features:
  1. Service discovery: scans all active bus names
  2. Interface introspection: queries exported methods/properties per service
  3. Dynamic method invocation: call any method on any service
  4. MPRIS shortcut: pause/play/next/prev for any media player
  5. Discovery cache at /tmp/snowos_dbus_services.json

Graceful fallback when dbus-python is unavailable.
"""
import os
import sys
import json
import time
import logging
import xml.etree.ElementTree as ET

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DBusBridge] %(levelname)s %(message)s",
)
logger = logging.getLogger("DBusBridge")

SERVICES_CACHE = "/tmp/snowos_dbus_services.json"

# ── Try dbus import ──────────────────────────────────────────────────────────
_DBUS_AVAILABLE = False
try:
    import dbus
    _DBUS_AVAILABLE = True
except ImportError:
    logger.warning("dbus-python not available. DBus bridge running in stub mode.")


class DBusBridge:
    """
    Dynamic DBus introspection and control layer for Nyx.
    Discovers services at runtime and exposes a generic call_method API.
    """

    def __init__(self):
        self._session_bus = None
        self._system_bus = None
        self._services_cache: dict = {}
        if _DBUS_AVAILABLE:
            try:
                self._session_bus = dbus.SessionBus()
                self._system_bus = dbus.SystemBus()
                logger.info("DBus session and system buses connected.")
            except Exception as e:
                logger.warning(f"DBus connection failed: {e}")

    # ── Service Discovery ─────────────────────────────────────────────────────
    def discover_services(self) -> dict:
        """Scan all active DBus service names on the session bus."""
        if not self._session_bus:
            return {"status": "unavailable", "services": []}

        try:
            bus_obj = self._session_bus.get_object(
                "org.freedesktop.DBus", "/org/freedesktop/DBus"
            )
            iface = dbus.Interface(bus_obj, "org.freedesktop.DBus")
            names = [str(n) for n in iface.ListNames() if not n.startswith(":")]

            services = {}
            for name in names:
                services[name] = {"name": name, "introspected": False}

            self._services_cache = services
            self._flush_cache()
            logger.info(f"Discovered {len(services)} DBus services.")
            return {"status": "ok", "count": len(services), "services": list(services.keys())}
        except Exception as e:
            logger.error(f"Service discovery failed: {e}")
            return {"status": "error", "reason": str(e)}

    # ── Introspection ─────────────────────────────────────────────────────────
    def introspect(self, bus_name: str, object_path: str = "/") -> dict:
        """
        Introspect a DBus service to discover its interfaces, methods,
        signals, and properties.
        """
        if not self._session_bus:
            return {"status": "unavailable"}

        try:
            obj = self._session_bus.get_object(bus_name, object_path)
            iface = dbus.Interface(obj, "org.freedesktop.DBus.Introspectable")
            xml_data = str(iface.Introspect())

            result = self._parse_introspection_xml(xml_data)
            # Update cache
            if bus_name in self._services_cache:
                self._services_cache[bus_name]["introspected"] = True
                self._services_cache[bus_name]["interfaces"] = result
                self._flush_cache()

            return {"status": "ok", "bus_name": bus_name, "interfaces": result}
        except Exception as e:
            logger.error(f"Introspection failed for {bus_name}: {e}")
            return {"status": "error", "reason": str(e)}

    def _parse_introspection_xml(self, xml_str: str) -> list:
        """Parse DBus introspection XML into a structured list of interfaces."""
        interfaces = []
        try:
            root = ET.fromstring(xml_str)
            for iface_elem in root.findall("interface"):
                iface_name = iface_elem.get("name", "")
                methods = []
                for method_elem in iface_elem.findall("method"):
                    args = []
                    for arg_elem in method_elem.findall("arg"):
                        args.append({
                            "name": arg_elem.get("name", ""),
                            "type": arg_elem.get("type", ""),
                            "direction": arg_elem.get("direction", "in"),
                        })
                    methods.append({
                        "name": method_elem.get("name", ""),
                        "args": args,
                    })

                signals = [s.get("name", "") for s in iface_elem.findall("signal")]
                properties = []
                for prop_elem in iface_elem.findall("property"):
                    properties.append({
                        "name": prop_elem.get("name", ""),
                        "type": prop_elem.get("type", ""),
                        "access": prop_elem.get("access", "read"),
                    })

                interfaces.append({
                    "name": iface_name,
                    "methods": methods,
                    "signals": signals,
                    "properties": properties,
                })
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
        return interfaces

    # ── Generic Method Call ────────────────────────────────────────────────────
    def call_method(self, bus_name: str, object_path: str,
                    interface: str, method: str, *args) -> dict:
        """Call any method on any DBus service dynamically."""
        if not self._session_bus:
            return {"status": "unavailable"}

        try:
            obj = self._session_bus.get_object(bus_name, object_path)
            iface = dbus.Interface(obj, interface)
            func = getattr(iface, method)
            result = func(*args)
            return {"status": "ok", "result": str(result) if result else "void"}
        except Exception as e:
            logger.error(f"DBus call failed: {bus_name}.{method}: {e}")
            return {"status": "error", "reason": str(e)}

    # ── MPRIS Media Control Shortcuts ─────────────────────────────────────────
    def media_control(self, action: str) -> dict:
        """
        Shortcut for MPRIS2 media player control.
        Actions: play, pause, playpause, next, previous, stop
        """
        if not self._session_bus:
            return {"status": "unavailable"}

        try:
            bus_obj = self._session_bus.get_object(
                "org.freedesktop.DBus", "/org/freedesktop/DBus"
            )
            dbus_iface = dbus.Interface(bus_obj, "org.freedesktop.DBus")
            names = [str(n) for n in dbus_iface.ListNames()]

            mpris_players = [n for n in names if n.startswith("org.mpris.MediaPlayer2.")]
            if not mpris_players:
                return {"status": "error", "reason": "No MPRIS media player found."}

            player_bus = mpris_players[0]
            method_map = {
                "play": "Play",
                "pause": "Pause",
                "playpause": "PlayPause",
                "next": "Next",
                "previous": "Previous",
                "stop": "Stop",
            }
            method_name = method_map.get(action.lower())
            if not method_name:
                return {"status": "error", "reason": f"Unknown media action: {action}"}

            return self.call_method(
                player_bus,
                "/org/mpris/MediaPlayer2",
                "org.mpris.MediaPlayer2.Player",
                method_name,
            )
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    # ── Cache ─────────────────────────────────────────────────────────────────
    def _flush_cache(self):
        try:
            # Convert to serializable format
            cache = {}
            for k, v in self._services_cache.items():
                entry = {"name": v.get("name", k), "introspected": v.get("introspected", False)}
                if "interfaces" in v:
                    entry["interface_count"] = len(v["interfaces"])
                cache[k] = entry
            with open(SERVICES_CACHE, "w") as f:
                json.dump({"timestamp": time.time(), "services": cache}, f, indent=2)
        except Exception:
            pass


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bridge = DBusBridge()
    if "--scan" in sys.argv:
        result = bridge.discover_services()
        print(json.dumps(result, indent=2))
    elif "--introspect" in sys.argv and len(sys.argv) > 2:
        result = bridge.introspect(sys.argv[sys.argv.index("--introspect") + 1])
        print(json.dumps(result, indent=2))
    elif "--media" in sys.argv and len(sys.argv) > 2:
        result = bridge.media_control(sys.argv[sys.argv.index("--media") + 1])
        print(json.dumps(result, indent=2))
    else:
        print("Usage: dbus_bridge.py --scan | --introspect <bus_name> | --media <action>")
