"""
db.py — Minimal SQLite session store for Gesture Vocalization.

Design decisions (see implementation_plan.md for rationale):
- Fresh connection per call (thread-safe for Flask dev server + subprocess POST)
- SCRIPT_DIR-relative DB path (consistent with fix pattern in Dashboard.py)
- Orphaned sessions (ended_at IS NULL) count toward Total Sessions
  but are excluded from Gestures Recognized and Recent Sessions detail
"""
import sqlite3
import os
from datetime import datetime, timezone

# Always resolve relative to this file's location, not CWD
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions.db')


def _utcnow() -> str:
    """ISO timestamp in UTC (datetime.utcnow is deprecated since 3.12)."""
    return datetime.now(timezone.utc).isoformat()


def _connect():
    """Return a fresh connection per call — never hold a global connection.
    timeout + busy_timeout + WAL make concurrent access wait instead of
    raising 'database is locked'."""
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at  TEXT    NOT NULL,
            ended_at    TEXT,               -- NULL = orphaned / in-progress
            screen      TEXT,               -- 'scanSent' or 'scanSingle'
            gesture_count INTEGER DEFAULT 0,
            letters     TEXT    DEFAULT ''  -- space-separated recognized letters
        )
    """)
    conn.commit()
    conn.close()


def log_session_start(screen: str) -> int:
    """
    Record the beginning of a recognition session.
    Called by app.py AFTER the single-instance guard passes.
    Returns the new session_id.
    """
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO sessions (started_at, screen) VALUES (?, ?)",
        (_utcnow(), screen)
    )
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def log_session_end(session_id: int, letters: str, gesture_count: int):
    """
    Mark a session as ended with its results.
    Called via POST /api/session-result from Dashboard.py.
    Safe to call even if session_id doesn't exist (no-op).
    """
    conn = _connect()
    conn.execute(
        """UPDATE sessions
           SET ended_at=?, gesture_count=?, letters=?
           WHERE id=?""",
        (_utcnow(), gesture_count, letters.strip(), session_id)
    )
    conn.commit()
    conn.close()


def get_stats() -> dict:
    """
    Return real KPI numbers for the dashboard stat cards.

    Orphan decision (explicit):
      - Total Sessions  = ALL rows (honest: each row = one attempt)
      - Total Gestures  = SUM only from COMPLETED sessions (ended_at IS NOT NULL)
      - Saved Sessions  = completed sessions that have at least one letter

    Delta/trend subtexts are NOT returned — no deltas until real history exists.
    """
    conn = _connect()

    total_sessions = conn.execute(
        "SELECT COUNT(*) FROM sessions"
    ).fetchone()[0]

    total_gestures = conn.execute(
        "SELECT COALESCE(SUM(gesture_count), 0) FROM sessions WHERE ended_at IS NOT NULL"
    ).fetchone()[0]

    saved_count = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE ended_at IS NOT NULL AND gesture_count > 0"
    ).fetchone()[0]

    conn.close()
    return {
        'total_sessions': total_sessions,
        'total_gestures': total_gestures,
        'saved_count': saved_count,
    }


def get_recent_sessions(n: int = 10) -> list:
    """
    Return the last n COMPLETED sessions for the history panel and chart.
    Orphaned sessions are excluded — they have no useful detail to display.
    """
    conn = _connect()
    rows = conn.execute(
        """SELECT id, screen, started_at, ended_at, gesture_count, letters
           FROM sessions
           WHERE ended_at IS NOT NULL
           ORDER BY started_at DESC
           LIMIT ?""",
        (n,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_model_status(model_path: str, labels: list) -> dict:
    """
    Report real model metadata without loading the full model.
    Checks file existence only — fast, no TF import needed here.
    """
    exists = os.path.isfile(model_path)
    size_mb = round(os.path.getsize(model_path) / 1_048_576, 1) if exists else None
    return {
        'loaded': exists,
        'class_count': len(labels) if exists else 0,
        'classes': labels if exists else [],
        'model_size_mb': size_mb,
        'path': model_path,
    }
