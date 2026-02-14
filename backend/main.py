from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import os
import json
import anthropic
from dotenv import load_dotenv

from models import Task, TaskUpdate, ChatRequest
from prompts import SYSTEM_PROMPT
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
    save_conversation
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
def get_conversation_endpoint() -> list[dict]:
    """Get saved conversation history."""
    return get_conversation()


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


def execute_operation(parsed: dict, today: str) -> str:
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
    message = parsed.get("message", "Done")

    # Create doesn't need task lookup
    if operation == "create" and title:
        effective_date = scheduled_date or (today if category in ("D", "M") else None)
        # Tasks with recurrence are created as templates
        is_template = bool(recurrence_rule)
        create_task_db(
            str(uuid.uuid4()),
            title,
            category,
            effective_date,
            recurrence_rule,
            is_template=is_template
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

        # Apply updates if any
        if updates:
            update_task_db(task.id, **updates)

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

    # Add current tasks to system prompt for context
    tasks = get_all_tasks()
    if tasks:
        task_list = "\n".join([f"- {task.task_key}: {task.title}" for task in tasks if not task.completed])
        system_prompt += f"\n\nCurrent incomplete tasks:\n{task_list}"

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

    message = execute_operation(parsed, today)

    # Save conversation with assistant response
    conversation = [{"role": m.role, "content": m.content} for m in chat_request.messages]
    conversation.append({"role": "assistant", "content": message})
    save_conversation(conversation)

    return {"response": message, "tasks": get_all_tasks()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
