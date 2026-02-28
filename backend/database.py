import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import create_engine, case, func
from sqlmodel import Session, select

from models import Task, CategorySequence, Conversation

DATABASE_URL = "sqlite:///tskr.db"
engine = create_engine(DATABASE_URL)


def init_db():
    """Initialize database by running Alembic migrations."""
    import subprocess
    import os

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
    with Session(engine) as session:
        # Templates always use category_sequences with R- prefix
        if is_template:
            seq_key = f"R-{category}"
            seq = session.get(CategorySequence, seq_key)
            if seq:
                next_num = seq.next_number
                seq.next_number = next_num + 1
            else:
                next_num = 1
                session.add(CategorySequence(category=seq_key, next_number=2))
            session.commit()
            return next_num

        # Instance tasks: D and M use per-date numbering
        if category in ("D", "M"):
            if scheduled_date:
                date_prefix = scheduled_date[:10]
                count = session.exec(
                    select(func.count(Task.id)).where(
                        Task.category == category,
                        func.substr(Task.scheduled_date, 1, 10) == date_prefix,
                        Task.is_template == False  # noqa: E712
                    )
                ).one()
                return count + 1
            else:
                return 1
        else:
            # Other categories use category_sequences
            seq = session.get(CategorySequence, category)
            if seq:
                next_num = seq.next_number
                seq.next_number = next_num + 1
            else:
                next_num = 1
                session.add(CategorySequence(category=category, next_number=2))
            session.commit()
            return next_num


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
        while next_date.weekday() >= 5:
            next_date += timedelta(days=1)
        return next_date.strftime("%Y-%m-%d")

    if rule.startswith("weekly:"):
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
            try:
                target_day = int(parts[0])
            except ValueError:
                return None
            if current.day >= target_day:
                if current.month == 12:
                    next_date = datetime(current.year + 1, 1, target_day)
                else:
                    next_date = datetime(current.year, current.month + 1, target_day)
            else:
                next_date = datetime(current.year, current.month, target_day)
            return next_date.strftime("%Y-%m-%d")
        elif len(parts) == 2:
            try:
                nth = int(parts[0])
                target_weekday = DAY_MAP.get(parts[1].upper().strip())
                if target_weekday is None:
                    return None
            except ValueError:
                return None
            return _find_nth_weekday(current, nth, target_weekday)

    if rule.startswith("yearly:"):
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
    first_of_month = datetime(current.year, current.month, 1)
    days_until = (weekday - first_of_month.weekday()) % 7
    first_occurrence = first_of_month + timedelta(days=days_until)
    target = first_occurrence + timedelta(weeks=nth - 1)

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
        return target.weekday() < 5

    if rule.startswith("weekly:"):
        days_str = rule[7:].upper()
        target_days = [DAY_MAP[d.strip()] for d in days_str.split(",") if d.strip() in DAY_MAP]
        return target.weekday() in target_days

    if rule.startswith("monthly:"):
        parts = rule[8:].split(":")
        if len(parts) == 1:
            try:
                target_day = int(parts[0])
                return target.day == target_day
            except ValueError:
                return False
        elif len(parts) == 2:
            try:
                nth = int(parts[0])
                target_weekday = DAY_MAP.get(parts[1].upper().strip())
                if target_weekday is None:
                    return False
            except ValueError:
                return False
            if target.weekday() != target_weekday:
                return False
            first_of_month = datetime(target.year, target.month, 1)
            days_until = (target_weekday - first_of_month.weekday()) % 7
            first_occurrence = first_of_month + timedelta(days=days_until)
            occurrence_num = ((target.day - first_occurrence.day) // 7) + 1
            return occurrence_num == nth

    if rule.startswith("yearly:"):
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

    template_scheduled = template.scheduled_date or ""
    time_portion = template_scheduled[10:] if len(template_scheduled) > 10 else ""
    instance_scheduled = target_date + time_portion

    return create_task_db(
        task_id=str(uuid.uuid4()),
        title=template.title,
        category=template.category,
        scheduled_date=instance_scheduled,
        recurrence_rule=template.recurrence_rule,
        is_template=False,
        parent_task_id=template.id,
        duration_minutes=template.duration_minutes,
        priority=template.priority
    )


def _instance_exists_for_date(template_id: str, target_date: str) -> bool:
    """Check if an instance already exists for this template on target_date."""
    with Session(engine) as session:
        result = session.exec(
            select(Task.id).where(
                Task.parent_task_id == template_id,
                func.substr(Task.scheduled_date, 1, 10) == target_date
            )
        ).first()
        return result is not None


def get_tasks_for_date(target_date: str, today: str) -> list[Task]:
    """
    Get tasks that should appear on a specific date's day view.
    target_date: The date being viewed (YYYY-MM-DD)
    today: Today's date (YYYY-MM-DD) for determining defaults

    For today: creates instances from matching templates if they don't exist.
    For past/future: returns templates directly as projections (is_template=True signals projection).
    """
    all_tasks = get_all_tasks()
    result: list[Task] = []
    is_today = target_date == today

    for task in all_tasks:
        scheduled = task.scheduled_date
        scheduled_date_only = scheduled[:10] if scheduled else None

        # Skip templates from direct inclusion - they generate instances/projections
        if task.is_template:
            template_start = task.created_at[:10]
            if target_date < template_start:
                continue
            if task.recurrence_rule and does_pattern_match_date(task.recurrence_rule, target_date):
                if is_today:
                    if not _instance_exists_for_date(task.id, target_date):
                        instance = _create_instance_from_template(task, target_date)
                        result.append(instance)
                else:
                    # Past or future: return template directly as projection
                    # Frontend identifies projections via is_template=True
                    if not _instance_exists_for_date(task.id, target_date):
                        time_portion = scheduled[10:] if scheduled and len(scheduled) > 10 else ""
                        projection = task.model_copy(update={
                            "scheduled_date": target_date + time_portion
                        })
                        result.append(projection)
            continue

        # Non-template tasks
        if scheduled_date_only == target_date:
            result.append(task)
            continue

        # For today only: include incomplete non-recurrent tasks with past scheduled_date (overdue)
        # Excluded: recurrent instances (each day gets its own) and meetings (time-bound events)
        if is_today and scheduled_date_only and scheduled_date_only < today and not task.completed and not task.parent_task_id and task.category != "M":
            result.append(task)
            continue

    return result


def get_all_tasks() -> list[Task]:
    with Session(engine) as session:
        statement = select(Task).order_by(
            case(
                (Task.category == "M", 1),
                (Task.category == "D", 2),
                else_=3
            ),
            Task.scheduled_date,
            Task.task_number
        )
        return list(session.exec(statement).all())


def create_task_db(
    task_id: str,
    title: str,
    category: str = "T",
    scheduled_date: Optional[str] = None,
    recurrence_rule: Optional[str] = None,
    is_template: bool = False,
    parent_task_id: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    priority: Optional[int] = None
) -> Task:
    """Create a task with auto-generated task_key.
    duration_minutes defaults to 15 if not provided.
    priority: 0=None, 1=Low, 2=Medium, 3=High, 4=Critical
    scheduled_date can be YYYY-MM-DD or YYYY-MM-DDTHH:MM format.
    """
    if duration_minutes is None:
        duration_minutes = 15
    created_at = datetime.now().isoformat()
    date_for_numbering = scheduled_date[:10] if scheduled_date else None
    task_number = get_next_task_number(category, date_for_numbering, is_template)

    if is_template:
        task_key = f"R-{category}-{task_number:02d}"
    else:
        task_key = f"{category}-{task_number:02d}"

    task = Task(
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
        priority=priority,
    )

    with Session(engine) as session:
        session.add(task)
        session.commit()
        session.refresh(task)

    return task


def update_task_db(task_id: str, **updates) -> Optional[Task]:
    """
    Update a task with any fields provided.
    Only updates fields that differ from current values.
    """
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            return None

        for field, new_value in updates.items():
            if not hasattr(task, field):
                continue
            current_value = getattr(task, field)
            if new_value != current_value:
                setattr(task, field, new_value)

        session.commit()
        session.refresh(task)
        # Return a detached copy so it can be used after session closes
        return task.model_copy()


def delete_task_db(task_id: str) -> bool:
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            return False
        session.delete(task)
        session.commit()
        return True


def find_task_by_title_db(title: str) -> Optional[Task]:
    """Find a task by partial title match (case-insensitive)."""
    with Session(engine) as session:
        results = session.exec(
            select(Task).where(func.lower(Task.title).contains(title.lower()))
        ).first()
        if results:
            return results.model_copy()
    return None


def find_task_by_key_db(task_key: str) -> Optional[Task]:
    """Find a task by its key (e.g., M-01)."""
    with Session(engine) as session:
        task = session.exec(
            select(Task).where(Task.task_key == task_key.upper())
        ).first()
        if task:
            return task.model_copy()
    return None


# Conversation operations

def get_conversation() -> dict:
    """Get the most recent conversation by updated_at. Returns {"id": int, "messages": list}."""
    with Session(engine) as session:
        conv = session.exec(
            select(Conversation).order_by(Conversation.updated_at.desc())
        ).first()
        if conv:
            return {"id": conv.id, "messages": json.loads(conv.messages)}
        return {"id": None, "messages": []}


def save_conversation(messages: list[dict], conversation_id: int):
    """Save conversation messages for the given conversation_id."""
    now = datetime.now().isoformat()
    with Session(engine) as session:
        conv = session.get(Conversation, conversation_id)
        if not conv:
            return

        conv.messages = json.dumps(messages)
        conv.updated_at = now

        # Auto-title from first user message if still default
        if conv.title == "Untitled":
            first_user = next((m["content"] for m in messages if m.get("role") == "user"), None)
            if first_user:
                conv.title = first_user[:50]

        session.commit()


def new_conversation() -> int:
    """Create a new empty conversation and return its id."""
    now = datetime.now().isoformat()
    with Session(engine) as session:
        conv = Conversation(created_at=now, updated_at=now)
        session.add(conv)
        session.commit()
        session.refresh(conv)
        return conv.id

def list_conversations(limit: int | None = None) -> list[dict]:
    """Return conversations ordered by updated_at DESC. Each dict has id, title, updated_at."""
    with Session(engine) as session:
        statement = select(Conversation).order_by(Conversation.updated_at.desc())
        if limit is not None:
            statement = statement.limit(limit)
        convs = session.exec(statement).all()
        return [{"id": c.id, "title": c.title, "updated_at": c.updated_at} for c in convs]


def get_conversation_by_id(conversation_id: int) -> dict:
    """Return {id, messages} for the given conversation_id, or {id: None, messages: []} if not found."""
    with Session(engine) as session:
        conv = session.get(Conversation, conversation_id)
        if conv:
            return {"id": conv.id, "messages": json.loads(conv.messages)}
        return {"id": None, "messages": []}

