import os
import subprocess
import time
import webbrowser
from rich.console import Console

console = Console()

def dashboard_command():
    """Start the SnowOS ANIL dashboard."""
    backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "interface", "backend", "server.py")
    
    console.print("[bold blue]🚀 Starting SnowOS AI-Native Interface Layer (ANIL)...[/bold blue]")
    
    # Check dependencies
    try:
        import fastapi
        import uvicorn
    except ImportError:
        console.print("[yellow]Installing dashboard dependencies (fastapi, uvicorn)...[/yellow]")
        subprocess.check_call([os.sys.executable, "-m", "pip", "install", "fastapi", "uvicorn", "python-multipart"])

    # Start backend in background
    # We use a detached process
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    proc = subprocess.Popen(
        [os.sys.executable, backend_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        start_new_session=True
    )
    
    console.print(f"[green]✅ Dashboard backend started (PID: {proc.pid})[/green]")
    console.print("[dim]Access the interface at: http://localhost:8000[/dim]")
    
    # Give it a second to start
    time.sleep(2)
    
    # Open browser
    try:
        webbrowser.open("http://localhost:8000")
        console.print("[blue]🌍 Opening dashboard in your browser...[/blue]")
    except Exception:
        console.print("[yellow]⚠️  Could not open browser automatically. Please visit http://localhost:8000 manually.[/yellow]")

    console.print("\n[bold]Press Ctrl+C to stop the dashboard server.[/bold]")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping dashboard...[/yellow]")
        proc.terminate()
        proc.wait()
        console.print("[dim]Dashboard stopped.[/dim]")
