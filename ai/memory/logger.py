import sqlite3
import os
import json
from datetime import datetime

class MemoryLogger:
    """Handles persistent logging of Nyx command execution to SQLite."""
    
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.expanduser("~/.snowos/nyx/memory/memory.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                command TEXT,
                action TEXT,
                status TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def log_event(self, command, action, status):
        """Log a command execution event."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            timestamp = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO command_history (timestamp, command, action, status)
                VALUES (?, ?, ?, ?)
            ''', (timestamp, command, action, status))
            conn.commit()
            conn.close()
        except Exception as e:
            # Silent fail for logger to ensure no blocking
            pass

    def get_recent_history(self, limit=50):
        """Retrieve recent command history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, command, action, status 
                FROM command_history 
                ORDER BY id DESC 
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception:
            return []
