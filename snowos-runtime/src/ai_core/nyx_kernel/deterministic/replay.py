import time
from .storage import DELStorage

class ReplayEngine:
    def __init__(self, storage: DELStorage, sandbox_manager=None, policy_engine=None, enforcer=None):
        self.storage = storage
        self.sandbox = sandbox_manager
        self.policy_engine = policy_engine
        self.enforcer = enforcer

    def replay(self, plan_id, mode="dry-run"):
        """Replay a recorded plan."""
        plan = self.storage.get_plan(plan_id)
        if not plan:
            return f"Error: Plan {plan_id} not found."
            
        executions = self.storage.get_executions(plan_id)
        if not executions:
            return f"No recorded executions for plan {plan_id}."
            
        print(f"\n--- Replaying Plan: {plan['goal']} ---")
        print(f"Mode: {mode.upper()}\n")
        
        if mode == "dry-run":
            for i, exe in enumerate(executions):
                print(f"[{i+1}] {exe['command']}")
                print(f"    Status: {exe['status']} (Latency: {exe['latency']:.4f}s)")
                if exe['stdout']:
                    print(f"    STDOUT: {exe['stdout'][:100]}...")
                if exe['stderr']:
                    print(f"    STDERR: {exe['stderr'][:100]}...")
            return "Dry-run complete."
            
        elif mode == "live":
            if not self.sandbox:
                return "Error: Sandbox manager not provided for live replay."
                
            # Create a new sandbox for replay
            exec_id = f"replay_{plan_id[:8]}"
            workspace = self.sandbox.create(exec_id)
            
            # CBSM: Handle security for replay
            allowed_commands = []
            if self.policy_engine and self.enforcer:
                # Retrieve original caps from observability (if storage supports it)
                # Note: We need the observability storage instance here.
                # Assuming storage has get_granted_capabilities_for_plan
                original_caps = []
                if hasattr(self.enforcer.storage, "get_granted_capabilities_for_plan"):
                    original_caps = self.enforcer.storage.get_granted_capabilities_for_plan(plan_id)
                
                # Reissue token with exact same caps
                self.policy_engine.create_token(
                    task_id=exec_id,
                    plan_id=plan_id,
                    task_type="replay",
                    replay_caps=original_caps
                )
                
                # Enforce before execution
                for cmd in [e["command"] for e in executions]:
                    verdict = self.enforcer.enforce(exec_id, cmd)
                    if verdict.allowed:
                        allowed_commands.append(cmd)
                    else:
                        print(f"🚫 Replay BLOCKED by CBSM: {cmd} (Reason: {verdict.reason})")
            else:
                allowed_commands = [e["command"] for e in executions]

            if not allowed_commands:
                return "Error: Replay blocked by security policy."
                
            results = self.sandbox.execute(exec_id, allowed_commands)
            
            # Compare results
            print("Comparing live results with original recorded results:")
            for i, (orig, live) in enumerate(zip(executions, results)):
                print(f"[{i+1}] {orig['command']}")
                orig_status = orig["status"]
                live_status = "SUCCESS" if live.get("returncode", 0) == 0 else "FAILED"
                
                if orig_status == live_status:
                    print(f"    Status Match: {orig_status} ✅")
                else:
                    print(f"    Status MISMATCH: Recorded={orig_status}, Live={live_status} ❌")
                    
            return "Live replay complete."
            
        else:
            return f"Unknown replay mode: {mode}"
