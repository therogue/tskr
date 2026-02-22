# Day View Implementation Plan

## Summary
Add a day view (default) that shows all tasks for a selected day, with toggle to category view.

## Requirements
1. **Day view (default)**: Shows tasks for today, sorted by category within the day
2. **Category view**: Shows all tasks grouped by category, then by date within each category
3. **Recurring task projection**: Show "planned" recurring tasks dimmed (not created in DB)
4. **Overdue recurring tasks**: Show on both their actual scheduled_date AND today if pattern matches
5. **Incomplete tasks**: Default to today unless scheduled for a future date
6. **Completed tasks**: Shown slightly grayed out

## Key Decision: Where to compute recurring task projections?

**Option A: Frontend** - Parse recurrence_rule in TypeScript
- Pros: No API changes, simpler backend
- Cons: Duplicates logic from database.py, must keep in sync

**Option B: Backend** - New endpoint `GET /tasks/for-date?date=YYYY-MM-DD`
- Pros: Single source of truth for recurrence logic, cleaner frontend
- Cons: New endpoint, slightly more complex

**Recommendation**: Option B - keeps recurrence logic in one place (backend)

## Implementation Steps

### Step 0: Copy plan to docs/
Copy this plan file to `docs/day-view-plan.md` for reference.

### Backend Changes

**1. Add `does_pattern_match_date()` function in database.py**
- Check if a recurrence pattern includes a specific date
- Reuse DAY_MAP and date parsing from existing code

**2. Add `get_tasks_for_date(date: str)` function in database.py**
Returns tasks for a specific date:
- Tasks with scheduled_date matching the date
- Incomplete tasks with no scheduled_date or past scheduled_date (default to today only)
- Recurring tasks where pattern matches the date (marked as `projected: true`)

**3. Add `GET /tasks/for-date` endpoint in main.py**
- Query param: `date` (YYYY-MM-DD format)
- Returns tasks with additional `projected` field for recurring projections

### Frontend Changes

**4. Update TaskList.tsx**
- Add `viewMode` state: 'day' | 'category'
- Add `selectedDate` state (defaults to today)
- Add toggle button in header
- Fetch from `/tasks/for-date?date=X` for day view
- Use existing `/tasks` for category view

**5. Add day view rendering**
- Group tasks by category within the day
- Show projected recurring tasks with dimmed styling
- Show completed tasks with grayed out styling

**6. Update App.css**
- Add `.task-projected` class for dimmed recurring task styling
- Add view toggle button styling

## Files to Modify
- `backend/database.py` - add `does_pattern_match_date()`, `get_tasks_for_date()`
- `backend/main.py` - add `GET /tasks/for-date` endpoint
- `frontend/src/components/TaskList.tsx` - view mode toggle, day view rendering
- `frontend/src/App.css` - styling for projected tasks, toggle button

## Verification
1. Create a recurring daily task scheduled for yesterday
2. Verify it appears on today's day view as projected (dimmed)
3. Complete it and verify date advances
4. Toggle to category view and verify all tasks visible
5. Create a task with no scheduled_date, verify it appears on today
