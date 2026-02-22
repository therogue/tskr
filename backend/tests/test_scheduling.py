"""
Tests for build_schedule_context() in scheduling.py.
Tests gap calculation and schedule formatting for auto-scheduling.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Task
from scheduling import build_schedule_context


def _task(task_key, title, scheduled_date, duration_minutes=30, completed=False):
    # Assumes: task_key format is CATEGORY-NN, scheduled_date is YYYY-MM-DD or YYYY-MM-DDTHH:MM
    return Task(
        id="test-id",
        task_key=task_key,
        category=task_key[0],
        task_number=1,
        title=title,
        scheduled_date=scheduled_date,
        duration_minutes=duration_minutes,
        created_at="2026-02-22T00:00:00",
        completed=completed,
    )


class TestBuildScheduleContext:

    def test_empty_list_returns_empty(self):
        assert build_schedule_context([]) == ""

    def test_no_timed_tasks_returns_empty(self):
        tasks = [
            _task("T-01", "Review docs", "2026-02-22"),
            _task("T-02", "No date task", None),
        ]
        assert build_schedule_context(tasks) == ""

    def test_completed_timed_task_excluded(self):
        tasks = [_task("M-01", "Standup", "2026-02-22T09:00", 30, completed=True)]
        assert build_schedule_context(tasks) == ""

    def test_single_timed_task_format(self):
        tasks = [_task("M-01", "Standup", "2026-02-22T09:00", 30)]
        result = build_schedule_context(tasks)
        assert "M-01: Standup (09:00-09:30, 30min)" in result
        assert "Available business-hours gaps:" in result
        # Gap after standup within business hours
        assert "09:30-17:00" in result
        # No gap before 09:00 (business hours start at 09:00)
        assert "00:00" not in result

    def test_two_tasks_with_gap_between(self):
        tasks = [
            _task("M-01", "Standup", "2026-02-22T09:00", 30),
            _task("T-03", "Code review", "2026-02-22T10:00", 60),
        ]
        result = build_schedule_context(tasks)
        assert "M-01: Standup (09:00-09:30, 30min)" in result
        assert "T-03: Code review (10:00-11:00, 60min)" in result
        assert "09:30-10:00" in result
        assert "11:00-17:00" in result
        # No gap before business hours
        assert "00:00" not in result

    def test_adjacent_tasks_no_gap_between_them(self):
        tasks = [
            _task("M-01", "Meeting A", "2026-02-22T09:00", 60),
            _task("M-02", "Meeting B", "2026-02-22T10:00", 60),
        ]
        result = build_schedule_context(tasks)
        # No gap between adjacent meetings
        assert "09:00-10:00" not in result
        # Gap after both meetings
        assert "11:00-17:00" in result

    def test_task_outside_business_hours_does_not_create_biz_gap(self):
        # Task before business hours — should not show up as a gap
        tasks = [_task("M-01", "Early meeting", "2026-02-22T07:00", 60)]
        result = build_schedule_context(tasks)
        # Full business hours should be available since task is before 09:00
        assert "09:00-17:00" in result

    def test_task_overlapping_start_of_business_hours(self):
        # Task 08:00-09:30 eats into first 30min of business hours
        tasks = [_task("M-01", "Early overlap", "2026-02-22T08:00", 90)]
        result = build_schedule_context(tasks)
        # Gap starts at 09:30 (where the task ends within biz hours)
        assert "09:30-17:00" in result
        assert "09:00-" not in result

    def test_full_business_hours_booked_shows_no_gaps(self):
        tasks = [_task("M-01", "All day", "2026-02-22T09:00", 480)]  # 9:00-17:00
        result = build_schedule_context(tasks)
        assert "Available business-hours gaps: none" in result

    def test_none_duration_falls_back_to_default(self):
        tasks = [_task("T-01", "Task", "2026-02-22T10:00", None)]
        result = build_schedule_context(tasks)
        # Should not crash; default is 15min
        assert "10:00-10:15" in result

    def test_tasks_sorted_by_time(self):
        # Create tasks out of order
        tasks = [
            _task("M-02", "Later meeting", "2026-02-22T11:00", 30),
            _task("M-01", "Earlier meeting", "2026-02-22T09:00", 30),
        ]
        result = build_schedule_context(tasks)
        earlier_pos = result.index("M-01")
        later_pos = result.index("M-02")
        assert earlier_pos < later_pos
