from typing import Optional
from sqlmodel import SQLModel, Field


# --- Table models (ORM + Pydantic) ---

class Task(SQLModel, table=True):
    __tablename__ = "tasks"
    id: str = Field(primary_key=True)
    task_key: str
    category: str
    task_number: int
    title: str
    completed: bool = False
    scheduled_date: Optional[str] = None     # YYYY-MM-DD or YYYY-MM-DDTHH:MM
    recurrence_rule: Optional[str] = None
    created_at: str = ""                     # ISO datetime, set by create_task_db
    is_template: bool = False
    parent_task_id: Optional[str] = None
    duration_minutes: Optional[int] = None
    priority: Optional[int] = None           # 0=None, 1=Low, 2=Medium, 3=High, 4=Critical


class CategorySequence(SQLModel, table=True):
    __tablename__ = "category_sequences"
    category: str = Field(primary_key=True)
    next_number: int


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"
    id: Optional[int] = Field(default=None, primary_key=True)
    messages: str = "[]"                     # JSON-encoded list of message dicts
    title: str = "Untitled"
    created_at: str = ""                     # ISO datetime
    updated_at: str = ""                     # ISO datetime


# --- Non-table schemas (API request/response only) ---

class TaskUpdate(SQLModel):
    title: Optional[str] = None
    completed: Optional[bool] = None
    scheduled_date: Optional[str] = None
    recurrence_rule: Optional[str] = None
    duration_minutes: Optional[int] = None
    priority: Optional[int] = None

class UserSettings(SQLModel, table=True):
    __tablename__ = "user_settings"
    id: str = Field(default="default", primary_key=True)
    default_category: str = "T"
    default_priority: str = "medium"     # "none"|"low"|"medium"|"high"|"critical"
    conflict_resolution: str = "overlap" # "overlap"|"unschedule"|"backlog"


class UserSettingsRead(SQLModel):
    default_category: str
    default_priority: str
    conflict_resolution: str


class UserSettingsUpdate(SQLModel):
    default_category: Optional[str] = None
    default_priority: Optional[str] = None
    conflict_resolution: Optional[str] = None


class Message(SQLModel):
    role: str
    content: str

class ChatRequest(SQLModel):
    messages: list[Message]
    conversation_id: int | None = None
