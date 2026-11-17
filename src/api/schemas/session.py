from pydantic import BaseModel, Field


class ResetSessionRequest(BaseModel):
    session_id: str = Field(min_length=1, default="default", description="Session ID to clear")


class ResetSessionResponse(BaseModel):
    session_id: str
    message: str


class SessionInfoResponse(BaseModel):
    session_id: str
    message_count: int
    turn_count: int


class SessionItem(BaseModel):
    id: str
    title: str
    is_pinned: bool = False
    voice: str | None = None
    speed: float = 1.0
    message_count: int = 0
    turn_count: int = 0
    created_at: str
    updated_at: str


class SessionMessageItem(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class SessionDetailResponse(BaseModel):
    session_id: str
    id: str
    title: str
    is_pinned: bool = False
    voice: str | None = None
    speed: float = 1.0
    message_count: int = 0
    turn_count: int = 0
    created_at: str
    updated_at: str
    messages: list[SessionMessageItem] = []


class CreateSessionRequest(BaseModel):
    session_id: str | None = Field(default=None, description="Optional custom session ID; auto-generated if omitted")
    title: str | None = Field(default="New Conversation", description="Session title")
    voice: str | None = Field(default=None, description="Preferred voice")
    speed: float | None = Field(default=1.0, ge=0.5, le=2.0, description="Preferred speech speed")


class UpdateSessionRequest(BaseModel):
    title: str | None = Field(default=None, description="Updated session title")
    is_pinned: bool | None = Field(default=None, description="Pin status")
    voice: str | None = Field(default=None, description="Preferred voice")
    speed: float | None = Field(default=None, ge=0.5, le=2.0, description="Preferred speech speed")


class PinSessionResponse(BaseModel):
    session_id: str
    is_pinned: bool
    message: str


class DeleteSessionResponse(BaseModel):
    session_id: str
    message: str
