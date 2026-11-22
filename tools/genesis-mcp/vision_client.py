from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Final

from opencode_auth import read_provider_key

DEFAULT_BASE_URL: Final[str] = "https://api.deepseek.com/v1"
DEFAULT_MODEL: Final[str] = "deepseek-chat"
DEFAULT_PROVIDER: Final[str] = "deepseek"
DEFAULT_TIMEOUT_SECONDS: Final[float] = 60.0

SCREEN_DESCRIPTION_PROMPT: Final[str] = (
    "You describe frames of Shadowrun for the Sega Genesis for another agent. "
    "Transcribe every readable text string verbatim, top to bottom, preserving case. "
    "Name the screen type (title, class menu, dialog, combat, inventory, map, shop), "
    "the highlighted option or selected item, and any readable values. "
    "Never invent text or numbers. If the screen is dark or empty, say so."
)


class ModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisionEndpoint:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    key_source: str = "environment"

    @classmethod
    def from_environment(cls) -> "VisionEndpoint":
        model = os.environ.get("PLAYER_VISION_MODEL") or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
        provider = os.environ.get("PLAYER_VISION_PROVIDER", DEFAULT_PROVIDER)
        base_url = (
            os.environ.get("PLAYER_VISION_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or default_base_url(model)
        )
        api_key = os.environ.get("PLAYER_VISION_API_KEY") or os.environ.get("OPENAI_API_KEY")
        key_source = "environment"
        if not api_key:
            api_key = read_provider_key(provider)
            key_source = f"opencode-auth/{provider}"
        if not api_key:
            raise ModelError(
                "no vision API key found: set PLAYER_VISION_API_KEY (or OPENAI_API_KEY), or sign a "
                f"provider into opencode so {provider} appears in its auth file"
            )
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=float(os.environ.get("PLAYER_VISION_TIMEOUT", DEFAULT_TIMEOUT_SECONDS)),
            key_source=key_source,
        )

    def completion_url(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"


def default_base_url(model: str) -> str:
    if model.startswith("deepseek"):
        return DEFAULT_BASE_URL
    return "https://api.openai.com/v1"


def post_completion(endpoint: VisionEndpoint, body: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint.completion_url(),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {endpoint.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout or endpoint.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise ModelError(f"vision endpoint returned HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise ModelError(f"cannot reach the vision endpoint at {endpoint.completion_url()}: {error.reason}") from error


def message_text(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ModelError(f"unexpected vision response shape: {json.dumps(payload)[:300]}") from error
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    raise ModelError("vision response carried no text content")


def describe_png(png: bytes) -> str | None:
    try:
        endpoint = VisionEndpoint.from_environment()
    except ModelError:
        return None
    body = {
        "model": endpoint.model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SCREEN_DESCRIPTION_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the current screen."},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode("ascii")},
                    },
                ],
            },
        ],
    }
    try:
        description = message_text(post_completion(endpoint, body)).strip()
    except ModelError:
        return None
    return description or None
