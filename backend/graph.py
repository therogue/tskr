import json
import os
import uuid
from contextlib import nullcontext
from typing import Optional, TypedDict

import anthropic
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from database import (
    create_task_db,
    delete_task_db,
    get_all_tasks,
    get_tasks_for_date,
    update_task_db,
)
from prompts import INTENT_PROMPT, RESCHEDULE_PROMPT, SYSTEM_PROMPT
from scheduling import build_schedule_context

load_dotenv()
_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

LANGFUSE_ENABLED = False
_langfuse = None

try:
    if os.getenv("LANGFUSE_SECRET_KEY") and os.getenv("LANGFUSE_PUBLIC_KEY"):
        from langfuse import Langfuse
        _langfuse = Langfuse()
        LANGFUSE_ENABLED = True
        print("[graph] Langfuse enabled")
    else:
        print("[graph] Langfuse disabled — LANGFUSE_SECRET_KEY or LANGFUSE_PUBLIC_KEY not set")
except Exception as e:
    print(f"[graph] Langfuse disabled — init error: {type(e).__name__}: {e}")


class GraphState(TypedDict):
    messages: list[dict]       # full conversation history in Anthropic API format
    user_message: str
    today: str
    intent: str                # "task_operation" | "clarification_answer" | "reschedule"
    extracted_context: str     # entities pulled from classify_intent or resolve_clarification
    target_date: str           # YYYY-MM-DD from classify_intent, or "" if none mentioned
    relevant_tasks: list[dict]
    operation_result: dict     # raw parsed LLM JSON
    final_response: str
    default_category: str      # user setting, e.g. "T"
    default_priority: str      # user setting, e.g. "medium"
    conflict_resolution: str   # user setting: "overlap" | "unschedule" | "backlog"
    langfuse_trace_id: str     # set by classify_intent; empty string when Langfuse is disabled


# ---------------------------------------------------------------------------
# Private helpers (mirrors execute_operation logic from main.py to avoid
# circular import — main.py imports graph.py, so graph.py cannot import main.py)
# ---------------------------------------------------------------------------

def _strip_markdown(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def _find_task_in_scope(
    relevant_tasks: list[dict],
    title: str = "",
    task_key: str = "",
    target_date: str = "",
    user_message: str = "",
) -> Optional[dict]:
    """Find a task from the scoped list by task_key (preferred) or title substring.
    When task_key matches multiple tasks, narrows by:
      1. target_date (scheduled_date prefix)
      2. title substring (LLM's title vs task titles)
      3. user_message substring (original user input vs task titles)
    """
    if task_key:
        matches = [t for t in relevant_tasks if t["task_key"] == task_key.upper()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            if target_date:
                date_matches = [
                    t for t in matches
                    if t.get("scheduled_date", "")[:10] == target_date
                ]
                if len(date_matches) == 1:
                    print(f"[graph] _find_task_in_scope: disambiguated {task_key} by target_date={target_date}")
                    return date_matches[0]
            if title:
                title_matches = [
                    t for t in matches
                    if title.lower() in t["title"].lower() or t["title"].lower() in title.lower()
                ]
                if len(title_matches) == 1:
                    print(f"[graph] _find_task_in_scope: disambiguated {task_key} by title={title!r}")
                    return title_matches[0]
            # Use the raw user message — contains the ORIGINAL task name
            if user_message:
                msg_lower = user_message.lower()
                msg_matches = [
                    t for t in matches
                    if t["title"].lower() in msg_lower
                ]
                if len(msg_matches) == 1:
                    print(f"[graph] _find_task_in_scope: disambiguated {task_key} by user_message")
                    return msg_matches[0]
            match_titles = [t["title"] for t in matches]
            print(f"[graph] _find_task_in_scope: {task_key} still ambiguous ({len(matches)} matches: {match_titles})")
        return None
    if title:
        matches = [t for t in relevant_tasks if title.lower() in t["title"].lower()]
        if len(matches) == 1:
            return matches[0]
        return None
    return None


def _time_to_minutes(scheduled_date: str) -> int:
    """Parse YYYY-MM-DDTHH:MM and return minutes since midnight."""
    h, m = map(int, scheduled_date[11:16].split(":"))
    return h * 60 + m


def _resolve_conflicts(
    new_scheduled_date: str,
    new_duration_minutes: int,
    exclude_task_id: str,
    conflict_resolution: str,
) -> None:
    """Find tasks overlapping new_scheduled_date's time slot and apply conflict_resolution."""
    if conflict_resolution == "overlap":
        return
    if not new_scheduled_date or "T" not in new_scheduled_date:
        return

    new_date = new_scheduled_date[:10]
    new_start = _time_to_minutes(new_scheduled_date)
    new_end = new_start + new_duration_minutes

    for task in get_all_tasks():
        if task.id == exclude_task_id or task.completed or task.is_template:
            continue
        if not task.scheduled_date or "T" not in task.scheduled_date:
            continue
        if task.scheduled_date[:10] != new_date:
            continue
        task_start = _time_to_minutes(task.scheduled_date)
        task_end = task_start + (task.duration_minutes or 15)
        if new_start < task_end and new_end > task_start:
            if conflict_resolution == "unschedule":
                update_task_db(task.id, scheduled_date=task.scheduled_date[:10])
            elif conflict_resolution == "backlog":
                update_task_db(task.id, scheduled_date=None)


def _apply_operation(
    parsed: dict, today: str, relevant_tasks: list[dict],
    conflict_resolution: str = "overlap",
    target_date: str = "", user_message: str = "",
) -> str:
    """Execute a task operation from a parsed LLM response. Returns user-facing message.
    relevant_tasks: task list used for lookups and ambiguity resolution.
    target_date: date hint from classify_intent for disambiguating duplicate keys.
    user_message: raw user input for disambiguation when key and title both fail.
    """
    operation = parsed.get("operation", "none")
    title = parsed.get("title", "")
    task_key = parsed.get("task_key", "")
    category = (parsed.get("category") or "T").upper()
    scheduled_date = parsed.get("scheduled_date")
    recurrence_rule = parsed.get("recurrence_rule")
    duration_minutes = parsed.get("duration_minutes")
    priority = parsed.get("priority")
    message = parsed.get("message", "Done")

    print(f"[graph] _apply_operation: op={operation} key={task_key!r} title={title!r} scheduled_date={scheduled_date!r}")

    if operation == "create" and title:
        # Issue #45: enforce sensible defaults at the LLM-aware layer so new
        # tasks never have null duration/priority. Updates keep null-as-noop.
        if duration_minutes is None:
            duration_minutes = 15
        if priority is None:
            priority = 2
        task_id = str(uuid.uuid4())
        effective_date = scheduled_date or (today if category in ("D", "M") else None)
        is_template = bool(recurrence_rule)
        create_task_db(
            task_id,
            title,
            category,
            effective_date,
            recurrence_rule,
            is_template=is_template,
            duration_minutes=duration_minutes,
            priority=priority,
        )
        if effective_date and "T" in effective_date:
            _resolve_conflicts(effective_date, duration_minutes or 15, task_id, conflict_resolution)
        print(f"[graph] created task: {title!r} date={effective_date!r}")
        return message

    if operation == "update":
        scoped = _find_task_in_scope(relevant_tasks, title, task_key, target_date, user_message)
        if not scoped:
            print(f"[graph] update: task not found in scoped list for key={task_key!r} title={title!r} user_message={user_message!r}")
            return f"Sorry, I couldn't identify which task to update. Could you specify the exact task title or key?"
        task_id = scoped["id"]
        print(f"[graph] update: found task id={task_id} key={scoped['task_key']} title={scoped['title']!r} current_scheduled={scoped['scheduled_date']!r}")
        updates: dict = {}
        completed = parsed.get("completed")
        if title and title != scoped["title"]:
            updates["title"] = title
        if category and category != scoped["category"]:
            updates["category"] = category
        if scheduled_date is not None and scheduled_date != scoped["scheduled_date"]:
            updates["scheduled_date"] = scheduled_date
        if recurrence_rule is not None:
            updates["recurrence_rule"] = recurrence_rule
        if completed is not None and completed != scoped["completed"]:
            updates["completed"] = completed
        if duration_minutes is not None:
            updates["duration_minutes"] = duration_minutes
        if priority is not None:
            updates["priority"] = priority
        print(f"[graph] update: applying updates={updates}")
        if updates:
            update_task_db(task_id, **updates)
            new_sched = updates.get("scheduled_date")
            if new_sched and "T" in new_sched:
                dur = updates.get("duration_minutes") or duration_minutes or 15
                _resolve_conflicts(new_sched, dur, task_id, conflict_resolution)
        else:
            print(f"[graph] update: no changes — task already matches requested state")
            return "That task is already up to date — nothing was changed."
        return message

    if operation == "delete":
        scoped = _find_task_in_scope(relevant_tasks, title, task_key, target_date, user_message)
        if not scoped:
            print(f"[graph] delete: task not found in scoped list for key={task_key!r} title={title!r} user_message={user_message!r}")
            return f"Sorry, I couldn't identify which task to delete. Could you specify the exact task title or key?"
        delete_task_db(scoped["id"])
        print(f"[graph] deleted task id={scoped['id']} key={scoped['task_key']}")
        return message

    return message


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

async def classify_intent(state: GraphState) -> dict:
    """LLM call: classify user intent into task_operation | clarification_answer | reschedule."""
    trace_id = _langfuse.create_trace_id() if LANGFUSE_ENABLED else ""
    system = INTENT_PROMPT.format(today=state["today"])
    try:
        with (
            _langfuse.start_as_current_observation(
                trace_context={"trace_id": trace_id},
                name="classify_intent",
                as_type="generation",
                model="claude-sonnet-4-5",
                input=state["messages"],
            )
            if LANGFUSE_ENABLED
            else nullcontext()
        ):
            response = await _client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=128,
                system=system,
                messages=state["messages"],
            )
            if LANGFUSE_ENABLED:
                _langfuse.update_current_generation(
                    output=response.content[0].text,
                    usage_details={"input": response.usage.input_tokens, "output": response.usage.output_tokens},
                )
        if LANGFUSE_ENABLED:
            _langfuse.flush()
        parsed = json.loads(_strip_markdown(response.content[0].text))
        intent = parsed.get("intent", "task_operation")
        context = parsed.get("extracted_context", "")
        target_date = parsed.get("target_date") or ""
        print(f"[graph] classify_intent: intent={intent!r} context={context!r} target_date={target_date!r}")
        return {"intent": intent, "extracted_context": context, "target_date": target_date, "langfuse_trace_id": trace_id}
    except Exception as e:
        print(f"[graph] classify_intent error: {e} — defaulting to task_operation")
        return {"intent": "task_operation", "extracted_context": "", "target_date": "", "langfuse_trace_id": trace_id}


def resolve_clarification(state: GraphState) -> dict:
    """
    No LLM call. Scan conversation history for the last assistant message (the prior
    clarification question) and prepend it to extracted_context so execute_operation
    has full context when the user's answer is processed.
    """
    messages = state["messages"]
    for msg in reversed(messages[:-1]):
        if msg.get("role") == "assistant":
            combined = (
                f"Prior assistant question: {msg['content']}\n"
                f"User answered: {state['extracted_context']}"
            )
            print(f"[graph] resolve_clarification: found prior question, merged context")
            return {"extracted_context": combined}
    print(f"[graph] resolve_clarification: no prior assistant message found")
    return {}


def _fetch_tasks_for_state(state: GraphState, label: str) -> list[dict]:
    """Always fetch all incomplete tasks. target_date is passed to the LLM for prioritization."""
    tasks = [t for t in get_all_tasks() if not t.completed]
    target_date = state.get("target_date", "")
    print(f"[graph] {label}: {len(tasks)} incomplete task(s), target_date={target_date!r}")

    return [
        {
            "id": t.id,
            "task_key": t.task_key,
            "title": t.title,
            "category": t.category,
            "scheduled_date": t.scheduled_date,
            "completed": t.completed,
            "duration_minutes": t.duration_minutes,
            "priority": t.priority,
            "recurrence_rule": t.recurrence_rule,
        }
        for t in tasks
    ]


def fetch_tasks_op(state: GraphState) -> dict:
    """Fetch tasks for task_operation and clarification_answer paths."""
    return {"relevant_tasks": _fetch_tasks_for_state(state, "fetch_tasks_op")}


def fetch_tasks_rs(state: GraphState) -> dict:
    """Fetch tasks for the reschedule path."""
    return {"relevant_tasks": _fetch_tasks_for_state(state, "fetch_tasks_rs")}


async def execute_operation(state: GraphState) -> dict:
    """LLM call: parse intent into a task operation and execute it."""
    today = state["today"]
    tasks = state["relevant_tasks"]

    trace_id = state.get("langfuse_trace_id", "")
    target_date = state.get("target_date", "")
    system = SYSTEM_PROMPT.format(today=today)

    default_category = state.get("default_category", "T")
    default_priority = state.get("default_priority", "medium")
    system += (
        f"\n\nUser-configured defaults — use these exactly; do not estimate or override:"
        f"\n- Default category: {default_category}"
        f"\n- Default priority: {default_priority} (ignore task description when assigning priority;"
        f" always use this value unless the user explicitly states a different priority)"
    )

    if tasks:
        task_list = "\n".join(
            f"- {t['task_key']}: {t['title']} (scheduled: {t['scheduled_date'] or 'unscheduled'})"
            for t in tasks
        )
        print(f"[graph] execute_operation task_list:\n{task_list}")
        system += f"\n\nCurrent incomplete tasks:\n{task_list}"
    if target_date:
        system += f"\n\nThe user is referring to tasks on: {target_date}. Prefer matching tasks scheduled on this date."

    today_tasks = get_tasks_for_date(today, today)
    schedule_context = build_schedule_context(today_tasks)
    if schedule_context:
        system += schedule_context

    try:
        with (
            _langfuse.start_as_current_observation(
                trace_context={"trace_id": trace_id},
                name="execute_operation",
                as_type="generation",
                model="claude-sonnet-4-5",
                input=state["messages"],
            )
            if LANGFUSE_ENABLED and trace_id
            else nullcontext()
        ):
            response = await _client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=256,
                system=system,
                messages=state["messages"],
            )
            ai_text = response.content[0].text
            if LANGFUSE_ENABLED and trace_id:
                _langfuse.update_current_generation(
                    output=ai_text,
                    usage_details={"input": response.usage.input_tokens, "output": response.usage.output_tokens},
                )
        if LANGFUSE_ENABLED and trace_id:
            _langfuse.flush()
        print(f"[graph] execute_operation raw: {ai_text}")
        parsed = json.loads(_strip_markdown(ai_text))
    except json.JSONDecodeError:
        print(f"[graph] execute_operation: LLM returned non-JSON, using raw text as response")
        return {"operation_result": {}, "final_response": ai_text}
    except Exception as e:
        print(f"[graph] execute_operation error: {e}")
        return {"operation_result": {}, "final_response": f"Error processing request: {e}"}

    conflict_resolution = state.get("conflict_resolution", "overlap")
    user_message = state.get("user_message", "")
    message = _apply_operation(parsed, today, tasks, conflict_resolution, target_date, user_message)
    return {"operation_result": parsed, "final_response": message}


async def execute_reschedule(state: GraphState) -> dict:
    """LLM call: identify which tasks to reschedule and apply the date updates."""
    today = state["today"]
    tasks = state["relevant_tasks"]

    trace_id = state.get("langfuse_trace_id", "")
    task_list = (
        "\n".join(
            f"- {t['task_key']}: {t['title']} (scheduled: {t['scheduled_date'] or 'unscheduled'})"
            for t in tasks
        )
        if tasks
        else "No tasks found."
    )

    target_date = state.get("target_date", "")
    print(f"[graph] execute_reschedule task_list:\n{task_list}")
    system = RESCHEDULE_PROMPT.format(today=today, task_list=task_list)
    if target_date:
        system += f"\n\nThe user is referring to tasks on: {target_date}. Prefer matching tasks scheduled on this date."

    try:
        with (
            _langfuse.start_as_current_observation(
                trace_context={"trace_id": trace_id},
                name="execute_reschedule",
                as_type="generation",
                model="claude-sonnet-4-5",
                input=state["messages"],
            )
            if LANGFUSE_ENABLED and trace_id
            else nullcontext()
        ):
            response = await _client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=256,
                system=system,
                messages=state["messages"],
            )
            ai_text = response.content[0].text
            if LANGFUSE_ENABLED and trace_id:
                _langfuse.update_current_generation(
                    output=ai_text,
                    usage_details={"input": response.usage.input_tokens, "output": response.usage.output_tokens},
                )
        if LANGFUSE_ENABLED and trace_id:
            _langfuse.flush()
        print(f"[graph] execute_reschedule raw: {ai_text}")
        parsed = json.loads(_strip_markdown(ai_text))
    except json.JSONDecodeError:
        print(f"[graph] execute_reschedule: LLM returned non-JSON, using raw text as response")
        return {"operation_result": {}, "final_response": ai_text}
    except Exception as e:
        print(f"[graph] execute_reschedule error: {e}")
        return {"operation_result": {}, "final_response": f"Error processing reschedule: {e}"}

    updated_count = 0
    not_found_keys = []
    for item in parsed.get("reschedules", []):
        task_key = item.get("task_key", "")
        new_date = item.get("new_scheduled_date")
        print(f"[graph] execute_reschedule: rescheduling key={task_key!r} to {new_date!r}")
        if task_key and new_date:
            user_message = state.get("user_message", "")
            title_hint = item.get("title", "")
            scoped = _find_task_in_scope(
                tasks, title=title_hint, task_key=task_key,
                target_date=target_date, user_message=user_message,
            )
            if scoped:
                update_task_db(scoped["id"], scheduled_date=new_date)
                print(f"[graph] execute_reschedule: updated task id={scoped['id']} title={scoped['title']!r}")
                updated_count += 1
            else:
                print(f"[graph] execute_reschedule: task not found in scoped list for key={task_key!r}")
                not_found_keys.append(task_key)

    if not_found_keys:
        return {
            "operation_result": parsed,
            "final_response": f"Could not find task(s) {', '.join(not_found_keys)} to reschedule.",
        }
    if updated_count == 0 and parsed.get("reschedules"):
        return {
            "operation_result": parsed,
            "final_response": "No tasks were rescheduled.",
        }

    return {"operation_result": parsed, "final_response": parsed.get("message", "Done")}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def _route_intent(state: GraphState) -> str:
    intent = state["intent"]
    if intent == "clarification_answer":
        print(f"[graph] route → resolve_clarification")
        return "resolve_clarification"
    if intent == "reschedule":
        print(f"[graph] route → fetch_tasks_rs (reschedule)")
        return "fetch_tasks_rs"
    print(f"[graph] route → fetch_tasks_op (task_operation)")
    return "fetch_tasks_op"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

_builder = StateGraph(GraphState)

_builder.add_node("classify_intent", classify_intent)
_builder.add_node("resolve_clarification", resolve_clarification)
_builder.add_node("fetch_tasks_op", fetch_tasks_op)
_builder.add_node("fetch_tasks_rs", fetch_tasks_rs)
_builder.add_node("execute_operation", execute_operation)
_builder.add_node("execute_reschedule", execute_reschedule)

_builder.add_edge(START, "classify_intent")
_builder.add_conditional_edges(
    "classify_intent",
    _route_intent,
    {
        "resolve_clarification": "resolve_clarification",
        "fetch_tasks_op": "fetch_tasks_op",
        "fetch_tasks_rs": "fetch_tasks_rs",
    },
)
_builder.add_edge("resolve_clarification", "fetch_tasks_op")
_builder.add_edge("fetch_tasks_op", "execute_operation")
_builder.add_edge("fetch_tasks_rs", "execute_reschedule")
_builder.add_edge("execute_operation", END)
_builder.add_edge("execute_reschedule", END)

chat_graph = _builder.compile()
