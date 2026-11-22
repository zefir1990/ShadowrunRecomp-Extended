from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .runtime import StepRecord, action_summary, frame_of

DEFAULT_STALL_LIMIT: Final[int] = 4
STDERR_TAIL_LINES: Final[int] = 120


class CrashDetected(RuntimeError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason if not detail else f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class WatchSettings:
    report_directory: Path
    stderr_log: Path | None = None
    crash_log: Path | None = None
    stall_limit: int = DEFAULT_STALL_LIMIT


class CrashWatcher:
    def __init__(self, settings: WatchSettings) -> None:
        self._settings = settings
        self._last_frame: int | None = None
        self._stalled_turns = 0
        self._last_step: StepRecord | None = None
        self._crash_log_signature = self._signature(settings.crash_log)

    @property
    def last_step(self) -> StepRecord | None:
        return self._last_step

    @staticmethod
    def _signature(path: Path | None) -> object:
        if path is None:
            return None
        try:
            stat = path.stat()
        except OSError:
            return ("missing",)
        return (stat.st_mtime_ns, stat.st_size)

    def record(self, step: StepRecord) -> None:
        self._last_step = step
        self._check_crash_log()
        frame = frame_of(step)
        if frame is None:
            return
        if self._last_frame is not None and frame <= self._last_frame:
            self._stalled_turns += 1
        else:
            self._stalled_turns = 0
        self._last_frame = frame
        if self._stalled_turns >= self._settings.stall_limit:
            raise CrashDetected(
                "frame counter did not advance",
                f"stuck at frame {frame} for {self._stalled_turns} turns",
            )

    def _check_crash_log(self) -> None:
        if self._crash_log_signature is None:
            return
        current = self._signature(self._settings.crash_log)
        if current != self._crash_log_signature:
            self._crash_log_signature = current
            raise CrashDetected("the runner wrote a crash report", str(self._settings.crash_log))

    def write_report(self, reason: str, detail: str = "") -> Path:
        self._settings.report_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now()
        path = self._settings.report_directory / f"crash-{timestamp.strftime('%Y%m%d-%H%M%S')}.md"
        step = self._last_step
        lines = [
            "# Crash report",
            "",
            f"- time: {timestamp.isoformat(timespec='seconds')}",
            f"- reason: {reason}",
            f"- detail: {detail or 'none'}",
        ]
        if step is not None:
            lines.extend(
                [
                    f"- last turn: {step.turn}",
                    f"- last frame: {frame_of(step)}",
                    f"- last action: {action_summary(step.action)}",
                    f"- last description: {step.description}",
                    f"- screenshot: {step.screenshot_path or 'not saved'}",
                    f"- screenshot sha256: {step.screenshot_sha256}",
                ]
            )
        lines.append("")
        lines.extend(self._section("runner stderr (tail)", self._settings.stderr_log))
        lines.extend(self._section("last_error.log (tail)", self._settings.crash_log))
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
        return path

    @staticmethod
    def _section(title: str, path: Path | None) -> list[str]:
        lines = [f"## {title}", ""]
        if path is None:
            return lines + ["not configured", ""]
        try:
            content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as error:
            return lines + [f"cannot read {path}: {error}", ""]
        if not content:
            return lines + [f"{path} is empty", ""]
        tail = content[-STDERR_TAIL_LINES:]
        return lines + ["```", *tail, "```", ""]
