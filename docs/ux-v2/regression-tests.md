# Regression Tests — UX v2 Baseline

## Stack

- **Unit / component**: Vitest + jsdom + `@testing-library/react` + `@testing-library/jest-dom` + `@testing-library/user-event`
- **E2E smoke**: `@playwright/test` with the dev server (mocked backend via network routes)

## Running tests

```bash
cd frontend

# Unit + component (fast, no browser)
pnpm test:unit

# E2E (requires backend stub, launches Chromium)
pnpm test:e2e

# Both
pnpm test
```

## Test locations

| Kind | Location |
|------|----------|
| Component tests | `frontend/src/__tests__/` |
| E2E specs | `frontend/e2e/` |
| Test setup | `frontend/src/test/setup.ts` |
| Fetch mocks | `frontend/src/test/mocks/server.ts` |
| Fixtures | `frontend/src/test/fixtures/tasks.ts` |
| Playwright config | `frontend/playwright.config.ts` |

## Baseline test inventory (flag OFF — must always pass)

### App shell
- Renders header with logo + settings button
- `Ctrl+.` opens QuickEntry; Esc closes

### TaskList — tabs
- All four tabs render and are clickable
- Switching tabs clears selection

### TaskList — Day list
- Section headers rendered for non-empty sections (Overdue, Meetings, Daily, Tasks)
- Checkbox toggles complete (PATCH)
- Row click selects; Ctrl+click toggles; Shift+click range
- ≥1 selected → Reschedule button; ≥2 → Delete button
- Per-row trash opens confirm-popup; confirm calls DELETE
- Hover shows creation-date tooltip

### TaskList — Day calendar
- Switching to Calendar renders the grid
- Timed task block at expected top/height position
- Drag-resize emits PATCH with updated `duration_minutes`

### TaskList — All / Completed / Backlog
- Each fetches the correct URL
- Backlog excludes scheduled tasks; Completed shows only done tasks

### ChatInterface
- Mount fires POST /conversation/new
- Send fires POST /chat, renders response, calls onTasksUpdate
- Typing indicator visible while loading
- History button fires GET /conversations?limit=3
- All Chats overlay fires GET /conversations; clicking chat fires GET /conversations/:id
- New Chat fires POST /conversation/new, clears messages
- Collapse/expand toggle changes panel class
- Enter sends; Shift+Enter inserts newline; send button disabled when empty

### QuickEntry
- Ctrl+. focuses textarea
- Submit fires POST /conversation/new then POST /chat, closes, refreshes tasks

### SettingsModal
- Opens from gear button
- Renders conflict-resolution radio set
- Save fires PATCH /settings and closes

### E2E smoke (Playwright, one spec)
1. Load app → Day view with seeded tasks visible
2. Tab to Backlog → Completed → back to Day
3. Ctrl+click two tasks → Reschedule → pick tomorrow → both updated
4. Click trash on one task → confirm → task removed
5. Open chat → send "hi" → response bubble appears
6. Open Settings → change value → save → reopen → value persisted
7. Ctrl+. → QuickEntry opens → Esc closes

## Per-PR additions (flag ON)

Each sub-issue PR adds tests for its flag-ON path. See the per-PR additions in the main plan.

## Per-PR rule

Every PR to `feat/86-ux-revamp` must:
1. Pass the full baseline suite with `ux_v2 = false` (default)
2. Add new tests for the changed component with `ux_v2 = true` in `beforeEach`
3. The baseline suite is never deleted
