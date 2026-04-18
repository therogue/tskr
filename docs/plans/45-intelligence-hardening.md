# Issue #45 — Intelligence Hardening

## Problem
The LLM may create duplicate tasks, return incomplete task data (missing duration/priority), and operates without full awareness of the user's task state.

## 1. Prevent duplicate task creation (prompt-based)

Enrich the task list in the system prompt so the LLM can detect similarity and warn the user before creating a duplicate.

### Changes

**`backend/graph.py` — `_fetch_tasks_for_state`**
- Include `duration_minutes`, `priority`, `recurrence_rule` in the task dict (currently only `task_key`, `title`, `scheduled_date`, `category`, `completed`, `id`)

**`backend/graph.py` — `execute_operation`**
- Enrich the task list format sent to the LLM to include more fields:
  ```
  - T-05: Play marbles (scheduled: 2026-02-22T19:00, 30m, priority: 1, recurring: null)
  ```

**`backend/prompts.py` — `SYSTEM_PROMPT`**
- Add duplicate detection instructions:
  - Before creating a task, check the existing task list for tasks with similar titles or overlapping time slots
  - If a potential duplicate is found, respond with `"operation": "none"` and ask the user if they want to create it anyway
  - Consider semantic similarity (e.g., "Shoot hoops" vs. "Play basketball at 3 PM")

## 2. Ensure all tasks have duration and priority

### Changes

**`backend/graph.py` — `_apply_operation`**
- After parsing the LLM response for a "create" operation, enforce defaults:
  - If `duration_minutes` is null → set to 15
  - If `priority` is null → set to 2 (Medium)
- This is a safety net — the prompt already instructs the LLM to populate these fields

**`backend/prompts.py` — `SYSTEM_PROMPT`**
- Strengthen language: "You MUST always include `duration_minutes` and `priority` in create operations. Never leave them null."

## 3. Enrich LLM context with task metadata

### Changes

**`backend/graph.py` — `_fetch_tasks_for_state`**
- Already addressed in item 1 — the enriched task dict includes duration, priority, recurrence

**`backend/graph.py` — `execute_operation`**
- Include backlog tasks (tasks with no `scheduled_date`) in the task list, labeled as "(backlog)"
- Currently only incomplete tasks are fetched; this is already correct since backlog tasks are incomplete and unscheduled

**`backend/graph.py` — task list format**
- Update the format string to include all fields:
  ```
  - T-05: Play marbles (scheduled: 2026-02-22T19:00, 30m, priority: 1)
  - T-08: Research ORM libraries (backlog, 60m, priority: 2)
  ```

## Implementation Order
1. Enrich `_fetch_tasks_for_state` with additional fields
2. Update task list format string in `execute_operation` and `execute_reschedule`
3. Add duplicate detection instructions to `SYSTEM_PROMPT`
4. Add post-parse defaults enforcement in `_apply_operation`
5. Strengthen prompt language for required fields

## Testing
- LLM integration test: create a task, then ask to create a similar one — expect a clarification response
- Unit test: verify `_apply_operation` fills in null duration/priority with defaults
- Verify enriched task list format in system prompt
