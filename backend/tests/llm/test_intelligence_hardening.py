"""
LLM tests for Issue #45 — Intelligence Hardening.
Tests duplicate detection, required fields, and enriched context.

Run with: pytest --run-llm -v -s tests/llm/test_intelligence_hardening.py
"""

import json
import os

import anthropic
import pytest
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

pytestmark = pytest.mark.llm

from database import create_task_db, get_all_tasks
from graph import execute_operation, execute_reschedule, GraphState

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


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

class TestDuplicateDetection:

    @pytest.mark.asyncio
    async def test_exact_duplicate_blocked(self, test_db):
        """LLM should warn when a task with the same title already exists."""
        create_task_db("id-1", "buy groceries", "T", "2026-03-18")
        state = _make_state("create a task to buy groceries", today="2026-03-18")
        state["relevant_tasks"] = [
            {"id": "id-1", "task_key": "T-01", "title": "buy groceries", "category": "T", "scheduled_date": "2026-03-18", "completed": False},
        ]
        result = await execute_operation(state)

        tasks = get_all_tasks()
        verdict = _judge(
            "User says 'create a task to buy groceries' but 'buy groceries' already exists as T-01",
            "LLM should NOT create a duplicate. It should either warn about the existing task or ask the user to confirm. "
            "There should still be only 1 task.",
            f"task_count={len(tasks)}, final_response={result['final_response']!r}, "
            f"operation_result={result['operation_result']}",
        )
        assert verdict["pass"], verdict["reason"]
        assert len(tasks) == 1, f"Expected 1 task (no duplicate), got {len(tasks)}"

    @pytest.mark.skip(reason="Semantic duplicate detection is non-trivial — LLM struggles to equate e.g. 'shoot hoops' with 'play basketball'. Revisit if we invest in embedding-based similarity.")
    @pytest.mark.asyncio
    async def test_semantic_duplicate_blocked(self, test_db):
        """LLM should detect semantically similar tasks as potential duplicates."""
        create_task_db("id-1", "play basketball at 3pm", "T", "2026-03-18T15:00")
        state = _make_state("add a task to shoot hoops this afternoon", today="2026-03-18")
        state["relevant_tasks"] = [
            {"id": "id-1", "task_key": "T-01", "title": "play basketball at 3pm", "category": "T", "scheduled_date": "2026-03-18T15:00", "completed": False},
        ]
        result = await execute_operation(state)

        tasks = get_all_tasks()
        verdict = _judge(
            "User says 'add a task to shoot hoops this afternoon' but 'play basketball at 3pm' already exists. "
            "These are semantically the same activity.",
            "LLM should detect the similarity and either warn about the existing task or ask the user to confirm. "
            "There should still be only 1 task.",
            f"task_count={len(tasks)}, final_response={result['final_response']!r}, "
            f"operation_result={result['operation_result']}",
        )
        assert verdict["pass"], verdict["reason"]
        assert len(tasks) == 1, f"Expected 1 task (no duplicate), got {len(tasks)}"


# ---------------------------------------------------------------------------
# Required fields (duration, priority)
# ---------------------------------------------------------------------------

class TestRequiredFields:

    @pytest.mark.asyncio
    async def test_create_has_duration_and_priority(self, test_db):
        """Created tasks must always have duration_minutes and priority populated."""
        from graph import chat_graph

        state = _make_state("add a task to review the pull request", today="2026-03-18")
        await chat_graph.ainvoke(state)

        tasks = get_all_tasks()
        assert len(tasks) == 1
        task = tasks[0]
        assert task.duration_minutes is not None, "duration_minutes should not be null"
        assert task.duration_minutes > 0, "duration_minutes should be positive"
        assert task.priority is not None, "priority should not be null"
        assert 0 <= task.priority <= 4, f"priority should be 0-4, got {task.priority}"

    @pytest.mark.asyncio
    async def test_vague_task_has_duration_and_priority(self, test_db):
        """Even vague tasks with no clear scope should get duration and priority."""
        from graph import chat_graph

        state = _make_state("add a reminder to check on things", today="2026-03-18")
        await chat_graph.ainvoke(state)

        tasks = get_all_tasks()
        assert len(tasks) == 1
        task = tasks[0]
        assert task.duration_minutes is not None, "duration_minutes should not be null for vague task"
        assert task.duration_minutes > 0, "duration_minutes should be positive"
        assert task.priority is not None, "priority should not be null for vague task"
        assert 0 <= task.priority <= 4, f"priority should be 0-4, got {task.priority}"

    @pytest.mark.asyncio
    async def test_minimal_input_has_duration_and_priority(self, test_db):
        """Bare-minimum input should still produce duration and priority."""
        from graph import chat_graph

        state = _make_state("task: milk", today="2026-03-18")
        await chat_graph.ainvoke(state)

        tasks = get_all_tasks()
        assert len(tasks) == 1
        task = tasks[0]
        assert task.duration_minutes is not None, "duration_minutes should not be null for minimal input"
        assert task.duration_minutes > 0, "duration_minutes should be positive"
        assert task.priority is not None, "priority should not be null for minimal input"
        assert 0 <= task.priority <= 4, f"priority should be 0-4, got {task.priority}"

    @pytest.mark.asyncio
    async def test_abstract_task_has_duration_and_priority(self, test_db):
        """Non-actionable/abstract tasks should still get estimated duration and priority."""
        from graph import chat_graph

        state = _make_state("think about career goals", today="2026-03-18")
        await chat_graph.ainvoke(state)

        tasks = get_all_tasks()
        assert len(tasks) == 1
        task = tasks[0]
        assert task.duration_minutes is not None, "duration_minutes should not be null for abstract task"
        assert task.duration_minutes > 0, "duration_minutes should be positive"
        assert task.priority is not None, "priority should not be null for abstract task"
        assert 0 <= task.priority <= 4, f"priority should be 0-4, got {task.priority}"

    @pytest.mark.asyncio
    async def test_time_only_task_has_duration_and_priority(self, test_db):
        """Tasks with only a time and no effort description should still get duration and priority."""
        from graph import chat_graph

        state = _make_state("something at 2pm", today="2026-03-18")
        await chat_graph.ainvoke(state)

        tasks = get_all_tasks()
        assert len(tasks) == 1
        task = tasks[0]
        assert task.duration_minutes is not None, "duration_minutes should not be null for time-only task"
        assert task.duration_minutes > 0, "duration_minutes should be positive"
        assert task.priority is not None, "priority should not be null for time-only task"
        assert 0 <= task.priority <= 4, f"priority should be 0-4, got {task.priority}"


# ---------------------------------------------------------------------------
# Enriched context
# ---------------------------------------------------------------------------

class TestEnrichedContext:

    @pytest.mark.asyncio
    async def test_reschedule_preserves_duration_and_priority(self, test_db):
        """Duration and priority should be preserved through a reschedule operation."""
        create_task_db("id-1", "buy groceries", "T", "2026-03-18", duration_minutes=30, priority=2)

        state = _make_state("reschedule buy groceries to tomorrow", today="2026-03-18")
        state["relevant_tasks"] = [
            {"id": "id-1", "task_key": "T-01", "title": "buy groceries", "category": "T",
             "scheduled_date": "2026-03-18", "completed": False,
             "duration_minutes": 30, "priority": 2},
        ]
        await execute_reschedule(state)

        tasks = get_all_tasks()
        assert tasks[0].duration_minutes == 30, "duration should be preserved after reschedule"
        assert tasks[0].priority == 2, "priority should be preserved after reschedule"
