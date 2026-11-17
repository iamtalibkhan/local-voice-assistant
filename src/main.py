import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routers import chat, health, session, tts, voice
from src.services.transcription_service import load_model as load_whisper_model
from src.services.tts_service import load_tts_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Loading Whisper model during startup...")
    try:
        await asyncio.to_thread(load_whisper_model)
        logger.info("Whisper model is ready")
    except Exception as exc:
        logger.warning("Whisper model failed to load during startup: %s", exc)

    logger.info("Loading Kokoro TTS model during startup...")
    try:
        await asyncio.to_thread(load_tts_model)
        logger.info("Kokoro TTS model is ready")
    except Exception as exc:
        logger.warning("Kokoro TTS model failed to load during startup: %s", exc)

    yield


app = FastAPI(
    title="Local Voice Assistant",
    description="A fully local AI-powered voice assistant with STT (Whisper), LLM (Ollama), and TTS (Kokoro)",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    path = request.url.path
    # Skip verbose logs for static web assets like CSS/JS, but disable caching during dev
    if path.startswith("/static"):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    start_time = time.perf_counter()
    client_host = request.client.host if request.client else "unknown"
    query = str(request.url.query)
    query_str = f"?{query}" if query else ""

    logger.info("--> [START %s] %s%s (client: %s)", request.method, path, query_str, client_host)

    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "<-- [END %s] %s%s status=%d (took %.2fms)",
            request.method,
            path,
            query_str,
            response.status_code,
            duration_ms,
        )
        return response
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.exception(
            "<-- [FAIL %s] %s%s error=%s (took %.2fms)",
            request.method,
            path,
            query_str,
            exc,
            duration_ms,
        )
        raise


# Static files and Web UI
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(
            index_file,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return {"message": "Local Voice Assistant API is running. Web UI not found."}


# API Routers
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(voice.router)
app.include_router(tts.router)
app.include_router(session.router)
