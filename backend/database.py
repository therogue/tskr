import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager

from models import Task

DATABASE_PATH = "tskr.db"

@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize database by running Alembic migrations."""
    import subprocess
    import os

    # Run alembic upgrade from the backend directory
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=backend_dir,
        check=True
    )

def get_next_task_number(category: str, scheduled_date: Optional[str] = None, is_template: bool = False) -> int:
    """
    Get next task number for a category.
    For D and M instance categories, number is per-date.
    For templates and other categories, number continues indefinitely via category_sequences.
    Templates use "R-{category}" as the sequence key.
    """
    with get_db() as conn:
        # Templates always use category_sequences with R- prefix
        if is_template:
            seq_key = f"R-{category}"
            row = conn.execute(
                "SELECT next_number FROM category_sequences WHERE category = ?",
                (seq_key,)
            ).fetchone()
            if row:
                next_num = row["next_number"]
                conn.execute(
                    "UPDATE category_sequences SET next_number = ? WHERE category = ?",
                    (next_num + 1, seq_key)
                )
            else:
                next_num = 1
                conn.execute(
                    "INSERT INTO category_sequences (category, next_number) VALUES (?, 2)",
                    (seq_key,)
                )
            conn.commit()
            return next_num

        # Instance tasks: D and M use per-date numbering
        if category in ("D", "M"):
            # Count existing non-template tasks for this category on this date
            # Use substr to match date portion only (scheduled_date may include time)
            if scheduled_date:
                count = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE category = ? AND substr(scheduled_date, 1, 10) = ? AND (is_template = 0 OR is_template IS NULL)",
                    (category, scheduled_date[:10])
                ).fetchone()[0]
                return count + 1
            else:
                # D/M without date - use 1 (edge case)
                return 1
        else:
            # Other categories use category_sequences
            row = conn.execute(
                "SELECT next_number FROM category_sequences WHERE category = ?",
                (category,)
            ).fetchone()
            if row:
                next_num = row["next_number"]
                conn.execute(
                    "UPDATE category_sequences SET next_number = ? WHERE category = ?",
                    (next_num + 1, category)
                )
            else:
                next_num = 1
                conn.execute(
                    "INSERT INTO category_sequences (category, next_number) VALUES (?, 2)",
                    (category,)
                )
            conn.commit()
            return next_num

def _row_to_task(row) -> Task:
    """Convert a database row to a Task model."""
    keys = row.keys()
    # Treat empty string as None for recurrence_rule
    recurrence = row["recurrence_rule"] if "recurrence_rule" in keys else None
    if recurrence == "":
        recurrence = None
    return Task(
        id=row["id"],
        task_key=row["task_key"],
        category=row["category"],
        task_number=row["task_number"],
        title=row["title"],
        completed=bool(row["completed"]),
        scheduled_date=row["scheduled_date"],
        recurrence_rule=recurrence,
        created_at=row["created_at"],
        is_template=bool(row["is_template"]) if "is_template" in keys else False,
        parent_task_id=row["parent_task_id"] if "parent_task_id" in keys else None,
        duration_minutes=row["duration_minutes"] if "duration_minutes" in keys else None,
    )


# Recurrence calculation functions
DAY_MAP = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}


def calculate_next_occurrence(rule: str, current_date: str) -> Optional[str]:
    """
    Calculate the next occurrence date based on recurrence rule.
    current_date is in YYYY-MM-DD format.
    Returns next date in YYYY-MM-DD format, or None if rule is invalid.
    """
    if not rule or not current_date:
        return None

    try:
        year, month, day = map(int, current_date.split("-"))
        current = datetime(year, month, day)
    except (ValueError, AttributeError):
        return None

    rule = rule.lower().strip()

    if rule == "daily":
        next_date = current + timedelta(days=1)
        return next_date.strftime("%Y-%m-%d")

    if rule == "weekdays":
        next_date = current + timedelta(days=1)
        # Skip to Monday if landing on weekend
        while next_date.weekday() >= 5:  # 5=Sat, 6=Sun
            next_date += timedelta(days=1)
        return next_date.strftime("%Y-%m-%d")

    if rule.startswith("weekly:"):
        # Format: weekly:MON,WED,FRI
        days_str = rule[7:].upper()
        target_days = [DAY_MAP[d.strip()] for d in days_str.split(",") if d.strip() in DAY_MAP]
        if not target_days:
            return None
        target_days.sort()

        next_date = current + timedelta(days=1)
        for _ in range(7):
            if next_date.weekday() in target_days:
                return next_date.strftime("%Y-%m-%d")
            next_date += timedelta(days=1)
        return next_date.strftime("%Y-%m-%d")

    if rule.startswith("monthly:"):
        parts = rule[8:].split(":")
        if len(parts) == 1:
            # Format: monthly:15 (day of month)
            try:
                target_day = int(parts[0])
            except ValueError:
                return None
            # Move to next month if we're past target day
            if current.day >= target_day:
                if current.month == 12:
                    next_date = datetime(current.year + 1, 1, target_day)
                else:
                    next_date = datetime(current.year, current.month + 1, target_day)
            else:
                next_date = datetime(current.year, current.month, target_day)
            return next_date.strftime("%Y-%m-%d")
        elif len(parts) == 2:
            # Format: monthly:3:WED (3rd Wednesday)
            try:
                nth = int(parts[0])
                target_weekday = DAY_MAP.get(parts[1].upper().strip())
                if target_weekday is None:
                    return None
            except ValueError:
                return None
            return _find_nth_weekday(current, nth, target_weekday)

    if rule.startswith("yearly:"):
        # Format: yearly:01-15 (MM-DD)
        try:
            mm_dd = rule[7:]
            target_month, target_day = map(int, mm_dd.split("-"))
        except ValueError:
            return None
        target_this_year = datetime(current.year, target_month, target_day)
        if current >= target_this_year:
            next_date = datetime(current.year + 1, target_month, target_day)
        else:
            next_date = target_this_year
        return next_date.strftime("%Y-%m-%d")

    return None


def _find_nth_weekday(current: datetime, nth: int, weekday: int) -> str:
    """Find the nth occurrence of weekday in a month, starting from current date."""
    # Start with first day of current month
    first_of_month = datetime(current.year, current.month, 1)

    # Find first occurrence of target weekday
    days_until = (weekday - first_of_month.weekday()) % 7
    first_occurrence = first_of_month + timedelta(days=days_until)

    # Find nth occurrence
    target = first_occurrence + timedelta(weeks=nth - 1)

    # If target is in the past or today, move to next month
    if target <= current:
        if current.month == 12:
            first_of_month = datetime(current.year + 1, 1, 1)
        else:
            first_of_month = datetime(current.year, current.month + 1, 1)
        days_until = (weekday - first_of_month.weekday()) % 7
        first_occurrence = first_of_month + timedelta(days=days_until)
        target = first_occurrence + timedelta(weeks=nth - 1)

    return target.strftime("%Y-%m-%d")


def does_pattern_match_date(rule: str, target_date: str) -> bool:
    """
    Check if a recurrence pattern includes a specific date.
    target_date is in YYYY-MM-DD format.
    Returns True if the pattern would include this date.
    """
    if not rule or not target_date:
        return False

    try:
        year, month, day = map(int, target_date.split("-"))
        target = datetime(year, month, day)
    except (ValueError, AttributeError):
        return False

    rule = rule.lower().strip()

    if rule == "daily":
        return True

    if rule == "weekdays":
        return target.weekday() < 5  # Mon-Fri

    if rule.startswith("weekly:"):
        days_str = rule[7:].upper()
        target_days = [DAY_MAP[d.strip()] for d in days_str.split(",") if d.strip() in DAY_MAP]
        return target.weekday() in target_days

    if rule.startswith("monthly:"):
        parts = rule[8:].split(":")
        if len(parts) == 1:
            # Format: monthly:15 (day of month)
            try:
                target_day = int(parts[0])
                return target.day == target_day
            except ValueError:
                return False
        elif len(parts) == 2:
            # Format: monthly:3:WED (3rd Wednesday)
            try:
                nth = int(parts[0])
                target_weekday = DAY_MAP.get(parts[1].upper().strip())
                if target_weekday is None:
                    return False
            except ValueError:
                return False
            # Check if target is the nth occurrence of target_weekday in its month
            if target.weekday() != target_weekday:
                return False
            # Count which occurrence this is
            first_of_month = datetime(target.year, target.month, 1)
            days_until = (target_weekday - first_of_month.weekday()) % 7
            first_occurrence = first_of_month + timedelta(days=days_until)
            occurrence_num = ((target.day - first_occurrence.day) // 7) + 1
            return occurrence_num == nth

    if rule.startswith("yearly:"):
        # Format: yearly:01-15 (MM-DD)
        try:
            mm_dd = rule[7:]
            target_month, target_day = map(int, mm_dd.split("-"))
            return target.month == target_month and target.day == target_day
        except ValueError:
            return False

    return False


def _create_instance_from_template(template: Task, target_date: str) -> Task:
    """
    Create a task instance from a template for a specific date.
    Copies title, category, recurrence_rule (for display), and time portion from template.
    """
    import uuid

    # Preserve time portion from template's scheduled_date if present
    template_scheduled = template.scheduled_date or ""
    time_portion = template_scheduled[10:] if len(template_scheduled) > 10 else ""
    instance_scheduled = target_date + time_portion

    return create_task_db(
        task_id=str(uuid.uuid4()),
        title=template.title,
        category=template.category,
        scheduled_date=instance_scheduled,
        recurrence_rule=template.recurrence_rule,  # Copy for display
        is_template=False,
        parent_task_id=template.id,
        duration_minutes=template.duration_minutes
    )


def _instance_exists_for_date(template_id: str, target_date: str) -> bool:
    """Check if an instance already exists for this template on target_date."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM tasks WHERE parent_task_id = ? AND substr(scheduled_date, 1, 10) = ?",
            (template_id, target_date)
        ).fetchone()
        return row is not None


def get_tasks_for_date(target_date: str, today: str) -> list[Task]:
    """
    Get tasks that should appear on a specific date's day view.
    target_date: The date being viewed (YYYY-MM-DD)
    today: Today's date (YYYY-MM-DD) for determining defaults

    For today: creates instances from matching templates if they don't exist.
    For past/future: shows projections for templates without instances.

    Returns tasks with 'projected' field set appropriately.
    """
    all_tasks = get_all_tasks()
    result: list[Task] = []
    is_today = target_date == today

    for task in all_tasks:
        scheduled = task.scheduled_date
        scheduled_date_only = scheduled[:10] if scheduled else None

        # Skip templates from direct inclusion - they generate instances/projections
        if task.is_template:
            # Check if pattern matches target_date and date is >= template creation date
            template_start = task.created_at[:10]  # Extract date from ISO datetime
            if target_date < template_start:
                continue
            if task.recurrence_rule and does_pattern_match_date(task.recurrence_rule, target_date):
                if is_today:
                    # Create instance if it doesn't exist
                    if not _instance_exists_for_date(task.id, target_date):
                        instance = _create_instance_from_template(task, target_date)
                        # instance already has projected=False by default
                        result.append(instance)
                    # If instance exists, it will be picked up in the non-template loop below
                else:
                    # Past or future: show as projection if no instance exists
                    if not _instance_exists_for_date(task.id, target_date):
                        # Create a projection based on template
                        time_portion = scheduled[10:] if scheduled and len(scheduled) > 10 else ""
                        projection = task.model_copy(update={
                            "projected": True,
                            "scheduled_date": target_date + time_portion
                        })
                        result.append(projection)
            continue

        # Non-template tasks (instances and regular tasks)
        # Task directly scheduled for this date
        if scheduled_date_only == target_date:
            result.append(task)  # projected=False by default
            continue

        # For today only: include tasks with no scheduled_date
        if is_today and not scheduled:
            result.append(task)
            continue

        # For today only: include incomplete non-recurrent tasks with past scheduled_date (overdue)
        # Recurrent instances (parent_task_id set) are excluded — each day gets its own instance
        if is_today and scheduled_date_only and scheduled_date_only < today and not task.completed and not task.parent_task_id:
            result.append(task)
            continue

    return result


def get_all_tasks() -> list[Task]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM tasks
            ORDER BY
                CASE category
                    WHEN 'M' THEN 1
                    WHEN 'D' THEN 2
                    ELSE 3
                END,
                scheduled_date,
                task_number
        """).fetchall()
        return [_row_to_task(row) for row in rows]

def create_task_db(
    task_id: str,
    title: str,
    category: str = "T",
    scheduled_date: Optional[str] = None,
    recurrence_rule: Optional[str] = None,
    is_template: bool = False,
    parent_task_id: Optional[str] = None,
    duration_minutes: Optional[int] = None
) -> Task:
    """Create a task with auto-generated task_key.
    duration_minutes defaults to 15 if not provided.
    scheduled_date can be YYYY-MM-DD or YYYY-MM-DDTHH:MM format.
    If is_template=True, creates a recurring template with R- prefix key.
    If parent_task_id is set, this is an instance created from a template.
    """
    if duration_minutes is None:
        duration_minutes = 15
    created_at = datetime.now().isoformat()
    # Extract date portion for task numbering (D/M categories use per-date numbering)
    date_for_numbering = scheduled_date[:10] if scheduled_date else None
    task_number = get_next_task_number(category, date_for_numbering, is_template)

    # Templates get R- prefix: R-D-01, R-M-01, etc.
    # Instances get normal keys: D-01, M-01, etc.
    if is_template:
        task_key = f"R-{category}-{task_number:02d}"
    else:
        task_key = f"{category}-{task_number:02d}"

    with get_db() as conn:
        conn.execute(
            """INSERT INTO tasks
               (id, task_key, category, task_number, title, completed, scheduled_date, recurrence_rule, created_at, is_template, parent_task_id, duration_minutes)
               VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)""",
            (task_id, task_key, category, task_number, title, scheduled_date, recurrence_rule, created_at, int(is_template), parent_task_id, duration_minutes)
        )
        conn.commit()

    return Task(
        id=task_id,
        task_key=task_key,
        category=category,
        task_number=task_number,
        title=title,
        completed=False,
        scheduled_date=scheduled_date,
        recurrence_rule=recurrence_rule,
        created_at=created_at,
        is_template=is_template,
        parent_task_id=parent_task_id,
        duration_minutes=duration_minutes,
    )

def update_task_db(task_id: str, **updates) -> Optional[Task]:
    """
    Update a task with any fields provided.
    Only updates fields that differ from current values.

    Args:
        task_id: Task ID to update
        **updates: Field names and values to update (title, completed, scheduled_date, recurrence_rule)
    """
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None

        keys = row.keys()

        # Filter updates: only include fields that differ from current values
        changes = {}
        for field, new_value in updates.items():
            if field not in keys:
                continue

            current_value = row[field]

            # Convert bool to int for comparison with SQLite storage
            if isinstance(new_value, bool):
                new_value_cmp = int(new_value)
                current_value_cmp = current_value
            else:
                new_value_cmp = new_value
                current_value_cmp = current_value

            # Only include if different
            if new_value_cmp != current_value_cmp:
                changes[field] = int(new_value) if isinstance(new_value, bool) else new_value

        # Execute UPDATE only if there are actual changes
        if changes:
            set_clause = ", ".join(f"{field} = ?" for field in changes.keys())
            values = list(changes.values()) + [task_id]
            conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
            conn.commit()

        # Return updated task (re-fetch to get current state)
        updated_row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(updated_row)

def delete_task_db(task_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0

def find_task_by_title_db(title: str) -> Optional[Task]:
    """Find a task by partial title match (case-insensitive)."""
    title_lower = title.lower()
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
        for row in rows:
            if title_lower in row["title"].lower():
                return _row_to_task(row)
    return None

def find_task_by_key_db(task_key: str) -> Optional[Task]:
    """Find a task by its key (e.g., M-01)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_key = ?",
            (task_key.upper(),)
        ).fetchone()
        if row:
            return _row_to_task(row)
    return None

# Conversation operations
def get_conversation() -> dict:
    """Get the most recent conversation by updated_at. Returns {"id": int, "messages": list}."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, messages FROM conversations ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if row:
            return {"id": row["id"], "messages": json.loads(row["messages"])}
        return {"id": None, "messages": []}

def save_conversation(messages: list[dict], conversation_id: int):
    """Save conversation messages for the given conversation_id."""
    now = datetime.now().isoformat()
    messages_json = json.dumps(messages)
    # Auto-title: set title from first user message if still 'Untitled'
    first_user = next((m["content"] for m in messages if m.get("role") == "user"), None)
    with get_db() as conn:
        row = conn.execute("SELECT title FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row:
            if row["title"] == "Untitled" and first_user:
                title = first_user[:50]
                conn.execute(
                    "UPDATE conversations SET messages = ?, updated_at = ?, title = ? WHERE id = ?",
                    (messages_json, now, title, conversation_id)
                )
            else:
                conn.execute(
                    "UPDATE conversations SET messages = ?, updated_at = ? WHERE id = ?",
                    (messages_json, now, conversation_id)
                )
        conn.commit()

def new_conversation() -> int:
    """Create a new empty conversation and return its id."""
    now = datetime.now().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO conversations (messages, title, created_at, updated_at) VALUES ('[]', 'Untitled', ?, ?)",
            (now, now)
        )
        conn.commit()
        return cursor.lastrowid
