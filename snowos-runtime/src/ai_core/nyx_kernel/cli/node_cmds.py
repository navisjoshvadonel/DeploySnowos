import click
import requests
import json
from rich.console import Console
from rich.table import Table

console = Console()

@click.group(name="node")
def node_group():
    """Distributed Node & Trust Management (DITL)"""
    pass

@node_group.command(name="add")
@click.argument("url")
def node_add(url):
    """Register a new remote node via URL."""
    try:
        # 1. Fetch node info (node_id, public_key) from the remote node
        # In DITL, nodes have a /api/node/info endpoint
        info_url = url.rstrip("/") + "/api/node/info"
        res = requests.get(info_url, timeout=5)
        if res.status_code != 200:
            console.print(f"[red]❌ Failed to fetch node info from {url}: {res.status_code}[/red]")
            return
            
        data = res.json()
        node_id = data.get("node_id")
        pub_key = data.get("public_key")
        
        if not node_id or not pub_key:
            console.print("[red]❌ Invalid node info received.[/red]")
            return
            
        # 2. Add to local store
        from nyx import NyxAI
        nyx = NyxAI(autonomous=False)
        nyx.node_manager.add_node(node_id, url, pub_key)
        
        console.print(f"[green]✔ Node {node_id} added successfully.[/green]")
        console.print(f"[yellow]Note: Node is currently UNTRUSTED. Use 'nyx node trust {node_id}' to enable execution.[/yellow]")
        
    except Exception as e:
        console.print(f"[red]❌ Error adding node: {e}[/red]")

@node_group.command(name="trust")
@click.argument("node_id")
def node_trust(node_id):
    """Explicitly trust a known node."""
    from nyx import NyxAI
    nyx = NyxAI(autonomous=False)
    if nyx.node_manager.trust.trust_node(node_id):
        console.print(f"[green]✔ Node {node_id} is now TRUSTED.[/green]")
    else:
        console.print(f"[red]❌ Node {node_id} not found.[/red]")

@node_group.command(name="list")
def node_list():
    """List all registered nodes and their trust status."""
    from nyx import NyxAI
    nyx = NyxAI(autonomous=False)
    nodes = nyx.node_manager.get_nodes()
    
    if not nodes:
        console.print("[yellow]No nodes registered.[/yellow]")
        return
        
    table = Table(title="SnowOS Trusted Swarm")
    table.add_column("Node ID", style="cyan")
    table.add_column("URL", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Last Seen", style="dim")
    
    for n in nodes:
        status_color = "green" if n["trust_status"] == "trusted" else "yellow"
        table.add_row(
            n["node_id"][:12] + "...",
            n["url"],
            f"[{status_color}]{n['trust_status']}[/{status_color}]",
            n["last_seen"] or "never"
        )
    
    console.print(table)

@node_group.command(name="remove")
@click.argument("node_id")
def node_remove(node_id):
    """Remove a node from the swarm."""
    from nyx import NyxAI
    nyx = NyxAI(autonomous=False)
    nyx.node_manager.store.remove_node(node_id)
    console.print(f"[green]✔ Node {node_id} removed.[/green]")
