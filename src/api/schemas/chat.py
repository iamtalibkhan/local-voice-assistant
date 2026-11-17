from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, description="Message to send to the assistant")
    session_id: str | None = Field(default="default", description="Optional session ID for conversational memory")


class ChatResponse(BaseModel):
    response: str
