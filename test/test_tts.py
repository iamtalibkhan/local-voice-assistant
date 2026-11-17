import base64
from fastapi.testclient import TestClient

from src.main import app
from src.services.tts_service import clean_text_for_tts

client = TestClient(app)


def test_clean_text_for_tts_strips_markdown():
    raw_text = (
        "### Top News 🚀\n"
        "Here is **very important** info:\n"
        "* Item 1 with *italics*\n"
        "* Item 2 with #1 ranking & 50% discount\n"
        "Check [our docs](https://example.com) and run `uv sync`."
    )
    cleaned = clean_text_for_tts(raw_text)

    # Must not contain asterisks or hashes
    assert "*" not in cleaned
    assert "#" not in cleaned
    assert "`" not in cleaned
    assert "https://example.com" not in cleaned
    assert "Top News" in cleaned
    assert "very important" in cleaned
    assert "Item 1 with italics" in cleaned
    assert "and" in cleaned  # & converted to and
    assert "percent" in cleaned  # % converted to percent
    assert "our docs" in cleaned
    assert "uv sync" in cleaned


def test_clean_text_for_tts_empty():
    assert clean_text_for_tts("") == ""
    assert clean_text_for_tts("   ") == ""


def test_list_voices():
    response = client.get("/tts/voices")
    assert response.status_code == 200
    data = response.json()
    assert "voices" in data
    assert isinstance(data["voices"], list)
    assert data["total"] > 0
    assert "af_heart" in data["voices"]
    assert data["default_voice"] == "af_heart"


def test_synthesize_wav():
    response = client.post(
        "/tts/synthesize",
        json={"text": "Test synthesis.", "voice": "af_heart", "speed": 1.0},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert len(response.content) > 1000
    # Check WAV header RIFF
    assert response.content[:4] == b"RIFF"


def test_synthesize_json():
    response = client.post(
        "/tts/synthesize-json",
        json={"text": "Hello world with **bold** and #tag.", "voice": "af_heart", "speed": 1.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert "audio_base64" in data
    assert data["format"] == "audio/wav"
    assert data["sample_rate"] == 24000
    assert data["voice"] == "af_heart"

    # Decode and check RIFF signature
    audio_bytes = base64.b64decode(data["audio_base64"])
    assert audio_bytes[:4] == b"RIFF"
