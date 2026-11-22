from __future__ import annotations

import base64
import json
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Final

from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.types import ImageContent, TextContent

DEFAULT_SERVER_PATH: Final[str] = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "genesis-mcp",
    "server.py",
)


class GameToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class McpGameSettings:
    server_path: str = DEFAULT_SERVER_PATH
    python_executable: str = sys.executable


class McpGame:
    def __init__(self, settings: McpGameSettings | None = None) -> None:
        self._settings = settings or McpGameSettings()
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "McpGame":
        parameters = StdioServerParameters(
            command=self._settings.python_executable,
            args=[self._settings.server_path],
            env=dict(os.environ),
        )
        read_stream, write_stream = await self._stack.enter_async_context(stdio_client(parameters))
        self._session = await self._stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self._session.initialize()
        return self

    async def __aexit__(self, exception_type: object, exception_value: object, traceback: object) -> None:
        await self._stack.aclose()
        self._session = None

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("the game session is not open")
        return self._session

    async def _call(self, tool_name: str, arguments: dict[str, object]) -> list[TextContent | ImageContent]:
        result = await self._require_session().call_tool(tool_name, arguments)
        if result.is_error:
            message = result.content[0].text if result.content else "unknown error"
            raise GameToolError(f"{tool_name} failed: {message}")
        return result.content

    async def _call_text(self, tool_name: str, arguments: dict[str, object]) -> str:
        texts = [
            block.text for block in await self._call(tool_name, arguments) if isinstance(block, TextContent)
        ]
        return "\n".join(texts)

    async def screenshot(self) -> bytes:
        for block in await self._call("screenshot", {}):
            if isinstance(block, ImageContent):
                return base64.b64decode(block.data)
        raise GameToolError("screenshot returned no image")

    async def press(self, button: str, duration_ms: int) -> str:
        for block in await self._call("press_button", {"button": button, "duration_ms": duration_ms}):
            if isinstance(block, TextContent):
                return block.text
        return f"Pressed {button} for {duration_ms} ms."

    async def read_state(self) -> str:
        for block in await self._call("read_state", {}):
            if isinstance(block, TextContent):
                return block.text
        return ""

    async def internal_state(self) -> dict[str, object]:
        return json.loads(await self._call_text("read_game_state", {}))

    async def record_state(self, description: str, screenshot_sha256: str) -> str:
        return await self._call_text(
            "record_state",
            {"description": description, "screenshot_sha256": screenshot_sha256},
        )

    async def save_state(self, path: str) -> str:
        return await self._call_text("save_state", {"path": path})

    async def load_state(self, path: str) -> str:
        return await self._call_text("load_state", {"path": path})
