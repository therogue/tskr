"""
Scheduling utilities for auto-assigning time slots.
Builds schedule context for the system prompt.
"""
from models import Task


def build_schedule_context(tasks: list[Task]) -> str:
    """
    Build today's schedule context string for the system prompt.

    tasks: today's tasks (as returned by get_tasks_for_date)

    Returns a formatted string with scheduled tasks and available business-hours
    gaps (09:00-17:00), or empty string if no tasks have a specific time.
    Assumes: scheduled_date is YYYY-MM-DDTHH:MM when a time is present.
    """
    # Only include incomplete tasks that have a specific time
    timed = [
        t for t in tasks
        if t.scheduled_date and "T" in t.scheduled_date and not t.completed
    ]
    if not timed:
        return ""

    timed.sort(key=lambda t: t.scheduled_date)

    BIZ_START = 9 * 60   # 09:00 in minutes
    BIZ_END = 17 * 60    # 17:00 in minutes

    booked = []
    lines = []
    for task in timed:
        time_str = task.scheduled_date.split("T")[1]  # HH:MM
        h, m = map(int, time_str.split(":"))
        start_min = h * 60 + m
        duration = task.duration_minutes or 15  # consistent with create_task_db default
        end_min = start_min + duration
        end_h, end_m = divmod(end_min, 60)
        lines.append(
            f"  {task.task_key}: {task.title} ({time_str}-{end_h:02d}:{end_m:02d}, {duration}min)"
        )
        booked.append((start_min, end_min))

    # Clip booked intervals to business hours and compute gaps
    clipped = []
    for start, end in booked:
        s = max(start, BIZ_START)
        e = min(end, BIZ_END)
        if s < e:
            clipped.append((s, e))
    clipped.sort()

    gaps = []
    prev_end = BIZ_START
    for start, end in clipped:
        if start > prev_end:
            g_sh, g_sm = divmod(prev_end, 60)
            g_eh, g_em = divmod(start, 60)
            gaps.append(f"{g_sh:02d}:{g_sm:02d}-{g_eh:02d}:{g_em:02d}")
        prev_end = max(prev_end, end)
    if prev_end < BIZ_END:
        g_sh, g_sm = divmod(prev_end, 60)
        gaps.append(f"{g_sh:02d}:{g_sm:02d}-17:00")

    schedule_str = "\n".join(lines)
    gaps_str = ", ".join(gaps) if gaps else "none"
    return f"\nToday's schedule:\n{schedule_str}\nAvailable business-hours gaps: {gaps_str}"
