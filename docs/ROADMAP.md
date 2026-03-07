## 0.1

- Use SQLAlchemy ORM instead of raw SQL for database modeling
- Auto-schedule unscheduled tasks based on priority, duration, and availability
- Backlog tab for parking unscheduled tasks separately from the day view
- LLM-assigned priority scoring (0-4) for new tasks
- Multiple chat threads with separate conversation histories
- Bulk-complete selected tasks via multi-select
- Add Tskr logo

## 0.2
- Add CONTRIBUTIONS.md file including details about e.g. alembic autogenerate migrations, etc.
- User-configurable defaults / settings: default category, priority, and conflict resolution behavior (e.g. move conflicting tasks to unscheduled or backlog)
- User intent prompt: detect whether the user wants a task operation, is answering an LLM clarification, or is requesting an automatic reschedule (introduce LangGraph?)
- Create title for chats based on conversation content
- Design overhaul:
  - Collapsible/minimizable conversation panel
  - Spotlight-style quick-entry popup for task creation that appears when user clicks New Task or with a hotkey 
  - Bulk and drag-and-drop rescheduling for tasks
  - Themes: Light/Dark or system
- Intelligence hardening:
  - Prevent duplicate task creation
  - Ensure all tasks have estimated duration and priority
  - Enrich LLM context window with task metadata relevant to the current view
- Add stats re tasks per week, total tasks etc the top middle area to the right of the logo

## 0.3
- Export all tasks to an ICS calendar file
- Ensure links in task description are displayed as clickable
- Add location field
- Prompt injection prevention
- Add expandable Task details on hover over the item, small fade-in component to show verbose task details.
- Estimate if there are pre-requisites for a task (e.g. prep for a meeting) and ask the user for clarification

## 0.4
- Add integration with some external tools e.g. Google Calendar  

## 0.6
- Include external widgets, e.g. weather