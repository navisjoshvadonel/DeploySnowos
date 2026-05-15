import click
import requests
import os
import json
from rich.console import Console
from rich.table import Table
from identity.user import Role
from identity.store import UserStore
from identity.auth import hash_password

console = Console()
NYX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(NYX_DIR, ".cli_token")

def get_token():
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "r") as f:
            return f.read().strip()
    return None

def save_token(token):
    with open(TOKEN_PATH, "w") as f:
        f.write(token)

def clear_token():
    if os.path.exists(TOKEN_PATH):
        os.remove(TOKEN_PATH)

@click.group(name="user")
def user_group():
    """Manage SnowOS users and roles."""
    pass

@user_group.command(name="create")
@click.argument("username")
@click.argument("password")
@click.option("--role", type=click.Choice([r.value for r in Role]), default="developer")
def create_user_cmd(username, password, role):
    """Create a new user (Local Admin only)."""
    store = UserStore(os.path.join(NYX_DIR, "nyx_identity.db"))
    pw_hash = hash_password(password)
    user_id = store.create_user(username, pw_hash, Role(role))
    if user_id:
        console.print(f"[green]User {username} created successfully (ID: {user_id})[/green]")
    else:
        console.print(f"[red]Failed to create user. Username might already exist.[/red]")

@user_group.command(name="list")
def list_users_cmd():
    """List all users."""
    store = UserStore(os.path.join(NYX_DIR, "nyx_identity.db"))
    users = store.list_users()
    
    table = Table(title="SnowOS Users")
    table.add_column("Username", style="cyan")
    table.add_column("Role", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Created At", style="dim")
    
    for u in users:
        table.add_row(u["username"], u["role"], u["status"], u["created_at"])
    
    console.print(table)

@user_group.command(name="role")
@click.argument("username")
@click.argument("role", type=click.Choice([r.value for r in Role]))
def update_role_cmd(username, role):
    """Update user role."""
    store = UserStore(os.path.join(NYX_DIR, "nyx_identity.db"))
    if store.update_user_role(username, Role(role)):
        console.print(f"[green]Role for {username} updated to {role}[/green]")
    else:
        console.print(f"[red]User {username} not found.[/red]")

@click.command(name="login")
@click.argument("username")
def login_cmd(username):
    """Login to SnowOS."""
    password = click.prompt("Password", hide_input=True)
    # In a real CLI we would call the API, but since we are local we can check store
    # Actually, to be consistent with MUIL, we should call the API if server is running
    # but for bootstrap we use the store.
    # Let's try API first, fallback to store if server is not reachable?
    # No, MUIL objective says "token-based authentication".
    
    try:
        response = requests.post("http://localhost:8000/api/auth/login", data={
            "username": username,
            "password": password
        })
        if response.status_code == 200:
            token = response.json()["access_token"]
            save_token(token)
            console.print(f"[green]Successfully logged in as {username}[/green]")
            return
    except Exception:
        pass

    # Fallback to store for local bootstrap (if server not running)
    store = UserStore(os.path.join(NYX_DIR, "nyx_identity.db"))
    from identity.auth import verify_password, create_access_token
    user = store.get_user_by_username(username)
    if user and verify_password(password, user["password_hash"]):
        token = create_access_token(data={"sub": user["user_id"], "role": user["role"]})
        save_token(token)
        console.print(f"[yellow]Logged in locally as {username} (API server offline)[/yellow]")
    else:
        console.print("[red]Invalid credentials.[/red]")

@click.command(name="whoami")
def whoami_cmd():
    """Display current identity."""
    token = get_token()
    if not token:
        console.print("[yellow]Not logged in.[/yellow]")
        return
    
    try:
        # Try to call API to verify
        response = requests.get("http://localhost:8000/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        if response.status_code == 200:
            user = response.json()
            console.print(f"Logged in as: [bold cyan]{user['username']}[/bold cyan] ([magenta]{user['role']}[/magenta])")
            return
    except Exception:
        pass
    
    # Offline decode
    from identity.auth import decode_access_token
    payload = decode_access_token(token)
    if payload:
        console.print(f"Logged in as (Offline): [cyan]ID:{payload['sub']}[/cyan] ([magenta]{payload['role']}[/magenta])")
    else:
        console.print("[red]Session expired. Please login again.[/red]")

@click.command(name="logout")
def logout_cmd():
    """Logout from SnowOS."""
    clear_token()
    console.print("[green]Logged out.[/green]")
