"""
Tests for session memory — persistent SQLite backend.
"""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.session_service import SessionManager, session_manager
from src.services.storage_service import db_clear_all

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe the SQLite session DB before every test for isolation."""
    db_clear_all()
    # Reset max_history_turns to default between tests
    session_manager.max_history_turns = 20
    yield
    db_clear_all()


# ---------------------------------------------------------------------------
# Unit tests — SessionManager
# ---------------------------------------------------------------------------

def test_session_manager_add_and_reset():
    sid = "test-session-1"
    assert session_manager.get_history(sid) == []

    session_manager.add_turn(sid, "Hello", "Hi there!")
    history = session_manager.get_history(sid)
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "Hello"}
    assert history[1] == {"role": "assistant", "content": "Hi there!"}

    session_manager.reset_session(sid)
    assert session_manager.get_history(sid) == []


def test_session_manager_turn_capping():
    sid = "test-session-cap"
    session_manager.max_history_turns = 2  # cap at 2 turns / 4 messages

    # Add 3 turns (6 messages) → oldest pair should be evicted
    for i in range(3):
        session_manager.add_turn(sid, f"User {i}", f"Assistant {i}")

    history = session_manager.get_history(sid)
    assert len(history) == 4
    assert history[0]["content"] == "User 1"
    assert history[-1]["content"] == "Assistant 2"


def test_history_persists_across_new_manager_instance():
    """Core guarantee: a new SessionManager reads the same DB."""
    sid = "persist-test"
    session_manager.add_turn(sid, "Remembered", "Yes I remember")

    # Create a fresh manager — no in-memory state
    fresh = SessionManager()
    history = fresh.get_history(sid)
    assert len(history) == 2
    assert history[0]["content"] == "Remembered"
    assert history[1]["content"] == "Yes I remember"


def test_multiple_sessions_are_isolated():
    session_manager.add_turn("alice", "Alice Q", "Alice A")
    session_manager.add_turn("bob",   "Bob Q",   "Bob A")

    alice = session_manager.get_history("alice")
    bob   = session_manager.get_history("bob")

    assert len(alice) == 2 and alice[0]["content"] == "Alice Q"
    assert len(bob)   == 2 and bob[0]["content"]   == "Bob Q"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

def test_session_reset_endpoint():
    sid = "test-endpoint-reset"
    session_manager.add_turn(sid, "Ping", "Pong")
    assert len(session_manager.get_history(sid)) == 2

    resp = client.post("/session/reset", json={"session_id": sid})
    assert resp.status_code == 200
    assert resp.json()["session_id"] == sid
    assert session_manager.get_history(sid) == []


def test_session_info_endpoint():
    sid = "test-info-session"
    session_manager.add_turn(sid, "Question", "Answer")

    resp = client.get(f"/session/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == sid
    assert data["message_count"] == 2
    assert data["turn_count"] == 1


def test_chat_without_session_id_defaults_to_default_and_maintains_history():
    with patch("src.services.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Response 1"
        client.post("/chat", json={"prompt": "Turn 1"})

    history = session_manager.get_history("default")
    assert len(history) == 2
    assert history[0]["content"] == "Turn 1"
    assert history[1]["content"] == "Response 1"

    # Next request should receive the previous turn in history
    with patch("src.services.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Response 2"
        client.post("/chat", json={"prompt": "Turn 2"})

        mock_llm.assert_called_once()
        _, kwargs = mock_llm.call_args
        assert kwargs["history"] == [
            {"role": "user",      "content": "Turn 1"},
            {"role": "assistant", "content": "Response 1"},
        ]

    assert len(session_manager.get_history("default")) == 4


# ---------------------------------------------------------------------------
# Logging tests
# ---------------------------------------------------------------------------

def test_session_manager_logs_history_and_trimming(caplog):
    sid = "test-log-session"
    session_manager.max_history_turns = 1  # 1 turn = 2 messages

    with caplog.at_level(logging.INFO):
        # Turn 1 added
        session_manager.add_turn(sid, "User Q1", "Assistant A1")
        assert "Added turn to session" in caplog.text

        # History fed
        history = session_manager.get_history(sid)
        assert len(history) == 2
        assert "Feeding session history" in caplog.text

        # Turn 2 triggers eviction of turn 1
        session_manager.add_turn(sid, "User Q2", "Assistant A2")
        assert "exceeded limit of 1 turn(s)" in caplog.text
        assert "Removed" in caplog.text

        history_after = session_manager.get_history(sid)
        assert len(history_after) == 2
        assert history_after[0]["content"] == "User Q2"
        assert history_after[1]["content"] == "Assistant A2"


def test_list_and_create_sessions_api():
    # 1. Create a session via POST
    res = client.post("/session", json={"session_id": "sess_1", "title": "My Custom Chat"})
    assert res.status_code == 200
    created = res.json()
    assert created["id"] == "sess_1"
    assert created["title"] == "My Custom Chat"

    # 2. Add turn via chat or add_turn
    session_manager.add_turn("sess_1", "User prompt here", "Assistant response here")

    # 3. List sessions
    list_res = client.get("/session")
    assert list_res.status_code == 200
    sessions = list_res.json()
    assert len(sessions) >= 1
    found = next((s for s in sessions if s["id"] == "sess_1"), None)
    assert found is not None
    assert found["title"] == "My Custom Chat"
    assert found["message_count"] == 2


def test_pin_and_update_session_api():
    client.post("/session", json={"session_id": "pin_test", "title": "Pin Test"})

    # Toggle pin ON
    pin_res = client.post("/session/pin_test/pin")
    assert pin_res.status_code == 200
    assert pin_res.json()["is_pinned"] is True

    # Update title
    update_res = client.patch("/session/pin_test", json={"title": "Renamed Chat"})
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Renamed Chat"

    # Toggle pin OFF
    pin_res2 = client.post("/session/pin_test/pin")
    assert pin_res2.status_code == 200
    assert pin_res2.json()["is_pinned"] is False


def test_delete_session_api():
    client.post("/session", json={"session_id": "del_test", "title": "Delete Me"})
    session_manager.add_turn("del_test", "Hi", "Bye")

    del_res = client.delete("/session/del_test")
    assert del_res.status_code == 200

    # Ensure it no longer appears in list
    list_res = client.get("/session")
    sessions = list_res.json()
    assert not any(s["id"] == "del_test" for s in sessions)

