import sqlite3
import json
import time

class DELStorage:
    def __init__(self, db_path="nyx_deterministic.db"):
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
            
            # Plans table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS plans (
                    plan_id TEXT PRIMARY KEY,
                    goal TEXT,
                    plan_json TEXT,
                    created_at REAL
                )
            ''')
            
            # Executions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id TEXT,
                    trace_id TEXT,
                    span_id TEXT,
                    command TEXT,
                    status TEXT,
                    stdout TEXT,
                    stderr TEXT,
                    exit_code INTEGER,
                    start_time REAL,
                    end_time REAL,
                    latency REAL,
                    FOREIGN KEY(plan_id) REFERENCES plans(plan_id)
                )
            ''')
            
            # Snapshots table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    plan_id TEXT,
                    path TEXT,
                    created_at REAL,
                    FOREIGN KEY(plan_id) REFERENCES plans(plan_id)
                )
            ''')
            
            conn.commit()

    def save_plan(self, plan_id, goal, plan_json):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO plans (plan_id, goal, plan_json, created_at) VALUES (?, ?, ?, ?)",
                (plan_id, goal, json.dumps(plan_json), time.time())
            )
            conn.commit()

    def save_execution(self, plan_id, trace_id, span_id, command, status, stdout, stderr, exit_code, start_time, end_time, latency):
        with self._get_connection() as conn:
            conn.execute(
                '''INSERT INTO executions 
                   (plan_id, trace_id, span_id, command, status, stdout, stderr, exit_code, start_time, end_time, latency) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (plan_id, trace_id, span_id, command, status, stdout, stderr, exit_code, start_time, end_time, latency)
            )
            conn.commit()

    def save_snapshot(self, snapshot_id, plan_id, path):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO snapshots (snapshot_id, plan_id, path, created_at) VALUES (?, ?, ?, ?)",
                (snapshot_id, plan_id, path, time.time())
            )
            conn.commit()

    def get_plan(self, plan_id):
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,)).fetchone()
            return dict(row) if row else None

    def get_executions(self, plan_id):
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM executions WHERE plan_id = ? ORDER BY id ASC", (plan_id,)).fetchall()
            return [dict(row) for row in rows]

    def get_snapshot(self, snapshot_id):
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)).fetchone()
            return dict(row) if row else None
            
    def get_history(self, limit=50, failed_only=False):
        with self._get_connection() as conn:
            query = "SELECT p.plan_id, p.goal, p.created_at, (SELECT status FROM executions WHERE plan_id = p.plan_id ORDER BY id DESC LIMIT 1) as last_status FROM plans p"
            if failed_only:
                query += " WHERE last_status = 'FAILED'"
            query += " ORDER BY p.created_at DESC LIMIT ?"
            rows = conn.execute(query, (limit,)).fetchall()
            return [dict(row) for row in rows]
