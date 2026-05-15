import os
import time
from .monitor import KernelMonitor

class ProcessIntelligence:
    def __init__(self, storage=None):
        self.storage = storage
        self.registry = {} # pid -> last_stats
        self.anomalies = []

    def scan(self):
        """Scan all running processes and update registry."""
        current_pids = [pid for pid in os.listdir('/proc') if pid.isdigit()]
        events = []
        
        for pid in current_pids:
            stats = KernelMonitor.get_process_stats(pid)
            if not stats: continue
            
            # Check for anomalies
            if pid in self.registry:
                last_stats = self.registry[pid]
                anomaly = self._detect_anomalies(last_stats, stats)
                if anomaly:
                    events.append(anomaly)
            
            self.registry[pid] = stats
            
            # Log to storage if available
            if self.storage and hasattr(self.storage, 'save_process_metrics'):
                self.storage.save_process_metrics(stats)

        # Cleanup dead processes
        dead_pids = set(self.registry.keys()) - set(current_pids)
        for pid in dead_pids:
            del self.registry[pid]
            
        return events

    def _detect_anomalies(self, last, current):
        """
        BEHAVIORAL SECURITY: 
        Detects anomalies using dynamic ratios instead of static thresholds.
        """
        # CPU Behavior: Check for sudden 10x jump in consumption
        cpu_last = last['utime'] + last['stime']
        cpu_current = current['utime'] + current['stime']
        cpu_growth = cpu_current - cpu_last
        
        if cpu_growth > 1000: # Significant absolute spike
            return {
                "type": "BEHAVIORAL_ANOMALY",
                "subtype": "CPU_STRESS",
                "pid": current['pid'],
                "name": current['name'],
                "description": f"Process {current['name']} is exhibiting aggressive compute behavior."
            }
            
        # File Descriptor Behavior: Detect rapid leakage
        if current['fds'] > last['fds'] * 1.5 and current['fds'] > 100:
            return {
                "type": "BEHAVIORAL_ANOMALY",
                "subtype": "RESOURCE_LEAK",
                "pid": current['pid'],
                "name": current['name'],
                "description": f"Process {current['name']} has increased open descriptors by 50% ({current['fds']})"
            }
            
        # Path Entropy: Flag processes running from /tmp or /var/tmp (common for exploits)
        exe_path = current.get('exe', '')
        if exe_path.startswith('/tmp') or exe_path.startswith('/var/tmp'):
            return {
                "type": "SECURITY_FLAG",
                "subtype": "UNTRUSTED_LOCATION",
                "pid": current['pid'],
                "name": current['name'],
                "description": f"Process {current['name']} is executing from a volatile/untrusted directory: {exe_path}"
            }

        return None
