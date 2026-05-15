import sqlite3
import json
import time
import os

class Storage:
    def __init__(self, db_path="nyx_observability.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        # Enable thread-safety and WAL mode
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Logs table (simplified)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    event TEXT,
                    user_id TEXT,
                    role TEXT,
                    origin_node_id TEXT,
                    exec_node_id TEXT,
                    data TEXT
                )
            ''')
            
            # Unified Spans table for distributed tracing
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS spans (
                    span_id TEXT PRIMARY KEY,
                    trace_id TEXT,
                    parent_id TEXT,
                    user_id TEXT,
                    role TEXT,
                    origin_node_id TEXT,
                    exec_node_id TEXT,
                    name TEXT,
                    type TEXT,
                    start_time REAL,
                    end_time REAL,
                    status TEXT,
                    metadata TEXT
                )
            ''')
            
            # Optimization: Indexes for fast lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trace_id ON spans(trace_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_parent_id ON spans(parent_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON spans(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_start_time ON spans(start_time);")
            
            # Metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    value REAL,
                    status TEXT,
                    user_id TEXT,
                    role TEXT,
                    timestamp REAL,
                    metadata TEXT
                )
            ''')
            
            # Scheduling Events table (Stage 33)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scheduling_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    plan_id TEXT,
                    user_id TEXT,
                    role TEXT,
                    priority INTEGER,
                    enqueue_time REAL,
                    start_time REAL,
                    end_time REAL,
                    wait_time REAL,
                    execution_time REAL,
                    status TEXT
                )
            ''')
            
            # Capability Events table (Stage 34 — CBSM audit trail)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS capability_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    plan_id TEXT,
                    user_id TEXT,
                    role TEXT,
                    command TEXT,
                    required_capability TEXT,
                    granted INTEGER,
                    timestamp REAL,
                    reason TEXT
                )
            ''')
            # Stage 37: Kernel Interaction Layer
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS kernel_events (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    pid INTEGER,
                    description TEXT,
                    timestamp REAL,
                    metadata TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS process_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pid INTEGER,
                    name TEXT,
                    cpu_utime INTEGER,
                    cpu_stime INTEGER,
                    memory_rss TEXT,
                    fds INTEGER,
                    timestamp REAL
                )
            ''')
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kevent_type ON kernel_events(type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pmetrics_pid ON process_metrics(pid);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pmetrics_time ON process_metrics(timestamp);")
            
            conn.commit()

    def save_log(self, event, data, user_id=None, role=None, origin_node_id=None, exec_node_id=None):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO logs (timestamp, event, user_id, role, origin_node_id, exec_node_id, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (time.time(), event, user_id, role, origin_node_id, exec_node_id, json.dumps(data))
            )
            conn.commit()

    def save_span(self, span_id, trace_id, parent_id, name, type, start_time, status="RUNNING", metadata=None, user_id=None, role=None, origin_node_id=None, exec_node_id=None):
        with self._get_connection() as conn:
            conn.execute(
                '''INSERT OR REPLACE INTO spans 
                   (span_id, trace_id, parent_id, user_id, role, origin_node_id, exec_node_id, name, type, start_time, status, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (span_id, trace_id, parent_id, user_id, role, origin_node_id, exec_node_id, name, type, start_time, status, json.dumps(metadata or {}))
            )
            conn.commit()

    def update_span_end(self, span_id, end_time, status, metadata=None):
        with self._get_connection() as conn:
            if metadata:
                conn.execute(
                    "UPDATE spans SET end_time = ?, status = ?, metadata = ? WHERE span_id = ?",
                    (end_time, status, json.dumps(metadata), span_id)
                )
            else:
                conn.execute(
                    "UPDATE spans SET end_time = ?, status = ? WHERE span_id = ?",
                    (end_time, status, span_id)
                )
            conn.commit()

    def save_metric(self, name, value, status, metadata=None, user_id=None, role=None):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO metrics (name, value, status, user_id, role, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, value, status, user_id, role, time.time(), json.dumps(metadata or {}))
            )
            conn.commit()

    def get_trace(self, trace_id):
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time ASC", (trace_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_all_metrics(self, name=None):
        with self._get_connection() as conn:
            if name:
                cursor = conn.execute("SELECT * FROM metrics WHERE name = ? ORDER BY timestamp DESC", (name,))
            else:
                cursor = conn.execute("SELECT * FROM metrics ORDER BY timestamp DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_spans(self, limit=100):
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM spans ORDER BY start_time DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # Stage 33: Scheduling
    def save_scheduling_event(self, task_id, plan_id, priority, enqueue_time, status, user_id=None, role=None):
        with self._get_connection() as conn:
            conn.execute(
                '''INSERT INTO scheduling_events (task_id, plan_id, user_id, role, priority, enqueue_time, status) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (task_id, plan_id, user_id, role, priority, enqueue_time, status)
            )
            conn.commit()

    def update_scheduling_event(self, task_id, **kwargs):
        if not kwargs:
            return
        
        with self._get_connection() as conn:
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            params = list(kwargs.values()) + [task_id]
            conn.execute(
                f"UPDATE scheduling_events SET {set_clause} WHERE task_id = ?",
                params
            )
            conn.commit()

    # Stage 34: Capability-Based Security
    def save_capability_event(self, task_id, plan_id, command, required_capability, granted, reason="", user_id=None, role=None):
        with self._get_connection() as conn:
            conn.execute(
                '''INSERT INTO capability_events 
                   (task_id, plan_id, user_id, role, command, required_capability, granted, timestamp, reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (task_id, plan_id, user_id, role, command, required_capability, 1 if granted else 0, time.time(), reason)
            )
            conn.commit()

    def get_capability_violations(self, limit=50):
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM capability_events WHERE granted = 0 ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    # Stage 37: Kernel Interaction Layer
    def save_kernel_event(self, event):
        with self._get_connection() as conn:
            conn.execute(
                '''INSERT INTO kernel_events (id, type, pid, description, timestamp, metadata)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (event['id'], event['type'], event['pid'], event['description'], 
                 event['timestamp'], json.dumps(event.get('metadata', {})))
            )
            conn.commit()

    def save_process_metrics(self, stats):
        with self._get_connection() as conn:
            conn.execute(
                '''INSERT INTO process_metrics (pid, name, cpu_utime, cpu_stime, memory_rss, fds, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (stats['pid'], stats['name'], stats['utime'], stats['stime'], 
                 stats['memory_rss'], stats['fds'], time.time())
            )
            conn.commit()

    def get_capability_events_for_task(self, task_id):
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM capability_events WHERE task_id = ? ORDER BY timestamp ASC",
                (task_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_granted_capabilities_for_plan(self, plan_id):
        """Retrieve all capabilities that were granted during the execution of a plan."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT required_capability FROM capability_events WHERE plan_id = ? AND granted = 1",
                (plan_id,)
            )
            caps = []
            for row in cursor.fetchall():
                # required_capability might be a comma-separated string if multiple were checked
                for cap in row['required_capability'].split(','):
                    caps.append(cap.strip())
            return list(set(caps))
