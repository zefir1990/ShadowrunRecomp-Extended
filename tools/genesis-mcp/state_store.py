from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Final

MAXIMUM_ENTRIES: Final[int] = 500
DEFAULT_STORE_NAME: Final[str] = "genesis-mcp-state.json"


def digest_png(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def default_store_path() -> Path:
    override = os.environ.get("GENESIS_STATE_STORE")
    return Path(override) if override else Path(tempfile.gettempdir()) / DEFAULT_STORE_NAME


class StateStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_store_path()

    @property
    def path(self) -> Path:
        return self._path

    def lookup(self, digest: str) -> str | None:
        entry = self._load().get(digest)
        if not isinstance(entry, dict):
            return None
        description = entry.get("description")
        return description if isinstance(description, str) and description else None

    def remember(self, digest: str, description: str) -> None:
        entries = self._load()
        entries[digest] = {
            "description": description,
            "recorded_at": time.time(),
        }
        if len(entries) > MAXIMUM_ENTRIES:
            oldest = sorted(entries, key=lambda key: entries[key].get("recorded_at", 0))
            for key in oldest[: len(entries) - MAXIMUM_ENTRIES]:
                entries.pop(key, None)
        self._save(entries)

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        entries = payload.get("entries") if isinstance(payload, dict) else None
        if not isinstance(entries, dict):
            return {}
        return {key: value for key, value in entries.items() if isinstance(value, dict)}

    def _save(self, entries: dict[str, dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(self._path.name + ".tmp")
        temporary.write_text(json.dumps({"entries": entries}, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self._path)
