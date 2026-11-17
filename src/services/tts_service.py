import base64
import io
import logging
import os
import re
import threading
from typing import Any

from kokoro_onnx import Kokoro
import soundfile as sf

from src.core.config import settings

logger = logging.getLogger(__name__)

_tts_model: Kokoro | None = None
_tts_lock = threading.Lock()
_available_voices: list[str] = []


def clean_text_for_tts(text: str) -> str:
    """
    Sanitizes markdown, asterisks, hashtags, and code symbols so that
    the TTS model reads natural, conversational prose without awkward
    pronunciation of formatting symbols.
    """
    if not text:
        return ""

    # Remove fenced code blocks ```...```
    cleaned = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code backticks `code` -> code
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)

    # Remove Markdown headers (# Header, ## Header, etc.)
    cleaned = re.sub(r"^#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s+#{1,6}\s+", " ", cleaned)

    # Remove Markdown links [text](url) -> text
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    # Remove Markdown images ![alt](url) -> ""
    cleaned = re.sub(r"!\[([^\]]*)\]\([^)]+\)", "", cleaned)

    # Remove bold, italics, strikethrough: ***text***, **text**, *text*, __text__, _text_, ~~text~~
    cleaned = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", cleaned)
    cleaned = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", cleaned)
    cleaned = re.sub(r"~~([^~]+)~~", r"\1", cleaned)

    # Remove bullet points and list markers at the start of lines (*, -, +, 1., etc.)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)

    # Remove blockquotes (> quote)
    cleaned = re.sub(r"^\s*>\s*", "", cleaned, flags=re.MULTILINE)

    # Remove horizontal rules (---, ***, ___)
    cleaned = re.sub(r"^\s*[-*_]{3,}\s*$", "", cleaned, flags=re.MULTILINE)

    # Remove remaining standalone special characters: #, *, ~, _, `, |, <, >
    cleaned = re.sub(r"[*#~_`|<>]", "", cleaned)

    # Replace common symbols for natural speech
    cleaned = re.sub(r"&", " and ", cleaned)
    cleaned = re.sub(r"%", " percent ", cleaned)
    cleaned = re.sub(r"\s+/\s+", " or ", cleaned)

    # Remove emojis (Unicode surrogate / emoji range)
    cleaned = re.sub(r"[\U00010000-\U0010ffff]", "", cleaned)

    # Collapse extra whitespace and newlines into clean spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def load_tts_model() -> Kokoro:
    global _tts_model, _available_voices

    if _tts_model is None:
        with _tts_lock:
            if _tts_model is None:
                if not os.path.exists(settings.kokoro_model_path):
                    raise FileNotFoundError(
                        f"Kokoro ONNX model file not found at: {settings.kokoro_model_path}. "
                        "Please download kokoro-v1.0.onnx and place it in the models/kokoro directory."
                    )
                if not os.path.exists(settings.kokoro_voices_path):
                    raise FileNotFoundError(
                        f"Kokoro voices file not found at: {settings.kokoro_voices_path}. "
                        "Please download voices-v1.0.bin and place it in the models/kokoro directory."
                    )

                logger.info(
                    "Initializing Kokoro TTS model from %s and %s",
                    settings.kokoro_model_path,
                    settings.kokoro_voices_path,
                )
                model = Kokoro(settings.kokoro_model_path, settings.kokoro_voices_path)
                _available_voices = sorted(model.get_voices())
                _tts_model = model
                logger.info("Kokoro TTS initialized with %d voices", len(_available_voices))

    return _tts_model


def get_available_voices() -> list[str]:
    if not _available_voices:
        load_tts_model()
    return _available_voices


def samples_to_wav_bytes(samples: Any, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def synthesize_audio(
    text: str,
    voice: str | None = None,
    speed: float | None = None,
    lang: str | None = None,
) -> tuple[Any, int]:
    model = load_tts_model()
    selected_voice = voice or settings.kokoro_default_voice
    selected_speed = speed if speed is not None else settings.kokoro_default_speed
    selected_lang = lang or settings.kokoro_default_lang

    voices = get_available_voices()
    if selected_voice not in voices:
        logger.warning(
            "Requested voice '%s' not found. Falling back to '%s'",
            selected_voice,
            settings.kokoro_default_voice,
        )
        selected_voice = settings.kokoro_default_voice

    sanitized_text = clean_text_for_tts(text)
    if not sanitized_text:
        sanitized_text = "I have nothing to say."

    samples, sample_rate = model.create(
        text=sanitized_text,
        voice=selected_voice,
        speed=selected_speed,
        lang=selected_lang,
    )
    return samples, sample_rate


def synthesize_to_bytes(
    text: str,
    voice: str | None = None,
    speed: float | None = None,
    lang: str | None = None,
) -> bytes:
    samples, sample_rate = synthesize_audio(text, voice=voice, speed=speed, lang=lang)
    return samples_to_wav_bytes(samples, sample_rate)


def synthesize_to_base64(
    text: str,
    voice: str | None = None,
    speed: float | None = None,
    lang: str | None = None,
) -> str:
    wav_bytes = synthesize_to_bytes(text, voice=voice, speed=speed, lang=lang)
    return base64.b64encode(wav_bytes).decode("utf-8")
