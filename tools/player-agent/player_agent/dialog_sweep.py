from __future__ import annotations

import argparse
import asyncio
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Sequence

from .game import McpGame, McpGameSettings
from .model import VisionEndpoint, VisionPlayerModel
from .runtime import StepRecord, WaitAction
from .watcher import CrashDetected, CrashWatcher, WatchSettings

DEFAULT_PORT: Final[int] = 4378
DIALOG_WAIT_SECONDS: Final[float] = 180.0
STEP_PAUSE_SECONDS: Final[float] = 0.6


@dataclass(frozen=True)
class SweepSettings:
    executable: Path
    rom: Path
    route: Path
    output_directory: Path
    dialog_frame: int
    options: Sequence[str]
    steps: int = 12
    port: int = DEFAULT_PORT
    describe: bool = False
    stderr_log: Path | None = None
    crash_log: Path | None = None


def wait_for_port(port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def start_game(settings: SweepSettings) -> tuple[subprocess.Popen[bytes], object]:
    debug_ini = settings.executable.parent / "debug.ini"
    debug_ini.write_text(f"port={settings.port}\n", encoding="ascii", newline="\n")
    stderr = open(settings.stderr_log, "ab") if settings.stderr_log else subprocess.DEVNULL
    arguments = [
        str(settings.executable),
        str(settings.rom),
        "--no-launcher",
        "--input-script",
        str(settings.route),
        "--turbo",
    ]
    process = subprocess.Popen(
        arguments,
        cwd=str(settings.executable.parent.parent),
        stderr=stderr,
        stdout=subprocess.DEVNULL,
    )
    return process, stderr


async def run_one_path(settings: SweepSettings, option: str) -> list[str]:
    lines = [f"## Option {option.upper()}", ""]
    process, stderr_handle = start_game(settings)
    watcher = CrashWatcher(
        WatchSettings(
            report_directory=settings.output_directory,
            stderr_log=settings.stderr_log,
            crash_log=settings.crash_log,
        )
    )
    model = VisionPlayerModel(VisionEndpoint.from_environment()) if settings.describe else None
    try:
        if not await asyncio.to_thread(wait_for_port, settings.port, DIALOG_WAIT_SECONDS):
            lines.append("the debug server never came up")
            return lines
        async with McpGame(McpGameSettings()) as game:
            deadline = time.monotonic() + DIALOG_WAIT_SECONDS
            state: dict[str, object] = {}
            while time.monotonic() < deadline:
                state = await game.internal_state()
                if isinstance(state.get("frame"), int) and state["frame"] >= settings.dialog_frame:
                    break
                await asyncio.sleep(0.5)
            lines.append(f"dialog reached at frame {state.get('frame')}")
            await game.press(option, 150)
            for step in range(1, settings.steps + 1):
                screenshot = await game.screenshot()
                path = settings.output_directory / f"option-{option.lower()}-step-{step:02d}.png"
                path.write_bytes(screenshot)
                state = await game.internal_state()
                description = ""
                if model is not None:
                    observation = await model.observe_and_decide(screenshot, "Describe this dialog screen.", [])
                    description = observation.description
                lines.append(f"- step {step}: frame {state.get('frame')} {description}".rstrip())
                watcher.record(
                    StepRecord(
                        turn=step,
                        description=description,
                        mcp_state="",
                        internal_state=state,
                        screenshot_sha256="",
                        action=WaitAction(150),
                        screenshot_path=str(path),
                    )
                )
                await asyncio.sleep(STEP_PAUSE_SECONDS)
                await game.press("a", 150)
            lines.append("")
    except CrashDetected as detected:
        report = watcher.write_report(detected.reason, detected.detail)
        lines.append(f"CRASH: {detected.reason} ({detected.detail}); report {report}")
        lines.append("")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        if stderr_handle is not subprocess.DEVNULL:
            stderr_handle.close()
    return lines


async def run_sweep(settings: SweepSettings) -> Path:
    settings.output_directory.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Dialog path sweep",
        "",
        f"- route: {settings.route}",
        f"- dialog frame: {settings.dialog_frame}",
        f"- options: {', '.join(option.upper() for option in settings.options)}",
        f"- steps per path: {settings.steps}",
        "",
    ]
    for option in settings.options:
        lines.extend(await run_one_path(settings, option))
    report = settings.output_directory / "sweep.md"
    report.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="player-agent.dialog_sweep",
        description="Replay a route, take each dialog option, and walk every path while watching for crashes.",
    )
    parser.add_argument("--exe", required=True)
    parser.add_argument("--rom", required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--dialog-frame", type=int, required=True)
    parser.add_argument("--options", default="a,b,c")
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--stderr-log", default="")
    parser.add_argument("--crash-log", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    settings = SweepSettings(
        executable=Path(arguments.exe).resolve(),
        rom=Path(arguments.rom).resolve(),
        route=Path(arguments.route).resolve(),
        output_directory=Path(arguments.out).resolve(),
        dialog_frame=arguments.dialog_frame,
        options=[option.strip().lower() for option in arguments.options.split(",") if option.strip()],
        steps=arguments.steps,
        port=arguments.port,
        describe=arguments.describe,
        stderr_log=Path(arguments.stderr_log).resolve() if arguments.stderr_log else None,
        crash_log=Path(arguments.crash_log).resolve() if arguments.crash_log else None,
    )
    report = asyncio.run(run_sweep(settings))
    print(f"sweep report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
