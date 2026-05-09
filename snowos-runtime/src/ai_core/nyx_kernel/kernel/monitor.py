import os
import time

class KernelMonitor:
    """Reads system metrics directly from /proc and /sys interfaces."""
    
    @staticmethod
    def get_cpu_stats():
        """Read /proc/stat for global CPU usage."""
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()
                if not line: return None
                fields = [float(column) for column in line.strip().split()[1:]]
                idle, total = fields[3], sum(fields)
                return {"idle": idle, "total": total}
        except Exception:
            return None

    @staticmethod
    def get_mem_info():
        """Read /proc/meminfo for memory usage."""
        try:
            mem = {}
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        name = parts[0].strip()
                        value = int(parts[1].split()[0])
                        mem[name] = value
            return {
                "total": mem.get("MemTotal", 0),
                "available": mem.get("MemAvailable", 0),
                "free": mem.get("MemFree", 0),
                "buffers": mem.get("Buffers", 0),
                "cached": mem.get("Cached", 0)
            }
        except Exception:
            return None

    @staticmethod
    def get_process_stats(pid):
        """Read /proc/[pid]/stat and /proc/[pid]/status."""
        try:
            # /proc/[pid]/stat for CPU
            with open(f'/proc/{pid}/stat', 'r') as f:
                fields = f.read().split()
                utime = int(fields[13])
                stime = int(fields[14])
                cutime = int(fields[15])
                cstime = int(fields[16])
                starttime = int(fields[21])
                
            # /proc/[pid]/status for memory and other info
            status = {}
            with open(f'/proc/{pid}/status', 'r') as f:
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        status[parts[0].strip()] = parts[1].strip()
            
            # /proc/[pid]/fd for file descriptors
            try:
                fds = len(os.listdir(f'/proc/{pid}/fd'))
            except Exception:
                fds = 0

            return {
                "pid": pid,
                "name": status.get("Name", "unknown"),
                "state": status.get("State", "unknown"),
                "memory_rss": status.get("VmRSS", "0 kB"),
                "utime": utime,
                "stime": stime,
                "fds": fds,
                "threads": status.get("Threads", "0")
            }
        except Exception:
            return None

    @staticmethod
    def get_net_dev():
        """Read /proc/net/dev for network IO."""
        try:
            stats = {}
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:] # Skip header
                for line in lines:
                    parts = line.split(':')
                    if len(parts) == 2:
                        iface = parts[0].strip()
                        fields = parts[1].split()
                        stats[iface] = {
                            "rx_bytes": int(fields[0]),
                            "rx_packets": int(fields[1]),
                            "tx_bytes": int(fields[8]),
                            "tx_packets": int(fields[9])
                        }
            return stats
        except Exception:
            return None

    @staticmethod
    def get_cpu_freq():
        """Read /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq."""
        try:
            freqs = []
            for i in range(os.cpu_count()):
                path = f'/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq'
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        freqs.append(int(f.read().strip()))
            return freqs
        except Exception:
            return []
