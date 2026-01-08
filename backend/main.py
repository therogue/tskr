from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Dict
import uuid
import os
import anthropic
from dotenv import load_dotenv

from models import Task, TaskCreate, TaskUpdate, ChatRequest

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory task storage
tasks: Dict[str, Task] = {}

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# System prompt for task decomposition
# Assumption: User requests will be simple task operations (create, complete, delete)
SYSTEM_PROMPT = """You are a task management assistant. Parse the user's request and respond with JSON only.

Supported operations:
- create: Create a new task
- complete: Mark a task as completed (requires task title or id to identify)
- delete: Delete a task (requires task title or id to identify)

Respond with this exact JSON format:
{
    "operation": "create" | "complete" | "delete",
    "title": "task title here",
    "message": "friendly response to user"
}

If the request is unclear or not a task operation, respond with:
{
    "operation": "none",
    "message": "your clarifying question or response"
}

Only respond with valid JSON, no other text."""


@app.get("/tasks")
def get_tasks() -> list[Task]:
    return list(tasks.values())


@app.post("/tasks")
def create_task(task_data: TaskCreate) -> Task:
    task_id = str(uuid.uuid4())
    task = Task(
        id=task_id,
        title=task_data.title,
        completed=False,
        created_at=datetime.now()
    )
    tasks[task_id] = task
    return task


@app.patch("/tasks/{task_id}")
def update_task(task_id: str, task_data: TaskUpdate) -> Task:
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    if task_data.title is not None:
        task.title = task_data.title
    if task_data.completed is not None:
        task.completed = task_data.completed
    tasks[task_id] = task
    return task


@app.delete("/tasks/{task_id}")
def delete_task(task_id: str) -> dict:
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    del tasks[task_id]
    return {"status": "deleted"}


def find_task_by_title(title: str) -> Task | None:
    """Find a task by partial title match (case-insensitive)."""
    title_lower = title.lower()
    for task in tasks.values():
        if title_lower in task.title.lower():
            return task
    return None


@app.post("/chat")
async def chat(chat_request: ChatRequest) -> dict:
    """Process user message through Claude and execute task operations."""

    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-api-key-here":
        return {"response": "API key not configured", "tasks": list(tasks.values())}

    # Convert messages to Claude API format
    api_messages = [{"role": m.role, "content": m.content} for m in chat_request.messages]

    # Call Claude API
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=api_messages
        )
    except anthropic.APIError as e:
        return {"response": f"API error: {e}", "tasks": list(tasks.values())}

    ai_text = response.content[0].text
    print(f"Claude response: {ai_text}")

    # Strip markdown code block if present
    ai_text = ai_text.strip()
    if ai_text.startswith("```"):
        # Remove opening ```json or ``` and closing ```
        lines = ai_text.split("\n")
        lines = lines[1:]  # Remove first line (```json)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # Remove last line (```)
        ai_text = "\n".join(lines)

    # Parse JSON response from Claude
    try:
        import json
        parsed = json.loads(ai_text)
    except json.JSONDecodeError:
        return {"response": "Failed to parse AI response", "tasks": list(tasks.values())}

    operation = parsed.get("operation", "none")
    title = parsed.get("title", "")
    message = parsed.get("message", "Done")

    # Execute operation
    if operation == "create" and title:
        create_task(TaskCreate(title=title))
    elif operation == "complete" and title:
        task = find_task_by_title(title)
        if task:
            update_task(task.id, TaskUpdate(completed=True))
        else:
            message = f"Could not find task matching '{title}'"
    elif operation == "delete" and title:
        task = find_task_by_title(title)
        if task:
            delete_task(task.id)
        else:
            message = f"Could not find task matching '{title}'"

    return {"response": message, "tasks": list(tasks.values())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
