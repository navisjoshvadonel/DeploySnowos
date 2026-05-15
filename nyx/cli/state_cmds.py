import datetime
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
import json

console = Console()

def state_history_command(engine):
    history = engine.get_history()
    if not history:
        console.print("[yellow]No states recorded yet.[/yellow]")
        return
        
    table = Table(title="🕒 SnowOS State History")
    table.add_column("State ID", style="cyan")
    table.add_column("Timestamp", style="magenta")
    table.add_column("Plan ID", style="green")
    table.add_column("Label", style="blue")
    
    for s in history:
        ts = datetime.datetime.fromtimestamp(s['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        meta = json.loads(s['metadata'])
        label = meta.get('label', 'n/a')
        table.add_row(s['state_id'], ts, s['plan_id'] or "n/a", label)
        
    console.print(table)

def state_show_command(engine, state_id):
    state = engine.storage.get_state(state_id)
    if not state:
        console.print(f"[red]State {state_id} not found.[/red]")
        return
        
    console.print(f"[bold cyan]State: {state_id}[/bold cyan]")
    console.print(f"Parent: {state['parent_state_id'] or 'None'}")
    console.print(f"Plan: {state['plan_id'] or 'None'}")
    console.print(f"Time: {datetime.datetime.fromtimestamp(state['timestamp'])}")
    
    files = engine.storage.get_state_files(state_id)
    console.print(f"\n[bold]Tracked Files ({len(files)}):[/bold]")
    for f in files[:20]: # Show first 20
        console.print(f"  {f['path']} ([dim]{f['hash'][:8]}[/dim])")
    if len(files) > 20:
        console.print(f"  ... and {len(files) - 20} more.")

def state_diff_command(engine, id1, id2):
    diff = engine.get_diff(id1, id2)
    if not diff:
        console.print("[yellow]No changes found or invalid state IDs.[/yellow]")
        return
        
    table = Table(title=f"🔍 State Diff: {id1} ➔ {id2}")
    table.add_column("Type", style="bold")
    table.add_column("Path")
    table.add_column("Details", style="dim")
    
    for change in diff:
        ctype = change['type']
        color = "green" if ctype == "ADDED" else "yellow" if ctype == "MODIFIED" else "red"
        
        details = ""
        if ctype == "MODIFIED":
            details = f"{change['old_hash'][:8]} -> {change['new_hash'][:8]}"
            
        table.add_row(f"[{color}]{ctype}[/{color}]", change['path'], details)
        
    console.print(table)

def state_checkout_command(engine, state_id):
    console.print(f"[yellow]⚠️  Restoring system to state {state_id}...[/yellow]")
    try:
        engine.checkout(state_id)
        console.print(f"[green]✅ Successfully restored to {state_id}.[/green]")
    except Exception as e:
        console.print(f"[red]❌ Restore failed: {e}[/red]")
