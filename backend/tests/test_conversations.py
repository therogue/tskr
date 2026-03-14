"""
Tests for conversation history feature (Issue #26).
Covers: list_conversations, get_conversation_by_id, GET /conversations, GET /conversations/{id}.
"""
import json
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import (
    new_conversation,
    save_conversation,
    get_conversation_by_id,
    list_conversations,
)


class TestListConversations:
    """Tests for list_conversations() DB function."""

    def test_empty_returns_empty_list(self, test_db):
        assert list_conversations() == []

    def test_returns_all_conversations(self, test_db):
        new_conversation()
        new_conversation()
        new_conversation()
        result = list_conversations()
        assert len(result) == 3

    def test_ordered_by_updated_at_desc(self, test_db):
        id1 = new_conversation()
        id2 = new_conversation()
        id3 = new_conversation()
        # Touch id1 last so it should appear first
        save_conversation(id1, json.dumps([{"role": "user", "content": "hello"}]))
        result = list_conversations()
        assert result[0]["id"] == id1
        assert {r["id"] for r in result} == {id1, id2, id3}

    def test_each_item_has_required_fields(self, test_db):
        new_conversation()
        result = list_conversations()
        assert len(result) == 1
        item = result[0]
        assert "id" in item
        assert "title" in item
        assert "updated_at" in item

    def test_limit_restricts_results(self, test_db):
        for _ in range(5):
            new_conversation()
        result = list_conversations(limit=3)
        assert len(result) == 3

    def test_limit_none_returns_all(self, test_db):
        for _ in range(5):
            new_conversation()
        assert len(list_conversations(limit=None)) == 5

    def test_title_reflects_saved_conversation(self, test_db):
        conv_id = new_conversation()
        save_conversation(conv_id, json.dumps([{"role": "user", "content": "Plan my week"}]), title="Plan my week")
        result = list_conversations()
        assert result[0]["title"] == "Plan my week"

    def test_untitled_default(self, test_db):
        new_conversation()
        result = list_conversations()
        assert result[0]["title"] == "Untitled"


class TestGetConversationById:
    """Tests for get_conversation_by_id() DB function."""

    def test_returns_correct_conversation(self, test_db):
        id1 = new_conversation()
        id2 = new_conversation()
        save_conversation(id1, json.dumps([{"role": "user", "content": "msg for id1"}]))
        save_conversation(id2, json.dumps([{"role": "user", "content": "msg for id2"}]))

        result = get_conversation_by_id(id1)
        assert result["id"] == id1
        assert result["messages"][0]["content"] == "msg for id1"

    def test_returns_empty_messages_for_new_conversation(self, test_db):
        conv_id = new_conversation()
        result = get_conversation_by_id(conv_id)
        assert result["id"] == conv_id
        assert result["messages"] == []

    def test_missing_id_returns_none_id(self, test_db):
        result = get_conversation_by_id(9999)
        assert result["id"] is None
        assert result["messages"] == []

    def test_messages_roundtrip(self, test_db):
        conv_id = new_conversation()
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        save_conversation(conv_id, json.dumps(msgs))
        result = get_conversation_by_id(conv_id)
        assert result["messages"] == msgs


class TestConversationsAPI:
    """Tests for GET /conversations and GET /conversations/{id} endpoints."""

    def test_list_endpoint_empty(self, app_client):
        res = app_client.get("/conversations")
        assert res.status_code == 200
        assert res.json() == []

    def test_list_endpoint_returns_conversations(self, app_client):
        app_client.post("/conversation/new")
        app_client.post("/conversation/new")
        res = app_client.get("/conversations")
        assert res.status_code == 200
        # At least 2 conversations (startup may create one too)
        assert len(res.json()) >= 2

    def test_list_endpoint_limit_param(self, app_client):
        for _ in range(5):
            app_client.post("/conversation/new")
        res = app_client.get("/conversations?limit=3")
        assert res.status_code == 200
        assert len(res.json()) == 3

    def test_list_endpoint_item_shape(self, app_client):
        app_client.post("/conversation/new")
        res = app_client.get("/conversations")
        assert res.status_code == 200
        item = res.json()[0]
        assert "id" in item
        assert "title" in item
        assert "updated_at" in item

    def test_get_by_id_endpoint(self, app_client):
        created = app_client.post("/conversation/new").json()
        conv_id = created["id"]
        res = app_client.get(f"/conversations/{conv_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == conv_id
        assert "messages" in data

    def test_get_by_id_endpoint_404(self, app_client):
        res = app_client.get("/conversations/99999")
        assert res.status_code == 404

    def test_get_by_id_returns_saved_messages(self, app_client):
        # Start a new conversation via the API
        created = app_client.post("/conversation/new").json()
        conv_id = created["id"]

        # Save a message by calling /chat is not practical without mocking Claude.
        # Instead call save_conversation directly through the DB function.
        import database
        database.save_conversation(
            conv_id,
            json.dumps([{"role": "user", "content": "test message"}]),
        )

        res = app_client.get(f"/conversations/{conv_id}")
        assert res.status_code == 200
        msgs = res.json()["messages"]
        assert len(msgs) == 1
        assert msgs[0]["content"] == "test message"

    def test_list_ordered_most_recent_first(self, app_client):
        id1 = app_client.post("/conversation/new").json()["id"]
        id2 = app_client.post("/conversation/new").json()["id"]
        # Touch id1 to make it most recent
        import database
        database.save_conversation(id1, json.dumps([{"role": "user", "content": "bump"}]))

        res = app_client.get("/conversations?limit=2")
        ids = [item["id"] for item in res.json()]
        assert ids[0] == id1


class TestAppOpenFreshConversation:
    """
    Tests for the app-open behaviour: POST /conversation/new is called on mount,
    clearing the chat window and starting a fresh conversation while preserving
    the previous conversation in history.
    """

    def test_app_open_returns_new_conversation_id(self, app_client):
        """POST /conversation/new returns a new id (simulates app mount)."""
        res = app_client.post("/conversation/new")
        assert res.status_code == 200
        assert "id" in res.json()
        assert res.json()["id"] is not None

    def test_app_open_new_conversation_has_no_messages(self, app_client):
        """New conversation starts empty — chat window shows no messages."""
        new_id = app_client.post("/conversation/new").json()["id"]
        res = app_client.get(f"/conversations/{new_id}")
        assert res.status_code == 200
        assert res.json()["messages"] == []

    def test_app_open_creates_distinct_conversation(self, app_client):
        """Each app open produces a different conversation id."""
        id1 = app_client.post("/conversation/new").json()["id"]
        id2 = app_client.post("/conversation/new").json()["id"]
        assert id1 != id2

    def test_previous_conversation_preserved_in_history(self, app_client):
        """Previous conversation with messages appears in GET /conversations after app open."""
        import database

        old_id = app_client.post("/conversation/new").json()["id"]
        database.save_conversation(old_id, json.dumps([{"role": "user", "content": "yesterday's task"}]))

        # Simulate reopening the app
        app_client.post("/conversation/new")

        history_ids = [c["id"] for c in app_client.get("/conversations").json()]
        assert old_id in history_ids

    def test_previous_conversation_messages_intact_after_app_open(self, app_client):
        """Previous conversation messages are retrievable by id after app open."""
        import database

        old_id = app_client.post("/conversation/new").json()["id"]
        database.save_conversation(old_id, json.dumps([{"role": "user", "content": "keep this"}]))

        app_client.post("/conversation/new")

        res = app_client.get(f"/conversations/{old_id}")
        assert res.status_code == 200
        assert res.json()["messages"][0]["content"] == "keep this"
