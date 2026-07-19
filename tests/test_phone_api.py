from __future__ import annotations

import asyncio

from fastapi import FastAPI
import httpx

from app import models
from app.config import settings
from app.database import get_db
from app.routes.phone import router
from app.services.core import utcnow


def test_phone_scoped_focus_state(db):
    task = models.Task(title="Read chapter", estimated_minutes=25, status="doing")
    db.add(task)
    db.flush()
    db.add(models.FocusSession(
        task_id=task.id,
        title=task.title,
        mode="pomodoro",
        status="running",
        planned_minutes=25,
        started_at=utcnow(),
        last_resumed_at=utcnow(),
    ))
    db.commit()

    test_app = FastAPI()
    test_app.include_router(router)

    def override_db():
        yield db

    test_app.dependency_overrides[get_db] = override_db
    headers = {"X-Focus-Phone-Token": settings.phone_token} if settings.phone_token else {}

    async def exercise():
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/phone/focus", headers=headers)
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["active_session"]["title"] == "Read chapter"
            assert data["active_session"]["status"] == "running"
            assert "projects" not in data
            assert "tasks" not in data

    asyncio.run(exercise())
