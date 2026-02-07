"""
Shared pytest fixtures for backend tests.
Uses in-memory SQLite database for isolation.
"""
import pytest
import sqlite3
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database


@pytest.fixture
def test_db(monkeypatch, tmp_path):
    """
    Create an isolated test database for each test.
    Uses a temp file (not :memory:) because database.py opens new connections per operation.
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    monkeypatch.setattr(database, "init_db", lambda: None)

    # Create tables directly (skip alembic for tests)
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            task_key TEXT NOT NULL,
            category TEXT NOT NULL,
            task_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            scheduled_date TEXT,
            recurrence_rule TEXT,
            created_at TEXT NOT NULL,
            is_template INTEGER DEFAULT 0,
            parent_task_id TEXT
        );

        CREATE TABLE category_sequences (
            category TEXT PRIMARY KEY,
            next_number INTEGER NOT NULL
        );

        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY,
            messages TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

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

    # Re-import to pick up monkeypatched database
    with TestClient(main.app) as client:
        yield client
