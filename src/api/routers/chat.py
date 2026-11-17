import logging

import httpx
from fastapi import APIRouter, HTTPException

from src.api.schemas.chat import ChatRequest, ChatResponse
from src.services.llm_service import generate_chat_response

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


def _preview_text(text: str, max_len: int = 140) -> str:
    clean = " ".join(text.split())
    if len(clean) <= max_len:
        return clean
    return f"{clean[:max_len]}... [total={len(text)} chars]"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or "default"
    logger.info(
        "Received /chat request | session_id: %r, prompt: %r",
        session_id,
        _preview_text(request.prompt),
    )
    try:
        response = await generate_chat_response(request.prompt, session_id=session_id)
        logger.info(
            "Sending /chat response | session_id: %r, response: %r",
            session_id,
            _preview_text(response),
        )
    except httpx.HTTPStatusError as exc:
        logger.error("Ollama HTTP error during /chat: %s", exc)
        raise HTTPException(502, "Ollama could not generate a response.") from exc
    except httpx.RequestError as exc:
        logger.error("Ollama connection error during /chat: %s", exc)
        raise HTTPException(
            503,
            "Ollama is unavailable. Start the local Ollama service and try again.",
        ) from exc

    return ChatResponse(response=response)
