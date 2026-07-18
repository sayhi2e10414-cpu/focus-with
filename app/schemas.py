from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class DirectionInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    goal: Optional[str] = None
    status: Literal["active", "paused", "archived"] = "active"
    weekly_target_minutes: int = Field(default=0, ge=0, le=10080)
    sort_order: int = 0


class ProjectInput(BaseModel):
    direction_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=200)
    outcome: Optional[str] = None
    notes: Optional[str] = None
    status: Literal["active", "paused", "completed", "archived"] = "active"
    weekly_target_minutes: int = Field(default=0, ge=0, le=10080)
    target_minutes: int = Field(default=0, ge=0)
    due_date: Optional[date] = None
    sort_order: int = 0


class TaskInput(BaseModel):
    project_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=240)
    details: Optional[str] = None
    status: Literal["todo", "doing", "done", "abandoned"] = "todo"
    task_scope: Literal["daily", "backlog"] = "daily"
    priority: int = Field(default=3, ge=1, le=5)
    sort_order: int = 0
    estimated_minutes: int = Field(default=25, ge=1, le=1440)
    target_date: Optional[date] = None
    blocked_apps: list[str] = Field(default_factory=list)


class ChecklistInput(BaseModel):
    content: str = Field(min_length=1, max_length=400)
    is_done: bool = False
    sort_order: int = 0


class SessionStartInput(BaseModel):
    task_id: Optional[int] = None
    project_id: Optional[int] = None
    session_kind: Literal["work", "break"] = "work"
    mode: Literal["pomodoro", "deep", "countup"] = "pomodoro"
    title: Optional[str] = None
    goal: Optional[str] = None
    planned_minutes: Optional[int] = Field(default=25, ge=0, le=1440)


class SessionUpdateInput(BaseModel):
    action: Literal["pause", "resume", "complete", "cancel"]
    note: Optional[str] = None


class PolicyInput(BaseModel):
    blocked_apps: list[str] = Field(default_factory=list)
    grace_seconds: int = Field(default=90, ge=15, le=3600)
    strikes_for_punishment: int = Field(default=3, ge=1, le=20)
    reminder_cooldown_seconds: int = Field(default=300, ge=30, le=86400)
    punishment_pool: list[str] = Field(default_factory=list)


class PhoneEventInput(BaseModel):
    app_name: str = Field(min_length=1, max_length=120)
    event_type: Literal["opened", "closed", "toggle"] = "toggle"
    device_id: str = Field(default="iphone", min_length=1, max_length=80)
    source: str = Field(default="shortcut", max_length=40)
    occurred_at: Optional[datetime] = None


class NotificationActionInput(BaseModel):
    action: Literal["complete", "repeat", "break", "resume", "dismiss"]


class CompanionMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class CompanionChatInput(BaseModel):
    messages: list[CompanionMessage] = Field(min_length=1, max_length=40)


class PlanImportInput(BaseModel):
    markdown: str = Field(min_length=1, max_length=50000)
    project_id: Optional[int] = None
    target_date: Optional[date] = None


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
