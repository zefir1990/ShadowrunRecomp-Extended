from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from typing import Final, Sequence

from genesis_pad import BUTTON_ORDER, normalize_button
from vision_client import ModelError, VisionEndpoint, message_text, post_completion

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


class VisionPlayerModel:
    def __init__(self, endpoint: VisionEndpoint) -> None:
        self._endpoint = endpoint

    async def observe_and_decide(
        self, screenshot: bytes, goal: str, history: Sequence[str]
    ) -> Observation:
        request_body = self.build_request(screenshot, goal, history)
        payload = await asyncio.to_thread(post_completion, self._endpoint, request_body)
        return parse_observation(message_text(payload))

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
