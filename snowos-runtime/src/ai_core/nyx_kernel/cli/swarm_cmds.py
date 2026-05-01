import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

@click.group(name="swarm")
def swarm_group():
    """Autonomous Swarm Intelligence Layer (ASIL)"""
    pass

@swarm_group.command(name="status")
def swarm_status():
    """Show swarm health and topology."""
    from nyx import NyxAI
    nyx = NyxAI(autonomous=False)
    
    topology = nyx.swarm_obs.get_topology()
    nodes = topology["nodes"]
    
    console.print(Panel("[bold cyan]❄️  SnowOS Swarm Topology[/bold cyan]"))
    
    table = Table()
    table.add_column("Node ID", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("CPU", style="yellow")
    table.add_column("Mem", style="yellow")
    
    for n in nodes:
        profile = n.get("profile", {})
        node_type = "LOCAL" if n.get("is_local") else "REMOTE"
        status = n.get("status", "online")
        status_color = "green" if status == "online" else "red"
        
        table.add_row(
            n["node_id"][:12] + "...",
            node_type,
            f"[{status_color}]{status}[/{status_color}]",
            f"{profile.get('current_load', 0):.1f}%",
            f"{profile.get('mem_used', 0):.1f}%"
        )
    
    console.print(table)
    
    active_jobs = topology["active_tasks"]
    if active_jobs:
        console.print(f"\n[bold yellow]Active Swarm Jobs: {len(active_jobs)}[/bold yellow]")
        for job in active_jobs:
            console.print(f"  - {job['id']}: {job['description']} ({len(job['subtasks'])} subtasks)")

@swarm_group.command(name="nodes")
def swarm_nodes():
    """List nodes and their profiles."""
    from nyx import NyxAI
    nyx = NyxAI(autonomous=False)
    
    peers = nyx.swarm_engine.get_active_peers()
    local = nyx.profiler.get_profile()
    
    table = Table(title="Swarm Node Profiles")
    table.add_column("Node ID", style="cyan")
    table.add_column("Load", style="yellow")
    table.add_column("Success Rate", style="green")
    table.add_column("Latency", style="blue")
    
    # Local
    table.add_row(
        local["node_id"][:12] + " (Self)",
        f"{local['current_load']:.1f}%",
        f"{local.get('success_rate', 1.0)*100:.1f}%",
        f"{local.get('avg_latency', 0):.2f}s"
    )
    
    for p in peers:
        profile = p.get("profile", {})
        table.add_row(
            p["node_id"][:12] + "...",
            f"{profile.get('current_load', 0):.1f}%",
            f"{profile.get('success_rate', 1.0)*100:.1f}%",
            f"{profile.get('avg_latency', 0):.2f}s"
        )
    
    console.print(table)

@swarm_group.command(name="tasks")
def swarm_tasks():
    """Show distributed tasks."""
    from nyx import NyxAI
    nyx = NyxAI(autonomous=False)
    
    jobs = nyx.swarm_executor.list_active_jobs()
    if not jobs:
        console.print("[yellow]No active swarm tasks.[/yellow]")
        return
        
    for job in jobs:
        console.print(Panel(f"Job: {job['id']} - {job['description']}", style="bold cyan"))
        table = Table()
        table.add_column("Subtask ID")
        table.add_column("Node")
        table.add_column("Goal")
        table.add_column("Status")
        
        for st in job["subtasks"]:
            status_color = "green" if st["status"] == "dispatched" else "yellow"
            table.add_row(
                st["id"],
                st["node_id"][:12] + "...",
                st["goal"][:30] + "...",
                f"[{status_color}]{st['status']}[/{status_color}]"
            )
        console.print(table)

@swarm_group.command(name="route")
@click.argument("task")
def swarm_route(task):
    """Show routing decision for a task."""
    from nyx import NyxAI
    nyx = NyxAI(autonomous=False)
    
    node_id, reason = nyx.swarm_router.route_task(task)
    
    console.print(f"[bold cyan]Task:[/bold cyan] {task}")
    console.print(f"[bold green]Routed to:[/bold green] {node_id}")
    console.print(f"[bold yellow]Reason:[/bold yellow] {reason}")
    
    if nyx.swarm_router.should_decompose(task):
        console.print("[magenta]💡 This task would be decomposed for the swarm.[/magenta]")
        assignments = nyx.swarm_router.decompose_for_swarm(task)
        for a in assignments:
            console.print(f"  ↳ {a['node_id']} : {a['goal']}")
