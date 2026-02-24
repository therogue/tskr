# SQLAlchemy ORM Migration — Task Model + Core CRUD

## Context
The backend uses raw SQL via `sqlite3` for all database operations. This makes schema changes error-prone (test fixtures fall out of sync, manual CREATE TABLE duplication). Converting to SQLModel (SQLAlchemy + Pydantic unified) gives us a single source of truth for schema, automatic test table creation, `alembic --autogenerate` support, and no separate ORM-to-Pydantic conversion layer.

Scope: **Task model and core CRUD only**. Conversations stay as raw SQL (via `session.execute(text(...))`) through the same SQLAlchemy engine.

New dependency: `pip install sqlmodel`

## Files to modify

| File | Change |
|------|--------|
| `backend/models.py` | Replace Pydantic models with SQLModel classes. `Task` becomes both ORM table and Pydantic schema. Add `CategorySequence` table model. Drop `TaskCreate` (dead code). Keep non-table Pydantic models (`TaskUpdate`, `Message`, `ChatRequest`) as plain SQLModel classes (no `table=True`). |
| `backend/database.py` | Replace `sqlite3` with SQLAlchemy `engine`/`Session`. Convert Task CRUD to ORM queries. Drop `_row_to_task()` (no conversion needed — Task IS the ORM model). Conversation functions use `session.execute(text(...))`. |
| `backend/alembic/env.py` | Set `target_metadata = SQLModel.metadata` for autogenerate. Add `include_object` filter to exclude conversations table. |
| `backend/alembic.ini` | Add timestamp `file_template` |
| `backend/alembic/script.py.mako` | Replace `import sqlite3` with `import sqlalchemy as sa` |
| `backend/tests/conftest.py` | Replace hardcoded `CREATE TABLE` with `SQLModel.metadata.create_all()` + raw SQL for conversations table only |
| `backend/tests/test_database.py` | Update `TestTemplateStartDate` raw SQL inserts to use ORM |
| `backend/tests/test_api.py` | Update raw SQL insert in `test_get_tasks_for_date_creates_instance` to use ORM |
| `backend/main.py` | No changes needed — same function signatures, same return types |
| `frontend/src/components/TaskList.tsx` | Replace `projected` with `is_template` for CSS class and React keys |
| `frontend/src/App.css` | Rename `.projected` CSS rules to `.is-template` (or keep `.projected` and just change the JS condition) |

## Step 1: Rewrite `models.py` with SQLModel

```python
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

# --- Non-table schemas (API request/response only) ---
# TaskCreate removed — dead code, never imported anywhere

class TaskUpdate(SQLModel):
    title: Optional[str] = None
    completed: Optional[bool] = None
    scheduled_date: Optional[str] = None
    recurrence_rule: Optional[str] = None
    duration_minutes: Optional[int] = None
    priority: Optional[int] = None

class Message(SQLModel):
    role: str
    content: str

class ChatRequest(SQLModel):
    messages: list[Message]
    conversation_id: int | None = None
```

Notes:
- `Task` with `table=True` is both ORM model and Pydantic schema — no `_row_to_task()` conversion needed
- `projected` field is **dropped entirely**. The frontend uses `is_template` instead (any template in a day view result is a projection). See Step 6 below.
- String dates preserved (not `Date` type) to avoid format migration
- No `ForeignKey` on `parent_task_id` (matches existing schema)

## Step 2: Rewrite `database.py`

### Connection management
```python
from sqlalchemy import create_engine, text, case, func
from sqlmodel import Session, select
from models import Task, CategorySequence

DATABASE_URL = "sqlite:///tskr.db"
engine = create_engine(DATABASE_URL)
```

Each function opens its own `Session(engine)` (matches current pattern of per-function connections).

### Key simplification
No `_row_to_task()` conversion needed. ORM queries return `Task` objects directly.

### Functions to convert to ORM queries
- `create_task_db()` — `session.add(Task(...))`, commit, refresh, return task
- `update_task_db()` — `session.get(Task, task_id)`, `setattr()` per changed field, commit+refresh
- `delete_task_db()` — `session.get(Task, task_id)`, `session.delete()`, commit
- `get_all_tasks()` — `session.exec(select(Task).order_by(case(...)))` for M→1, D→2, else→3
- `get_next_task_number()` — ORM queries on `CategorySequence` and `Task`
- `find_task_by_title_db()` — `select(Task).where(func.lower(Task.title).contains(...))`
- `find_task_by_key_db()` — `select(Task).where(func.upper(Task.task_key) == ...)`
- `_instance_exists_for_date()` — `select(Task.id).where(...)`
- `get_tasks_for_date()` — returns `list[Task]`. No more `projected` field — templates in the result are projections by definition

### Functions unchanged (pure Python, no DB)
- `calculate_next_occurrence()`, `does_pattern_match_date()`, `_find_nth_weekday()`

### Conversation functions — raw SQL via SQLAlchemy engine
Switch from `sqlite3.connect()` + `?` placeholders to `session.execute(text(...))` + `:name` placeholders.

## Step 3: Alembic config

### `alembic.ini` — add timestamp file_template after `script_location`
```
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d%%(second).2d_%%(rev)s_%%(slug)s
```

### `alembic/env.py` — wire `target_metadata`
```python
from sqlmodel import SQLModel
from models import Task, CategorySequence  # ensure models are imported so metadata is populated
target_metadata = SQLModel.metadata
```

Add `include_object` filter to exclude conversations table (no ORM model yet):
```python
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name == "conversations":
        return False
    return True
```

### `alembic/script.py.mako` — replace `import sqlite3` with `import sqlalchemy as sa`

## Step 4: Update tests

### `conftest.py`
- Monkeypatch `database.engine` with a test engine pointing to tmp_path
- Use `SQLModel.metadata.create_all(test_engine)` for tasks + category_sequences
- Create conversations table via raw SQL `text("CREATE TABLE IF NOT EXISTS conversations ...")`

### `test_database.py`
- `TestTemplateStartDate` — replace `sqlite3.connect()` inserts with `session.add(Task(...))`

### `test_api.py`
- `test_get_tasks_for_date_creates_instance` — replace `sqlite3.connect()` insert with ORM

## Step 5: Generate baseline migration

After implementation, user runs:
```bash
cd backend
pip install sqlmodel
alembic revision --autogenerate -m "baseline orm models"
```
Inspect the generated file — should be mostly empty if model matches existing schema.

## Step 6: Drop `projected` from frontend

### `TaskList.tsx`
- Remove `projected?: boolean` from Task interface
- Replace `task.projected ? 'projected' : ''` with `task.is_template ? 'projected' : ''` (4 occurrences)
- Replace `task.projected ? '-projected' : ''` with `task.is_template ? '-template' : ''` in React keys (2 occurrences)

### `App.css`
- No changes needed — `.projected` CSS class name stays, just driven by `is_template` now

### `database.py`
- Remove `"projected": True` dict merging in `get_tasks_for_date()` — templates are returned directly

## Verification
1. Run `pytest tests/` — all existing tests pass
2. Run `alembic revision --autogenerate -m "test"` — confirm no unexpected diffs
3. Start the app, create/update/delete tasks via the chat UI — confirm behavior unchanged
