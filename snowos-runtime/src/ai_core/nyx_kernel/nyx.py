import os
import subprocess
import json
import getpass
import re
import time
import datetime
import requests
import uuid
import signal
import shutil
import threading
import concurrent.futures
import math
from google import genai
import http.server
import socketserver
import importlib.util
import sys
from observability import Telemetry
from cli.trace_cmd import trace_command
from cli.metrics_cmd import metrics_command
from deterministic import DELStorage, PlanHashingEngine, ExecutionRecorder
from cli.replay_cmd import replay_command
from cli.rollback_cmd import rollback_command
from cli.history_cmd import history_command
from scheduler.engine import SchedulerEngine
from cli.scheduler_cmds import queue_command, workers_command, scheduler_status_command
from security import TokenStore, PolicyEngine, EnforcementEngine
from security.policy import TaskType
from cli.security_cmds import policy_command, token_command, audit_command
from state.storage import StateStorage
from state.engine import PersistentStateEngine
from cli.state_cmds import state_history_command, state_show_command, state_diff_command, state_checkout_command
from cli.dashboard_cmd import dashboard_command
from kernel.monitor import KernelMonitor
from kernel.process import ProcessIntelligence
from kernel.events import KernelEventSystem
from kernel.healing import HealingBroker
from kernel.arbitrator import ResourceArbitrator
from cli.kernel_cmds import kernel_status_command, processes_command, kernel_events_command
from distributed_identity.node_store import NodeStore
from distributed_identity.trust import TrustManager
from distributed_identity.crypto import CryptoEngine
from swarm.profiler import NodeProfiler
from swarm.engine import SwarmEngine
from swarm.router import TaskRouter, RoutingStrategy
from swarm.executor import SwarmExecutor
from swarm.learning import SwarmLearningSync
from swarm.cache import SwarmCache
from swarm.observability import SwarmObservability
from swarm.fault_tolerance import SwarmFaultTolerance
from architecture.profiler import ArchitectureProfiler
from architecture.engine import DesignAnalysisEngine, RefactorProposalEngine
from architecture.simulation import ArchitectureSimulator
from architecture.modifier import SelfModificationEngine
from interface.state_controller import UIStateController
from interface.ui_memory import UIMemory
from ai_core.nyx_kernel.frost_shell import FrostShell
from ai_core.nyx_kernel.deterministic.semantic_fs import SemanticFS
from ai_core.nyx_kernel.memory.engine import NyxMemoryEngine
from runtime.event_bus import bus
from runtime.state_manager import StateManager
from runtime.controller import RuntimeController
from runtime.scheduler import RuntimeScheduler
from ui_intelligence.spatial_engine import SpatialUIEngine
from ui_intelligence.dock_ai import DockAI
from ui_intelligence.window_ai import WindowAI
from ui_intelligence.layout_manager import LayoutManager
from personality.engine import PersonalityEngine
from personality.trust import TrustEngine
from personality.feedback import FeedbackSystem
from personality.gating import ActionGating
from ai_core.nyx_kernel.learning.retriever import NyxRetriever
from ai_core.nyx_kernel.learning.feedback_loop import LearningFeedbackLoop
from ai_core.nyx_kernel.learning.trainer import WorkflowTrainer
from system.logger import SnowLogger
from system.monitor import SystemMonitor
from system.watchdog import SnowWatchdog
from system.crash_handler import CrashHandler
from performance.profiler import NyxProfiler
from performance.resource_manager import ResourceManager
from performance.scheduler_ai import AIScheduler
from performance.optimizer import PerformanceOptimizer
from ai_core.nyx_kernel.swarm.sentient_discovery import SentientDiscovery
from ai_core.nyx_kernel.swarm.task_broker import TaskBroker
from ai_core.nyx_kernel.swarm.federated_memory import FederatedMemory

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
import rich.box

console = Console()

# ─────────────────────────────────────────
#  STAGE 13 — SYSTEM STATE
# ─────────────────────────────────────────
class SystemState:
    def __init__(self):
        self.cwd = os.getcwd()
        self.env = dict(os.environ)
        self.last_commands: list[str] = []
        self.execution_results: list[dict] = []
        self.pending_subgoals: list[str] = []

# ─────────────────────────────────────────
#  STAGE 25 — CONFIG MANAGER
# ─────────────────────────────────────────
class ConfigManager:
    DEFAULT_CONFIG = {
        "max_workers": 3,
        "sandbox_enabled": True,
        "auto_improve": False,
        "api_enabled": False,
        "api_port": 8080,
        "api_key": None # Will be generated if missing
    }

    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.config_path = os.path.join(config_dir, "config.json")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config = self._load()
        
        if not self.config.get("api_key"):
            self.config["api_key"] = str(uuid.uuid4())[:8]
            self._save()

        if not self.config.get("node_id"):
            self.config["node_id"] = str(uuid.uuid4())
            self._save()

    def _load(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                    return {**self.DEFAULT_CONFIG, **data}
            except Exception:
                pass
        
        conf = dict(self.DEFAULT_CONFIG)
        return conf

    def _save(self):
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self._save()

# ─────────────────────────────────────────
#  STAGE 25 — PLUGIN MANAGER
# ─────────────────────────────────────────
class PluginManager:
    def __init__(self, plugins_dir: str, registry: 'ToolRegistry', nyx_agent):
        self.plugins_dir = plugins_dir
        self.registry = registry
        self.nyx = nyx_agent
        self.loaded_plugins = []
        os.makedirs(self.plugins_dir, exist_ok=True)

    def load_all(self):
        for name in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, name)
            if os.path.isdir(plugin_path):
                self._load_plugin(plugin_path, name)

    def _load_plugin(self, path: str, name: str):
        config_path = os.path.join(path, "plugin.json")
        main_path = os.path.join(path, "main.py")
        
        if not os.path.exists(config_path):
            return

        try:
            with open(config_path) as f:
                meta = json.load(f)
            
            intents = meta.get("intents", {})
            for module, mapping in intents.items():
                for pattern, cmd in mapping.items():
                    self.registry.register(f"plugin:{name}:{module}", pattern, cmd)
            
            self.loaded_plugins.append(meta)
            
            # Load dynamic logic
            if os.path.exists(main_path):
                spec = importlib.util.spec_from_file_location(f"nyx.plugins.{name}", main_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"nyx.plugins.{name}"] = module
                spec.loader.exec_module(module)
                if hasattr(module, "init"):
                    module.init(self.nyx)
                    
        except Exception as e:
            console.print(f"[red]❌ Failed to load plugin {name}: {e}[/red]")

# ─────────────────────────────────────────
# ─────────────────────────────────────────
#  STAGE 28/40 — NODE MANAGER & SWARM CLIENT (DITL)
# ─────────────────────────────────────────
class NodeManager:
    def __init__(self, db_path: str):
        self.store = NodeStore(db_path)
        self.trust = TrustManager(self.store)

    def add_node(self, node_id: str, url: str, public_key: str):
        self.store.add_node(node_id, url, public_key)

    def get_nodes(self):
        return self.store.list_nodes()

class SwarmClient:
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent

    def call_node(self, node_id: str, endpoint: str, data: dict = None) -> dict:
        node = self.nyx.node_manager.store.get_node(node_id)
        if not node:
            return {"error": f"Node {node_id} not found"}
        
        if node["trust_status"] != "trusted":
            return {"error": f"Node {node_id} is not trusted. Trust it first via 'nyx node trust'."}
        
        url = node["url"].rstrip("/") + endpoint
        
        # Identity Propagation: Sign a fresh capability token for this remote call
        # In a real swarm, this would be a specific RemoteExecution token.
        from security.tokens import CapabilityToken
        from security.capabilities import CapabilitySet
        
        # For simplicity, we propagate the current user's role and some basic capabilities
        # Or if we have an active task token, we use that.
        # Here we generate a "cross-node" token.
        
        token = CapabilityToken(
            task_id=str(uuid.uuid4()),
            plan_id="cross-node-execution",
            user_id=self.nyx.current_user["user_id"],
            role=self.nyx.current_user["role"],
            capabilities=CapabilitySet(["read", "execute"]), # Minimal remote caps
            node_origin=self.nyx.node_id,
            private_key=self.nyx.node_priv_key
        )
        
        headers = {
            "Authorization": f"Bearer {json.dumps(token.to_dict())}",
            "X-Nyx-Node-ID": self.nyx.node_id,
            "Content-Type": "application/json"
        }
        
        # Distributed Tracing Propagation
        current_span = self.nyx.telemetry.tracer.get_current_span()
        if current_span:
            headers["X-Nyx-Trace-ID"] = current_span["trace_id"]
            headers["X-Nyx-Parent-Span-ID"] = current_span["span_id"]
        
        # Start a span for this remote call
        trace_id = current_span["trace_id"] if current_span else uuid.uuid4().hex
        parent_id = current_span["span_id"] if current_span else None
        span_id = self.nyx.telemetry.start_span(
            name=f"remote_call:{endpoint}", 
            type="network", 
            trace_id=trace_id, 
            parent_id=parent_id,
            exec_node_id=node_id
        )
        start_time = time.time()
        
        try:
            if data:
                res = requests.post(url, json=data, headers=headers, timeout=10)
            else:
                res = requests.get(url, headers=headers, timeout=10)
            
            latency = time.time() - start_time
            status = "SUCCESS" if res.status_code == 200 else "ERROR"
            self.nyx.telemetry.end_span(span_id, status, metadata={"latency": latency, "endpoint": endpoint, "status_code": res.status_code})
            
            if res.status_code == 200:
                return res.json()
            return {"error": f"Node returned {res.status_code}: {res.text}"}
        except Exception as e:
            self.nyx.telemetry.end_span(span_id, "ERROR", metadata={"error": str(e)})
            return {"error": f"Connection failed: {e}"}

# ─────────────────────────────────────────
#  STAGE 29 — AUTONOMY ENGINE
# ─────────────────────────────────────────
class AutonomyEngine:
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.enabled = self.nyx.config.get("autonomy_enabled", False)
        self.log_file = os.path.join(self.nyx.log_dir, "autonomy.log")
        self.last_run = 0
        self.task_count_hour = 0
        self.last_hour_reset = time.time()
        self._thread = None
        self._stop_event = threading.Event()
        self.failed_goals = {} # Goal -> count of persistent failures

    def start(self):
        if not self._thread or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _log(self, rationale: str, goal: str, status: str):
        with open(self.log_file, "a") as f:
            ts = datetime.datetime.now().isoformat()
            f.write(f"[{ts}] [Goal: {goal}] [Why: {rationale}] -> {status}\n")

    def _loop(self):
        while not self._stop_event.is_set():
            if self.enabled and len(self.nyx.scheduler_engine.active_workers) == 0:
                self._think()
            self._stop_event.wait(10) # Faster frequency for "always occurring" AI interaction

    def _think(self):
        # Rate limiting
        if time.time() - self.last_hour_reset > 3600:
            self.task_count_hour = 0
            self.last_hour_reset = time.time()
        
        # INCREASED LIMIT for "always occurring" request
        if self.task_count_hour >= self.nyx.config.get("max_auto_tasks_per_hour", 50):
            return

        # 1. Look for failed patterns in EMG
        failures = [n for n in self.nyx.emg.graph["nodes"] if isinstance(n, dict) and n.get("type") == "failure"]
        
        # 2. Look for reflection insights
        insights = self.nyx.reflection.insights
        
        prompt = (
            "You are the Autonomy Executive of SnowOS.\n"
            "System state: Idle.\n"
            f"Recent Failures: {failures[-3:] if failures else 'None'}\n"
            f"Insights: {insights[:3] if insights else 'None'}\n\n"
            "Should we take any proactive action? If so, return JSON: {\"rationale\": \"...\", \"goal\": \"...\", \"priority\": \"LOW|MEDIUM\"}\n"
            "If no action is needed, return 'NONE'."
        )
        
        response = self.nyx._llm(prompt)
        if response and "{" in response:
            try:
                data = json.loads(re.search(r'\{.*\}', response, re.DOTALL).group(0))
                self.task_count_hour += 1
                self._log(data["rationale"], data["goal"], "proposed")
                console.print(f"[bold magenta]🧠 Autonomy:[/bold magenta] {data['rationale']}")
                self.nyx.process(f"nyx goal \"{data['goal']}\"")
            except Exception as e:
                self._log("JSON error", response, f"failed: {e}")

# ─────────────────────────────────────────
#  STAGE 27 — SECURITY MANAGER
# ─────────────────────────────────────────
class SecurityManager:
    RISK_PATTERNS = {
        "HIGH": [
            r"rm\s+-rf\s+/", r"chmod\s+.*777", r"chown\s+", r"sudo\s+", 
            r"curl\s+.*\s+\|\s+sh", r"apt-get\s+", r"yum\s+", r"pip\s+install",
            r">/etc/", r">/boot/"
        ],
        "MEDIUM": [
            r"rm\s+", r"mkdir\s+", r"touch\s+", r"mv\s+", r"cp\s+", r"sed\s+-i",
            r">" 
        ],
        "LOW": [
            r"ls\s*", r"cat\s+", r"grep\s+", r"echo\s+", r"pwd\s*", r"find\s+"
        ]
    }

    def __init__(self, nyx_agent):
        self.nyx = nyx_agent

    def classify_risk(self, command: str) -> str:
        for level, patterns in self.RISK_PATTERNS.items():
            for p in patterns:
                if re.search(p, command):
                    return level
        return "MEDIUM" 

    def check_permission(self, source_plugin: str, category: str) -> bool:
        if not source_plugin: return True 
        
        plugin = next((p for p in self.nyx.plugin_manager.loaded_plugins if p.get("name") == source_plugin), None)
        if not plugin: return False
        
        # categories: filesystem, network, process
        perms = plugin.get("permissions", [])
        return category in perms

# ─────────────────────────────────────────
#  STAGE 18 — TOOL REGISTRY
# ─────────────────────────────────────────
class ToolRegistry:
    DEFAULT_TOOLS = {
        "files": {
            r"^(?:list|show) files?$": "snow files list",
            r"^find file (.+)$": "snow files find '{0}'",
        },
        "dev": {
            r"^create python project$": "snow dev python",
            r"^setup python environment$": "snow dev python",
            r"^init git$": "snow dev git",
        },
        "system": {
            r"^(?:system|show) status$": "snow status",
        },
    }

    def __init__(self, tools_file: str):
        self.tools = {k: dict(v) for k, v in self.DEFAULT_TOOLS.items()}
        if os.path.exists(tools_file):
            try:
                with open(tools_file) as f:
                    extra = json.load(f)
                for module, intents in extra.items():
                    self.tools.setdefault(module, {}).update(intents)
            except Exception:
                pass

    def register(self, module: str, pattern: str, command: str):
        self.tools.setdefault(module, {})[pattern] = command

    def match(self, text: str) -> str | None:
        for _, intents in self.tools.items():
            for pattern, template in intents.items():
                m = re.match(pattern, text)
                if m:
                    return template.format(*m.groups()) if m.groups() else template
        return None

# ─────────────────────────────────────────
#  STAGE 14 — PROCESS MANAGER
# ─────────────────────────────────────────
class ProcessManager:
    def __init__(self, registry_file: str, log_dir: str):
        self.registry_file = registry_file
        self.log_dir = log_dir
        self.processes = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        with open(self.registry_file, "w") as f:
            json.dump(self.processes, f, indent=2)

    def start(self, command: str, cwd: str) -> str:
        if len([p for p in self.processes.values() if self.get_status(p["id"]) == "running"]) >= 10:
            raise Exception("Max concurrent processes (10) reached.")

        pid_id = str(uuid.uuid4())[:8]
        log_file = os.path.join(self.log_dir, f"{pid_id}.log")
        
        with open(log_file, "w") as f:
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdout=f,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )

        self.processes[pid_id] = {
            "id": pid_id,
            "command": command,
            "cwd": cwd,
            "pid": proc.pid,
            "status": "running",
            "start_time": datetime.datetime.now().isoformat(),
            "log_file": log_file
        }
        self._save()
        return pid_id

    def get_status(self, pid_id: str) -> str:
        if pid_id not in self.processes:
            return "not_found"
        
        proc_info = self.processes[pid_id]
        if proc_info["status"] != "running":
            return proc_info["status"]
            
        try:
            os.kill(proc_info["pid"], 0)
            return "running"
        except OSError:
            proc_info["status"] = "stopped"
            self._save()
            return "stopped"

    def stop(self, pid_id: str) -> bool:
        if pid_id not in self.processes:
            return False
            
        proc_info = self.processes[pid_id]
        if self.get_status(pid_id) == "running":
            try:
                os.killpg(os.getpgid(proc_info["pid"]), signal.SIGTERM)
            except Exception:
                try:
                    os.kill(proc_info["pid"], signal.SIGTERM)
                except Exception:
                    pass
                    
        proc_info["status"] = "stopped"
        self._save()
        return True

    def restart(self, pid_id: str) -> str:
        if pid_id not in self.processes:
            raise Exception("Process not found.")
        self.stop(pid_id)
        info = self.processes[pid_id]
        return self.start(info["command"], info["cwd"])

    def attach(self, pid_id: str):
        if pid_id not in self.processes:
            console.print(f"[red]Process {pid_id} not found.[/red]")
            return
            
        log_file = self.processes[pid_id]["log_file"]
        if not os.path.exists(log_file):
            console.print(f"[red]Log file missing for {pid_id}.[/red]")
            return
            
        console.print(f"[cyan]Attaching to {pid_id} (tail -f). Press Ctrl+C to detach.[/cyan]")
        try:
            subprocess.run(["tail", "-f", log_file])
        except KeyboardInterrupt:
            console.print("\n[yellow]Detached.[/yellow]")


# ─────────────────────────────────────────
#  STAGE 16 — EXECUTION MEMORY GRAPH
# ─────────────────────────────────────────
class MemoryGraph:
    """Persistent Execution Memory Graph (EMG).

    Nodes: execution_plan | command | file_created | file_modified |
           process_started | failure_event
    Edges (stored on source node): CREATED | MODIFIED | EXECUTED_BY |
           CAUSED_BY | PART_OF | FAILED_DUE_TO
    """

    def __init__(self, emg_file: str):
        self.emg_file = emg_file
        os.makedirs(os.path.dirname(emg_file), exist_ok=True)
        self.graph = self._load()

    # ——— persistence ——————————————————————————————
    def _load(self) -> dict:
        if os.path.exists(self.emg_file):
            try:
                with open(self.emg_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"nodes": {}, "edges": []}

    def _save(self):
        with open(self.emg_file, "w") as f:
            json.dump(self.graph, f, indent=2)

    # ——— node builders —————————————————————————————
    def _make_node(self, node_type: str, metadata: dict) -> str:
        node_id = str(uuid.uuid4())[:12]
        self.graph["nodes"][node_id] = {
            "id": node_id,
            "type": node_type,
            "timestamp": datetime.datetime.now().isoformat(),
            "metadata": metadata,
        }
        return node_id

    def _add_edge(self, src: str, rel: str, dst: str):
        self.graph["edges"].append({"src": src, "rel": rel, "dst": dst})

    # ——— public API ——————————————————————————————
    def update(self, plan: list[str], diff: dict,
               execution_id: str, is_valid: bool,
               cwd: str, user_input: str = ""):
        """Convert an execution run into EMG nodes + edges and persist."""

        # 1. Plan node
        plan_id = self._make_node("execution_plan", {
            "execution_id": execution_id,
            "user_input": user_input,
            "cwd": cwd,
            "steps": len(plan),
            "verified": is_valid,
        })

        # 2. Command nodes
        for cmd in plan:
            cmd_id = self._make_node("command", {"cmd": cmd, "cwd": cwd})
            self._add_edge(plan_id, "CAUSED_BY", cmd_id)
            self._add_edge(cmd_id, "PART_OF", plan_id)

        # 3. File nodes from diff
        for path in diff.get("created", []):
            fid = self._make_node("file_created", {"path": path})
            self._add_edge(plan_id, "CREATED", fid)

        for path in diff.get("modified", []):
            fid = self._make_node("file_modified", {"path": path})
            self._add_edge(plan_id, "MODIFIED", fid)

        # 4. Failure node
        if not is_valid:
            fail_id = self._make_node("failure_event", {
                "execution_id": execution_id,
                "plan": plan,
            })
            self._add_edge(plan_id, "FAILED_DUE_TO", fail_id)

        self._save()
        return plan_id

    def query(self, question: str, llm_fn) -> str:
        """Use LLM to reason over the graph and answer a natural language query."""
        # Build a compact summary to avoid token bloat
        node_count = len(self.graph["nodes"])
        edge_count = len(self.graph["edges"])

        # Most recent 40 nodes
        recent_nodes = list(self.graph["nodes"].values())[-40:]
        summary = json.dumps({
            "total_nodes": node_count,
            "total_edges": edge_count,
            "recent_nodes": recent_nodes,
        })

        prompt = (
            "You are a graph-based memory retrieval engine for an AI operating system.\n"
            "Answer the user's question using the Execution Memory Graph below.\n"
            "Be specific: mention file paths, commands, timestamps, and execution IDs where relevant.\n"
            "If nothing relevant is found, say so clearly.\n\n"
            f"User Question: {question}\n\n"
            f"Memory Graph (recent):\n{summary}"
        )
        return llm_fn(prompt) or "Memory query failed."


# ─────────────────────────────────────────
#  STAGE 18 — TASK SCHEDULER & TEMPORAL ENGINE
# ─────────────────────────────────────────
PRIORITY = {"HIGH": 0, "NORMAL": 1, "LOW": 2}


class TaskScheduler:
    """Persistent task queue with priority, dependency chains,
    delayed execution, and optional recurrence.

    Task schema:
    {
      "id": "uuid8",
      "goal": "setup flask project",
      "cwd": "/path",
      "priority": "HIGH|NORMAL|LOW",
      "status": "pending|running|done|failed|cancelled",
      "run_at": ISO timestamp or null,
      "interval_sec": int or null,
      "depends_on": ["task_id", ...],
      "created_at": ISO timestamp,
      "completed_at": ISO timestamp or null,
    }
    """

    TICK_INTERVAL = 5  # seconds between scheduler ticks

    def __init__(self, queue_file: str, nyx_agent):
        self.queue_file = queue_file
        self.nyx = nyx_agent          # reference to NyxAI for execution
        self.queue: dict[str, dict] = self._load()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="NyxScheduler"
        )

    # ——— persistence ——————————————————————————————
    def _load(self) -> dict:
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        with open(self.queue_file, "w") as f:
            json.dump(self.queue, f, indent=2)

    # ——— public task API ———————————————————————————
    def schedule(self, goal: str, cwd: str,
                 priority: str = "NORMAL",
                 delay_sec: int = 0,
                 interval_sec: int | None = None,
                 depends_on: list[str] | None = None,
                 goal_id: str | None = None) -> str:
        task_id = str(uuid.uuid4())[:8]
        run_at = None
        if delay_sec > 0:
            run_at = (datetime.datetime.now() +
                      datetime.timedelta(seconds=delay_sec)).isoformat()
        self.queue[task_id] = {
            "id": task_id,
            "goal": goal,
            "cwd": cwd,
            "priority": priority.upper() if priority.upper() in PRIORITY else "NORMAL",
            "status": "pending",
            "run_at": run_at,
            "interval_sec": interval_sec,
            "depends_on": depends_on or [],
            "created_at": datetime.datetime.now().isoformat(),
            "completed_at": None,
            "goal_id": goal_id,
        }
        self._save()
        return task_id

    def cancel(self, task_id: str) -> bool:
        if task_id in self.queue:
            if self.queue[task_id]["status"] in ("pending",):
                self.queue[task_id]["status"] = "cancelled"
                self._save()
                return True
        return False

    def list_tasks(self) -> list[dict]:
        return sorted(
            self.queue.values(),
            key=lambda t: (PRIORITY.get(t["priority"], 1), t["created_at"])
        )

    # ——— dependency resolution ———————————————————————
    def _deps_satisfied(self, task: dict) -> bool:
        for dep_id in task.get("depends_on", []):
            dep = self.queue.get(dep_id)
            if not dep or dep["status"] != "done":
                return False
        return True

    def _is_due(self, task: dict) -> bool:
        if task["run_at"] is None:
            return True
        return datetime.datetime.now() >= datetime.datetime.fromisoformat(task["run_at"])

    # ——— background scheduler loop ————————————————————
    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _scheduler_loop(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop_event.wait(self.TICK_INTERVAL)

    def _tick(self):
        """Dispatch ready tasks: independent -> WorkerPool, dependent -> inline."""
        ready = [
            t for t in self.queue.values()
            if t["status"] == "pending"
            and self._is_due(t)
            and self._deps_satisfied(t)
        ]
        ready.sort(key=lambda t: PRIORITY.get(t["priority"], 1))

        pool = getattr(self.nyx, "scheduler_engine", None)
        priority_map = {
            "critical": 10,
            "high": 10,
            "normal": 5,
            "low": 1
        }

        for task in ready:
            task["status"] = "running"
            self._save()
            
            if pool and not task.get("depends_on"):
                # Define handler for the scheduler
                def task_handler(t, limits):
                    # Ensure autonomous tasks get restricted tokens
                    if limits is None:
                        limits = {}
                    limits["task_type"] = TaskType.AUTONOMOUS
                    
                    self.nyx.process(t["goal"], limits=limits)
                    # Mark task as done in scheduler
                    t["status"] = "done"
                    t["completed_at"] = datetime.datetime.now().isoformat()
                    if t.get("goal_id") and hasattr(self.nyx, "goal_engine"):
                        self.nyx.goal_engine.on_task_complete(t["goal_id"], t["id"], True)
                
                task["handler"] = task_handler
                task["priority"] = priority_map.get(task["priority"].lower(), 1)
                pool.submit(task)
            else:
                self._run_task_inline(task)

    def _run_task_inline(self, task: dict):
        """Execute a scheduled task on the current (scheduler) thread."""
        try:
            original_cwd = self.nyx.state.cwd
            if task["cwd"] and os.path.isdir(task["cwd"]):
                os.chdir(task["cwd"])
                self.nyx.state.cwd = task["cwd"]

            console.print(
                f"\n[bold magenta]\u23f0 Scheduler: executing '{task['goal']}' "
                f"[{task['priority']}][/bold magenta]"
            )
            self.nyx.process(task["goal"])

            task["status"] = "done"
            task["completed_at"] = datetime.datetime.now().isoformat()

            if task.get("goal_id") and hasattr(self.nyx, "goal_engine"):
                self.nyx.goal_engine.on_task_complete(task["goal_id"], task["id"], True)

            if task.get("interval_sec"):
                self.schedule(
                    goal=task["goal"], cwd=task["cwd"],
                    priority=task["priority"],
                    delay_sec=task["interval_sec"],
                    interval_sec=task["interval_sec"],
                    goal_id=task.get("goal_id")
                )

            if os.path.isdir(original_cwd):
                os.chdir(original_cwd)
                self.nyx.state.cwd = original_cwd

        except Exception as e:
            task["status"] = "failed"
            task["completed_at"] = datetime.datetime.now().isoformat()
            console.print(f"[red]\u274c Scheduler task failed: {e}[/red]")
            if task.get("goal_id") and hasattr(self.nyx, "goal_engine"):
                self.nyx.goal_engine.on_task_complete(task["goal_id"], task["id"], False)

        self._save()


# -----------------------------------------
#  STAGE 21 - PARALLEL WORKER POOL
# -----------------------------------------
class WorkerPool:
    """Thread-based parallel execution pool for independent SnowOS tasks.

    Each submitted task:
    - Runs in its own worker thread
    - Uses its own sandbox (filesystem isolation)
    - Locks EMG writes via nyx._emg_lock
    - Reports back to TaskScheduler + GoalEngine
    """

    DEFAULT_MAX = 3
    TASK_TIMEOUT = 300

    def __init__(self, max_workers: int = DEFAULT_MAX, nyx_agent=None):
        self.max_workers = max_workers
        self.nyx = nyx_agent
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="NyxWorker"
        )
        self._futures: dict[str, concurrent.futures.Future] = {}
        self._lock = threading.Lock()

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(1 for f in self._futures.values() if not f.done())

    def submit(self, task: dict, scheduler) -> bool:
        if self.active_count >= self.max_workers:
            task["status"] = "pending"
            scheduler._save()
            console.print(
                f"[yellow]\u26a0\ufe0f Worker pool full ({self.max_workers}/{self.max_workers}) "
                f"- task {task['id']} re-queued.[/yellow]"
            )
            return False

        future = self._executor.submit(self._worker_fn, task, scheduler)
        with self._lock:
            self._futures[task["id"]] = future
        console.print(
            f"[cyan]>> Worker spawned for '{task['goal']}' [{task['priority']}] "
            f"(id: {task['id']})[/cyan]"
        )
        return True

    def _worker_fn(self, task: dict, scheduler):
        nyx = self.nyx
        task_id = task["id"]
        goal = task["goal"]
        cwd = task["cwd"] if task["cwd"] and os.path.isdir(task["cwd"]) else os.getcwd()

        console.print(f"\n[bold cyan]\ud83d\udce6 Worker [{task_id}]: starting '{goal}'[/bold cyan]")

        try:
            plan = nyx.reasoning_loop(goal)
            if not plan:
                raise Exception("No plan generated")
            plan = nyx.validate_plan(plan)
            plan = nyx.optimize_plan(plan)
            if not plan:
                raise Exception("Plan empty after validation")

            exec_id = f"w_{task_id}"
            sandbox_ws = nyx.sandbox.create(exec_id, cwd)
            nyx.sandbox.execute(exec_id, plan)

            # Compute diff from sandbox
            pre = {"cwd": sandbox_ws, "files": {}, "env": {}, "timestamp": ""}
            post_files: dict = {}
            for root, _, files in os.walk(sandbox_ws):
                for fname in files:
                    fp = os.path.join(root, fname)
                    try:
                        post_files[fp] = os.path.getmtime(fp)
                    except Exception:
                        pass
            post = {"cwd": sandbox_ws, "files": post_files, "env": {}, "timestamp": ""}
            diff = nyx.compute_diff(pre, post)

            is_valid = nyx.verify_execution(plan, diff)

            if is_valid:
                committed = nyx.sandbox.commit(exec_id, cwd)
                console.print(f"[green]\ud83d\udce6 Worker [{task_id}] committed {len(committed)} file(s)[/green]")
            else:
                nyx.sandbox.discard(exec_id)
                console.print(f"[red]\ud83d\udce6 Worker [{task_id}] discarded - verification failed[/red]")

            # Thread-safe EMG write
            with nyx._emg_lock:
                nyx.emg.update(
                    plan=plan, diff=diff, execution_id=exec_id,
                    is_valid=is_valid, cwd=cwd, user_input=goal
                )

            task["status"] = "done" if is_valid else "failed"
            task["completed_at"] = datetime.datetime.now().isoformat()
            scheduler._save()

            if task.get("goal_id") and hasattr(nyx, "goal_engine"):
                nyx.goal_engine.on_task_complete(task["goal_id"], task_id, is_valid)

        except Exception as e:
            console.print(f"[red]\ud83d\udce6 Worker [{task_id}] crashed: {e}[/red]")
            task["status"] = "failed"
            task["completed_at"] = datetime.datetime.now().isoformat()
            scheduler._save()
            if task.get("goal_id") and hasattr(nyx, "goal_engine"):
                nyx.goal_engine.on_task_complete(task["goal_id"], task_id, False)
        finally:
            with self._lock:
                self._futures.pop(task_id, None)

    def status(self) -> list[dict]:
        with self._lock:
            return [
                {"task_id": tid, "done": f.done(), "running": f.running()}
                for tid, f in self._futures.items()
            ]

    def shutdown(self):
        self._executor.shutdown(wait=False, cancel_futures=True)


# -----------------------------------------
#  STAGE 22 - KNOWLEDGE ENGINE
# -----------------------------------------
def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)

class KnowledgeEngine:
    """Retrieval-Augmented Generation (RAG) system for SnowOS.
    Indexes codebase in the background and provides semantic search.
    """
    def __init__(self, knowledge_file: str, workspace_root: str, nyx_agent):
        self.knowledge_file = knowledge_file
        self.workspace_root = workspace_root
        self.nyx = nyx_agent
        self.index: dict[str, dict] = self._load()
        self.status = "idle"
        self.files_indexed = len(self.index)
        self.chunks_indexed = sum(len(f["chunks"]) for f in self.index.values())
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._indexer_loop, daemon=True, name="NyxIndexer"
        )

    def _load(self) -> dict:
        if os.path.exists(self.knowledge_file):
            try:
                with open(self.knowledge_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        try:
            with open(self.knowledge_file, "w") as f:
                json.dump(self.index, f)
        except Exception:
            pass

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def reindex(self):
        self.index.clear()
        self.files_indexed = 0
        self.chunks_indexed = 0
        self._save()

    def _get_embedding(self, text: str) -> list[float]:
        try:
            result = self.nyx.client.models.embed_content(
                model="text-embedding-004",
                contents=text,
            )
            # The result is a list of embeddings if multiple contents are provided, 
            # or a single embedding object.
            return result.embeddings[0].values
        except Exception:
            return []

    def _indexer_loop(self):
        ignore_dirs = {".git", "venv", "__pycache__", "node_modules"}
        ignore_exts = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".sqlite3", ".db", ".so", ".bin"}
        
        while not self._stop_event.is_set():
            self.status = "scanning"
            try:
                for root, dirs, files in os.walk(self.workspace_root):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ignore_dirs and "tmp" not in d]
                    
                    for fname in files:
                        if self._stop_event.is_set():
                            break
                            
                        ext = os.path.splitext(fname)[1].lower()
                        if ext in ignore_exts or fname.startswith("."):
                            continue
                            
                        fp = os.path.join(root, fname)
                        try:
                            # Skip files > 1MB
                            if os.path.getsize(fp) > 1024 * 1024:
                                continue
                                
                            mtime = os.path.getmtime(fp)
                            rel_path = os.path.relpath(fp, self.workspace_root)
                            
                            # Skip if already indexed and unmodified
                            if rel_path in self.index and self.index[rel_path].get("mtime") >= mtime:
                                continue
                                
                            self.status = f"indexing {rel_path}"
                            with open(fp, "r", encoding="utf-8") as f:
                                content = f.read()
                                
                            # Simple chunking (by paragraphs/functions approx 500 chars)
                            chunks = [content[i:i+500] for i in range(0, len(content), 500)]
                            embedded_chunks = []
                            for c in chunks:
                                if len(c.strip()) < 10:
                                    continue
                                emb = self._get_embedding(c)
                                if emb:
                                    embedded_chunks.append({"text": c, "embedding": emb})
                                    self.chunks_indexed += 1
                                # Rate limit protection for background thread
                                time.sleep(1.0)
                                
                            self.index[rel_path] = {
                                "mtime": mtime,
                                "chunks": embedded_chunks
                            }
                            if rel_path not in self.index:
                                self.files_indexed += 1
                            self._save()
                            
                        except Exception:
                            pass
                            
            except Exception:
                pass
                
            self.status = "idle"
            # Wait 5 minutes before next sweep
            if self._stop_event.wait(300):
                break

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        query_emb = self._get_embedding(query)
        if not query_emb:
            return []
            
        results = []
        for fp, data in self.index.items():
            for chunk in data.get("chunks", []):
                score = _cosine_similarity(query_emb, chunk["embedding"])
                results.append({"file": fp, "score": score, "text": chunk["text"]})
                
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

# -----------------------------------------
#  STAGE 23 - REFLECTION ENGINE
# -----------------------------------------
class ReflectionEngine:
    """Analyzes system execution history to find inefficient patterns and suggest improvements."""
    def __init__(self, insights_file: str, nyx_agent):
        self.insights_file = insights_file
        self.nyx = nyx_agent
        self.insights: list[dict] = self._load()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._reflection_loop, daemon=True, name="NyxReflector"
        )
        self.last_run = None

    def _load(self) -> list:
        if os.path.exists(self.insights_file):
            try:
                with open(self.insights_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save(self):
        try:
            with open(self.insights_file, "w") as f:
                json.dump(self.insights, f, indent=2)
        except Exception:
            pass

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _reflection_loop(self):
        while not self._stop_event.is_set():
            if self._stop_event.wait(600):  # 10 minutes
                break
            try:
                self.reflect()
            except Exception:
                pass

    def reflect(self):
        nodes = list(self.nyx.emg.graph["nodes"].values())[-20:]
        if not nodes:
            return
            
        history = []
        for n in nodes:
            history.append(f"[{n['type']}] timestamp={n['timestamp']} ok={n['metadata'].get('verified', True)} plan={n['metadata'].get('plan')}")
            
        prompt = (
            "You are a reflection engine for SnowOS. Analyze the following recent execution history.\n"
            "Identify repeated failures, redundant patterns, or inefficient workflows.\n"
            "If you find a clear pattern that can be optimized, generate a single JSON insight.\n"
            "Otherwise, return an empty array [].\n"
            "Return ONLY a JSON array. No markdown, no explanations.\n"
            "Format:\n"
            "[\n"
            "  {\n"
            "    \"type\": \"optimization\",\n"
            "    \"message\": \"You repeatedly initialize python environments. Suggest creating a reusable command.\",\n"
            "    \"confidence\": 0.85\n"
            "  }\n"
            "]\n\n"
            f"History:\n" + "\n".join(history)
        )
        
        text = self.nyx._llm(prompt)
        if not text:
            return
            
        parsed = self.nyx._parse_json_list(text)
        if parsed and isinstance(parsed, list):
            new_insights = 0
            for item in parsed:
                if isinstance(item, dict) and "message" in item:
                    item["id"] = f"ins_{str(uuid.uuid4())[:6]}"
                    item["timestamp"] = datetime.datetime.now().isoformat()
                    item["status"] = "new"
                    self.insights.append(item)
                    new_insights += 1
            if new_insights > 0:
                self._save()
        self.last_run = datetime.datetime.now().isoformat()


# -----------------------------------------
#  STAGE 24 - EVOLUTION ENGINE
# -----------------------------------------
class EvolutionEngine:
    def __init__(self, improvements_file: str, nyx_agent):
        self.improvements_file = improvements_file
        self.nyx = nyx_agent
        self.improvements: dict[str, dict] = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.improvements_file):
            try:
                with open(self.improvements_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        try:
            with open(self.improvements_file, "w") as f:
                json.dump(self.improvements, f, indent=2)
        except Exception:
            pass

    def generate_from_insight(self, insight_id: str):
        ins = next((i for i in self.nyx.reflection.insights if i["id"] == insight_id), None)
        if not ins:
            console.print(f"[red]❌ Insight {insight_id} not found[/red]")
            return

        console.print(f"[cyan]🧠 Generating improvement plan for: {ins['message']}[/cyan]")
        prompt = (
            "You are the Evolution Engine for SnowOS. Convert this insight into a safe, concrete shell command plan.\n"
            "Rules:\n"
            "1. DO NOT modify `nyx.py` or system core binaries.\n"
            "2. Generate shell scripts, aliases, or config changes in user-space.\n"
            "3. Return ONLY a JSON list of command strings.\n\n"
            f"Insight: {ins['message']}\n"
            f"Context: {ins.get('type')}"
        )
        text = self.nyx._llm(prompt)
        plan = self.nyx._parse_json_list(text)
        if not plan:
            console.print("[red]❌ Failed to generate plan[/red]")
            return

        imp_id = f"imp_{str(uuid.uuid4())[:6]}"
        self.improvements[imp_id] = {
            "id": imp_id,
            "source_insight": insight_id,
            "proposal": ins['message'],
            "plan": plan,
            "status": "proposed"
        }
        self._save()
        console.print(f"[green]✅ Generated improvement {imp_id} (proposed)[/green]")

    def test(self, imp_id: str):
        imp = self.improvements.get(imp_id)
        if not imp:
            console.print(f"[red]❌ Improvement {imp_id} not found[/red]")
            return
        if imp["status"] not in ("proposed", "failed_test"):
            console.print(f"[yellow]⚠️ Improvement is {imp['status']}, cannot test[/yellow]")
            return

        console.print(f"[cyan]🧪 Testing improvement {imp_id} in sandbox...[/cyan]")
        plan = imp["plan"]
        
        # Protect core
        for cmd in plan:
            if "nyx.py" in cmd or "/boot" in cmd or "/etc" in cmd:
                console.print(f"[red]🚫 Plan contains protected paths: {cmd}[/red]")
                imp["status"] = "rejected"
                self._save()
                return

        cwd = self.nyx.state.cwd
        exec_id = f"test_{imp_id}"
        sandbox_ws = self.nyx.sandbox.create(exec_id, cwd)

        self.nyx.state.cwd = sandbox_ws
        pre = self.nyx.capture_state()
        self.nyx.state.cwd = cwd

        results = self.nyx.sandbox.execute(exec_id, plan)
        has_error = any(r.get("returncode", 0) != 0 for r in results)

        self.nyx.state.cwd = sandbox_ws
        post = self.nyx.capture_state()
        self.nyx.state.cwd = cwd

        diff = self.nyx.compute_diff(pre, post)
        self.nyx.sandbox.discard(exec_id)

        if has_error:
            imp["status"] = "failed_test"
            console.print(f"[red]❌ Test failed. Status -> failed_test[/red]")
        else:
            imp["status"] = "verified"
            console.print(f"[green]✅ Test passed. Status -> verified[/green]")
            has_diff = any(v for k, v in diff.items() if v)
            if has_diff:
                for k, items in diff.items():
                    if items:
                        console.print(f"  [dim]{k}: {items}[/dim]")
        
        self._save()

    def apply(self, imp_id: str):
        imp = self.improvements.get(imp_id)
        if not imp:
            console.print(f"[red]❌ Improvement {imp_id} not found[/red]")
            return
        if imp["status"] != "verified":
            console.print(f"[red]🚫 Must be 'verified' before apply. Current: {imp['status']}[/red]")
            return

        console.print(f"[magenta]🚀 Applying improvement {imp_id} to host system...[/magenta]")
        self.nyx.run_plan(imp["plan"], label=f"Apply Improvement {imp_id}")
        imp["status"] = "applied"
        self._save()
        console.print(f"[green]✅ Successfully evolved system![/green]")

# -----------------------------------------
#  STAGE 19 - GOAL ENGINE
# -----------------------------------------
class GoalEngine:
    def __init__(self, goals_file: str, nyx_agent):
        self.goals_file = goals_file
        self.nyx = nyx_agent
        self.goals: dict[str, dict] = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.goals_file):
            try:
                with open(self.goals_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        with open(self.goals_file, "w") as f:
            json.dump(self.goals, f, indent=2)

    def create_goal(self, description: str, cwd: str) -> str:
        goal_id = "g_" + str(uuid.uuid4())[:8]
        console.print(f"[magenta]🧠 Decomposing Goal: {description}...[/magenta]")
        
        subgoals = self.nyx.decompose_task(description)
        if not subgoals:
            subgoals = [description]
            
        self.goals[goal_id] = {
            "id": goal_id,
            "description": description,
            "status": "in_progress",
            "tasks": [],
            "completed_tasks": [],
            "failed_tasks": [],
            "progress": 0.0,
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
            "retries": {}
        }
        
        console.print(f"[cyan]Sub-goals formulated for {goal_id}:[/cyan]")
        prev_tid = None
        for i, sub in enumerate(subgoals, 1):
            # Stage 41: Route sub-goal
            node_id, reason = self.nyx.swarm_router.route_task(sub)
            
            deps = [prev_tid] if prev_tid else []
            
            if node_id == self.nyx.node_id:
                console.print(f"  {i}. {sub} [dim](Local)[/dim]")
                tid = self.nyx.scheduler.schedule(
                    goal=sub, cwd=cwd, priority="NORMAL", depends_on=deps, goal_id=goal_id
                )
            else:
                console.print(f"  {i}. {sub} [dim](↳ {node_id} - {reason})[/dim]")
                # Create a remote execution task
                remote_goal = f"RemoteExec:{node_id}:{sub}"
                tid = self.nyx.scheduler.schedule(
                    goal=remote_goal, cwd=cwd, priority="NORMAL", depends_on=deps, goal_id=goal_id
                )
                
            self.goals[goal_id]["tasks"].append(tid)
            prev_tid = tid
        return goal_id

    def on_task_complete(self, goal_id: str, task_id: str, success: bool):
        if goal_id not in self.goals:
            return
        g = self.goals[goal_id]
        if success:
            if task_id not in g["completed_tasks"]:
                g["completed_tasks"].append(task_id)
            if task_id in g["failed_tasks"]:
                g["failed_tasks"].remove(task_id)
        else:
            if task_id not in g["failed_tasks"]:
                g["failed_tasks"].append(task_id)
            
            # Auto-retry logic
            retries = g["retries"].get(task_id, 0)
            if retries < 3:
                g["retries"][task_id] = retries + 1
                console.print(f"[yellow]🔄 GoalEngine: Retrying task {task_id} (Attempt {retries+1}/3)[/yellow]")
                
                # Reschedule the exact same task logic. The EOC will adapt the plan.
                old_task = self.nyx.scheduler.queue.get(task_id, {})
                if old_task:
                    new_tid = self.nyx.scheduler.schedule(
                        goal=old_task["goal"], cwd=old_task["cwd"], 
                        depends_on=old_task["depends_on"], goal_id=goal_id
                    )
                    # replace in goal list
                    g["tasks"] = [new_tid if x == task_id else x for x in g["tasks"]]
                    task_id = new_tid # for progress math

        # Update progress
        total = len(g["tasks"])
        if total > 0:
            g["progress"] = len(g["completed_tasks"]) / total
            
        if g["progress"] >= 1.0:
            g["status"] = "completed"
            console.print(f"\n[bold green]🏆 Goal Completed: {g['description']}[/bold green]")
        elif len(g["failed_tasks"]) > 0 and g["retries"].get(task_id, 0) >= 3:
            g["status"] = "failed"
            console.print(f"\n[bold red]❌ Goal Failed: {g['description']} (max retries hit)[/bold red]")
            # Update autonomy blacklist
            self.nyx.autonomy.failed_goals[g['description']] = self.nyx.autonomy.failed_goals.get(g['description'], 0) + 1
            # Cancel remaining
            for t in g["tasks"]:
                self.nyx.scheduler.cancel(t)
                
        g["updated_at"] = datetime.datetime.now().isoformat()
        self._save()

    def list_goals(self) -> list[dict]:
        return sorted(self.goals.values(), key=lambda g: g["created_at"], reverse=True)


# ─────────────────────────────────────────
#  STAGE 17 — GLOBAL STATE MODEL
# ─────────────────────────────────────────
class GlobalStateModel:
    """Single source of truth for all SnowOS subsystem states."""

    def __init__(self):
        self.filesystem: dict = {}     # path → mtime
        self.processes: dict = {}      # id → status
        self.memory_summary: dict = {} # node counts by type
        self.last_plan: list = []
        self.last_diff: dict = {}
        self.last_exec_valid: bool | None = None
        self.execution_count: int = 0

    def sync(self, filesystem: dict, processes: dict,
             emg_nodes: dict, plan: list, diff: dict, valid: bool):
        self.filesystem = filesystem
        self.processes = processes
        self.memory_summary = {}
        for n in emg_nodes.values():
            t = n["type"]
            self.memory_summary[t] = self.memory_summary.get(t, 0) + 1
        self.last_plan = plan
        self.last_diff = diff
        self.last_exec_valid = valid
        self.execution_count += 1

    def to_context_str(self) -> str:
        return (
            f"Execution #{self.execution_count} | "
            f"Last valid: {self.last_exec_valid} | "
            f"EMG nodes: {self.memory_summary} | "
            f"Last plan: {self.last_plan}"
        )


# ─────────────────────────────────────────
#  STAGE 20 — EXECUTION SANDBOX ENGINE
# ─────────────────────────────────────────
SANDBOX_ROOT = "/tmp/snowos_sandboxes"
SANDBOX_MAX_BYTES = 200 * 1024 * 1024  # 200 MB per sandbox limit


class SandboxManager:
    """Lightweight user-space filesystem sandbox.

    Each sandbox is an isolated temp directory:
        /tmp/snowos_sandboxes/<exec_id>/workspace/

    Execution flow:
        create() → mirror_workspace() → execute_in_sandbox()
        → verify → commit() OR discard()
    """

    def __init__(self, log_dir: str):
        self.log_dir = log_dir
        self.active: dict[str, dict] = {}  # exec_id → metadata
        os.makedirs(SANDBOX_ROOT, exist_ok=True)

    def create(self, exec_id: str, host_cwd: str, user_id: str = "anonymous") -> str:
        """Create an isolated sandbox workspace and mirror host_cwd into it."""
        sandbox_dir = os.path.join(SANDBOX_ROOT, user_id, exec_id)
        workspace = os.path.join(sandbox_dir, "workspace")
        os.makedirs(workspace, exist_ok=True)

        # Mirror host_cwd (shallow: files only, max 2 levels deep)
        self._mirror(host_cwd, workspace)

        log_file = os.path.join(self.log_dir, f"sandbox_{exec_id}.log")
        self.active[exec_id] = {
            "exec_id": exec_id,
            "sandbox_dir": sandbox_dir,
            "workspace": workspace,
            "host_cwd": host_cwd,
            "status": "created",
            "log_file": log_file,
        }
        return workspace

    def _mirror(self, src: str, dst: str, depth: int = 0):
        """Shallow-copy src into dst, max 2 levels deep."""
        if depth > 2:
            return
        try:
            for entry in os.scandir(src):
                target = os.path.join(dst, entry.name)
                if entry.is_file(follow_symlinks=False):
                    try:
                        shutil.copy2(entry.path, target)
                    except Exception:
                        pass
                elif entry.is_dir(follow_symlinks=False):
                    # Skip hidden dirs and the snowos dir itself
                    if entry.name.startswith(".") or entry.name in ("venv", "__pycache__", "node_modules"):
                        continue
                    os.makedirs(target, exist_ok=True)
                    self._mirror(entry.path, target, depth + 1)
        except Exception:
            pass

    def execute(self, exec_id: str, commands: list[str], limits: dict = None) -> list[dict]:
        """Run commands sequentially inside the sandbox workspace."""
        meta = self.active.get(exec_id)
        if not meta:
            raise ValueError(f"Sandbox {exec_id} not found.")

        workspace = meta["workspace"]
        meta["status"] = "running"
        results = []

        with open(meta["log_file"], "w") as logf:
            for cmd in commands:
                # ... cd logic omitted for brevity, but I must keep it ...
                if cmd.strip().startswith("cd "):
                     new_dir = cmd.strip()[3:].strip()
                     candidate = os.path.join(workspace, new_dir) if not os.path.isabs(new_dir) else new_dir
                     if os.path.isdir(candidate):
                         workspace = candidate
                         meta["workspace"] = workspace
                     results.append({"cmd": cmd, "returncode": 0, "stdout": "", "stderr": ""})
                     continue

                start_t = time.time()
                
                # Apply resource limits via cgroups/systemd-run
                final_cmd = cmd
                if limits:
                    final_cmd = CgroupEnforcer.wrap_command(cmd, exec_id, limits)
                
                try:
                    result = subprocess.run(
                        final_cmd, shell=True, cwd=workspace,
                        text=True, capture_output=True, timeout=120
                    )
                    latency = time.time() - start_t
                    logf.write(f"$ {cmd}\n{result.stdout}\n{result.stderr}\n")
                    results.append({
                        "cmd": cmd,
                        "returncode": result.returncode,
                        "stdout": result.stdout.strip(),
                        "stderr": result.stderr.strip(),
                        "latency": latency
                    })
                except Exception as e:
                    latency = time.time() - start_t
                    logf.write(f"$ {cmd}\nERROR: {e}\n")
                    results.append({
                        "cmd": cmd, 
                        "returncode": -1, 
                        "error": str(e),
                        "latency": latency
                    })

        meta["status"] = "executed"
        return results

    def commit(self, exec_id: str, host_cwd: str) -> list[str]:
        """Merge sandbox workspace back into host_cwd.
        Returns list of committed file paths.
        """
        meta = self.active.get(exec_id)
        if not meta:
            return []

        workspace = meta["sandbox_dir"] + "/workspace"
        committed = []
        try:
            for root, dirs, files in os.walk(workspace):
                # Skip venv and hidden dirs during commit
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "__pycache__")]
                rel_root = os.path.relpath(root, workspace)
                dest_root = os.path.join(host_cwd, rel_root) if rel_root != "." else host_cwd
                os.makedirs(dest_root, exist_ok=True)
                for fname in files:
                    src_file = os.path.join(root, fname)
                    dst_file = os.path.join(dest_root, fname)
                    # Only commit files that are NEW or CHANGED
                    orig = os.path.join(host_cwd, rel_root, fname) if rel_root != "." else os.path.join(host_cwd, fname)
                    if not os.path.exists(orig) or os.path.getmtime(src_file) > os.path.getmtime(orig):
                        shutil.copy2(src_file, dst_file)
                        committed.append(dst_file)
        except Exception as e:
            console.print(f"[red]❌ Sandbox commit error: {e}[/red]")

        meta["status"] = "committed"
        self.discard(exec_id)
        return committed

    def discard(self, exec_id: str):
        """Destroy sandbox — no filesystem changes propagate to host."""
        meta = self.active.get(exec_id)
        if not meta:
            return
        try:
            shutil.rmtree(meta["sandbox_dir"], ignore_errors=True)
        except Exception:
            pass
        meta["status"] = "discarded"
        self.active.pop(exec_id, None)

    def list_active(self) -> list[dict]:
        return list(self.active.values())


# ─────────────────────────────────────────
#  STAGE 25 — API SERVER
# ─────────────────────────────────────────
class APIHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        auth_header = self.headers.get('Authorization', '')
        token = auth_header[7:] if auth_header.startswith('Bearer ') else self.headers.get('X-Nyx-Key')

        if token != self.server.nyx.config.get("api_key"):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return

        try:
            data = json.loads(post_data)
            
            # Stage 41: Distributed Tracing Support
            trace_id = self.headers.get('X-Nyx-Trace-ID')
            parent_span_id = self.headers.get('X-Nyx-Parent-Span-ID')
            origin_node_id = self.headers.get('X-Nyx-Node-ID')
            
            if trace_id:
                self.server.nyx.telemetry.start_span(
                    name=f"api_request:{self.path}",
                    type="api",
                    trace_id=trace_id,
                    parent_id=parent_span_id,
                    origin_node_id=origin_node_id,
                    exec_node_id=self.server.nyx.node_id
                )
            
            if self.path == "/run":
                cmd = data.get("command")
                if cmd:
                    threading.Thread(target=self.server.nyx.process, args=(cmd,)).start()
                    self._send_json({"status": "ok", "message": f"Queued: {cmd}"})
                else:
                    self._send_error("Missing 'command'")
            elif self.path == "/goal":
                goal = data.get("goal")
                if goal:
                    threading.Thread(target=self.server.nyx.process, args=(f"nyx goal \"{goal}\"",)).start()
                    self._send_json({"status": "ok", "message": f"Goal queued: {goal}"})
                else:
                    self._send_error("Missing 'goal'")
            elif self.path == "/swarm/execute":
                goal = data.get("goal")
                if goal:
                    threading.Thread(target=self.server.nyx.process, args=(f"nyx goal \"{goal}\"",)).start()
                    self._send_json({"status": "ok", "message": f"Swarm task queued: {goal}"})
                else:
                    self._send_error("Missing 'goal'")
            elif self.path == "/swarm/learn":
                insights = data.get("insights", [])
                self.server.nyx.swarm_learning.ingest_remote_insights(insights)
                self._send_json({"status": "ok"})
            elif self.path == "/swarm/cache/get":
                task_hash = data.get("hash")
                result = self.server.nyx.swarm_cache.cache.get(task_hash)
                self._send_json({"result": result.get("result") if result else None})
            elif self.path == "/architecture/simulate":
                proposal_id = data.get("proposal_id")
                # Find proposal (simplified)
                findings = self.server.nyx.design_analysis.generate_findings()
                proposals = self.server.nyx.refactor_engine.generate_proposals(findings)
                prop = next((p for p in proposals if p["id"] == proposal_id), None)
                if prop:
                    result = self.server.nyx.arch_simulator.simulate_proposal(prop)
                    self._send_json(result)
                else:
                    self._send_error("Proposal not found")
            elif self.path == "/architecture/apply":
                proposal_id = data.get("proposal_id")
                findings = self.server.nyx.design_analysis.generate_findings()
                proposals = self.server.nyx.refactor_engine.generate_proposals(findings)
                prop = next((p for p in proposals if p["id"] == proposal_id), None)
                if prop:
                    sim = self.server.nyx.arch_simulator.simulate_proposal(prop)
                    success = self.server.nyx.arch_modifier.apply_proposal(prop, sim)
                    self._send_json({"success": success})
                else:
                    self._send_error("Proposal not found")
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            self._send_error(str(e))

    def do_GET(self):
        if self.path == "/status":
            status = {
                "version": "4.1.0",
                "workers": self.server.nyx.scheduler_engine.max_workers,
                "processes": len(self.server.nyx.process_manager.processes),
                "goals": len(self.server.nyx.goal_engine.goals)
            }
            self._send_json(status)
        elif self.path == "/swarm/profile":
            self._send_json(self.server.nyx.profiler.get_profile())
        elif self.path == "/swarm/topology":
            self._send_json(self.server.nyx.swarm_obs.get_topology())
        elif self.path == "/architecture/graph":
            self._send_json(self.server.nyx.arch_profiler.graph.get_graph_snapshot())
        elif self.path == "/architecture/insights":
            findings = self.server.nyx.design_analysis.generate_findings()
            self._send_json(findings)
        elif self.path == "/architecture/proposals":
            findings = self.server.nyx.design_analysis.generate_findings()
            proposals = self.server.nyx.refactor_engine.generate_proposals(findings)
            self._send_json(proposals)
        elif self.path == "/api/memory/suggestions":
            self._send_json(self.server.nyx.memory_engine.get_suggestions())
        elif self.path == "/api/memory/frequent":
            self._send_json(self.server.nyx.memory_engine.get_frequent_apps())
        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error(self, message):
        self.send_response(400)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "error", "message": message}).encode())

    def log_message(self, format, *args):
        pass

class APIServer:
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.port = self.nyx.config.get("api_port", 8080)
        self.enabled = self.nyx.config.get("api_enabled", False)
        self.httpd = None
        self._thread = None

    def start(self):
        if not self.enabled:
            return
        
        try:
            # Simple wrapper to allow socket reuse
            class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
                allow_reuse_address = True
            
            self.httpd = ThreadedTCPServer(("", self.port), APIHandler)
            self.httpd.nyx = self.nyx
            self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self._thread.start()
            console.print(f"[dim]🌐 API Server listening on port {self.port}[/dim]")
        except Exception as e:
            console.print(f"[red]❌ Failed to start API server: {e}[/red]")

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()


# ─────────────────────────────────────────
#  MAIN AGENT
# ─────────────────────────────────────────
class ModelArena:
    """Benchmark and select the best model for SnowOS tasks."""
    def __init__(self, nyx_agent):
        self.nyx = nyx_agent
        self.performance_file = os.path.join(self.nyx.nyx_dir, "model_performance.json")
        self.scores = self._load()

    def _load(self):
        if os.path.exists(self.performance_file):
            try:
                with open(self.performance_file) as f:
                    return json.load(f)
            except: pass
        return {}

    def _save(self):
        with open(self.performance_file, "w") as f:
            json.dump(self.scores, f, indent=2)

    def train(self, sample_tasks: list[str] = None):
        if not sample_tasks:
            sample_tasks = [
                "Decompose this goal into a 5-step plan: 'Build a secure, authenticated FastAPI backend with SQLite and a React frontend.'",
                "Review this shell script for security vulnerabilities and performance bottlenecks: 'for f in $(ls /var/log/*.log); do cp $f /tmp/backup/; done'",
                "Explain the difference between a Swarm Intelligence layer and a traditional Distributed Task Queue in the context of an OS.",
                "Generate a Python script to monitor system CPU stress and trigger a callback if it exceeds 90% for more than 30 seconds.",
                "Analyze this Execution Memory Graph node: {'id': 'e123', 'type': 'failure', 'metadata': {'error': 'Permission Denied', 'cmd': 'rm -rf /root'}} and suggest a fix."
            ]
            
        console.print("[bold cyan]🏋️ Nyx Training — Evaluating Models...[/bold cyan]")
        for task in sample_tasks:
            for model in self.nyx.available_models:
                console.print(f"  Testing [yellow]{model}[/yellow]...", end=" ")
                start = time.time()
                res = self.nyx._llm(task, model=model)
                latency = time.time() - start
                
                # Heuristic scoring
                score = 0.4
                if res:
                    if len(res) > 50: score += 0.2
                    if "{" in res or "[" in res: score += 0.2
                    if "def " in res or "import " in res: score += 0.1 # Coding relevance
                    if latency < 5.0: score += 0.1
                
                console.print(f"Score: [bold]{score:.2f}[/bold] ({latency:.1f}s)")
                
                if model not in self.scores: self.scores[model] = []
                self.scores[model].append(score)
            
            for m in self.scores: self.scores[m] = self.scores[m][-10:]
        
        self._save()
        best = self.get_best_model()
        console.print(f"[bold green]✅ Training complete. Best model: {best}[/bold green]")

    def get_best_model(self):
        if not self.scores: return self.nyx.model_id
        averages = {m: sum(s)/len(s) for m, s in self.scores.items() if s}
        if not averages: return self.nyx.model_id
        return max(averages, key=averages.get)

class NyxAI:
    MAX_CRITIQUE_ATTEMPTS = 3

    def __init__(self, autonomous: bool = False):
        # Stage 25: Platform Config
        self.config_manager = ConfigManager(os.path.expanduser("~/.snowos"))
        self.config = self.config_manager.config

        self.api_key = os.getenv("NYX_API_KEY")
        if not self.api_key:
            console.print("[red]NYX_API_KEY not set[/red]")
            raise SystemExit

        self.user = getpass.getuser()
        self.state = SystemState()
        self.autonomous = autonomous
        self.internal_commands = {} # Stage 26: Plugin hooks

        # paths
        self.nyx_dir = os.path.expanduser("~/snowos/nyx")
        self.memory_file = os.path.join(self.nyx_dir, "memory.json")
        self.tools_file = os.path.join(self.nyx_dir, "tools.json")
        self.log_dir = os.path.expanduser("~/snowos/logs")
        self.audit_file = os.path.join(self.log_dir, "audit.log")

        os.makedirs(self.nyx_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(os.path.expanduser("~/snowos/memory"), exist_ok=True)

        self.client = genai.Client(api_key=self.api_key)
        self.model_id = self.config.get("model_id", "gemini-2.0-flash")
        self.available_models = [
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash-exp"
        ]
        self.arena = ModelArena(self)
        self.competitive_mode = self.config.get("competitive_mode", True) # Default ON for competitive request

        self.security = SecurityManager(self) # Stage 27
        self.node_manager = NodeManager(os.path.join(self.nyx_dir, "nyx_network.db")) # Stage 40
        self.swarm = SwarmClient(self) # Stage 40
        
        # Node Identity (DITL)
        self.node_id = self.config.get("node_id")
        self.node_priv_key, self.node_pub_key = CryptoEngine.get_node_keys()

        self.memory = self._load_memory()
        self.registry = ToolRegistry(self.tools_file)
        
        # Stage 25: Plugin Loading
        self.plugin_manager = PluginManager(os.path.expanduser("~/snowos/plugins"), self.registry, self)
        self.plugin_manager.load_all()

        self.process_registry_file = os.path.join(self.nyx_dir, "processes.json")
        self.process_manager = ProcessManager(self.process_registry_file, self.log_dir)
        self.memory_engine = NyxMemoryEngine()
        self.emg = MemoryGraph(os.path.expanduser("~/snowos/memory/emg.json"))
        self.gsm = GlobalStateModel()   # Stage 17
        self.sandbox = SandboxManager(self.log_dir)  # Stage 20
        self._emg_lock = threading.Lock()             # Stage 21: protects EMG writes
        self.goal_engine = GoalEngine(  # Stage 19
            goals_file=os.path.join(self.nyx_dir, "goals.json"),
            nyx_agent=self
        )
        self.scheduler = TaskScheduler(   # Stage 18
            queue_file=os.path.join(self.nyx_dir, "queue.json"),
            nyx_agent=self,
        )
        
        # Stage 33: Resource-Aware Execution Engine (Initialized later)
        
        self.knowledge = KnowledgeEngine(  # Stage 22
            knowledge_file=os.path.join(self.nyx_dir, "knowledge.json"),
            workspace_root=os.path.expanduser("~/snowos"),
            nyx_agent=self
        )
        self.reflection = ReflectionEngine( # Stage 23
            insights_file=os.path.join(self.nyx_dir, "insights.json"),
            nyx_agent=self
        )
        self.evolution = EvolutionEngine( # Stage 24
            improvements_file=os.path.join(self.nyx_dir, "improvements.json"),
            nyx_agent=self
        )
        self.autonomy = AutonomyEngine(self) # Stage 29
        self.scheduler.start()
        self.knowledge.start()
        self.reflection.start()
        
        # SOC: Observability
        self.telemetry = Telemetry(db_path=os.path.join(self.nyx_dir, "nyx_observability.db"))
        
        # DEL: Deterministic Execution Layer
        self.del_storage = DELStorage(db_path=os.path.join(self.nyx_dir, "nyx_deterministic.db"))
        self.del_recorder = ExecutionRecorder(self.del_storage)
        # Stage 35: Persistent State Engine
        self.state_storage = StateStorage(db_path=os.path.join(self.nyx_dir, "nyx_state.db"))
        self.state_engine = PersistentStateEngine(
            self.state_storage,
            workspace_root=self.state.cwd
        )
        
        # Stage 33: Resource-Aware Execution Engine
        self.scheduler_engine = SchedulerEngine(
            storage=self.telemetry.storage, 
            max_workers=self.config.get("max_workers", 4)
        )
        self.scheduler_engine.start()
        
        # Stage 34: Capability-Based Security Model
        self.token_store = TokenStore()
        self.policy_engine = PolicyEngine(self.token_store)
        self.enforcer = EnforcementEngine(self.token_store, storage=self.telemetry.storage)

        # Stage 37: Kernel Interaction Layer
        self.kernel_events = KernelEventSystem(storage=self.telemetry.storage, telemetry=self.telemetry)
        
        # Identity
        self.current_user = self._load_identity()
        if self.current_user["user_id"] != "anonymous":
            workspace_root = os.path.expanduser("~/snowos/workspaces")
            user_workspace = os.path.join(workspace_root, self.current_user["user_id"])
            os.makedirs(user_workspace, exist_ok=True)
            os.chdir(user_workspace)
            self.state.cwd = user_workspace
        self.process_intel = ProcessIntelligence(storage=self.telemetry.storage)
        self.healing = HealingBroker(self)
        self.arbitrator = ResourceArbitrator(self)
        
        # Stage 41: Autonomous Swarm Intelligence Layer (ASIL)
        self.profiler = NodeProfiler(self.node_id)
        self.swarm_engine = SwarmEngine(self)
        self.swarm_router = TaskRouter(self)
        self.swarm_executor = SwarmExecutor(self)
        self.swarm_learning = SwarmLearningSync(self)
        self.swarm_cache = SwarmCache(self)
        self.swarm_obs = SwarmObservability(self)
        self.swarm_ft = SwarmFaultTolerance(self)
        
        # Stage 42: Self-Designing System Layer (SDSL)
        self.arch_profiler = ArchitectureProfiler(self)
        self.design_analysis = DesignAnalysisEngine(self.arch_profiler)
        self.refactor_engine = RefactorProposalEngine(self)
        self.arch_simulator = ArchitectureSimulator(self)
        self.arch_modifier = SelfModificationEngine(self)
        
        # Stage 44: UI/UX Intelligence Layer
        self.ui_state = UIStateController(on_intent_change=self.arbitrator.apply_persona)
        self.ui_state.start()
        self.ui_memory = UIMemory()
        self.semantic_fs = SemanticFS(self)
        self.shell = FrostShell(self)

        self.arch_profiler.start()

        self.profiler.start()
        self.swarm_engine.start()
        self.swarm_learning.start()
        self.swarm_ft.start()

        # Stage 50: Sentient Runtime Layer
        self.runtime_state = StateManager()
        self.runtime_controller = RuntimeController(self.runtime_state)
        self.runtime_scheduler = RuntimeScheduler(self)
        self.runtime_scheduler.start()

        # Stage 60: Autonomous Spatial UI layer
        self.dock_ai = DockAI()
        self.window_ai = WindowAI()
        self.layout_manager = LayoutManager()
        self.spatial_ui = SpatialUIEngine(self.dock_ai, self.window_ai, self.layout_manager)

        # Stage 70: Trust & Personality Layer
        self.personality = PersonalityEngine()
        self.trust = TrustEngine(self.memory_engine)
        self.feedback = FeedbackSystem()
        self.gating = ActionGating(self.personality, self.trust)

        # Stage 80: Learning Engine (RAG & Feedback)
        self.retriever = NyxRetriever(self.memory_engine)
        self.learning_feedback = LearningFeedbackLoop(self.memory_engine)
        self.trainer = WorkflowTrainer(self.memory_engine)
        
        # Stage 90: Stability & Observability Layer
        self.sys_logger = SnowLogger()
        self.monitor = SystemMonitor()
        self.watchdog = SnowWatchdog()
        self.crash_handler = CrashHandler(self.sys_logger)

        # Stage 100: Deterministic Performance Engine
        self.profiler = NyxProfiler()
        self.resource_manager = ResourceManager(self.profiler)
        self.scheduler_engine = AIScheduler(self.resource_manager)
        self.performance_optimizer = PerformanceOptimizer(self.profiler, self.resource_manager, self.scheduler_engine)

        # Stage 110: Sentient Swarm Intelligence (ASIL)
        self.swarm_discovery = SentientDiscovery()
        self.swarm_broker = TaskBroker(self.swarm_discovery)
        self.federated_memory = FederatedMemory(self.memory_engine, self.swarm_broker)

        # Subscribe feedback loop to EventBus
        bus.subscribe("user_feedback", self.learning_feedback.ingest_feedback)

        self.api_server = APIServer(self)
        self.api_server.start()
        self.autonomy.start()
        self.start_kernel_monitor()

    def _load_identity(self):
        from cli.user_cmds import get_token
        from identity.auth import decode_access_token
        token = get_token()
        if token:
            payload = decode_access_token(token)
            if payload:
                return {
                    "user_id": payload["sub"],
                    "role": payload["role"],
                    "token": token
                }
        return {
            "user_id": "anonymous",
            "role": "viewer",
            "token": None
        }

    def start_kernel_monitor(self):
        """Start background thread for kernel and process monitoring."""
        def monitor_loop():
            while True:
                try:
                    # Scan processes for anomalies
                    anomalies = self.process_intel.scan()
                    for anomaly in anomalies:
                        self.kernel_events.emit(
                            anomaly["type"],
                            anomaly["description"],
                            pid=anomaly["pid"],
                            metadata={"name": anomaly["name"]}
                        )
                    
                    # Scan system-level stats
                    cpu = KernelMonitor.get_cpu_stats()
                    mem = KernelMonitor.get_mem_info()
                    sys_events = self.kernel_events.check_system_anomalies(cpu, mem)
                    for e in sys_events:
                        self.healing.process_event(e)
                    
                    # Scan background service health
                    svc_events = self.kernel_events.check_service_health(self.process_manager)
                    for e in svc_events:
                        self.healing.process_event(e)
                    
                    # ⚖️ Resource Arbitration
                    intent = self.ui_state.state.get("user_intent", "idle")
                    self.arbitrator.apply_persona(intent)
                    
                    # 🛰️ Sentient Event Routing
                    bus.publish("system_health", {"cpu": cpu, "mem": mem})
                    bus.publish("user_intent", {"intent": intent})
                    
                    # Adapt polling frequency based on load
                    # (Simplified adaptive logic)
                    time.sleep(10) 
                except Exception:
                    time.sleep(30) # Back off on error
                    
        t = threading.Thread(target=monitor_loop, daemon=True, name="NyxKernelMonitor")
        t.start()
        
        # Stage 19: Resume incomplete goals automatically
        if self.autonomous:
            in_prog = [g for g in self.goal_engine.goals.values() if g["status"] == "in_progress"]
            if in_prog:
                console.print(f"[cyan]🔄 Resuming {len(in_prog)} in-progress goals...[/cyan]")

    def show_platform_status(self):
        console.print(Panel(
            f"[bold]Version:[/bold] 4.1.0-platform\n"
            f"[bold]API Enabled:[/bold] {'[green]Yes[/green]' if self.api_server.enabled else '[dim]No[/dim]'}\n"
            f"[bold]Workers:[/bold] {len(self.scheduler_engine.active_workers)}/{self.scheduler_engine.max_workers}\n"
            f"[bold]Plugins Loaded:[/bold] {len(self.plugin_manager.loaded_plugins)}\n"
            f"[bold]Swarm Nodes:[/bold] {len(self.node_manager.nodes)}\n"
            f"[bold]Goal Engine:[/bold] {len(self.goal_engine.goals)} objective(s)",
            title="❄️ SnowOS Platform Status"
        ))

    def run_doctor(self):
        console.print("[bold cyan]🩺 SnowOS Doctor — Diagnostic Report[/bold cyan]")
        
        # 1. Config Check
        conf_ok = os.path.exists(self.config_manager.config_path)
        console.print(f"  [{'green' if conf_ok else 'red'}] Config: {'OK' if conf_ok else 'Missing'}")
        
        # 2. API Check
        if self.api_server.enabled:
            api_ok = self.api_server.httpd is not None
            console.print(f"  [{'green' if api_ok else 'red'}] API Server: {'Running' if api_ok else 'Failed'}")
        else:
            console.print("  [dim] API Server: Disabled[/dim]")
            
        # 3. Memory Check
        mem_ok = len(self.emg.graph["nodes"]) > 0
        console.print(f"  [{'green' if mem_ok else 'yellow'}] Knowledge Graph: {len(self.emg.graph['nodes'])} nodes")
        
        # 4. Plugin Check
        console.print(f"  [green] Plugins: {len(self.plugin_manager.loaded_plugins)} loaded")
        
        console.print("\n[green]✅ All systems functional.[/green]")

    def run_heal(self):
        console.print("[bold cyan]🛠️ SnowOS Healing Engine — Manual Diagnostic[/bold cyan]")
        
        # 1. Check all background processes
        svc_events = self.kernel_events.check_service_health(self.process_manager)
        if not svc_events:
            console.print("  [green]✅ Background services: Stable[/green]")
        else:
            console.print(f"  [yellow]⚠️ Detected {len(svc_events)} service issues. Attempting repair...[/yellow]")
            for e in svc_events:
                self.healing.process_event(e)

        # 2. Check system resources
        cpu = KernelMonitor.get_cpu_stats()
        mem = KernelMonitor.get_mem_info()
        sys_events = self.kernel_events.check_system_anomalies(cpu, mem)
        if not sys_events:
            console.print("  [green]✅ System resources: Healthy[/green]")
        else:
            for e in sys_events:
                self.healing.process_event(e)

        report = self.healing.get_report()
        console.print(f"\n[bold green]✅ Healing session complete. Success Rate: {report['success_rate']*100:.1f}%[/bold green]")

    def analyze_shell_error(self, command: str, exit_code: str, error: str, cwd: str) -> dict:
        """Analyze a failed shell command and suggest a fix."""
        prompt = (
            f"The user ran the command: '{command}'\n"
            f"It failed with exit code {exit_code}.\n"
            f"Error output: {error}\n"
            f"Current directory: {cwd}\n\n"
            "Analyze the failure and provide a helpful suggestion and a potential fix command.\n"
            "Return JSON: {\"suggestion\": \"...\", \"fix_cmd\": \"...\"}"
        )
        
        try:
            res_text = self._llm(prompt)
            if res_text:
                # Clean markdown
                if "```json" in res_text:
                    res_text = res_text.split("```json")[1].split("```")[0].strip()
                return json.loads(res_text)
        except Exception:
            pass
            
        return {"suggestion": "Command failed. Check your syntax or dependencies.", "fix_cmd": None}

    # ══════════════════════════════════════
    #  STAGE 17 — STRUCTURED MEMORY
    # ══════════════════════════════════════
    def _load_memory(self) -> dict:
        schema = {
            "user_profile": {"name": self.user, "shell": os.environ.get("SHELL", "bash")},
            "projects": {},
            "execution_history": [],
            "conversation": [],
            "failures": [],
        }
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file) as f:
                    data = json.load(f)
                # migrate legacy flat history
                if "history" in data and "conversation" not in data:
                    schema["conversation"] = data["history"][-20:]
                    return schema
                schema.update(data)
                return schema
            except Exception:
                pass
        return schema

    def _save_memory(self):
        with open(self.memory_file, "w") as f:
            json.dump(self.memory, f, indent=2)

    def _mem_log_conversation(self, user: str, response: str):
        self.memory["conversation"].append({"user": user, "nyx": response})
        self.memory["conversation"] = self.memory["conversation"][-30:]
        self._save_memory()

    def _mem_log_execution(self, plan: list[str], results: list[dict]):
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "cwd": self.state.cwd,
            "plan": plan,
            "results": results,
        }
        self.memory["execution_history"].append(entry)
        self.memory["execution_history"] = self.memory["execution_history"][-50:]
        self._save_memory()

    def _mem_log_failure(self, cmd: str, error: str):
        self.memory["failures"].append({
            "timestamp": datetime.datetime.now().isoformat(),
            "cmd": cmd, "error": error,
        })
        self.memory["failures"] = self.memory["failures"][-20:]
        self._save_memory()

    # ══════════════════════════════════════
    #  STAGE 24 — AUDIT LOG
    # ══════════════════════════════════════
    def _audit(self, action: str, cmd: str, result: str, risk: str = "LOW"):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_id = self.current_user["user_id"]
        line = f"[{ts}] {user_id} | {action} | {risk} | {cmd} | {result}\n"
        try:
            with open(self.audit_file, "a") as f:
                f.write(line)
        except Exception:
            pass
        
        # Also log to telemetry for visibility in dashboard
        self.telemetry.log_event("AUDIT", {
            "action": action,
            "command": cmd,
            "result": result,
            "risk": risk
        }, user_id=user_id, role=self.current_user["role"])

    # ══════════════════════════════════════
    #  LLM HELPER — with rate-limit backoff
    # ══════════════════════════════════════
    def _llm(self, prompt: str, retries: int = 2, model: str = None) -> str | None:
        target_model = model
        if not target_model:
            target_model = self.arena.get_best_model() if self.competitive_mode else self.model_id
            
        for attempt in range(retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=target_model,
                    contents=prompt
                )
                return response.text.strip()
            except Exception as e:
                msg = str(e)
                if "429" in msg and attempt < retries:
                    wait = 15 * (attempt + 1)
                    console.print(f"[yellow]⏳ Rate limit hit — waiting {wait}s...[/yellow]")
                    time.sleep(wait)
                else:
                    return None
        return None

    def _parse_json_list(self, text: str) -> list | None:
        if not text:
            return None
        t = text.strip()
        for prefix in ("```json", "```"):
            if t.startswith(prefix):
                t = t[len(prefix):]
        if t.endswith("```"):
            t = t[:-3]
        try:
            result = json.loads(t.strip())
            return result if isinstance(result, list) else None
        except Exception:
            return None

    # ══════════════════════════════════════
    #  STAGE 12 — LLM PLANNER
    # ══════════════════════════════════════
    def _find_cached_plan(self, user_input: str) -> list[str] | None:
        """Search EMG for a similar successful goal and return its plan."""
        if not hasattr(self, "emg") or not self.emg.graph["nodes"]:
            return None
            
        for node in self.emg.graph["nodes"].values():
            if node["type"] == "execution_plan" and node["metadata"].get("verified", False):
                past_goal = node["metadata"].get("user_input", "")
                if not past_goal: continue
                
                # Check for high similarity
                if user_input.lower().strip() == past_goal.lower().strip():
                    plan_id = node["id"]
                    plan_cmds = []
                    # In this EMG implementation, edges are separate
                    for edge in self.emg.graph["edges"]:
                        if edge["src"] == plan_id and edge["rel"] == "CAUSED_BY":
                            cmd_node = self.emg.graph["nodes"].get(edge["dst"])
                            if cmd_node:
                                plan_cmds.append(cmd_node["metadata"]["cmd"])
                    if plan_cmds:
                        console.print(f"[green]🧠 Semantic Cache: Found identical match for '{user_input}'[/green]")
                        return plan_cmds
        return None

    def generate_plan(self, user_input: str) -> list[str] | None:
        # Check blacklist
        if hasattr(self, "autonomy") and self.autonomy.failed_goals.get(user_input, 0) >= 3:
            console.print(f"[red]🚫 Autonomy: Skipping '{user_input}' due to repeated failures.[/red]")
            return None

        # Check semantic cache first
        cached_plan = self._find_cached_plan(user_input)
        if cached_plan:
            return cached_plan

        recent_conv = self.memory["conversation"][-3:]
        history_str = "\n".join(f"  User: {e['user']}" for e in recent_conv)

        # EMG context: last 5 execution_plan nodes
        emg_plans = [
            n for n in self.emg.graph["nodes"].values()
            if n["type"] == "execution_plan"
        ][-5:]
        emg_ctx = ""
        if emg_plans:
            emg_ctx = "\nPast Executions (from memory graph):\n" + "\n".join(
                f"  [{p['timestamp'][:19]}] cwd={p['metadata'].get('cwd','')} "
                f"steps={p['metadata'].get('steps',0)} "
                f"ok={p['metadata'].get('verified',True)}"
                for p in emg_plans
            )

        # Stage 22: Knowledge Context
        knowledge_ctx = ""
        if hasattr(self, "knowledge") and self.knowledge.chunks_indexed > 0:
            results = self.knowledge.search(user_input, top_k=3)
            if results:
                knowledge_ctx = "\nCodebase Knowledge:\n" + "\n".join(
                    f"--- {r['file']} ---\n{r['text']}" for r in results
                )

        prompt = (
            "You are a system planner for SnowOS.\n"
            "Convert user requests into a list of safe shell commands.\n"
            "Return ONLY a JSON array of strings. No explanation. No markdown.\n\n"
            f"Working Directory: {self.state.cwd}\n"
            f"Last Commands: {self.state.last_commands[-5:]}\n"
            f"Recent Context:\n{history_str}"
            f"{emg_ctx}\n"
            f"{knowledge_ctx}\n\n"
            f"User Request: {user_input}"
        )
        text = self._llm(prompt)
        return self._parse_json_list(text)

    # ══════════════════════════════════════
    #  STAGE 14 — PLAN CRITIQUE ENGINE
    # ══════════════════════════════════════
    def critique_plan(self, plan: list[str], goal: str) -> tuple[bool, list[str]]:
        prompt = (
            "You are a senior DevOps engineer reviewing a shell command plan.\n"
            "Check for: missing steps, wrong order, redundant commands, unsafe ops.\n"
            'Return ONLY one of:\n'
            '  {"status": "OK"}\n'
            '  {"status": "REVISED", "plan": ["cmd1", "cmd2", ...]}\n'
            "No explanation. No markdown.\n\n"
            f"Goal: {goal}\n"
            f"Working Directory: {self.state.cwd}\n"
            f"Plan: {json.dumps(plan)}"
        )
        text = self._llm(prompt)
        if not text:
            return True, plan   # degraded gracefully
        t = text.strip()
        for prefix in ("```json", "```"):
            if t.startswith(prefix):
                t = t[len(prefix):]
        if t.endswith("```"):
            t = t[:-3]
        try:
            data = json.loads(t.strip())
            if data.get("status") == "OK":
                return True, plan
            if data.get("status") == "REVISED" and isinstance(data.get("plan"), list):
                return False, data["plan"]
        except Exception:
            pass
        return True, plan   # parse failed → treat as OK

    # ══════════════════════════════════════
    #  STAGE 15 — REASONING LOOP
    # ══════════════════════════════════════
    def reasoning_loop(self, user_input: str) -> list[str] | None:
        plan = self.generate_plan(user_input)
        if not plan:
            return None

        for attempt in range(self.MAX_CRITIQUE_ATTEMPTS):
            ok, plan = self.critique_plan(plan, user_input)
            if ok:
                if attempt > 0:
                    console.print(f"[green]✅ Plan accepted after {attempt} revision(s)[/green]")
                return plan
            console.print(f"[yellow]🔁 Critique pass {attempt + 1}: plan revised[/yellow]")

        return plan   # return best effort after max attempts

    # ══════════════════════════════════════
    #  STAGE 18 — TOOL REGISTRY ROUTER
    # ══════════════════════════════════════
    def route_intents(self, user_input: str) -> list[str]:
        text = user_input.lower().strip()
        segments = re.split(r'\s+and\s+|\s+then\s+|,\s*', text)
        commands = []
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            match = self.registry.match(seg)
            if match:
                commands.append(match)
        return commands

    # ══════════════════════════════════════
    #  STAGE 19 — TASK DECOMPOSITION
    # ══════════════════════════════════════
    def decompose_task(self, user_input: str) -> list[str] | None:
        keywords = ["build", "create a full", "make me a", "develop", "generate a project"]
        text = user_input.lower()
        if not any(k in text for k in keywords):
            return None
        prompt = (
            "You are a project planning assistant.\n"
            "Break the user's high-level goal into ordered sub-goals (2–6 items).\n"
            "Each sub-goal should be a SHORT English phrase suitable to pass to a shell planner.\n"
            "Return ONLY a JSON array of strings. No explanation. No markdown.\n\n"
            f"Goal: {user_input}"
        )
        text_resp = self._llm(prompt)
        return self._parse_json_list(text_resp)

    # ══════════════════════════════════════
    #  STAGE 20 — PROJECT BUILDER
    # ══════════════════════════════════════
    def build_project(self, user_input: str) -> bool:
        triggers = ["build me a", "build a", "create a full", "generate a project"]
        text = user_input.lower()
        if not any(t in text for t in triggers):
            return False

        console.print("[cyan]\n🏗️  Project Builder activated...[/cyan]")
        prompt = (
            "You are a project scaffold generator.\n"
            "Return ONLY valid JSON with two keys:\n"
            '  "commands": [list of shell commands to run in order]\n'
            '  "files": {"relative/path.ext": "file content string"}\n'
            "No explanation. No markdown.\n\n"
            f"Working Directory: {self.state.cwd}\n"
            f"Project Goal: {user_input}"
        )
        text_resp = self._llm(prompt)
        if not text_resp:
            return False

        t = text_resp.strip()
        for prefix in ("```json", "```"):
            if t.startswith(prefix):
                t = t[len(prefix):]
        if t.endswith("```"):
            t = t[:-3]
        try:
            data = json.loads(t.strip())
        except Exception:
            return False

        commands = data.get("commands", [])
        files = data.get("files", {})

        if commands:
            safe = self.validate_plan(commands)
            optimized = self.optimize_plan(safe)
            self.simulate(optimized)
            results = []
            for cmd in optimized:
                console.print(f"⚙️  Executing: {cmd}")
                r = self.resilient_execute(cmd)
                results.append(r)
            self._mem_log_execution(optimized, results)

        if files:
            console.print("\n[cyan]📄 Writing project files:[/cyan]")
            for rel_path, content in files.items():
                abs_path = os.path.join(self.state.cwd, rel_path)
                try:
                    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                    with open(abs_path, "w") as f:
                        f.write(content)
                    console.print(f"  ✅ {rel_path}")
                    self._audit("WRITE", abs_path, "OK")
                except Exception as e:
                    console.print(f"  ❌ {rel_path}: {e}")
                    self._audit("WRITE", abs_path, f"FAIL: {e}")

        return True

    # ══════════════════════════════════════
    #  EXECUTION LAYER
    # ══════════════════════════════════════
    DANGEROUS = ["rm -rf", "mkfs", "shutdown", "reboot", ":(){ :|:& };:"]

    def is_safe(self, cmd: str) -> bool:
        return not any(d in cmd for d in self.DANGEROUS)

    def validate_plan(self, commands: list[str]) -> list[str]:
        cleaned = []
        for cmd in commands:
            if self.is_safe(cmd):
                cleaned.append(cmd)
            else:
                console.print(f"[red]🚫 Removed unsafe step: {cmd}[/red]")
                self._audit("BLOCKED", cmd, "unsafe")
        return cleaned

    # ══════════════════════════════════════
    #  STAGE 16 — ENHANCED OPTIMIZER
    # ══════════════════════════════════════
    def optimize_plan(self, commands: list[str]) -> list[str]:
        optimized = []
        seen_dirs: set[str] = set()
        has_venv = os.path.isdir(os.path.join(self.state.cwd, "venv"))

        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue

            # source is not subprocess-compatible → skip
            if cmd.startswith("source ") or cmd == "source":
                console.print(f"[yellow]⚡ Optimizer: Skipped non-executable '{cmd}'[/yellow]")
                continue

            # Rewrite global pip → venv pip if venv exists
            if has_venv and re.match(r"^pip install", cmd):
                cmd = cmd.replace("pip install", "venv/bin/pip install", 1)

            # Prevent redundant mkdir
            if cmd.startswith("mkdir "):
                dir_name = re.sub(r'^mkdir\s+(-p\s+)?', '', cmd).strip()
                if dir_name in seen_dirs or os.path.exists(os.path.join(self.state.cwd, dir_name)):
                    console.print(f"[yellow]⚡ Optimizer: Skipped redundant '{cmd}'[/yellow]")
                    continue
                seen_dirs.add(dir_name)

            # Ensure mkdir comes before cd into same dir
            cd_match = re.match(r'^cd (.+)$', cmd)
            if cd_match:
                target = cd_match.group(1).strip()
                mkdir_cmd = f"mkdir -p {target}"
                if (mkdir_cmd not in optimized
                        and not os.path.exists(os.path.join(self.state.cwd, target))):
                    optimized.append(mkdir_cmd)
                    seen_dirs.add(target)

            # Prevent sequential duplicates
            if optimized and optimized[-1] == cmd:
                console.print(f"[yellow]⚡ Optimizer: Removed duplicate '{cmd}'[/yellow]")
                continue

            optimized.append(cmd)

        return optimized

    # ══════════════════════════════════════
    #  STAGE 23 — SIMULATION / DRY RUN
    # ══════════════════════════════════════
    def simulate(self, commands: list[str]):
        console.print("\n[cyan]🧪 Simulation — Execution Plan:[/cyan]")
        sim_cwd = self.state.cwd
        for i, cmd in enumerate(commands, 1):
            note = ""
            if cmd.startswith("mkdir "):
                d = re.sub(r'^mkdir\s+(-p\s+)?', '', cmd).strip()
                note = f"[dim]→ creates dir: {d}[/dim]"
            elif cmd.startswith("cd "):
                d = cmd[3:].strip()
                sim_cwd = os.path.join(sim_cwd, d)
                note = f"[dim]→ cwd becomes: {sim_cwd}[/dim]"
            elif cmd.startswith("touch ") or re.match(r'.+>\s*.+', cmd):
                note = "[dim]→ creates/modifies file[/dim]"
            elif "pip install" in cmd:
                note = "[dim]→ installs python package[/dim]"
            elif "git init" in cmd:
                note = "[dim]→ initializes git repo[/dim]"
            console.print(f"  {i}. {cmd}  {note}")
        console.print()

    # ══════════════════════════════════════
    #  STAGE 21 — RESILIENT EXECUTE
    # ══════════════════════════════════════
    def resilient_execute(self, cmd: str, retries: int = 1, source: str = "system") -> dict:
        self.state.last_commands.append(cmd)
        risk = self.security.classify_risk(cmd)
        
        if risk == "HIGH":
            console.print(Panel(f"[bold red]⚠️  HIGH RISK COMMAND DETECTED[/bold red]\n\n{cmd}", title="Security Alert"))
            if not self.autonomous:
                if not Confirm.ask("Do you want to proceed?"):
                    self._audit("SECURITY", cmd, "BLOCKED (User rejected)", risk=risk)
                    return {"cmd": cmd, "returncode": -1, "error": "Blocked by user"}
            else:
                self._audit("SECURITY", cmd, "ALLOWED (Auto mode)", risk=risk)

        self._audit("EXEC", cmd, "started", risk=risk)

        if not self.is_safe(cmd):
            console.print(f"[red]🚫 Blocked: {cmd}[/red]")
            self._audit("BLOCKED", cmd, "unsafe")
            return {"cmd": cmd, "returncode": -1, "error": "unsafe"}

        # cd — handled in-process
        if cmd.startswith("cd "):
            path = cmd[3:].strip()
            try:
                os.chdir(path)
                self.state.cwd = os.getcwd()
                console.print(f"[blue]📂 cwd → {self.state.cwd}[/blue]")
                self._audit("CD", path, "OK")
                return {"cmd": cmd, "returncode": 0}
            except Exception as e:
                console.print(f"[red]❌ cd failed: {e}[/red]")
                self._audit("CD", path, f"FAIL: {e}")
                self._mem_log_failure(cmd, str(e))
                return {"cmd": cmd, "returncode": 1, "error": str(e)}

        for attempt in range(retries + 1):
            try:
                result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
                if result.stdout:
                    console.print(result.stdout.strip())
                if result.stderr:
                    stderr = result.stderr.strip()

                    # STAGE 21 — self-heal: externally-managed pip
                    if result.returncode != 0 and "externally-managed-environment" in stderr and attempt == 0:
                        venv_pip = os.path.join(self.state.cwd, "venv", "bin", "pip")
                        if os.path.exists(venv_pip):
                            fixed = re.sub(r'\bpip\b', venv_pip, cmd, count=1)
                            console.print(f"[yellow]🔧 Self-heal: retrying with venv pip[/yellow]")
                            cmd = fixed
                            continue

                    if result.returncode != 0:
                        console.print(f"[yellow]{stderr}[/yellow]")
                        
                        # Detect missing dependencies
                        module_match = re.search(r"ModuleNotFoundError: No module named '([^']+)'", stderr)
                        if not module_match:
                             module_match = re.search(r"ImportError: No module named ([^\s]+)", stderr)
                        
                        if module_match:
                            module_name = module_match.group(1)
                            self.kernel_events.emit(
                                "MISSING_DEPENDENCY",
                                f"Execution failed due to missing module: {module_name}",
                                metadata={"module": module_name}
                            )
                            # Immediate healing
                            self.healing.process_event({
                                "type": "MISSING_DEPENDENCY",
                                "metadata": {"module": module_name}
                            })
                            if attempt < retries:
                                console.print(f"[yellow]🛠️ Healing: dependency {module_name} addressed. Retrying...[/yellow]")
                                continue
                    else:
                        console.print(f"[yellow]{stderr}[/yellow]")

                rc_str = f"rc={result.returncode}"
                self._audit("EXEC", cmd, rc_str)
                if result.returncode != 0 and attempt == 0:
                    self._mem_log_failure(cmd, result.stderr.strip())
                
                # Log to Behavioral Memory
                status = "success" if result.returncode == 0 else "failure"
                self.memory_engine.log_event(cmd, "shell_execution", status)
                
                return {
                    "cmd": cmd,
                    "returncode": result.returncode,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                }
            except Exception as e:
                console.print(f"[red]❌ Error: {cmd}: {e}[/red]")
                self._audit("EXEC", cmd, f"EXCEPTION: {e}")
                self._mem_log_failure(cmd, str(e))
                return {"cmd": cmd, "returncode": -1, "error": str(e)}

        return {"cmd": cmd, "returncode": -1, "error": "max retries reached"}

    # ══════════════════════════════════════
    #  STATE DIFF & VERIFICATION ENGINE
    # ══════════════════════════════════════
    def capture_state(self) -> dict:
        state = {
            "cwd": self.state.cwd,
            "timestamp": datetime.datetime.now().isoformat(),
            "env": {k: v for k, v in os.environ.items()},
            "files": {}
        }
        
        base_depth = self.state.cwd.count(os.sep)
        for root, dirs, files in os.walk(self.state.cwd):
            depth = root.count(os.sep) - base_depth
            if depth > 2:
                dirs.clear()
                continue
            
            for name in files:
                filepath = os.path.join(root, name)
                try:
                    state["files"][filepath] = os.path.getmtime(filepath)
                except Exception:
                    pass
            for name in dirs:
                dirpath = os.path.join(root, name)
                state["files"][dirpath] = "dir"
                
        return state

    def compute_diff(self, pre: dict, post: dict) -> dict:
        diff = {
            "created": [],
            "deleted": [],
            "modified": [],
            "cwd_changes": None,
            "env_changes": []
        }
        
        if pre["cwd"] != post["cwd"]:
            diff["cwd_changes"] = {"from": pre["cwd"], "to": post["cwd"]}
            
        pre_files = set(pre["files"].keys())
        post_files = set(post["files"].keys())
        
        diff["created"] = list(post_files - pre_files)
        diff["deleted"] = list(pre_files - post_files)
        
        for f in pre_files.intersection(post_files):
            if pre["files"][f] != "dir" and pre["files"][f] != post["files"][f]:
                diff["modified"].append(f)
                
        pre_env = set(pre["env"].keys())
        post_env = set(post["env"].keys())
        for k in post_env - pre_env:
            diff["env_changes"].append(f"+{k}")
            
        return diff

    def verify_execution(self, plan: list[str], diff: dict) -> bool:
        if not any(v for k,v in diff.items() if v):
            console.print("[dim]No state changes detected.[/dim]")
            return True

        prompt = (
            "You are a system verification engine.\n"
            "Given the planned commands and the resulting filesystem/state diff, determine if the execution was successful and matched expectations.\n"
            "Return ONLY JSON:\n"
            '{"status": "SUCCESS", "reason": "..."} OR {"status": "FAILURE", "reason": "..."}\n'
            "No markdown.\n\n"
            f"Plan:\n{json.dumps(plan)}\n\n"
            f"Resulting Diff:\n{json.dumps(diff)}"
        )
        text = self._llm(prompt)
        if not text:
            return True
            
        t = text.strip()
        for prefix in ("```json", "```"):
            if t.startswith(prefix): t = t[len(prefix):]
        if t.endswith("```"): t = t[:-3]
        
        try:
            data = json.loads(t.strip())
            if data.get("status") == "SUCCESS":
                return True
            else:
                reason = data.get("reason", "Mismatched expectations")
                console.print(f"[red]⚠️ Verification Failed: {reason}[/red]")
                return False
        except Exception:
            return True

    def rollback_state(self, diff: dict):
        console.print("[yellow]⏪ Initiating Automated Rollback...[/yellow]")
        rollback_count = 0
        
        # 1. Revert Created Files/Dirs
        for path in reversed(diff.get("created", [])):
            if os.path.exists(path):
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    console.print(f"  [dim]🗑️ Deleted: {path}[/dim]")
                    rollback_count += 1
                    self._audit("ROLLBACK", f"deleted {path}", "OK")
                except Exception as e:
                    console.print(f"  [red]Failed to delete {path}: {e}[/red]")
                    self._audit("ROLLBACK", f"failed delete {path}", str(e))
                    
        # 2. Revert CWD
        cwd_change = diff.get("cwd_changes")
        if cwd_change and cwd_change.get("from"):
            try:
                os.chdir(cwd_change["from"])
                self.state.cwd = os.getcwd()
                console.print(f"  [dim]📂 Reverted CWD to: {self.state.cwd}[/dim]")
                rollback_count += 1
                self._audit("ROLLBACK", f"cwd -> {self.state.cwd}", "OK")
            except Exception as e:
                console.print(f"  [red]Failed to revert CWD: {e}[/red]")
                
        if rollback_count > 0:
            console.print("[green]✅ Rollback complete.[/green]")
        else:
            console.print("[dim]No safe rollback actions could be performed.[/dim]")

    # ══════════════════════════════════════
    #  STAGE 17 — EOC: EXECUTION ORCHESTRATION CORE
    # ══════════════════════════════════════

    def _eoc_decision(self, plan: list[str], user_input: str) -> dict:
        """Pre-flight reasoning: consult EMG + GSM before committing to a plan.
        Returns {proceed: bool, reason: str, suggested_plan: list | None}
        """
        # Build a rich context from both EMG history and GSM
        past_failures = self.memory.get("failures", [])[-3:]
        gsm_ctx = self.gsm.to_context_str()

        # Recent EMG failures
        fail_nodes = [
            n for n in self.emg.graph["nodes"].values()
            if n["type"] == "failure_event"
        ][-3:]

        prompt = (
            "You are the Execution Decision Engine of SnowOS.\n"
            "Given the proposed plan, the global system state, and the execution memory graph,\n"
            "decide whether to PROCEED, ABORT, or MODIFY the plan.\n"
            "Criteria:\n"
            "  - Is this plan redundant (did we just do this)?\n"
            "  - Does it conflict with any active processes or existing files?\n"
            "  - Have similar plans failed recently?\n"
            "  - Are there missing prerequisite steps?\n"
            "Return ONLY JSON (no markdown):\n"
            '{"decision": "PROCEED|ABORT|MODIFY", "reason": "...", "modified_plan": null or ["cmd",...]}\n\n'
            f"User Goal: {user_input}\n"
            f"Proposed Plan: {json.dumps(plan)}\n"
            f"Global State: {gsm_ctx}\n"
            f"CWD: {self.state.cwd}\n"
            f"Recent Failures (memory): {json.dumps(past_failures)}\n"
            f"Recent EMG Failures: {json.dumps(fail_nodes)}\n"
            f"Active Processes: {list(self.process_manager.processes.keys())}"
        )
        text = self._llm(prompt)
        if not text:
            return {"decision": "PROCEED", "reason": "LLM unavailable", "modified_plan": None}

        t = text.strip()
        for prefix in ("```json", "```"):
            if t.startswith(prefix): t = t[len(prefix):]
        if t.endswith("```"): t = t[:-3]
        try:
            data = json.loads(t.strip())
            return {
                "decision": data.get("decision", "PROCEED"),
                "reason": data.get("reason", ""),
                "modified_plan": data.get("modified_plan"),
            }
        except Exception:
            return {"decision": "PROCEED", "reason": "parse error", "modified_plan": None}

    def _eoc_predict_failure(self, plan: list[str]) -> str | None:
        """Lightweight programmatic failure predictor using EMG + GSM.
        Returns a warning string if a likely failure is detected, else None.
        """
        warnings = []

        # 1. Redundancy check — same last plan
        if self.gsm.last_plan == plan:
            warnings.append("⚠️ Redundant: identical plan was just executed.")

        # 2. Last execution failed
        if self.gsm.last_exec_valid is False:
            warnings.append("⚠️ Last execution was invalid — caution with similar plan.")

        # 3. Repeated failure pattern in EMG
        fail_count = self.gsm.memory_summary.get("failure_event", 0)
        if fail_count >= 2:
            warnings.append(f"⚠️ EMG records {fail_count} failure event(s) — high-risk environment.")

        # 4. Target dirs already exist
        for cmd in plan:
            m = re.match(r'^mkdir(?:\s+-p)?\s+(\S+)', cmd)
            if m:
                target = os.path.join(self.state.cwd, m.group(1))
                if os.path.isdir(target):
                    warnings.append(f"⚠️ Directory already exists: {target}")

        return "\n".join(warnings) if warnings else None

    def run_plan(self, commands: list[str], label: str = "", limits: dict = None):
        """EOC-unified execution pipeline:
        decision → validate → predict → optimize → simulate
        → pre-state → execute → post-state → diff
        → verify → rollback? → EMG → GSM sync
        """
        if label:
            console.print(f"\n[bold cyan]📋 Phase: {label}[/bold cyan]")

        # 1. Safety filter
        safe = self.validate_plan(commands)
        if not safe:
            return

        # 2. Optimizer
        optimized = self.optimize_plan(safe)
        if not optimized:
            return

        # 3. EOC Decision Engine (pre-flight reasoning)
        console.print("[dim]🧠 EOC: Consulting decision engine...[/dim]")
        decision = self._eoc_decision(optimized, label or "(unlabeled)")
        d = decision["decision"]
        reason = decision["reason"]

        if d == "ABORT":
            console.print(f"[red]🛑 EOC ABORT: {reason}[/red]")
            self._audit("EOC", str(optimized), f"ABORT: {reason}")
            return

        if d == "MODIFY" and decision.get("modified_plan"):
            console.print(f"[yellow]🔄 EOC MODIFY: {reason}[/yellow]")
            optimized = self.validate_plan(decision["modified_plan"])
            optimized = self.optimize_plan(optimized)
            if not optimized:
                return
        else:
            if reason:
                console.print(f"[dim]✅ EOC PROCEED: {reason}[/dim]")

        # 4. Failure predictor
        prediction = self._eoc_predict_failure(optimized)
        if prediction:
            console.print(f"[yellow]🔮 Failure Prediction:\n{prediction}[/yellow]")

        # 5. Simulation
        self.simulate(optimized)

        # 6. Create sandbox (Stage 20)
        exec_id = str(uuid.uuid4())[:8]
        host_cwd = self.state.cwd
        console.print(f"[dim]📦 Creating sandbox {exec_id} for {self.current_user['user_id']}...[/dim]")
        sandbox_workspace = self.sandbox.create(exec_id, host_cwd, user_id=self.current_user["user_id"])

        # 7. Pre-state snapshot (from sandbox workspace)
        console.print("[dim]📸 Capturing pre-execution state...[/dim]")
        # Temporarily switch state.cwd so capture_state scans sandbox
        self.state.cwd = sandbox_workspace
        pre_state = self.capture_state()
        self.state.cwd = host_cwd

        # 8. Execute INSIDE sandbox
        console.print(f"[dim]🔒 Executing inside sandbox {exec_id}...[/dim]")
        
        # DEL: Generate deterministic plan ID
        plan_id = PlanHashingEngine.generate_plan_id(label or "unlabeled", optimized)
        self.del_storage.save_plan(plan_id, label or "unlabeled", optimized)
        
        # Stage 35: Persistent State Engine - Capture Pre-state
        pre_state_id = self.state_engine.capture_state(plan_id, label=f"Pre-exec: {label or 'unlabeled'}", user_id=self.current_user["user_id"])
        console.print(f"[dim]📸 PSE State Captured (Pre): {pre_state_id}[/dim]")
        
        # CBSM: Issue capability token for this execution
        task_type = TaskType.USER  # Default for interactive sessions
        if limits and limits.get("task_type"):
            task_type = limits["task_type"]
        
        cap_token = self.policy_engine.create_token(
            task_id=exec_id,
            plan_id=plan_id,
            user_id=self.current_user["user_id"],
            role=self.current_user["role"],
            task_type=task_type,
        )
        console.print(f"[dim]🔐 CBSM Token issued: {len(cap_token.capabilities.to_list())} capabilities[/dim]")
        
        # CBSM: Pre-execution enforcement — check every command BEFORE running
        allowed_commands = []
        for cmd in optimized:
            verdict = self.enforcer.enforce(exec_id, cmd)
            if verdict.allowed:
                allowed_commands.append(cmd)
            else:
                console.print(f"[red]🚫 BLOCKED: {cmd}[/red]")
                console.print(f"[red]   Reason: {verdict.reason}[/red]")
        
        if not allowed_commands:
            console.print("[red]All commands blocked by capability policy. Aborting.[/red]")
            self.token_store.revoke(exec_id)
            return
        
        # SOC: Distributed Tracing
        trace_id = exec_id
        goal_span_id = self.telemetry.start_span(label or "Unlabeled Goal", "goal", trace_id, user_id=self.current_user["user_id"], role=self.current_user["role"])
        plan_span_id = self.telemetry.start_span("Execution Plan", "plan", trace_id, parent_id=goal_span_id, user_id=self.current_user["user_id"], role=self.current_user["role"])
        
        results = self.sandbox.execute(exec_id, allowed_commands, limits=limits)
        
        for i, r in enumerate(results):
            cmd = r["cmd"]
            latency = r.get("latency", 0.0)
            status = "SUCCESS" if r.get("returncode", 0) == 0 else "FAILED"
            start_t = time.time() - latency # Approximation
            
            # Record command span (SOC)
            metadata = {
                "command": cmd,
                "latency": latency,
                "exit_code": r.get("returncode"),
                "stdout": r.get("stdout", "")[:1000],
                "stderr": r.get("stderr", "")[:1000]
            }
            
            if status == "FAILED":
                metadata["suggested_fix"] = "Check command syntax or system permissions."
            
            cmd_span_id = self.telemetry.start_span(cmd, "command", trace_id, parent_id=plan_span_id, user_id=self.current_user["user_id"], role=self.current_user["role"])
            self.telemetry.end_span(cmd_span_id, status, metadata=metadata)
            
            # DEL: Record execution step
            self.del_recorder.record_step(
                plan_id=plan_id,
                trace_id=trace_id,
                span_id=cmd_span_id,
                command=cmd,
                status=status,
                stdout=r.get("stdout", ""),
                stderr=r.get("stderr", ""),
                exit_code=r.get("returncode"),
                start_time=start_t,
                end_time=start_t + latency,
                latency=latency
            )
            
            if r.get("stdout"):
                console.print(r["stdout"])
            if r.get("stderr") and r.get("returncode", 0) != 0:
                console.print(f"[yellow]{r['stderr']}[/yellow]")

        # End plan and goal spans
        plan_status = "SUCCESS" if all(r.get("returncode", 0) == 0 for r in results) else "FAILED"
        self.telemetry.end_span(plan_span_id, plan_status)
        self.telemetry.end_span(goal_span_id, plan_status)

        # Stage 35: Persistent State Engine - Capture Post-state
        post_state_id = self.state_engine.capture_state(plan_id, label=f"Post-exec: {label or 'unlabeled'}")
        console.print(f"[dim]📸 PSE State Captured (Post): {post_state_id}[/dim]")
        # Display Diff
        pse_diff = self.state_engine.get_diff(pre_state_id, post_state_id)
        if pse_diff:
            console.print("\n[magenta]📊 PSE State Diff:[/magenta]")
            for d in pse_diff[:10]:
                color = "green" if d['type'] == "ADDED" else "yellow" if d['type'] == "MODIFIED" else "red"
                console.print(f"  [{color}]{d['type']}[/{color}] {d['path']}")
            if len(pse_diff) > 10:
                console.print(f"  ... and {len(pse_diff) - 10} more.")

        # Legacy diff format for verify_execution
        diff = {"added": [], "modified": [], "removed": []}
        for d in pse_diff:
            if d['type'] == "ADDED": diff["added"].append(d['path'])
            elif d['type'] == "MODIFIED": diff["modified"].append(d['path'])
            elif d['type'] == "REMOVED": diff["removed"].append(d['path'])

        # 11. Verify
        is_valid = self.verify_execution(optimized, diff)
        if is_valid:
            # COMMIT: merge sandbox → host
            committed = self.sandbox.commit(exec_id, host_cwd)
            console.print(f"[green]✅ Sandbox committed — {len(committed)} file(s) merged to workspace.[/green]")
        else:
            # DISCARD: destroy sandbox, run rollback on host diff
            self.sandbox.discard(exec_id)
            console.print("[red]🗑️  Sandbox discarded — host filesystem untouched.[/red]")
            self.rollback_state(diff)

        # 12. EMG update
        self.emg.update(
            plan=optimized, diff=diff,
            execution_id=exec_id, is_valid=is_valid,
            cwd=host_cwd, user_input=label,
        )

        # 13. GSM sync
        self.gsm.sync(
            filesystem=post_state.get("files", {}),
            processes={k: self.process_manager.get_status(k)
                       for k in self.process_manager.processes},
            emg_nodes=self.emg.graph["nodes"],
            plan=optimized,
            diff=diff,
            valid=is_valid,
        )

        self._mem_log_execution(optimized, results)
        self._audit("SANDBOX", str(optimized), f"Valid:{is_valid} Exec:{exec_id} Committed:{is_valid}")
        
        # SOC: Actionable Insights Bridge
        insights = self.telemetry.get_actionable_insights()
        for insight in insights:
            self.reflection.insights.append({
                "id": f"soc_{str(uuid.uuid4())[:6]}",
                "timestamp": datetime.datetime.now().isoformat(),
                "type": insight["type"],
                "message": insight["message"],
                "status": "new"
            })
        if insights:
            self.reflection._save()
            console.print(f"[bold magenta]🧠 SOC:[/bold magenta] {len(insights)} actionable insight(s) ingested into reflection engine.")

    # (run_autonomous removed in favor of Stage 19 Goal Engine)

    # ══════════════════════════════════════
    #  AI FALLBACK
    # ══════════════════════════════════════
    def _heartbeat(self):
        """Periodic system check and broadcast."""
        health = self.monitor.collect()
        self.watchdog.poke("nyx_engine")
        self.swarm_discovery.broadcast_presence(health)
        
        # Sync memory if in Intelligent mode
        if self.performance_optimizer.current_mode == "intelligent":
            self.federated_memory.sync_knowledge()

    def call_ai(self, user_input: str) -> str:
        conv_ctx = "\n".join(
            f"User: {e['user']}\nNyx: {e['nyx']}"
            for e in self.memory["conversation"][-3:]
        )
        prompt = (
            f"You are Nyx AI — a powerful OS assistant.\n"
            f"User: {self.user}  |  Directory: {self.state.cwd}\n"
            f"Rules:\n"
            f"1. If a system command is needed, return JSON: {{\"command\": \"...\"}}\n"
            f"2. If a web search is needed, say: SEARCH: query\n"
            f"3. Otherwise respond normally.\n\n"
            f"Recent conversation:\n{conv_ctx}\n\n"
            f"{self.retriever.get_enriched_prompt(user_input)}"
        )
        
        # Profile reasoning latency
        span = self.profiler.start("nyx.reasoning")
        response = self._llm(prompt)
        self.profiler.stop(span)
        
        return response or "AI error: could not get response."

    def internet_search(self, query: str) -> str:
        try:
            url = "https://api.duckduckgo.com/"
            res = requests.get(url, params={"q": query, "format": "json"}, timeout=10).json()
            return res.get("AbstractText") or "No result found."
        except Exception:
            return "Internet search failed."

    # ══════════════════════════════════════
    #  CORE PROCESS LOOP
    # ══════════════════════════════════════
    def process(self, user_input: str, limits: dict = None):
        self.ui_state.state["ai_active"] = True
        self.ui_state._save()
        try:
            self._process_logic(user_input, limits)
        finally:
            self.ui_state.state["ai_active"] = False
            self.ui_state._save()

    def _process_logic(self, user_input: str, limits: dict = None):
        text = user_input.strip()
        
        # Distributed Tracing
        trace_id = uuid.uuid4().hex
        span_id = self.telemetry.start_span(
            name=f"process:{text[:20]}", 
            type="command", 
            trace_id=trace_id,
            user_id=self.current_user["user_id"],
            role=self.current_user["role"]
        )
        start_time = time.time()
        if text.startswith("RemoteExec:"):
            parts = text.split(":", 2)
            node_id = parts[1]
            goal = parts[2]
            console.print(f"[cyan]🌐 Swarm Dispatch:[/cyan] Sending task to {node_id}...")
            res = self.swarm.call_node(node_id, "/swarm/execute", {"goal": goal})
            if "error" in res:
                console.print(f"[red]❌ Swarm Error:[/red] {res['error']}")
                # In failover mode, we'd retry locally or on another node
                raise Exception(f"Remote execution failed: {res['error']}")
            return

        # Check swarm cache for expensive tasks
        if len(text) > 10 and not text.startswith("nyx "):
            cached = self.swarm_cache.get(text)
            if not cached:
                cached = self.swarm_cache.query_swarm(text)
            
            if cached:
                console.print("[green]✨ Swarm Cache Hit![/green]")
                console.print(cached)
                return

        from cli.user_cmds import user_group, login_cmd, logout_cmd, whoami_cmd
        # ── Stage 39/40: Identity & Distributed Node hooks ───────────
        if text.startswith("nyx user "):
            try:
                ctx = user_group.make_context("user", text.split()[2:])
                user_group.invoke(ctx)
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")
            return

        if text.startswith("nyx node "):
            from cli.node_cmds import node_group
            try:
                ctx = node_group.make_context("node", text.split()[2:])
                node_group.invoke(ctx)
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")
            return

        if text.startswith("nyx swarm "):
            from cli.swarm_cmds import swarm_group
            try:
                ctx = swarm_group.make_context("swarm", text.split()[2:])
                swarm_group.invoke(ctx)
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")
            return

        if text.startswith("nyx architecture "):
            from cli.architecture_cmds import architecture_group
            try:
                ctx = architecture_group.make_context("architecture", text.split()[2:])
                architecture_group.invoke(ctx)
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")
            return

        if text.startswith("nyx mode"):
            parts = text.split()
            if len(parts) >= 3:
                mode = parts[2]
                success = self.personality.set_mode(mode)
                if success:
                    console.print(f"[bold cyan]❄ SnowOS:[/bold cyan] Mode set to [bold]{mode}[/bold]")
                else:
                    console.print(f"[bold red]Error:[/bold red] Unknown mode '{mode}'")
            else:
                console.print(f"[bold cyan]Current Mode:[/bold cyan] {self.personality.current_mode}")
            return

        if text.startswith("nyx feedback"):
            parts = text.split()
            if len(parts) >= 3:
                sentiment = parts[2]
                comment = " ".join(parts[3:])
                self.feedback.submit(sentiment, comment)
                console.print("[bold green]Thank you![/bold green] Feedback logged.")
            else:
                console.print("Usage: nyx feedback <good/bad> [message]")
            return

        if text == "nyx explain":
            explanation = self.trust.get_last_explanation()
            console.print(Panel(
                f"[bold magenta]Reason:[/bold magenta] {explanation['reason']}\n"
                f"[bold cyan]Confidence:[/bold cyan] {int(explanation.get('confidence', 0)*100)}%",
                title="Nyx Explainability",
                border_style="magenta"
            ))
            return

        if text == "nyx status":
            health = self.monitor.collect()
            console.print(Panel(
                f"[bold cyan]CPU:[/bold cyan] {health['cpu']}%\n"
                f"[bold green]RAM:[/bold green] {health['ram']}%\n"
                f"[bold yellow]Disk:[/bold yellow] {health['disk']}%\n"
                f"[bold magenta]System Mode:[/bold magenta] {self.personality.current_mode}",
                title="❄ SnowOS System Health",
                border_style="cyan"
            ))
            return

        if text == "nyx debug on":
            self.sys_logger.event("nyx", "debug_mode", {"status": "enabled"})
            console.print("[bold yellow]Debug Mode Enabled.[/bold yellow] Verbose logging active.")
            return

        if text.startswith("nyx login "):
            try:
                parts = text.split()
                if len(parts) < 3:
                    console.print("[yellow]Usage: nyx login <username>[/yellow]")
                else:
                    ctx = login_cmd.make_context("login", [parts[2]])
                    login_cmd.invoke(ctx)
                    self.current_user = self._load_identity()
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")
            return

        if text == "nyx logout":
            ctx = logout_cmd.make_context("logout", [])
            logout_cmd.invoke(ctx)
            self.current_user = self._load_identity()
            return

        if text == "nyx whoami" or text == "nyx whoami --global":
            from cli.user_cmds import get_token
            from identity.auth import decode_access_token
            token = get_token()
            if token:
                payload = decode_access_token(token)
                if payload:
                    role_color = "red" if payload['role'] == "admin" else "green"
                    console.print(f"Logged in as: [cyan]ID:{payload['sub']}[/cyan] ([{role_color}]{payload['role']}[/{role_color}])")
                    console.print(f"Node Identity: [yellow]{self.node_id}[/yellow]")
                    return
            console.print("[yellow]Not logged in.[/yellow]")
            return

        if text.lower() in ("exit", "quit"):
            console.print("[yellow]Exiting Nyx...[/yellow]")
            exit()

        # ── Stage 25: Platform CLI hooks ──────────────────
        if text == "nyx --version":
            console.print("[bold cyan]❄️  SnowOS Nyx Engine v4.1.0-platform[/bold cyan]")
            return

        if text == "nyx --status":
            self.show_platform_status()
            return

        if text == "nyx doctor":
            self.run_doctor()
            return

        if text == "nyx heal":
            self.run_heal()
            return

        if text == "nyx swarm status":
            console.print("[bold cyan]🌐 SnowOS Swarm Intelligence Status[/bold cyan]")
            nodes = self.node_manager.list_nodes()
            if not nodes:
                console.print("  [dim]No peers discovered.[/dim]")
            else:
                for n in nodes:
                    trust_color = "green" if n["trust_status"] == "trusted" else "yellow"
                    console.print(f"  ● {n['node_id'][:8]} @ {n['url']} [{trust_color}]{n['trust_status']}[/{trust_color}]")
            
            insights_count = len([i for i in self.reflection.insights if i.get("source") == "swarm"])
            console.print(f"\n  [bold]Knowledge Sync:[/bold] {insights_count} swarm-shared insights")
            return

        if text.startswith("nyx trace "):
            parts = text.split()
            goal_id = parts[2] if len(parts) > 2 else ""
            show_slow = "--slow" in parts
            trace_command(goal_id, db_path=os.path.join(self.nyx_dir, "nyx_observability.db"), show_slow=show_slow)
            return

        if text == "nyx metrics":
            metrics_command(db_path=os.path.join(self.nyx_dir, "nyx_observability.db"))
            return

        # ── Stage 32: DEL CLI hooks ───────────────────────
        if text.startswith("nyx replay "):
            parts = text.split()
            plan_id = parts[2] if len(parts) > 2 else ""
            mode = "live" if "--live" in parts else "dry-run"
            replay_command(
                plan_id, 
                mode=mode, 
                db_path=os.path.join(self.nyx_dir, "nyx_deterministic.db"), 
                sandbox_manager=self.sandbox,
                policy_engine=self.policy_engine,
                enforcer=self.enforcer
            )
            return

        if text.startswith("nyx rollback "):
            snapshot_id = text[13:].strip()
            rollback_command(snapshot_id, target_dir=self.state.cwd, db_path=os.path.join(self.nyx_dir, "nyx_deterministic.db"))
            return

        if text.startswith("nyx history"):
            failed_only = "--failed" in text
            history_command(failed_only=failed_only, db_path=os.path.join(self.nyx_dir, "nyx_deterministic.db"))
            return

        # ── Stage 26: Plugin internal hooks ───────────────
        for pattern, callback in self.internal_commands.items():
            m = re.match(pattern, text)
            if m:
                callback(m)
                return

        # ── Stage 14: Daemon CLI hooks ─────────────────────
        if text.startswith("nyx run background "):
            cmd = text[19:].strip().strip('"').strip("'")
            if not self.is_safe(cmd):
                console.print(f"[red]🚫 Blocked dangerous background command: {cmd}[/red]")
                return
            try:
                pid = self.process_manager.start(cmd, self.state.cwd)
                console.print(f"[green]✅ Started '{cmd}' in background (ID: {pid})[/green]")
            except Exception as e:
                console.print(f"[red]❌ Failed to start: {e}[/red]")
            return

        if text == "nyx list processes":
            processes = self.process_manager.processes
            if not processes:
                console.print("[dim]No background processes.[/dim]")
                return
            console.print("[bold cyan]📋 Background Processes[/bold cyan]")
            for p_id, info in processes.items():
                status = self.process_manager.get_status(p_id)
                color = "green" if status == "running" else "yellow"
                console.print(f"  [{p_id}] [{color}]{status}[/{color}] - {info['command']}")
            return

        if text == "nyx sandbox list":
            active = self.sandbox.list_active()
            if not active:
                console.print("[dim]No active sandboxes.[/dim]")
            else:
                console.print("[bold cyan]📦 Active Sandboxes[/bold cyan]")
                for s in active:
                    console.print(f"  [{s['exec_id']}] {s['status']} → {s['workspace']}")
            return

        if text == "nyx workers":
            workers_command(self.scheduler_engine)
            return

        if text == "nyx queue":
            queue_command(self.scheduler_engine)
            return

        if text == "nyx scheduler-status":
            scheduler_status_command(self.scheduler_engine)
            return

        # ── Stage 34: CBSM CLI hooks ─────────────────────
        if text == "nyx policy":
            policy_command(self.policy_engine)
            return

        if text.startswith("nyx token "):
            task_id = text[10:].strip()
            token_command(self.token_store, task_id)
            return

        if text == "nyx audit":
            audit_command(self.telemetry.storage)
            return

        # ── Stage 35: Persistent State Engine (PSE) hooks ──
        if text == "nyx state history":
            state_history_command(self.state_engine)
            return

        if text.startswith("nyx state show "):
            state_id = text[15:].strip()
            state_show_command(self.state_engine, state_id)
            return

        if text.startswith("nyx state diff "):
            parts = text.split()
            if len(parts) >= 5:
                state_diff_command(self.state_engine, parts[3], parts[4])
            return

        if text.startswith("nyx state checkout "):
            state_id = text[19:].strip()
            state_checkout_command(self.state_engine, state_id)
            return

        if text == "nyx dashboard":
            dashboard_command()
            return

        # ── Stage 37: Kernel Interaction Layer hooks ─────
        if text == "nyx kernel-status":
            kernel_status_command()
            return

        if text == "nyx processes":
            processes_command(self.process_intel)
            return

        if text == "nyx kernel-events":
            kernel_events_command(self.telemetry.storage)
            return

        # ── Stage 28: Swarm CLI hooks ─────────────────────
        if text == "nyx swarm list":
            nodes = self.node_manager.nodes
            if not nodes:
                console.print("[dim]No nodes registered in the swarm.[/dim]")
                return
            console.print("[bold cyan]🌐 SnowOS Swarm Nodes[/bold cyan]")
            for n_id, info in nodes.items():
                console.print(f"  [{n_id}] {info['host']}:{info['port']} - [green]{info['status']}[/green]")
            return

        if text.startswith("nyx swarm add "):
            parts = text[14:].split()
            if len(parts) == 4:
                try:
                    n_id, host, port, token = parts
                    self.node_manager.add_node(n_id, host, int(port), token)
                    console.print(f"[green]✅ Node '{n_id}' added to swarm.[/green]")
                except ValueError:
                    console.print("[red]Port must be an integer.[/red]")
            else:
                console.print("[red]Usage: nyx swarm add <id> <host> <port> <token>[/red]")
            return

        if text.startswith("nyx run ") and " on " in text:
            m = re.match(r'^nyx run "(.+)" on (.+)$', text)
            if m:
                cmd, node_id = m.groups()
                if node_id == "local":
                    self.process(cmd)
                else:
                    console.print(f"[cyan]📡 Routing command to node '{node_id}': {cmd}[/cyan]")
                    res = self.swarm.call_node(node_id, "/run", {"command": cmd})
                    if "error" in res:
                        console.print(f"[red]❌ Swarm error: {res['error']}[/red]")
                        console.print("[yellow]Falling back to local execution...[/yellow]")
                        self.process(cmd)
                    else:
                        console.print(f"[green]✅ {res['message']}[/green]")
                return

        # ── Stage 29: Autonomy Engine hooks ───────────────
        if text == "nyx auto on":
            self.autonomy.enabled = True
            self.config_manager.set("autonomy_enabled", True)
            self.autonomy.start()
            console.print("[green]✅ Continuous Autonomy enabled.[/green]")
            return

        if text == "nyx auto off":
            self.autonomy.enabled = False
            self.config_manager.set("autonomy_enabled", False)
            console.print("[yellow]⚠️ Continuous Autonomy disabled.[/yellow]")
            return

        if text == "nyx auto status":
            status = "enabled" if self.autonomy.enabled else "disabled"
            color = "green" if self.autonomy.enabled else "dim"
            console.print(f"[bold magenta]🧠 Autonomy Engine Status:[/bold magenta] [{color}]{status}[/{color}]")
            console.print(f"  Tasks this hour: {self.autonomy.task_count_hour}/{self.config.get('max_auto_tasks_per_hour', 2)}")
            return

        if text == "nyx auto think":
            console.print("[dim]🧠 Autonomy: Scanning for proactive tasks...[/dim]")
            self.autonomy._think()
            return

        # ── Stage 22: Knowledge Engine hooks ──────────────
        if text == "nyx knowledge status":
            status = self.knowledge.status
            files = self.knowledge.files_indexed
            chunks = self.knowledge.chunks_indexed
            console.print(f"[bold cyan]📚 Knowledge Engine[/bold cyan]")
            console.print(f"  Status:  [green]{status}[/green]")
            console.print(f"  Indexed: {files} files ({chunks} chunks)")
            return
            
        if text.startswith("nyx knowledge search "):
            query = text[21:].strip().strip('"').strip("'")
            results = self.knowledge.search(query)
            if not results:
                console.print("[dim]No relevant knowledge found.[/dim]")
            else:
                for i, r in enumerate(results):
                    console.print(f"\n[bold cyan]Result {i+1} (Score: {r['score']:.2f}) - {r['file']}[/bold cyan]")
                    console.print(r['text'])
            return
            
        if text == "nyx knowledge reindex":
            self.knowledge.reindex()
            console.print("[green]✅ Knowledge index cleared and rebuild scheduled.[/green]")
            return

        # ── Stage 23: Reflection Engine hooks ─────────────
        if text == "nyx reflect now":
            console.print("[cyan]🧠 Running reflection analysis on recent history...[/cyan]")
            self.reflection.reflect()
            console.print("[green]✅ Reflection complete. Run 'nyx insights list' to view.[/green]")
            return
            
        if text == "nyx insights list":
            if not self.reflection.insights:
                console.print("[dim]No insights available.[/dim]")
            else:
                console.print(f"[bold cyan]💡 System Insights ({len(self.reflection.insights)})[/bold cyan]")
                for ins in reversed(self.reflection.insights[-5:]):
                    color = "green" if ins.get("status") == "new" else "dim"
                    console.print(f"  [{ins['id']}] [{color}]{ins.get('type', 'info')}[/{color}] - {ins['message'][:60]}...")
            return
            
        if text.startswith("nyx insights show "):
            ins_id = text[18:].strip()
            for ins in self.reflection.insights:
                if ins["id"] == ins_id:
                    console.print(Panel(
                        f"[bold]Type:[/bold] {ins.get('type')}\n"
                        f"[bold]Confidence:[/bold] {ins.get('confidence')}\n"
                        f"[bold]Status:[/bold] {ins.get('status')}\n\n"
                        f"{ins.get('message')}",
                        title=f"💡 Insight {ins_id}"
                    ))
                    ins["status"] = "read"
                    self.reflection._save()
                    return
            console.print(f"[red]❌ Insight {ins_id} not found[/red]")
            return

        # ── Stage 24: Evolution Engine hooks ──────────────
        if text == "nyx improve list":
            imps = self.evolution.improvements
            if not imps:
                console.print("[dim]No proposed improvements.[/dim]")
            else:
                console.print(f"[bold cyan]🚀 System Improvements ({len(imps)})[/bold cyan]")
                for i_id, imp in imps.items():
                    color = "green" if imp["status"] == "applied" else ("yellow" if imp["status"] == "verified" else "dim")
                    console.print(f"  [{i_id}] [{color}]{imp['status']}[/{color}] - {imp['proposal'][:60]}...")
            return

        if text.startswith("nyx improve generate "):
            insight_id = text[21:].strip()
            self.evolution.generate_from_insight(insight_id)
            return

        if text.startswith("nyx improve test "):
            imp_id = text[17:].strip()
            self.evolution.test(imp_id)
            return

        if text.startswith("nyx improve apply "):
            imp_id = text[18:].strip()
            self.evolution.apply(imp_id)
            return

        if text.startswith("nyx stop "):
            pid = text[9:].strip()
            if self.process_manager.stop(pid):
                console.print(f"[green]✅ Stopped process {pid}[/green]")
            else:
                console.print(f"[red]❌ Process {pid} not found[/red]")
            return

        if text.startswith("nyx restart "):
            pid = text[12:].strip()
            try:
                new_pid = self.process_manager.restart(pid)
                console.print(f"[green]✅ Restarted process. New ID: {new_pid}[/green]")
            except Exception as e:
                console.print(f"[red]❌ Failed to restart: {e}[/red]")
            return

        if text.startswith("nyx attach "):
            pid = text[11:].strip()
            self.process_manager.attach(pid)
            return

        # ── Stage 16: EMG memory query ──────────────────
        if text.startswith("nyx memory query "):
            question = text[17:].strip().strip('"').strip("'")
            console.print("[cyan]🧠 Querying Execution Memory Graph...[/cyan]")
            answer = self.emg.query(question, self._llm)
            console.print(Panel(Markdown(answer), title="🗂️ Memory Graph"))
            return

        if text == "nyx memory stats":
            nodes = len(self.emg.graph["nodes"])
            edges = len(self.emg.graph["edges"])
            types: dict[str, int] = {}
            for n in self.emg.graph["nodes"].values():
                types[n["type"]] = types.get(n["type"], 0) + 1
            console.print(Panel(
                f"[bold]Nodes:[/bold] {nodes}  [bold]Edges:[/bold] {edges}\n" +
                "\n".join(f"  {t}: {c}" for t, c in types.items()),
                title="🗺️ EMG Stats"
            ))
            return

        # ── Stage 18: Scheduler CLI hooks ───────────────
        # nyx schedule "goal" [in Xs] [every Ys] [priority P] [after id1,id2]
        m = re.match(
            r'^nyx schedule "(.+?)"'
            r'(?: in (\d+)([smh]))?'
            r'(?: every (\d+)([smh]))?'
            r'(?: priority (HIGH|NORMAL|LOW))?'
            r'(?: after ([\w,]+))?$',
            text, re.IGNORECASE
        )
        if m:
            goal = m.group(1)
            # delay
            delay_sec = 0
            if m.group(2):
                v, u = int(m.group(2)), m.group(3).lower()
                delay_sec = v * (60 if u == 'm' else 3600 if u == 'h' else 1)
            # interval
            interval_sec = None
            if m.group(4):
                v, u = int(m.group(4)), m.group(5).lower()
                interval_sec = v * (60 if u == 'm' else 3600 if u == 'h' else 1)
            priority = m.group(6) or "NORMAL"
            depends_on = [d.strip() for d in m.group(7).split(",")] if m.group(7) else []
            tid = self.scheduler.schedule(
                goal=goal, cwd=self.state.cwd,
                priority=priority, delay_sec=delay_sec,
                interval_sec=interval_sec, depends_on=depends_on,
            )
            run_msg = f" in {delay_sec}s" if delay_sec else " immediately"
            rec_msg = f", recurring every {interval_sec}s" if interval_sec else ""
            console.print(f"[green]⏰ Scheduled '{goal}'{run_msg}{rec_msg} — ID: {tid}[/green]")
            return

        if text == "nyx queue list":
            tasks = self.scheduler.list_tasks()
            if not tasks:
                console.print("[dim]No tasks in queue.[/dim]")
                return
            console.print("[bold cyan]⏰ Task Queue[/bold cyan]")
            for t in tasks:
                color = {
                    "pending": "yellow", "running": "green",
                    "done": "dim", "failed": "red", "cancelled": "bright_black"
                }.get(t["status"], "white")
                run_at = t["run_at"][:19] if t["run_at"] else "now"
                console.print(
                    f"  [{t['id']}] [{color}]{t['status']:9}[/{color}] "
                    f"[{t['priority']:6}] run@{run_at} — {t['goal']}"
                )
            return

        if text.startswith("nyx queue cancel "):
            tid = text[17:].strip()
            if self.scheduler.cancel(tid):
                console.print(f"[green]✅ Cancelled task {tid}[/green]")
            else:
                console.print(f"[red]❌ Cannot cancel {tid} (not pending or not found)[/red]")
            return

        # ── Stage 19: Goal Engine CLI hooks ───────────────
        if text.startswith("nyx goal "):
            desc = text[9:].strip().strip('"').strip("'")
            gid = self.goal_engine.create_goal(desc, self.state.cwd)
            console.print(f"[green]🚀 Goal Tracked: {gid}[/green]")
            return
            
        if text == "nyx goals list":
            goals = self.goal_engine.list_goals()
            if not goals:
                console.print("[dim]No goals tracked.[/dim]")
                return
            console.print("[bold cyan]🎯 Tracked Goals[/bold cyan]")
            for g in goals:
                color = {
                    "in_progress": "yellow", "completed": "green", "failed": "red"
                }.get(g["status"], "white")
                pct = int(g["progress"] * 100)
                console.print(f"  [{g['id']}] [{color}]{g['status']:11}[/{color}] {pct:3}% — {g['description']}")
            return
            
        if text.startswith("nyx goals cancel "):
            gid = text[17:].strip()
            if gid in self.goal_engine.goals:
                self.goal_engine.goals[gid]["status"] = "failed"
                for tid in self.goal_engine.goals[gid]["tasks"]:
                    self.scheduler.cancel(tid)
                self.goal_engine._save()
                console.print(f"[green]✅ Goal {gid} cancelled.[/green]")
            else:
                console.print(f"[red]❌ Goal {gid} not found.[/red]")
            return

        # ── Stage 45: Model Arena ────────────────────────
        if text == "nyx train":
            self.arena.train()
            return

        if text == "nyx models":
            console.print("[bold cyan]🤖 Model Arena Performance[/bold cyan]")
            for model, scores in self.arena.scores.items():
                avg = sum(scores)/len(scores) if scores else 0
                console.print(f"  {model:25} : [bold]{avg:.2f}[/bold] ({len(scores)} samples)")
            return

        # ── Stage 44: UI/UX Engine CLI hooks ──────────────
        if text.startswith("nyx ui "):
            from cli.ui_cmds import ui_group
            parts = text.split()[2:]
            try:
                with ui_group.make_context('ui', parts, obj=self) as ctx:
                    ui_group.invoke(ctx)
            except Exception as e:
                console.print(f"[red]❌ UI Engine error: {e}[/red]")
            return

        # ── Stage 20: project builder ─────────────────────
        if self.build_project(text):
            return

        # ── Stage 15: reasoning loop → LLM plan ──────────
        commands = self.reasoning_loop(text)

        # ── Stage 18: intent router fallback ─────────────
        if not commands:
            commands = self.route_intents(text)

        if commands:
            self.run_plan(commands, limits=limits)
            return

        # ── AI conversational fallback ────────────────────
        response = self.call_ai(text)

        if response.startswith("SEARCH:"):
            query = response[7:].strip()
            result = self.internet_search(query)
            console.print(Panel(result, title="🌐 Search"))
            return

        match = re.search(r'\{[^}]+\}', response)
        if match:
            try:
                data = json.loads(match.group(0))
                cmd = data.get("command", "")
                if cmd:
                    console.print(Panel(cmd, title="AI Command"))
                    self.resilient_execute(cmd)
                    return
            except Exception:
                pass

        console.print(Panel(Markdown(response), title="Nyx"))
        self._mem_log_conversation(text, response)
        
        # Stage 44: UI Feedback Loop
        self._evaluate_ui_outcome(text, response)

    def _evaluate_ui_outcome(self, user_input, nyx_response):
        """Observe the UI state after an action and adjust behavior."""
        # Check if the UI is stressed
        stress = self.ui_state.state["system_stress"]
        if stress > 0.9:
            # Proactively suggest low-power or compact mode
            self.ui_state.state["performance_mode"] = "low_power"
            console.print("[dim]Nyx: UI performance scaled down due to extreme system stress.[/dim]")

    # ══════════════════════════════════════
    #  RUN
    # ══════════════════════════════════════
    def run(self):
        os.system("clear")
        mode_tag = " [AUTO]" if self.autonomous else ""
        console.print(Panel(
            f"❄️  Nyx v4 — Agentic OS Layer{mode_tag}",
            box=rich.box.DOUBLE_EDGE
        ))

        while True:
            try:
                user_input = Prompt.ask("SnowOS ❯")
                if user_input.strip():
                    self.process(user_input)
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted.[/yellow]")
                break
        self.scheduler.stop()
        self.scheduler_engine.stop()
        self.knowledge.stop()
        self.reflection.stop()
        self.autonomy.stop()
        self.api_server.stop()
        self.ui_state.stop()
        self.arch_profiler.stop()


if __name__ == "__main__":
    import sys
    auto = "--auto" in sys.argv
    nyx = NyxAI(autonomous=auto)
    
    # If arguments provided (other than --auto), process them and exit
    args = [a for a in sys.argv[1:] if a != "--auto"]
    if args:
        nyx.process("nyx " + " ".join(args))
        # Shutdown
        nyx.scheduler.stop()
        nyx.scheduler_engine.stop()
        nyx.knowledge.stop()
        nyx.reflection.stop()
        nyx.autonomy.stop()
        nyx.api_server.stop()
        nyx.ui_state.stop()
        nyx.arch_profiler.stop()
    else:
        # Launch the Sentient Shell
        nyx.shell.run()
