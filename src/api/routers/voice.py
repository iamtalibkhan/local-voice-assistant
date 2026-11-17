import asyncio
import logging
import os
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from starlette.datastructures import UploadFile

from src.api.schemas.voice import TranscriptionResponse, VoiceChatResponse, VoiceTextRequest
from src.core.config import settings
from src.services.transcription_service import transcribe_audio_file
from src.services.voice_service import (
    generate_voice_response_text,
    generate_voice_response_with_audio,
)

router = APIRouter(tags=["voice"])
logger = logging.getLogger(__name__)

AUDIO_SUFFIXES = {
    "audio/flac": ".flac",
    "audio/m4a": ".m4a",
    "audio/mp4": ".mp4",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
    "audio/x-wav": ".wav",
    "audio/x-m4a": ".m4a",
    "application/x-m4a": ".m4a",
    "application/octet-stream": ".audio",
}
ALLOWED_AUDIO_SUFFIXES = set(AUDIO_SUFFIXES.values())


def _preview_text(text: str, max_len: int = 140) -> str:
    clean = " ".join(text.split())
    if len(clean) <= max_len:
        return clean
    return f"{clean[:max_len]}... [total={len(text)} chars]"


async def _transcribe_request(request: Request) -> TranscriptionResponse:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    temp_path: str | None = None
    upload: UploadFile | None = None
    total_bytes = 0

    try:
        if content_type == "multipart/form-data":
            form = await request.form()
            upload = next(
                (value for value in form.values() if isinstance(value, UploadFile)),
                None,
            )
            if upload is None:
                logger.warning("Rejected audio upload: no file attached in multipart form")
                raise HTTPException(400, "Attach an audio file.")
            suffix = AUDIO_SUFFIXES.get(
                (upload.content_type or "").lower(),
                Path(upload.filename or "").suffix.lower(),
            )
        else:
            suffix = AUDIO_SUFFIXES.get(content_type)

        if suffix not in ALLOWED_AUDIO_SUFFIXES:
            logger.warning(
                "Rejected audio upload with unsupported content-type: %r, suffix: %r",
                content_type,
                suffix,
            )
            raise HTTPException(415, "Upload MP3, M4A, WAV, WebM, OGG, FLAC, or MP4 audio.")

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as audio_file:
            temp_path = audio_file.name
            if upload is not None:
                while chunk := await upload.read(1024 * 1024):
                    total_bytes += len(chunk)
                    if total_bytes > settings.max_audio_bytes:
                        raise HTTPException(413, "Audio must be 25 MB or smaller.")
                    audio_file.write(chunk)
            else:
                async for chunk in request.stream():
                    total_bytes += len(chunk)
                    if total_bytes > settings.max_audio_bytes:
                        raise HTTPException(413, "Audio must be 25 MB or smaller.")
                    audio_file.write(chunk)

        if total_bytes == 0:
            logger.warning("Rejected audio upload: body is empty (0 bytes)")
            raise HTTPException(400, "The audio body is empty.")

        logger.info(
            "Transcribing audio with Whisper | format: %s, size: %d bytes (%.2f KB)",
            suffix,
            total_bytes,
            total_bytes / 1024,
        )

        result = await asyncio.to_thread(transcribe_audio_file, temp_path)
        logger.info(
            "Transcription completed | text: %r, language: %s (confidence: %.2f)",
            _preview_text(str(result.get("text", ""))),
            result.get("language"),
            float(result.get("language_probability", 0.0)),
        )
        return TranscriptionResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Transcription failed with unexpected error")
        raise HTTPException(
            422,
            "Audio could not be transcribed. Check the audio format and Whisper setup.",
        ) from exc
    finally:
        if upload is not None:
            await upload.close()
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(request: Request) -> TranscriptionResponse:
    logger.info("Received /transcribe request")
    res = await _transcribe_request(request)
    logger.info(
        "Sending /transcribe response | text: %r, lang: %s",
        _preview_text(res.text),
        res.language,
    )
    return res


@router.post("/respond-text", response_model=VoiceChatResponse)
async def respond_to_text(body: VoiceTextRequest) -> VoiceChatResponse:
    session_id = body.session_id or "default"
    effective_voice = body.voice or settings.kokoro_default_voice
    effective_speed = body.speed or settings.kokoro_default_speed
    logger.info(
        "Received /respond-text request | session_id: %r, save_to_session: %s, text: %r, voice: %r, speed: %.2f",
        session_id,
        body.save_to_session,
        _preview_text(body.text),
        effective_voice,
        effective_speed,
    )
    try:
        response, audio_base64 = await generate_voice_response_with_audio(
            body.text,
            voice=body.voice,
            speed=body.speed,
            session_id=session_id,
            save_to_session=body.save_to_session,
        )
        audio_info = f"{len(audio_base64)} chars" if audio_base64 else "None"
        logger.info(
            "Sending /respond-text response | session_id: %r, response: %r, audio_base64: %s",
            session_id,
            _preview_text(response),
            audio_info,
        )
    except httpx.HTTPStatusError as exc:
        logger.error("Ollama HTTP status error during /respond-text: %s", exc)
        raise HTTPException(502, "Ollama could not generate a response.") from exc
    except httpx.RequestError as exc:
        logger.error("Ollama connection error during /respond-text: %s", exc)
        raise HTTPException(
            503,
            "Ollama is unavailable. Start the local Ollama service and try again.",
        ) from exc

    return VoiceChatResponse(
        transcript=body.text,
        response=response,
        audio_base64=audio_base64,
    )


@router.post("/voice-chat", response_model=VoiceChatResponse)
async def voice_chat(
    request: Request,
    include_audio: bool = Query(default=True, description="Whether to include synthesized TTS audio in the response"),
    voice: str | None = Query(default=None, description="Kokoro voice to use for TTS"),
    speed: float = Query(default=1.0, ge=0.5, le=2.0, description="Speech speed multiplier"),
    session_id: str | None = Query(default="default", description="Session ID for conversational memory"),
) -> VoiceChatResponse:
    effective_session_id = session_id or "default"
    effective_voice = voice or settings.kokoro_default_voice
    logger.info(
        "Received /voice-chat request | session_id: %r, include_audio: %s, voice: %r, speed: %.2f",
        effective_session_id,
        include_audio,
        effective_voice,
        speed,
    )
    transcription = await _transcribe_request(request)
    if not transcription.text:
        logger.warning("No speech detected in /voice-chat audio payload")
        raise HTTPException(422, "No speech was detected in the audio.")

    try:
        if include_audio:
            response, audio_base64 = await generate_voice_response_with_audio(
                transcription.text,
                voice=voice,
                speed=speed,
                session_id=effective_session_id,
            )
        else:
            response = await generate_voice_response_text(transcription.text, session_id=effective_session_id)
            audio_base64 = None

        audio_info = f"{len(audio_base64)} chars" if audio_base64 else "None"
        logger.info(
            "Sending /voice-chat response | session_id: %r, transcript: %r, response: %r, audio_base64: %s",
            effective_session_id,
            _preview_text(transcription.text),
            _preview_text(response),
            audio_info,
        )
    except httpx.HTTPStatusError as exc:
        logger.error("Ollama HTTP status error during /voice-chat: %s", exc)
        raise HTTPException(502, "Ollama could not generate a response.") from exc
    except httpx.RequestError as exc:
        logger.error("Ollama connection error during /voice-chat: %s", exc)
        raise HTTPException(
            503,
            "Ollama is unavailable. Start the local Ollama service and try again.",
        ) from exc

    return VoiceChatResponse(
        transcript=transcription.text,
        response=response,
        audio_base64=audio_base64,
    )
