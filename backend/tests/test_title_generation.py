"""
Tests for LLM-based conversation title generation (Issue #53).
Covers: get_conversation_title, update_conversation_title, PATCH endpoint,
generate_conversation_title helper, and /chat title integration.
"""
import asyncio
import json
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import (
    new_conversation,
    save_conversation,
    get_conversation_title,
    update_conversation_title,
)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

class TestGetConversationTitle:
    def test_new_conversation_is_untitled(self, test_db):
        conv_id = new_conversation()
        assert get_conversation_title(conv_id) == "Untitled"

    def test_missing_conversation_returns_none(self, test_db):
        assert get_conversation_title(9999) is None

    def test_reflects_updated_title(self, test_db):
        conv_id = new_conversation()
        update_conversation_title(conv_id, "My New Title")
        assert get_conversation_title(conv_id) == "My New Title"


class TestUpdateConversationTitle:
    def test_sets_title(self, test_db):
        conv_id = new_conversation()
        update_conversation_title(conv_id, "Task Planning Session")
        assert get_conversation_title(conv_id) == "Task Planning Session"

    def test_overwrites_existing_title(self, test_db):
        conv_id = new_conversation()
        update_conversation_title(conv_id, "First")
        update_conversation_title(conv_id, "Second")
        assert get_conversation_title(conv_id) == "Second"

    def test_missing_conversation_is_noop(self, test_db):
        # Should not raise; silently ignores unknown id
        update_conversation_title(9999, "Ghost Title")


# ---------------------------------------------------------------------------
# PATCH /conversations/{id}/title endpoint
# ---------------------------------------------------------------------------

class TestPatchTitleEndpoint:
    def test_success_returns_id_and_title(self, app_client):
        conv_id = app_client.post("/conversation/new").json()["id"]
        res = app_client.patch(
            f"/conversations/{conv_id}/title",
            json={"title": "Weekly Review"},
        )
        assert res.status_code == 200
        assert res.json() == {"id": conv_id, "title": "Weekly Review"}

    def test_title_persisted_in_db(self, app_client):
        conv_id = app_client.post("/conversation/new").json()["id"]
        app_client.patch(f"/conversations/{conv_id}/title", json={"title": "Persisted"})
        assert get_conversation_title(conv_id) == "Persisted"

    def test_empty_string_title_returns_422(self, app_client):
        conv_id = app_client.post("/conversation/new").json()["id"]
        res = app_client.patch(f"/conversations/{conv_id}/title", json={"title": ""})
        assert res.status_code == 422

    def test_whitespace_only_title_returns_422(self, app_client):
        conv_id = app_client.post("/conversation/new").json()["id"]
        res = app_client.patch(f"/conversations/{conv_id}/title", json={"title": "   "})
        assert res.status_code == 422

    def test_missing_title_field_returns_422(self, app_client):
        conv_id = app_client.post("/conversation/new").json()["id"]
        res = app_client.patch(f"/conversations/{conv_id}/title", json={})
        assert res.status_code == 422

    def test_title_is_stripped(self, app_client):
        conv_id = app_client.post("/conversation/new").json()["id"]
        res = app_client.patch(
            f"/conversations/{conv_id}/title",
            json={"title": "  Trimmed  "},
        )
        assert res.json()["title"] == "Trimmed"


# ---------------------------------------------------------------------------
# generate_conversation_title helper
# ---------------------------------------------------------------------------

class TestGenerateConversationTitle:
    """Unit tests for the async title-generation helper."""

    def _make_mock_client(self, title_text: str):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=title_text)]
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        return mock_client

    def test_returns_title_on_success(self, monkeypatch):
        import main
        monkeypatch.setattr(main, "client", self._make_mock_client("Add Weekly Tasks"))
        result = asyncio.run(main.generate_conversation_title([
            {"role": "user", "content": "Add my weekly tasks"},
            {"role": "assistant", "content": "Done, added 3 tasks."},
        ]))
        assert result == "Add Weekly Tasks"

    def test_strips_whitespace_from_title(self, monkeypatch):
        import main
        monkeypatch.setattr(main, "client", self._make_mock_client("  Padded Title  "))
        result = asyncio.run(main.generate_conversation_title([
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]))
        assert result == "Padded Title"

    def test_returns_none_when_no_user_message(self, monkeypatch):
        import main
        monkeypatch.setattr(main, "client", self._make_mock_client("Should Not Be Called"))
        result = asyncio.run(main.generate_conversation_title([
            {"role": "assistant", "content": "hi"},
        ]))
        assert result is None

    def test_works_with_user_message_only(self, monkeypatch):
        import main
        monkeypatch.setattr(main, "client", self._make_mock_client("Buy Groceries"))
        result = asyncio.run(main.generate_conversation_title([
            {"role": "user", "content": "buy groceries today"},
        ]))
        assert result == "Buy Groceries"

    def test_returns_none_on_api_error(self, monkeypatch):
        import main
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("network error"))
        monkeypatch.setattr(main, "client", mock_client)
        result = asyncio.run(main.generate_conversation_title([
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]))
        assert result is None

    def test_returns_none_on_empty_response(self, monkeypatch):
        import main
        monkeypatch.setattr(main, "client", self._make_mock_client(""))
        result = asyncio.run(main.generate_conversation_title([
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]))
        assert result is None


# ---------------------------------------------------------------------------
# /chat title integration
# ---------------------------------------------------------------------------

def _make_chat_client(task_response_json: str):
    """Return a mock AsyncAnthropic client for the main task-processing LLM call."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=task_response_json)]
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    return mock_client


_NOOP_RESPONSE = json.dumps({"operation": "none", "message": "Got it"})


class TestChatTitleIntegration:
    """Integration tests for title generation triggered from POST /chat."""

    def _setup(self, monkeypatch, generated_title=None):
        """Patch Claude client and generate_conversation_title for /chat tests."""
        import main
        monkeypatch.setattr(main, "ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(main, "client", _make_chat_client(_NOOP_RESPONSE))
        monkeypatch.setattr(
            main,
            "generate_conversation_title",
            AsyncMock(return_value=generated_title),
        )

    def test_title_returned_in_response(self, app_client, monkeypatch):
        self._setup(monkeypatch, generated_title="Add Weekly Tasks")
        conv_id = app_client.post("/conversation/new").json()["id"]
        res = app_client.post("/chat", json={
            "messages": [{"role": "user", "content": "Add my weekly tasks"}],
            "conversation_id": conv_id,
        })
        assert res.status_code == 200
        assert res.json()["title"] == "Add Weekly Tasks"

    def test_generated_title_persisted(self, app_client, monkeypatch):
        self._setup(monkeypatch, generated_title="Schedule Team Meeting")
        conv_id = app_client.post("/conversation/new").json()["id"]
        app_client.post("/chat", json={
            "messages": [{"role": "user", "content": "Schedule a meeting"}],
            "conversation_id": conv_id,
        })
        assert get_conversation_title(conv_id) == "Schedule Team Meeting"

    def test_title_generation_called_once_per_conversation(self, app_client, monkeypatch):
        import main
        self._setup(monkeypatch, generated_title="First Turn Title")
        gen_mock = AsyncMock(return_value="First Turn Title")
        monkeypatch.setattr(main, "generate_conversation_title", gen_mock)

        conv_id = app_client.post("/conversation/new").json()["id"]
        messages = [{"role": "user", "content": "first message"}]

        # First turn — should call generate_conversation_title
        app_client.post("/chat", json={"messages": messages, "conversation_id": conv_id})
        assert gen_mock.call_count == 1

        # Second turn — title is no longer "Untitled", should not call again
        messages.append({"role": "assistant", "content": "Got it"})
        messages.append({"role": "user", "content": "second message"})
        app_client.post("/chat", json={"messages": messages, "conversation_id": conv_id})
        assert gen_mock.call_count == 1

    def test_fallback_title_when_llm_returns_none(self, app_client, monkeypatch):
        self._setup(monkeypatch, generated_title=None)
        conv_id = app_client.post("/conversation/new").json()["id"]
        user_msg = "A" * 60  # longer than 50 chars to test truncation
        app_client.post("/chat", json={
            "messages": [{"role": "user", "content": user_msg}],
            "conversation_id": conv_id,
        })
        # save_conversation fallback: first 50 chars of user message
        assert get_conversation_title(conv_id) == user_msg[:50]

    def test_no_conversation_id_returns_none_title(self, app_client, monkeypatch):
        self._setup(monkeypatch, generated_title="Should Not Appear")
        res = app_client.post("/chat", json={
            "messages": [{"role": "user", "content": "hello"}],
            "conversation_id": None,
        })
        assert res.status_code == 200
        assert res.json()["title"] is None
