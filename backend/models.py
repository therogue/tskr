from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Task(BaseModel):
    id: str
    task_key: str
    category: str
    task_number: int
    title: str
    completed: bool = False
    scheduled_date: Optional[str] = None
    recurrence_rule: Optional[str] = None
    created_at: datetime

class TaskCreate(BaseModel):
    title: str
    category: str = "T"
    scheduled_date: Optional[str] = None
    recurrence_rule: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None
    scheduled_date: Optional[str] = None
    recurrence_rule: Optional[str] = None

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
