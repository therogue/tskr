# Recurring Tasks

## Overview

Tasks can have recurrence rules that cause them to repeat on a schedule. When a recurring task is completed, its scheduled date automatically advances to the next occurrence.

## Recurrence Patterns

The `recurrence_rule` field uses a simple string format:

| Pattern | Format | Example | Description |
|---------|--------|---------|-------------|
| Daily | `daily` | `daily` | Every day |
| Weekdays | `weekdays` | `weekdays` | Monday through Friday |
| Weekly on specific days | `weekly:DAY,DAY,...` | `weekly:MON,WED,FRI` | Specific days of week |
| Monthly by date | `monthly:DD` | `monthly:15` | Same date each month |
| Monthly by weekday | `monthly:N:DAY` | `monthly:3:WED` | Nth weekday of month (e.g., 3rd Wednesday) |
| Yearly | `yearly:MM-DD` | `yearly:01-15` | Same date each year |

Day abbreviations: MON, TUE, WED, THU, FRI, SAT, SUN

## Behavior

### Completion
When a recurring task is marked complete:
1. The task's `scheduled_date` advances to the next occurrence
2. The task is marked as incomplete (ready for next occurrence)
3. The completion is logged (NOT IMPLEMENTED - future feature)

### Display Rules
- **Daily tasks (category D)**: Only show tasks scheduled for today
- **Meetings (category M)**: Show all upcoming occurrences
- **Other recurring tasks**: Show all upcoming occurrences

### Non-recurring tasks
Tasks without a `recurrence_rule` behave as before - completion marks them done permanently.

## Database Schema

`tasks` table fields:
```sql
scheduled_date TEXT   -- YYYY-MM-DD or YYYY-MM-DDTHH:MM format
recurrence_rule TEXT  -- NULL for non-recurring tasks
```

The `scheduled_date` field supports both date-only and datetime formats. When a recurring task has a time component, the time is preserved when advancing to the next occurrence.

## Chat Interface

Users can create and modify recurring tasks via natural language:

**Creating:**
- "Add a daily standup meeting at 9am"
- "Create a task to review reports every Monday"
- "Add a birthday reminder for January 15th every year"

**Converting existing tasks:**
- "Make T-01 a daily task"
- "Set M-03 to repeat every weekday"

**Removing recurrence:**
- "Stop T-01 from repeating"
- "Make D-02 a one-time task"

## Implementation Notes

- Recurrence calculation happens in Python backend
- Frontend receives tasks with their current `scheduled_date`
- No separate "instances" table - simpler single-task model
- Past occurrences are not tracked (task just moves forward)
