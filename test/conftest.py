"""
Pytest configuration and fixtures.
Ensures tests use an isolated SQLite test database and never wipe data/sessions.db.
"""

from pathlib import Path
import pytest
from src.services.storage_service import set_db_path


@pytest.fixture(scope="session", autouse=True)
def setup_test_db(tmp_path_factory):
    """Point storage_service to an isolated temporary SQLite database for the entire test run."""
    test_dir = tmp_path_factory.mktemp("test_db")
    test_db = test_dir / "test_sessions.db"
    set_db_path(test_db)
    yield test_db
    set_db_path(None)
