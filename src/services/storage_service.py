"""
SQLite-backed persistent session storage.

Schema
------
  sessions (
    id         TEXT    PRIMARY KEY,
    title      TEXT    NOT NULL,
    is_pinned  INTEGER DEFAULT 0,    -- 0: unpinned, 1: pinned
    voice      TEXT,
    speed      REAL    DEFAULT 1.0,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
  )

  messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT    NOT NULL,
    role       TEXT    NOT NULL,     -- 'user' | 'assistant'
    content    TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
  )
"""

import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from src.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _preview_text(text: str, max_len: int = 60) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= max_len else f"{clean[:max_len]}..."


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# SQLite connection (one per thread to stay thread-safe)
# ---------------------------------------------------------------------------

_local = threading.local()
_custom_db_path: Path | None = None


def set_db_path(path: Path | str | None) -> None:
    """Set a custom database path (e.g. for isolated test suites) and reinitialise schema."""
    global _custom_db_path
    _custom_db_path = Path(path) if path is not None else None
    _init_db()


def get_db_path() -> Path:
    """Return the active SQLite database path."""
    if _custom_db_path is not None:
        return _custom_db_path
    env_path = os.getenv("SESSION_DB_PATH")
    if env_path:
        return Path(env_path)
    return Path(settings.session_db_path)


def _get_conn() -> sqlite3.Connection:
    """Return a per-thread SQLite connection, creating it if needed."""
    db_path = get_db_path()
    conn: sqlite3.Connection | None = getattr(_local, "conn", None)
    conn_path: Path | None = getattr(_local, "conn_path", None)

    if conn is None or conn_path != db_path:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
        _local.conn_path = db_path
    return conn


def _init_db() -> None:
    """Create the schema and perform any necessary migrations."""
    conn = _get_conn()

    # 1. Sessions master table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id         TEXT    PRIMARY KEY,
            title      TEXT    NOT NULL,
            is_pinned  INTEGER DEFAULT 0,
            voice      TEXT,
            speed      REAL    DEFAULT 1.0,
            created_at TEXT    NOT NULL,
            updated_at TEXT    NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_pinned_updated ON sessions(is_pinned DESC, updated_at DESC)"
    )

    # 2. Messages table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT    NOT NULL,
            role       TEXT    NOT NULL,
            content    TEXT    NOT NULL,
            created_at TEXT    NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)"
    )

    # 3. Backfill sessions table if messages exist without a session record
    conn.execute(
        """
        INSERT OR IGNORE INTO sessions (id, title, is_pinned, created_at, updated_at)
        SELECT 
            m1.session_id,
            COALESCE(
                substr((SELECT content FROM messages m2 WHERE m2.session_id = m1.session_id AND m2.role = 'user' ORDER BY id ASC LIMIT 1), 1, 45),
                'Conversation'
            ),
            0,
            MIN(m1.created_at),
            MAX(m1.created_at)
        FROM messages m1
        GROUP BY m1.session_id
        """
    )

    conn.commit()
    logger.info("Session DB initialised at %s", get_db_path().resolve())


# ---------------------------------------------------------------------------
# Public API — Sessions Management
# ---------------------------------------------------------------------------

def db_ensure_session(
    session_id: str,
    title: str | None = None,
    voice: str | None = None,
    speed: float = 1.0,
) -> dict:
    """Ensure a session exists in the sessions table; returns session dict."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row:
        return dict(row)

    now = _utcnow()
    assigned_title = (title or "New Conversation").strip()
    conn.execute(
        """
        INSERT INTO sessions (id, title, is_pinned, voice, speed, created_at, updated_at)
        VALUES (?, ?, 0, ?, ?, ?, ?)
        """,
        (session_id, assigned_title, voice, speed, now, now),
    )
    conn.commit()
    return {
        "id": session_id,
        "title": assigned_title,
        "is_pinned": 0,
        "voice": voice,
        "speed": speed,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }


def db_create_session(
    session_id: str,
    title: str = "New Conversation",
    voice: str | None = None,
    speed: float = 1.0,
) -> dict:
    """Explicitly create a new session."""
    return db_ensure_session(session_id=session_id, title=title, voice=voice, speed=speed)


def db_list_sessions() -> list[dict]:
    """Return all sessions sorted by is_pinned DESC, updated_at DESC with message counts."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT 
            s.id,
            s.title,
            s.is_pinned,
            s.voice,
            s.speed,
            s.created_at,
            s.updated_at,
            COUNT(m.id) AS message_count
        FROM sessions s
        LEFT JOIN messages m ON s.id = m.session_id
        GROUP BY s.id
        ORDER BY s.is_pinned DESC, s.updated_at DESC
        """
    ).fetchall()

    return [
        {
            "id": r["id"],
            "title": r["title"],
            "is_pinned": bool(r["is_pinned"]),
            "voice": r["voice"],
            "speed": float(r["speed"]) if r["speed"] is not None else 1.0,
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "message_count": r["message_count"],
            "turn_count": r["message_count"] // 2,
        }
        for r in rows
    ]


def db_get_session(session_id: str) -> dict | None:
    """Return metadata for a single session."""
    conn = _get_conn()
    r = conn.execute(
        """
        SELECT 
            s.id,
            s.title,
            s.is_pinned,
            s.voice,
            s.speed,
            s.created_at,
            s.updated_at,
            COUNT(m.id) AS message_count
        FROM sessions s
        LEFT JOIN messages m ON s.id = m.session_id
        WHERE s.id = ?
        GROUP BY s.id
        """,
        (session_id,),
    ).fetchone()

    if not r:
        return None

    return {
        "id": r["id"],
        "title": r["title"],
        "is_pinned": bool(r["is_pinned"]),
        "voice": r["voice"],
        "speed": float(r["speed"]) if r["speed"] is not None else 1.0,
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
        "message_count": r["message_count"],
        "turn_count": r["message_count"] // 2,
    }


def db_get_session_messages(session_id: str) -> list[dict]:
    """Return all messages for a session in chronological order."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT id, role, content, created_at
        FROM messages
        WHERE session_id = ?
        ORDER BY id ASC
        """,
        (session_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def db_update_session(
    session_id: str,
    title: str | None = None,
    is_pinned: bool | None = None,
    voice: str | None = None,
    speed: float | None = None,
) -> bool:
    """Update editable fields on a session."""
    conn = _get_conn()
    updates = []
    params = []

    if title is not None:
        updates.append("title = ?")
        params.append(title.strip() or "Conversation")
    if is_pinned is not None:
        updates.append("is_pinned = ?")
        params.append(1 if is_pinned else 0)
    if voice is not None:
        updates.append("voice = ?")
        params.append(voice)
    if speed is not None:
        updates.append("speed = ?")
        params.append(speed)

    if not updates:
        return False

    updates.append("updated_at = ?")
    params.append(_utcnow())

    params.append(session_id)
    query = f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?"
    cursor = conn.execute(query, params)
    conn.commit()
    return cursor.rowcount > 0


def db_toggle_pin(session_id: str) -> bool | None:
    """Toggle is_pinned for a session. Returns new is_pinned boolean, or None if not found."""
    conn = _get_conn()
    row = conn.execute("SELECT is_pinned FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return None

    new_pinned = 0 if row["is_pinned"] else 1
    conn.execute(
        "UPDATE sessions SET is_pinned = ? WHERE id = ?",
        (new_pinned, session_id),
    )
    conn.commit()
    return bool(new_pinned)


def db_delete_session(session_id: str) -> bool:
    """Delete a session and all its messages."""
    conn = _get_conn()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Public API — History & Turn Management
# ---------------------------------------------------------------------------

def db_load_history(session_id: str, limit: int) -> list[dict[str, str]]:
    """Return the most recent *limit* messages for session_id (oldest first)."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT role, content FROM (
            SELECT id, role, content
            FROM   messages
            WHERE  session_id = ?
            ORDER  BY id DESC
            LIMIT  ?
        )
        ORDER BY id ASC
        """,
        (session_id, limit),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def db_add_turn(session_id: str, user_content: str, assistant_content: str) -> None:
    """Append one user message and one assistant message, creating or updating the session record."""
    conn = _get_conn()
    now = _utcnow()

    # Check if session exists in sessions table
    existing = conn.execute(
        "SELECT id, title FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()

    if not existing:
        # First turn in a new session: use first prompt as title
        auto_title = user_content[:45].strip() or "Conversation"
        conn.execute(
            """
            INSERT INTO sessions (id, title, is_pinned, created_at, updated_at)
            VALUES (?, ?, 0, ?, ?)
            """,
            (session_id, auto_title, now, now),
        )
    else:
        # If title is placeholder, update it with meaningful user prompt
        current_title = existing["title"]
        if current_title in ("New Conversation", "Conversation", "default"):
            auto_title = user_content[:45].strip() or current_title
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (auto_title, now, session_id),
            )
        else:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )

    conn.executemany(
        "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        [
            (session_id, "user",      user_content,      now),
            (session_id, "assistant", assistant_content, now),
        ],
    )
    conn.commit()


def db_count_messages(session_id: str) -> int:
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM messages WHERE session_id = ?", (session_id,)
    ).fetchone()
    return row["n"] if row else 0


def db_trim_history(session_id: str, keep_messages: int) -> int:
    """Delete the oldest messages so that at most *keep_messages* remain."""
    conn = _get_conn()
    total = db_count_messages(session_id)
    excess = total - keep_messages
    if excess <= 0:
        return 0

    boundary = conn.execute(
        """
        SELECT id FROM messages
        WHERE  session_id = ?
        ORDER  BY id ASC
        LIMIT  ? OFFSET ?
        """,
        (session_id, 1, excess - 1),
    ).fetchone()

    if boundary is None:
        return 0

    conn.execute(
        "DELETE FROM messages WHERE session_id = ? AND id <= ?",
        (session_id, boundary["id"]),
    )
    conn.commit()
    return conn.execute("SELECT changes() AS n").fetchone()["n"]


def db_reset_session(session_id: str) -> int:
    """Delete all messages for session_id without deleting the session entry."""
    conn = _get_conn()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    now = _utcnow()
    conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
    conn.commit()
    return conn.execute("SELECT changes() AS n").fetchone()["n"]


def db_clear_all() -> None:
    """Wipe every session and message (used in tests)."""
    conn = _get_conn()
    conn.execute("DELETE FROM messages")
    conn.execute("DELETE FROM sessions")
    conn.commit()


# Initialise the schema when this module is first imported.
_init_db()
