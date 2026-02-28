"""
Tests for prompt category handling: LLM should recognize project names as task categories.

Coverage:
- Prompt content: correct instructions present for project/category phrasing
- execute_operation: category field is respected, normalized, and defaults correctly
- strip_markdown_: JSON extraction from LLM response
- execute_operation sad paths: missing task, missing title, unknown operation
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import create_task_db, get_all_tasks
from prompts import SYSTEM_PROMPT
from main import execute_operation, strip_markdown_


# ---------------------------------------------------------------------------
# Prompt content — static checks that the right instructions are present
# ---------------------------------------------------------------------------

class TestPromptProjectPhrasing:
    """Prompt must instruct the LLM to map project/category phrasings to category field."""

    def test_prompt_mentions_project_x_phrasing(self):
        assert "project X" in SYSTEM_PROMPT or "project" in SYSTEM_PROMPT.lower()

    def test_prompt_covers_add_to_project(self):
        assert "add to project" in SYSTEM_PROMPT.lower()

    def test_prompt_covers_for_project(self):
        assert "for project" in SYSTEM_PROMPT.lower()

    def test_prompt_covers_in_project(self):
        assert "in project" in SYSTEM_PROMPT.lower()

    def test_prompt_covers_category_phrasing(self):
        assert "category X" in SYSTEM_PROMPT or "category" in SYSTEM_PROMPT.lower()

    def test_prompt_covers_under_phrasing(self):
        assert "under X" in SYSTEM_PROMPT or "under" in SYSTEM_PROMPT.lower()

    def test_prompt_covers_tag_phrasing(self):
        assert "tag X" in SYSTEM_PROMPT or "tag" in SYSTEM_PROMPT.lower()

    def test_prompt_mentions_uppercase_normalization(self):
        assert "uppercase" in SYSTEM_PROMPT.lower() or "UPPERCASE" in SYSTEM_PROMPT

    def test_prompt_still_has_today_placeholder(self):
        # Regression: ensure prior placeholder wasn't accidentally removed
        assert "{today}" in SYSTEM_PROMPT

    def test_prompt_does_not_restrict_categories_to_T_D_M_only(self):
        # Prompt should NOT say "only T, D, M are allowed"
        assert "only T, D, M" not in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# execute_operation — category handling
# ---------------------------------------------------------------------------

class TestExecuteOperationCategory:
    """execute_operation must use the category from the parsed LLM response."""

    def test_custom_category_is_stored(self, test_db):
        today = "2026-02-28"
        execute_operation(
            {"operation": "create", "title": "Build login page", "category": "P", "message": "ok"},
            today,
        )
        tasks = get_all_tasks()
        assert any(t.category == "P" for t in tasks)

    def test_project_name_as_category(self, test_db):
        today = "2026-02-28"
        execute_operation(
            {"operation": "create", "title": "Write tests", "category": "BACKEND", "message": "ok"},
            today,
        )
        tasks = get_all_tasks()
        assert any(t.category == "BACKEND" for t in tasks)

    def test_lowercase_category_is_uppercased(self, test_db):
        # execute_operation does .upper() on category
        today = "2026-02-28"
        execute_operation(
            {"operation": "create", "title": "Deploy app", "category": "work", "message": "ok"},
            today,
        )
        tasks = get_all_tasks()
        assert any(t.category == "WORK" for t in tasks)

    def test_null_category_defaults_to_T(self, test_db):
        today = "2026-02-28"
        execute_operation(
            {"operation": "create", "title": "No category task", "category": None, "message": "ok"},
            today,
        )
        tasks = get_all_tasks()
        assert any(t.title == "No category task" and t.category == "T" for t in tasks)

    def test_missing_category_key_defaults_to_T(self, test_db):
        today = "2026-02-28"
        execute_operation(
            {"operation": "create", "title": "Another task", "message": "ok"},
            today,
        )
        tasks = get_all_tasks()
        assert any(t.title == "Another task" and t.category == "T" for t in tasks)

    def test_empty_string_category_defaults_to_T(self, test_db):
        today = "2026-02-28"
        execute_operation(
            {"operation": "create", "title": "Empty cat task", "category": "", "message": "ok"},
            today,
        )
        tasks = get_all_tasks()
        assert any(t.title == "Empty cat task" and t.category == "T" for t in tasks)

    def test_returns_message_from_parsed(self, test_db):
        today = "2026-02-28"
        result = execute_operation(
            {"operation": "create", "title": "Task X", "category": "T", "message": "Created!"},
            today,
        )
        assert result == "Created!"

    def test_multiple_custom_categories_independent(self, test_db):
        today = "2026-02-28"
        execute_operation(
            {"operation": "create", "title": "Task A", "category": "ALPHA", "message": "ok"},
            today,
        )
        execute_operation(
            {"operation": "create", "title": "Task B", "category": "BETA", "message": "ok"},
            today,
        )
        tasks = get_all_tasks()
        cats = {t.category for t in tasks}
        assert "ALPHA" in cats
        assert "BETA" in cats


# ---------------------------------------------------------------------------
# execute_operation — create sad paths
# ---------------------------------------------------------------------------

class TestExecuteOperationCreateSadPaths:

    def test_missing_title_does_not_create_task(self, test_db):
        today = "2026-02-28"
        execute_operation(
            {"operation": "create", "title": "", "category": "T", "message": "ok"},
            today,
        )
        tasks = get_all_tasks()
        assert len(tasks) == 0

    def test_no_title_key_does_not_create_task(self, test_db):
        today = "2026-02-28"
        execute_operation(
            {"operation": "create", "category": "T", "message": "ok"},
            today,
        )
        assert get_all_tasks() == []

    def test_unknown_operation_returns_default_message(self, test_db):
        today = "2026-02-28"
        result = execute_operation(
            {"operation": "frobnicate", "title": "Task", "message": "ok"},
            today,
        )
        # Should not crash; should return message field
        assert result == "ok"

    def test_operation_none_returns_message(self, test_db):
        today = "2026-02-28"
        result = execute_operation(
            {"operation": "none", "message": "I don't understand"},
            today,
        )
        assert result == "I don't understand"


# ---------------------------------------------------------------------------
# execute_operation — update/delete sad paths
# ---------------------------------------------------------------------------

class TestExecuteOperationUpdateDeleteSadPaths:

    def test_update_nonexistent_by_title_returns_error(self, test_db):
        today = "2026-02-28"
        result = execute_operation(
            {"operation": "update", "title": "Ghost task", "completed": True, "message": "ok"},
            today,
        )
        assert "Ghost task" in result or "Could not find" in result

    def test_update_nonexistent_by_key_returns_error(self, test_db):
        today = "2026-02-28"
        result = execute_operation(
            {"operation": "update", "task_key": "T-99", "completed": True, "message": "ok"},
            today,
        )
        assert "T-99" in result or "Could not find" in result

    def test_delete_nonexistent_returns_error(self, test_db):
        today = "2026-02-28"
        result = execute_operation(
            {"operation": "delete", "title": "Phantom", "message": "ok"},
            today,
        )
        assert "Phantom" in result or "Could not find" in result

    def test_update_existing_task_succeeds(self, test_db):
        create_task_db("id-u1", "Real task", "T")
        today = "2026-02-28"
        result = execute_operation(
            {"operation": "update", "title": "Real task", "completed": True, "message": "Done!"},
            today,
        )
        assert result == "Done!"
        tasks = get_all_tasks()
        updated = next(t for t in tasks if t.title == "Real task")
        assert updated.completed is True

    def test_delete_existing_task_removes_it(self, test_db):
        create_task_db("id-d1", "To delete", "T")
        today = "2026-02-28"
        execute_operation(
            {"operation": "delete", "title": "To delete", "message": "Deleted"},
            today,
        )
        tasks = get_all_tasks()
        assert all(t.title != "To delete" for t in tasks)


# ---------------------------------------------------------------------------
# strip_markdown_ — JSON extraction
# ---------------------------------------------------------------------------

class TestStripMarkdown:

    def test_plain_json_unchanged(self):
        raw = '{"operation": "create"}'
        assert strip_markdown_(raw) == raw

    def test_json_block_stripped(self):
        raw = '```json\n{"operation": "create"}\n```'
        result = strip_markdown_(raw)
        assert result == '{"operation": "create"}'

    def test_bare_code_block_stripped(self):
        raw = '```\n{"operation": "none"}\n```'
        result = strip_markdown_(raw)
        assert result == '{"operation": "none"}'

    def test_whitespace_trimmed(self):
        raw = '  {"operation": "delete"}  '
        assert strip_markdown_(raw) == '{"operation": "delete"}'

    def test_multiline_json_block_stripped(self):
        raw = '```json\n{\n  "operation": "create",\n  "title": "Task"\n}\n```'
        result = strip_markdown_(raw)
        import json
        parsed = json.loads(result)
        assert parsed["operation"] == "create"
        assert parsed["title"] == "Task"

    def test_no_closing_fence_returns_content(self):
        # No closing ```, still strips the opening line
        raw = '```json\n{"operation": "create"}'
        result = strip_markdown_(raw)
        assert '{"operation": "create"}' in result
