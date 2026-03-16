from __future__ import annotations

from datetime import datetime
from typing import Any


SENSITIVE_KEYS = {
    "bot_token",
    "ts3_query_password",
    "ts3audiobot_api_key",
    "authorization",
    "password",
    "token",
    "secret",
}


def mask_secret(value: str, visible_prefix: int = 3) -> str:
    if not value:
        return ""
    if len(value) <= visible_prefix:
        return "*" * len(value)
    return f"{value[:visible_prefix]}{'*' * (len(value) - visible_prefix)}"


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = key.lower()
        if lowered in SENSITIVE_KEYS and isinstance(value, str):
            sanitized[key] = mask_secret(value)
            continue
        sanitized[key] = value
    return sanitized


def now_utc() -> datetime:
    return datetime.utcnow()
