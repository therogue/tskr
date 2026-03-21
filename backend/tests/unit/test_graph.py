"""
Tests for graph.py — helpers, routing, scoped lookups, and apply_operation.
Does NOT test LLM-calling nodes (classify_intent, execute_operation, execute_reschedule).
"""
from database import create_task_db, get_all_tasks, update_task_db
from graph import (
    _strip_markdown,
    _find_task_in_scope,
    _apply_operation,
    _resolve_conflicts,
    _time_to_minutes,
    _fetch_tasks_for_state,
    _route_intent,
    resolve_clarification,
)


# -- Sample scoped task lists for tests --

TASKS_NO_CONFLICT = [
    {"id": "id-1", "task_key": "M-01", "title": "go to an event", "category": "M", "scheduled_date": "2026-03-18T14:00", "completed": False},
    {"id": "id-2", "task_key": "M-02", "title": "meet with Barnabas", "category": "M", "scheduled_date": "2026-03-18T16:00", "completed": False},
    {"id": "id-3", "task_key": "T-01", "title": "buy groceries", "category": "T", "scheduled_date": None, "completed": False},
]

TASKS_WITH_CONFLICT = [
    {"id": "id-1", "task_key": "M-02", "title": "meet Alex", "category": "M", "scheduled_date": "2026-03-18T15:00", "completed": False},
    {"id": "id-2", "task_key": "M-02", "title": "meet Barnabas", "category": "M", "scheduled_date": "2026-03-18T16:00", "completed": False},
]


class TestStripMarkdown:

    def test_plain_json(self):
        assert _strip_markdown('{"a": 1}') == '{"a": 1}'

    def test_wrapped_json(self):
        raw = '```json\n{"a": 1}\n```'
        assert _strip_markdown(raw) == '{"a": 1}'

    def test_wrapped_no_lang(self):
        raw = '```\n{"a": 1}\n```'
        assert _strip_markdown(raw) == '{"a": 1}'

    def test_whitespace(self):
        raw = '  \n```json\n{"a": 1}\n```\n  '
        assert _strip_markdown(raw) == '{"a": 1}'


class TestFindTaskInScope:

    def test_find_by_key(self):
        result = _find_task_in_scope(TASKS_NO_CONFLICT, task_key="M-02")
        assert result is not None
        assert result["title"] == "meet with Barnabas"

    def test_find_by_key_case_insensitive(self):
        result = _find_task_in_scope(TASKS_NO_CONFLICT, task_key="m-02")
        assert result is not None
        assert result["title"] == "meet with Barnabas"

    def test_find_by_title_substring(self):
        result = _find_task_in_scope(TASKS_NO_CONFLICT, title="groceries")
        assert result is not None
        assert result["task_key"] == "T-01"

    def test_find_by_title_case_insensitive(self):
        result = _find_task_in_scope(TASKS_NO_CONFLICT, title="GROCERIES")
        assert result is not None

    def test_not_found_by_key(self):
        result = _find_task_in_scope(TASKS_NO_CONFLICT, task_key="Z-99")
        assert result is None

    def test_not_found_by_title(self):
        result = _find_task_in_scope(TASKS_NO_CONFLICT, title="nonexistent")
        assert result is None

    def test_ambiguous_key_returns_none(self):
        result = _find_task_in_scope(TASKS_WITH_CONFLICT, task_key="M-02")
        assert result is None

    def test_ambiguous_title_returns_none(self):
        result = _find_task_in_scope(TASKS_WITH_CONFLICT, title="meet")
        assert result is None

    def test_no_key_no_title(self):
        assert _find_task_in_scope(TASKS_NO_CONFLICT) is None

    def test_key_preferred_over_title(self):
        result = _find_task_in_scope(TASKS_NO_CONFLICT, title="groceries", task_key="M-01")
        assert result["title"] == "go to an event"

    def test_disambiguate_by_target_date(self):
        tasks = [
            {"id": "id-1", "task_key": "M-02", "title": "meet Alex", "category": "M", "scheduled_date": "2026-03-18T15:00", "completed": False},
            {"id": "id-2", "task_key": "M-02", "title": "meet Barnabas", "category": "M", "scheduled_date": "2026-03-19T16:00", "completed": False},
        ]
        result = _find_task_in_scope(tasks, task_key="M-02", target_date="2026-03-18")
        assert result is not None
        assert result["title"] == "meet Alex"

        result = _find_task_in_scope(tasks, task_key="M-02", target_date="2026-03-19")
        assert result is not None
        assert result["title"] == "meet Barnabas"

    def test_disambiguate_by_title_when_date_fails(self):
        tasks = [
            {"id": "id-1", "task_key": "M-02", "title": "meet Alex", "category": "M", "scheduled_date": "2026-03-18T15:00", "completed": False},
            {"id": "id-2", "task_key": "M-02", "title": "meet Barnabas", "category": "M", "scheduled_date": "2026-03-19T16:00", "completed": False},
        ]
        # target_date doesn't match either, but title "Alex" narrows to one
        result = _find_task_in_scope(tasks, title="Alex", task_key="M-02", target_date="2026-03-25")
        assert result is not None
        assert result["title"] == "meet Alex"

    def test_still_ambiguous_when_nothing_helps(self):
        result = _find_task_in_scope(TASKS_WITH_CONFLICT, task_key="M-02", target_date="2026-03-25")
        assert result is None

    def test_disambiguate_by_user_message(self):
        """When key is ambiguous and title is the NEW name (post-rename),
        user_message containing the ORIGINAL name should disambiguate."""
        tasks = [
            {"id": "id-1", "task_key": "M-02", "title": "meet with Alex", "category": "M", "scheduled_date": "2026-03-18T16:00", "completed": False},
            {"id": "id-2", "task_key": "M-02", "title": "meet with Barnabas", "category": "M", "scheduled_date": "2026-03-19T16:00", "completed": False},
        ]
        result = _find_task_in_scope(
            tasks, title="meet with Barney", task_key="M-02",
            target_date="2026-03-25",
            user_message="rename meet with Alex to meet with Barney",
        )
        assert result is not None
        assert result["title"] == "meet with Alex"

    def test_user_message_not_used_when_key_unique(self):
        """user_message should not interfere when key is already unique."""
        result = _find_task_in_scope(
            TASKS_NO_CONFLICT, task_key="M-02",
            user_message="irrelevant text about groceries",
        )
        assert result is not None
        assert result["title"] == "meet with Barnabas"

    def test_user_message_ambiguous_too(self):
        """If user_message matches both tasks, still returns None."""
        result = _find_task_in_scope(
            TASKS_WITH_CONFLICT, task_key="M-02",
            user_message="something about meet",
        )
        assert result is None


class TestApplyOperationCreate:

    def test_create_task(self, test_db):
        parsed = {
            "operation": "create",
            "title": "new task",
            "category": "T",
            "scheduled_date": "2026-03-18",
            "message": "Created!",
        }
        result = _apply_operation(parsed, "2026-03-18", [])
        assert result == "Created!"
        tasks = get_all_tasks()
        assert len(tasks) == 1
        assert tasks[0].title == "new task"

    def test_create_meeting_defaults_to_today(self, test_db):
        parsed = {
            "operation": "create",
            "title": "standup",
            "category": "M",
            "message": "Done",
        }
        _apply_operation(parsed, "2026-03-18", [])
        tasks = get_all_tasks()
        assert tasks[0].scheduled_date == "2026-03-18"

    def test_create_without_title_is_noop(self, test_db):
        parsed = {"operation": "create", "title": "", "message": "Done"}
        result = _apply_operation(parsed, "2026-03-18", [])
        assert result == "Done"
        assert len(get_all_tasks()) == 0


class TestApplyOperationUpdate:

    def test_update_title(self, test_db):
        create_task_db("id-2", "meet with Barnabas", "M", "2026-03-18T16:00")
        scoped = [{"id": "id-2", "task_key": "M-01", "title": "meet with Barnabas", "category": "M", "scheduled_date": "2026-03-18T16:00", "completed": False}]

        parsed = {
            "operation": "update",
            "task_key": "M-01",
            "title": "meet with Alex",
            "message": "Updated!",
        }
        result = _apply_operation(parsed, "2026-03-18", scoped)
        assert result == "Updated!"
        tasks = get_all_tasks()
        assert tasks[0].title == "meet with Alex"

    def test_update_scheduled_date(self, test_db):
        create_task_db("id-1", "event", "M", "2026-03-18T14:00")
        scoped = [{"id": "id-1", "task_key": "M-01", "title": "event", "category": "M", "scheduled_date": "2026-03-18T14:00", "completed": False}]

        parsed = {
            "operation": "update",
            "task_key": "M-01",
            "scheduled_date": "2026-03-19T10:00",
            "message": "Moved!",
        }
        result = _apply_operation(parsed, "2026-03-18", scoped)
        assert result == "Moved!"
        tasks = get_all_tasks()
        assert tasks[0].scheduled_date == "2026-03-19T10:00"

    def test_update_not_found(self, test_db):
        result = _apply_operation(
            {"operation": "update", "task_key": "Z-99", "message": "Done"},
            "2026-03-18",
            TASKS_NO_CONFLICT,
        )
        assert "couldn't identify" in result

    def test_update_ambiguous_key_not_found(self, test_db):
        result = _apply_operation(
            {"operation": "update", "task_key": "M-02", "title": "new", "message": "Done"},
            "2026-03-18",
            TASKS_WITH_CONFLICT,
        )
        assert "couldn't identify" in result

    def test_update_with_user_message_disambiguation(self, test_db):
        """Exact reproduction of the failing scenario: two M-02 tasks, LLM returns
        the NEW title, but user_message contains the OLD title for disambiguation."""
        create_task_db("id-1", "meet with Alex", "M", "2026-03-18T16:00")
        create_task_db("id-2", "meet with Barnabas", "M", "2026-03-19T16:00")
        scoped = [
            {"id": "id-1", "task_key": "M-02", "title": "meet with Alex", "category": "M", "scheduled_date": "2026-03-18T16:00", "completed": False},
            {"id": "id-2", "task_key": "M-02", "title": "meet with Barnabas", "category": "M", "scheduled_date": "2026-03-19T16:00", "completed": False},
        ]
        parsed = {
            "operation": "update",
            "task_key": "M-02",
            "title": "meet with Barney",
            "message": "Updated your meeting.",
        }
        result = _apply_operation(
            parsed, "2026-03-18", scoped,
            target_date="2026-03-25",
            user_message="update meet with Alex to meet with Barney",
        )
        assert result == "Updated your meeting."
        tasks = get_all_tasks()
        renamed = [t for t in tasks if t.title == "meet with Barney"]
        assert len(renamed) == 1
        assert renamed[0].id == "id-1"

    def test_update_no_changes(self, test_db):
        create_task_db("id-1", "task", "T")
        scoped = [{"id": "id-1", "task_key": "T-01", "title": "task", "category": "T", "scheduled_date": None, "completed": False}]
        result = _apply_operation(
            {"operation": "update", "task_key": "T-01", "message": "Done"},
            "2026-03-18",
            scoped,
        )
        assert "already up to date" in result


class TestApplyOperationDelete:

    def test_delete_task(self, test_db):
        create_task_db("id-1", "delete me", "T")
        scoped = [{"id": "id-1", "task_key": "T-01", "title": "delete me", "category": "T", "scheduled_date": None, "completed": False}]

        result = _apply_operation(
            {"operation": "delete", "task_key": "T-01", "message": "Deleted!"},
            "2026-03-18",
            scoped,
        )
        assert result == "Deleted!"
        assert len(get_all_tasks()) == 0

    def test_delete_not_found(self, test_db):
        result = _apply_operation(
            {"operation": "delete", "task_key": "Z-99", "message": "Done"},
            "2026-03-18",
            TASKS_NO_CONFLICT,
        )
        assert "couldn't identify" in result

    def test_delete_ambiguous_key_not_found(self, test_db):
        result = _apply_operation(
            {"operation": "delete", "task_key": "M-02", "message": "Done"},
            "2026-03-18",
            TASKS_WITH_CONFLICT,
        )
        assert "couldn't identify" in result


class TestApplyOperationNone:

    def test_none_operation(self, test_db):
        result = _apply_operation(
            {"operation": "none", "message": "What would you like?"},
            "2026-03-18",
            [],
        )
        assert result == "What would you like?"


class TestFetchTasksForState:

    def test_returns_all_incomplete_even_with_target_date(self, test_db):
        create_task_db("id-1", "task on day", "T", "2026-03-18")
        create_task_db("id-2", "task other day", "T", "2026-03-19")

        state = {"today": "2026-03-18", "target_date": "2026-03-18"}
        result = _fetch_tasks_for_state(state, "test")
        assert len(result) == 2

    def test_all_incomplete_without_date(self, test_db):
        create_task_db("id-1", "task A", "T", "2026-03-18")
        create_task_db("id-2", "task B", "T", "2026-03-19")
        create_task_db("id-3", "done", "T")
        update_task_db("id-3", completed=True)

        state = {"today": "2026-03-18", "target_date": ""}
        result = _fetch_tasks_for_state(state, "test")
        assert len(result) == 2
        titles = {r["title"] for r in result}
        assert "done" not in titles

    def test_includes_id_field(self, test_db):
        create_task_db("id-1", "task", "T", "2026-03-18")
        state = {"today": "2026-03-18", "target_date": "2026-03-18"}
        result = _fetch_tasks_for_state(state, "test")
        assert "id" in result[0]
        assert result[0]["id"] == "id-1"


class TestRouteIntent:

    def test_task_operation(self):
        assert _route_intent({"intent": "task_operation"}) == "fetch_tasks_op"

    def test_clarification_answer(self):
        assert _route_intent({"intent": "clarification_answer"}) == "resolve_clarification"

    def test_reschedule(self):
        assert _route_intent({"intent": "reschedule"}) == "fetch_tasks_rs"

    def test_unknown_defaults_to_task_op(self):
        assert _route_intent({"intent": "something_else"}) == "fetch_tasks_op"


class TestResolveClarification:

    def test_finds_prior_assistant_question(self):
        state = {
            "messages": [
                {"role": "user", "content": "add a task"},
                {"role": "assistant", "content": "What title?"},
                {"role": "user", "content": "buy milk"},
            ],
            "extracted_context": "buy milk",
        }
        result = resolve_clarification(state)
        assert "What title?" in result["extracted_context"]
        assert "buy milk" in result["extracted_context"]

    def test_no_prior_assistant_message(self):
        state = {
            "messages": [
                {"role": "user", "content": "hello"},
            ],
            "extracted_context": "hello",
        }
        result = resolve_clarification(state)
        assert result == {}

    def test_skips_current_user_message(self):
        state = {
            "messages": [
                {"role": "assistant", "content": "first question"},
                {"role": "user", "content": "first answer"},
                {"role": "assistant", "content": "second question"},
                {"role": "user", "content": "second answer"},
            ],
            "extracted_context": "second answer",
        }
        result = resolve_clarification(state)
        assert "second question" in result["extracted_context"]


class TestTimeToMinutes:

    def test_morning(self):
        assert _time_to_minutes("2026-03-18T09:30") == 570

    def test_afternoon(self):
        assert _time_to_minutes("2026-03-18T15:00") == 900

    def test_midnight(self):
        assert _time_to_minutes("2026-03-18T00:00") == 0


class TestResolveConflicts:

    def test_overlap_is_noop(self, test_db):
        create_task_db("id-1", "existing", "M", "2026-03-18T10:00", duration_minutes=60)
        _resolve_conflicts("2026-03-18T10:30", 30, "new-id", "overlap")
        tasks = get_all_tasks()
        assert tasks[0].scheduled_date == "2026-03-18T10:00"

    def test_unschedule_strips_time(self, test_db):
        create_task_db("id-1", "existing", "M", "2026-03-18T10:00", duration_minutes=60)
        _resolve_conflicts("2026-03-18T10:30", 30, "new-id", "unschedule")
        tasks = get_all_tasks()
        assert tasks[0].scheduled_date == "2026-03-18"

    def test_backlog_clears_date(self, test_db):
        create_task_db("id-1", "existing", "M", "2026-03-18T10:00", duration_minutes=60)
        _resolve_conflicts("2026-03-18T10:30", 30, "new-id", "backlog")
        tasks = get_all_tasks()
        assert tasks[0].scheduled_date is None

    def test_no_conflict_no_change(self, test_db):
        create_task_db("id-1", "existing", "M", "2026-03-18T10:00", duration_minutes=30)
        _resolve_conflicts("2026-03-18T11:00", 30, "new-id", "unschedule")
        tasks = get_all_tasks()
        assert tasks[0].scheduled_date == "2026-03-18T10:00"

    def test_excludes_self(self, test_db):
        create_task_db("id-1", "existing", "M", "2026-03-18T10:00", duration_minutes=60)
        _resolve_conflicts("2026-03-18T10:00", 60, "id-1", "backlog")
        tasks = get_all_tasks()
        assert tasks[0].scheduled_date == "2026-03-18T10:00"

    def test_date_only_is_noop(self, test_db):
        create_task_db("id-1", "existing", "M", "2026-03-18T10:00", duration_minutes=60)
        _resolve_conflicts("2026-03-18", 30, "new-id", "unschedule")
        tasks = get_all_tasks()
        assert tasks[0].scheduled_date == "2026-03-18T10:00"


class TestApplyOperationConflictResolution:

    def test_create_with_unschedule(self, test_db):
        create_task_db("id-1", "blocker", "M", "2026-03-18T10:00", duration_minutes=60)
        parsed = {
            "operation": "create",
            "title": "new meeting",
            "category": "M",
            "scheduled_date": "2026-03-18T10:30",
            "duration_minutes": 30,
            "message": "Created!",
        }
        _apply_operation(parsed, "2026-03-18", [], "unschedule")
        tasks = get_all_tasks()
        blocker = next(t for t in tasks if t.title == "blocker")
        assert blocker.scheduled_date == "2026-03-18"

    def test_create_defaults_to_overlap(self, test_db):
        create_task_db("id-1", "blocker", "M", "2026-03-18T10:00", duration_minutes=60)
        parsed = {
            "operation": "create",
            "title": "new meeting",
            "category": "M",
            "scheduled_date": "2026-03-18T10:30",
            "duration_minutes": 30,
            "message": "Created!",
        }
        _apply_operation(parsed, "2026-03-18", [])
        tasks = get_all_tasks()
        blocker = next(t for t in tasks if t.title == "blocker")
        assert blocker.scheduled_date == "2026-03-18T10:00"
