# Local Voice Assistant

A fully local, privacy-respecting AI voice assistant powered by **FastAPI**, **faster-whisper** (STT), **Ollama** (LLM), and **Kokoro** (TTS). Includes an interactive web interface with real-time audio visualization, push-to-talk voice messaging, and speech synthesis.

---

## 🌟 Overview

The **Local Voice Assistant** runs completely on your own machine without relying on external cloud APIs:

1. **Speech-to-Text (STT)**: Powered by `faster-whisper` (`small` model, `int8` CPU quantization by default) for high-accuracy local transcription.
2. **Intelligence (LLM)**: Asynchronously interfaces with a local `Ollama` server (e.g. `qwen3.5:4b`) to generate natural conversational answers.
3. **Text-to-Speech (TTS)**: Built with `kokoro-onnx` using the lightweight, 82M-parameter `Kokoro-82M` neural model offering 54 distinct voices and customizable speech speed. Includes automatic markdown/symbol sanitization so symbols like asterisks, hashtags, bullets, and backticks are cleaned before vocalization.
4. **Interactive Web Interface**: A responsive dark-mode web application featuring push-to-talk and hands-free **Auto-Listen** mode with automatic silence/pause detection (VAD), immediate speech transcription display, real-time waveform visualizer, stop/interrupt controls, and a Kokoro TTS voice studio.

---

## 🏗️ Architecture

```
                                  ┌───────────────────────────────┐
                                  │      Client / Web UI          │
                                  │ (Microphone & Web Audio API)  │
                                  └──────────────┬────────────────┘
                                                 │
                                                 │ HTTP / Multipart Audio / JSON
                                                 ▼
                                  ┌───────────────────────────────┐
                                  │      FastAPI Application      │
                                  │         (src/main.py)         │
                                  └──────────────┬────────────────┘
                                                 │
                   ┌─────────────────────────────┼─────────────────────────────┐
                   ▼                             ▼                             ▼
         ┌───────────────────┐         ┌───────────────────┐         ┌───────────────────┐
         │   faster-whisper   │         │    Ollama API     │         │    Kokoro TTS     │
         │ (Speech-to-Text)  │         │   (Local Model)   │         │ (Text-to-Speech)  │
         │  src/services/    │         │  src/services/    │         │  src/services/    │
         │  transcription_   │         │  llm_service.py   │         │  tts_service.py   │
         │  service.py       │         └───────────────────┘         └───────────────────┘
         └───────────────────┘
```

---

## 📁 Project Structure

```
local-voice-assistant/
├── models/
│   └── kokoro/                     # Kokoro ONNX model and voice weights
│       ├── kokoro-v1.0.onnx
│       └── voices-v1.0.bin
├── src/
│   ├── __init__.py
│   ├── main.py                     # Application entry point & lifespan manager
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routers/                # FastAPI endpoint handlers
│   │   │   ├── __init__.py
│   │   │   ├── chat.py             # Direct text chat endpoint
│   │   │   ├── health.py           # Health check endpoint
│   │   │   ├── tts.py              # Kokoro TTS endpoints (synthesize & voices)
│   │   │   └── voice.py            # STT & voice-chat pipeline
│   │   └── schemas/                # Pydantic request & response models
│   │       ├── __init__.py
│   │       ├── chat.py
│   │       ├── tts.py
│   │       └── voice.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py               # Application settings & environment variables
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_service.py          # Ollama communication service
│   │   ├── transcription_service.py# Whisper model loader & transcriber
│   │   ├── tts_service.py          # Kokoro TTS loader & audio synthesizer
│   │   └── voice_service.py        # Voice pipeline orchestrator
│   └── static/                     # Web UI frontend assets
│       ├── index.html              # Interface layout
│       ├── style.css               # Dark theme styles & visualizer styling
│       └── app.js                  # Audio recorder, visualizer, & API client
├── test/
│   ├── test_chat.py                # LLM chat route tests
│   ├── test_health.py              # Health check tests
│   ├── test_static.py              # Web UI asset tests
│   ├── test_tts.py                 # Kokoro TTS tests
│   └── test_voice.py               # Transcription & voice chat tests
├── pyproject.toml                  # Project metadata & dependencies
├── uv.lock                         # Pinned dependency lockfile
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python**: `>=3.13`
- **uv**: Fast Python package manager ([docs.astral.sh/uv](https://docs.astral.sh/uv/))
- **Ollama**: Running locally with a conversational model (e.g., `ollama run qwen3.5:4b`)

### 2. Install Dependencies
```bash
uv sync
```

### 3. Download Kokoro TTS Models
Ensure the Kokoro model files are present in `models/kokoro/`:
```bash
mkdir -p models/kokoro
curl -fL -o models/kokoro/kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -fL -o models/kokoro/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### 4. Configure Environment (Optional)
Copy the template if you need to customize the Ollama URL, model, or Whisper size:
```bash
cp .env.example .env
```
*(Ensure Ollama is running and the configured model is pulled, e.g. `ollama pull qwen3.5:4b`.)*

### 5. Run the Server
```bash
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```
*(On first startup, `faster-whisper` will automatically download the Whisper `small` model from Hugging Face.)*

### 6. Access the Web Interface
Open your browser and navigate to:
```
http://localhost:8000
```
*(Note: Use `localhost` or `127.0.0.1` so the browser grants microphone access.)*

#### Key Interface Capabilities:
- **Auto-Listen / Hands-Free Mode**: Toggle the `Auto-Listen` button to converse hands-free. The browser detects speech, monitors audio levels, detects pauses (default 1.5s), and automatically sends the utterance to Whisper.
- **Immediate Transcript Preview**: Displays your recognized words in the conversation feed as soon as Whisper processes them, followed by the assistant's answer.
- **Audio Stop & Interrupt**: Dedicated stop controls in the recorder bar, on each message card, and via the `Escape` key to immediately silence voice output.
- **VAD & Sensitivity Customization**: Fine-tune the silence pause threshold (0.8s – 3.0s) and mic sensitivity in the settings drawer.
- **Request / Response Live Logs**: Comprehensive HTTP logging on the server terminal showing incoming prompts, audio upload sizes, recognized transcripts, and outgoing model responses with millisecond latency metrics.

---

## 🌐 API Reference

### Health
- `GET /health`
  - Returns service status: `{"status": "healthy", "message": "..."}`

### Text Chat
- `POST /chat`
  - **Body**: `{"prompt": "Hello assistant!"}`
  - **Response**: `{"response": "Hello! How can I help you today?"}`

### Speech-to-Text
- `POST /transcribe`
  - **Body**: Audio file (Multipart `file` upload or raw audio stream: WAV, MP3, WebM, OGG, FLAC)
  - **Response**: `{"text": "Transcribed text", "language": "en", "language_probability": 0.99}`

### Voice Chat (End-to-End Voice Pipeline)
- `POST /voice-chat?include_audio=true&voice=af_heart&speed=1.0`
  - **Body**: Spoken audio file
  - **Workflow**:
    1. Transcribes audio using `faster-whisper`.
    2. Sends prompt to `Ollama`.
    3. Synthesizes spoken answer via `Kokoro TTS`.
  - **Response**:
    ```json
    {
      "transcript": "What is the speed of light?",
      "response": "The speed of light in a vacuum is approximately 299,792,458 meters per second.",
      "audio_base64": "UklGRi..."
    }
    ```

### Text-to-Speech (Kokoro)
- `GET /tts/voices`
  - Returns list of 54 supported neural voice IDs (e.g. `af_heart`, `am_adam`, `bf_emma`, etc.) and default configuration.
- `POST /tts/synthesize`
  - **Body**: `{"text": "Hello world", "voice": "af_heart", "speed": 1.0, "lang": "en-us"}`
  - **Response**: Raw `audio/wav` binary stream.
- `POST /tts/synthesize-json`
  - **Body**: `{"text": "Hello world", "voice": "af_heart", "speed": 1.0, "lang": "en-us"}`
  - **Response**: `{"audio_base64": "...", "format": "audio/wav", "voice": "af_heart", "sample_rate": 24000}`

---

## ⚙️ Configuration

Set any of the following environment variables to customize behavior:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Address of the local Ollama instance (override in `.env` if using WSL2) |
| `OLLAMA_MODEL` | `qwen3.5:4b` | Model name to invoke in Ollama |
| `OLLAMA_TIMEOUT_SECONDS` | `120.0` | HTTP request timeout for LLM generation |
| `WHISPER_MODEL` | `small` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`) |
| `WHISPER_DEVICE` | `cpu` | Device for Whisper inference (`cpu` or `cuda`) |
| `WHISPER_COMPUTE_TYPE` | `int8` | Model quantization (`int8`, `float16`, `float32`) |
| `WHISPER_LANGUAGE` | `en` | Default transcription language |
| `KOKORO_MODEL_PATH` | `models/kokoro/kokoro-v1.0.onnx` | Path to Kokoro ONNX model file |
| `KOKORO_VOICES_PATH` | `models/kokoro/voices-v1.0.bin` | Path to Kokoro voices binary file |
| `KOKORO_DEFAULT_VOICE` | `af_heart` | Default voice ID for speech synthesis |
| `KOKORO_DEFAULT_SPEED` | `1.0` | Default speech rate multiplier |
| `KOKORO_DEFAULT_LANG` | `en-us` | Default language code for Kokoro |
| `VOICE_SYSTEM_PROMPT` | *(Spoken plain-text instructions)* | System prompt preventing markdown, asterisks, and lists in voice output |
| `CHAT_SYSTEM_PROMPT` | *(Rich markdown instructions)* | System prompt generating structured, thorough markdown answers for text chat |

---

## 🧪 Running Tests

Execute the unit and integration test suite:

```bash
uv run pytest -v
```

---

## 🚀 Potential Enhancements & Future Roadmap

Here are recommended future directions and architectural upgrades for the project:

1. **WebSocket / Full-Duplex Real-Time Streaming**:
   - Stream audio chunks continuously from browser mic to server.
   - Stream LLM tokens directly into Kokoro's `create_stream()` generator to begin speaking before the full response is finished, cutting latency from ~2s to <500ms.
2. **Wake Word Detection**:
   - Add local on-device wake-word detection (e.g., using `openWakeWord`) so the assistant can trigger automatically on "Hey Assistant" without needing a button press.
3. **Multi-Turn Conversation Memory**:
   - Introduce session management (e.g., session IDs via Redis or in-memory LRU cache) to maintain conversational history across multiple turns.
4. **Local Tools & Function Calling**:
   - Equip Ollama with function-calling capabilities for real-world tasks (e.g., local system controls, weather checks, calendar queries, web searches).
5. **GPU Acceleration**:
   - Provide preconfigured options for CUDA / ROCm acceleration for both Whisper and ONNX Runtime (`onnxruntime-gpu`) for sub-second generation on systems with dedicated GPUs.
6. **Containerization**:
   - Provide a `Dockerfile` and `docker-compose.yml` pre-bundling models and services for one-click deployment.

