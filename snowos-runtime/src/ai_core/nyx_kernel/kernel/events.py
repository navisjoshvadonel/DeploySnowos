import time
import uuid

class KernelEventSystem:
    def __init__(self, storage=None, telemetry=None):
        self.storage = storage
        self.telemetry = telemetry

    def emit(self, event_type, description, pid=None, metadata=None):
        """Emit a kernel-level event to observability and decision systems."""
        event = {
            "id": f"kev_{str(uuid.uuid4())[:8]}",
            "type": event_type,
            "pid": pid,
            "description": description,
            "metadata": metadata or {},
            "timestamp": time.time()
        }
        
        # Save to database
        if self.storage and hasattr(self.storage, 'save_kernel_event'):
            self.storage.save_kernel_event(event)
            
        # Log to telemetry (Stage 31)
        if self.telemetry:
            self.telemetry.metrics.record(f"kernel.event.{event_type}", 1)
            
        return event

    def check_system_anomalies(self, cpu_stats, mem_info):
        """Check for global system-level anomalies."""
        events = []
        
        # 1. Memory Pressure
        if mem_info and mem_info['available'] < mem_info['total'] * 0.05: # < 5% available
            events.append(self.emit(
                "MEMORY_CRITICAL",
                "System memory is critically low (< 5% available)",
                metadata={"available": mem_info['available'], "total": mem_info['total']}
            ))
            
        # 2. Zombie Process Check (Simplified)
        # In a real OS, we'd scan /proc for 'Z' status
        
        return events

    def check_service_health(self, process_manager):
        """Check if registered background services are still running."""
        events = []
        for pid_id, info in process_manager.processes.items():
            if info["status"] == "running":
                status = process_manager.get_status(pid_id)
                if status != "running":
                    events.append(self.emit(
                        "SERVICE_DOWN",
                        f"Background service '{info['command']}' (ID: {pid_id}) has stopped unexpectedly.",
                        metadata={"name": info['command'], "id": pid_id}
                    ))
        return events
