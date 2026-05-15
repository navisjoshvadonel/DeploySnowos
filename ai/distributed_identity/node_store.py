import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

class NodeStore:
    """Handles persistence of known nodes and their trust status."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    public_key TEXT NOT NULL,
                    trust_status TEXT DEFAULT 'untrusted',
                    last_seen TEXT,
                    cpu_capacity INTEGER,
                    mem_capacity INTEGER,
                    current_load REAL,
                    avg_latency REAL,
                    success_rate REAL,
                    tags TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS swarm_cache (
                    task_hash TEXT PRIMARY KEY,
                    result TEXT,
                    expires REAL,
                    user_id TEXT,
                    node_id TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS architecture_states (
                    version_id TEXT PRIMARY KEY,
                    snapshot TEXT,
                    change_id TEXT,
                    timestamp REAL,
                    performance_metrics TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS architecture_proposals (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    impact_score REAL,
                    risk_level TEXT,
                    affected_modules TEXT,
                    simulation_data TEXT,
                    timestamp REAL
                )
            ''')
            conn.commit()

    def add_node(self, node_id: str, url: str, public_key: str):
        """Add or update a node."""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO nodes (node_id, url, public_key, last_seen)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    url=excluded.url,
                    public_key=excluded.public_key,
                    last_seen=excluded.last_seen
            ''', (node_id, url, public_key, datetime.now().isoformat()))
            conn.commit()

    def set_trust(self, node_id: str, status: str):
        """Update trust status (trusted/untrusted/blocked)."""
        with self._get_connection() as conn:
            conn.execute("UPDATE nodes SET trust_status = ? WHERE node_id = ?", (status, node_id))
            conn.commit()

    def get_node(self, node_id: str) -> Optional[Dict]:
        """Retrieve node info by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone()
            return dict(row) if row else None

    def get_node_by_url(self, url: str) -> Optional[Dict]:
        """Retrieve node info by URL."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM nodes WHERE url = ?", (url,)).fetchone()
            return dict(row) if row else None

    def list_nodes(self) -> List[Dict]:
        """List all known nodes."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM nodes").fetchall()
            return [dict(row) for row in rows]

    def remove_node(self, node_id: str):
        """Remove a node from the store."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM nodes WHERE node_id = ?", (node_id,))
            conn.commit()
