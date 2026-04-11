# Bugfixes v0.2

## Items

### 1. Category change should update task_key
When a task is moved to a different category (e.g., T → M), the `task_key` remains unchanged (e.g., still `T-05`). It should be reassigned a new key from the target category's sequence (e.g., `M-04`).

**Affected code:** `backend/graph.py` — `_apply_operation` update branch (~line 199)
**Fix:** When `category` changes, also generate a new `task_key` and `task_number` from the target category's sequence.

### 2. Bulk delete all tasks for today
Allow users to delete all tasks scheduled for today in one operation.

### 3. Move all tasks for today to backlog
Allow users to move all tasks scheduled for today to backlog (clear `scheduled_date`) in one operation.

### 4. Overdue tasks default to backlog instead of carry-forward
Currently, incomplete past-dated tasks are carried forward and shown on today's day view. Change the default behavior so overdue tasks are moved to the backlog (clear `scheduled_date`) instead of being carried forward.

**Affected code:** `backend/database.py` — `get_tasks_for_date()` overdue filter

### 5. Show task creation date on hover
Display the task's `created_at` date in a tooltip when hovering over the task row.

**Affected code:** `frontend/src/components/TaskList.tsx` — task row element (add `title` attribute)

### 6. Clear selection state after deleting tasks
After deleting selected tasks, `selectedIds` is not cleared, so the "delete multiple" button remains visible even though the tasks are gone.

**Fix:** Clear `selectedIds` after a successful delete operation.

### 7. "Delete multiple" button should require 2+ selected tasks
The bulk delete button currently shows when a single task is selected. It should only appear when `selectedIds.size > 1`.

**Affected code:** `frontend/src/components/TaskList.tsx` — conditional rendering of the delete button

### 8. Calendar tasks offset to the right when there's no overlap
Tasks in the calendar/day view are rendered on the right side as if they overlap with other tasks, even when they're the only task in their time slot. They should use the full width when there's no conflict.

**Affected code:** `frontend/src/components/TaskList.tsx` or calendar CSS — overlap/column layout logic

### 9. Completed tasks should remain visible in day view
Completed tasks currently disappear from the day view. They should still show up with strikethrough/grayed out styling, consistent with how they appear in the completed task list. We should have an animation indicating the transition to completed status.

### 10. Setting recurrence on an existing task doesn't generate instances
When updating a non-recurring task to add a `recurrence_rule`, the rule is stored but no recurring instances are generated for subsequent days. The projection/instance generation logic likely only runs at task creation time.

**Affected code:** `backend/database.py` — `update_task_db` and/or the recurrence projection logic

## Small Features

### 11. Group completed tasks by day in reverse chronological order
The completed tab should group tasks by the date they were completed, most recent day first.

### 12. Show backlog in a collapsed section on day view
Display a collapsible section at the bottom (or top) of the day view showing backlog tasks (no `scheduled_date`). Collapsed by default.

### 13. Show completed tasks for today in collapsed section on day view
Display a collapsible section on the day view for today's completed tasks. When a task is marked complete, it should move into this section (with the animation from #9).
