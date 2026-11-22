from __future__ import annotations

import asyncio
import json
import os
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TOOL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TOOL_ROOT not in sys.path:
    sys.path.insert(0, TOOL_ROOT)

import server
import state_store
from debug_link import DebugEndpoint, GenesisDebugLink
from genesis_pad import button_mask, normalize_button
from state_store import StateStore

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def encode_test_png(width: int, height: int) -> bytes:
    def chunk(chunk_type: bytes, payload: bytes) -> bytes:
        body = chunk_type + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = bytearray()
    for _ in range(height):
        raw.append(0)
        raw.extend(bytes(width * 3))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw)))
        + chunk(b"IEND", b"")
    )


class FakeDebugServer:
    def __init__(self) -> None:
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)
        self.port = self._listener.getsockname()[1]
        self.commands: list[dict[str, object]] = []
        self.frame = 100
        self.image = encode_test_png(8, 4)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        connection, _ = self._listener.accept()
        with connection:
            for line in connection.makefile("rb"):
                command = json.loads(line)
                self.commands.append(command)
                response: dict[str, object] = {"id": command["id"], "ok": True}
                if command["cmd"] == "frame_info":
                    response["current_frame"] = self.frame
                elif command["cmd"] == "get_frame":
                    response.update(
                        {
                            "frame": command["frame"],
                            "m68k": {"PC": 4660, "SR": 0},
                            "vdp": {"display": 1, "vint": 1},
                        }
                    )
                elif command["cmd"] == "read_joypad_port":
                    response["buttons"] = "0x00"
                elif command["cmd"] in {"save_state", "load_state"}:
                    response["path"] = command["path"]
                elif command["cmd"] == "screenshot":
                    with open(str(command["path"]), "wb") as image_file:
                        image_file.write(self.image)
                connection.sendall((json.dumps(response) + "\n").encode("utf-8"))
        self._listener.close()

    def input_commands(self) -> list[dict[str, object]]:
        return [command for command in self.commands if command["cmd"] == "set_input"]


class ButtonTableTest(unittest.TestCase):
    def test_button_names_are_case_insensitive(self) -> None:
        self.assertEqual(button_mask("A"), 0x40)
        self.assertEqual(button_mask(" start "), 0x80)
        self.assertEqual(normalize_button("Down"), "down")

    def test_unknown_button_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            button_mask("jump")


class LinkTest(unittest.TestCase):
    def test_unreachable_server_reports_the_endpoint(self) -> None:
        closed_port = self._closed_port()
        endpoint = DebugEndpoint(host="127.0.0.1", port=closed_port)
        with self.assertRaises(RuntimeError) as raised:
            with GenesisDebugLink(endpoint):
                pass
        self.assertIn(f"127.0.0.1:{closed_port}", str(raised.exception))

    @staticmethod
    def _closed_port() -> int:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        return port


class PressButtonTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_server = FakeDebugServer()
        os.environ["GENESIS_DEBUG_PORT"] = str(self.fake_server.port)

    def tearDown(self) -> None:
        os.environ.pop("GENESIS_DEBUG_PORT", None)

    def test_press_holds_then_releases(self) -> None:
        started = time.monotonic()
        message = server.press_button("a", 80)
        elapsed_ms = (time.monotonic() - started) * 1000.0
        commands = self.fake_server.input_commands()
        self.assertGreaterEqual(elapsed_ms, 75.0)
        self.assertEqual([command["keys"] for command in commands], ["40", "off"])
        self.assertIn("Pressed A for 80 ms", message)

    def test_duration_is_bounded(self) -> None:
        with self.assertRaises(ValueError):
            server.press_button("a", 0)
        with self.assertRaises(ValueError):
            server.press_button("a", 60_001)


class ScreenshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_server = FakeDebugServer()
        os.environ["GENESIS_DEBUG_PORT"] = str(self.fake_server.port)

    def tearDown(self) -> None:
        os.environ.pop("GENESIS_DEBUG_PORT", None)

    def test_returns_the_captured_png(self) -> None:
        image = server.screenshot()
        self.assertEqual(image.to_image_content().mime_type, "image/png")
        self.assertEqual(image.data, self.fake_server.image)
        requested = [command for command in self.fake_server.commands if command["cmd"] == "screenshot"]
        self.assertEqual(len(requested), 1)
        self.assertTrue(str(requested[0]["path"]).endswith("screen.png"))

    def test_capture_file_is_removed(self) -> None:
        image = server.screenshot()
        captured_path = next(
            str(command["path"])
            for command in self.fake_server.commands
            if command["cmd"] == "screenshot"
        )
        self.assertEqual(image.data[:8], PNG_SIGNATURE)
        self.assertFalse(os.path.exists(captured_path.replace("/", os.sep)))


class DescriptionHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        self.rfile.read(length)
        payload = {"choices": [{"message": {"content": "Generated description."}}]}
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *arguments: object) -> None:
        return


class ReadStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        os.environ["GENESIS_STATE_STORE"] = str(Path(self.directory.name) / "states.json")
        os.environ["PLAYER_VISION_OPENCODE_AUTH"] = str(Path(self.directory.name) / "auth.json")
        self.fake_server = FakeDebugServer()
        os.environ["GENESIS_DEBUG_PORT"] = str(self.fake_server.port)

    def tearDown(self) -> None:
        for name in list(os.environ):
            if name.startswith("PLAYER_VISION_") or name.startswith("GENESIS_"):
                os.environ.pop(name, None)
        self.directory.cleanup()

    def new_game_server(self) -> None:
        self.fake_server = FakeDebugServer()
        os.environ["GENESIS_DEBUG_PORT"] = str(self.fake_server.port)

    def test_placeholder_when_no_model_and_no_cache(self) -> None:
        self.assertEqual(server.read_state(), "State will be here")

    def test_returns_the_description_recorded_for_the_same_screenshot(self) -> None:
        digest = state_store.digest_png(self.fake_server.image)
        server.record_state("Title screen with PRESS START.", digest)
        self.new_game_server()
        self.assertEqual(server.read_state(), "Title screen with PRESS START.")

    def test_describes_a_new_screen_then_answers_from_cache(self) -> None:
        endpoint_server = ThreadingHTTPServer(("127.0.0.1", 0), DescriptionHandler)
        threading.Thread(target=endpoint_server.serve_forever, daemon=True).start()
        port = endpoint_server.server_address[1]
        os.environ["PLAYER_VISION_API_KEY"] = "key"
        os.environ["PLAYER_VISION_MODEL"] = "vision-test"
        os.environ["PLAYER_VISION_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
        try:
            self.assertEqual(server.read_state(), "Generated description.")
        finally:
            endpoint_server.shutdown()
            endpoint_server.server_close()
        os.environ.pop("PLAYER_VISION_API_KEY")
        self.new_game_server()
        self.assertEqual(server.read_state(), "Generated description.")

    def test_rejects_an_empty_description(self) -> None:
        with self.assertRaises(ValueError):
            server.record_state("   ", "0" * 64)

    def test_rejects_a_bad_digest(self) -> None:
        with self.assertRaises(ValueError):
            server.record_state("text", "not-a-digest")


class StateStoreTest(unittest.TestCase):
    def test_entries_survive_a_new_instance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "states.json"
            first = StateStore(path)
            first.remember("a" * 64, "menu screen")
            self.assertEqual(StateStore(path).lookup("a" * 64), "menu screen")
            self.assertIsNone(StateStore(path).lookup("b" * 64))

    def test_oldest_entries_are_evicted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / "states.json")
            for index in range(state_store.MAXIMUM_ENTRIES + 5):
                store.remember(f"{index:064x}", f"state {index}")
            self.assertEqual(len(json.loads((Path(directory) / "states.json").read_text())["entries"]), state_store.MAXIMUM_ENTRIES)


class GameStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_server = FakeDebugServer()
        os.environ["GENESIS_DEBUG_PORT"] = str(self.fake_server.port)

    def tearDown(self) -> None:
        os.environ.pop("GENESIS_DEBUG_PORT", None)

    def test_returns_registers_vdp_and_input_as_json(self) -> None:
        state = json.loads(server.read_game_state())
        self.assertEqual(state["m68k"]["PC"], 4660)
        self.assertEqual(state["vdp"]["display"], 1)
        self.assertEqual(state["input"]["buttons"], "0x00")
        self.assertNotIn("id", state)
        self.assertNotIn("ok", state)


class StateFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_server = FakeDebugServer()
        os.environ["GENESIS_DEBUG_PORT"] = str(self.fake_server.port)

    def tearDown(self) -> None:
        os.environ.pop("GENESIS_DEBUG_PORT", None)

    def test_save_and_load_forward_the_path(self) -> None:
        self.assertIn("saved", server.save_state(r"C:\states\dialog.state"))
        saved = [command for command in self.fake_server.commands if command["cmd"] == "save_state"]
        self.assertEqual(saved[0]["path"], "C:/states/dialog.state")
        self.fake_server = FakeDebugServer()
        os.environ["GENESIS_DEBUG_PORT"] = str(self.fake_server.port)
        self.assertIn("loaded", server.load_state(r"C:\states\dialog.state"))
        loaded = [command for command in self.fake_server.commands if command["cmd"] == "load_state"]
        self.assertEqual(loaded[0]["path"], "C:/states/dialog.state")


class ToolRegistrationTest(unittest.TestCase):
    def test_all_tools_are_exposed(self) -> None:
        tools = {tool.name: tool for tool in asyncio.run(server.server.list_tools())}
        self.assertEqual(
            set(tools),
            {
                "press_button",
                "read_state",
                "screenshot",
                "read_game_state",
                "record_state",
                "save_state",
                "load_state",
            },
        )
        self.assertEqual(set(tools["press_button"].input_schema.get("properties", {})), {"button", "duration_ms"})
        self.assertEqual(tools["read_state"].input_schema.get("properties", {}), {})
        self.assertEqual(tools["screenshot"].input_schema.get("properties", {}), {})
        self.assertEqual(tools["read_game_state"].input_schema.get("properties", {}), {})
        self.assertEqual(
            set(tools["record_state"].input_schema.get("properties", {})),
            {"description", "screenshot_sha256"},
        )
        self.assertEqual(set(tools["save_state"].input_schema.get("properties", {})), {"path"})
        self.assertEqual(set(tools["load_state"].input_schema.get("properties", {})), {"path"})


if __name__ == "__main__":
    unittest.main()
