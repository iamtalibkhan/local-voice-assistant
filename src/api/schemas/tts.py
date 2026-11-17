from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, description="Text to synthesize into spoken audio")
    voice: str | None = Field(default=None, description="Voice ID (e.g. af_heart, am_adam)")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed multiplier (0.5 to 2.0)")
    lang: str = Field(default="en-us", description="Language code")


class TTSResponse(BaseModel):
    audio_base64: str = Field(description="Base64-encoded WAV audio data")
    format: str = Field(default="audio/wav")
    voice: str
    sample_rate: int = 24000


class TTSVoicesResponse(BaseModel):
    voices: list[str]
    default_voice: str
    total: int

