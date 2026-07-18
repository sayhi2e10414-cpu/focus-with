from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Header, HTTPException

from .config import settings


def _matches(provided: Optional[str], expected: str) -> bool:
    return bool(provided and expected and secrets.compare_digest(provided, expected))


def require_api_token(x_focus_token: Optional[str] = Header(default=None)) -> str:
    if not settings.api_token and settings.local_only:
        return "local"
    if not _matches(x_focus_token, settings.api_token):
        raise HTTPException(status_code=401, detail="Invalid Focus API token")
    return "api"


def require_phone_token(
    x_focus_phone_token: Optional[str] = Header(default=None),
    x_focus_token: Optional[str] = Header(default=None),
) -> str:
    if _matches(x_focus_phone_token, settings.phone_token):
        return "phone"
    if _matches(x_focus_token, settings.api_token):
        return "api"
    if not settings.phone_token and not settings.api_token and settings.local_only:
        return "local"
    raise HTTPException(status_code=401, detail="Invalid phone event token")
