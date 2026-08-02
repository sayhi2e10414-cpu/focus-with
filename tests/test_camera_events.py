from __future__ import annotations

import asyncio
from datetime import timedelta

from fastapi import FastAPI
import httpx

from app import models, schemas
from app.config import settings
from app.database import get_db
from app.routes.api import router
from app.services.core import (
    active_policy,
    record_camera_phone_distraction,
    start_session,
    utcnow,
)


def test_camera_event_is_private_idempotent_and_uses_focus_notifications(db):
    now = utcnow()
    policy = active_policy(db)
    policy.reminder_cooldown_seconds = 30
    task = models.Task(title="Read chapter", estimated_minutes=25, status="doing")
    db.add(task)
    db.flush()
    start_session(db, schemas.SessionStartInput(task_id=task.id, planned_minutes=25))
    payload = schemas.CameraPhoneEventInput(
        event_id="camera-event-001",
        duration_seconds=10,
        detected_at=now,
        source="macos_focus_float",
    )

    first = record_camera_phone_distraction(db, payload, now)
    duplicate = record_camera_phone_distraction(db, payload, now + timedelta(seconds=1))

    assert first["accepted"] is True
    assert duplicate["accepted"] is True
    assert duplicate["reason"] == "duplicate"
    assert db.query(models.Intervention).count() == 1
    assert db.query(models.Notification).count() == 1
    intervention = db.query(models.Intervention).one()
    assert intervention.phone_open_event_id is None
    assert intervention.source_type == "camera_phone"
    assert intervention.duration_seconds == 10
    event = (
        db.query(models.FocusEvent)
        .filter(models.FocusEvent.event_type == "distraction_warning")
        .one()
    )
    assert "camera-event-001" not in event.payload_json
    assert "confidence" not in event.payload_json
    assert "bounding" not in event.payload_json


def test_camera_event_respects_session_and_server_cooldown(db):
    now = utcnow()
    no_session = record_camera_phone_distraction(
        db,
        schemas.CameraPhoneEventInput(event_id="camera-event-none", duration_seconds=10),
        now,
    )
    assert no_session["reason"] == "no_running_focus"
    assert db.query(models.Intervention).count() == 0

    policy = active_policy(db)
    policy.reminder_cooldown_seconds = 30
    start_session(db, schemas.SessionStartInput(title="Write", planned_minutes=25))
    first = record_camera_phone_distraction(
        db,
        schemas.CameraPhoneEventInput(event_id="camera-event-101", duration_seconds=10),
        now,
    )
    suppressed = record_camera_phone_distraction(
        db,
        schemas.CameraPhoneEventInput(event_id="camera-event-102", duration_seconds=10),
        now + timedelta(seconds=10),
    )
    second = record_camera_phone_distraction(
        db,
        schemas.CameraPhoneEventInput(event_id="camera-event-103", duration_seconds=10),
        now + timedelta(seconds=31),
    )

    assert first["strike"] == 1
    assert suppressed["reason"] == "cooldown"
    assert second["accepted"] is True
    assert second["strike"] == 2
    assert db.query(models.Notification).count() == 2


def test_camera_endpoint_rejects_image_fields(db):
    test_app = FastAPI()
    test_app.include_router(router)

    def override_db():
        yield db

    test_app.dependency_overrides[get_db] = override_db
    headers = {"X-Focus-Token": settings.api_token} if settings.api_token else {}

    async def exercise_api():
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/vision-events/phone",
                headers=headers,
                json={
                    "event_id": "camera-event-private",
                    "duration_seconds": 10,
                    "source": "macos_focus_float",
                    "image": "not-allowed",
                },
            )
            assert response.status_code == 422

    asyncio.run(exercise_api())
