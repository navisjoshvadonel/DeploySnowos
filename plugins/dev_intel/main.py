import os
import json
import re
from rich.panel import Panel
from rich.markdown import Markdown

def init(nyx):
    # Register hooks
    nyx.internal_commands[r"^nyx dev find \"(.+)\"$"] = lambda m: dev_find(nyx, m.group(1))
    nyx.internal_commands[r"^nyx dev explain \"(.+)\"$"] = lambda m: dev_explain(nyx, m.group(1))
    nyx.internal_commands[r"^nyx dev create \"(.+)\"$"] = lambda m: dev_create(nyx, m.group(1))
    nyx.internal_commands[r"^nyx dev debug \"(.+)\"$"] = lambda m: dev_debug(nyx, m.group(1))
    nyx.internal_commands[r"^nyx dev optimize$"] = lambda m: dev_optimize(nyx)

def dev_find(nyx, query):
    from rich.console import Console
    console = Console()
    console.print(f"[cyan]🔍 Searching codebase for: {query}[/cyan]")
    results = nyx.knowledge.search(query, top_k=5)
    if not results:
        console.print("[yellow]No relevant code found.[/yellow]")
        return
    
    for r in results:
        content = r.get('content', '')
        snippet = content[:300] + "..." if len(content) > 300 else content
        console.print(Panel(
            f"[bold]{r['file']}[/bold] (score: {r['score']:.2f})\n\n{snippet}",
            title="Relevant Snippet"
        ))

def dev_explain(nyx, filename):
    from rich.console import Console
    console = Console()
    path = os.path.join(nyx.state.cwd, filename)
    if not os.path.exists(path):
        console.print(f"[red]File not found: {filename}[/red]")
        return
    
    with open(path) as f:
        content = f.read()
    
    console.print(f"[cyan]🧠 Explaining {filename}...[/cyan]")
    prompt = f"Explain the following code in a structured way for a developer:\n\n```python\n{content}\n```"
    explanation = nyx._llm(prompt)
    if explanation:
        console.print(Panel(Markdown(explanation), title=f"Logic Breakdown: {filename}"))
    else:
        console.print("[red]❌ Failed to generate explanation.[/red]")

def dev_create(nyx, objective):
    from rich.console import Console
    console = Console()
    console.print(f"[cyan]🛠 Creating: {objective}[/cyan]")
    # Use GoalEngine to decompose and execute
    nyx.process(f"nyx goal \"{objective}\"")

def dev_debug(nyx, error_msg):
    from rich.console import Console
    console = Console()
    console.print(f"[cyan]🕵️ Debugging: {error_msg}[/cyan]")
    
    # Analyze EMG for recent failures
    failures = [n for n in nyx.emg.graph["nodes"] if n.get("type") == "failure"]
    failure_context = ""
    if failures:
        last = failures[-1]
        failure_context = f"Last failure: {last.get('id')} - {last.get('data')}"
    
    prompt = (
        "You are a Senior Debugging Agent. Analyze this error and system context to provide a root cause and fix.\n"
        f"Error: {error_msg}\n"
        f"System Context: {failure_context}"
    )
    analysis = nyx._llm(prompt)
    if analysis:
        console.print(Panel(Markdown(analysis), title="Debug Report"))
    else:
        console.print("[red]❌ Failed to generate debug report.[/red]")

def dev_optimize(nyx):
    from rich.console import Console
    console = Console()
    console.print("[cyan]📈 Analyzing project for optimizations...[/cyan]")
    # Use Reflection insights
    insights = nyx.reflection.insights
    if not insights:
        console.print("[yellow]No optimization insights available yet. Run 'nyx reflect now' to generate.[/yellow]")
        return
    
    for ins in insights:
        if ins.get("type") == "optimization":
            console.print(Panel(ins["message"], title=f"Insight {ins['id']}"))
