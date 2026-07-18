from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def dump_list(values) -> str:
    return json.dumps([str(item).strip() for item in (values or []) if str(item).strip()], ensure_ascii=False)


def json_value(raw: Optional[str], fallback):
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return fallback


def event_payload(event: models.FocusEvent) -> dict[str, Any]:
    value = json_value(event.payload_json, {})
    return value if isinstance(value, dict) else {}


def session_elapsed(session: models.FocusSession, now: Optional[datetime] = None) -> int:
    elapsed = max(0, int(session.elapsed_seconds or 0))
    if session.status == "running":
        anchor = session.last_resumed_at or session.started_at
        if anchor:
            elapsed += max(0, int(((now or utcnow()) - anchor).total_seconds()))
    return elapsed


def serialize_direction(item: models.Direction) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "goal": item.goal,
        "status": item.status,
        "weekly_target_minutes": item.weekly_target_minutes or 0,
        "sort_order": item.sort_order or 0,
    }


def serialize_project(item: models.Project) -> dict:
    return {
        "id": item.id,
        "direction_id": item.direction_id,
        "title": item.title,
        "outcome": item.outcome,
        "notes": item.notes,
        "status": item.status,
        "weekly_target_minutes": item.weekly_target_minutes or 0,
        "target_minutes": item.target_minutes or 0,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "sort_order": item.sort_order or 0,
    }


def serialize_checklist(item: models.ChecklistItem) -> dict:
    return {
        "id": item.id,
        "task_id": item.task_id,
        "content": item.content,
        "is_done": bool(item.is_done),
        "sort_order": item.sort_order or 0,
    }


def serialize_task(item: models.Task) -> dict:
    return {
        "id": item.id,
        "project_id": item.project_id,
        "title": item.title,
        "details": item.details,
        "status": item.status,
        "task_scope": item.task_scope,
        "priority": item.priority,
        "sort_order": item.sort_order or 0,
        "estimated_minutes": item.estimated_minutes or 25,
        "target_date": item.target_date.isoformat() if item.target_date else None,
        "blocked_apps": json_value(item.blocked_apps_json, []),
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "checklist": [serialize_checklist(row) for row in item.checklist],
    }


def serialize_session(item: models.FocusSession, now: Optional[datetime] = None) -> dict:
    return {
        "id": item.id,
        "task_id": item.task_id,
        "project_id": item.project_id,
        "session_kind": item.session_kind,
        "mode": item.mode,
        "title": item.title,
        "goal": item.goal,
        "note": item.note,
        "planned_minutes": item.planned_minutes,
        "elapsed_seconds": session_elapsed(item, now),
        "status": item.status,
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "ended_at": item.ended_at.isoformat() if item.ended_at else None,
    }


def serialize_policy(item: models.FocusPolicy) -> dict:
    return {
        "id": item.id,
        "blocked_apps": json_value(item.blocked_apps_json, []),
        "grace_seconds": item.grace_seconds,
        "strikes_for_punishment": item.strikes_for_punishment,
        "reminder_cooldown_seconds": item.reminder_cooldown_seconds,
        "punishment_pool": json_value(item.punishment_pool_json, []),
    }


def serialize_intervention(item: models.Intervention) -> dict:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "task_id": item.task_id,
        "app_name": item.app_name,
        "opened_at": item.opened_at.isoformat(),
        "closed_at": item.closed_at.isoformat() if item.closed_at else None,
        "duration_seconds": item.duration_seconds or 0,
        "strike_number": item.strike_number or 0,
        "status": item.status,
        "message": item.message,
        "punishment": item.punishment,
    }


def serialize_notification(item: models.Notification) -> dict:
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "body": item.body,
        "actions": json_value(item.actions_json, []),
        "status": item.status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def active_policy(db: Session) -> models.FocusPolicy:
    policy = (
        db.query(models.FocusPolicy)
        .filter(models.FocusPolicy.is_active.is_(True))
        .order_by(models.FocusPolicy.updated_at.desc(), models.FocusPolicy.id.desc())
        .first()
    )
    if policy:
        return policy
    policy = models.FocusPolicy(name="Default", blocked_apps_json="[]", punishment_pool_json="[]")
    db.add(policy)
    db.flush()
    return policy


def active_session(db: Session) -> Optional[models.FocusSession]:
    return (
        db.query(models.FocusSession)
        .filter(models.FocusSession.status.in_(["running", "paused"]))
        .order_by(models.FocusSession.updated_at.desc(), models.FocusSession.id.desc())
        .first()
    )


def record_event(
    db: Session,
    event_type: str,
    *,
    session: Optional[models.FocusSession] = None,
    task: Optional[models.Task] = None,
    dedupe_key: Optional[str] = None,
    payload: Optional[dict] = None,
) -> models.FocusEvent:
    if dedupe_key:
        existing = db.query(models.FocusEvent).filter(models.FocusEvent.dedupe_key == dedupe_key).first()
        if existing:
            return existing
    event = models.FocusEvent(
        session_id=session.id if session else None,
        task_id=task.id if task else (session.task_id if session else None),
        event_type=event_type,
        dedupe_key=dedupe_key,
        payload_json=json.dumps(payload or {}, ensure_ascii=False),
    )
    db.add(event)
    db.flush()
    return event


def create_notification(
    db: Session,
    event: models.FocusEvent,
    *,
    kind: str,
    title: str,
    body: str,
    actions: Optional[list[dict]] = None,
) -> models.Notification:
    existing = db.query(models.Notification).filter(models.Notification.event_id == event.id).first()
    if existing:
        return existing
    item = models.Notification(
        event_id=event.id,
        kind=kind,
        title=title,
        body=body,
        actions_json=json.dumps(actions or [], ensure_ascii=False),
    )
    db.add(item)
    db.flush()
    return item


def apply_notification_action(db: Session, item: models.Notification, action: str) -> dict:
    if item.status == "read":
        return {"status": "already_handled"}
    event = db.get(models.FocusEvent, item.event_id) if item.event_id else None
    source_session = db.get(models.FocusSession, event.session_id) if event and event.session_id else None
    task = db.get(models.Task, event.task_id) if event and event.task_id else None
    result: dict = {"action": action}

    if action == "complete":
        if not task:
            raise ValueError("This notification is not linked to a task")
        task.status = "done"
        task.completed_at = utcnow()
        record_event(db, "task_completed", task=task, dedupe_key=f"task_completed:task:{task.id}")
        result["task"] = serialize_task(task)
    elif action == "repeat":
        if not source_session:
            raise ValueError("This notification is not linked to a focus session")
        repeated = start_session(db, schemas.SessionStartInput(
            task_id=source_session.task_id,
            project_id=source_session.project_id,
            session_kind=source_session.session_kind,
            mode=source_session.mode,
            title=source_session.title,
            goal=source_session.goal,
            planned_minutes=source_session.planned_minutes,
        ))
        result["session"] = serialize_session(repeated)
    elif action == "break":
        break_session = start_session(db, schemas.SessionStartInput(
            session_kind="break",
            mode="pomodoro",
            title="Break",
            planned_minutes=5,
        ))
        result["session"] = serialize_session(break_session)
    elif action == "resume":
        current = active_session(db)
        if not current or current.status != "paused":
            raise ValueError("There is no paused focus session")
        update_session(db, current, "resume")
        result["session"] = serialize_session(current)
    elif action != "dismiss":
        raise ValueError(f"Unsupported notification action: {action}")

    item.status = "read"
    item.read_at = utcnow()
    return result


def pause_current_session(db: Session, now: datetime) -> None:
    current = active_session(db)
    if not current or current.status != "running":
        return
    current.elapsed_seconds = session_elapsed(current, now)
    current.last_resumed_at = None
    current.status = "paused"
    record_event(db, "session_paused", session=current, payload={"reason": "another_session_started"})


def start_session(db: Session, values) -> models.FocusSession:
    now = utcnow()
    pause_current_session(db, now)
    task = db.get(models.Task, values.task_id) if values.task_id else None
    project_id = values.project_id or (task.project_id if task else None)
    item = models.FocusSession(
        task_id=values.task_id,
        project_id=project_id,
        session_kind=values.session_kind,
        mode=values.mode,
        title=(values.title or "").strip() or None,
        goal=(values.goal or "").strip() or None,
        planned_minutes=values.planned_minutes or None,
        status="running",
        started_at=now,
        last_resumed_at=now,
    )
    db.add(item)
    db.flush()
    if task and task.status == "todo":
        task.status = "doing"
    record_event(
        db,
        "session_started",
        session=item,
        task=task,
        payload={"title": task.title if task else (item.goal or item.title), "planned_minutes": item.planned_minutes},
    )
    return item


def update_session(db: Session, item: models.FocusSession, action: str, note: Optional[str] = None) -> models.FocusSession:
    now = utcnow()
    task = db.get(models.Task, item.task_id) if item.task_id else None
    if action == "pause" and item.status == "running":
        item.elapsed_seconds = session_elapsed(item, now)
        item.last_resumed_at = None
        item.status = "paused"
        record_event(db, "session_paused", session=item, task=task)
    elif action == "resume" and item.status == "paused":
        item.last_resumed_at = now
        item.status = "running"
        record_event(db, "session_resumed", session=item, task=task)
    elif action in {"complete", "cancel"} and item.status in {"running", "paused"}:
        item.elapsed_seconds = session_elapsed(item, now)
        item.last_resumed_at = None
        item.ended_at = now
        item.status = "completed" if action == "complete" else "cancelled"
        event_type = "session_completed" if action == "complete" else "session_cancelled"
        record_event(
            db,
            event_type,
            session=item,
            task=task,
            dedupe_key=f"{event_type}:session:{item.id}",
        )
    if note is not None:
        item.note = note.strip() or None
    return item


def task_title(db: Session, session: models.FocusSession) -> str:
    task = db.get(models.Task, session.task_id) if session.task_id else None
    return task.title if task else (session.goal or session.title or "Focus session")


def finish_due_timer(db: Session, session: models.FocusSession, now: datetime) -> bool:
    if session.status != "running" or not session.planned_minutes:
        return False
    if session_elapsed(session, now) < int(session.planned_minutes) * 60:
        return False
    session.elapsed_seconds = int(session.planned_minutes) * 60
    session.last_resumed_at = None
    session.ended_at = now
    session.status = "completed"
    event_type = "break_completed" if session.session_kind == "break" else "session_completed"
    event = record_event(
        db,
        event_type,
        session=session,
        dedupe_key=f"{event_type}:session:{session.id}",
        payload={"title": task_title(db, session), "planned_minutes": session.planned_minutes},
    )
    label = task_title(db, session)
    if session.session_kind == "break":
        title = "Break finished"
        body = f"Your break is over. Ready to return to {label}?"
        actions = [{"action": "dismiss", "label": "Back to focus"}]
    else:
        title = "Focus timer finished"
        body = f"Your {session.planned_minutes}-minute session for {label} is complete."
        actions = [
            {"action": "complete", "label": "Complete task"},
            {"action": "repeat", "label": "Repeat"},
            {"action": "break", "label": "Take a break"},
        ]
    create_notification(db, event, kind=event_type, title=title, body=body, actions=actions)
    return True


def current_open_event(db: Session, device_id: str = "iphone") -> Optional[models.PhoneAppEvent]:
    rows = (
        db.query(models.PhoneAppEvent)
        .filter(models.PhoneAppEvent.device_id == device_id)
        .order_by(models.PhoneAppEvent.occurred_at.desc(), models.PhoneAppEvent.id.desc())
        .limit(100)
        .all()
    )
    state: dict[str, models.PhoneAppEvent] = {}
    for row in rows:
        state.setdefault(row.app_name, row)
    opened = [row for row in state.values() if row.event_type == "opened"]
    return max(opened, key=lambda row: (row.occurred_at, row.id)) if opened else None


def record_phone_event(db: Session, values) -> models.PhoneAppEvent:
    now = values.occurred_at
    if now and now.tzinfo:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    now = now or utcnow()
    event_type = values.event_type
    if event_type == "toggle":
        latest = (
            db.query(models.PhoneAppEvent)
            .filter(models.PhoneAppEvent.device_id == values.device_id, models.PhoneAppEvent.app_name == values.app_name)
            .order_by(models.PhoneAppEvent.occurred_at.desc(), models.PhoneAppEvent.id.desc())
            .first()
        )
        event_type = "closed" if latest and latest.event_type == "opened" else "opened"
    if event_type == "opened":
        active = current_open_event(db, values.device_id)
        if active and active.app_name != values.app_name:
            db.add(models.PhoneAppEvent(
                device_id=values.device_id,
                app_name=active.app_name,
                event_type="closed",
                source="auto_close",
                occurred_at=now,
            ))
    item = models.PhoneAppEvent(
        device_id=values.device_id,
        app_name=values.app_name.strip(),
        event_type=event_type,
        source=values.source,
        occurred_at=now,
    )
    db.add(item)
    db.flush()
    return item


def phone_usage_for_date(db: Session, local_day, device_id: str = "iphone", now: Optional[datetime] = None) -> dict:
    now = now or utcnow()
    start_local = datetime.combine(local_day, datetime.min.time(), tzinfo=settings.timezone)
    end_local = start_local + timedelta(days=1)
    start = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    effective_end = min(end, now)
    rows = (
        db.query(models.PhoneAppEvent)
        .filter(models.PhoneAppEvent.device_id == device_id, models.PhoneAppEvent.occurred_at < end)
        .order_by(models.PhoneAppEvent.occurred_at, models.PhoneAppEvent.id)
        .all()
    )
    opened: dict[str, datetime] = {}
    seconds: dict[str, int] = {}
    for row in rows:
        key = row.app_name
        if row.event_type == "opened":
            opened.setdefault(key, max(row.occurred_at, start))
        elif row.event_type == "closed" and key in opened:
            close_at = min(row.occurred_at, effective_end)
            seconds[key] = seconds.get(key, 0) + max(0, int((close_at - opened.pop(key)).total_seconds()))
    for key, opened_at in opened.items():
        seconds[key] = seconds.get(key, 0) + max(0, int((effective_end - opened_at).total_seconds()))
    apps = sorted(
        ({"app_name": key, "seconds": value, "minutes": round(value / 60)} for key, value in seconds.items()),
        key=lambda item: item["seconds"],
        reverse=True,
    )
    return {"date": local_day.isoformat(), "device_id": device_id, "total_seconds": sum(seconds.values()), "apps": apps}


def close_stale_interventions(db: Session, current: Optional[models.PhoneAppEvent], now: datetime) -> None:
    rows = db.query(models.Intervention).filter(models.Intervention.closed_at.is_(None)).all()
    for row in rows:
        if current and current.id == row.phone_open_event_id:
            continue
        row.closed_at = now
        row.duration_seconds = max(0, int((now - row.opened_at).total_seconds()))
        row.resolved_at = now
        row.status = "resolved_before_grace" if row.status == "observing" else "resolved"


def observe_distraction(db: Session, session: models.FocusSession, now: datetime) -> bool:
    current = current_open_event(db)
    close_stale_interventions(db, current, now)
    if not current:
        return False
    policy = active_policy(db)
    task = db.get(models.Task, session.task_id) if session.task_id else None
    task_apps = json_value(task.blocked_apps_json, []) if task else []
    blocked = {str(name).strip().casefold() for name in (task_apps or json_value(policy.blocked_apps_json, []))}
    if current.app_name.casefold() not in blocked:
        return False
    item = db.query(models.Intervention).filter(models.Intervention.phone_open_event_id == current.id).first()
    if item and item.sent_at:
        return False
    if not item:
        item = models.Intervention(
            session_id=session.id,
            task_id=session.task_id,
            phone_open_event_id=current.id,
            app_name=current.app_name,
            opened_at=current.occurred_at,
        )
        db.add(item)
        db.flush()
    age = max(0, int((now - item.opened_at).total_seconds()))
    if age < max(15, policy.grace_seconds or 90):
        return False
    previous = (
        db.query(models.Intervention)
        .filter(models.Intervention.session_id == session.id, models.Intervention.sent_at.isnot(None))
        .order_by(models.Intervention.strike_number.desc())
        .first()
    )
    if previous and previous.sent_at:
        cooldown = max(30, policy.reminder_cooldown_seconds or 300)
        if (now - previous.sent_at).total_seconds() < cooldown:
            item.status = "suppressed_cooldown"
            item.closed_at = now
            item.resolved_at = now
            return False
    strike = (previous.strike_number if previous else 0) + 1
    pool = json_value(policy.punishment_pool_json, [])
    punishment = None
    if strike >= max(1, policy.strikes_for_punishment or 3):
        punishment = pool[(strike - policy.strikes_for_punishment) % len(pool)] if pool else "Review this distraction"
    item.strike_number = strike
    item.status = "punishment_pending" if punishment else "sent"
    item.punishment = punishment
    item.sent_at = now
    item.duration_seconds = age
    label = task_title(db, session)
    body = f"{current.app_name} was opened during {label}. If you are still there, return to the task."
    item.message = body
    event = record_event(
        db,
        "distraction_punishment" if punishment else "distraction_warning",
        session=session,
        task=task,
        dedupe_key=f"distraction:phone-event:{current.id}",
        payload={"app_name": current.app_name, "strike": strike, "punishment": punishment},
    )
    create_notification(db, event, kind="distraction", title=f"Focus reminder · {strike}", body=body)
    return True


def build_stats(db: Session, now: Optional[datetime] = None) -> dict:
    now = now or utcnow()
    local_now = now.replace(tzinfo=timezone.utc).astimezone(settings.timezone)
    today = local_now.date()
    week_start = today - timedelta(days=today.weekday())
    sessions = db.query(models.FocusSession).filter(models.FocusSession.status != "cancelled").all()

    def local_date(row: models.FocusSession):
        stamp = row.started_at or row.created_at
        return stamp.replace(tzinfo=timezone.utc).astimezone(settings.timezone).date() if stamp else None

    def summarize(rows):
        seconds = sum(session_elapsed(row, now) for row in rows if row.session_kind != "break")
        grouped: dict[str, dict] = {}
        for row in rows:
            if row.session_kind == "break":
                continue
            task = db.get(models.Task, row.task_id) if row.task_id else None
            label = task.title if task else (row.title or row.goal or "Free focus")
            key = f"task:{row.task_id}" if row.task_id else f"free:{label.strip().casefold()}"
            bucket = grouped.setdefault(key, {
                "task_id": row.task_id,
                "project_id": row.project_id,
                "title": label,
                "focus_seconds": 0,
                "session_count": 0,
            })
            bucket["focus_seconds"] += session_elapsed(row, now)
            bucket["session_count"] += 1
        return {
            "focus_seconds": seconds,
            "focus_minutes": round(seconds / 60),
            "session_count": len([row for row in rows if row.session_kind != "break"]),
            "by_activity": sorted(grouped.values(), key=lambda item: item["focus_seconds"], reverse=True),
        }

    today_rows = [row for row in sessions if local_date(row) == today]
    week_rows = [row for row in sessions if local_date(row) and week_start <= local_date(row) <= today]
    completed_today = db.query(models.Task).filter(models.Task.status == "done").all()
    completed_today = [
        row for row in completed_today
        if row.completed_at and row.completed_at.replace(tzinfo=timezone.utc).astimezone(settings.timezone).date() == today
    ]
    interventions = db.query(models.Intervention).all()
    today_interventions = [
        row for row in interventions
        if row.opened_at
        and row.opened_at.replace(tzinfo=timezone.utc).astimezone(settings.timezone).date() == today
    ]
    return {
        "today": {**summarize(today_rows), "completed_tasks": len(completed_today), "interruptions": len(today_interventions)},
        "week": summarize(week_rows),
    }
