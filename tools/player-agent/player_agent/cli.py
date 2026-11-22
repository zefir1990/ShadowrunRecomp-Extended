from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from .game import McpGame, McpGameSettings
from .model import ModelError, VisionEndpoint, VisionPlayerModel
from .runtime import PlayerRuntime, PlayerSettings, StepRecord, action_summary


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
    return parser


def print_step(step: StepRecord) -> None:
    first_line = step.description.splitlines()[0] if step.description else ""
    print(f"[turn {step.turn}] {first_line}", flush=True)
    print(f"  mcp read_state: {step.mcp_state}", flush=True)
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
    )
    game_settings = McpGameSettings(server_path=arguments.server) if arguments.server else McpGameSettings()
    async with McpGame(game_settings) as game:
        runtime = PlayerRuntime(game, VisionPlayerModel(endpoint), settings, on_step=print_step)
        steps = await runtime.run()
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
