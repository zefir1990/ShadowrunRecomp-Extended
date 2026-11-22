# player-agent

An autonomous player for ShadowrunRecomp. It drives the game through the
`genesis-mcp` server, captures a screenshot every turn, asks a vision model for a
text description of that screenshot plus the next action, and performs the
action. Each turn is recorded with its screenshot, so a run leaves a readable
trail of what the agent saw and did.

It uses `read_state` not at all: the MCP server's `read_state` is still a
placeholder, so the description comes from the screenshot through the model.

## Loop

```
screenshot (PNG from MCP)
    -> vision model: {"screen": "<facts about this frame>", "action": <action>}
    -> runtime presses the button / waits / stops
    -> transcript + screenshots on disk
```

The system prompt requires the model to transcribe every readable string
verbatim, name the screen type and the highlighted option, and never invent text
or numbers. Anything unreadable has to be reported as unreadable.

## Requirements

```powershell
python -m pip install -r tools\player-agent\requirements.txt
```

A vision-capable chat model behind an OpenAI-compatible `/chat/completions`
endpoint. The default is DeepSeek (`deepseek-chat`), whose API accepts `image_url`
content: the key is read from `PLAYER_VISION_API_KEY`/`OPENAI_API_KEY`, or from
the opencode auth store (`~/.local/share/opencode/auth.json`, provider
`deepseek`). Text-only models cannot describe the screenshot.

| Variable | Meaning |
| --- | --- |
| `PLAYER_VISION_API_KEY` (or `OPENAI_API_KEY`) | API key; falls back to the opencode auth store |
| `PLAYER_VISION_MODEL` (or `OPENAI_MODEL`) | vision model name, default `deepseek-chat` |
| `PLAYER_VISION_BASE_URL` (or `OPENAI_BASE_URL`) | endpoint root; DeepSeek and OpenAI roots are picked from the model name |
| `PLAYER_VISION_PROVIDER` | provider in the opencode auth store, default `deepseek` |
| `PLAYER_VISION_OPENCODE_AUTH` | alternate `auth.json` path |
| `PLAYER_VISION_TIMEOUT` | request timeout in seconds, default `60` |

Model notes from live runs: `deepseek-chat` read the title-screen copyright lines
and the `Start Options` menu verbatim. `deepseek-v4-pro` rejects images and
`deepseek-flash` returned empty content, so keep the default.

The MCP server needs the game running from a trace build with `debug.ini`
(`port=4378`) next to the executable; see `tools/genesis-mcp/README.md`.

## Run

```powershell
cd tools\player-agent
python -m player_agent --goal "start a new game as Samurai and leave the apartment" --turns 30 --transcript runs\apartment
```

No key export is needed when opencode already has the `deepseek` provider signed
in; the CLI prints which source it used. Run it from `tools\player-agent` or put
that directory on `PYTHONPATH`.

| Flag | Meaning |
| --- | --- |
| `--goal` | what the agent tries to do; required |
| `--turns` | observation budget, default 24 |
| `--transcript` | output directory; omit to keep everything in memory |
| `--server` | alternate `genesis-mcp/server.py` |
| `--base-url`, `--api-key`, `--model`, `--timeout` | override the environment |

## Crash detection

The runtime watches for a dead or stuck runner while it plays:

| Signal | Detection |
| --- | --- |
| runner stopped answering | any MCP call raises (`connection refused`, closed stdio stream) |
| runner froze | `read_game_state` frame stays the same for 4 turns |
| runner wrote a crash report | `last_error.log` changes on disk (`crash_report_dump_persistent`) |

Any of these ends the run with exit code `3` and writes
`crash-YYYYMMDD-HHMMSS.md` next to the transcript. The report records the last
turn's frame, action, description and screenshot path, plus the tail of the
runner stderr log and `last_error.log`.

```powershell
python -m player_agent --goal "..." --turns 80 `
  --transcript runs\bar `
  --stderr-log build\game-stderr.log `
  --crash-log build\last_error.log
```

A clean run exits `0`; a model or key failure exits `2`.

## Stuck detection

A hang is not a process crash: the runner keeps answering and the frame counter
keeps advancing, but the screen never changes again (a dialog that ignores input,
a frozen animation, a spin on a device). `player_agent.stuck_watch` watches the
rendered screen instead:

```powershell
python -m player_agent.stuck_watch --out runs\prison-watch --seconds 12 --probe a
```

- screenshots every 0.5 s and hashes them;
- unchanged for `--seconds`: writes `stuck-<timestamp>.md` and the matching PNG;
- with `--probe`, presses that button once and reports whether the screen reacted
  (`recovered after the probe` means static but alive; `still identical` means a
  real hang).

Use it while playing manually; it only presses the probe button when it is about
to report.

`scripts\run-monitored.ps1` covers the other failure mode: it launches the game,
records its exit code and stderr, and writes a report under `build\crash-reports`
when the process dies or `last_error.log` appears.

## Output

```
runs\apartment\
  screenshots\turn-001.png ... turn-030.png
  transcript.jsonl      one record per turn: description, mcp_state, internal_state, action, screenshot path
  transcript.md         the same trail as prose
```

Each turn pairs three views of the same moment: the screenshot, the model's
description of it, and the emulator snapshot from `read_game_state` (frame, A7,
Z80 PC, display, pad). The runtime registers the description with
`record_state`, so the `read_state` it takes right after returns the same text
from the cache; when the screen moved between the capture and the call, that
`read_state` describes the newer frame instead of reusing stale text. Records
carry the screenshot SHA-256 used for the match.

Actions are exactly one of:

```json
{"type": "press", "button": "a", "duration_ms": 150}
{"type": "wait", "duration_ms": 500}
{"type": "stop", "reason": "goal reached"}
```

Buttons are the eight pad inputs: `up`, `down`, `left`, `right`, `a`, `b`, `c`,
`start`. The runtime rejects unknown buttons, durations outside 1..60000 ms and
any action type the model invents.

## Code map

| File | Responsibility |
| --- | --- |
| `player_agent/game.py` | MCP client wrapper: `screenshot`, `press`, `read_state` || `player_agent/model.py` | vision request, strict JSON parsing, action validation |
| `player_agent/runtime.py` | observe/decide/act loop, history window, transcript |
| `player_agent/cli.py` | argument parsing and wiring |

## Tests

```powershell
python -m unittest discover -s tools\player-agent\tests -v
```

The suite fakes both the game and the model, and covers the HTTP request shape
against a local test server, so it needs neither a ROM nor an API key.
