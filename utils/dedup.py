"""
utils/dedup.py
--------------
SQLite-backed deduplication store.

CRITICAL CONTRACT
─────────────────
• mark_sent(email)    → writes a record; idempotent
• already_sent(email) → True if email is in the store
• get_all_sent()      → returns list of all sent records
• close()             → safely closes the connection

The DB is opened in WAL mode so concurrent reads don't block writes.
"""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from config import settings


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sent_emails (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT    NOT NULL UNIQUE,
    name        TEXT,
    company     TEXT,
    sent_at     TEXT    NOT NULL,
    subject     TEXT
);
"""

_INSERT_SQL = """
INSERT OR IGNORE INTO sent_emails (email, name, company, sent_at, subject)
VALUES (?, ?, ?, ?, ?);
"""

_CHECK_SQL  = "SELECT 1 FROM sent_emails WHERE email = ? LIMIT 1;"
_ALL_SQL    = "SELECT email, name, company, sent_at, subject FROM sent_emails;"


class DeduplicationStore:
    """Thread-safe SQLite deduplication store."""

    def __init__(self, db_path: str = settings.DB_PATH):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = self._connect()

    # ── Private ───────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
        return conn

    # ── Public API ─────────────────────────────────────────────────────────────

    def already_sent(self, email: str) -> bool:
        """Returns True if this email address has been sent to before."""
        email = email.strip().lower()
        with self._lock:
            cur = self._conn.execute(_CHECK_SQL, (email,))
            return cur.fetchone() is not None

    def mark_sent(
        self,
        email: str,
        name: str = "",
        company: str = "",
        subject: str = "",
    ) -> None:
        """Records a sent email. Safe to call multiple times (INSERT OR IGNORE)."""
        email = email.strip().lower()
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(_INSERT_SQL, (email, name, company, now, subject))
            self._conn.commit()

    def get_all_sent(self) -> list[dict]:
        """Returns all sent records as a list of dicts."""
        with self._lock:
            cur = self._conn.execute(_ALL_SQL)
            rows = cur.fetchall()
        return [
            {
                "email":   r[0],
                "name":    r[1],
                "company": r[2],
                "sent_at": r[3],
                "subject": r[4],
            }
            for r in rows
        ]

    def count(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM sent_emails;")
            return cur.fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ── Context manager support ───────────────────────────────────────────────
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# Module-level singleton — reuse across the run
_store: DeduplicationStore | None = None


def get_store() -> DeduplicationStore:
    global _store
    if _store is None:
        _store = DeduplicationStore()
    return _store
