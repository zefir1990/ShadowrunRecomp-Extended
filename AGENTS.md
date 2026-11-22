# AGENTS.md - AI Agent Guide

Project-specific instructions for AI agents working on this Shadowrun
recompilation.

## What this is

A native Windows x64 port of **Shadowrun (Sega Genesis, 1994)** built with
`segagenesisrecomp`. The 68000 code is statically translated to C and runs
against the shared Genesis runtime. The cartridge ROM remains the source of all
game data.

This is an experimental research port. It is not a finished game.

## Repository layout

| Path | Purpose |
| --- | --- |
| `game/shadowrun.bin` | ROM image the build consumes. Git-ignored. Four-class image, CRC32 `93B0D845` |
| `game/game.toml` | Recompiler configuration for this port |
| `game/shadowrun_spec.c` | GameSpec, CRC pin, VBlank hook, Mage spell filter |
| `patches/rom/Shadowrun (USA) 1995 Four Classes.ips` | Binary IPS patch for the stock USA dump |
| `scripts/apply-rom-patch.ps1` | Applies that IPS to a stock dump with hash checks and writes `game/shadowrun.bin` |
| `patches/*.patch` | Engine patches, applied by `scripts/apply-framework-patches.ps1` |
| `segagenesisrecomp/` | Engine submodule (pinned `9cbfe88`, m68k core `6f705f2`) |
| `build/` | CMake build tree, executable, `debug.ini`, generated sources |
| `build/generated/shadowrun/` | Generated C copied out of the generation stage. Never edit by hand |
| `build/generation-stage/shadowrun/` | Raw recompiler output, same rule |
| `tools/genesis-mcp/` | MCP server that drives the running game |
| `tools/player-agent/` | Autonomous player: screenshots plus a vision model drive the pad |
| `game-wiki/` | Weapons and character reference notes |
| `docs/` | Run, ROM patch, runner, validation and milestone notes |
| `scripts/` | Build, patch, validation and autotest scripts |

## Hard rules

1. **Do not edit generated files.** `build/generated/shadowrun/*` and
   `build/generation-stage/shadowrun/*` are produced from `game/shadowrun.bin`
   and `game/game.toml`. Change the ROM or the config and rebuild instead.
2. **Prefer game-owned code.** Put behavior in `game/shadowrun_spec.c` or
   `game/game.toml`. Do not modify `segagenesisrecomp/` unless the task needs an
   engine fix, and then record it as a patch in `patches/`.
3. **Never overwrite the original ROM.** Keep the stock dump untouched; patch a
   copy. `scripts/apply-rom-patch.ps1` refuses any input that is not the known
   stock or patched image.
4. **Keep ROM identity consistent.** The patch already pins the header checksum
   at `0x18E` to `0xBE5C`; `expected_rom_crc32` in `game/shadowrun_spec.c` must
   match `game/shadowrun.bin` (`93B0D845`). Re-verify both after any ROM change.
5. **Document ROM changes.** Record offsets and meanings in
   `docs/ROM-PATCH.md`, not in the README.
6. **No code comments.** Use clear, self-documenting names and decomposition.
7. **Keep documents ASCII-only.** The markdown files are ASCII for Windows
   compatibility.
8. **Verify by running.** A successful build is not enough. Run the game and
   check exit codes, logs, screenshots and RAM state.
9. **Use `C:\git\cmd\git.exe`.** Git is not on `PATH`; the portable install
   lives at `C:\git`.

## Current build state

- ROM: `game/shadowrun.bin`, a copy of the stock USA dump with the IPS applied.
- CRC32: `93B0D845`; SHA-1 `2F0FFB4C402972A183C936C17A10E9941123AC07`.
- Header checksum at `0x18E`: `0xBE5C`.
- Engine pin: `segagenesisrecomp 9cbfe88`, m68k core `6f705f2`.
- Engine `9cbfe88` includes YM2612 timer A. Do not downgrade to an engine that
  only implements timer B; Shadowrun music depends on timer A.
- Four classes: Samurai, Decker, Shaman, Mage.
- Shaman: original Gator Shaman template, archetype `1`, Gator Totem `0x2A`,
  shaman spells allowed.
- Mage: archetype `0`, Power Focus `0x18`, Trent portrait `0x0007241A`,
  Mana Zap level 4, shaman spells and shaman focus items blocked.
- Ricky's hire template is overwritten by the Mage class template. This is a
  known side effect.

## Preparing the ROM

The stock dump is never modified in place:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\apply-rom-patch.ps1 -Rom "C:\roms\Shadowrun (USA).gen"
```

The script verifies the stock CRC32/SHA-1 before patching, verifies the result
against the pin, and writes `game/shadowrun.bin`. Re-running it on an already
patched image is safe; `-Out` changes the destination.

For a new ROM change:

1. Copy the current ROM to a new file.
2. Patch the bytes.
3. Recompute the header checksum over words from `0x200` to the end and store
   it big-endian at `0x18E`.
4. Print the new CRC32 and SHA-1.
5. Update the IPS in `patches/rom/` and the identities in
   `scripts/apply-rom-patch.ps1`.
6. Update `expected_rom_crc32` in `game/shadowrun_spec.c`.
7. Rebuild and rerun the verification commands.
8. Update `docs/ROM-PATCH.md` and `patches/README.md`.

## Build

Use the local MinGW-w64 toolchain under `C:\mingw64\bin`. It carries `gcc`,
`g++`, `cmake` and `mingw32-make`.

```powershell
$env:Path = "C:\mingw64\bin;" + $env:Path
cd C:\Users\Ilia\Sources\ShadowrunRecomp-Extended

cmake -S . -B build -G "MinGW Makefiles" `
    -DCMAKE_MAKE_PROGRAM=C:/mingw64/bin/mingw32-make.exe `
    -DCMAKE_C_COMPILER=C:/mingw64/bin/gcc.exe `
    -DCMAKE_CXX_COMPILER=C:/mingw64/bin/g++.exe `
    -DCMAKE_BUILD_TYPE=Release `
    -DSHADOWRUN_ENABLE_TRACE=ON
cmake --build build -j 12
```

`-DSHADOWRUN_ENABLE_TRACE=ON` is required for the TCP debug server: without it
the build links `runner/cmd_server_stub.c` and nothing listens on port 4378.
`-DGENESIS_NATIVE_IPO=OFF` keeps link time short when iterating.

The CMake helper regenerates C when the ROM or `game.toml` changes, and copies
`SDL2.dll` next to the executable. The MinGW runtime DLLs
(`libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `libwinpthread-1.dll`) come from
`C:\mingw64\bin`, so either keep that directory on `PATH` or copy them into
`build/`.

## Run and verify

```powershell
cd C:\Users\Ilia\Sources\ShadowrunRecomp-Extended
build\ShadowrunRecomp.exe game\shadowrun.bin --no-launcher
```

All runs should exit `0`. The windowed path should report Direct3D 11 and
48 kHz audio on stderr. After boot the log must contain:

```
[cmd] Listening on 127.0.0.1:4378
```

That line only appears when `debug.ini` exists next to the executable (see the
MCP section). The runner also supports `--input-script` with `WAIT`, `PRESS`,
`WRITE_RAM8`, `DUMP_RAM`, `SCREENSHOT` and `EXIT`; the scripts live in
`scripts/*.input`.

## MCP server

`tools/genesis-mcp` is an MCP stdio server that drives the running window:

```powershell
python -m pip install -r tools\genesis-mcp\requirements.txt
python -m unittest discover -s tools\genesis-mcp\tests -v
```

| Tool | Behavior |
| --- | --- |
| `press_button(button, duration_ms)` | Holds a pad button (`up`, `down`, `left`, `right`, `a`, `b`, `c`, `start`), sleeps, releases, reports the frame span |
| `screenshot()` | Returns the current screen as a PNG image |
| `read_state()` | Text description of the screen: cached, described on demand, or `State will be here` |
| `record_state(description, screenshot_sha256)` | Stores a description keyed by the screenshot hash |
| `read_game_state()` | Emulator snapshot for the current frame as JSON: m68k, Z80, VDP, pad input |

It talks to the runner's debug command server, so the game must run from a trace
build with a `debug.ini` next to the executable:

```ini
port=4378
```

Keys the server sends: `set_input` with a hex mask (`40` = A, `80` = Start) and
`off` to release, `screenshot` with a path, `frame_info` for the frame number.
Paths must use forward slashes: the runner's JSON reader copies string values
verbatim and does not unescape `\\`. The oracle build listens on `4379`; the
server accepts `GENESIS_DEBUG_HOST` and `GENESIS_DEBUG_PORT`.

Keep the tool contract: `read_state` returns a text description of the current
screen - cached for an identical frame, generated by the vision model for a new
one, and the placeholder `State will be here` only when no model is configured.
Matching is exact (PNG SHA-256); do not add fuzzy matching, because two menus that
differ by one word look nearly identical to any coarse hash. `screenshot` must keep
returning actual image content rather than text. Descriptions enter the store
through `record_state(description, screenshot_sha256)`; the player agent calls it
for every turn, which is what lets `read_state` answer without a second model call.

## Player agent

`tools/player-agent` is an autonomous player built on top of the MCP server. Each
turn it captures a screenshot, sends it to a vision model, parses the returned
`{"screen": ..., "action": ...}` JSON, and presses the chosen button. Every turn
is stored with its screenshot:

```powershell
cd tools\player-agent
python -m player_agent --goal "start a new game" --turns 20 --transcript runs\demo
```

The default provider is DeepSeek (`deepseek-chat`); the key comes from
`PLAYER_VISION_API_KEY`, `OPENAI_API_KEY`, or the `deepseek` entry in the
opencode auth store. `PLAYER_VISION_MODEL`, `PLAYER_VISION_BASE_URL` and
`PLAYER_VISION_PROVIDER` override that. The description is produced from the
screenshot by the vision model; the runtime also records it through
`record_state`, so the MCP store learns every screen it has described. The
transcript lands in
`screenshots/turn-NNN.png`, `transcript.jsonl` and `transcript.md`, and each
record carries the current `read_state` answer (the stored description for that
screen, or the placeholder `State will be here`), the `read_game_state` snapshot
(frame, A7, Z80 PC, display, pad) and the screenshot SHA-256 used to register the
description, next to the description read from the same screenshot.
Tests use fake game and model objects, so they need no ROM and no API key:
`python -m unittest discover -s tools\player-agent\tests`.

The runtime also detects crashes while it plays: an MCP call that stops answering,
a frame counter that stops advancing for four turns, or a changed
`build/last_error.log` end the session with exit code `3` and write a
`crash-*.md` report with the last turn, the screenshot path and the runner log
tails. Pass `--stderr-log build\game-stderr.log --crash-log build\last_error.log`
so the report can quote them.

## Important addresses

### Class selection

Class templates use a `0x100` stride starting at `0x7291A`:

| Index | Class | Address |
| --- | --- | --- |
| 0 | Samurai | `0x7291A` |
| 1 | Decker | `0x72A1A` |
| 2 | Shaman | `0x72B1A` |
| 3 | Mage | `0x72C1A` |

Template fields:

| Offset | Meaning |
| --- | --- |
| `+0x50` | 32-bit portrait block pointer |
| `+0x59` | Name field |
| `+0x6D` | Starting inventory item |
| `+0x77..+0x7C` | Body, Quickness, Strength, Charisma, Intelligence, Willpower |
| `+0x7F` | Sorcery skill |
| `+0x9A` | Race byte |
| `+0x9B` | Archetype byte: `0` Mage, `1` Shaman, `2` Samurai, `3` Decker |

Archetype menu:

- Text string: `0x1B64F0`
- Selectable count: `MOVEQ #3,D3` at `0x592A2` (`0x592A3 = 0x03`)
- Menu cursor RAM: `0xFFF0DC`
- Selected index RAM: `0xFFF0AE`

Character-info name table:

- Race table base: `0xD19C7`, 6-byte entries, `0xFF` terminated
- Archetype table base: `0xD19E5`, 8-byte entries, `0xFF` terminated

### Portrait blocks

Portrait blocks are `0xA0` bytes. The class/runner record stores a 32-bit
pointer at `+0x50`.

- Samurai: `0x720FA`
- Shaman / Ricky: `0x7219A`
- Decker: `0x7223A`
- Trent (Human Mage): `0x7241A`

### Mage runtime hook

In `game/shadowrun_spec.c`, `shadowrun_apply_mage_start()` is called from
`shadowrun_call_vblank()`.

- Character pointer: 32-bit big-endian at `0xFFFC04`
- Archetype check: `character + 0x9B == 0` (Mage only)
- Spellbook count: `0xFF1EFB` (`0` means one spell)
- Spell entries: `0xFF1EFC`, two bytes each: spell ID, level
- Inventory slots: `0xFFF21B`, eight bytes

Blocked shaman spell IDs:

```
00 Flame Dart   01 Flame Bolt   02 Hellblast
03 Invisibility 04 Sleep        05 Stink
0C Confusion    0D Barrier
```

Blocked shaman focus items:

```
19 Flame Dart SF  1A Flame Bolt SF  1B Hellblast SF
1C Invisibility SF 1D Sleep SF      1E Stink SF
25 Confusion SF   26 Barrier SF
```

If no spells remain, the hook grants Mana Zap level 4 (`07 04`).

The hook runs every VBlank and is idempotent. The Shaman archetype is not
filtered.

## Docs

- `README.md` - build, run and modification overview
- `docs/ROM-PATCH.md` - ROM offsets and class table
- `docs/RUNNER.md`, `docs/SDL-FRONTEND.md` - runner and frontend notes
- `STATUS.md` - known WIP gameplay issues
- `game-wiki/WEAPONS.md`, `game-wiki/CHARACTERS.md` - game reference
- `tools/genesis-mcp/README.md` - MCP setup and wire protocol
- `patches/README.md` - engine and ROM patch inventory

## Windows-specific notes

- Git lives at `C:\git`; invoke `C:\git\cmd\git.exe` or add `C:\git\cmd` to
  `PATH`. `git status <path>` is invalid: use `git -C <path> status`.
- Use `Start-Process` with quoted paths for ROMs containing spaces.
- If the executable exits with `0xC0000135`, the MinGW runtime DLLs are missing
  from `PATH` and from the executable directory.
- CMake 4.x emits a deprecation warning for SDL2 2.28.5's
  `cmake_minimum_required`. It is harmless.
- The linker reports an `.rsrc` manifest merge warning from the launcher UI; the
  executable is still produced.

## Legal and distribution

- The ROM is user-supplied and must not be redistributed.
- Do not publish built executables that contain translated game code.
- Do not publish `patches/rom/*.ips` outside this local copy: it carries
  ROM-derived bytes.
- The recompiler and integration code are PolyForm Noncommercial 1.0.0 with the
  additional permissions in `PERMISSIONS.md`.
- Shadowrun is a trademark of The Topps Company / FASA; the game is
  (c) SEGA. This project is not affiliated with or endorsed by any rights
  holder.
