# Task Identifiers

## Format

Tasks use Jira-style identifiers: `CATEGORY-##` (e.g., `M-01`, `T-15`)

## Categories

| Category | Description | Numbering |
|----------|-------------|-----------|
| T | Regular tasks | Continues indefinitely |
| D | Daily tasks | Resets per scheduled date |
| M | Meetings | Resets per scheduled date |
| (custom) | User-defined via chat | Continues indefinitely |

## Numbering Rules

- **T and custom categories**: Numbers increment globally (T-01, T-02, T-03...)
- **D and M**: Numbers reset per scheduled date. Uniqueness = number + date (M-01 on Jan 15 ≠ M-01 on Jan 16)

## Scheduling

- Tasks can be **unscheduled** (no date/time) or **scheduled** for a specific date/time
- Format: `YYYY-MM-DD` (date only) or `YYYY-MM-DDTHH:MM` (date and time)
- User schedules tasks via chat ("schedule this for tomorrow at 3pm")
- For D and M tasks, scheduling is required (they are date-bound by nature)

## Display (Phase 1 - Option A)

- Task panel shows all tasks grouped by category
- Groups: Meetings / Daily Tasks / Other Tasks
- Identifiers displayed inline (e.g., "M-01: Team standup")
- Scheduled dates shown but no date navigation yet

## Database Schema

```sql
-- Tasks table
tasks (
    id TEXT PRIMARY KEY,          -- UUID for internal use
    task_key TEXT NOT NULL,       -- Display identifier (e.g., "M-01")
    category TEXT NOT NULL,       -- T, D, M, or custom
    task_number INTEGER NOT NULL, -- The ## part
    title TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    scheduled_date TEXT,          -- YYYY-MM-DD or YYYY-MM-DDTHH:MM, nullable
    recurrence_rule TEXT,         -- Recurrence pattern (see recurring-tasks.md)
    created_at TEXT NOT NULL
)

-- Track next number per category (for indefinite categories)
category_sequences (
    category TEXT PRIMARY KEY,
    next_number INTEGER DEFAULT 1
)
```

## Future Considerations

- Date navigation (week view, day picker)
- Task completion history tracking
