from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from .game import McpGame, McpGameSettings
from .model import ModelError, VisionEndpoint, VisionPlayerModel
from .runtime import PlayerRuntime, PlayerSettings, StepRecord, action_summary, state_summary
from .watcher import CrashDetected, CrashWatcher, WatchSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="player-agent",
        description="Play Shadowrun through the genesis-mcp server using a vision model.",
    )
    parser.add_argument("--goal", required=True, help="what the agent should accomplish")
    parser.add_argument("--turns", type=int, default=24, help="maximum observe/act turns (default 24)")
    parser.add_argument("--transcript", default="", help="directory for screenshots and transcripts")
    parser.add_argument("--server", default="", help="path to tools/genesis-mcp/server.py")
    parser.add_argument("--base-url", default="", help="OpenAI-compatible endpoint (overrides env)")
    parser.add_argument("--api-key", default="", help="API key (overrides env)")
    parser.add_argument("--model", default="", help="vision model name (overrides env)")
    parser.add_argument("--timeout", type=float, default=0.0, help="per-request timeout in seconds")
    parser.add_argument("--stderr-log", default="", help="game stderr file to quote in a crash report")
    parser.add_argument("--crash-log", default="", help="runner last_error.log to quote in a crash report")
    parser.add_argument("--crash-dir", default="", help="where crash reports go (default: transcript directory)")
    parser.add_argument("--record-route", default="", help="write the presses as an input script route")
    return parser


def print_step(step: StepRecord) -> None:
    first_line = step.description.splitlines()[0] if step.description else ""
    print(f"[turn {step.turn}] {first_line}", flush=True)
    print(f"  mcp read_state: {step.mcp_state}", flush=True)
    print(f"  internal: {state_summary(step.internal_state)}", flush=True)
    print(f"  -> {action_summary(step.action)}", flush=True)


def resolve_endpoint(arguments: argparse.Namespace) -> VisionEndpoint:
    endpoint = VisionEndpoint.from_environment()
    if arguments.base_url:
        endpoint = replace(endpoint, base_url=arguments.base_url)
    if arguments.api_key:
        endpoint = replace(endpoint, api_key=arguments.api_key)
    if arguments.model:
        endpoint = replace(endpoint, model=arguments.model)
    if arguments.timeout:
        endpoint = replace(endpoint, timeout_seconds=arguments.timeout)
    return endpoint


async def play(arguments: argparse.Namespace, endpoint: VisionEndpoint) -> int:
    print(
        f"vision: model={endpoint.model} endpoint={endpoint.completion_url()} key={endpoint.key_source}",
        flush=True,
    )
    settings = PlayerSettings(
        goal=arguments.goal,
        max_turns=arguments.turns,
        transcript_directory=Path(arguments.transcript) if arguments.transcript else None,
        route_path=Path(arguments.record_route) if arguments.record_route else None,
    )
    crash_directory = Path(arguments.crash_dir) if arguments.crash_dir else (
        settings.transcript_directory or Path.cwd()
    )
    watcher = CrashWatcher(
        WatchSettings(
            report_directory=crash_directory,
            stderr_log=Path(arguments.stderr_log) if arguments.stderr_log else None,
            crash_log=Path(arguments.crash_log) if arguments.crash_log else None,
        )
    )

    def observe(step: StepRecord) -> None:
        print_step(step)
        watcher.record(step)

    game_settings = McpGameSettings(server_path=arguments.server) if arguments.server else McpGameSettings()
    async with McpGame(game_settings) as game:
        runtime = PlayerRuntime(game, VisionPlayerModel(endpoint), settings, on_step=observe)
        try:
            steps = await runtime.run()
        except CrashDetected as detected:
            report = watcher.write_report(detected.reason, detected.detail)
            print(f"CRASH DETECTED: {detected.reason} ({detected.detail})", file=sys.stderr)
            print(f"report: {report}", file=sys.stderr)
            return 3
        except ModelError as error:
            print(f"model error: {error}", file=sys.stderr)
            return 2
        except Exception as error:
            report = watcher.write_report("the runner stopped answering MCP", f"{type(error).__name__}: {error}")
            print(f"CRASH DETECTED: runner stopped answering ({error})", file=sys.stderr)
            print(f"report: {report}", file=sys.stderr)
            return 3
    if not steps:
        print("no turns were played", file=sys.stderr)
        return 1
    last = steps[-1]
    print(f"stopped after {len(steps)} turn(s): {action_summary(last.action)}")
    if settings.transcript_directory:
        print(f"transcript written under {settings.transcript_directory}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        endpoint = resolve_endpoint(arguments)
    except ModelError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2
    try:
        return asyncio.run(play(arguments, endpoint))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
