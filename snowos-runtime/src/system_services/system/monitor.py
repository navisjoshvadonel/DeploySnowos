import psutil
import sqlite3
import time
import os
import logging

class SystemMonitor:
    """Tracks system telemetry and stores time-series metrics."""
    
    def __init__(self):
        self.db_path = os.path.expanduser("~/.snowos/system/metrics.db")
        self.logger = logging.getLogger("SnowOS.Monitor")
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    timestamp REAL, 
                    cpu REAL, 
                    ram REAL, 
                    disk REAL, 
                    net_latency REAL,
                    nyx_load REAL
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed to init metrics.db: {e}")

    def collect(self):
        """Gather current system stats and persist them."""
        try:
            stats = {
                "timestamp": time.time(),
                "cpu": psutil.cpu_percent(),
                "ram": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage('/').percent,
                "net_latency": 0.0, # Placeholder
                "nyx_load": 0.0     # Placeholder
            }
            
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO metrics VALUES (?, ?, ?, ?, ?, ?)", 
                (stats["timestamp"], stats["cpu"], stats["ram"], stats["disk"], stats["net_latency"], stats["nyx_load"])
            )
            conn.commit()
            conn.close()
            
            # Broadcast health status
            from runtime.event_bus import bus
            bus.publish("system_health", stats)
            
            return stats
        except Exception as e:
            self.logger.error(f"Metric collection failed: {e}")
            return {}

    def get_history(self, limit=100):
        """Retrieve recent metrics for visualization."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT * FROM metrics ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception:
            return []
