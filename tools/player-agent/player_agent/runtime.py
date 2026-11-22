from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Final, Protocol, Sequence

from .model import Action, Observation, PressAction, StopAction, WaitAction

DEFAULT_MAX_TURNS: Final[int] = 24
DEFAULT_HISTORY_SIZE: Final[int] = 6


class GamePort(Protocol):
    async def screenshot(self) -> bytes: ...
    async def press(self, button: str, duration_ms: int) -> str: ...


class PlayerModelPort(Protocol):
    async def observe_and_decide(
        self, screenshot: bytes, goal: str, history: Sequence[str]
    ) -> Observation: ...


@dataclass(frozen=True)
class PlayerSettings:
    goal: str
    max_turns: int = DEFAULT_MAX_TURNS
    transcript_directory: Path | None = None
    history_size: int = DEFAULT_HISTORY_SIZE


@dataclass(frozen=True)
class StepRecord:
    turn: int
    description: str
    action: Action
    screenshot_path: str | None


class Transcript:
    def __init__(self, directory: Path, goal: str) -> None:
        self._directory = directory
        self._goal = goal
        self._steps: list[StepRecord] = []

    def add(self, step: StepRecord) -> None:
        self._steps.append(step)

    def save_screenshot(self, turn: int, screenshot: bytes) -> str:
        screenshots = self._directory / "screenshots"
        screenshots.mkdir(parents=True, exist_ok=True)
        path = screenshots / f"turn-{turn:03d}.png"
        path.write_bytes(screenshot)
        return str(path)

    def write(self) -> tuple[Path, Path]:
        self._directory.mkdir(parents=True, exist_ok=True)
        jsonl_path = self._directory / "transcript.jsonl"
        with jsonl_path.open("w", encoding="utf-8", newline="\n") as stream:
            for step in self._steps:
                stream.write(json.dumps(_step_payload(step)) + "\n")
        markdown_path = self._directory / "transcript.md"
        markdown_path.write_text(self._markdown(), encoding="utf-8", newline="\n")
        return jsonl_path, markdown_path

    def _markdown(self) -> str:
        lines = ["# Player transcript", "", f"Goal: {self._goal}", ""]
        for step in self._steps:
            lines.append(f"## Turn {step.turn}")
            lines.append("")
            lines.append(step.description)
            lines.append("")
            lines.append(f"Action: {action_summary(step.action)}")
            if step.screenshot_path:
                lines.append(f"Screenshot: {step.screenshot_path}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def action_summary(action: Action) -> str:
    if isinstance(action, PressAction):
        return f"press {action.button} for {action.duration_ms} ms"
    if isinstance(action, WaitAction):
        return f"wait {action.duration_ms} ms"
    if isinstance(action, StopAction):
        return f"stop ({action.reason or 'no reason given'})"
    return "unknown"


def _step_payload(step: StepRecord) -> dict[str, object]:
    if isinstance(step.action, PressAction):
        action_payload: dict[str, object] = {
            "type": "press",
            "button": step.action.button,
            "duration_ms": step.action.duration_ms,
        }
    elif isinstance(step.action, WaitAction):
        action_payload = {"type": "wait", "duration_ms": step.action.duration_ms}
    else:
        action_payload = {"type": "stop", "reason": step.action.reason}
    return {
        "turn": step.turn,
        "description": step.description,
        "action": action_payload,
        "screenshot_path": step.screenshot_path,
    }


class PlayerRuntime:
    def __init__(
        self,
        game: GamePort,
        model: PlayerModelPort,
        settings: PlayerSettings,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        on_step: Callable[[StepRecord], None] | None = None,
    ) -> None:
        self._game = game
        self._model = model
        self._settings = settings
        self._sleep = sleep
        self._on_step = on_step
        self._records: list[StepRecord] = []
        self._transcript = (
            Transcript(settings.transcript_directory, settings.goal)
            if settings.transcript_directory is not None
            else None
        )

    @property
    def steps(self) -> list[StepRecord]:
        return list(self._records)

    async def run(self) -> list[StepRecord]:
        history: list[str] = []
        try:
            for turn in range(1, self._settings.max_turns + 1):
                screenshot = await self._game.screenshot()
                observation = await self._model.observe_and_decide(screenshot, self._settings.goal, history)
                screenshot_path = (
                    self._transcript.save_screenshot(turn, screenshot) if self._transcript else None
                )
                step = StepRecord(
                    turn=turn,
                    description=observation.description,
                    action=observation.action,
                    screenshot_path=screenshot_path,
                )
                self._records.append(step)
                if self._transcript:
                    self._transcript.add(step)
                if self._on_step:
                    self._on_step(step)
                history.append(f"turn {turn}: {observation.description}")
                if isinstance(observation.action, StopAction):
                    history = history[-self._settings.history_size:]
                    break
                if isinstance(observation.action, PressAction):
                    await self._game.press(observation.action.button, observation.action.duration_ms)
                    history.append(f"pressed {observation.action.button}")
                elif isinstance(observation.action, WaitAction):
                    await self._sleep(observation.action.duration_ms / 1000.0)
                history = history[-self._settings.history_size:]
        finally:
            if self._transcript:
                self._transcript.write()
        return self.steps
