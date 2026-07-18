from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Direction(Base):
    __tablename__ = "directions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160), index=True)
    goal: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    weekly_target_minutes: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    projects: Mapped[list["Project"]] = relationship(back_populates="direction")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    direction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("directions.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    outcome: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    weekly_target_minutes: Mapped[int] = mapped_column(Integer, default=0)
    target_minutes: Mapped[int] = mapped_column(Integer, default=0)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    direction: Mapped[Optional[Direction]] = relationship(back_populates="projects")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    details: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="todo", index=True)
    task_scope: Mapped[str] = mapped_column(String(24), default="daily")
    priority: Mapped[int] = mapped_column(Integer, default=3)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=25)
    target_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    blocked_apps_json: Mapped[str] = mapped_column(Text, default="[]")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project: Mapped[Optional[Project]] = relationship(back_populates="tasks")
    checklist: Mapped[list["ChecklistItem"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    content: Mapped[str] = mapped_column(String(400))
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task: Mapped[Task] = relationship(back_populates="checklist")


class FocusSession(Base):
    __tablename__ = "focus_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), index=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), index=True)
    session_kind: Mapped[str] = mapped_column(String(16), default="work")
    mode: Mapped[str] = mapped_column(String(24), default="pomodoro")
    title: Mapped[Optional[str]] = mapped_column(String(240))
    goal: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)
    planned_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    elapsed_seconds: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="planned", index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_resumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    timer_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FocusPolicy(Base):
    __tablename__ = "focus_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Default")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    blocked_apps_json: Mapped[str] = mapped_column(Text, default="[]")
    grace_seconds: Mapped[int] = mapped_column(Integer, default=90)
    strikes_for_punishment: Mapped[int] = mapped_column(Integer, default=3)
    reminder_cooldown_seconds: Mapped[int] = mapped_column(Integer, default=300)
    punishment_pool_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PhoneAppEvent(Base):
    __tablename__ = "phone_app_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(80), default="iphone", index=True)
    app_name: Mapped[str] = mapped_column(String(120), index=True)
    event_type: Mapped[str] = mapped_column(String(16), index=True)
    source: Mapped[str] = mapped_column(String(40), default="shortcut")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Intervention(Base):
    __tablename__ = "interventions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("focus_sessions.id"), index=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), index=True)
    phone_open_event_id: Mapped[int] = mapped_column(ForeignKey("phone_app_events.id"), unique=True, index=True)
    app_name: Mapped[str] = mapped_column(String(120), index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    strike_number: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="observing", index=True)
    message: Mapped[Optional[str]] = mapped_column(Text)
    punishment: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FocusEvent(Base):
    __tablename__ = "focus_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("focus_sessions.id"), index=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(160), unique=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("focus_events.id"), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(48), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    actions_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class OAuthClient(Base):
    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    data_json: Mapped[str] = mapped_column(Text)
    created_at_epoch: Mapped[int] = mapped_column(Integer, index=True)


class OAuthLoginRequest(Base):
    __tablename__ = "oauth_login_requests"

    ticket_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    client_id: Mapped[str] = mapped_column(String(160), index=True)
    oauth_state: Mapped[Optional[str]] = mapped_column(Text)
    redirect_uri: Mapped[str] = mapped_column(Text)
    redirect_uri_explicit: Mapped[bool] = mapped_column(Boolean, default=True)
    code_challenge: Mapped[str] = mapped_column(String(160))
    scopes_json: Mapped[str] = mapped_column(Text)
    resource: Mapped[str] = mapped_column(Text)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at_epoch: Mapped[int] = mapped_column(Integer, index=True)
    used_at_epoch: Mapped[Optional[int]] = mapped_column(Integer)


class OAuthAuthorizationCodeRecord(Base):
    __tablename__ = "oauth_authorization_codes"

    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(160), index=True)
    redirect_uri: Mapped[str] = mapped_column(Text)
    redirect_uri_explicit: Mapped[bool] = mapped_column(Boolean, default=True)
    code_challenge: Mapped[str] = mapped_column(String(160))
    scopes_json: Mapped[str] = mapped_column(Text)
    resource: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(160), default="owner")
    expires_at_epoch: Mapped[int] = mapped_column(Integer, index=True)
    used_at_epoch: Mapped[Optional[int]] = mapped_column(Integer)


class OAuthLoginFailure(Base):
    __tablename__ = "oauth_login_failures"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at_epoch: Mapped[int] = mapped_column(Integer, index=True)


class OAuthTokenRecord(Base):
    __tablename__ = "oauth_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_type: Mapped[str] = mapped_column(String(16), index=True)
    client_id: Mapped[str] = mapped_column(String(160), index=True)
    scopes_json: Mapped[str] = mapped_column(Text)
    resource: Mapped[Optional[str]] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(160), default="owner")
    family_id: Mapped[str] = mapped_column(String(80), index=True)
    created_at_epoch: Mapped[int] = mapped_column(Integer, index=True)
    expires_at_epoch: Mapped[int] = mapped_column(Integer, index=True)
    revoked_at_epoch: Mapped[Optional[int]] = mapped_column(Integer, index=True)
