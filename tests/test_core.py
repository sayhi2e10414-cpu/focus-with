from __future__ import annotations

from datetime import timedelta

from app import models, schemas
from app.services.core import (
    active_policy,
    apply_notification_action,
    build_stats,
    finish_due_timer,
    observe_distraction,
    phone_usage_for_date,
    record_phone_event,
    start_session,
    utcnow,
)
from app.services.focus_tools import execute_focus_tool


def test_focus_tools_create_group_and_start(db):
    project = execute_focus_tool(db, "create_project", {"title": "Exam", "outcome": "Finish review"})
    task = execute_focus_tool(db, "create_task", {
        "title": "Review sentencing",
        "project_id": project["id"],
        "estimated_minutes": 40,
    })
    session = execute_focus_tool(db, "start_focus", {"task_id": task["id"]})

    assert session["status"] == "running"
    assert session["planned_minutes"] == 40
    context = execute_focus_tool(db, "get_focus_context")
    assert context["projects"][0]["title"] == "Exam"
    assert context["open_tasks"][0]["project_id"] == project["id"]


def test_timer_completion_is_idempotent(db):
    item = start_session(db, schemas.SessionStartInput(title="Read", planned_minutes=25))
    now = utcnow()
    item.last_resumed_at = now - timedelta(minutes=26)

    assert finish_due_timer(db, item, now) is True
    assert finish_due_timer(db, item, now + timedelta(seconds=5)) is False
    assert item.status == "completed"
    assert db.query(models.Notification).count() == 1
    assert db.query(models.FocusEvent).filter_by(event_type="session_completed").count() == 1


def test_timer_notification_action_repeats_once(db):
    item = start_session(db, schemas.SessionStartInput(title="Read", planned_minutes=25))
    now = utcnow()
    item.last_resumed_at = now - timedelta(minutes=26)
    finish_due_timer(db, item, now)
    notification = db.query(models.Notification).one()

    result = apply_notification_action(db, notification, "repeat")
    assert result["session"]["status"] == "running"
    assert result["session"]["id"] != item.id
    assert apply_notification_action(db, notification, "repeat") == {"status": "already_handled"}


def test_same_task_sessions_are_merged_in_statistics(db):
    task = models.Task(title="Outline chapter", estimated_minutes=25, status="doing")
    db.add(task)
    db.flush()
    now = utcnow()
    db.add_all([
        models.FocusSession(task_id=task.id, title=task.title, session_kind="work", status="completed", elapsed_seconds=900, started_at=now),
        models.FocusSession(task_id=task.id, title=task.title, session_kind="work", status="completed", elapsed_seconds=600, started_at=now),
    ])
    db.flush()

    activity = build_stats(db, now)["today"]["by_activity"]
    assert len(activity) == 1
    assert activity[0]["focus_seconds"] == 1500
    assert activity[0]["session_count"] == 2


def test_distraction_counts_each_distinct_open_once(db):
    now = utcnow()
    policy = active_policy(db)
    policy.blocked_apps_json = '["Xiaohongshu"]'
    policy.grace_seconds = 15
    policy.reminder_cooldown_seconds = 30
    task = models.Task(title="Study", estimated_minutes=25, status="doing")
    db.add(task)
    db.flush()
    session = start_session(db, schemas.SessionStartInput(task_id=task.id, planned_minutes=25))

    first = record_phone_event(db, schemas.PhoneEventInput(
        app_name="Xiaohongshu", event_type="opened", occurred_at=now - timedelta(seconds=20)
    ))
    assert observe_distraction(db, session, now) is True
    assert observe_distraction(db, session, now + timedelta(seconds=1)) is False
    assert db.query(models.Intervention).count() == 1
    assert db.query(models.Intervention).one().phone_open_event_id == first.id

    record_phone_event(db, schemas.PhoneEventInput(
        app_name="Xiaohongshu", event_type="closed", occurred_at=now + timedelta(seconds=2)
    ))
    observe_distraction(db, session, now + timedelta(seconds=2))
    second = record_phone_event(db, schemas.PhoneEventInput(
        app_name="Xiaohongshu", event_type="opened", occurred_at=now + timedelta(seconds=33)
    ))
    assert observe_distraction(db, session, now + timedelta(seconds=50)) is True
    rows = db.query(models.Intervention).order_by(models.Intervention.id).all()
    assert len(rows) == 2
    assert rows[1].phone_open_event_id == second.id
    assert rows[1].strike_number == 2


def test_phone_usage_events_exist_without_active_focus(db):
    now = utcnow()
    event = record_phone_event(db, schemas.PhoneEventInput(app_name="Xiaohongshu", event_type="opened", occurred_at=now - timedelta(minutes=12)))
    record_phone_event(db, schemas.PhoneEventInput(app_name="Xiaohongshu", event_type="closed", occurred_at=now))
    db.commit()
    assert event.id is not None
    assert db.query(models.PhoneAppEvent).count() == 2
    assert db.query(models.Intervention).count() == 0
    usage = phone_usage_for_date(db, now.date(), now=now)
    assert usage["apps"][0]["seconds"] == 12 * 60
