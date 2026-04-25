# Frontend (React + Vite + TypeScript)

## Layout

- `App.tsx` — root component. Owns task fetching (`tasks`, `overdueTasks`), view mode, selected date, modal toggles. Passes data + callbacks down.
- `main.tsx` — Vite entry point.
- `components/`
  - `TaskList.tsx` — day/all/completed/backlog views, list+calendar modes, drag/drop, multi-select, bulk delete/reschedule.
  - `ChatInterface.tsx` — chat panel, conversation history.
  - `SettingsModal.tsx` — user settings form.
  - `QuickEntry.tsx` — Ctrl+. spotlight-style task creation.
- `utils/calendarLayout.ts` — column packing for overlapping calendar blocks, snap-to-minutes helpers.
- `App.css` / `index.css` — styles. Theme via CSS custom properties.

## Design notes

- **API base** is hard-coded `http://localhost:8000` in each component that needs it. There is no shared client wrapper; calls use native `fetch()`.
- **Task shape duplicated.** `App.tsx` and `TaskList.tsx` each declare their own `Task` interface. They must stay in sync with each other and with `backend/models.py`. Comment them with the `// Assumption:` prefix when adding fields.
- **Single source of truth for tasks** is `App.tsx`'s `tasks` state, refilled by `fetchTasks()`. Children call `onTasksUpdate()` after mutations to trigger a refetch.
- **Today is client-local.** `formatDateStr(new Date())` builds `YYYY-MM-DD` from local components. No timezone is sent to the backend; backend uses server-local. This works because dev is single-user on one machine.
- **Day view** uses `GET /tasks/for-date?date=...`. When the selected date equals today, App also fetches `GET /tasks/overdue` in parallel and passes the result as `overdueTasks` to TaskList. TaskList renders Overdue as the first section above Meetings/Daily/Tasks (list mode only).
- **Selection state** lives in TaskList. `orderedVisibleTasksRef` tracks the currently rendered order so shift-click range selection works across sections.
- **Drag/drop** is calendar-mode-only and timed-tasks-only. Group drag uses `selectedIds` to move other selected timed tasks by the same delta. Lookup uses `tasks.find` — overdue tasks aren't in `tasks`, so they can't be dragged (intentional; they aren't on today's calendar).

## Guidelines for changes

- Prefer co-locating a new view's data fetch in `App.tsx` and passing as a prop, over fetching inside a component. Children should be presentational where possible.
- After a write, call `onTasksUpdate()` rather than mutating local state — the refetch keeps everything consistent.
- Bulk operations on selections may include ids from sources outside `tasks` (e.g. `overdueTasks`). When looking up by id, fall back: `tasks.find(...) ?? overdueTasks.find(...)`.
- Section ordering and `orderedVisibleTasksRef` must stay aligned. When you add a section, increment a running index and pass it as `startIndex` to `renderSection`.
- Don't add a styling library or component framework — this is a deliberately small CSS-driven UI.
- Type the Task interface explicitly in any new component that holds tasks. Don't import types across components — duplicate them with the `// Assumption:` comment.
- Don't introduce a global API client unless we have a reason; the duplicated `fetch` calls are intentional for now.
