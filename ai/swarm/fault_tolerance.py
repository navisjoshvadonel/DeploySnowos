import threading
import time
from typing import Dict, List

class SwarmFaultTolerance:
    """
    Stage 41 — Fault Tolerance & Failover.
    Monitors node health and reassigns tasks if a node fails.
    """
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            self._check_for_failures()
            time.sleep(15)

    def _check_for_failures(self):
        """Identify failed nodes and reassign their subtasks."""
        peers = self.nyx.swarm_engine.peers
        failed_nodes = [nid for nid, data in peers.items() if data["status"] == "offline"]
        
        if not failed_nodes:
            return
            
        active_jobs = self.nyx.swarm_executor.list_active_jobs()
        for job in active_jobs:
            if job["status"] != "in_progress":
                continue
                
            for st in job["subtasks"]:
                if st["node_id"] in failed_nodes and st["status"] in ["pending", "dispatched"]:
                    self._reassign_subtask(job["id"], st)

    def _reassign_subtask(self, job_id: str, subtask: Dict):
        """Find a new node for a subtask and dispatch it."""
        task_description = subtask["goal"]
        new_node, reason = self.nyx.swarm_router.route_task(task_description)
        
        if new_node == subtask["node_id"]:
            # If router picked the same failed node, fallback to local
            new_node = self.nyx.node_id
            
        print(f"[yellow]⚠️ SwarmFaultTolerance: Reassigning subtask {subtask['id']} from failed node to {new_node} ({reason})[/yellow]")
        
        # Update subtask info
        subtask["node_id"] = new_node
        subtask["status"] = "reassigned"
        
        # Dispatch again
        self.nyx.swarm_executor._dispatch_subtask(job_id, subtask["id"], new_node, task_description)
