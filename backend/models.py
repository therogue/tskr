from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Task(BaseModel):
    id: str
    title: str
    completed: bool = False
    created_at: datetime

class TaskCreate(BaseModel):
    title: str

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
