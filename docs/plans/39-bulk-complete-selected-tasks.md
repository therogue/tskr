# Bulk-complete selected tasks via multi-select

## Problem
Users can multi-select tasks but toggling a checkbox only affects that single task. Completing/uncompleting a batch requires clicking each checkbox individually.

## Solution
When a user toggles the checkbox of a task that belongs to the current selection, apply that same completed state to all selected tasks. No new UI elements needed.

## Scope
Frontend only — `frontend/src/components/TaskList.tsx`. No backend changes (existing `PATCH /tasks/{id}` already supports `{ completed: true/false }`).

## Changes

### `TaskList.tsx`

Modify `handleToggle(task)` (line ~122):
- If `selectedIds` contains `task.id` and `selectedIds.size > 1`: PATCH all selected task ids with `{ completed: !task.completed }`
- Otherwise: existing single-task behavior (PATCH just that one task)
- Call `onTasksUpdate()` after all PATCHes complete

```ts
async function handleToggle(task: Task) {
  const newCompleted = !task.completed
  try {
    // If task is part of a multi-selection, apply to all selected
    const ids = selectedIds.has(task.id) && selectedIds.size > 1
      ? Array.from(selectedIds)
      : [task.id]
    await Promise.all(ids.map(id =>
      fetch(`${API_URL}/tasks/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed: newCompleted }),
      })
    ))
    onTasksUpdate()
  } catch (err) {
    // Ignore errors
  }
}
```

## Verification
1. Select 3 incomplete tasks via Ctrl+click
2. Check the checkbox of any one of them — all 3 become completed
3. With all 3 still selected, uncheck one — all 3 become uncompleted
4. Click a checkbox of an unselected task — only that task toggles (existing behavior)
