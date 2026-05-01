import sqlite3
import json
import logging
import os

logger = logging.getLogger("MemoryStore")
DB_PATH = "/tmp/snowos_memory.db"

class MemoryStore:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY,
                action TEXT,
                target TEXT,
                outcome TEXT,
                confidence REAL
            )
        ''')
        self.conn.commit()

    def log_decision(self, decision_id, action, target, confidence):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO decisions (decision_id, action, target, outcome, confidence)
            VALUES (?, ?, ?, 'pending', ?)
        ''', (decision_id, action, target, confidence))
        self.conn.commit()
        logger.debug(f"Logged decision {decision_id} into persistent memory.")

    def update_outcome(self, decision_id, outcome, new_confidence):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE decisions SET outcome = ?, confidence = ? WHERE decision_id = ?
        ''', (outcome, new_confidence, decision_id))
        self.conn.commit()
        
    def get_historical_confidence(self, action, target):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT confidence FROM decisions 
            WHERE action = ? AND target = ? AND outcome = 'success'
            ORDER BY ROWID DESC LIMIT 1
        ''', (action, target))
        row = cursor.fetchone()
        return row[0] if row else 0.5 # Default baseline confidence
