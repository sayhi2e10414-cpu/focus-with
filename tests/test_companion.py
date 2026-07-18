from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app import models
from app.services import companion


def test_anthropic_companion_executes_focus_tool(db, monkeypatch):
    monkeypatch.setattr(companion, "settings", SimpleNamespace(
        ai_provider="anthropic",
        ai_model="test-model",
        ai_api_key="test-key",
        ai_base_url="",
    ))
    responses = iter([
        {
            "content": [{
                "type": "tool_use",
                "id": "tool-1",
                "name": "create_task",
                "input": {"title": "Read chapter", "estimated_minutes": 20},
            }],
        },
        {"content": [{"type": "text", "text": "Task created."}]},
    ])

    async def fake_post(*_args, **_kwargs):
        return next(responses)

    monkeypatch.setattr(companion, "_post", fake_post)
    reply, actions = asyncio.run(companion.companion_reply(db, [{"role": "user", "content": "Add a reading task"}]))

    assert reply == "Task created."
    assert actions == [{"tool": "create_task", "success": True}]
    assert db.query(models.Task).one().title == "Read chapter"
