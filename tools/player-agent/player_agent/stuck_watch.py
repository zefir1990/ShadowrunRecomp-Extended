from __future__ import annotations

import argparse
import asyncio
import datetime
import hashlib
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Sequence

from .game import McpGame, McpGameSettings

DEFAULT_SECONDS: Final[float] = 12.0
DEFAULT_INTERVAL: Final[float] = 0.5
PROBE_DURATION_MS: Final[int] = 150
PROBE_SETTLE_SECONDS: Final[float] = 1.2


@dataclass(frozen=True)
class WatchSettings:
    output_directory: Path
    seconds: float = DEFAULT_SECONDS
    interval: float = DEFAULT_INTERVAL
    probe: str = ""
    maximum_minutes: float = 60.0


def frame_of(state: dict[str, object]) -> int | None:
    frame = state.get("frame")
    return frame if isinstance(frame, int) else None


async def watch(settings: WatchSettings) -> int:
    settings.output_directory.mkdir(parents=True, exist_ok=True)
    async with McpGame(McpGameSettings()) as game:
        previous_digest = ""
        stable_since = time.monotonic()
        started = time.monotonic()
        while True:
            screenshot = await game.screenshot()
            digest = hashlib.sha256(screenshot).hexdigest()
            now = time.monotonic()
            if digest != previous_digest:
                previous_digest = digest
                stable_since = now
            elif now - stable_since >= settings.seconds:
                return await report_stuck(game, settings, screenshot, started, stable_since, now)
            if now - started >= settings.maximum_minutes * 60.0:
                print(f"screen kept changing for {settings.maximum_minutes:g} minutes; no hang")
                return 0
            await asyncio.sleep(settings.interval)


async def report_stuck(
    game: McpGame,
    settings: WatchSettings,
    screenshot: bytes,
    started: float,
    stable_since: float,
    now: float,
) -> int:
    timestamp = datetime.datetime.now()
    stem = f"stuck-{timestamp.strftime('%Y%m%d-%H%M%S')}"
    image_path = settings.output_directory / f"{stem}.png"
    image_path.write_bytes(screenshot)
    state = await game.internal_state()
    probe_result = ""
    if settings.probe:
        before = hashlib.sha256(screenshot).hexdigest()
        await game.press(settings.probe, PROBE_DURATION_MS)
        await asyncio.sleep(PROBE_SETTLE_SECONDS)
        after = hashlib.sha256(await game.screenshot()).hexdigest()
        probe_result = "recovered after the probe" if after != before else "still identical after the probe"
    report = settings.output_directory / f"{stem}.md"
    lines = [
        "# Screen unchanged",
        "",
        f"- detected: {timestamp.isoformat(timespec='seconds')}",
        f"- unchanged for: {now - stable_since:.1f} s",
        f"- frame: {frame_of(state)}",
        f"- screenshot: {image_path}",
        f"- screenshot sha256: {hashlib.sha256(screenshot).hexdigest()}",
        f"- probe: {settings.probe or 'disabled'}{': ' + probe_result if probe_result else ''}",
        "",
        "The runner is still answering, but the rendered screen has not changed. A dialog that "
        "ignores input, a frozen animation or a spin waiting on a device all look like this.",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"STUCK: screen unchanged for {now - stable_since:.1f} s (frame {frame_of(state)}), report {report}")
    return 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="player-agent.stuck_watch",
        description="Report when the running game stops changing its screen while still answering.",
    )
    parser.add_argument("--out", required=True, help="directory for the screenshot and report")
    parser.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    parser.add_argument("--probe", default="", help="button to press once before reporting")
    parser.add_argument("--minutes", type=float, default=60.0, help="give up after this long")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    settings = WatchSettings(
        output_directory=Path(arguments.out),
        seconds=arguments.seconds,
        interval=arguments.interval,
        probe=arguments.probe,
        maximum_minutes=arguments.minutes,
    )
    try:
        return asyncio.run(watch(settings))
    except KeyboardInterrupt:
        print("stopped", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
