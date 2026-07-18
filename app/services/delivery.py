from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from .core import apply_notification_action, json_value, utcnow


_telegram_offset = 0


def telegram_enabled() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def _telegram_url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"


def _keyboard(item: models.Notification) -> dict[str, Any] | None:
    actions = json_value(item.actions_json, [])
    buttons = [
        {"text": action.get("label", action.get("action", "Action")), "callback_data": f"focus:n:{item.id}:{action.get('action')}"}
        for action in actions
        if action.get("action")
    ]
    return {"inline_keyboard": [[button] for button in buttons]} if buttons else None


async def deliver_pending_telegram(db: Session) -> int:
    if not telegram_enabled():
        return 0
    rows = (
        db.query(models.Notification)
        .filter(models.Notification.status == "pending", models.Notification.delivered_at.is_(None))
        .order_by(models.Notification.id)
        .limit(10)
        .all()
    )
    delivered = 0
    async with httpx.AsyncClient(timeout=20) as client:
        for item in rows:
            payload: dict[str, Any] = {
                "chat_id": settings.telegram_chat_id,
                "text": f"{item.title}\n\n{item.body}",
            }
            keyboard = _keyboard(item)
            if keyboard:
                payload["reply_markup"] = keyboard
            response = await client.post(_telegram_url("sendMessage"), json=payload)
            response.raise_for_status()
            item.delivered_at = utcnow()
            delivered += 1
    return delivered


async def poll_telegram_callbacks(db: Session) -> int:
    global _telegram_offset
    if not telegram_enabled():
        return 0
    params = {"offset": _telegram_offset, "timeout": 0, "allowed_updates": '["callback_query"]'}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(_telegram_url("getUpdates"), params=params)
        response.raise_for_status()
        updates = response.json().get("result") or []
        handled = 0
        for update in updates:
            _telegram_offset = max(_telegram_offset, int(update.get("update_id", 0)) + 1)
            callback = update.get("callback_query") or {}
            callback_id = callback.get("id")
            data = callback.get("data") or ""
            answer = "That action is no longer available."
            callback_chat_id = str((((callback.get("message") or {}).get("chat") or {}).get("id", "")))
            if callback_chat_id != str(settings.telegram_chat_id):
                answer = "This Focus bot is private."
            elif data.startswith("focus:n:"):
                try:
                    _, _, notification_id, action = data.split(":", 3)
                    item = db.get(models.Notification, int(notification_id))
                    if not item:
                        answer = "Focus could not find that reminder."
                    else:
                        apply_notification_action(db, item, action)
                        answer = "Done. Focus is updated."
                        handled += 1
                except (TypeError, ValueError) as exc:
                    answer = str(exc)[:160]
            if callback_id:
                await client.post(_telegram_url("answerCallbackQuery"), json={
                    "callback_query_id": callback_id,
                    "text": answer,
                })
        return handled
