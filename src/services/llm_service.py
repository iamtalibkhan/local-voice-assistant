import logging
import httpx

from src.core.config import settings
from src.services.session_service import session_manager

logger = logging.getLogger(__name__)


async def generate_response(
    prompt: str,
    system_prompt: str | None = None,
    think: bool = False,
    history: list[dict[str, str]] | None = None,
) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    if history:
        logger.info(
            "Fed Ollama payload with %d prior history message(s) (%d turn(s)) + current user prompt",
            len(history),
            len(history) // 2,
        )
    else:
        logger.info("Fed Ollama payload with 0 history messages (fresh prompt)")

    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "think": think,
    }

    async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
        response = await client.post(
            f"{settings.ollama_url}/api/chat",
            json=payload,
        )

        response.raise_for_status()

        result = response.json()

    return result["message"]["content"]


async def generate_chat_response(
    prompt: str,
    session_id: str | None = None,
    save_to_session: bool = True,
) -> str:
    """Generates rich, detailed text response for screen reading, maintaining session memory."""
    sid = session_id or "default"
    history = session_manager.get_history(sid)
    response = await generate_response(
        prompt=prompt,
        system_prompt=settings.chat_system_prompt,
        think=False,
        history=history,
    )
    if save_to_session:
        session_manager.add_turn(sid, user_content=prompt, assistant_content=response)
    else:
        logger.info("Skipping session write for /chat (save_to_session=False, another call owns session write)")
    return response


async def generate_voice_response(
    prompt: str,
    session_id: str | None = None,
    save_to_session: bool = True,
) -> str:
    """Generates concise, natural plain-text response for speech synthesis, maintaining session memory."""
    sid = session_id or "default"
    history = session_manager.get_history(sid)
    response = await generate_response(
        prompt=prompt,
        system_prompt=settings.voice_system_prompt,
        think=False,
        history=history,
    )
    if save_to_session:
        session_manager.add_turn(sid, user_content=prompt, assistant_content=response)
    else:
        logger.info("Skipping session write for voice (save_to_session=False, another call owns session write)")
    return response
