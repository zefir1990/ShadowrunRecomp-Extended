from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_AUTH_PATH = Path.home() / ".local" / "share" / "opencode" / "auth.json"


def auth_path() -> Path:
    override = os.environ.get("PLAYER_VISION_OPENCODE_AUTH")
    return Path(override) if override else DEFAULT_AUTH_PATH


def read_provider_key(provider: str) -> str | None:
    path = auth_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    entry = payload.get(provider)
    if not isinstance(entry, dict):
        return None
    key = entry.get("key")
    return key if isinstance(key, str) and key else None
