"""
Tests for main.py functionality.
Tests that don't require API client (for /chat endpoint mocking would be needed).
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import create_task_db, get_all_tasks
from prompts import SYSTEM_PROMPT


class TestSystemPromptTaskContext:
    """Tests for task context formatting in system prompt (Issue #4)."""

    def test_task_list_formatting(self, test_db):
        """Task list is formatted correctly for system prompt."""
        # Create some tasks
        create_task_db("id-1", "Buy groceries", "T")
        create_task_db("id-2", "Team meeting", "M", "2025-02-07T10:00")
        create_task_db("id-3", "Review PR", "T")

        tasks = get_all_tasks()
        task_list = "\n".join([f"- {task.task_key}: {task.title}" for task in tasks if not task.completed])

        # Should have 3 incomplete tasks
        lines = task_list.split("\n")
        assert len(lines) == 3
        assert "- T-01: Buy groceries" in task_list
        assert "- M-01: Team meeting" in task_list
        assert "- T-02: Review PR" in task_list

    def test_task_list_excludes_completed(self, test_db):
        """Completed tasks are excluded from task list."""
        task1 = create_task_db("id-1", "Task 1", "T")
        task2 = create_task_db("id-2", "Task 2", "T")
        task3 = create_task_db("id-3", "Task 3", "T")

        # Mark task 2 as completed
        from database import update_task_db
        update_task_db("id-2", completed=True)

        tasks = get_all_tasks()
        task_list = "\n".join([f"- {task.task_key}: {task.title}" for task in tasks if not task.completed])

        # Should only have 2 incomplete tasks
        lines = task_list.split("\n")
        assert len(lines) == 2
        assert "Task 1" in task_list
        assert "Task 2" not in task_list  # Completed, excluded
        assert "Task 3" in task_list

    def test_empty_task_list(self, test_db):
        """Empty task list when no tasks exist."""
        tasks = get_all_tasks()
        assert len(tasks) == 0

        # Formatting should handle empty list
        task_list = "\n".join([f"- {task.task_key}: {task.title}" for task in tasks if not task.completed])
        assert task_list == ""

    def test_system_prompt_has_today_placeholder(self, test_db):
        """System prompt contains {today} placeholder."""
        assert "{today}" in SYSTEM_PROMPT

    def test_system_prompt_mentions_task_context(self, test_db):
        """System prompt mentions task list will be provided."""
        assert "task_key" in SYSTEM_PROMPT.lower() or "current tasks" in SYSTEM_PROMPT.lower()