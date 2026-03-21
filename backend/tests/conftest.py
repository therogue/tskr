"""
Shared pytest fixtures for backend tests.
Uses temp file SQLite database for isolation.

Directory layout:
  tests/unit/  — deterministic tests (no API calls)
  tests/llm/   — tests that hit the Anthropic API (skipped by default)

Run unit tests only (default):  pytest
Run everything:                 pytest --run-llm
Run LLM tests only:             pytest -m llm --run-llm
"""
import pytest
import sys
import os

# Add backend to path so test files can `import database`, `import main`, etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlmodel import SQLModel

import database


# ---------------------------------------------------------------------------
# --run-llm flag: LLM tests are skipped unless the user opts in
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--run-llm", action="store_true", default=False,
        help="Run tests that make real LLM API calls (requires ANTHROPIC_API_KEY)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-llm"):
        return
    skip_llm = pytest.mark.skip(reason="needs --run-llm flag to run")
    for item in items:
        if "llm" in item.keywords:
            item.add_marker(skip_llm)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db(monkeypatch, tmp_path):
    """
    Create an isolated test database for each test.
    Uses a temp file (not :memory:) because database.py opens new sessions per operation.
    """
    db_path = str(tmp_path / "test.db")
    db_url = f"sqlite:///{db_path}"
    test_engine = create_engine(db_url)

    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "init_db", lambda: None)

    SQLModel.metadata.create_all(test_engine)

    yield db_path


@pytest.fixture
def app_client(test_db, monkeypatch):
    """
    Create a test client for the FastAPI app.
    Mocks init_db to skip alembic migrations.
    """
    from fastapi.testclient import TestClient
    import main

    monkeypatch.setattr(database, "init_db", lambda: None)

    with TestClient(main.app) as client:
        yield client
