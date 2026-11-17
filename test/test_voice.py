import io
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_transcribe_endpoint():
    with patch("src.api.routers.voice.transcribe_audio_file") as mock_transcribe:
        mock_transcribe.return_value = {
            "text": "Testing audio transcription",
            "language": "en",
            "language_probability": 0.99,
        }

        fake_wav = io.BytesIO(b"RIFF" + b"\x00" * 100)
        response = client.post(
            "/transcribe",
            files={"file": ("test.wav", fake_wav, "audio/wav")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Testing audio transcription"
        assert data["language"] == "en"


def test_transcribe_empty_speech():
    with patch("src.api.routers.voice.transcribe_audio_file") as mock_transcribe:
        mock_transcribe.return_value = {
            "text": "",
            "language": "en",
            "language_probability": 0.0,
        }

        fake_wav = io.BytesIO(b"RIFF" + b"\x00" * 100)
        response = client.post(
            "/transcribe",
            files={"file": ("silent.wav", fake_wav, "audio/wav")},
        )
        assert response.status_code == 200
        assert response.json()["text"] == ""


def test_respond_text_endpoint():
    with patch("src.api.routers.voice.generate_voice_response_with_audio", new_callable=AsyncMock) as mock_voice:
        mock_voice.return_value = ("Madrid is the capital of Spain.", "fake_audio")

        response = client.post(
            "/respond-text",
            json={"text": "Capital of Spain?", "voice": "af_heart", "speed": 1.0},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["transcript"] == "Capital of Spain?"
        assert data["response"] == "Madrid is the capital of Spain."
        assert data["audio_base64"] == "fake_audio"


def test_voice_chat_endpoint():
    with patch("src.api.routers.voice.transcribe_audio_file") as mock_transcribe, \
         patch("src.api.routers.voice.generate_voice_response_with_audio", new_callable=AsyncMock) as mock_voice:

        mock_transcribe.return_value = {
            "text": "What is the capital of France?",
            "language": "en",
            "language_probability": 0.99,
        }
        mock_voice.return_value = ("Paris is the capital of France.", "fake_base64_audio")

        fake_wav = io.BytesIO(b"RIFF" + b"\x00" * 100)
        response = client.post(
            "/voice-chat",
            files={"file": ("query.wav", fake_wav, "audio/wav")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["transcript"] == "What is the capital of France?"
        assert data["response"] == "Paris is the capital of France."
        assert data["audio_base64"] == "fake_base64_audio"
