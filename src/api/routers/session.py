import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from src.api.schemas.session import (
    CreateSessionRequest,
    DeleteSessionResponse,
    PinSessionResponse,
    ResetSessionRequest,
    ResetSessionResponse,
    SessionDetailResponse,
    SessionItem,
    SessionMessageItem,
    UpdateSessionRequest,
)
from src.services.session_service import session_manager
from src.services.storage_service import (
    db_create_session,
    db_delete_session,
    db_ensure_session,
    db_get_session,
    db_get_session_messages,
    db_list_sessions,
    db_toggle_pin,
    db_update_session,
)

router = APIRouter(prefix="/session", tags=["session"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[SessionItem])
async def list_sessions() -> list[SessionItem]:
    """List all sessions ordered by is_pinned DESC, updated_at DESC."""
    sessions = db_list_sessions()
    return [SessionItem(**s) for s in sessions]


@router.post("", response_model=SessionItem)
async def create_session(body: CreateSessionRequest) -> SessionItem:
    """Create a new session."""
    sid = body.session_id or f"sess_{uuid.uuid4().hex[:8]}_{int(datetime.now(timezone.utc).timestamp())}"
    title = (body.title or "New Conversation").strip()
    session_data = db_create_session(
        session_id=sid,
        title=title,
        voice=body.voice,
        speed=body.speed or 1.0,
    )
    logger.info("Created new session: %r (%r)", sid, title)
    return SessionItem(
        id=session_data["id"],
        title=session_data["title"],
        is_pinned=bool(session_data.get("is_pinned", 0)),
        voice=session_data.get("voice"),
        speed=session_data.get("speed", 1.0),
        message_count=session_data.get("message_count", 0),
        turn_count=session_data.get("message_count", 0) // 2,
        created_at=session_data["created_at"],
        updated_at=session_data["updated_at"],
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(session_id: str) -> SessionDetailResponse:
    """Get metadata and full message history for a session."""
    session = db_get_session(session_id)
    if not session:
        # If session not found, auto-ensure it so fresh sessions load without error
        session = db_ensure_session(session_id)

    messages = db_get_session_messages(session_id)
    return SessionDetailResponse(
        session_id=session["id"],
        id=session["id"],
        title=session["title"],
        is_pinned=bool(session["is_pinned"]),
        voice=session["voice"],
        speed=session["speed"],
        message_count=len(messages),
        turn_count=len(messages) // 2,
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        messages=[SessionMessageItem(**m) for m in messages],
    )


@router.patch("/{session_id}", response_model=SessionItem)
async def update_session(session_id: str, body: UpdateSessionRequest) -> SessionItem:
    """Update title, is_pinned, voice, or speed on a session."""
    session = db_get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db_update_session(
        session_id,
        title=body.title,
        is_pinned=body.is_pinned,
        voice=body.voice,
        speed=body.speed,
    )
    updated = db_get_session(session_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found")
    logger.info("Updated session %r metadata", session_id)
    return SessionItem(**updated)


@router.post("/{session_id}/pin", response_model=PinSessionResponse)
async def toggle_pin_session(session_id: str) -> PinSessionResponse:
    """Toggle the pinned state of a session."""
    db_ensure_session(session_id)
    new_pinned = db_toggle_pin(session_id)
    if new_pinned is None:
        raise HTTPException(status_code=404, detail="Session not found")

    action = "pinned" if new_pinned else "unpinned"
    logger.info("Session %r %s", session_id, action)
    return PinSessionResponse(
        session_id=session_id,
        is_pinned=new_pinned,
        message=f"Session successfully {action}.",
    )


@router.delete("/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(session_id: str) -> DeleteSessionResponse:
    """Delete a session and all its messages."""
    deleted = db_delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info("Deleted session %r", session_id)
    return DeleteSessionResponse(
        session_id=session_id,
        message=f"Session {session_id} deleted successfully.",
    )


@router.post("/reset", response_model=ResetSessionResponse)
async def reset_session(body: ResetSessionRequest) -> ResetSessionResponse:
    """Reset / clear message history for a session."""
    logger.info("Received request to reset session: %r", body.session_id)
    session_manager.reset_session(body.session_id)
    logger.info("Session %r reset completed", body.session_id)
    return ResetSessionResponse(
        session_id=body.session_id,
        message="Session memory reset successfully.",
    )
