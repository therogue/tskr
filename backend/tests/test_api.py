"""
Tests for FastAPI endpoints in main.py.
Does not test /chat endpoint (requires mocking Claude API).
Uses create_task_db to set up test data since POST /tasks was removed.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import create_task_db


class TestTaskEndpoints:
    """Tests for /tasks endpoints."""

    def test_get_tasks_empty(self, app_client):
        """GET /tasks returns empty list when no tasks."""
        response = app_client.get("/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_tasks_returns_tasks(self, test_db, app_client):
        """GET /tasks returns created tasks."""
        create_task_db("id-1", "Task 1", "T")
        create_task_db("id-2", "Task 2", "T")

        response = app_client.get("/tasks")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 2

    def test_update_task_title(self, test_db, app_client):
        """PATCH /tasks/{id} updates title."""
        create_task_db("id-1", "Old title", "T")

        response = app_client.patch("/tasks/id-1", json={
            "title": "New title"
        })
        assert response.status_code == 200
        assert response.json()["title"] == "New title"

    def test_update_task_completed(self, test_db, app_client):
        """PATCH /tasks/{id} marks task completed."""
        create_task_db("id-1", "Complete me", "T")

        response = app_client.patch("/tasks/id-1", json={
            "completed": True
        })
        assert response.status_code == 200
        assert response.json()["completed"] is True

    def test_update_task_not_found(self, app_client):
        """PATCH /tasks/{id} returns 404 for nonexistent task."""
        response = app_client.patch("/tasks/nonexistent", json={
            "title": "New title"
        })
        assert response.status_code == 404

    def test_delete_task(self, test_db, app_client):
        """DELETE /tasks/{id} removes task."""
        create_task_db("id-1", "Delete me", "T")

        response = app_client.delete("/tasks/id-1")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify task is gone
        tasks = app_client.get("/tasks").json()
        assert len(tasks) == 0

    def test_delete_task_not_found(self, app_client):
        """DELETE /tasks/{id} returns 404 for nonexistent task."""
        response = app_client.delete("/tasks/nonexistent")
        assert response.status_code == 404


class TestConversationEndpoint:
    """Tests for /conversation endpoint."""

    def test_get_conversation_empty(self, app_client):
        """GET /conversation returns empty list when no conversation."""
        response = app_client.get("/conversation")
        assert response.status_code == 200
        assert response.json() == []


class TestRecurringTaskViaAPI:
    """Test recurring task behavior through API."""

    def test_complete_recurring_task_advances(self, test_db, app_client):
        """Completing recurring task via PATCH advances date."""
        create_task_db("id-1", "Daily task", "D", "2025-01-20", "daily")

        response = app_client.patch("/tasks/id-1", json={
            "completed": True
        })

        # Should advance date, not mark complete
        assert response.status_code == 200
        data = response.json()
        assert data["completed"] is False
        assert data["scheduled_date"] == "2025-01-21"
