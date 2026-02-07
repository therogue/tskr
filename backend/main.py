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

# System prompt for task decomposition
# Categories: T=regular tasks, D=daily tasks, M=meetings, or user-defined
# Scheduling: tasks can have scheduled_date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM)
# Recurrence: tasks can have a recurrence_rule for repeating
SYSTEM_PROMPT = """You are a task management assistant. Parse the user's request and respond with JSON only.

Supported operations:
- create: Create a new task
- complete: Mark a task as completed
- delete: Delete a task
- schedule: Schedule an existing task for a specific date/time
- set_recurrence: Set or change a task's recurrence pattern
- remove_recurrence: Stop a task from repeating

Task categories:
- T: Regular tasks (default)
- D: Daily tasks (date-specific, often recurring)
- M: Meetings (date-specific, usually have a time)
- Or any custom category the user specifies (e.g., "P" for projects)

Recurrence patterns (for recurrence_rule field):
- "daily" - Every day
- "weekdays" - Monday through Friday
- "weekly:MON,WED,FRI" - Specific days of week
- "monthly:15" - Same date each month (e.g., 15th)
- "monthly:3:WED" - Nth weekday of month (e.g., 3rd Wednesday)
- "yearly:01-15" - Same date each year (MM-DD format)

For scheduling:
- Date only: use YYYY-MM-DD format (e.g., "2025-01-21")
- Date with time: use YYYY-MM-DDTHH:MM format (e.g., "2025-01-21T15:00")
- Convert relative dates like "today", "tomorrow", "next Monday" appropriately
- Convert times to 24-hour format, e.g., "3pm" -> "15:00", "9:30am" -> "09:30"
- Today's date is: {today}

Respond with this exact JSON format:
{{
    "operation": "create" | "complete" | "delete" | "schedule" | "set_recurrence" | "remove_recurrence",
    "title": "task title here",
    "category": "T" | "D" | "M" | custom,
    "scheduled_date": "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM" or null,
    "recurrence_rule": "pattern" or null,
    "message": "friendly response to user"
}}

For complete/delete/schedule/set_recurrence/remove_recurrence, you can also use "task_key" instead of "title" to identify the task (e.g., "M-01").

If the request is unclear or not a task operation, respond with:
{{
    "operation": "none",
    "message": "your clarifying question or response"
}}

Only respond with valid JSON, no other text."""


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
    result = update_task_db(
        task_id,
        task_data.title,
        task_data.completed,
        task_data.scheduled_date,
        task_data.recurrence_rule
    )
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


def find_task(title: str = None, task_key: str = None) -> dict | None:
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

    # All other operations require finding the task first
    if operation in ("complete", "delete", "schedule", "set_recurrence", "remove_recurrence"):
        task = find_task(title, task_key)
        if not task:
            return f"Could not find task matching '{task_key or title}'"

        if operation == "complete":
            update_task_db(task["id"], completed=True)
        elif operation == "delete":
            delete_task_db(task["id"])
        elif operation == "schedule":
            if scheduled_date:
                update_task_db(task["id"], scheduled_date=scheduled_date)
            else:
                return "No date provided for scheduling"
        elif operation == "set_recurrence":
            # Convert existing task to a template
            # Note: This is a simplified approach - ideally we'd create a new template
            if recurrence_rule:
                new_scheduled = scheduled_date or task.get("scheduled_date") or today
                update_task_db(task["id"], scheduled_date=new_scheduled, recurrence_rule=recurrence_rule)
            else:
                return "No recurrence pattern provided"
        elif operation == "remove_recurrence":
            update_task_db(task["id"], recurrence_rule="")

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
