import asyncio
import logging

from fastapi import APIRouter, HTTPException, Response

from src.api.schemas.tts import TTSRequest, TTSResponse, TTSVoicesResponse
from src.core.config import settings
from src.services.tts_service import (
    get_available_voices,
    synthesize_to_base64,
    synthesize_to_bytes,
)

router = APIRouter(prefix="/tts", tags=["tts"])
logger = logging.getLogger(__name__)


def _preview_text(text: str, max_len: int = 140) -> str:
    clean = " ".join(text.split())
    if len(clean) <= max_len:
        return clean
    return f"{clean[:max_len]}... [total={len(text)} chars]"


@router.get("/voices", response_model=TTSVoicesResponse)
async def list_voices() -> TTSVoicesResponse:
    logger.info("Received /tts/voices request")
    try:
        voices = await asyncio.to_thread(get_available_voices)
        logger.info(
            "Sending /tts/voices response | total=%d voices, default=%r",
            len(voices),
            settings.kokoro_default_voice,
        )
        return TTSVoicesResponse(
            voices=voices,
            default_voice=settings.kokoro_default_voice,
            total=len(voices),
        )
    except FileNotFoundError as exc:
        logger.error("Voices file not found: %s", exc)
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to load Kokoro voices")
        raise HTTPException(500, "Could not load TTS voices.") from exc


@router.post("/synthesize")
async def synthesize_audio(request: TTSRequest) -> Response:
    effective_voice = request.voice or settings.kokoro_default_voice
    effective_speed = request.speed or settings.kokoro_default_speed
    effective_lang = request.lang or settings.kokoro_default_lang
    logger.info(
        "Received /tts/synthesize request | text: %r, voice: %r, speed: %.2f, lang: %r",
        _preview_text(request.text),
        effective_voice,
        effective_speed,
        effective_lang,
    )
    try:
        wav_bytes = await asyncio.to_thread(
            synthesize_to_bytes,
            request.text,
            request.voice,
            request.speed,
            request.lang,
        )
        logger.info(
            "Sending /tts/synthesize response | content-type=audio/wav, size=%d bytes (%.2f KB)",
            len(wav_bytes),
            len(wav_bytes) / 1024,
        )
        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": 'inline; filename="speech.wav"',
            },
        )
    except FileNotFoundError as exc:
        logger.error("TTS model/voices file missing: %s", exc)
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception("TTS synthesis failed")
        raise HTTPException(500, "Text-to-speech synthesis failed.") from exc


@router.post("/synthesize-json", response_model=TTSResponse)
async def synthesize_json(request: TTSRequest) -> TTSResponse:
    effective_voice = request.voice or settings.kokoro_default_voice
    effective_speed = request.speed or settings.kokoro_default_speed
    effective_lang = request.lang or settings.kokoro_default_lang
    logger.info(
        "Received /tts/synthesize-json request | text: %r, voice: %r, speed: %.2f, lang: %r",
        _preview_text(request.text),
        effective_voice,
        effective_speed,
        effective_lang,
    )
    try:
        audio_base64 = await asyncio.to_thread(
            synthesize_to_base64,
            request.text,
            request.voice,
            request.speed,
            request.lang,
        )
        selected_voice = request.voice or settings.kokoro_default_voice
        logger.info(
            "Sending /tts/synthesize-json response | voice: %r, sample_rate=24000, audio_base64=%d chars",
            selected_voice,
            len(audio_base64),
        )
        return TTSResponse(
            audio_base64=audio_base64,
            format="audio/wav",
            voice=selected_voice,
            sample_rate=24000,
        )
    except FileNotFoundError as exc:
        logger.error("TTS model/voices file missing: %s", exc)
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception("TTS synthesis failed")
        raise HTTPException(500, "Text-to-speech synthesis failed.") from exc
