import datetime
from rich.console import Console
from rich.table import Table
from kernel.monitor import KernelMonitor

console = Console()

def kernel_status_command():
    """Display real-time kernel metrics."""
    cpu = KernelMonitor.get_cpu_stats()
    mem = KernelMonitor.get_mem_info()
    net = KernelMonitor.get_net_dev()
    freqs = KernelMonitor.get_cpu_freq()

    table = Table(title="🐧 SnowOS Kernel Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")

    if cpu:
        table.add_row("Global CPU Idle", f"{cpu['idle']}")
        table.add_row("Global CPU Total", f"{cpu['total']}")
    
    if freqs:
        avg_freq = sum(freqs) / len(freqs)
        table.add_row("Avg CPU Freq", f"{avg_freq/1000:.2f} MHz")

    if mem:
        table.add_row("Mem Total", f"{mem['total']/1024:.2f} MB")
        table.add_row("Mem Available", f"{mem['available']/1024:.2f} MB")
        table.add_row("Mem Free", f"{mem['free']/1024:.2f} MB")

    if net:
        for iface, stats in net.items():
            if stats['rx_bytes'] > 0:
                table.add_row(f"Net {iface} RX", f"{stats['rx_bytes']/1024/1024:.2f} MB")
                table.add_row(f"Net {iface} TX", f"{stats['tx_bytes']/1024/1024:.2f} MB")

    console.print(table)

def processes_command(intelligence):
    """List tracked processes with real-time metrics."""
    intelligence.scan()
    table = Table(title="📑 Tracked Processes (Kernel Aware)")
    table.add_column("PID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Memory (RSS)", style="green")
    table.add_column("FDs", style="yellow")
    table.add_column("Threads", style="blue")

    # Sort by memory usage (crude)
    sorted_procs = sorted(intelligence.registry.values(), key=lambda x: x['memory_rss'], reverse=True)
    
    for p in sorted_procs[:20]: # Show top 20
        table.add_row(
            p['pid'],
            p['name'],
            p['memory_rss'],
            str(p['fds']),
            p['threads']
        )
    
    console.print(table)

def kernel_events_command(storage):
    """Show recent kernel-level events from storage."""
    with storage._get_connection() as conn:
        cursor = conn.execute("SELECT * FROM kernel_events ORDER BY timestamp DESC LIMIT 20")
        events = cursor.fetchall()

    if not events:
        console.print("[yellow]No kernel events recorded yet.[/yellow]")
        return

    table = Table(title="🚨 Recent Kernel Events")
    table.add_column("ID", style="dim")
    table.add_column("Type", style="bold red")
    table.add_column("Description")
    table.add_column("Time", style="magenta")

    for e in events:
        ts = datetime.datetime.fromtimestamp(e['timestamp']).strftime('%H:%M:%S')
        table.add_row(e['id'], e['type'], e['description'], ts)

    console.print(table)
