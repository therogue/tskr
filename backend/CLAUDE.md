# Backend (FastAPI + SQLModel + SQLite)

## What's here

- `main.py` — FastAPI app, all HTTP routes (one file, no routers/blueprints), startup runs Alembic via `init_db()`.
- `database.py` — SQLModel data layer: task CRUD, task numbering, recurrence calculation, `get_tasks_for_date()`, `get_overdue_tasks()`, settings, conversations.
- `models.py` — SQLModel table classes (`Task`, `CategorySequence`, `Conversation`, `UserSettings`) and non-table API schemas (`TaskUpdate`, `UserSettingsRead`, `UserSettingsUpdate`, `ChatRequest`, `Message`).
- `graph.py` — LangGraph pipeline for the `/chat` endpoint (intent classification → operation execution).
- `prompts.py` — System prompts.
- `scheduling.py` — Schedule context builder for prompts.
- `alembic/` — Migrations.

## Design notes

- **Sync-first.** All routes are sync `def` except `/chat` and the title-generation helper, which are `async` only because they await Anthropic SDK calls.
- **No background-task infrastructure.** No `BackgroundTasks`, threading, scheduler, or queue. Add one only if a task genuinely cannot run within the request lifecycle.
- **Per-operation sessions.** Every DB op opens its own `Session(engine)` block and commits before returning. Returned ORM objects are detached via `.model_copy()` so callers can use them after the session closes.
- **`get_all_tasks()` then filter in Python** is the prevailing pattern for query-shaped functions (`get_tasks_for_date`, `get_overdue_tasks`). Volumes are small; SQL-side filtering isn't worth the complexity yet.
- **Today is server-local.** `datetime.now().strftime("%Y-%m-%d")` — no client TZ, no UTC.
- **Templates vs instances.** Recurring tasks are stored as templates (`is_template=True`, key prefix `R-`). Instances are materialized on demand by `get_tasks_for_date()` for today, or rendered as projections (template returned with overridden `scheduled_date`) for past/future dates.
- **`scheduled_date` format.** `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM`. Lexicographic comparison works for date-prefix ordering. Use `scheduled_date[:10]` to extract the date portion.
- **Categories.** `M` = meeting (time-bound, never carried/overdue), `D` = daily, `T` = generic task, others = projects.

## Guidelines for changes

- Add new endpoints in `main.py` next to related existing ones; don't introduce routers unless the file becomes unmanageable.
- New DB ops go in `database.py`. Match the existing style: open a `Session`, do work, commit, return detached copies.
- Schema changes need an Alembic migration. Never drop columns without a migration.
- Don't add blocking I/O to a sync route; if you need to, switch the route to `async def` and use the async client (`anthropic.AsyncAnthropic` is already wired up).
- Lexicographic date math is fine for the current `scheduled_date` format. Don't add `dateutil` for trivial cases.
- When filtering tasks, remember to handle: templates (`is_template`), recurrent instances (`parent_task_id` set), meetings (`category == "M"`), and completed (`completed`) — most filters need at least three of these.
