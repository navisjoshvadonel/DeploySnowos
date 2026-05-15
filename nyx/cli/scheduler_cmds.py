from rich.console import Console
from rich.table import Table
import time

console = Console()

def queue_command(scheduler):
    status = scheduler.get_status()
    pending = status["pending_tasks"]
    
    table = Table(title="RAEE Task Queue")
    table.add_column("Task ID", style="cyan")
    table.add_column("Priority", style="magenta")
    table.add_column("Wait Time", style="green")
    table.add_column("Goal", style="white")
    
    for t in pending:
        table.add_row(
            t["task_id"], 
            str(t["priority"]), 
            f"{t['wait_time']:.1f}s", 
            t["goal"]
        )
    
    console.print(table)

def workers_command(scheduler):
    with scheduler._lock:
        active = list(scheduler.active_workers.values())
    
    table = Table(title="RAEE Worker Status")
    table.add_column("Task ID", style="cyan")
    table.add_column("Runtime", style="green")
    table.add_column("CPU Limit", style="magenta")
    table.add_column("MEM Limit", style="magenta")
    
    for w in active:
        runtime = time.time() - w["start_time"]
        limits = w["limits"]
        table.add_row(
            w["task"]["id"],
            f"{runtime:.1f}s",
            f"{limits.get('cpu_quota', 'N/A')}%",
            f"{limits.get('memory_limit', 'N/A')}"
        )
    
    console.print(table)

def scheduler_status_command(scheduler):
    status = scheduler.get_status()
    load = status["load"]
    
    console.print(f"\n[bold]System Load:[/bold]")
    console.print(f"  CPU: {load['cpu_percent']}%")
    console.print(f"  MEM: {load['memory_percent']}%")
    console.print(f"  Load Avg: {load['load_avg']}")
    
    console.print(f"\n[bold]Scheduler:[/bold]")
    console.print(f"  Queue Length: {status['queue_size']}")
    console.print(f"  Active Workers: {status['active_workers']}")
