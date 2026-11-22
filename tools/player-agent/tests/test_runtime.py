from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import player_agent
from player_agent import model as vision
from player_agent.cli import build_parser
from player_agent.model import (
    ModelError,
    Observation,
    PressAction,
    StopAction,
    VisionEndpoint,
    VisionPlayerModel,
    WaitAction,
    parse_observation,
)
from player_agent.runtime import PlayerRuntime, PlayerSettings, StepRecord

PNG_BYTES = b"\x89PNG\r\n\x1a\n-test-image"


class FakeGame:
    def __init__(self, screenshots: list[bytes]) -> None:
        self._screenshots = list(screenshots)
        self.presses: list[tuple[str, int]] = []
        self.state_requests = 0

    async def screenshot(self) -> bytes:
        return self._screenshots.pop(0) if len(self._screenshots) > 1 else self._screenshots[0]

    async def press(self, button: str, duration_ms: int) -> str:
        self.presses.append((button, duration_ms))
        return f"Pressed {button}"

    async def read_state(self) -> str:
        self.state_requests += 1
        return "State will be here"


class ScriptedModel:
    def __init__(self, observations: list[Observation]) -> None:
        self._observations = list(observations)
        self.histories: list[list[str]] = []

    async def observe_and_decide(self, screenshot: bytes, goal: str, history: list[str]) -> Observation:
        self.histories.append(list(history))
        return self._observations.pop(0)


class RuntimeTest(unittest.TestCase):
    def test_presses_waits_and_stops(self) -> None:
        game = FakeGame([PNG_BYTES])
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        model = ScriptedModel(
            [
                Observation("Title screen. PRESS START.", PressAction("start", 300)),
                Observation("Class menu. Samurai highlighted.", WaitAction(500)),
                Observation("Character sheet.", StopAction("goal reached")),
            ]
        )
        runtime = PlayerRuntime(game, model, PlayerSettings(goal="start"), sleep=fake_sleep)
        steps = asyncio.run(runtime.run())
        self.assertEqual(len(steps), 3)
        self.assertEqual(game.presses, [("start", 300)])
        self.assertEqual(sleeps, [0.5])
        self.assertIsInstance(steps[-1].action, StopAction)

    def test_history_is_passed_and_trimmed(self) -> None:
        game = FakeGame([PNG_BYTES])
        model = ScriptedModel(
            [
                Observation("one", PressAction("a", 100)),
                Observation("two", PressAction("b", 100)),
                Observation("three", StopAction("done")),
            ]
        )
        settings = PlayerSettings(goal="goal", max_turns=5, history_size=2)
        asyncio.run(PlayerRuntime(game, model, settings).run())
        self.assertEqual(model.histories[0], [])
        self.assertIn("pressed b", model.histories[2])
        self.assertLessEqual(len(model.histories[2]), 2)

    def test_max_turns_bounds_the_loop(self) -> None:
        game = FakeGame([PNG_BYTES])
        model = ScriptedModel([Observation("idle", WaitAction(1)) for _ in range(4)])
        settings = PlayerSettings(goal="goal", max_turns=3)
        steps = asyncio.run(PlayerRuntime(game, model, settings).run())
        self.assertEqual(len(steps), 3)

    def test_transcript_and_screenshots_are_written(self) -> None:
        game = FakeGame([PNG_BYTES])
        model = ScriptedModel(
            [
                Observation("Title screen. PRESS START.", PressAction("start", 300)),
                Observation("Class menu.", StopAction("done")),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            settings = PlayerSettings(goal="start a game", max_turns=4, transcript_directory=Path(directory))
            steps = asyncio.run(PlayerRuntime(game, model, settings).run())
            self.assertEqual(len(steps), 2)
            self.assertTrue((Path(directory) / "screenshots" / "turn-001.png").exists())
            self.assertTrue((Path(directory) / "screenshots" / "turn-002.png").exists())
            jsonl = (Path(directory) / "transcript.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(jsonl[0])["action"]["type"], "press")
            self.assertEqual(json.loads(jsonl[0])["mcp_state"], "State will be here")
            self.assertEqual(json.loads(jsonl[1])["action"]["type"], "stop")
            markdown = (Path(directory) / "transcript.md").read_text(encoding="utf-8")
            self.assertIn("Goal: start a game", markdown)
            self.assertIn("MCP read_state: State will be here", markdown)
            self.assertIn("Title screen. PRESS START.", markdown)
            self.assertEqual(game.state_requests, 2)


class ParseObservationTest(unittest.TestCase):
    def test_parses_fenced_json(self) -> None:
        text = '```json\n{"screen": "Menu. New Game highlighted.", "action": {"type": "press", "button": "A"}}\n```'
        observation = parse_observation(text)
        self.assertEqual(observation.description, "Menu. New Game highlighted.")
        self.assertEqual(observation.action, PressAction("a", 150))

    def test_rejects_missing_description(self) -> None:
        with self.assertRaises(ModelError):
            parse_observation('{"action": {"type": "stop", "reason": "x"}}')

    def test_rejects_unknown_action(self) -> None:
        with self.assertRaises(ModelError):
            parse_observation('{"screen": "x", "action": {"type": "jump"}}')

    def test_rejects_unknown_button(self) -> None:
        with self.assertRaises(ModelError):
            parse_observation('{"screen": "x", "action": {"type": "press", "button": "jump"}}')

    def test_stop_without_reason_is_allowed(self) -> None:
        observation = parse_observation('{"screen": "x", "action": {"type": "stop"}}')
        self.assertEqual(observation.action, StopAction(""))


class EndpointTest(unittest.TestCase):
    def test_environment_configuration(self) -> None:
        previous = dict(os.environ)
        try:
            os.environ["PLAYER_VISION_API_KEY"] = "key"
            os.environ["PLAYER_VISION_MODEL"] = "vision-model"
            os.environ["PLAYER_VISION_BASE_URL"] = "http://localhost:9/v1"
            endpoint = VisionEndpoint.from_environment()
            self.assertEqual(endpoint.completion_url(), "http://localhost:9/v1/chat/completions")
            self.assertEqual(endpoint.key_source, "environment")
        finally:
            os.environ.clear()
            os.environ.update(previous)

    def test_deepseek_defaults(self) -> None:
        previous = dict(os.environ)
        try:
            for name in list(os.environ):
                if name.startswith("PLAYER_VISION_") or name.startswith("OPENAI_"):
                    os.environ.pop(name)
            os.environ["PLAYER_VISION_OPENCODE_AUTH"] = str(self._auth_file("deepseek", "abc"))
            endpoint = VisionEndpoint.from_environment()
            self.assertEqual(endpoint.model, "deepseek-chat")
            self.assertEqual(endpoint.completion_url(), "https://api.deepseek.com/v1/chat/completions")
            self.assertEqual(endpoint.api_key, "abc")
            self.assertEqual(endpoint.key_source, "opencode-auth/deepseek")
        finally:
            os.environ.clear()
            os.environ.update(previous)

    def test_missing_configuration_is_reported(self) -> None:
        previous = dict(os.environ)
        try:
            for name in list(os.environ):
                if name.startswith("PLAYER_VISION_") or name.startswith("OPENAI_"):
                    os.environ.pop(name)
            os.environ["PLAYER_VISION_OPENCODE_AUTH"] = str(Path(tempfile.gettempdir()) / "missing-auth.json")
            with self.assertRaises(ModelError):
                VisionEndpoint.from_environment()
        finally:
            os.environ.clear()
            os.environ.update(previous)

    @staticmethod
    def _auth_file(provider: str, key: str) -> Path:
        handle, name = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        path = Path(name)
        path.write_text(json.dumps({provider: {"type": "api", "key": key}}), encoding="utf-8")
        return path

    def test_request_carries_the_screenshot(self) -> None:
        endpoint = VisionEndpoint(base_url="http://localhost:1/v1", api_key="k", model="m")
        request = VisionPlayerModel(endpoint).build_request(PNG_BYTES, "start a game", ["turn 1: title"])
        messages = request["messages"]
        user_content = messages[1]["content"]
        image_url = user_content[1]["image_url"]["url"]
        self.assertTrue(image_url.startswith("data:image/png;base64,"))
        self.assertIn("start a game", user_content[0]["text"])
        self.assertIn("turn 1: title", user_content[0]["text"])
        self.assertEqual(request["model"], "m")


class RecordingHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, object]] = []
    response_text = json.dumps({"screen": "Title screen. PRESS START.", "action": {"type": "stop", "reason": "done"}})

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        RecordingHandler.requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "body": json.loads(self.rfile.read(length)),
            }
        )
        payload = {"choices": [{"message": {"content": RecordingHandler.response_text}}]}
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *arguments: object) -> None:
        return


class VisionModelTest(unittest.TestCase):
    def setUp(self) -> None:
        RecordingHandler.requests = []
        self.http_server = ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        self.thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.http_server.server_address[1]

    def tearDown(self) -> None:
        self.http_server.shutdown()
        self.http_server.server_close()

    def test_posts_the_image_and_parses_the_answer(self) -> None:
        endpoint = VisionEndpoint(
            base_url=f"http://127.0.0.1:{self.port}/v1",
            api_key="secret",
            model="vision-test",
        )
        observation = asyncio.run(VisionPlayerModel(endpoint).observe_and_decide(PNG_BYTES, "start", ["turn 1: x"]))
        self.assertEqual(observation.action, StopAction("done"))
        self.assertEqual(observation.description, "Title screen. PRESS START.")
        request = RecordingHandler.requests[0]
        self.assertEqual(request["path"], "/v1/chat/completions")
        self.assertEqual(request["authorization"], "Bearer secret")
        self.assertEqual(request["body"]["model"], "vision-test")


class CliTest(unittest.TestCase):
    def test_requires_a_goal(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args([])

    def test_defaults(self) -> None:
        arguments = build_parser().parse_args(["--goal", "win"])
        self.assertEqual(arguments.turns, 24)
        self.assertEqual(arguments.transcript, "")


if __name__ == "__main__":
    unittest.main()
