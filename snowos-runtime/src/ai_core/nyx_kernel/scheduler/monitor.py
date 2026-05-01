import psutil
import os

class ResourceMonitor:
    @staticmethod
    def get_system_load():
        """Returns current system resource utilization."""
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_io": psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {},
            "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
        }

    @staticmethod
    def is_overloaded(cpu_threshold=85.0, mem_threshold=90.0):
        load = ResourceMonitor.get_system_load()
        return load["cpu_percent"] > cpu_threshold or load["memory_percent"] > mem_threshold

    @staticmethod
    def get_process_resources(pid):
        try:
            p = psutil.Process(pid)
            return {
                "cpu_percent": p.cpu_percent(),
                "memory_mb": p.memory_info().rss / (1024 * 1024)
            }
        except psutil.NoSuchProcess:
            return None
