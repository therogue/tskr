# Hakadorio

A personal task management app with an AI-powered chat interface for creating, scheduling, and organizing tasks. Single-user, local-first.

## Stack

- **Frontend**: React 18 + TypeScript + Vite, pnpm. Source in [frontend/src/](frontend/src/).
- **Backend**: FastAPI + SQLModel (SQLAlchemy ORM) + Alembic + SQLite. Source in [backend/](backend/).
- **LLM**: Anthropic Claude via the `anthropic` SDK, orchestrated with LangGraph.

## Architecture

```
frontend/src/        React UI: TaskList, ChatInterface, calendar/list day view
backend/main.py      FastAPI routes (/tasks, /chat, /conversations, /settings)
backend/graph.py     LangGraph chat flow: classify_intent → fetch_tasks → execute_*
backend/database.py  ORM CRUD; alembic migrations under backend/alembic/versions/
backend/models.py    SQLModel tables (Task, CategorySequence, Conversation) + API schemas
backend/prompts.py   System prompts for intent classification, operations, reschedule
backend/scheduling.py  Schedule context builder (gaps, conflicts) for auto-scheduling
```

## Data Model

- **Task** — `id`, `task_key` (e.g. `T-05`, `M-01`), `category`, `task_number`, `title`, `completed`, `scheduled_date` (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM`), `recurrence_rule`, `is_template`, `parent_task_id`, `duration_minutes`, `priority` (0–4).
- **CategorySequence** — per-category counter for `task_number`.
- **Conversation** — chat history (JSON-encoded `messages`, `title`).

Categories: `T` (regular), `D` (daily), `M` (meeting), or any user-defined custom category. Recurring tasks are stored as templates (`is_template=True`); instances are generated per date via `get_tasks_for_date()`.

## Key Workflows

**Chat → operation**: `POST /chat` → `chat_graph.ainvoke()` → `classify_intent` (task_operation | clarification_answer | reschedule) → `fetch_tasks_*` → `execute_operation` or `execute_reschedule` → returns `final_response` + updated task list.

**Auto-scheduling**: When a task is created for today without a time, `build_schedule_context()` injects today's schedule + available gaps into the LLM prompt; the LLM picks a slot.

**Conflict resolution**: User setting `conflict_resolution` controls behavior when a new task overlaps an existing one — `overlap`, `unschedule`, or `backlog`.

## Conventions

- Branches, commits, migrations, tests: see [CONTRIBUTING.md](CONTRIBUTING.md).
- Claude communication style and behavior rules: see [CLAUDE.md](CLAUDE.md).
- Tests: unit tests in [backend/tests/unit/](backend/tests/unit/), LLM integration tests in [backend/tests/llm/](backend/tests/llm/) (run with `pytest --run-llm`).
