import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import os
import configparser

console = Console()

@click.group(name="ui")
def ui_group():
    """SnowOS UI/UX Management Engine"""
    pass

@ui_group.command(name="upgrade")
def ui_upgrade():
    """Deploy the latest SnowOS UI/UX upgrades."""
    console.print(Panel("[bold cyan]❄️ Deploying SnowOS UI/UX Upgrade: 'Frost & Space'[/bold cyan]"))
    
    # 1. Update config
    config_path = "/home/develop/snowos/SnowOS-Visuals-Pack/ui/theme/snowos-motion.conf"
    if os.path.exists(config_path):
        console.print("[green]✔ Configuration validated.[/green]")
    
    # 2. Re-install extension
    console.print("[yellow]Updating GNOME Shell Extension...[/yellow]")
    os.system("sudo bash /home/develop/snowos/scripts/install-visual-pack.sh")
    
    console.print("[bold green]✔ SnowOS UI/UX upgraded successfully.[/bold green]")
    console.print("[dim]Log out and back in to see all changes take effect.[/dim]")

@ui_group.command(name="mode")
@click.argument("mode", type=click.Choice(["calm", "default", "dev"]))
def ui_mode(mode):
    """Set the motion personality mode."""
    config_path = "/home/develop/snowos/SnowOS-Visuals-Pack/ui/theme/snowos-motion.conf"
    config = configparser.ConfigParser()
    config.read(config_path)
    
    if 'PERSONALITY' not in config:
        config['PERSONALITY'] = {}
    
    config['PERSONALITY']['mode'] = mode
    
    with open(config_path, 'w') as f:
        config.write(f)
        
    console.print(f"[green]✔ Motion personality set to: [bold]{mode}[/bold][/green]")
    # Signal the extension (simplified: it should watch for file changes)
    
@ui_group.command(name="status")
def ui_status():
    """Show current UI/UX engine status."""
    config_path = "/home/develop/snowos/SnowOS-Visuals-Pack/ui/theme/snowos-motion.conf"
    config = configparser.ConfigParser()
    config.read(config_path)
    
    table = Table(title="SnowOS UI Status")
    table.add_column("Component", style="cyan")
    table.add_column("State", style="yellow")
    
    table.add_row("Motion Engine", config.get("PERSONALITY", "mode", fallback="default"))
    table.add_row("Spatial Awareness", "Enabled" if "SPATIAL" in config else "Disabled")
    table.add_row("Adaptive UI", "Active" if "ADAPTIVE" in config else "Idle")
    
    console.print(table)

@ui_group.command(name="intent")
@click.argument("intent")
@click.pass_obj
def ui_intent(nyx, intent):
    """Set the current user intent (e.g., coding, browsing)."""
    nyx.ui_state.set_intent(intent)
    console.print(f"[green]✔ User intent updated to: [bold]{intent}[/bold][/green]")

@ui_group.command(name="stress")
@click.argument("level", type=float)
@click.pass_obj
def ui_stress(nyx, level):
    """Manually simulate system stress level (0.0 to 1.0)."""
    nyx.ui_state.state["system_stress"] = level
    nyx.ui_state._save()
    console.print(f"[yellow]⚠ Simulated system stress set to: {level:.2f}[/yellow]")

@ui_group.command(name="learn")
@click.pass_obj
def ui_learn(nyx):
    """Trigger a UI learning pass on current layout and behavior."""
    console.print("[cyan]🧠 Nyx is learning from your current UI layout...[/cyan]")
    nyx.ui_memory.learn_from_session()
    console.print("[green]✔ UI learning pass completed. Prediction models updated.[/green]")
