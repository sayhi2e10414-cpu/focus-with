from __future__ import annotations

import json
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from .focus_tools import anthropic_tools, execute_focus_tool, openai_tools


class CompanionError(RuntimeError):
    pass


SYSTEM_PROMPT = """You are the user's calm Focus companion inside a private productivity app.
Help turn vague intentions into concrete projects and small tasks, choose the next task, and protect an active focus session.
Use Focus tools when the user asks you to inspect or change their Focus data. Do not claim a change happened unless a tool succeeded.
Before starting a timer, use the duration the user gave; otherwise use the task estimate. Never invent personal facts or use pet names.
Keep replies brief, warm, specific, and in the same language as the user."""


def _ensure_configured() -> None:
    if settings.ai_provider == "none":
        raise CompanionError("The AI companion is off. Set FOCUS_AI_PROVIDER, FOCUS_AI_MODEL, and the provider credentials in .env.")
    if not settings.ai_model:
        raise CompanionError("FOCUS_AI_MODEL is required when the AI companion is enabled.")
    if not settings.ai_api_key and not settings.ai_base_url:
        raise CompanionError("FOCUS_AI_API_KEY is required unless a local compatible base URL is configured.")


async def _post(url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        raise CompanionError(f"The AI provider returned {exc.response.status_code}: {detail}") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise CompanionError(f"Could not reach the AI provider: {exc}") from exc


async def _anthropic_reply(db: Session, messages: list[dict[str, str]]) -> tuple[str, list[dict[str, Any]]]:
    base = settings.ai_base_url or "https://api.anthropic.com"
    url = f"{base.rstrip('/')}/v1/messages"
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    if settings.ai_api_key:
        headers["x-api-key"] = settings.ai_api_key
    conversation: list[dict[str, Any]] = [{"role": item["role"], "content": item["content"]} for item in messages]
    actions: list[dict[str, Any]] = []

    for _ in range(6):
        result = await _post(url, headers=headers, payload={
            "model": settings.ai_model,
            "max_tokens": 1200,
            "system": SYSTEM_PROMPT,
            "messages": conversation,
            "tools": anthropic_tools(),
        })
        content = result.get("content") or []
        calls = [block for block in content if block.get("type") == "tool_use"]
        if not calls:
            text = "\n".join(block.get("text", "") for block in content if block.get("type") == "text").strip()
            return text or "Done.", actions
        conversation.append({"role": "assistant", "content": content})
        tool_results = []
        for call in calls:
            try:
                output = execute_focus_tool(db, call["name"], call.get("input") or {})
                db.flush()
                actions.append({"tool": call["name"], "success": True})
                payload = json.dumps(output, ensure_ascii=False)
                is_error = False
            except Exception as exc:
                payload = str(exc)
                is_error = True
                actions.append({"tool": call.get("name", "unknown"), "success": False, "error": payload})
            tool_results.append({"type": "tool_result", "tool_use_id": call["id"], "content": payload, "is_error": is_error})
        conversation.append({"role": "user", "content": tool_results})
    raise CompanionError("The companion used too many tool steps. Try a smaller request.")


async def _openai_reply(db: Session, messages: list[dict[str, str]]) -> tuple[str, list[dict[str, Any]]]:
    base = settings.ai_base_url or "https://api.openai.com/v1"
    url = f"{base.rstrip('/')}/chat/completions"
    headers = {"content-type": "application/json"}
    if settings.ai_api_key:
        headers["authorization"] = f"Bearer {settings.ai_api_key}"
    conversation: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
    actions: list[dict[str, Any]] = []

    for _ in range(6):
        result = await _post(url, headers=headers, payload={
            "model": settings.ai_model,
            "messages": conversation,
            "tools": openai_tools(),
            "tool_choice": "auto",
        })
        choices = result.get("choices") or []
        if not choices:
            raise CompanionError("The AI provider returned no response.")
        message = choices[0].get("message") or {}
        calls = message.get("tool_calls") or []
        if not calls:
            return (message.get("content") or "Done.").strip(), actions
        conversation.append(message)
        for call in calls:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
                output = execute_focus_tool(db, function.get("name", ""), arguments)
                db.flush()
                actions.append({"tool": function.get("name"), "success": True})
                payload = json.dumps(output, ensure_ascii=False)
            except Exception as exc:
                payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
                actions.append({"tool": function.get("name", "unknown"), "success": False, "error": str(exc)})
            conversation.append({"role": "tool", "tool_call_id": call.get("id"), "content": payload})
    raise CompanionError("The companion used too many tool steps. Try a smaller request.")


async def companion_reply(db: Session, messages: list[dict[str, str]]) -> tuple[str, list[dict[str, Any]]]:
    _ensure_configured()
    if settings.ai_provider == "anthropic":
        return await _anthropic_reply(db, messages)
    if settings.ai_provider in {"openai-compatible", "openai_compatible", "openai"}:
        return await _openai_reply(db, messages)
    raise CompanionError(f"Unsupported FOCUS_AI_PROVIDER: {settings.ai_provider}")
