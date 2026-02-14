from pydantic import BaseModel
from typing import Optional

class Task(BaseModel):
    id: str
    task_key: str
    category: str
    task_number: int
    title: str
    completed: bool = False
    scheduled_date: Optional[str] = None  # ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM
    recurrence_rule: Optional[str] = None
    created_at: str  # ISO format datetime string
    is_template: bool = False
    parent_task_id: Optional[str] = None
    duration_minutes: Optional[int] = None  # Estimated task duration in minutes
    projected: bool = False  # True for recurring task projections in day view

class TaskCreate(BaseModel):
    title: str
    category: str = "T"
    scheduled_date: Optional[str] = None  # ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM
    recurrence_rule: Optional[str] = None
    duration_minutes: Optional[int] = None
    is_template: bool = False

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None
    scheduled_date: Optional[str] = None  # ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM
    recurrence_rule: Optional[str] = None
    duration_minutes: Optional[int] = None

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
