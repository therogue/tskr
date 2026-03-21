"""
Tests for main.py functionality.
Tests that don't require API client (for /chat endpoint mocking would be needed).
"""
import pytest

from database import create_task_db, get_all_tasks, get_tasks_for_date, update_task_db
from main import execute_operation
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


class TestDayViewExcludesUnscheduledTasks:
    """Unscheduled tasks must not appear in day view (Issue #16)."""

    def test_unscheduled_task_excluded_from_today(self, test_db):
        """Tasks with no scheduled_date do not appear in get_tasks_for_date for today."""
        today = "2026-02-23"
        create_task_db("id-unscheduled", "Unscheduled task", "T")

        result = get_tasks_for_date(today, today)
        ids = [t.id for t in result]
        assert "id-unscheduled" not in ids

    def test_scheduled_task_appears_in_day_view(self, test_db):
        """Tasks with a matching scheduled_date still appear in day view."""
        today = "2026-02-23"
        create_task_db("id-scheduled", "Scheduled task", "T", today)

        result = get_tasks_for_date(today, today)
        ids = [t.id for t in result]
        assert "id-scheduled" in ids

    def test_unscheduled_task_appears_in_get_all_tasks(self, test_db):
        """Unscheduled tasks are still returned by get_all_tasks (for backlog tab)."""
        create_task_db("id-backlog", "Backlog task", "T")

        all_tasks = get_all_tasks()
        ids = [t.id for t in all_tasks]
        assert "id-backlog" in ids


class TestConflictResolution:
    """Tests for execute_operation conflict resolution behavior."""

    # Helper: create a task scheduled at HH:MM with given duration
    def _make_scheduled(self, task_id: str, hhmm: str, duration: int) -> None:
        create_task_db(task_id, f"Task {task_id}", "T", f"2026-03-07T{hhmm}")
        update_task_db(task_id, duration_minutes=duration)

    def test_unschedule_strips_time_from_conflicting_task(self, test_db):
        """conflict_resolution='unschedule' strips time from overlapping task."""
        self._make_scheduled("existing", "09:00", 60)  # 09:00–10:00

        execute_operation(
            {"operation": "create", "title": "New task", "scheduled_date": "2026-03-07T09:30",
             "duration_minutes": 30, "message": "done"},
            today="2026-03-07",
            conflict_resolution="unschedule",
        )

        tasks = {t.id: t for t in get_all_tasks()}
        # Existing task should have time stripped (date only)
        assert tasks["existing"].scheduled_date == "2026-03-07"

    def test_backlog_sets_scheduled_date_none(self, test_db):
        """conflict_resolution='backlog' sets scheduled_date=None on overlapping task."""
        self._make_scheduled("existing", "09:00", 60)  # 09:00–10:00

        execute_operation(
            {"operation": "create", "title": "New task", "scheduled_date": "2026-03-07T09:30",
             "duration_minutes": 30, "message": "done"},
            today="2026-03-07",
            conflict_resolution="backlog",
        )

        tasks = {t.id: t for t in get_all_tasks()}
        assert tasks["existing"].scheduled_date is None

    def test_overlap_leaves_conflicting_task_unchanged(self, test_db):
        """conflict_resolution='overlap' does not modify overlapping task."""
        self._make_scheduled("existing", "09:00", 60)

        execute_operation(
            {"operation": "create", "title": "New task", "scheduled_date": "2026-03-07T09:30",
             "duration_minutes": 30, "message": "done"},
            today="2026-03-07",
            conflict_resolution="overlap",
        )

        tasks = {t.id: t for t in get_all_tasks()}
        assert tasks["existing"].scheduled_date == "2026-03-07T09:00"

    def test_non_overlapping_task_never_affected(self, test_db):
        """Tasks that do not overlap are never modified regardless of conflict_resolution."""
        self._make_scheduled("before", "07:00", 30)  # 07:00–07:30
        self._make_scheduled("after", "12:00", 60)   # 12:00–13:00

        execute_operation(
            {"operation": "create", "title": "New task", "scheduled_date": "2026-03-07T09:00",
             "duration_minutes": 60, "message": "done"},
            today="2026-03-07",
            conflict_resolution="unschedule",
        )

        tasks = {t.id: t for t in get_all_tasks()}
        assert tasks["before"].scheduled_date == "2026-03-07T07:00"
        assert tasks["after"].scheduled_date == "2026-03-07T12:00"