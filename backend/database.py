import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager

DATABASE_PATH = "deskbot.db"

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

def get_next_task_number(category: str, scheduled_date: Optional[str] = None) -> int:
    """
    Get next task number for a category.
    For D and M categories, number is per-date.
    For others, number continues indefinitely.
    """
    with get_db() as conn:
        if category in ("D", "M"):
            # Count existing tasks for this category on this date
            # Use substr to match date portion only (scheduled_date may include time)
            if scheduled_date:
                count = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE category = ? AND substr(scheduled_date, 1, 10) = ?",
                    (category, scheduled_date[:10])
                ).fetchone()[0]
                return count + 1
            else:
                # D/M without date - use 1 (edge case)
                return 1
        else:
            # Get from sequence table
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

def _row_to_task(row) -> dict:
    """Convert a database row to a task dict."""
    keys = row.keys()
    # Treat empty string as None for recurrence_rule
    recurrence = row["recurrence_rule"] if "recurrence_rule" in keys else None
    if recurrence == "":
        recurrence = None
    return {
        "id": row["id"],
        "task_key": row["task_key"],
        "category": row["category"],
        "task_number": row["task_number"],
        "title": row["title"],
        "completed": bool(row["completed"]),
        "scheduled_date": row["scheduled_date"],
        "recurrence_rule": recurrence,
        "created_at": row["created_at"]
    }


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

def get_all_tasks() -> list[dict]:
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
    recurrence_rule: Optional[str] = None
) -> dict:
    """Create a task with auto-generated task_key.
    scheduled_date can be YYYY-MM-DD or YYYY-MM-DDTHH:MM format.
    """
    created_at = datetime.now().isoformat()
    # Extract date portion for task numbering (D/M categories use per-date numbering)
    date_for_numbering = scheduled_date[:10] if scheduled_date else None
    task_number = get_next_task_number(category, date_for_numbering)
    task_key = f"{category}-{task_number:02d}"

    with get_db() as conn:
        conn.execute(
            """INSERT INTO tasks
               (id, task_key, category, task_number, title, completed, scheduled_date, recurrence_rule, created_at)
               VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)""",
            (task_id, task_key, category, task_number, title, scheduled_date, recurrence_rule, created_at)
        )
        conn.commit()

    return {
        "id": task_id,
        "task_key": task_key,
        "category": category,
        "task_number": task_number,
        "title": title,
        "completed": False,
        "scheduled_date": scheduled_date,
        "recurrence_rule": recurrence_rule,
        "created_at": created_at
    }

def update_task_db(
    task_id: str,
    title: Optional[str] = None,
    completed: Optional[bool] = None,
    scheduled_date: Optional[str] = None,
    recurrence_rule: Optional[str] = None
) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None

        keys = row.keys()
        new_title = title if title is not None else row["title"]
        new_scheduled = scheduled_date if scheduled_date is not None else row["scheduled_date"]
        current_rule = row["recurrence_rule"] if "recurrence_rule" in keys else None
        new_rule = recurrence_rule if recurrence_rule is not None else current_rule

        # Handle recurring task completion
        # If completing a recurring task, advance to next occurrence instead
        # Extract date portion for recurrence calculation, preserve time if present
        if completed and new_rule and new_scheduled:
            date_portion = new_scheduled[:10]  # YYYY-MM-DD
            time_portion = new_scheduled[10:] if len(new_scheduled) > 10 else ""  # THH:MM if present
            next_date = calculate_next_occurrence(new_rule, date_portion)
            if next_date:
                new_scheduled = next_date + time_portion  # Preserve time
                new_completed = 0  # Reset to incomplete for next occurrence
            else:
                new_completed = 1  # Invalid rule, just mark complete
        else:
            new_completed = int(completed) if completed is not None else row["completed"]

        conn.execute(
            "UPDATE tasks SET title = ?, completed = ?, scheduled_date = ?, recurrence_rule = ? WHERE id = ?",
            (new_title, new_completed, new_scheduled, new_rule, task_id)
        )
        conn.commit()

        return {
            "id": task_id,
            "task_key": row["task_key"],
            "category": row["category"],
            "task_number": row["task_number"],
            "title": new_title,
            "completed": bool(new_completed),
            "scheduled_date": new_scheduled,
            "recurrence_rule": new_rule,
            "created_at": row["created_at"]
        }

def delete_task_db(task_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0

def find_task_by_title_db(title: str) -> Optional[dict]:
    """Find a task by partial title match (case-insensitive)."""
    title_lower = title.lower()
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
        for row in rows:
            if title_lower in row["title"].lower():
                return _row_to_task(row)
    return None

def find_task_by_key_db(task_key: str) -> Optional[dict]:
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
def get_conversation() -> list[dict]:
    """Get the current conversation messages."""
    with get_db() as conn:
        row = conn.execute("SELECT messages FROM conversations WHERE id = 1").fetchone()
        if row:
            return json.loads(row["messages"])
        return []

def save_conversation(messages: list[dict]):
    """Save conversation messages."""
    now = datetime.now().isoformat()
    messages_json = json.dumps(messages)
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM conversations WHERE id = 1").fetchone()
        if existing:
            conn.execute(
                "UPDATE conversations SET messages = ?, updated_at = ? WHERE id = 1",
                (messages_json, now)
            )
        else:
            conn.execute(
                "INSERT INTO conversations (id, messages, created_at, updated_at) VALUES (1, ?, ?, ?)",
                (messages_json, now, now)
            )
        conn.commit()
