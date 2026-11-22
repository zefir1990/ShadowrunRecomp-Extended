from __future__ import annotations

import asyncio
import hashlib
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
    async def read_state(self) -> str: ...
    async def internal_state(self) -> dict[str, object]: ...
    async def record_state(self, description: str, screenshot_sha256: str) -> str: ...


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
    route_path: Path | None = None


@dataclass(frozen=True)
class StepRecord:
    turn: int
    description: str
    mcp_state: str
    internal_state: dict[str, object]
    screenshot_sha256: str
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
            lines.append(f"MCP read_state: {step.mcp_state}")
            lines.append("")
            lines.append(f"Internal state: {state_summary(step.internal_state)}")
            lines.append("")
            lines.append(f"Screenshot SHA-256: {step.screenshot_sha256}")
            lines.append("")
            lines.append(f"Action: {action_summary(step.action)}")
            if step.screenshot_path:
                lines.append(f"Screenshot: {step.screenshot_path}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def frame_of(step: StepRecord) -> int | None:
    frame = step.internal_state.get("frame")
    return frame if isinstance(frame, int) else None


def action_summary(action: Action) -> str:
    if isinstance(action, PressAction):
        return f"press {action.button} for {action.duration_ms} ms"
    if isinstance(action, WaitAction):
        return f"wait {action.duration_ms} ms"
    if isinstance(action, StopAction):
        return f"stop ({action.reason or 'no reason given'})"
    return "unknown"


def state_summary(state: dict[str, object]) -> str:
    if not state:
        return "unavailable"
    parts = [f"frame {state.get('frame')}"]
    m68k = state.get("m68k") if isinstance(state.get("m68k"), dict) else {}
    registers = m68k.get("A") if isinstance(m68k.get("A"), list) else []
    if len(registers) == 8 and isinstance(registers[7], int):
        parts.append(f"A7 0x{registers[7]:06X}")
    z80 = state.get("z80") if isinstance(state.get("z80"), dict) else {}
    z80_pc = z80.get("PC")
    if isinstance(z80_pc, int):
        parts.append(f"z80 PC 0x{z80_pc:04X}")
    vdp = state.get("vdp") if isinstance(state.get("vdp"), dict) else {}
    display = vdp.get("display")
    if display is not None:
        parts.append(f"display {display}")
    pad = state.get("input") if isinstance(state.get("input"), dict) else {}
    buttons = pad.get("buttons")
    if buttons is not None:
        parts.append(f"pad {buttons}")
    return ", ".join(parts)


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
        "mcp_state": step.mcp_state,
        "internal_state": step.internal_state,
        "screenshot_sha256": step.screenshot_sha256,
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
        self._route_lines: list[str] = []
        self._route_last_frame = 0
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
                internal_state = await self._game.internal_state()
                observation = await self._model.observe_and_decide(screenshot, self._settings.goal, history)
                screenshot_path = (
                    self._transcript.save_screenshot(turn, screenshot) if self._transcript else None
                )
                screenshot_sha256 = hashlib.sha256(screenshot).hexdigest()
                await self._game.record_state(observation.description, screenshot_sha256)
                mcp_state = await self._game.read_state()
                step = StepRecord(
                    turn=turn,
                    description=observation.description,
                    mcp_state=mcp_state,
                    internal_state=internal_state,
                    screenshot_sha256=screenshot_sha256,
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
                    self._record_route_press(step, observation.action)
                    await self._game.press(observation.action.button, observation.action.duration_ms)
                    history.append(f"pressed {observation.action.button}")
                elif isinstance(observation.action, WaitAction):
                    await self._sleep(observation.action.duration_ms / 1000.0)
                history = history[-self._settings.history_size:]
        finally:
            if self._transcript:
                self._transcript.write()
            self._write_route()
        return self.steps

    def _record_route_press(self, step: StepRecord, action: PressAction) -> None:
        frame = frame_of(step)
        if frame is None:
            return
        gap = max(1, frame - self._route_last_frame)
        duration_frames = max(1, round(action.duration_ms * 60 / 1000))
        self._route_lines.append(f"WAIT {gap}")
        self._route_lines.append(f"PRESS {action.button.upper()} {duration_frames}")
        self._route_last_frame = frame

    def _write_route(self) -> None:
        path = self._settings.route_path
        if path is None or not self._route_lines:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [*self._route_lines, "WAIT 1000000", ""]
        path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
