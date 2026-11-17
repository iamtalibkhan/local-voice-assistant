from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_chat_success():
    with patch("src.api.routers.chat.generate_chat_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Hello! I am your AI assistant."

        response = client.post("/chat", json={"prompt": "Hello"})
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Hello! I am your AI assistant."


def test_chat_empty_prompt():
    response = client.post("/chat", json={"prompt": ""})
    assert response.status_code == 422
