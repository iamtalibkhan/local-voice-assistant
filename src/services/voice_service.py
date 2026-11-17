import asyncio
import logging

from src.services.llm_service import generate_voice_response
from src.services.tts_service import synthesize_to_base64

logger = logging.getLogger(__name__)


async def generate_voice_response_text(
    transcript: str,
    session_id: str | None = None,
    save_to_session: bool = True,
) -> str:
    return await generate_voice_response(transcript, session_id=session_id, save_to_session=save_to_session)


async def generate_voice_response_with_audio(
    transcript: str,
    voice: str | None = None,
    speed: float | None = None,
    session_id: str | None = None,
    save_to_session: bool = True,
) -> tuple[str, str | None]:
    """Generates voice-optimized plain-text response and synthesizes it to base64 WAV audio."""
    response_text = await generate_voice_response(
        transcript, session_id=session_id, save_to_session=save_to_session
    )
    audio_base64 = None
    try:
        audio_base64 = await asyncio.to_thread(
            synthesize_to_base64,
            response_text,
            voice,
            speed,
        )
    except Exception as exc:
        logger.warning("TTS synthesis failed for voice response: %s", exc)

    return response_text, audio_base64
