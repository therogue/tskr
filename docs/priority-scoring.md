# Priority Scoring Feature Plan

## Overview
Add AI-powered priority scoring to tasks. Claude assigns priority (5 levels) when creating tasks.

## Priority Levels
- **4 = Critical** - Urgent and important
- **3 = High** - Important, should do soon
- **2 = Medium** - Normal priority (default)
- **1 = Low** - Can wait
- **0 = None** - No priority / backlog

## Files to Modify

### Backend

**1. `backend/models.py`**
- Add `priority: Optional[int] = None` field to `Task` model (0-4 scale)
- Add `priority` to `TaskCreate` and `TaskUpdate` schemas

**2. `backend/database.py`**
- Create migration `004_add_priority.py` to add `priority INTEGER` column

**3. `backend/prompts.py`**
- Add priority estimation instructions to `SYSTEM_PROMPT`
- Include priority field in example JSON response format

### Frontend

**4. `frontend/src/App.tsx`**
- Add `priority: number | null` to Task interface

**5. `frontend/src/App.css`**
- Add priority badge styles with distinct colors:
  - Critical: red (#e74c3c)
  - High: orange (#e67e22)
  - Medium: yellow (#f1c40f)
  - Low: green (#27ae60)
  - None: gray (#7f8c8d)

**6. `frontend/src/components/TaskList.tsx`**
- Add priority badge next to task title
- Badge shows abbreviated label (C/H/M/L/-)

## Implementation Order
1. Backend: models.py (add field)
2. Backend: database migration
3. Backend: prompts.py (update system prompt)
4. Frontend: App.tsx (update interface)
5. Frontend: App.css (badge styles)
6. Frontend: TaskList.tsx (render badge)

## Demo Flow
1. Show existing tasks (no priority)
2. Create new task via chat: "Add a task to prepare presentation slides"
3. Claude creates task with estimated priority
4. Priority badge appears in task list
