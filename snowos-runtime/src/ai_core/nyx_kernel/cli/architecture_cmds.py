import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

console = Console()

@click.group(name="architecture")
def architecture_group():
    """Self-Designing System Layer (SDSL)"""
    pass

@architecture_group.command(name="show")
def architecture_show():
    """Display the system architecture graph."""
    from nyx import NyxAI
    nyx = NyxAI(autonomous=False)
    
    snapshot = nyx.arch_profiler.graph.get_graph_snapshot()
    nodes = snapshot["nodes"]
    edges = snapshot["edges"]
    
    console.print(Panel("[bold cyan]📐 SnowOS Architecture Graph[/bold cyan]"))
    
    # Represent as a Tree for visualization
    tree = Tree("[bold magenta]SnowOS Core[/bold magenta]")
    for name, node in nodes.items():
        n_tree = tree.add(f"[cyan]{name}[/cyan] ({node['type']})")
        n_tree.add(f"Latency: {node['latency_contribution']:.3f}s")
        n_tree.add(f"CPU: {node['cpu_usage']:.1f}%")
        n_tree.add(f"Coupling: {node['coupling_level']:.2f}")
        
    console.print(tree)
    
    if edges:
        console.print("\n[bold yellow]Interactions:[/bold yellow]")
        for e in edges:
            console.print(f"  {e['source']} ➔ {e['target']} ([dim]{e['type']}[/dim]) | Latency: {e['avg_latency']:.3f}s")

@architecture_group.command(name="insights")
def architecture_insights():
    """List detected architectural findings."""
    from nyx import NyxAI
    nyx = NyxAI(autonomous=False)
    
    findings = nyx.design_analysis.generate_findings()
    if not findings:
        console.print("[green]✔ No architectural issues detected.[/green]")
        return
        
    table = Table(title="Architecture Design Insights")
    table.add_column("ID", style="dim")
    table.add_column("Component", style="cyan")
    table.add_column("Finding", style="yellow")
    table.add_column("Severity", style="bold red")
    table.add_column("Impact", style="magenta")
    
    for f in findings:
        sev_color = "red" if f["severity"] == "HIGH" else "yellow"
        table.add_row(
            f["id"],
            f["component"],
            f["finding"],
            f"[{sev_color}]{f['severity']}[/{sev_color}]",
            f"{f['impact_score']:.2f}"
        )
    
    console.print(table)

@architecture_group.command(name="proposals")
def architecture_proposals():
    """Show redesign and optimization suggestions."""
    from nyx import NyxAI
    nyx = NyxAI(autonomous=False)
    
    findings = nyx.design_analysis.generate_findings()
    proposals = nyx.refactor_engine.generate_proposals(findings)
    
    if not proposals:
        console.print("[yellow]No refactor proposals available.[/yellow]")
        return
        
    for p in proposals:
        console.print(Panel(
            f"[bold cyan]{p['type']}[/bold cyan]: {p['description']}\n"
            f"[green]Expected:[/green] {p['expected_improvement']}\n"
            f"[yellow]Risk:[/yellow] {p['risk_level']}",
            title=f"Proposal {p['id']}",
            border_style="blue"
        ))

@architecture_group.command(name="simulate")
@click.argument("proposal_id")
def architecture_simulate(proposal_id):
    """Run impact simulation for a proposal."""
    from nyx import NyxAI
    nyx = NyxAI(autonomous=False)
    
    findings = nyx.design_analysis.generate_findings()
    proposals = nyx.refactor_engine.generate_proposals(findings)
    prop = next((p for p in proposals if p["id"] == proposal_id), None)
    
    if not prop:
        console.print(f"[red]❌ Proposal {proposal_id} not found.[/red]")
        return
        
    result = nyx.arch_simulator.simulate_proposal(prop)
    
    table = Table(title=f"Simulation Results: {proposal_id}")
    table.add_column("Metric", style="cyan")
    table.add_column("Baseline", style="dim")
    table.add_column("Predicted", style="green")
    table.add_column("Change", style="bold")
    
    b = result["baseline"]
    p = result["predicted"]
    
    for k in b:
        diff = ((p[k] - b[k]) / b[k] * 100) if b[k] > 0 else 0
        diff_color = "green" if diff < 0 else "red" # Lower is better for these metrics
        table.add_row(
            k.capitalize(),
            f"{b[k]:.3f}",
            f"{p[k]:.3f}",
            f"[{diff_color}]{diff:+.1f}%[/{diff_color}]"
        )
        
    console.print(table)
    console.print(f"\n[bold]Improvement Score:[/bold] {result['improvement_score']:.2f}")
    status = "[green]SAFE[/green]" if result["is_safe"] else "[red]UNSAFE[/red]"
    console.print(f"[bold]Safety Check:[/bold] {status}")

@architecture_group.command(name="apply")
@click.argument("proposal_id")
def architecture_apply(proposal_id):
    """Apply an approved architectural improvement."""
    from nyx import NyxAI
    nyx = NyxAI(autonomous=False)
    
    if not Confirm.ask(f"Apply architecture change {proposal_id}?"):
        return
        
    findings = nyx.design_analysis.generate_findings()
    proposals = nyx.refactor_engine.generate_proposals(findings)
    prop = next((p for p in proposals if p["id"] == proposal_id), None)
    
    if not prop:
        console.print(f"[red]❌ Proposal {proposal_id} not found.[/red]")
        return
        
    sim = nyx.arch_simulator.simulate_proposal(prop)
    success = nyx.arch_modifier.apply_proposal(prop, sim)
    
    if success:
        console.print(f"[bold green]✔ Architecture successfully upgraded. Versioning tracked.[/bold green]")
    else:
        console.print(f"[red]❌ Upgrade failed or was rejected by safety checks.[/red]")
