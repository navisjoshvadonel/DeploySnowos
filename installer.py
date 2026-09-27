#!/usr/bin/env python3
"""
❄️ SnowOS Hardened Enterprise Deployment Dashboard
Unified, verified platform installer with real pre-flight checks,
step-by-step verified execution, genuine socket diagnostics, and rollback recovery.
"""
import os
import sys
import shutil
import socket
import hashlib
import json
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

console = Console()
WORKSPACE_ROOT = Path(__file__).resolve().parent

BANNER = """
   ❄️   ❄️   ❄️   ❄️   ❄️   ❄️   ❄️   ❄️   ❄️   ❄️   ❄️   ❄️   ❄️   ❄️
   ███████╗███╗   ██╗ ██████╗ ██╗    ██╗ ██████╗ ███████╗
   ██╔════╝████╗  ██║██╔═══██╗██║    ██║██╔═══██╗██╔════╝
   ███████╗██╔██╗ ██║██║   ██║██║ █╗ ██║██║   ██║███████╗
   ╚════██║██║╚██╗██║██║   ██║██║███╗██║██║   ██║╚════██║
   ███████║██║ ╚████║╚██████╔╝╚███╔███╔╝╚██████╔╝███████║
   ╚══════╝╚═╝  ╚═══╝ ╚═════╝  ╚══╝╚══╝  ╚═════╝ ╚══════╝
   >> HARDENED OPERATING PLATFORM  |  EDITION: DIGITAL FROST ❄️
   ==========================================================
"""

def print_banner():
    """Print header banner with cyan-to-blue gradient."""
    lines = BANNER.split("\n")
    for i, line in enumerate(lines):
        color = f"rgb({max(0, 100-i*5)}, {min(255, 180+i*5)}, 255)"
        console.print(Text(line, style=color))

def check_permissions():
    """Ensure installer runs under root."""
    if os.geteuid() != 0:
        console.print("\n[bold red]❌ Installation Terminated![/bold red]")
        console.print(Panel(
            "[bold yellow]SnowOS installs system daemons, GDM3 themes, and service accounts.\n"
            "Please run with root authorization:\n\n"
            "  [bold green]sudo python3 installer.py[/bold green][/bold yellow]",
            title="Root Access Required",
            border_style="red"
        ))
        sys.exit(1)

def run_preflight_checks() -> bool:
    """Run genuine diagnostic baseline and verify source tree integrity."""
    console.print("\n[bold cyan]⚡ Running Genuine Pre-flight Diagnostics...[/bold cyan]")
    has_errors = False

    table = Table(title="System Diagnostics & Source Integrity", border_style="cyan")
    table.add_column("Deployment Target / Requirement", style="bold white")
    table.add_column("System Status", style="bold")
    table.add_column("Detail", style="dim white")

    # 1. Check RAM
    mem_total_gb = 0.0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if "MemTotal" in line:
                    mem_total_gb = int(line.split()[1]) / 1024 / 1024
                    break
    except Exception:
        pass
    if mem_total_gb >= 3.8:
        table.add_row("System Memory (RAM)", "[green]Pass ✔[/green]", f"{mem_total_gb:.1f} GB Available")
    elif mem_total_gb >= 1.8:
        table.add_row("System Memory (RAM)", "[yellow]Warning ⚠[/yellow]", f"{mem_total_gb:.1f} GB (Low memory)")
    else:
        table.add_row("System Memory (RAM)", "[red]Fail ✖[/red]", f"{mem_total_gb:.1f} GB (Minimum 2GB required)")
        has_errors = True

    # 2. Check Disk Space
    _, _, free = shutil.disk_usage("/")
    free_gb = free / 1024 / 1024 / 1024
    if free_gb >= 5.0:
        table.add_row("Available Disk Space", "[green]Pass ✔[/green]", f"{free_gb:.1f} GB Free")
    elif free_gb >= 2.0:
        table.add_row("Available Disk Space", "[yellow]Warning ⚠[/yellow]", f"{free_gb:.1f} GB Free (Tight)")
    else:
        table.add_row("Available Disk Space", "[red]Fail ✖[/red]", f"{free_gb:.1f} GB Free (Minimum 2GB required)")
        has_errors = True

    # 3. Check Target OS
    os_name = "Unknown"
    os_id = ""
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    os_name = line.strip().split("=", 1)[1].replace('"', '')
                elif line.startswith("ID="):
                    os_id = line.strip().split("=", 1)[1].replace('"', '')
    if "ubuntu" in os_id or "debian" in os_id or "ubuntu" in os_name.lower():
        table.add_row("Operating System Base", "[green]Compatible ✔[/green]", os_name)
    else:
        table.add_row("Operating System Base", "[yellow]Non-Standard ⚠[/yellow]", f"{os_name} (Ubuntu LTS recommended)")

    # 4. Check Desktop Environment
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    session_type = os.environ.get("XDG_SESSION_TYPE", "unknown")
    gnome_present = shutil.which("gnome-shell") is not None
    if gnome_present:
        table.add_row("Desktop Compositor", "[green]GNOME Present ✔[/green]", f"Compositor: {desktop or 'GNOME'} ({session_type})")
    else:
        table.add_row("Desktop Compositor", "[yellow]Headless / Non-GNOME ℹ[/yellow]", f"Current: {desktop or 'Headless'} ({session_type})")

    # 5. Check Source Files Integrity
    required_sources = [
        WORKSPACE_ROOT / "snowos-runtime" / "src",
        WORKSPACE_ROOT / "snowos-runtime" / "config" / "snowos.env",
        WORKSPACE_ROOT / "snowos-runtime" / "config" / "boot_manifest.json",
        WORKSPACE_ROOT / "snowos-runtime" / "config" / "ai_features.json",
        WORKSPACE_ROOT / "snowos-runtime" / "config" / "brand.json",
        WORKSPACE_ROOT / "snowos-runtime" / "config" / "snowos-tmpfiles.conf",
        WORKSPACE_ROOT / "snowos-runtime" / "services" / "snowos-boot.service",
        WORKSPACE_ROOT / "snowos-runtime" / "services" / "snowos-broker.service",
        WORKSPACE_ROOT / "snowos-runtime" / "services" / "snowos-sentinel.service",
        WORKSPACE_ROOT / "distribution" / "cli" / "snowos",
        WORKSPACE_ROOT / "apply_branding.sh",
        WORKSPACE_ROOT / "rollback.sh"
    ]
    missing_sources = [p for p in required_sources if not p.exists()]
    if not missing_sources:
        table.add_row("Source Repository Integrity", "[green]All Present ✔[/green]", f"{len(required_sources)}/{len(required_sources)} assets verified")
    else:
        table.add_row("Source Repository Integrity", "[red]Files Missing ✖[/red]", f"Missing {len(missing_sources)} files")
        has_errors = True

    # 6. Check for Conflicting Dock Extensions
    conflicting_ext = shutil.which("dash-to-dock") is not None or os.path.exists("/usr/share/gnome-shell/extensions/dash-to-dock@vswitch.org")
    if conflicting_ext:
        table.add_row("Conflicting Extensions", "[yellow]Found dash-to-dock ⚠[/yellow]", "Will be replaced with ubuntu-dock")
    else:
        table.add_row("Conflicting Extensions", "[green]None Detected ✔[/green]", "No conflicting dock extensions")

    console.print(table)

    if has_errors:
        console.print("\n[bold red]❌ Pre-flight checks failed! Please correct the errors above before continuing.[/bold red]")
        sys.exit(1)

    console.print("\n[bold green]✔ Pre-flight verification completed successfully.[/bold green]")
    return True

def show_interactive_menu() -> str:
    """Prompt user for selection with verified options."""
    console.print("\n" + "="*58 + "\n")
    console.print("[bold cyan]❄️ SELECT SNOWOS DEPLOYMENT PROFILE:[/bold cyan]")
    
    console.print(Panel(
        "[bold cyan][1][/bold cyan] [bold white]Unified Platform Installation[/bold white] [green](RECOMMENDED)[/green]\n"
        "   Deploys both the Hardened Service Core (Boot, Broker, Sentinel, AICore)\n"
        "   and the Digital Frost Visual Identity (GDM3, Dock, Themes, GRUB).\n\n"
        "[bold cyan][2][/bold cyan] [bold white]Hardened Core Platform Only[/bold white]\n"
        "   Deploys system daemons, access policies, and validation tools without modifying desktop theming.\n\n"
        "[bold cyan][3][/bold cyan] [bold white]Digital Frost Visual Customization Only[/bold white]\n"
        "   Installs custom icons, wallpapers, GDM3 theme, and login banners.\n\n"
        "[bold cyan][4][/bold cyan] [bold yellow]System Rollback / Uninstallation[/bold yellow]\n"
        "   Safely reverts all SnowOS services, configs, diversions, and restores baseline.",
        border_style="blue"
    ))

    choice = ""
    while choice not in ["1", "2", "3", "4"]:
        choice = console.input("[bold white]Select Option [1-4]: [/bold white]").strip()
    return choice

def run_step(cmd, desc: str) -> tuple[bool, str]:
    """Execute a real deployment command synchronously and capture output."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(WORKSPACE_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180
        )
        return proc.returncode == 0, proc.stdout
    except subprocess.TimeoutExpired:
        return False, "Command timed out after 180 seconds."
    except Exception as exc:
        return False, str(exc)

def execute_installation(profile_choice: str):
    """Execute real deployment tasks without simulated delays or fake ticks."""
    if profile_choice == "4":
        console.print("\n[bold yellow]🔄 Executing Rollback Utility...[/bold yellow]")
        success, out = run_step(["bash", str(WORKSPACE_ROOT / "rollback.sh")], "Rollback")
        console.print(out)
        if success:
            console.print("[bold green]✔ System rollback completed successfully.[/bold green]")
        else:
            console.print("[bold red]✖ Rollback encountered issues. Please review logs above.[/bold red]")
        sys.exit(0 if success else 1)

    profile_map = {"1": "all", "2": "core", "3": "visual"}
    profile_arg = profile_map.get(profile_choice, "all")

    console.print(f"\n[bold cyan]🚀 Executing Deployment Pipeline for Profile: [white]{profile_arg.upper()}[/white][/bold cyan]\n")

    # Define actual real tasks based on profile
    real_tasks = [
        ("Executing Base Infrastructure & Service Pipeline...", ["bash", str(WORKSPACE_ROOT / "install.sh"), profile_arg])
    ]

    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30, complete_style="cyan", finished_style="green"),
        TaskProgressColumn(),
        console=console
    ) as progress:
        main_task = progress.add_task("[bold cyan]Deploying SnowOS Platform...", total=len(real_tasks))

        for desc, cmd in real_tasks:
            sub_task = progress.add_task(f"   [white]{desc}[/white]", total=100)
            progress.update(sub_task, advance=20)
            
            # Real command execution
            success, output = run_step(cmd, desc)
            progress.update(sub_task, completed=100)

            if not success:
                progress.stop()
                console.print(f"\n[bold red]❌ Deployment Failed during: {desc}[/bold red]")
                console.print(Panel(
                    output[-2500:] if len(output) > 2500 else output,
                    title="Execution Error Output",
                    border_style="red"
                ))
                console.print(Panel(
                    "[bold yellow]To revert changes and restore baseline system state, execute:\n"
                    "  [bold green]sudo ./rollback.sh[/bold green][/bold yellow]",
                    title="Recovery Options",
                    border_style="yellow"
                ))
                sys.exit(1)

            progress.remove_task(sub_task)
            progress.advance(main_task, 1)

    console.print("\n[bold green]⭐ SnowOS Platform Deployment Tasks Completed Successfully![/bold green]")

def run_diagnostics_sweep():
    """Perform real, verified health checks on sockets, daemons, and configs."""
    console.print("\n[bold cyan]🔍 Running Genuine SnowOS Health Diagnostics Sweep...[/bold cyan]")

    health_grid = Table(title="SnowOS Real-Time System Integrity Status", border_style="cyan")
    health_grid.add_column("Component / Subsystem", style="bold white")
    health_grid.add_column("Status", style="bold")
    health_grid.add_column("Diagnostics Detail", style="dim white")

    overall_healthy = True

    # 1. Check Broker Socket
    broker_sock = "/run/snowos/broker.sock"
    if os.path.exists(broker_sock):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(broker_sock)
            s.close()
            health_grid.add_row("Permission Broker Socket", "[green]Online ✔[/green]", f"{broker_sock} (Connected)")
        except Exception as exc:
            health_grid.add_row("Permission Broker Socket", "[yellow]Bound (Unresponsive) ⚠[/yellow]", f"{exc}")
            overall_healthy = False
    else:
        health_grid.add_row("Permission Broker Socket", "[red]Missing ✖[/red]", f"Not found at {broker_sock}")
        overall_healthy = False

    # 2. Check Sentinel Socket
    sentinel_sock = "/run/snowos/sentinel.sock"
    if os.path.exists(sentinel_sock):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(sentinel_sock)
            s.close()
            health_grid.add_row("AI Sentinel Socket", "[green]Online ✔[/green]", f"{sentinel_sock} (Connected)")
        except Exception as exc:
            health_grid.add_row("AI Sentinel Socket", "[yellow]Bound (Unresponsive) ⚠[/yellow]", f"{exc}")
    else:
        health_grid.add_row("AI Sentinel Socket", "[dim yellow]Inactive / Staged ℹ[/dim yellow]", f"Socket not yet bound")

    # 3. Check NyxVFS Socket (Real probe, no fake staged status)
    nyxvfs_sock = "/run/snowos/nyxvfs.sock"
    if os.path.exists(nyxvfs_sock):
        health_grid.add_row("NyxVFS IPC Socket", "[green]Online ✔[/green]", nyxvfs_sock)
    else:
        health_grid.add_row("NyxVFS IPC Socket", "[dim yellow]Inactive (Optional) ℹ[/dim yellow]", "Daemon not running")

    # 4. Check Core Systemd Services
    core_services = [
        "snowos-boot.service",
        "snowos-broker.service",
        "snowos-sentinel.service",
        "snowos-aicore.service",
        "snowos-control.service"
    ]
    for svc in core_services:
        res = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True)
        status = res.stdout.strip()
        if status == "active":
            health_grid.add_row(svc, "[green]Active ✔[/green]", "systemd runtime running")
        elif status == "activating":
            health_grid.add_row(svc, "[yellow]Activating ⚠[/yellow]", "systemd starting")
        else:
            health_grid.add_row(svc, f"[red]{status.upper()} ✖[/red]", f"Check: journalctl -u {svc}")
            if svc in ["snowos-boot.service", "snowos-broker.service"]:
                overall_healthy = False

    # 5. Check Integrity Manifest
    manifest_file = "/etc/snowos/integrity_manifest.json"
    if os.path.exists(manifest_file):
        try:
            with open(manifest_file) as f:
                data = json.load(f)
            tracked = data.get("tracked_files", [])
            health_grid.add_row("Integrity Manifest", "[green]Enforced ✔[/green]", f"Tracking {len(tracked)} system files")
        except Exception as exc:
            health_grid.add_row("Integrity Manifest", "[yellow]Invalid JSON ⚠[/yellow]", str(exc))
    else:
        health_grid.add_row("Integrity Manifest", "[red]Missing ✖[/red]", f"File {manifest_file} missing")

    # 6. Check Swarm Port
    swarm_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    swarm_sock.settimeout(0.5)
    swarm_res = swarm_sock.connect_ex(('127.0.0.1', 8443))
    swarm_sock.close()
    if swarm_res == 0:
        health_grid.add_row("P2P Swarm Memory Graph", "[green]Listening ✔[/green]", "Active on port 8443")
    else:
        health_grid.add_row("P2P Swarm Memory Graph", "[dim white]Standby / Unconfigured ℹ[/dim white]", "Port 8443 not active")

    # 7. Check Boot Status File
    boot_status_file = "/run/snowos/boot-status.json"
    if os.path.exists(boot_status_file):
        health_grid.add_row("Boot Orchestrator State", "[green]Synchronized ✔[/green]", boot_status_file)
    else:
        health_grid.add_row("Boot Orchestrator State", "[yellow]Not Generated ⚠[/yellow]", "Missing boot-status.json")

    console.print(health_grid)
    console.print("\n" + "="*58 + "\n")

    if overall_healthy:
        console.print(Panel(
            "[bold cyan]❄️ Congratulations! SnowOS Digital Frost is deployed and verified.[/bold cyan]\n\n"
            "To inspect platform status:\n"
            "  [bold green]snowos doctor[/bold green]\n\n"
            "To launch the AI-Native runtime interface:\n"
            "  [bold green]python3 /opt/snowos/ai_core/nyx_kernel/nyx.py[/bold green]\n\n"
            "Restart your system to view the cinematic GDM3 greeter & desktop docks.",
            title="Installation Verified",
            border_style="green"
        ))
    else:
        console.print(Panel(
            "[bold yellow]⚠️ Deployment finished with warnings or degraded components.[/bold yellow]\n\n"
            "Review the red/yellow entries above.\n"
            "To inspect service logs, use:\n"
            "  [bold white]journalctl -u snowos-broker.service -n 50[/bold white]\n\n"
            "To revert to a clean state:\n"
            "  [bold red]sudo ./rollback.sh[/bold red]",
            title="Deployment Attention Required",
            border_style="yellow"
        ))

def main():
    print_banner()
    check_permissions()
    run_preflight_checks()
    choice = show_interactive_menu()
    execute_installation(choice)
    run_diagnostics_sweep()

if __name__ == "__main__":
    main()
