from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os
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
def get_tasks() -> list[dict]:
    return get_all_tasks()


@app.post("/tasks")
def create_task(task_data: TaskCreate) -> dict:
    task_id = str(uuid.uuid4())
    return create_task_db(task_id, task_data.title)


@app.patch("/tasks/{task_id}")
def update_task(task_id: str, task_data: TaskUpdate) -> dict:
    result = update_task_db(task_id, task_data.title, task_data.completed)
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


@app.post("/chat")
async def chat(chat_request: ChatRequest) -> dict:
    """Process user message through Claude and execute task operations."""

    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-api-key-here":
        return {"response": "API key not configured", "tasks": get_all_tasks()}

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
        import json
        parsed = json.loads(ai_text)
    except json.JSONDecodeError:
        return {"response": "Failed to parse AI response", "tasks": get_all_tasks()}

    operation = parsed.get("operation", "none")
    title = parsed.get("title", "")
    message = parsed.get("message", "Done")

    # Execute operation
    if operation == "create" and title:
        create_task(TaskCreate(title=title))
    elif operation == "complete" and title:
        task = find_task_by_title_db(title)
        if task:
            update_task_db(task["id"], completed=True)
        else:
            message = f"Could not find task matching '{title}'"
    elif operation == "delete" and title:
        task = find_task_by_title_db(title)
        if task:
            delete_task_db(task["id"])
        else:
            message = f"Could not find task matching '{title}'"

    # Save conversation with assistant response
    conversation = [{"role": m.role, "content": m.content} for m in chat_request.messages]
    conversation.append({"role": "assistant", "content": message})
    save_conversation(conversation)

    return {"response": message, "tasks": get_all_tasks()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
