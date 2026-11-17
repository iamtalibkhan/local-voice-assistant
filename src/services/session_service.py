"""
Session memory manager — thin coordination layer over SQLite storage.

Each public method delegates persistence to storage_service and keeps
logging and sliding-window enforcement in one place.
"""

import logging

from src.core.config import settings
from src.services.storage_service import (
    db_add_turn,
    db_clear_all,
    db_count_messages,
    db_create_session,
    db_delete_session,
    db_ensure_session,
    db_get_session,
    db_get_session_messages,
    db_list_sessions,
    db_load_history,
    db_reset_session,
    db_toggle_pin,
    db_trim_history,
    db_update_session,
)

logger = logging.getLogger(__name__)


def _preview_text(text: str, max_len: int = 60) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= max_len else f"{clean[:max_len]}..."


class SessionManager:
    def __init__(self, max_history_turns: int = settings.session_max_history_turns) -> None:
        self.max_history_turns = max_history_turns

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_history(self, session_id: str | None) -> list[dict[str, str]]:
        sid = session_id or "default"
        max_messages = max(self.max_history_turns * 2, 2)

        # Trim before fetching so callers always get a clean window
        self._trim(sid, max_messages)

        history = db_load_history(sid, limit=max_messages)
        if history:
            preview = [
                f"[{m['role']}]: {_preview_text(m['content'])}" for m in history
            ]
            logger.info(
                "Feeding session history for %r (%d message(s) / %d turn(s)): %s",
                sid, len(history), len(history) // 2, preview,
            )
        else:
            logger.info(
                "Session %r has no previous history (starting fresh turn)", sid
            )
        return history

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_turn(
        self, session_id: str | None, user_content: str, assistant_content: str
    ) -> None:
        sid = session_id or "default"
        db_add_turn(sid, user_content, assistant_content)
        total = db_count_messages(sid)
        logger.info(
            "Added turn to session %r → total: %d message(s) / %d turn(s)",
            sid, total, total // 2,
        )

        max_messages = max(self.max_history_turns * 2, 2)
        self._trim(sid, max_messages)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def reset_session(self, session_id: str | None) -> bool:
        sid = session_id or "default"
        deleted = db_reset_session(sid)
        if deleted:
            logger.info(
                "Session %r reset — deleted %d message(s) from DB", sid, deleted
            )
        else:
            logger.info(
                "Session %r reset requested but had no stored messages", sid
            )
        return True

    def list_sessions(self) -> list[dict]:
        return db_list_sessions()

    def get_session(self, session_id: str) -> dict | None:
        return db_get_session(session_id)

    def get_session_messages(self, session_id: str) -> list[dict]:
        return db_get_session_messages(session_id)

    def create_session(
        self,
        session_id: str,
        title: str = "New Conversation",
        voice: str | None = None,
        speed: float = 1.0,
    ) -> dict:
        return db_create_session(session_id, title=title, voice=voice, speed=speed)

    def update_session(
        self,
        session_id: str,
        title: str | None = None,
        is_pinned: bool | None = None,
        voice: str | None = None,
        speed: float | None = None,
    ) -> bool:
        return db_update_session(
            session_id, title=title, is_pinned=is_pinned, voice=voice, speed=speed
        )

    def toggle_pin(self, session_id: str) -> bool | None:
        return db_toggle_pin(session_id)

    def delete_session(self, session_id: str) -> bool:
        deleted = db_delete_session(session_id)
        if deleted:
            logger.info("Session %r deleted completely", session_id)
        return deleted

    def clear_all(self) -> None:
        """Wipe every session. Used in tests only."""
        db_clear_all()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trim(self, sid: str, max_messages: int) -> None:
        total = db_count_messages(sid)
        if total <= max_messages:
            return
        excess = total - max_messages
        # Fetch the rows that will be dropped so we can log them
        about_to_remove = db_load_history(sid, limit=total)[:excess]
        removed = db_trim_history(sid, keep_messages=max_messages)
        if removed:
            preview = [
                f"[{m['role']}]: {_preview_text(m['content'])}"
                for m in about_to_remove
            ]
            logger.warning(
                "Session %r exceeded limit of %d turn(s) (%d messages). "
                "Removed %d earlier message(s) from DB: %s",
                sid, self.max_history_turns, max_messages, removed, preview,
            )


session_manager = SessionManager()
