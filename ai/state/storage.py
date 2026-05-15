import sqlite3
import json
import time
import os

class StateStorage:
    def __init__(self, db_path="nyx_state.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # States table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS states (
                    state_id TEXT PRIMARY KEY,
                    parent_state_id TEXT,
                    plan_id TEXT,
                    user_id TEXT,
                    timestamp REAL,
                    metadata TEXT
                )
            ''')
            
            # State files table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS state_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    state_id TEXT,
                    path TEXT,
                    hash TEXT,
                    size INTEGER,
                    modified_time REAL,
                    FOREIGN KEY(state_id) REFERENCES states(state_id)
                )
            ''')
            
            # State diffs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS state_diffs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_state TEXT,
                    to_state TEXT,
                    diff_json TEXT
                )
            ''')
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_state_parent ON states(parent_state_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_state ON state_files(state_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_diff_states ON state_diffs(from_state, to_state);")
            
            conn.commit()

    def save_state(self, state_id, parent_state_id, plan_id, metadata, files, user_id=None):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO states (state_id, parent_state_id, plan_id, user_id, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (state_id, parent_state_id, plan_id, user_id, time.time(), json.dumps(metadata))
            )
            
            for f in files:
                conn.execute(
                    "INSERT INTO state_files (state_id, path, hash, size, modified_time) VALUES (?, ?, ?, ?, ?)",
                    (state_id, f['path'], f['hash'], f['size'], f['modified_time'])
                )
            conn.commit()

    def save_diff(self, from_state, to_state, diff_data):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO state_diffs (from_state, to_state, diff_json) VALUES (?, ?, ?)",
                (from_state, to_state, json.dumps(diff_data))
            )
            conn.commit()

    def get_state(self, state_id):
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM states WHERE state_id = ?", (state_id,)).fetchone()
            if row:
                state = dict(row)
                state['metadata'] = json.loads(state['metadata'])
                return state
            return None

    def get_state_files(self, state_id):
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM state_files WHERE state_id = ?", (state_id,)).fetchall()
            return [dict(row) for row in rows]

    def get_history(self, limit=50):
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM states ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
            return [dict(row) for row in rows]

    def get_latest_state(self):
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM states ORDER BY timestamp DESC LIMIT 1").fetchone()
            if row:
                return dict(row)
            return None

    def get_diff(self, from_state, to_state):
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT diff_json FROM state_diffs WHERE from_state = ? AND to_state = ?",
                (from_state, to_state)
            ).fetchone()
            if row:
                return json.loads(row['diff_json'])
            return None
