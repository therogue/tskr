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
from prompts import TITLE_PROMPT
from graph import GraphState, chat_graph
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
    load_conversation,
    save_conversation,
    new_conversation,
    list_conversations,
    get_conversation_by_id,
    get_user_settings,
    update_user_settings,
    get_conversation_title,
    update_conversation_title,
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


@app.patch("/conversations/{conversation_id}/title")
def update_conversation_title_endpoint(conversation_id: int, body: dict) -> dict:
    """Set the title of a conversation."""
    title = body.get("title", "")
    if not isinstance(title, str) or not title.strip():
        raise HTTPException(status_code=422, detail="title must be a non-empty string")
    update_conversation_title(conversation_id, title.strip())
    return {"id": conversation_id, "title": title.strip()}


async def generate_conversation_title(messages: list[dict]) -> str | None:
    """Call Claude with TITLE_PROMPT to produce a short descriptive title. Returns None on failure.
    Only the first user message is sent — the assistant's reply is structured task metadata, not useful context.
    """
    first_user = next((m["content"] for m in messages if m.get("role") == "user"), None)
    if not first_user:
        return None
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=20,
            system=TITLE_PROMPT,
            messages=[{"role": "user", "content": first_user}],
        )
        title = response.content[0].text.strip()
        return title if title else None
    except Exception:
        return None


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


def execute_operation(
    parsed: dict, today: str, conflict_resolution: str = "overlap"
) -> str:
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
            priority=priority,
        )
        if effective_date and "T" in effective_date:
            _resolve_conflicts(
                effective_date, duration_minutes or 15, task_id, conflict_resolution
            )
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
            if new_sched and "T" in new_sched:
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
    """Process user message through the LangGraph intent pipeline."""

    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-api-key-here":
        return {"response": "API key not configured", "tasks": get_all_tasks()}

    today = datetime.now().strftime("%Y-%m-%d")
    api_messages = [{"role": m.role, "content": m.content} for m in chat_request.messages]
    user_message = api_messages[-1]["content"] if api_messages else ""

    settings = get_user_settings()

    initial_state: GraphState = {
        "messages": api_messages,
        "user_message": user_message,
        "today": today,
        "intent": "",
        "extracted_context": "",
        "target_date": "",
        "relevant_tasks": [],
        "operation_result": {},
        "final_response": "",
        "default_category": settings.default_category,
        "default_priority": settings.default_priority,
        "conflict_resolution": settings.conflict_resolution,
    }

    result = await chat_graph.ainvoke(initial_state)
    response_message = result["final_response"]

    conversation = api_messages.copy()
    conversation.append({"role": "assistant", "content": response_message})

    title: str | None = None
    if chat_request.conversation_id is not None:
        conv = load_conversation(chat_request.conversation_id)

        if conv:
            new_title: str | None = None
            if conv.title == "Untitled":
                new_title = await generate_conversation_title(conversation)
                if not new_title:
                    first_user = next((m["content"] for m in conversation if m.get("role") == "user"), None)
                    if first_user:
                        new_title = first_user[:50]

            save_conversation(chat_request.conversation_id, json.dumps(conversation), title=new_title)
            title = new_title or conv.title

    return {"response": response_message, "tasks": get_all_tasks(), "title": title}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
