# UX v2 — Implementation Detail

Source of truth for visual/behavior: `G:\Coding\Git\tskr\res\UI_UX\v2\samples\Hakadorio Chat.html`

## Branch order

1. `chore/ux-v2-test-baseline` → lands on `main` first
2. `feat/86-ux-revamp` created off updated `main`; feature flag system + scaffold committed directly
3. `feat/87-fixed-width-tabs` → merges into epic
4. `feat/88-widgets-panel` and `feat/91-task-detail-modal` → parallel, both off epic after #87
5. `feat/89-chat-overlay` → off epic after #88 and #91 merge
6. `feat/90-suggestive-followups` and `feat/92-task-cards-in-chat` → parallel, off epic after #89
7. `feat/86-ux-revamp` → merges into `main`

## Scaffold (direct commit on epic, before #87)

- CSS variables (DARK/LIGHT token sets) at `:root` and `[data-theme="dark"]` in `App.css`
- Three keyframes: `fadeSlideUp`, `bounce`, `pulse-ring`
- `frontend/src/hooks/useTheme.ts` — reads/writes `localStorage.theme`, toggles `document.documentElement.dataset.theme`
- `frontend/src/components/Icon.tsx` — shared SVG icon component; replaces inline `TrashIcon` in TaskList

## #87 — Fixed-width tabbed views

**Branch**: `feat/87-fixed-width-tabs`

- `App.tsx`: new `<main>` flex row — `<TaskList flex:1>` + `<div.right-panel flex:0 0 340px>`
- `App.css`: rewrite `.main`, `.chat-panel`; add `.right-panel { position: relative; overflow: hidden; }`
- `TaskList.tsx`: restyle tab bar (13px, 2px accent underline), date strip header, List|Calendar toggle with "Double-click a task to edit" hint
- Bulk actions toolbar: restyled as accent-pill buttons on right side of toggle row; same conditions and handlers
- Drop `chatCollapsed`/`onToggleCollapse` from `App.tsx` + `ChatInterface.tsx` (replaced by `chatOpen` overlay in #89)

## #88 — Productive widgets

**Branch**: `feat/88-widgets-panel`

New files:
- `frontend/src/components/WidgetPanel.tsx` — Dashboard header + Ask AI button + three widget cards
- `frontend/src/components/ProgressRing.tsx` — SVG progress ring

Widgets (all from existing `tasks` state — no new API calls):
- **Today's Progress**: ProgressRing done/total, last completed task title
- **Next Up**: first uncompleted timed task today, with "in Xh/Xm" badge
- **This Week**: 7-bar chart using `completed && scheduled_date.slice(0,10) === day` proxy (see resolved Q4)

## #91 — Task detail modal

**Branch**: `feat/91-task-detail-modal` (parallel to #88)

New files:
- `frontend/src/components/TaskModal.tsx` — edit form (title, priority, scheduled_date, duration_minutes). Notes field omitted (column doesn't exist — see resolved Q1).

Edits:
- `TaskList.tsx`: `clickTimers` ref + `handleRowActivate` — single click = select/toggle, double click = open modal. Applied to list rows and calendar blocks.

## #89 — Chat overlay

**Branch**: `feat/89-chat-overlay` (after #88 + #91 merge)

- `ChatInterface.tsx`: accepts `visible: boolean` + `onClose: () => void`; wraps root in absolute-positioned div with `translateX` transition
- New `<HistoryDrawer />` replaces inline popover and "All Chats" overlay
- `App.tsx`: lifts `chatOpen` state; wires `WidgetPanel.onOpenChat → setChatOpen(true)`

## #90 — Suggestion chips

**Branch**: `feat/90-suggestive-followups` (after #89)

- `QUICK_PROMPTS` const + `<Chip>` component + `<EmptyState>` (shown when no messages)
- Persistent chip strip above input when `messages.length > 0 && !loading`

## #92 — Task cards in chat

**Branch**: `feat/92-task-cards-in-chat` (parallel to #90)

New files:
- `frontend/src/components/TaskCard.tsx` — confirmation card rendered in AI bubbles

Edits:
- `ChatInterface.tsx`: diff `data.tasks` (from POST /chat response) against `tasks` prop snapshot to attach affected task to assistant message (see resolved Q2)

## Resolved questions

1. **notes column**: does not exist on Task model → dropped from TaskModal
2. **POST /chat response**: returns `{ response, tasks, title }` → diff-based attach for #92
3. **Theme toggle**: `ux_v2.theme_toggle` sub-flag (default OFF)
4. **Weekly bars**: client-side proxy using `completed && scheduled_date`
5. **Move to backlog**: out of #86 scope; toolbar reserves a slot

## Existing-feature translation matrix

| Feature | Status | Notes |
|---------|--------|-------|
| Bulk actions (reschedule ≥1, delete ≥2) | Carried over | Restyled as accent pills in #87 |
| Day-view section grouping (Overdue/Meetings/Daily/Tasks) | Carried over | HTML mockup's flat list is a sample |
| Calendar drag/resize/group drag | Untouched | Logic in calendarLayout.ts |
| Hover tooltip with creation date | Carried over | On every row, all views |
| Per-row trash + confirm-popup | Carried over | TaskModal delete is an additional path |
| QuickEntry (Ctrl+.) | Carried over | Opens above chat panel |
| SettingsModal | Carried over | Gear cog in new header |
| App-load fresh chat | Carried over | POST /conversation/new on mount |
| Conversation history | Carried over | HistoryDrawer in #89 |
| Move to backlog | Deferred | Tracked as Issue 5; toolbar slot reserved |
