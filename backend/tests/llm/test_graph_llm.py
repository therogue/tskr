"""
LLM-as-a-judge integration tests for graph.py.
Makes REAL Anthropic API calls — requires ANTHROPIC_API_KEY in .env.
Run with: pytest --run-llm -v -s
"""

import json
import os

import anthropic
import pytest
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

pytestmark = pytest.mark.llm

from database import create_task_db, get_all_tasks
from graph import classify_intent, execute_operation, execute_reschedule, GraphState

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

JUDGE_PROMPT = """You are an automated test judge. Given the SCENARIO, the EXPECTED outcome, and the ACTUAL result, decide if the test passed.

Respond with JSON only:
{
    "pass": true | false,
    "reason": "one-sentence explanation"
}
"""


def _judge(scenario: str, expected: str, actual: str) -> dict:
    """Calls the LLM to judge whether the actual result meets expectations."""
    response = _client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=128,
        system=JUDGE_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"SCENARIO: {scenario}\n\n"
                f"EXPECTED: {expected}\n\n"
                f"ACTUAL: {actual}"
            ),
        }],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)


def _make_state(user_message: str, today: str = "2026-03-18", **overrides) -> GraphState:
    messages = overrides.pop("messages", None) or [
        {"role": "user", "content": user_message}
    ]
    return {
        "messages": messages,
        "user_message": user_message,
        "today": today,
        "intent": "",
        "extracted_context": "",
        "target_date": "",
        "relevant_tasks": [],
        "operation_result": {},
        "final_response": "",
        **overrides,
    }


# -- Fixtures --

TASK_LIST_SCENARIO = [
    {"id": "id-1", "task_key": "M-01", "title": "go to an event", "category": "M", "scheduled_date": "2026-03-18T14:00", "completed": False},
    {"id": "id-2", "task_key": "T-02", "title": "go to the park", "category": "T", "scheduled_date": "2026-03-08", "completed": False},
    {"id": "id-3", "task_key": "T-04", "title": "work on my diary", "category": "T", "scheduled_date": "2026-03-08T21:00", "completed": False},
    {"id": "id-4", "task_key": "T-01", "title": "buy groceries", "category": "T", "scheduled_date": "2026-03-09", "completed": False},
    {"id": "id-5", "task_key": "T-03", "title": "go bowling", "category": "T", "scheduled_date": "2026-03-09", "completed": False},
    {"id": "id-6", "task_key": "M-01", "title": "have dinner with my friends", "category": "M", "scheduled_date": "2026-03-18T14:00", "completed": False},
    {"id": "id-7", "task_key": "M-02", "title": "meet with Alex", "category": "M", "scheduled_date": "2026-03-18T16:00", "completed": False},
    {"id": "id-8", "task_key": "M-02", "title": "meet with Barnabas", "category": "M", "scheduled_date": "2026-03-19T16:00", "completed": False},
]

# ---------------------------------------------------------------------------
# Intent classification tests
# ---------------------------------------------------------------------------

class TestClassifyIntent:

    @pytest.mark.asyncio
    async def test_create_intent(self):
        state = _make_state("create a task to buy milk")
        result = await classify_intent(state)
        verdict = _judge(
            "User says: 'create a task to buy milk'",
            "intent should be 'task_operation'",
            f"intent={result['intent']}",
        )
        assert verdict["pass"], verdict["reason"]

    @pytest.mark.asyncio
    async def test_reschedule_intent(self):
        state = _make_state("move my meeting to tomorrow")
        result = await classify_intent(state)
        verdict = _judge(
            "User says: 'move my meeting to tomorrow'",
            "intent should be 'reschedule'",
            f"intent={result['intent']}",
        )
        assert verdict["pass"], verdict["reason"]

    @pytest.mark.asyncio
    async def test_clarification_answer_intent(self):
        state = _make_state(
            "tomorrow at 3pm",
            messages=[
                {"role": "user", "content": "add a meeting"},
                {"role": "assistant", "content": "Sure! When should I schedule the meeting?"},
                {"role": "user", "content": "tomorrow at 3pm"},
            ],
        )
        result = await classify_intent(state)
        verdict = _judge(
            "Assistant asked 'When should I schedule the meeting?' and user answered 'tomorrow at 3pm' — "
            "this is clearly answering a clarification question, not a standalone request",
            "intent should be 'clarification_answer'",
            f"intent={result['intent']}",
        )
        assert verdict["pass"], verdict["reason"]

    @pytest.mark.asyncio
    async def test_update_intent(self):
        state = _make_state("rename meet with Alex to meet with Barney")
        result = await classify_intent(state)
        verdict = _judge(
            "User says: 'rename meet with Alex to meet with Barney'",
            "intent should be 'task_operation'",
            f"intent={result['intent']}",
        )
        assert verdict["pass"], verdict["reason"]

    @pytest.mark.asyncio
    async def test_delete_intent(self):
        state = _make_state("delete the bowling task")
        result = await classify_intent(state)
        verdict = _judge(
            "User says: 'delete the bowling task'",
            "intent should be 'task_operation'",
            f"intent={result['intent']}",
        )
        assert verdict["pass"], verdict["reason"]

    @pytest.mark.asyncio
    async def test_target_date_from_earlier_turn(self):
        state = _make_state(
            "rename it to standup",
            messages=[
                {"role": "user", "content": "create a meeting on Wednesday March 18th at 9am"},
                {"role": "assistant", "content": "Created a meeting on Wednesday March 18th."},
                {"role": "user", "content": "rename it to standup"},
            ],
        )
        result = await classify_intent(state)
        verdict = _judge(
            "User created a meeting on Wednesday March 18 and then says 'rename it to standup'",
            "target_date should be '2026-03-18' (resolved from earlier turn)",
            f"target_date={result['target_date']}",
        )
        assert verdict["pass"], verdict["reason"]


# ---------------------------------------------------------------------------
# Execute operation tests (task_operation path)
# ---------------------------------------------------------------------------

class TestExecuteOperation:

    @pytest.mark.asyncio
    async def test_create_task(self, test_db):
        state = _make_state("create a task to buy milk")
        state["relevant_tasks"] = []
        state["target_date"] = ""
        result = await execute_operation(state)
        verdict = _judge(
            "User says 'create a task to buy milk' with empty task list",
            "final_response should confirm creation, operation_result should have operation='create' and title containing 'milk'",
            f"final_response={result['final_response']!r}, operation_result={result['operation_result']}",
        )
        assert verdict["pass"], verdict["reason"]
        tasks = get_all_tasks()
        assert len(tasks) == 1

    @pytest.mark.asyncio
    async def test_update_rename_ambiguous_key(self, test_db):
        """The exact failing scenario: two M-02 tasks, user wants to rename
        'meet with Alex' to 'meet with Barney'. LLM may return title='meet with Barney'
        (the new name), but user_message has the old name for disambiguation."""
        create_task_db("id-7", "meet with Alex", "M", "2026-03-18T16:00")
        create_task_db("id-8", "meet with Barnabas", "M", "2026-03-19T16:00")

        state = _make_state("update meet with Alex to meet with Barney")
        state["relevant_tasks"] = [
            {"id": "id-7", "task_key": "M-02", "title": "meet with Alex", "category": "M", "scheduled_date": "2026-03-18T16:00", "completed": False},
            {"id": "id-8", "task_key": "M-02", "title": "meet with Barnabas", "category": "M", "scheduled_date": "2026-03-19T16:00", "completed": False},
        ]
        state["target_date"] = "2026-03-25"

        result = await execute_operation(state)

        tasks = get_all_tasks()
        renamed = [t for t in tasks if "Barney" in t.title or "barney" in t.title.lower()]
        not_renamed = [t for t in tasks if "Barnabas" in t.title]

        verdict = _judge(
            "Two tasks with key M-02: 'meet with Alex' (Mar 18) and 'meet with Barnabas' (Mar 19). "
            "User says 'update meet with Alex to meet with Barney'.",
            "'meet with Alex' should be renamed to something containing 'Barney'. "
            "'meet with Barnabas' should NOT be changed.",
            f"renamed_tasks={[t.title for t in renamed]}, "
            f"barnabas_tasks={[t.title for t in not_renamed]}, "
            f"final_response={result['final_response']!r}",
        )
        assert verdict["pass"], verdict["reason"]
        assert len(renamed) == 1, f"Expected exactly 1 renamed task, got {[t.title for t in renamed]}"
        assert len(not_renamed) == 1, "'meet with Barnabas' should be unchanged"

    @pytest.mark.asyncio
    async def test_complete_task(self, test_db):
        create_task_db("id-1", "buy groceries", "T", "2026-03-18")
        state = _make_state("mark buy groceries as done")
        state["relevant_tasks"] = [
            {"id": "id-1", "task_key": "T-01", "title": "buy groceries", "category": "T", "scheduled_date": "2026-03-18", "completed": False},
        ]
        result = await execute_operation(state)
        tasks = get_all_tasks()
        verdict = _judge(
            "User says 'mark buy groceries as done', task exists as T-01",
            "Task should be marked as completed. final_response should confirm completion.",
            f"task_completed={tasks[0].completed if tasks else 'N/A'}, final_response={result['final_response']!r}",
        )
        assert verdict["pass"], verdict["reason"]
        assert tasks[0].completed is True

    @pytest.mark.asyncio
    async def test_delete_task(self, test_db):
        create_task_db("id-1", "go bowling", "T", "2026-03-09")
        state = _make_state("delete the bowling task")
        state["relevant_tasks"] = [
            {"id": "id-1", "task_key": "T-03", "title": "go bowling", "category": "T", "scheduled_date": "2026-03-09", "completed": False},
        ]
        result = await execute_operation(state)
        tasks = get_all_tasks()
        verdict = _judge(
            "User says 'delete the bowling task', task 'go bowling' exists as T-03",
            "Task should be deleted. final_response should confirm deletion.",
            f"remaining_tasks={len(tasks)}, final_response={result['final_response']!r}",
        )
        assert verdict["pass"], verdict["reason"]
        assert len(tasks) == 0


# ---------------------------------------------------------------------------
# Execute reschedule tests
# ---------------------------------------------------------------------------

class TestExecuteReschedule:

    @pytest.mark.asyncio
    async def test_reschedule_single_task(self, test_db):
        create_task_db("id-7", "meet with Alex", "M", "2026-03-18T16:00")
        state = _make_state("move meet with Alex to March 20th at 3pm", today="2026-03-18")
        state["relevant_tasks"] = [
            {"id": "id-7", "task_key": "M-02", "title": "meet with Alex", "category": "M", "scheduled_date": "2026-03-18T16:00", "completed": False},
        ]
        state["target_date"] = "2026-03-18"
        result = await execute_reschedule(state)

        tasks = get_all_tasks()
        assert tasks[0].scheduled_date != "2026-03-18T16:00", "Task should have been rescheduled"
        verdict = _judge(
            "User says 'move meet with Alex to March 20th at 3pm'",
            "Task should be rescheduled to 2026-03-20 at 15:00. final_response should confirm.",
            f"new_scheduled_date={tasks[0].scheduled_date if tasks else 'N/A'}, final_response={result['final_response']!r}",
        )
        assert verdict["pass"], verdict["reason"]

    @pytest.mark.asyncio
    async def test_reschedule_ambiguous_key(self, test_db):
        """Two tasks with same key — reschedule should target the correct task."""
        create_task_db("id-7", "meet with Alex", "M", "2026-03-18T16:00")
        create_task_db("id-8", "meet with Barnabas", "M", "2026-03-19T16:00")

        state = _make_state("move meet with Alex to March 23rd at 2pm", today="2026-03-18")
        state["relevant_tasks"] = [
            {"id": "id-7", "task_key": "M-02", "title": "meet with Alex", "category": "M", "scheduled_date": "2026-03-18T16:00", "completed": False},
            {"id": "id-8", "task_key": "M-02", "title": "meet with Barnabas", "category": "M", "scheduled_date": "2026-03-19T16:00", "completed": False},
        ]
        state["target_date"] = "2026-03-18"
        result = await execute_reschedule(state)

        tasks = get_all_tasks()
        alex_task = next((t for t in tasks if "Alex" in t.title), None)
        barnabas_task = next((t for t in tasks if "Barnabas" in t.title), None)

        assert alex_task is not None, "Alex task should still exist"
        assert barnabas_task is not None, "Barnabas task should still exist"
        assert alex_task.scheduled_date != "2026-03-18T16:00", "Alex task should have been rescheduled"
        assert barnabas_task.scheduled_date == "2026-03-19T16:00", "Barnabas task should NOT have been changed"

        verdict = _judge(
            "Two M-02 tasks: 'meet with Alex' (originally Mar 18 16:00) and 'meet with Barnabas' (originally Mar 19 16:00). "
            "User says 'move meet with Alex to March 23rd at 2pm'.",
            "'meet with Alex' should be rescheduled away from its original date (Mar 18). "
            "'meet with Barnabas' must remain at its original date/time (2026-03-19T16:00).",
            f"alex_task: was 2026-03-18T16:00, now {alex_task.scheduled_date}. "
            f"barnabas_task: was 2026-03-19T16:00, now {barnabas_task.scheduled_date}. "
            f"final_response={result['final_response']!r}",
        )
        assert verdict["pass"], verdict["reason"]


# ---------------------------------------------------------------------------
# Full pipeline end-to-end (classify → fetch → execute)
# ---------------------------------------------------------------------------

class TestEndToEnd:

    @pytest.mark.asyncio
    async def test_create_and_verify(self, test_db):
        """Full pipeline: classify + fetch + execute for a create."""
        from graph import chat_graph

        state = _make_state("create a meeting called standup at 9am tomorrow", today="2026-03-18")
        result = await chat_graph.ainvoke(state)

        tasks = get_all_tasks()
        verdict = _judge(
            "Full pipeline: user says 'create a meeting called standup at 9am tomorrow', today=2026-03-18",
            "A task with title containing 'standup' should be created, scheduled for 2026-03-19T09:00. "
            "final_response should confirm creation.",
            f"tasks={[(t.title, t.scheduled_date) for t in tasks]}, "
            f"final_response={result['final_response']!r}",
        )
        assert verdict["pass"], verdict["reason"]
        assert len(tasks) >= 1
        standup = [t for t in tasks if "standup" in t.title.lower()]
        assert len(standup) == 1

    @pytest.mark.asyncio
    async def test_reschedule_pipeline(self, test_db):
        """Full pipeline for reschedule intent."""
        from graph import chat_graph

        create_task_db("id-1", "team sync", "M", "2026-03-18T10:00")
        state = _make_state("move team sync to 2pm", today="2026-03-18")
        result = await chat_graph.ainvoke(state)

        tasks = get_all_tasks()
        verdict = _judge(
            "Full pipeline: 'move team sync to 2pm', task exists at 10:00 on 2026-03-18",
            "Task 'team sync' should be rescheduled to 14:00 on the same day. "
            "final_response should confirm the change.",
            f"scheduled_date={tasks[0].scheduled_date if tasks else 'N/A'}, "
            f"final_response={result['final_response']!r}",
        )
        assert verdict["pass"], verdict["reason"]
