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


def test_openai_responses_companion_executes_focus_tool(db, monkeypatch):
    monkeypatch.setattr(companion, "settings", SimpleNamespace(
        ai_provider="openai-responses",
        ai_model="test-model",
        ai_api_key="test-key",
        ai_base_url="",
    ))
    responses = iter([
        {
            "output": [{
                "type": "function_call",
                "call_id": "call-1",
                "name": "create_task",
                "arguments": '{"title":"Read chapter","estimated_minutes":20}',
            }],
        },
        {
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": "Task created."}],
            }],
        },
    ])
    payloads = []

    async def fake_post(*_args, **kwargs):
        payloads.append(kwargs["payload"])
        return next(responses)

    monkeypatch.setattr(companion, "_post", fake_post)
    reply, actions = asyncio.run(companion.companion_reply(db, [{"role": "user", "content": "Add it"}]))

    assert reply == "Task created."
    assert actions == [{"tool": "create_task", "success": True}]
    assert db.query(models.Task).one().title == "Read chapter"
    tool_output = payloads[1]["input"][-1]
    assert tool_output["type"] == "function_call_output"
    assert tool_output["call_id"] == "call-1"
    assert '"title": "Read chapter"' in tool_output["output"]


def test_openai_compatible_companion_executes_focus_tool(db, monkeypatch):
    monkeypatch.setattr(companion, "settings", SimpleNamespace(
        ai_provider="openai-compatible",
        ai_model="test-model",
        ai_api_key="test-key",
        ai_base_url="https://provider.example/v1",
    ))
    responses = iter([
        {
            "choices": [{"message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "tool-1",
                    "type": "function",
                    "function": {
                        "name": "create_task",
                        "arguments": '{"title":"Make outline","estimated_minutes":30}',
                    },
                }],
            }}],
        },
        {"choices": [{"message": {"role": "assistant", "content": "Task created."}}]},
    ])

    async def fake_post(*_args, **_kwargs):
        return next(responses)

    monkeypatch.setattr(companion, "_post", fake_post)
    reply, actions = asyncio.run(companion.companion_reply(db, [{"role": "user", "content": "Add it"}]))

    assert reply == "Task created."
    assert actions == [{"tool": "create_task", "success": True}]
    assert db.query(models.Task).one().title == "Make outline"
