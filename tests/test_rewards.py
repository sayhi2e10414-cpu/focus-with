from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from fastapi import FastAPI
import httpx

from app import models, schemas
from app.config import settings
from app.database import get_db
from app.routes.api import router
from app.services.core import active_policy, record_camera_phone_distraction, start_session
from app.services.rewards import (
    ensure_reward_defaults,
    interrupt_reward_progress,
    process_reward_progress,
    record_camera_heartbeat,
    redeem_grant,
    reward_overview,
    select_reward,
)
from app.services.focus_tools import execute_focus_tool


BASE = datetime(2026, 8, 2, 10, 0, 0)


def _start_reward_session(db):
    ensure_reward_defaults(db)
    session = start_session(
        db,
        schemas.SessionStartInput(title="Write", planned_minutes=90),
    )
    progress = db.query(models.RewardProgress).filter_by(session_id=session.id).one()
    progress.last_accounted_at = BASE
    session.started_at = BASE
    session.last_resumed_at = BASE
    return session, progress


def test_default_reward_is_seeded_once_and_selected(db):
    first = reward_overview(db, BASE)
    second = reward_overview(db, BASE)

    assert len(first["catalog"]) == 1
    assert first["catalog"][0]["template_key"] == "free_break_10"
    assert first["catalog"][0]["focus_minutes"] == 25
    assert first["catalog"][0]["reward_minutes"] == 10
    assert first["selected_reward_id"] == first["catalog"][0]["id"]
    assert len(second["catalog"]) == 1


def test_uninterrupted_progress_awards_once_and_preserves_inventory(db):
    session, progress = _start_reward_session(db)

    process_reward_progress(db, session, BASE + timedelta(seconds=1499))
    assert db.query(models.RewardGrant).count() == 0
    process_reward_progress(db, session, BASE + timedelta(seconds=1500))
    process_reward_progress(db, session, BASE + timedelta(seconds=1510))

    grant = db.query(models.RewardGrant).one()
    assert grant.status == "available"
    assert grant.evidence_mode == "timer_only"
    assert progress.continuous_seconds == 1510

    interrupt_reward_progress(
        db,
        session,
        "camera:test-interruption",
        BASE + timedelta(seconds=1520),
    )
    assert progress.continuous_seconds == 0
    assert progress.segment_number == 2
    assert db.query(models.RewardGrant).one().status == "available"

    redeem_grant(db, grant, BASE + timedelta(seconds=1530))
    assert grant.status == "redeemed"
    assert grant.redeemed_at == BASE + timedelta(seconds=1530)


def test_camera_heartbeat_upgrades_then_safely_falls_back(db):
    session, progress = _start_reward_session(db)

    result = record_camera_heartbeat(
        db,
        schemas.CameraHeartbeatInput(
            observed_at=BASE + timedelta(seconds=1),
            source="macos_focus_float",
            camera_state="observing",
        ),
        BASE + timedelta(seconds=1),
    )
    assert result["accepted"] is True
    assert result["progress"]["evidence_mode"] == "camera_verified"

    overview = reward_overview(db, BASE + timedelta(seconds=77))
    assert overview["progress"]["evidence_mode"] == "timer_only"

    active_policy(db).blocked_apps_json = '["TikTok"]'
    overview = reward_overview(db, BASE + timedelta(seconds=78))
    assert overview["progress"]["evidence_mode"] == "timer_guarded"

    stopped = record_camera_heartbeat(
        db,
        schemas.CameraHeartbeatInput(
            observed_at=BASE + timedelta(seconds=79),
            source="macos_focus_float",
            camera_state="stopped",
        ),
        BASE + timedelta(seconds=79),
    )
    assert stopped["progress"]["evidence_mode"] == "timer_guarded"
    assert progress.last_camera_heartbeat_at is None
    assert session.status == "running"


def test_camera_phone_event_resets_progress_even_during_reminder_cooldown(db):
    session, progress = _start_reward_session(db)
    process_reward_progress(db, session, BASE + timedelta(minutes=5))
    policy = active_policy(db)
    policy.reminder_cooldown_seconds = 300

    first = record_camera_phone_distraction(
        db,
        schemas.CameraPhoneEventInput(
            event_id="reward-camera-001",
            duration_seconds=10,
            detected_at=BASE + timedelta(minutes=5),
        ),
        BASE + timedelta(minutes=5),
    )
    process_reward_progress(db, session, BASE + timedelta(minutes=6))
    second = record_camera_phone_distraction(
        db,
        schemas.CameraPhoneEventInput(
            event_id="reward-camera-002",
            duration_seconds=10,
            detected_at=BASE + timedelta(minutes=6),
        ),
        BASE + timedelta(minutes=6),
    )

    assert first["accepted"] is True
    assert second["reason"] == "cooldown"
    assert progress.segment_number == 3
    assert progress.continuous_seconds == 0


def test_selecting_a_new_target_resets_only_the_current_segment(db):
    session, progress = _start_reward_session(db)
    process_reward_progress(db, session, BASE + timedelta(minutes=5))
    reward = models.RewardDefinition(
        title="Tea",
        focus_minutes=10,
        reward_minutes=None,
        repeatable=False,
        is_active=True,
    )
    db.add(reward)
    db.flush()

    reset = select_reward(db, reward, BASE + timedelta(minutes=5))

    assert reset is True
    assert progress.reward_id == reward.id
    assert progress.continuous_seconds == 0
    assert progress.segment_number == 2


def test_reward_and_heartbeat_api_reject_image_derived_fields(db):
    test_app = FastAPI()
    test_app.include_router(router)

    def override_db():
        yield db

    test_app.dependency_overrides[get_db] = override_db
    headers = {"X-Focus-Token": settings.api_token} if settings.api_token else {}

    async def exercise_api():
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/rewards",
                headers=headers,
                json={
                    "title": "One episode",
                    "details": "Watch something fun",
                    "focus_minutes": 25,
                    "reward_minutes": 20,
                    "repeatable": False,
                    "sort_order": 2,
                },
            )
            assert created.status_code == 200
            reward_id = created.json()["data"]["id"]
            selected = await client.post(f"/api/rewards/{reward_id}/select", headers=headers)
            assert selected.status_code == 200

            heartbeat = await client.post(
                "/api/vision-events/heartbeat",
                headers=headers,
                json={
                    "source": "windows_focus_float",
                    "camera_state": "observing",
                    "image": "not-allowed",
                },
            )
            assert heartbeat.status_code == 422

    asyncio.run(exercise_api())


def test_mcp_reward_tools_create_select_query_and_redeem(db):
    session, progress = _start_reward_session(db)
    created = execute_focus_tool(
        db,
        "create_reward",
        {
            "title": "One episode",
            "details": "Watch something fun",
            "focus_minutes": 10,
            "reward_minutes": 20,
        },
    )
    selected = execute_focus_tool(db, "select_reward", {"reward_id": created["id"]})
    assert selected["progress_reset"] is True

    progress.last_accounted_at = BASE
    process_reward_progress(db, session, BASE + timedelta(minutes=10))
    status = execute_focus_tool(db, "get_reward_status")
    grant = next(
        item
        for item in status["grants"]
        if item["status"] == "available" and item["title"] == "One episode"
    )

    redeemed = execute_focus_tool(db, "redeem_reward", {"grant_id": grant["id"]})
    assert redeemed["status"] == "redeemed"
