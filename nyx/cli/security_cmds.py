"""
Stage 34 — Security CLI Commands

Provides:
  nyx policy   — Show current capability policies
  nyx token    — Inspect a task's capability token
  nyx audit    — Show recent capability violations
"""

import time
import datetime
from rich.console import Console
from rich.table import Table

console = Console()


def policy_command(policy_engine):
    """Display the current capability policy configuration."""
    summary = policy_engine.get_policy_summary()
    
    console.print("\n[bold cyan]🔐 CBSM Capability Policies[/bold cyan]\n")
    
    for task_type, caps in summary.items():
        table = Table(title=f"{task_type.upper()} Tasks")
        table.add_column("Capability", style="green")
        
        if caps:
            for cap in caps:
                table.add_row(cap)
        else:
            table.add_row("[dim]No default capabilities (inherits from original)[/dim]")
        
        console.print(table)
        console.print()


def token_command(token_store, task_id):
    """Inspect the capability token assigned to a task."""
    token = token_store.get(task_id)
    
    if not token:
        console.print(f"[yellow]No token found for task: {task_id}[/yellow]")
        return
    
    data = token.to_dict()
    valid = token.verify()
    
    console.print(f"\n[bold cyan]🔑 Token for Task: {task_id}[/bold cyan]\n")
    console.print(f"  Plan ID:    {data['plan_id']}")
    console.print(f"  Issued:     {datetime.datetime.fromtimestamp(data['issued_at']).strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"  Expires:    {datetime.datetime.fromtimestamp(data['expires_at']).strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"  Valid:      {'[green]Yes[/green]' if valid else '[red]No (expired or tampered)[/red]'}")
    console.print(f"  Signature:  {data['signature'][:16]}...")
    console.print(f"\n  [bold]Capabilities:[/bold]")
    
    for cap in data["capabilities"]:
        console.print(f"    • {cap}")
    console.print()


def audit_command(storage):
    """Show recent capability violations."""
    violations = storage.get_capability_violations(limit=20)
    
    if not violations:
        console.print("[green]✅ No capability violations recorded.[/green]")
        return
    
    table = Table(title="🚨 Recent Capability Violations")
    table.add_column("Time", style="dim")
    table.add_column("Task", style="cyan")
    table.add_column("Command", style="white", max_width=40)
    table.add_column("Missing", style="red")
    table.add_column("Reason", style="yellow", max_width=30)
    
    for v in violations:
        ts = datetime.datetime.fromtimestamp(v["timestamp"]).strftime("%H:%M:%S")
        cmd = v["command"][:40] if v["command"] else ""
        table.add_row(ts, v["task_id"] or "", cmd, v["required_capability"] or "", v["reason"] or "")
    
    console.print(table)
