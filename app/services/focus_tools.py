from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from .core import (
    active_session,
    build_stats,
    dump_list,
    serialize_project,
    serialize_session,
    serialize_task,
    start_session,
    update_session,
    utcnow,
)
from .rewards import (
    create_reward as create_reward_definition,
    redeem_grant,
    reward_overview,
    select_reward as select_reward_definition,
    serialize_grant,
    serialize_reward,
)


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "get_focus_context",
        "description": "Read the active timer, open projects, today's tasks, and daily/weekly focus statistics.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_project",
        "description": "Create a project for a concrete outcome. Use projects to group related tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "outcome": {"type": "string"},
                "weekly_target_minutes": {"type": "integer", "minimum": 0},
            },
            "required": ["title"],
        },
    },
    {
        "name": "create_task",
        "description": "Create one actionable focus task, optionally inside a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "details": {"type": "string"},
                "project_id": {"type": "integer"},
                "estimated_minutes": {"type": "integer", "minimum": 1, "maximum": 1440},
                "target_date": {"type": "string", "description": "ISO date, YYYY-MM-DD"},
                "priority": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_task",
        "description": "Move, reschedule, rename, or reprioritize an existing task. Only supplied fields are changed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "title": {"type": "string"},
                "details": {"type": "string"},
                "project_id": {"type": ["integer", "null"]},
                "estimated_minutes": {"type": "integer", "minimum": 1, "maximum": 1440},
                "target_date": {"type": "string", "description": "ISO date, YYYY-MM-DD"},
                "priority": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "start_focus",
        "description": "Start a focus timer for a task, or a free-focus title when task_id is omitted.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "title": {"type": "string"},
                "minutes": {"type": "integer", "minimum": 1, "maximum": 1440},
                "mode": {"type": "string", "enum": ["pomodoro", "deep", "countup"]},
            },
        },
    },
    {
        "name": "control_focus",
        "description": "Pause, resume, complete, or cancel the current focus session.",
        "input_schema": {
            "type": "object",
            "properties": {"action": {"type": "string", "enum": ["pause", "resume", "complete", "cancel"]}},
            "required": ["action"],
        },
    },
    {
        "name": "complete_task",
        "description": "Mark a task completed after the user says it is done.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "get_reward_status",
        "description": "Read the selected reward target, uninterrupted-focus progress, reward catalog, and earned reward inventory.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_reward",
        "description": "Create a custom reward that is earned after a chosen number of uninterrupted focus minutes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "details": {"type": "string"},
                "focus_minutes": {"type": "integer", "minimum": 5, "maximum": 1440},
                "reward_minutes": {"type": ["integer", "null"], "minimum": 1, "maximum": 1440},
                "repeatable": {"type": "boolean"},
            },
            "required": ["title", "focus_minutes"],
        },
    },
    {
        "name": "select_reward",
        "description": "Select a reward target. Changing it during a focus session restarts only the current uninterrupted progress.",
        "input_schema": {
            "type": "object",
            "properties": {"reward_id": {"type": "integer"}},
            "required": ["reward_id"],
        },
    },
    {
        "name": "redeem_reward",
        "description": "Redeem one already-earned reward from the reward cabinet after the user confirms they want to enjoy it now.",
        "input_schema": {
            "type": "object",
            "properties": {"grant_id": {"type": "integer"}},
            "required": ["grant_id"],
        },
    },
]


def _today() -> date:
    return datetime.now(timezone.utc).astimezone(settings.timezone).date()


def _must_get(db: Session, model, item_id: int, label: str):
    item = db.get(model, item_id)
    if not item:
        raise ValueError(f"{label} {item_id} was not found")
    return item


def focus_context(db: Session) -> dict[str, Any]:
    now = utcnow()
    projects = (
        db.query(models.Project)
        .filter(models.Project.status.in_(["active", "paused"]))
        .order_by(models.Project.sort_order, models.Project.id)
        .all()
    )
    tasks = (
        db.query(models.Task)
        .filter(models.Task.status.in_(["todo", "doing"]))
        .order_by(models.Task.target_date, models.Task.priority, models.Task.sort_order, models.Task.id)
        .all()
    )
    current = active_session(db)
    return {
        "today": _today().isoformat(),
        "active_session": serialize_session(current, now) if current else None,
        "projects": [serialize_project(item) for item in projects],
        "open_tasks": [serialize_task(item) for item in tasks],
        "stats": build_stats(db, now),
        "rewards": reward_overview(db, now),
    }


def execute_focus_tool(db: Session, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = arguments or {}
    if name == "get_focus_context":
        return focus_context(db)

    if name == "create_project":
        payload = schemas.ProjectInput(
            title=args.get("title", ""),
            outcome=args.get("outcome") or None,
            weekly_target_minutes=args.get("weekly_target_minutes", 0),
        )
        item = models.Project(**payload.model_dump())
        db.add(item)
        db.flush()
        return serialize_project(item)

    if name == "create_task":
        project_id = args.get("project_id")
        if project_id is not None:
            _must_get(db, models.Project, int(project_id), "Project")
        target = date.fromisoformat(args["target_date"]) if args.get("target_date") else _today()
        payload = schemas.TaskInput(
            project_id=project_id,
            title=args.get("title", ""),
            details=args.get("details") or None,
            estimated_minutes=args.get("estimated_minutes", 25),
            target_date=target,
            priority=args.get("priority", 3),
        )
        values = payload.model_dump(exclude={"blocked_apps"})
        item = models.Task(**values, blocked_apps_json=dump_list(payload.blocked_apps))
        db.add(item)
        db.flush()
        return serialize_task(item)

    if name == "update_task":
        item = _must_get(db, models.Task, int(args.get("task_id", 0)), "Task")
        if "project_id" in args and args["project_id"] is not None:
            _must_get(db, models.Project, int(args["project_id"]), "Project")
        for field in ("title", "details", "project_id", "estimated_minutes", "priority"):
            if field in args:
                setattr(item, field, args[field])
        if "target_date" in args:
            item.target_date = date.fromisoformat(args["target_date"])
        db.flush()
        return serialize_task(item)

    if name == "start_focus":
        task_id = args.get("task_id")
        task = _must_get(db, models.Task, int(task_id), "Task") if task_id is not None else None
        minutes = args.get("minutes", task.estimated_minutes if task else 25)
        mode = args.get("mode", "pomodoro")
        if mode == "countup":
            minutes = None
        payload = schemas.SessionStartInput(
            task_id=task.id if task else None,
            project_id=task.project_id if task else None,
            mode=mode,
            title=(task.title if task else args.get("title")) or "Free focus",
            goal=task.details if task else None,
            planned_minutes=minutes,
        )
        item = start_session(db, payload)
        db.flush()
        return serialize_session(item)

    if name == "control_focus":
        item = active_session(db)
        if not item:
            raise ValueError("There is no active focus session")
        update_session(db, item, str(args.get("action", "")))
        db.flush()
        return serialize_session(item)

    if name == "complete_task":
        item = _must_get(db, models.Task, int(args.get("task_id", 0)), "Task")
        item.status = "done"
        item.completed_at = utcnow()
        db.flush()
        return serialize_task(item)

    if name == "get_reward_status":
        return reward_overview(db)

    if name == "create_reward":
        payload = schemas.RewardInput(
            title=args.get("title", ""),
            details=args.get("details") or None,
            focus_minutes=args.get("focus_minutes", 25),
            reward_minutes=args.get("reward_minutes"),
            repeatable=args.get("repeatable", False),
        )
        item = create_reward_definition(db, payload)
        db.flush()
        return serialize_reward(item)

    if name == "select_reward":
        item = _must_get(
            db,
            models.RewardDefinition,
            int(args.get("reward_id", 0)),
            "Reward",
        )
        if not item.is_active:
            raise ValueError("That reward is no longer active")
        progress_reset = select_reward_definition(db, item)
        db.flush()
        return {"reward": serialize_reward(item), "progress_reset": progress_reset}

    if name == "redeem_reward":
        item = _must_get(
            db,
            models.RewardGrant,
            int(args.get("grant_id", 0)),
            "Reward grant",
        )
        redeem_grant(db, item)
        db.flush()
        return serialize_grant(item)

    raise ValueError(f"Unknown Focus tool: {name}")


def anthropic_tools() -> list[dict[str, Any]]:
    return TOOL_SPECS


def openai_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": item["name"],
                "description": item["description"],
                "parameters": item["input_schema"],
            },
        }
        for item in TOOL_SPECS
    ]


def openai_response_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": item["name"],
            "description": item["description"],
            "parameters": item["input_schema"],
        }
        for item in TOOL_SPECS
    ]
