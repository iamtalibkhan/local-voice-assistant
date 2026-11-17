from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    language_probability: float


class VoiceTextRequest(BaseModel):
    text: str = Field(min_length=1, description="Transcribed user text to respond to")
    voice: str | None = Field(default=None, description="Kokoro voice ID")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed multiplier")
    session_id: str | None = Field(default="default", description="Optional session ID for conversational memory")
    save_to_session: bool = Field(default=True, description="Whether to persist this turn to session history (set False for dual-stream voice where /chat owns the write)")


class VoiceChatResponse(BaseModel):
    transcript: str
    response: str
    audio_base64: str | None = Field(default=None, description="Base64-encoded WAV audio of the response")
