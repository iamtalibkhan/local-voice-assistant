import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file() -> None:
    env_file = Path(".env")
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k and k not in os.environ:
                os.environ[k] = v


_load_env_file()


@dataclass(frozen=True)
class Settings:
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
    ollama_timeout_seconds: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    whisper_model: str = os.getenv("WHISPER_MODEL", "small")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    whisper_language: str = os.getenv("WHISPER_LANGUAGE", "en")
    max_audio_bytes: int = 25 * 1024 * 1024

    # Kokoro TTS Settings
    kokoro_model_path: str = os.getenv("KOKORO_MODEL_PATH", "models/kokoro/kokoro-v1.0.onnx")
    kokoro_voices_path: str = os.getenv("KOKORO_VOICES_PATH", "models/kokoro/voices-v1.0.bin")
    kokoro_default_voice: str = os.getenv("KOKORO_DEFAULT_VOICE", "af_heart")
    kokoro_default_speed: float = float(os.getenv("KOKORO_DEFAULT_SPEED", "1.0"))
    kokoro_default_lang: str = os.getenv("KOKORO_DEFAULT_LANG", "en-us")

    # Session Memory Settings
    session_max_history_turns: int = int(os.getenv("SESSION_MAX_HISTORY_TURNS", "20"))
    session_db_path: str = os.getenv("SESSION_DB_PATH", "data/sessions.db")

    # Spoken Voice Assistant System Prompt (Simple, Conversational, No Markdown)
    voice_system_prompt: str = os.getenv(
        "VOICE_SYSTEM_PROMPT",
        "You are a helpful, conversational voice assistant. "
        "Provide direct, concise, natural-sounding answers in plain text. "
        "Do not use markdown formatting such as asterisks, hashtags, bullet points, numbered lists, emojis, or code blocks. "
        "Speak as if you are talking in a real-time voice conversation.",
    )

    # Standard Chat Assistant System Prompt (Rich, Markdown, Thorough)
    chat_system_prompt: str = os.getenv(
        "CHAT_SYSTEM_PROMPT",
        "You are a knowledgeable, helpful AI assistant. "
        "Provide thorough, well-structured, and clear answers. "
        "Use GitHub Flavored Markdown, subheadings, bullet points, and code blocks where helpful to make information scannable and easy to read.",
    )


settings = Settings()
