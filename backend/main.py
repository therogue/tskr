from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import os
import json
import anthropic
from dotenv import load_dotenv

from models import Task, TaskUpdate, ChatRequest, UserSettingsRead, UserSettingsUpdate
from prompts import SYSTEM_PROMPT
from scheduling import build_schedule_context
from database import (
    init_db,
    get_all_tasks,
    get_tasks_for_date,
    create_task_db,
    update_task_db,
    delete_task_db,
    find_task_by_title_db,
    find_task_by_key_db,
    get_conversation,
    save_conversation,
    new_conversation,
    list_conversations,
    get_conversation_by_id,
    get_user_settings,
    update_user_settings,
)

load_dotenv()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown (nothing to do)

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)



@app.get("/tasks")
def get_tasks() -> list[Task]:
    return get_all_tasks()


@app.get("/tasks/for-date")
def get_tasks_for_date_endpoint(date: str) -> list[Task]:
    """Get tasks for a specific date (day view)."""
    today = datetime.now().strftime("%Y-%m-%d")
    return get_tasks_for_date(date, today)


@app.patch("/tasks/{task_id}")
def update_task(task_id: str, task_data: TaskUpdate) -> Task:
    # Only pass fields that were explicitly set
    updates = task_data.model_dump(exclude_unset=True)
    result = update_task_db(task_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@app.delete("/tasks/{task_id}")
def delete_task(task_id: str) -> dict:
    if not delete_task_db(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}


@app.get("/conversation")
def get_conversation_endpoint() -> dict:
    """Get the most recent conversation as {id, messages}."""
    return get_conversation()


@app.post("/conversation/new")
def new_conversation_endpoint() -> dict:
    """Archive current conversation and start a new one."""
    conv_id = new_conversation()
    return {"id": conv_id}


@app.get("/conversations")
def list_conversations_endpoint(limit: int | None = None) -> list[dict]:
    """List conversations ordered by recency. Optionally limit to N most recent."""
    return list_conversations(limit)


@app.get("/conversations/{conversation_id}")
def get_conversation_by_id_endpoint(conversation_id: int) -> dict:
    """Get messages for a specific conversation."""
    result = get_conversation_by_id(conversation_id)
    if result["id"] is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result


@app.get("/settings")
def get_settings() -> UserSettingsRead:
    return get_user_settings()


@app.patch("/settings")
def patch_settings(data: UserSettingsUpdate) -> UserSettingsRead:
    updates = data.model_dump(exclude_unset=True)
    return update_user_settings(**updates)


def _time_to_minutes(scheduled_date: str) -> int:
    """Parse YYYY-MM-DDTHH:MM and return minutes since midnight."""
    h, m = map(int, scheduled_date[11:16].split(':'))
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
    if not new_scheduled_date or 'T' not in new_scheduled_date:
        return

    new_date = new_scheduled_date[:10]
    new_start = _time_to_minutes(new_scheduled_date)
    new_end = new_start + new_duration_minutes

    for task in get_all_tasks():
        if task.id == exclude_task_id or task.completed or task.is_template:
            continue
        if not task.scheduled_date or 'T' not in task.scheduled_date:
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


def find_task(title: str = None, task_key: str = None) -> Task | None:
    """Find a task by title or task_key."""
    if task_key:
        return find_task_by_key_db(task_key)
    if title:
        return find_task_by_title_db(title)
    return None


def strip_markdown_(text: str) -> str:
    """Remove markdown code block wrapper if present."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")[1:]  # Skip first line (```json)
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def execute_operation(parsed: dict, today: str, conflict_resolution: str = "overlap") -> str:
    """
    Execute a task operation based on parsed Claude response.
    Returns the message to display to the user.

    Tasks with recurrence_rule are created as templates (is_template=True).
    Templates generate instances for specific dates via get_tasks_for_date().
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

    # Create doesn't need task lookup
    if operation == "create" and title:
        task_id = str(uuid.uuid4())
        effective_date = scheduled_date or (today if category in ("D", "M") else None)
        # Tasks with recurrence are created as templates
        is_template = bool(recurrence_rule)
        create_task_db(
            task_id,
            title,
            category,
            effective_date,
            recurrence_rule,
            is_template=is_template,
            duration_minutes=duration_minutes,
            priority=priority
        )
        if effective_date and 'T' in effective_date:
            _resolve_conflicts(effective_date, duration_minutes or 15, task_id, conflict_resolution)
        return message

    # Update and delete operations require finding the task first
    if operation == "update":
        task = find_task(title, task_key)
        if not task:
            return f"Could not find task matching '{task_key or title}'"

        # Build updates dict from any fields provided by LLM
        updates = {}
        completed = parsed.get("completed")

        if title and title != task.title:
            updates["title"] = title
        if category and category != task.category:
            updates["category"] = category
        if scheduled_date is not None and scheduled_date != task.scheduled_date:
            updates["scheduled_date"] = scheduled_date
        if recurrence_rule is not None and recurrence_rule != task.recurrence_rule:
            updates["recurrence_rule"] = recurrence_rule
        if completed is not None and completed != task.completed:
            updates["completed"] = completed
        if duration_minutes is not None and duration_minutes != task.duration_minutes:
            updates["duration_minutes"] = duration_minutes
        if priority is not None and priority != task.priority:
            updates["priority"] = priority

        # Apply updates if any
        if updates:
            update_task_db(task.id, **updates)
            new_sched = updates.get("scheduled_date")
            if new_sched and 'T' in new_sched:
                dur = updates.get("duration_minutes") or task.duration_minutes or 15
                _resolve_conflicts(new_sched, dur, task.id, conflict_resolution)

    elif operation == "delete":
        task = find_task(title, task_key)
        if not task:
            return f"Could not find task matching '{task_key or title}'"
        delete_task_db(task.id)

    return message


@app.post("/chat")
async def chat(chat_request: ChatRequest) -> dict:
    """Process user message through Claude and execute task operations."""

    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-api-key-here":
        return {"response": "API key not configured", "tasks": get_all_tasks()}

    # Convert messages to Claude API format
    api_messages = [{"role": m.role, "content": m.content} for m in chat_request.messages]

    # Insert today's date into the system prompt
    today = datetime.now().strftime("%Y-%m-%d")
    system_prompt = SYSTEM_PROMPT.format(today=today)

    # Inject user defaults so Claude uses them when the user doesn't specify
    settings = get_user_settings()
    system_prompt += (
        f"\n\nUser-configured defaults — use these exactly; do not estimate or override:"
        f"\n- Default category: {settings.default_category}"
        f"\n- Default priority: {settings.default_priority} (ignore task description when assigning priority; always use this value unless the user explicitly states a different priority)"
    )

    # Add current tasks to system prompt for context
    tasks = get_all_tasks()
    if tasks:
        task_list = "\n".join([f"- {task.task_key}: {task.title}" for task in tasks if not task.completed])
        system_prompt += f"\n\nCurrent incomplete tasks:\n{task_list}"

    # Add today's schedule context for auto-scheduling
    today_tasks = get_tasks_for_date(today, today)
    schedule_context = build_schedule_context(today_tasks)
    if schedule_context:
        system_prompt += schedule_context

    # Call Claude API
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=256,
            system=system_prompt,
            messages=api_messages
        )
    except anthropic.APIError as e:
        return {"response": f"API error: {e}", "tasks": get_all_tasks()}

    ai_text = response.content[0].text
    print(f"Claude response: {ai_text}")

    try:
        parsed = json.loads(strip_markdown_(ai_text))
    except json.JSONDecodeError:
        return {"response": "Failed to parse AI response", "tasks": get_all_tasks()}

    message = execute_operation(parsed, today, settings.conflict_resolution)

    # Save conversation with assistant response
    conversation = [{"role": m.role, "content": m.content} for m in chat_request.messages]
    conversation.append({"role": "assistant", "content": message})
    if chat_request.conversation_id is not None:
        save_conversation(conversation, chat_request.conversation_id)

    return {"response": message, "tasks": get_all_tasks()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
