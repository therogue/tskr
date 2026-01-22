from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import os
import json
import anthropic
from dotenv import load_dotenv

from models import TaskCreate, TaskUpdate, ChatRequest
from database import (
    init_db,
    get_all_tasks,
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
# Scheduling: tasks can have a scheduled_date (ISO format YYYY-MM-DD)
# Recurrence: tasks can have a recurrence_rule for repeating
SYSTEM_PROMPT = """You are a task management assistant. Parse the user's request and respond with JSON only.

Supported operations:
- create: Create a new task
- complete: Mark a task as completed
- delete: Delete a task
- schedule: Schedule an existing task for a specific date
- set_recurrence: Set or change a task's recurrence pattern
- remove_recurrence: Stop a task from repeating

Task categories:
- T: Regular tasks (default)
- D: Daily tasks (date-specific, often recurring)
- M: Meetings (date-specific)
- Or any custom category the user specifies (e.g., "P" for projects)

Recurrence patterns (for recurrence_rule field):
- "daily" - Every day
- "weekdays" - Monday through Friday
- "weekly:MON,WED,FRI" - Specific days of week
- "monthly:15" - Same date each month (e.g., 15th)
- "monthly:3:WED" - Nth weekday of month (e.g., 3rd Wednesday)
- "yearly:01-15" - Same date each year (MM-DD format)

For scheduling, convert relative dates like "today", "tomorrow", "next Monday" to ISO format (YYYY-MM-DD).
Today's date is: {today}

Respond with this exact JSON format:
{{
    "operation": "create" | "complete" | "delete" | "schedule" | "set_recurrence" | "remove_recurrence",
    "title": "task title here",
    "category": "T" | "D" | "M" | custom,
    "scheduled_date": "YYYY-MM-DD" or null,
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
def get_tasks() -> list[dict]:
    return get_all_tasks()


@app.post("/tasks")
def create_task(task_data: TaskCreate) -> dict:
    task_id = str(uuid.uuid4())
    return create_task_db(
        task_id,
        task_data.title,
        task_data.category,
        task_data.scheduled_date,
        task_data.recurrence_rule
    )


@app.patch("/tasks/{task_id}")
def update_task(task_id: str, task_data: TaskUpdate) -> dict:
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

    # Strip markdown code block if present
    ai_text = ai_text.strip()
    if ai_text.startswith("```"):
        lines = ai_text.split("\n")
        lines = lines[1:]  # Remove first line (```json)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # Remove last line (```)
        ai_text = "\n".join(lines)

    # Parse JSON response from Claude
    try:
        parsed = json.loads(ai_text)
    except json.JSONDecodeError:
        return {"response": "Failed to parse AI response", "tasks": get_all_tasks()}

    operation = parsed.get("operation", "none")
    title = parsed.get("title", "")
    task_key = parsed.get("task_key", "")
    category = parsed.get("category", "T").upper()
    scheduled_date = parsed.get("scheduled_date")
    recurrence_rule = parsed.get("recurrence_rule")
    message = parsed.get("message", "Done")

    # Execute operation
    if operation == "create" and title:
        create_task(TaskCreate(
            title=title,
            category=category,
            scheduled_date=scheduled_date,
            recurrence_rule=recurrence_rule
        ))
    elif operation == "complete":
        task = find_task(title, task_key)
        if task:
            update_task_db(task["id"], completed=True)
        else:
            message = f"Could not find task matching '{task_key or title}'"
    elif operation == "delete":
        task = find_task(title, task_key)
        if task:
            delete_task_db(task["id"])
        else:
            message = f"Could not find task matching '{task_key or title}'"
    elif operation == "schedule":
        task = find_task(title, task_key)
        if task and scheduled_date:
            update_task_db(task["id"], scheduled_date=scheduled_date)
        elif not task:
            message = f"Could not find task matching '{task_key or title}'"
        else:
            message = "No date provided for scheduling"
    elif operation == "set_recurrence":
        task = find_task(title, task_key)
        if task and recurrence_rule:
            # If no scheduled_date, set it to today
            new_scheduled = scheduled_date or task.get("scheduled_date") or today
            update_task_db(task["id"], scheduled_date=new_scheduled, recurrence_rule=recurrence_rule)
        elif not task:
            message = f"Could not find task matching '{task_key or title}'"
        else:
            message = "No recurrence pattern provided"
    elif operation == "remove_recurrence":
        task = find_task(title, task_key)
        if task:
            # Set recurrence_rule to empty string to remove it
            update_task_db(task["id"], recurrence_rule="")
        else:
            message = f"Could not find task matching '{task_key or title}'"

    # Save conversation with assistant response
    conversation = [{"role": m.role, "content": m.content} for m in chat_request.messages]
    conversation.append({"role": "assistant", "content": message})
    save_conversation(conversation)

    return {"response": message, "tasks": get_all_tasks()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
