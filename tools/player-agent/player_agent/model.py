from __future__ import annotations

import asyncio
import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Final, Sequence

from genesis_pad import BUTTON_ORDER, normalize_button

from .opencode_auth import read_provider_key

DEFAULT_BASE_URL: Final[str] = "https://api.deepseek.com/v1"
DEFAULT_MODEL: Final[str] = "deepseek-chat"
DEFAULT_PROVIDER: Final[str] = "deepseek"
DEFAULT_TIMEOUT_SECONDS: Final[float] = 60.0
DEFAULT_PRESS_DURATION_MS: Final[int] = 150
MAXIMUM_DURATION_MS: Final[int] = 60_000
HISTORY_LIMIT: Final[int] = 6

SYSTEM_PROMPT: Final[str] = (
    "You play Shadowrun for the Sega Genesis. Every turn you receive one 320x224 screenshot "
    "of the current frame plus a goal.\n"
    "Answer with a single JSON object and nothing else:\n"
    '{"screen": "<description>", "action": <action>}\n'
    '"screen" describes only what is visible:\n'
    "- transcribe every readable text string verbatim, top to bottom, preserving case;\n"
    "- name the screen type (title, class menu, dialog, combat, inventory, map, shop);\n"
    "- name the highlighted menu option or selected item;\n"
    "- state health, ammo, money or attributes only when the numbers are readable.\n"
    "Never invent text or values you cannot see. If the screen is dark or empty, say so.\n"
    '"action" is exactly one of:\n'
    '{"type":"press","button":"' + "|".join(BUTTON_ORDER) + '","duration_ms":150}\n'
    '{"type":"wait","duration_ms":500}\n'
    '{"type":"stop","reason":"<why the goal is reached or cannot continue>"}\n'
    "Press at most one button per turn. Use wait after a press when the game needs time to react.\n"
)


class ModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class PressAction:
    button: str
    duration_ms: int = DEFAULT_PRESS_DURATION_MS


@dataclass(frozen=True)
class WaitAction:
    duration_ms: int


@dataclass(frozen=True)
class StopAction:
    reason: str


Action = PressAction | WaitAction | StopAction


@dataclass(frozen=True)
class Observation:
    description: str
    action: Action


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


class VisionPlayerModel:
    def __init__(self, endpoint: VisionEndpoint) -> None:
        self._endpoint = endpoint

    async def observe_and_decide(
        self, screenshot: bytes, goal: str, history: Sequence[str]
    ) -> Observation:
        request_body = self.build_request(screenshot, goal, history)
        payload = await _post_json_in_thread(
            self._endpoint.completion_url(), self._headers(), request_body, self._endpoint.timeout_seconds
        )
        return parse_observation(_extract_message_text(payload))

    def build_request(self, screenshot: bytes, goal: str, history: Sequence[str]) -> dict[str, object]:
        recent_steps = "\n".join(f"- {step}" for step in list(history)[-HISTORY_LIMIT:]) or "- none"
        encoded = base64.b64encode(screenshot).decode("ascii")
        return {
            "model": self._endpoint.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Goal: {goal}\nRecent steps:\n{recent_steps}\nCurrent screen:"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
                    ],
                },
            ],
        }

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._endpoint.api_key}",
            "Content-Type": "application/json",
        }


async def _post_json_in_thread(url: str, headers: dict[str, str], payload: dict[str, object], timeout: float) -> dict[str, object]:
    return await asyncio.to_thread(_post_json, url, headers, payload, timeout)


def _post_json(url: str, headers: dict[str, str], payload: dict[str, object], timeout: float) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise ModelError(f"vision endpoint returned HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise ModelError(f"cannot reach the vision endpoint at {url}: {error.reason}") from error


def _extract_message_text(payload: dict[str, object]) -> str:
    try:
        choices = payload["choices"]
        message = choices[0]["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ModelError(f"unexpected vision response shape: {json.dumps(payload)[:300]}") from error
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [part.get("text", "") for part in content if isinstance(part, dict)]
        return "".join(parts)
    raise ModelError("vision response carried no text content")


def parse_observation(text: str) -> Observation:
    payload = json.loads(_strip_code_fence(text))
    if not isinstance(payload, dict):
        raise ModelError("the model did not return a JSON object")
    description = payload.get("screen")
    if not isinstance(description, str) or not description.strip():
        raise ModelError("the model returned no screen description")
    return Observation(description=description.strip(), action=parse_action(payload.get("action")))


def parse_action(payload: object) -> Action:
    if not isinstance(payload, dict):
        raise ModelError("the model returned no action object")
    action_type = payload.get("type")
    if action_type == "press":
        try:
            button = normalize_button(str(payload.get("button", "")))
        except ValueError as error:
            raise ModelError(str(error)) from error
        return PressAction(
            button=button,
            duration_ms=_duration(payload.get("duration_ms"), DEFAULT_PRESS_DURATION_MS),
        )
    if action_type == "wait":
        return WaitAction(duration_ms=_duration(payload.get("duration_ms"), 500))
    if action_type == "stop":
        return StopAction(reason=str(payload.get("reason", "")).strip())
    raise ModelError(f"unknown action type {action_type!r}")


def _duration(value: object, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ModelError(f"duration_ms must be a number, got {value!r}")
    duration = int(value)
    if duration < 1 or duration > MAXIMUM_DURATION_MS:
        raise ModelError(f"duration_ms must be between 1 and {MAXIMUM_DURATION_MS}, got {duration}")
    return duration


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].startswith("```"):
        return "\n".join(lines[1:-1]).strip()
    return stripped
