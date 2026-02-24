"""
Tests for database.py - task CRUD, recurrence calculation, task numbering.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session

from database import (
    create_task_db,
    update_task_db,
    delete_task_db,
    get_all_tasks,
    get_tasks_for_date,
    find_task_by_title_db,
    find_task_by_key_db,
    get_next_task_number,
    calculate_next_occurrence,
    get_conversation,
    save_conversation,
    new_conversation,
)
import database
from models import Task


class TestTaskCRUD:
    """Tests for basic task create/read/update/delete operations."""

    def test_create_task_basic(self, test_db):
        """Create a simple task with default category."""
        task = create_task_db("id-1", "Buy groceries", "T")

        assert task.id == "id-1"
        assert task.title == "Buy groceries"
        assert task.category == "T"
        assert task.task_key == "T-01"
        assert task.completed is False
        assert task.scheduled_date is None
        assert task.recurrence_rule is None

    def test_create_task_with_schedule(self, test_db):
        """Create a task with scheduled date."""
        task = create_task_db("id-1", "Doctor appointment", "M", "2025-02-15T10:00")

        assert task.scheduled_date == "2025-02-15T10:00"
        assert task.category == "M"

    def test_create_task_with_recurrence(self, test_db):
        """Create a recurring task."""
        task = create_task_db("id-1", "Morning standup", "D", "2025-01-20", "weekdays")

        assert task.recurrence_rule == "weekdays"
        assert task.scheduled_date == "2025-01-20"

    def test_get_all_tasks_empty(self, test_db):
        """Get tasks from empty database."""
        tasks = get_all_tasks()
        assert tasks == []

    def test_get_all_tasks_multiple(self, test_db):
        """Get multiple tasks."""
        create_task_db("id-1", "Task 1", "T")
        create_task_db("id-2", "Task 2", "T")
        create_task_db("id-3", "Meeting", "M", "2025-01-20")

        tasks = get_all_tasks()
        assert len(tasks) == 3

    def test_update_task_title(self, test_db):
        """Update task title."""
        create_task_db("id-1", "Old title", "T")
        updated = update_task_db("id-1", title="New title")

        assert updated.title == "New title"
        assert updated.completed is False

    def test_update_task_completed(self, test_db):
        """Mark task as completed."""
        create_task_db("id-1", "Do something", "T")
        updated = update_task_db("id-1", completed=True)

        assert updated.completed is True

    def test_update_task_not_found(self, test_db):
        """Update nonexistent task returns None."""
        result = update_task_db("nonexistent", title="New title")
        assert result is None

    def test_update_task_no_changes(self, test_db):
        """Update with unchanged values still returns task."""
        task = create_task_db("id-1", "Same title", "T")
        updated = update_task_db("id-1", title="Same title")

        assert updated is not None
        assert updated.title == "Same title"
        assert updated.id == task.id

    def test_update_task_multiple_fields(self, test_db):
        """Update multiple fields at once."""
        create_task_db("id-1", "Old title", "T")
        updated = update_task_db("id-1", title="New title", completed=True)

        assert updated.title == "New title"
        assert updated.completed is True

    def test_update_task_bool_field(self, test_db):
        """Bool field updates work correctly."""
        create_task_db("id-1", "Task", "T")

        updated = update_task_db("id-1", completed=True)
        assert updated.completed is True

        updated = update_task_db("id-1", completed=False)
        assert updated.completed is False

    def test_update_task_only_changed_fields(self, test_db):
        """Only changed fields are updated."""
        task = create_task_db("id-1", "Title", "T", "2025-01-20")

        updated = update_task_db("id-1", title="New Title")
        assert updated.title == "New Title"
        assert updated.scheduled_date == "2025-01-20"

    def test_delete_task(self, test_db):
        """Delete a task."""
        create_task_db("id-1", "Delete me", "T")
        assert delete_task_db("id-1") is True

        tasks = get_all_tasks()
        assert len(tasks) == 0

    def test_delete_task_not_found(self, test_db):
        """Delete nonexistent task returns False."""
        assert delete_task_db("nonexistent") is False

    def test_find_task_by_title(self, test_db):
        """Find task by partial title match."""
        create_task_db("id-1", "Buy groceries at store", "T")

        task = find_task_by_title_db("groceries")
        assert task is not None
        assert task.id == "id-1"

        task = find_task_by_title_db("GROCERIES")
        assert task is not None

        task = find_task_by_title_db("nonexistent")
        assert task is None

    def test_find_task_by_key(self, test_db):
        """Find task by task_key."""
        create_task_db("id-1", "First task", "T")
        create_task_db("id-2", "Second task", "T")

        task = find_task_by_key_db("T-01")
        assert task.title == "First task"

        task = find_task_by_key_db("T-02")
        assert task.title == "Second task"

        task = find_task_by_key_db("t-01")
        assert task.title == "First task"

        task = find_task_by_key_db("T-99")
        assert task is None


class TestTaskNumbering:
    """Tests for task numbering logic."""

    def test_sequential_numbering_regular_tasks(self, test_db):
        """Regular tasks (T category) get sequential numbers."""
        t1 = create_task_db("id-1", "Task 1", "T")
        t2 = create_task_db("id-2", "Task 2", "T")
        t3 = create_task_db("id-3", "Task 3", "T")

        assert t1.task_key == "T-01"
        assert t2.task_key == "T-02"
        assert t3.task_key == "T-03"

    def test_per_date_numbering_meetings(self, test_db):
        """Meetings (M category) get per-date numbering."""
        m1 = create_task_db("id-1", "Meeting 1", "M", "2025-01-20T09:00")
        m2 = create_task_db("id-2", "Meeting 2", "M", "2025-01-20T14:00")
        m3 = create_task_db("id-3", "Meeting 3", "M", "2025-01-21T10:00")

        assert m1.task_key == "M-01"
        assert m2.task_key == "M-02"
        assert m3.task_key == "M-01"

    def test_per_date_numbering_daily_tasks(self, test_db):
        """Daily tasks (D category) get per-date numbering."""
        d1 = create_task_db("id-1", "Daily 1", "D", "2025-01-20")
        d2 = create_task_db("id-2", "Daily 2", "D", "2025-01-20")
        d3 = create_task_db("id-3", "Daily 3", "D", "2025-01-21")

        assert d1.task_key == "D-01"
        assert d2.task_key == "D-02"
        assert d3.task_key == "D-01"

    def test_datetime_vs_date_same_numbering(self, test_db):
        """Tasks with datetime and date-only on same day share numbering."""
        m1 = create_task_db("id-1", "Morning meeting", "M", "2025-01-20T09:00")
        m2 = create_task_db("id-2", "All-day event", "M", "2025-01-20")

        assert m1.task_key == "M-01"
        assert m2.task_key == "M-02"

    def test_custom_category_sequential(self, test_db):
        """Custom categories get sequential numbering."""
        p1 = create_task_db("id-1", "Project 1", "P")
        p2 = create_task_db("id-2", "Project 2", "P")

        assert p1.task_key == "P-01"
        assert p2.task_key == "P-02"


class TestRecurrenceCalculation:
    """Tests for calculate_next_occurrence function."""

    def test_daily(self, test_db):
        assert calculate_next_occurrence("daily", "2025-01-20") == "2025-01-21"
        assert calculate_next_occurrence("daily", "2025-01-31") == "2025-02-01"
        assert calculate_next_occurrence("daily", "2025-12-31") == "2026-01-01"

    def test_weekdays_from_weekday(self, test_db):
        assert calculate_next_occurrence("weekdays", "2025-01-20") == "2025-01-21"
        assert calculate_next_occurrence("weekdays", "2025-01-23") == "2025-01-24"

    def test_weekdays_from_friday(self, test_db):
        assert calculate_next_occurrence("weekdays", "2025-01-24") == "2025-01-27"

    def test_weekdays_from_weekend(self, test_db):
        assert calculate_next_occurrence("weekdays", "2025-01-25") == "2025-01-27"
        assert calculate_next_occurrence("weekdays", "2025-01-26") == "2025-01-27"

    def test_weekly_specific_days(self, test_db):
        assert calculate_next_occurrence("weekly:MON,WED,FRI", "2025-01-20") == "2025-01-22"
        assert calculate_next_occurrence("weekly:MON,WED,FRI", "2025-01-22") == "2025-01-24"
        assert calculate_next_occurrence("weekly:MON,WED,FRI", "2025-01-24") == "2025-01-27"

    def test_monthly_day_of_month(self, test_db):
        assert calculate_next_occurrence("monthly:15", "2025-01-10") == "2025-01-15"
        assert calculate_next_occurrence("monthly:15", "2025-01-15") == "2025-02-15"
        assert calculate_next_occurrence("monthly:15", "2025-01-20") == "2025-02-15"
        assert calculate_next_occurrence("monthly:15", "2025-12-20") == "2026-01-15"

    def test_monthly_nth_weekday(self, test_db):
        assert calculate_next_occurrence("monthly:3:WED", "2025-01-10") == "2025-01-15"
        assert calculate_next_occurrence("monthly:3:WED", "2025-01-15") == "2025-02-19"

    def test_yearly(self, test_db):
        assert calculate_next_occurrence("yearly:03-15", "2025-01-20") == "2025-03-15"
        assert calculate_next_occurrence("yearly:03-15", "2025-03-15") == "2026-03-15"
        assert calculate_next_occurrence("yearly:03-15", "2025-06-01") == "2026-03-15"

    def test_invalid_rules(self, test_db):
        assert calculate_next_occurrence("invalid", "2025-01-20") is None
        assert calculate_next_occurrence("", "2025-01-20") is None
        assert calculate_next_occurrence(None, "2025-01-20") is None
        assert calculate_next_occurrence("daily", None) is None
        assert calculate_next_occurrence("daily", "invalid-date") is None


class TestTemplateAndInstanceBehavior:
    """Tests for template and instance behavior."""

    def test_create_template(self, test_db):
        task = create_task_db("id-1", "Daily standup", "D", "2025-01-20", "daily", is_template=True)

        assert task.is_template is True
        assert task.task_key == "R-D-01"
        assert task.recurrence_rule == "daily"

    def test_template_numbering_separate(self, test_db):
        inst = create_task_db("id-1", "Instance task", "D", "2025-01-20")
        tpl = create_task_db("id-2", "Template task", "D", "2025-01-20", "daily", is_template=True)
        inst2 = create_task_db("id-3", "Instance task 2", "D", "2025-01-20")

        assert inst.task_key == "D-01"
        assert tpl.task_key == "R-D-01"
        assert inst2.task_key == "D-02"

    def test_instance_completes_normally(self, test_db):
        task = create_task_db("id-1", "Task instance", "D", "2025-01-20", "daily", is_template=False)
        updated = update_task_db("id-1", completed=True)

        assert updated.completed is True
        assert updated.scheduled_date == "2025-01-20"

    def test_create_instance_with_parent(self, test_db):
        tpl = create_task_db("tpl-1", "Daily standup", "D", "2025-01-20", "daily", is_template=True)
        inst = create_task_db("inst-1", "Daily standup", "D", "2025-01-21", "daily",
                              is_template=False, parent_task_id="tpl-1")

        assert inst.parent_task_id == "tpl-1"
        assert inst.is_template is False

    def test_complete_non_recurring_task(self, test_db):
        task = create_task_db("id-1", "One-time task", "T")
        updated = update_task_db("id-1", completed=True)

        assert updated.completed is True


def _insert_template_via_orm(created_at: str):
    """Helper: insert a daily template with specific created_at via ORM."""
    with Session(database.engine) as session:
        session.add(Task(
            id="tpl-1",
            task_key="R-D-01",
            category="D",
            task_number=1,
            title="Daily standup",
            completed=False,
            scheduled_date="2025-02-01",
            recurrence_rule="daily",
            created_at=created_at,
            is_template=True,
            parent_task_id=None,
        ))
        session.commit()


class TestTemplateStartDate:
    """Tests for template start date (created_at) logic in get_tasks_for_date."""

    def test_projection_not_shown_before_created_at(self, test_db):
        """Template projections should not appear for dates before created_at."""
        _insert_template_via_orm("2025-02-01T10:00:00")

        tasks = get_tasks_for_date("2025-01-15", "2025-01-15")
        assert len(tasks) == 0

    def test_projection_shown_on_created_at_date(self, test_db):
        """Template projections should appear on the created_at date."""
        _insert_template_via_orm("2025-02-01T10:00:00")

        tasks = get_tasks_for_date("2025-02-01", "2025-02-15")
        assert len(tasks) == 1
        assert tasks[0].is_template is True

    def test_projection_shown_after_created_at(self, test_db):
        """Template projections should appear for dates after created_at."""
        _insert_template_via_orm("2025-02-01T10:00:00")

        tasks = get_tasks_for_date("2025-02-10", "2025-02-15")
        assert len(tasks) == 1
        assert tasks[0].is_template is True
        assert tasks[0].scheduled_date == "2025-02-10"

    def test_instance_not_created_before_created_at(self, test_db):
        """Template instances should not be created for dates before created_at."""
        _insert_template_via_orm("2025-02-01T10:00:00")

        tasks = get_tasks_for_date("2025-01-15", "2025-01-15")
        assert len(tasks) == 0

        all_tasks = get_all_tasks()
        assert len(all_tasks) == 1  # Only the template

    def test_instance_created_on_created_at_date(self, test_db):
        """Template instance should be created on the created_at date when it's today."""
        _insert_template_via_orm("2025-02-01T10:00:00")

        tasks = get_tasks_for_date("2025-02-01", "2025-02-01")
        assert len(tasks) == 1
        assert tasks[0].is_template is False
        assert tasks[0].parent_task_id == "tpl-1"

    def test_instance_created_after_created_at(self, test_db):
        """Template instance should be created for dates after created_at when it's today."""
        _insert_template_via_orm("2025-02-01T10:00:00")

        tasks = get_tasks_for_date("2025-02-10", "2025-02-10")
        assert len(tasks) == 1
        assert tasks[0].is_template is False


class TestOverdueFiltering:
    """Tests for overdue task filtering in day view."""

    def test_overdue_recurrent_instance_excluded(self, test_db):
        tpl = create_task_db("tpl-1", "Stretch", "D", "2025-06-01", "daily", is_template=True)
        create_task_db("inst-old", "Stretch", "D", "2025-06-01", "daily",
                       is_template=False, parent_task_id="tpl-1")

        tasks = get_tasks_for_date("2025-06-15", "2025-06-15")
        task_ids = [t.id for t in tasks]

        assert "inst-old" not in task_ids

    def test_overdue_non_recurrent_task_included(self, test_db):
        create_task_db("task-1", "Buy groceries", "T", "2025-06-01")

        tasks = get_tasks_for_date("2025-06-15", "2025-06-15")
        task_ids = [t.id for t in tasks]

        assert "task-1" in task_ids

    def test_completed_non_recurrent_task_excluded(self, test_db):
        create_task_db("task-1", "Buy groceries", "T", "2025-06-01")
        update_task_db("task-1", completed=True)

        tasks = get_tasks_for_date("2025-06-15", "2025-06-15")
        task_ids = [t.id for t in tasks]

        assert "task-1" not in task_ids


class TestConversation:
    """Tests for conversation persistence."""

    def test_save_and_get_conversation(self, test_db):
        """Save and retrieve conversation."""
        conv_id = new_conversation()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        save_conversation(messages, conv_id)

        result = get_conversation()
        assert result["id"] == conv_id
        assert len(result["messages"]) == 2
        assert result["messages"][0]["content"] == "Hello"
        assert result["messages"][1]["content"] == "Hi there!"

    def test_get_empty_conversation(self, test_db):
        """Get conversation when none exists returns id=None and empty messages."""
        result = get_conversation()
        assert result["id"] is None
        assert result["messages"] == []

    def test_update_conversation(self, test_db):
        """Update existing conversation."""
        conv_id = new_conversation()
        save_conversation([{"role": "user", "content": "First"}], conv_id)
        save_conversation([
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Second"},
        ], conv_id)

        result = get_conversation()
        assert result["id"] == conv_id
        assert len(result["messages"]) == 3
