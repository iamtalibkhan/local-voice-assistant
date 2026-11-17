import logging
import threading

from faster_whisper import WhisperModel

from src.core.config import settings

logger = logging.getLogger(__name__)

_model: WhisperModel | None = None
_model_lock = threading.Lock()

# Known Whisper hallucinations on silence or low-volume background noise
WHISPER_SILENCE_HALLUCINATIONS = {
    "you",
    "you.",
    "you!",
    "you?",
    "thank you",
    "thank you.",
    "thank you!",
    "thank you for watching.",
    "thank you for watching",
    "bye",
    "bye.",
    "so",
    "so.",
    "[music]",
    "(music)",
    "♪",
    "♪♪",
}


def load_model() -> WhisperModel:
    global _model

    if _model is None:
        with _model_lock:
            if _model is None:
                _model = WhisperModel(
                    settings.whisper_model,
                    device=settings.whisper_device,
                    compute_type=settings.whisper_compute_type,
                )

    return _model


def transcribe_audio_file(file_path: str) -> dict[str, str | float]:
    model = load_model()
    segments, info = model.transcribe(
        file_path,
        language=settings.whisper_language,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        condition_on_previous_text=False,
    )
    text = " ".join(segment.text.strip() for segment in segments).strip()

    # Filter out empty audio / silence hallucinations
    if text.lower() in WHISPER_SILENCE_HALLUCINATIONS:
        logger.info("Filtered silence hallucination from Whisper: %r", text)
        text = ""

    return {
        "text": text,
        "language": info.language,
        "language_probability": info.language_probability,
    }
