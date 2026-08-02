from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from .. import models, schemas
from .core import (
    active_policy,
    active_session,
    create_notification,
    json_value,
    record_event,
    utcnow,
)


DEFAULT_REWARD = {
    "title": "10-minute free break",
    "details": "A guilt-free ten-minute break after one uninterrupted focus block.",
    "focus_minutes": 25,
    "reward_minutes": 10,
    "repeatable": False,
    "template_key": "free_break_10",
}


def _normal_time(value: Optional[datetime], now: datetime) -> datetime:
    if value and value.tzinfo:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    value = value or now
    return now if abs((value - now).total_seconds()) > 300 else value


def ensure_reward_defaults(db: Session) -> models.RewardSettings:
    settings = db.get(models.RewardSettings, 1)
    if settings:
        return settings
    reward = models.RewardDefinition(**DEFAULT_REWARD)
    db.add(reward)
    db.flush()
    settings = models.RewardSettings(
        id=1,
        selected_reward_id=reward.id,
        defaults_seeded=True,
        camera_heartbeat_timeout_seconds=75,
    )
    db.add(settings)
    db.flush()
    return settings


def serialize_reward(item: models.RewardDefinition) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "details": item.details,
        "focus_minutes": item.focus_minutes,
        "reward_minutes": item.reward_minutes,
        "repeatable": bool(item.repeatable),
        "is_active": bool(item.is_active),
        "template_key": item.template_key,
        "sort_order": item.sort_order or 0,
    }


def serialize_grant(item: models.RewardGrant) -> dict:
    return {
        "id": item.id,
        "reward_id": item.reward_id,
        "session_id": item.session_id,
        "title": item.title_snapshot,
        "details": item.details_snapshot,
        "focus_minutes": item.focus_minutes,
        "reward_minutes": item.reward_minutes,
        "evidence_mode": item.evidence_mode,
        "status": item.status,
        "earned_at": item.earned_at.isoformat(),
        "redeemed_at": item.redeemed_at.isoformat() if item.redeemed_at else None,
    }


def _configured_blocklist(db: Session, session: models.FocusSession) -> list[str]:
    task = db.get(models.Task, session.task_id) if session.task_id else None
    task_apps = json_value(task.blocked_apps_json, []) if task else []
    return task_apps or json_value(active_policy(db).blocked_apps_json, [])


def evidence_mode(
    db: Session,
    session: models.FocusSession,
    progress: models.RewardProgress,
    now: datetime,
) -> str:
    settings = ensure_reward_defaults(db)
    timeout = max(45, int(settings.camera_heartbeat_timeout_seconds or 75))
    if (
        progress.last_camera_heartbeat_at
        and now - progress.last_camera_heartbeat_at <= timedelta(seconds=timeout)
    ):
        return "camera_verified"
    return "timer_guarded" if _configured_blocklist(db, session) else "timer_only"


def ensure_reward_progress(
    db: Session,
    session: models.FocusSession,
    now: Optional[datetime] = None,
) -> models.RewardProgress:
    now = now or utcnow()
    progress = (
        db.query(models.RewardProgress)
        .filter(models.RewardProgress.session_id == session.id)
        .first()
    )
    if progress:
        return progress
    settings = ensure_reward_defaults(db)
    reward = db.get(models.RewardDefinition, settings.selected_reward_id)
    progress = models.RewardProgress(
        session_id=session.id,
        reward_id=reward.id if reward and reward.is_active else None,
        segment_number=1,
        continuous_seconds=0,
        last_accounted_at=now,
    )
    db.add(progress)
    db.flush()
    return progress


def _award_due_grants(
    db: Session,
    session: models.FocusSession,
    progress: models.RewardProgress,
    now: datetime,
) -> list[models.RewardGrant]:
    reward = db.get(models.RewardDefinition, progress.reward_id) if progress.reward_id else None
    if not reward or not reward.is_active:
        return []
    threshold = max(5, int(reward.focus_minutes or 25)) * 60
    earned_cycles = progress.continuous_seconds // threshold
    if not reward.repeatable:
        earned_cycles = min(earned_cycles, 1)
    if earned_cycles < 1:
        return []
    existing = {
        row.cycle_number
        for row in db.query(models.RewardGrant)
        .filter(
            models.RewardGrant.reward_id == reward.id,
            models.RewardGrant.session_id == session.id,
            models.RewardGrant.segment_number == progress.segment_number,
        )
        .all()
    }
    created: list[models.RewardGrant] = []
    for cycle in range(1, earned_cycles + 1):
        if cycle in existing:
            continue
        mode = evidence_mode(db, session, progress, now)
        grant = models.RewardGrant(
            reward_id=reward.id,
            session_id=session.id,
            segment_number=progress.segment_number,
            cycle_number=cycle,
            title_snapshot=reward.title,
            details_snapshot=reward.details,
            focus_minutes=reward.focus_minutes,
            reward_minutes=reward.reward_minutes,
            evidence_mode=mode,
            status="available",
            earned_at=now,
        )
        db.add(grant)
        db.flush()
        event = record_event(
            db,
            "reward_earned",
            session=session,
            dedupe_key=(
                f"reward-earned:{reward.id}:{session.id}:"
                f"{progress.segment_number}:{cycle}"
            ),
            payload={
                "reward_id": reward.id,
                "grant_id": grant.id,
                "focus_minutes": reward.focus_minutes,
                "evidence_mode": mode,
            },
        )
        create_notification(
            db,
            event,
            kind="reward_earned",
            title="Reward unlocked",
            body=f"You earned: {reward.title}.",
        )
        created.append(grant)
    return created


def process_reward_progress(
    db: Session,
    session: models.FocusSession,
    now: Optional[datetime] = None,
) -> models.RewardProgress:
    now = now or utcnow()
    progress = ensure_reward_progress(db, session, now)
    if session.session_kind == "break" or session.status != "running":
        progress.last_accounted_at = now
        return progress
    if now > progress.last_accounted_at:
        progress.continuous_seconds += max(
            0,
            int((now - progress.last_accounted_at).total_seconds()),
        )
        progress.last_accounted_at = now
    _award_due_grants(db, session, progress, now)
    return progress


def freeze_reward_progress(
    db: Session,
    session: models.FocusSession,
    now: Optional[datetime] = None,
) -> models.RewardProgress:
    now = now or utcnow()
    progress = process_reward_progress(db, session, now)
    progress.last_accounted_at = now
    return progress


def resume_reward_progress(
    db: Session,
    session: models.FocusSession,
    now: Optional[datetime] = None,
) -> models.RewardProgress:
    progress = ensure_reward_progress(db, session, now)
    progress.last_accounted_at = now or utcnow()
    return progress


def interrupt_reward_progress(
    db: Session,
    session: models.FocusSession,
    interruption_key: str,
    at: Optional[datetime] = None,
) -> bool:
    at = at or utcnow()
    progress = ensure_reward_progress(db, session, at)
    if progress.last_interruption_key == interruption_key:
        return False
    process_reward_progress(db, session, at)
    progress.segment_number += 1
    progress.continuous_seconds = 0
    progress.last_accounted_at = at
    progress.last_interruption_key = interruption_key[:160]
    record_event(
        db,
        "reward_progress_interrupted",
        session=session,
        dedupe_key=f"reward-interruption:{interruption_key}"[:160],
        payload={"segment_number": progress.segment_number},
    )
    return True


def record_camera_heartbeat(
    db: Session,
    values: schemas.CameraHeartbeatInput,
    now: Optional[datetime] = None,
) -> dict:
    now = now or utcnow()
    observed_at = _normal_time(values.observed_at, now)
    session = active_session(db)
    if not session or session.status != "running" or session.session_kind == "break":
        return {"accepted": False, "reason": "no_running_focus", "progress": None}
    progress = process_reward_progress(db, session, observed_at)
    if values.camera_state == "observing":
        if not progress.last_camera_heartbeat_at or observed_at >= progress.last_camera_heartbeat_at:
            progress.last_camera_heartbeat_at = observed_at
            progress.camera_source = values.source
    elif not progress.camera_source or progress.camera_source == values.source:
        progress.last_camera_heartbeat_at = None
        progress.camera_source = None
    return {
        "accepted": True,
        "reason": values.camera_state,
        "progress": serialize_progress(db, session, progress, now),
    }


def serialize_progress(
    db: Session,
    session: models.FocusSession,
    progress: models.RewardProgress,
    now: Optional[datetime] = None,
) -> dict:
    now = now or utcnow()
    reward = db.get(models.RewardDefinition, progress.reward_id) if progress.reward_id else None
    target_seconds = int(reward.focus_minutes) * 60 if reward and reward.is_active else 0
    cycle_seconds = progress.continuous_seconds
    if reward and reward.repeatable and target_seconds:
        cycle_seconds %= target_seconds
    return {
        "session_id": session.id,
        "reward_id": reward.id if reward and reward.is_active else None,
        "segment_number": progress.segment_number,
        "continuous_seconds": progress.continuous_seconds,
        "cycle_seconds": cycle_seconds,
        "target_seconds": target_seconds,
        "remaining_seconds": max(0, target_seconds - cycle_seconds) if target_seconds else 0,
        "evidence_mode": evidence_mode(db, session, progress, now),
        "camera_source": progress.camera_source,
        "camera_last_seen_at": (
            progress.last_camera_heartbeat_at.isoformat()
            if progress.last_camera_heartbeat_at
            else None
        ),
        "reward": serialize_reward(reward) if reward and reward.is_active else None,
    }


def reward_overview(db: Session, now: Optional[datetime] = None) -> dict:
    now = now or utcnow()
    settings = ensure_reward_defaults(db)
    session = active_session(db)
    progress_data = None
    if session and session.session_kind != "break":
        progress = process_reward_progress(db, session, now)
        progress_data = serialize_progress(db, session, progress, now)
    rewards = (
        db.query(models.RewardDefinition)
        .filter(models.RewardDefinition.is_active.is_(True))
        .order_by(models.RewardDefinition.sort_order, models.RewardDefinition.id)
        .all()
    )
    grants = (
        db.query(models.RewardGrant)
        .order_by(models.RewardGrant.earned_at.desc(), models.RewardGrant.id.desc())
        .limit(100)
        .all()
    )
    available_counts: dict[int, int] = {}
    for grant in grants:
        if grant.status == "available" and grant.reward_id:
            available_counts[grant.reward_id] = available_counts.get(grant.reward_id, 0) + 1
    return {
        "selected_reward_id": settings.selected_reward_id,
        "catalog": [
            {**serialize_reward(reward), "available_count": available_counts.get(reward.id, 0)}
            for reward in rewards
        ],
        "progress": progress_data,
        "grants": [serialize_grant(grant) for grant in grants],
        "available_count": sum(1 for grant in grants if grant.status == "available"),
    }


def create_reward(db: Session, values: schemas.RewardInput) -> models.RewardDefinition:
    ensure_reward_defaults(db)
    reward = models.RewardDefinition(
        title=values.title.strip(),
        details=(values.details or "").strip() or None,
        focus_minutes=values.focus_minutes,
        reward_minutes=values.reward_minutes,
        repeatable=values.repeatable,
        sort_order=values.sort_order,
    )
    db.add(reward)
    db.flush()
    return reward


def update_reward(
    db: Session,
    reward: models.RewardDefinition,
    values: schemas.RewardInput,
) -> models.RewardDefinition:
    reward.title = values.title.strip()
    reward.details = (values.details or "").strip() or None
    reward.focus_minutes = values.focus_minutes
    reward.reward_minutes = values.reward_minutes
    reward.repeatable = values.repeatable
    reward.sort_order = values.sort_order
    reward.template_key = None
    db.flush()
    return reward


def select_reward(db: Session, reward: models.RewardDefinition, now: Optional[datetime] = None) -> bool:
    now = now or utcnow()
    settings = ensure_reward_defaults(db)
    settings.selected_reward_id = reward.id
    reset = False
    session = active_session(db)
    if session and session.session_kind != "break":
        progress = process_reward_progress(db, session, now)
        if progress.reward_id != reward.id:
            progress.reward_id = reward.id
            progress.segment_number += 1
            progress.continuous_seconds = 0
            progress.last_accounted_at = now
            progress.last_interruption_key = f"reward-selected:{reward.id}:{progress.segment_number}"
            reset = True
    return reset


def archive_reward(db: Session, reward: models.RewardDefinition, now: Optional[datetime] = None) -> None:
    reward.is_active = False
    settings = ensure_reward_defaults(db)
    if settings.selected_reward_id == reward.id:
        settings.selected_reward_id = None
    session = active_session(db)
    if session:
        progress = ensure_reward_progress(db, session, now)
        if progress.reward_id == reward.id:
            progress.reward_id = None
            progress.continuous_seconds = 0
            progress.segment_number += 1
            progress.last_accounted_at = now or utcnow()


def redeem_grant(
    db: Session,
    grant: models.RewardGrant,
    now: Optional[datetime] = None,
) -> models.RewardGrant:
    if grant.status != "available":
        raise ValueError("This reward has already been redeemed")
    grant.status = "redeemed"
    grant.redeemed_at = now or utcnow()
    record_event(
        db,
        "reward_redeemed",
        session=db.get(models.FocusSession, grant.session_id),
        dedupe_key=f"reward-redeemed:{grant.id}",
        payload={"reward_id": grant.reward_id, "grant_id": grant.id},
    )
    return grant
