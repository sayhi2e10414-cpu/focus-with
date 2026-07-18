from __future__ import annotations

import asyncio

from fastapi import FastAPI
import httpx

from app.config import settings
from app.database import get_db
from app.routes.api import router


def test_project_task_and_bootstrap_api(db):
    test_app = FastAPI()
    test_app.include_router(router)

    def override_db():
        yield db

    test_app.dependency_overrides[get_db] = override_db
    headers = {"X-Focus-Token": settings.api_token} if settings.api_token else {}

    async def exercise_api():
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project_response = await client.post("/api/projects", headers=headers, json={
                "title": "Write first release",
                "outcome": "A clean public repository",
                "weekly_target_minutes": 120,
            })
            assert project_response.status_code == 200
            project_id = project_response.json()["data"]["id"]

            task_response = await client.post("/api/tasks", headers=headers, json={
                "project_id": project_id,
                "title": "Write installation guide",
                "estimated_minutes": 30,
            })
            assert task_response.status_code == 200

            bootstrap = await client.get("/api/bootstrap", headers=headers)
            assert bootstrap.status_code == 200
            data = bootstrap.json()["data"]
            assert data["projects"][0]["title"] == "Write first release"
            assert data["tasks"][0]["project_id"] == project_id

            imported = await client.post("/api/plans/import", headers=headers, json={
                "project_id": project_id,
                "markdown": "1. **Read overview** | 20 min\n2. **Break** | 10 min\n3. **Make outline** | 35 min",
            })
            assert imported.status_code == 200
            imported_data = imported.json()["data"]
            assert [item["title"] for item in imported_data["tasks"]] == ["Read overview", "Make outline"]
            assert imported_data["breaks"][0]["title"] == "Break"

    asyncio.run(exercise_api())
