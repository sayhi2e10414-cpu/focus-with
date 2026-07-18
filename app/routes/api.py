from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_api_token
from ..database import get_db
from ..services.core import (
    active_policy,
    active_session,
    apply_notification_action,
    build_stats,
    dump_list,
    record_event,
    serialize_direction,
    serialize_intervention,
    serialize_notification,
    serialize_policy,
    serialize_project,
    serialize_session,
    serialize_task,
    start_session,
    update_session,
    utcnow,
)
from ..config import settings
from ..services.companion import CompanionError, companion_reply
from ..services.plan_import import parse_markdown_plan


router = APIRouter(prefix="/api", dependencies=[Depends(require_api_token)])


def must_get(db: Session, model, item_id: int, label: str):
    item = db.get(model, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return item


@router.get("/bootstrap")
def bootstrap(db: Session = Depends(get_db)):
    now = utcnow()
    directions = db.query(models.Direction).order_by(models.Direction.sort_order, models.Direction.id).all()
    projects = db.query(models.Project).order_by(models.Project.sort_order, models.Project.id).all()
    tasks = db.query(models.Task).order_by(
        models.Task.status,
        models.Task.target_date,
        models.Task.priority,
        models.Task.sort_order,
        models.Task.id,
    ).all()
    sessions = db.query(models.FocusSession).order_by(models.FocusSession.id.desc()).limit(80).all()
    interventions = db.query(models.Intervention).order_by(models.Intervention.id.desc()).limit(40).all()
    notifications = (
        db.query(models.Notification)
        .filter(models.Notification.status == "pending")
        .order_by(models.Notification.id.asc())
        .limit(20)
        .all()
    )
    policy = active_policy(db)
    db.commit()
    current = active_session(db)
    return {
        "success": True,
        "data": {
            "directions": [serialize_direction(row) for row in directions],
            "projects": [serialize_project(row) for row in projects],
            "tasks": [serialize_task(row) for row in tasks],
            "active_session": serialize_session(current, now) if current else None,
            "recent_sessions": [serialize_session(row, now) for row in sessions],
            "interventions": [serialize_intervention(row) for row in interventions],
            "notifications": [serialize_notification(row) for row in notifications],
            "policy": serialize_policy(policy),
            "stats": build_stats(db, now),
        },
    }


@router.post("/directions")
def create_direction(payload: schemas.DirectionInput, db: Session = Depends(get_db)):
    item = models.Direction(**payload.model_dump())
    db.add(item)
    db.commit()
    return {"success": True, "data": serialize_direction(item)}


@router.put("/directions/{item_id}")
def update_direction(item_id: int, payload: schemas.DirectionInput, db: Session = Depends(get_db)):
    item = must_get(db, models.Direction, item_id, "Direction")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return {"success": True, "data": serialize_direction(item)}


@router.post("/projects")
def create_project(payload: schemas.ProjectInput, db: Session = Depends(get_db)):
    if payload.direction_id:
        must_get(db, models.Direction, payload.direction_id, "Direction")
    item = models.Project(**payload.model_dump())
    db.add(item)
    db.commit()
    return {"success": True, "data": serialize_project(item)}


@router.put("/projects/{item_id}")
def update_project(item_id: int, payload: schemas.ProjectInput, db: Session = Depends(get_db)):
    item = must_get(db, models.Project, item_id, "Project")
    if payload.direction_id:
        must_get(db, models.Direction, payload.direction_id, "Direction")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return {"success": True, "data": serialize_project(item)}


@router.post("/tasks")
def create_task(payload: schemas.TaskInput, db: Session = Depends(get_db)):
    if payload.project_id:
        must_get(db, models.Project, payload.project_id, "Project")
    values = payload.model_dump(exclude={"blocked_apps"})
    local_today = datetime.now(timezone.utc).astimezone(settings.timezone).date()
    values["target_date"] = values["target_date"] or local_today
    item = models.Task(**values, blocked_apps_json=dump_list(payload.blocked_apps))
    db.add(item)
    db.commit()
    return {"success": True, "data": serialize_task(item)}


@router.post("/plans/import")
def import_plan(payload: schemas.PlanImportInput, db: Session = Depends(get_db)):
    if payload.project_id:
        must_get(db, models.Project, payload.project_id, "Project")
    parsed = parse_markdown_plan(payload.markdown)
    if not parsed["tasks"]:
        raise HTTPException(status_code=422, detail="No task lines with a duration were found.")
    local_today = datetime.now(timezone.utc).astimezone(settings.timezone).date()
    created = []
    base_order = db.query(models.Task).count()
    for index, value in enumerate(parsed["tasks"]):
        item = models.Task(
            project_id=payload.project_id,
            title=value["title"],
            estimated_minutes=value["estimated_minutes"],
            target_date=payload.target_date or local_today,
            status="todo",
            task_scope="daily",
            priority=3,
            sort_order=base_order + index,
            blocked_apps_json="[]",
        )
        db.add(item)
        db.flush()
        created.append(serialize_task(item))
    db.commit()
    return {"success": True, "data": {"tasks": created, "breaks": parsed["breaks"]}}


@router.put("/tasks/{item_id}")
def update_task(item_id: int, payload: schemas.TaskInput, db: Session = Depends(get_db)):
    item = must_get(db, models.Task, item_id, "Task")
    if payload.project_id:
        must_get(db, models.Project, payload.project_id, "Project")
    for key, value in payload.model_dump(exclude={"blocked_apps"}).items():
        setattr(item, key, value)
    item.blocked_apps_json = dump_list(payload.blocked_apps)
    if item.status == "done" and not item.completed_at:
        item.completed_at = utcnow()
    elif item.status != "done":
        item.completed_at = None
    db.commit()
    return {"success": True, "data": serialize_task(item)}


@router.post("/tasks/{item_id}/complete")
def complete_task(item_id: int, db: Session = Depends(get_db)):
    item = must_get(db, models.Task, item_id, "Task")
    item.status = "done"
    item.completed_at = utcnow()
    record_event(db, "task_completed", task=item, dedupe_key=f"task_completed:task:{item.id}")
    db.flush()
    next_task = (
        db.query(models.Task)
        .filter(models.Task.status.in_(["todo", "doing"]), models.Task.id != item.id)
        .order_by(models.Task.target_date, models.Task.priority, models.Task.sort_order, models.Task.id)
        .first()
    )
    db.commit()
    return {"success": True, "data": {"task": serialize_task(item), "next_task": serialize_task(next_task) if next_task else None}}


@router.post("/tasks/{item_id}/abandon")
def abandon_task(item_id: int, db: Session = Depends(get_db)):
    item = must_get(db, models.Task, item_id, "Task")
    item.status = "abandoned"
    record_event(db, "task_abandoned", task=item, dedupe_key=f"task_abandoned:task:{item.id}")
    db.commit()
    return {"success": True, "data": serialize_task(item)}


@router.post("/tasks/{item_id}/checklist")
def add_checklist(item_id: int, payload: schemas.ChecklistInput, db: Session = Depends(get_db)):
    must_get(db, models.Task, item_id, "Task")
    row = models.ChecklistItem(task_id=item_id, **payload.model_dump())
    if row.is_done:
        row.completed_at = utcnow()
    db.add(row)
    db.commit()
    return {"success": True, "data": {"id": row.id}}


@router.post("/sessions")
def create_session(payload: schemas.SessionStartInput, db: Session = Depends(get_db)):
    if payload.task_id:
        must_get(db, models.Task, payload.task_id, "Task")
    if payload.project_id:
        must_get(db, models.Project, payload.project_id, "Project")
    item = start_session(db, payload)
    db.commit()
    return {"success": True, "data": serialize_session(item)}


@router.put("/sessions/{item_id}")
def change_session(item_id: int, payload: schemas.SessionUpdateInput, db: Session = Depends(get_db)):
    item = must_get(db, models.FocusSession, item_id, "Session")
    item = update_session(db, item, payload.action, payload.note)
    db.commit()
    return {"success": True, "data": serialize_session(item)}


@router.put("/policy")
def update_policy(payload: schemas.PolicyInput, db: Session = Depends(get_db)):
    item = active_policy(db)
    item.blocked_apps_json = dump_list(payload.blocked_apps)
    item.grace_seconds = payload.grace_seconds
    item.strikes_for_punishment = payload.strikes_for_punishment
    item.reminder_cooldown_seconds = payload.reminder_cooldown_seconds
    item.punishment_pool_json = dump_list(payload.punishment_pool)
    db.commit()
    return {"success": True, "data": serialize_policy(item)}


@router.get("/notifications")
def notifications(db: Session = Depends(get_db)):
    rows = (
        db.query(models.Notification)
        .filter(models.Notification.status == "pending")
        .order_by(models.Notification.id.asc())
        .limit(20)
        .all()
    )
    return {"success": True, "data": [serialize_notification(row) for row in rows]}


@router.post("/notifications/{item_id}/read")
def read_notification(item_id: int, db: Session = Depends(get_db)):
    item = must_get(db, models.Notification, item_id, "Notification")
    item.status = "read"
    item.read_at = utcnow()
    db.commit()
    return {"success": True}


@router.post("/notifications/{item_id}/action")
def notification_action(item_id: int, payload: schemas.NotificationActionInput, db: Session = Depends(get_db)):
    item = must_get(db, models.Notification, item_id, "Notification")
    try:
        result = apply_notification_action(db, item, payload.action)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return {"success": True, "data": result}


@router.post("/companion/chat")
async def chat_with_companion(payload: schemas.CompanionChatInput, db: Session = Depends(get_db)):
    try:
        reply, actions = await companion_reply(db, [item.model_dump() for item in payload.messages])
    except CompanionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    return {"success": True, "data": {"reply": reply, "actions": actions}}
