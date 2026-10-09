import json
import sqlite3
import threading
import time
import uuid


class Store:
    """One durable object store with indexed kind/id and transactional scheduler claims."""
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, body TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(kind,id))")
        self.db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, timestamp REAL, body TEXT)")
        self.db.commit()

    def put(self, kind, body, id=None):
        with self.lock:
            id = id or body.get("id") or uuid.uuid4().hex
            old = self.get(kind, id) or {}
            record = {**old, **body, "id": id, "created_at": old.get("created_at", time.time()), "updated_at": time.time()}
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO records VALUES (?,?,?,?)", (kind, id, json.dumps(record, default=str), time.time()))
            return record

    def get(self, kind, id):
        with self.lock:
            row = self.db.execute("SELECT body FROM records WHERE kind=? AND id=?", (kind, id)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, kind, limit=500):
        with self.lock:
            rows = self.db.execute("SELECT body FROM records WHERE kind=? ORDER BY updated DESC LIMIT ?", (kind, limit)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def delete(self, kind, id):
        with self.lock:
            with self.db:
                self.db.execute("DELETE FROM records WHERE kind=? AND id=?", (kind, id))

    def audit(self, body):
        with self.lock:
            with self.db:
                self.db.execute("INSERT INTO audit(timestamp,body) VALUES (?,?)", (time.time(), json.dumps(body)))

    def audits(self, limit=100):
        with self.lock:
            rows = self.db.execute("SELECT id,timestamp,body FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": a, "timestamp": b, **json.loads(c)} for a, b, c in rows]

    def close(self):
        self.db.close()
