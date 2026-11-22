from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Final

from mcp.server.mcpserver import Image, MCPServer

from debug_link import DebugEndpoint, GenesisDebugLink
from genesis_pad import button_mask, normalize_button
from state_store import StateStore, digest_png
from vision_client import describe_png

DEFAULT_DURATION_MS: Final[int] = 150
MINIMUM_DURATION_MS: Final[int] = 1
MAXIMUM_DURATION_MS: Final[int] = 60_000
READ_STATE_PLACEHOLDER: Final[str] = "State will be here"
DIGEST_LENGTH: Final[int] = 64

server = MCPServer(
    name="genesis-pad",
    title="Sega Genesis pad",
    instructions=(
        "Controls the running ShadowrunRecomp window through the runner's debug command server. "
        "Launch the game with a debug.ini next to ShadowrunRecomp.exe so the server listens on "
        "127.0.0.1:4378, or point GENESIS_DEBUG_HOST and GENESIS_DEBUG_PORT elsewhere."
    ),
)


def validate_duration(duration_ms: int) -> int:
    if duration_ms < MINIMUM_DURATION_MS or duration_ms > MAXIMUM_DURATION_MS:
        raise ValueError(
            f"duration_ms must be between {MINIMUM_DURATION_MS} and {MAXIMUM_DURATION_MS}, got {duration_ms}"
        )
    return duration_ms


def frame_or_none(link: GenesisDebugLink) -> int | None:
    try:
        return link.current_frame()
    except RuntimeError:
        return None


@server.tool(
    description=(
        "Hold one Sega Genesis pad button for a number of milliseconds and then release it. "
        "Buttons: up, down, left, right, a, b, c, start."
    )
)
def press_button(button: str, duration_ms: int = DEFAULT_DURATION_MS) -> str:
    mask = button_mask(button)
    duration = validate_duration(duration_ms)
    endpoint = DebugEndpoint.from_environment()
    with GenesisDebugLink(endpoint) as link:
        first_frame = frame_or_none(link)
        link.hold(mask)
        try:
            time.sleep(duration / 1000.0)
        finally:
            link.release()
        last_frame = frame_or_none(link)
    name = normalize_button(button).upper()
    if first_frame is None or last_frame is None:
        return f"Pressed {name} for {duration} ms."
    return f"Pressed {name} for {duration} ms across frames {first_frame}..{last_frame}."


def capture_screenshot_bytes() -> bytes:
    endpoint = DebugEndpoint.from_environment()
    with tempfile.TemporaryDirectory(prefix="genesis-mcp-") as directory:
        capture_path = Path(directory) / "screen.png"
        with GenesisDebugLink(endpoint) as link:
            link.screenshot(str(capture_path))
        if not capture_path.exists():
            raise RuntimeError("the runner answered the screenshot command but wrote no file")
        return capture_path.read_bytes()


@server.tool(description="Capture the current game screen and return it as a PNG image.")
def screenshot() -> Image:
    return Image(data=capture_screenshot_bytes(), format="png")


@server.tool(
    description=(
        "Return the text description of the current screen. An already described screen is answered "
        "from cache; a new screen is described by the vision model; without a model the placeholder "
        "'State will be here' is returned."
    )
)
def read_state() -> str:
    png = capture_screenshot_bytes()
    digest = digest_png(png)
    store = StateStore()
    cached = store.lookup(digest)
    if cached:
        return cached
    description = describe_png(png)
    if not description:
        return READ_STATE_PLACEHOLDER
    store.remember(digest, description)
    return description


@server.tool(
    description=(
        "Store the text description produced for one screenshot, keyed by that screenshot's "
        "SHA-256, so read_state returns it for the same game state."
    )
)
def record_state(description: str, screenshot_sha256: str) -> str:
    trimmed = description.strip()
    if not trimmed:
        raise ValueError("description must not be empty")
    digest = screenshot_sha256.strip().lower()
    if len(digest) != DIGEST_LENGTH or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError("screenshot_sha256 must be a 64 character hexadecimal SHA-256")
    StateStore().remember(digest, trimmed)
    return f"recorded description for state {digest[:12]}"


@server.tool(
    description=(
        "Return the emulator's internal state at the current frame as JSON: "
        "m68k registers, VDP flags, pad input and the frame number."
    )
)
def read_game_state() -> str:
    endpoint = DebugEndpoint.from_environment()
    with GenesisDebugLink(endpoint) as link:
        state = link.game_state()
    return json.dumps(state, sort_keys=True)


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
