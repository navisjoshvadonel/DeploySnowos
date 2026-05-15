import threading
import time
import uuid
from typing import Dict, List, Any

class SwarmExecutor:
    """
    Stage 41 — Cooperative Task Execution.
    Orchestrates execution of tasks across multiple swarm nodes.
    """
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.active_swarm_tasks: Dict[str, Dict] = {} # task_id -> info
        self._lock = threading.Lock()

    def execute_distributed_goal(self, goal_description: str, assignments: List[Dict]) -> str:
        """
        Executes a decomposed goal across assigned nodes.
        """
        swarm_job_id = "sj_" + str(uuid.uuid4())[:8]
        job_info = {
            "id": swarm_job_id,
            "description": goal_description,
            "subtasks": [],
            "status": "in_progress",
            "start_time": time.time()
        }
        
        with self._lock:
            self.active_swarm_tasks[swarm_job_id] = job_info
            
        for i, assign in enumerate(assignments):
            node_id = assign["node_id"]
            goal = assign["goal"]
            
            subtask_id = f"{swarm_job_id}_{i}"
            job_info["subtasks"].append({
                "id": subtask_id,
                "node_id": node_id,
                "goal": goal,
                "status": "pending"
            })
            
            # Dispatch to node
            threading.Thread(
                target=self._dispatch_subtask, 
                args=(swarm_job_id, subtask_id, node_id, goal),
                daemon=True
            ).start()
            
        return swarm_job_id

    def _dispatch_subtask(self, job_id: str, subtask_id: str, node_id: str, goal: str):
        """Sends a subtask to a specific node."""
        if node_id == self.nyx.node_id:
            # Local execution
            # We use nyx.process which handles scheduling
            self.nyx.process(f"nyx goal \"{goal}\"")
            # Note: Progress tracking for local goals is handled by GoalEngine
            # We need a bridge here.
        else:
            # Remote execution via SwarmClient
            response = self.nyx.swarm.call_node(node_id, "/swarm/execute", {"goal": goal})
            # Update status based on response
            with self._lock:
                if job_id in self.active_swarm_tasks:
                    for st in self.active_swarm_tasks[job_id]["subtasks"]:
                        if st["id"] == subtask_id:
                            st["status"] = "dispatched" if "error" not in response else "failed"
                            break

    def get_job_status(self, job_id: str) -> Dict:
        with self._lock:
            return self.active_swarm_tasks.get(job_id, {"status": "not_found"})
            
    def list_active_jobs(self) -> List[Dict]:
        with self._lock:
            return list(self.active_swarm_tasks.values())
