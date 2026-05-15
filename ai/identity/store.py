import sqlite3
import json
import os
from uuid import UUID
from datetime import datetime
from .user import User, Role

class UserStore:
    def __init__(self, db_path="nyx_identity.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    public_key TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            ''')
            conn.commit()

    def create_user(self, username, password_hash, role: Role, public_key: str = None):
        import uuid
        user_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        with self._get_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO users (user_id, username, password_hash, role, public_key, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, username, password_hash, role.value, public_key, created_at)
                )
                conn.commit()
                return user_id
            except sqlite3.IntegrityError:
                return None

    def get_user_by_username(self, username):
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id):
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def list_users(self):
        with self._get_connection() as conn:
            rows = conn.execute("SELECT user_id, username, role, status, created_at FROM users").fetchall()
            return [dict(row) for row in rows]

    def update_user_role(self, username, role: Role):
        with self._get_connection() as conn:
            cursor = conn.execute("UPDATE users SET role = ? WHERE username = ?", (role.value, username))
            conn.commit()
            return cursor.rowcount > 0
