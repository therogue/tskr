"""
Shared pytest fixtures for backend tests.
Uses temp file SQLite database for isolation.
"""
import pytest
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlmodel import SQLModel

import database


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

    # Create all ORM tables (tasks, category_sequences, conversations)
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

    # Skip alembic in tests - tables already created by test_db fixture
    monkeypatch.setattr(database, "init_db", lambda: None)

    with TestClient(main.app) as client:
        yield client
