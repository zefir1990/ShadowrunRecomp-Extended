# Starting inside an in-game dialog

The runner can boot directly into a conversation instead of replaying the intro
and the menus. The game still boots its VDP, font and sound driver, then the
runner copies the first Samurai template into the first party slot and calls the
game's conversation dispatcher.

## Configuration

The settings live in `debug.ini` next to `ShadowrunRecomp.exe`. `settings.ini`
is read first and `debug.ini` overrides it, so either file can carry the keys:

```ini
dialog_start=true
dialog_id=0
dialog_start_frame=120
```

| Key | Meaning |
| --- | --- |
| `dialog_start` | `true`, `yes`, `on` or `1` enables the direct dialog start |
| `dialog_id` | catalog index, `0xSSEE` scene/event pair, or `0xNNNNNN` node address |
| `dialog_start_frame` | guest frames to wait before the dialog opens; default 120 |

The frame delay is deliberate. The game must finish its VDP and font setup; a
dialog requested before that draws a black screen. Frame 120 is about two
seconds and is the earliest point that renders correctly.

## Dialog IDs

A decimal `dialog_id` is an index into `shadowrun_dialog_catalog[]` in
`game/shadowrun_dialogs.c`. The table below is generated from the game's
conversation dispatcher (`func_01FD80`), so it covers every fixed scene dialog
the dispatcher can open. Id `0` is the test case: the Hollywood Correctional
Facility gate.

| ID | Dialog | Node | Actor |
| --- | --- | --- | --- |
| 0 | Hollywood Correctional Facility gate | `0x1113D2` | `0x122030` |
| 1 | Tribal council building | `0x0F4B4C` | `0x121E14` |
| 2 | Elven guard gate | `0x11B5D8` | `0x122024` |
| 3 | Package delivery | `0x110AC2` | `0x122024` |
| 4 | Package pickup | `0x110ABA` | `0x122024` |
| 5 | Icarus Descending restaurant | `0x110A96` | `0x122024` |
| 6 | Guard package delivery | `0x110AD2` | `0x121F34` |
| 7 | Guard package pickup | `0x110ACA` | `0x121F34` |
| 8 | Matchstick nightclub | `0x110ADA` | `0x121F34` |
| 9 | Guard package inspection | `0x11139A` | `0x12209C` |
| 10 | Guard package handoff | `0x111392` | `0x12209C` |
| 11 | Mitsuhama office | `0x110CB2` | `0x12209C` |
| 12 | Fuchi guard package delivery | `0x110B7E` | `0x122090` |
| 13 | Fuchi guard package pickup | `0x110B76` | `0x122090` |
| 14 | Fuchi Industrial Electronics | `0x110B86` | `0x122090` |
| 15 | Bartender package delivery | `0x110B6E` | `0x1220B4` |
| 16 | Bartender package pickup | `0x110B66` | `0x1220B4` |
| 17 | Space Needle | `0x110B5E` | `0x1220B4` |
| 18 | Package delivery | `0x110EFA` | `0x121F70` |
| 19 | Package pickup | `0x110EF2` | `0x121F70` |
| 20 | Roscoe the fixer | `0x111934` | `0x121F70` |
| 21 | Ghoul building | `0x11C40A` | `0x121E20` |
| 22 | Friendship Restaurant owner | `0x110F12` | `0x121EEC` |
| 23 | Friendship Restaurant waitress | `0x110F0A` | `0x121EEC` |
| 24 | Friendship Restaurant | `0x110F02` | `0x121EEC` |
| 25 | Passport Lodge package delivery | `0x110D3E` | `0x121F34` |
| 26 | Passport Lodge package pickup | `0x110D36` | `0x121F34` |
| 27 | Passport Lodge | `0x110D46` | `0x121F34` |
| 28 | Ork Embassy package delivery | `0x110F5E` | `0x122054` |
| 29 | Ork Embassy package pickup | `0x110F56` | `0x122054` |
| 30 | Ork Embassy Building | `0x110F1A` | `0x122054` |
| 31 | Club Penumbra package delivery | `0x110C5E` | `0x121F40` |
| 32 | Club Penumbra package pickup | `0x110C42` | `0x121F40` |
| 33 | Club Penumbra | `0x110C7A` | `0x121F40` |
| 34 | Fuchi package delivery | `0x111382` | `0x122090` |
| 35 | Fuchi package pickup | `0x11137A` | `0x122090` |
| 36 | Fuchi office entrance | `0x110C9E` | `0x122090` |
| 37 | Mitsuhama package delivery | `0x110BBE` | `0x12209C` |
| 38 | Mitsuhama package pickup | `0x110BA2` | `0x12209C` |
| 39 | Mitsuhama Downtown office | `0x110BD2` | `0x12209C` |
| 40 | Eye-Fiver warehouse package delivery | `0x110C0A` | `0x122018` |
| 41 | Eye-Fiver warehouse package pickup | `0x110BEE` | `0x122018` |
| 42 | Eye-Fiver warehouse | `0x110C26` | `0x122018` |
| 43 | The Big Rhino package delivery | `0x110CE2` | `0x122060` |
| 44 | The Big Rhino package pickup | `0x110CCE` | `0x122060` |
| 45 | The Big Rhino | `0x110CC6` | `0x122060` |
| 46 | Lone Star package delivery | `0x110F82` | `0x122084` |
| 47 | Lone Star package pickup | `0x110F7A` | `0x122084` |
| 48 | Lone Star Security | `0x110F66` | `0x122084` |
| 49 | Ares package delivery | `0x111676` | `0x1220C0` |
| 50 | Ares package pickup | `0x11166E` | `0x1220C0` |
| 51 | Ares Macrotechnology | `0x110DBE` | `0x1220C0` |
| 52 | The Wanderer package delivery | `0x11165E` | `0x121E50` |
| 53 | The Wanderer package pickup | `0x111656` | `0x121E50` |
| 54 | The Wanderer | `0x110DA2` | `0x121E50` |
| 55 | The Wanderer | `0x110DB6` | `0x121E50` |
| 56 | Underground 93 package delivery | `0x110DEE` | `0x122060` |
| 57 | Underground 93 package pickup | `0x110DDA` | `0x122060` |
| 58 | Underground 93 | `0x110E02` | `0x122060` |
| 59 | Ork gang package delivery | `0x110E4A` | `0x122054` |
| 60 | Ork gang package pickup | `0x110E36` | `0x122054` |
| 61 | Ork gang hideout | `0x110E5E` | `0x122054` |
| 62 | Hollywood guard package delivery | `0x1114A2` | `0x122030` |
| 63 | Hollywood guard package pickup | `0x11149A` | `0x122030` |
| 64 | Shiawase Atomics Nuclear Plant | `0x110D0A` | `0x122030` |
| 65 | Jump House package delivery | `0x1114BA` | `0x121EBC` |
| 66 | Jump House package pickup | `0x1114B2` | `0x121EBC` |
| 67 | The Jump House | `0x110D1E` | `0x121EBC` |
| 68 | Halloweener package delivery | `0x1114D2` | `0x121E38` |
| 69 | Halloweener package pickup | `0x1114CA` | `0x121E38` |
| 70 | The Jackal's Lantern | `0x110D26` | `0x121E38` |
| 71 | Elven package delivery | `0x1114E2` | `0x122024` |
| 72 | Lone Star grunt | `0x1114DA` | `0x122024` |
| 73 | Lone Star cordon | `0x110D2E` | `0x122024` |
| 74 | Abandoned shack | `0x110D72` | `0x121E38` |
| 75 | Halloweener package pickup | `0x11155E` | `0x121E38` |
| 76 | Abandoned shack | `0x110D86` | `0x121E38` |
| 77 | Frag Grenade package delivery | `0x1117FA` | `0x121E8C` |
| 78 | Frag Grenade package pickup | `0x1117F2` | `0x121E8C` |
| 79 | The Frag Grenade | `0x110E96` | `0x121E8C` |
| 80 | Renraku package delivery | `0x1117CE` | `0x121F88` |
| 81 | Renraku package pickup | `0x1117B2` | `0x121F88` |
| 82 | Renraku Computer Systems | `0x110E82` | `0x121F88` |
| 83 | Tribal council building | `0x0F4B68` | `0x121E14` |

### Raw addresses

`dialog_id=0x0200` sets the dispatcher scene byte `$FFFBF8 = 0x02` and event byte
`$FFFBF9 = 0x00`, then calls `func_01FD80`. This is the same path the game uses
when gameplay enters a location. `dialog_id=0x1113D2` calls the conversation
engine directly with the catalog actor for that node, which is useful for a node
that is not in the table.

## Implementation

- `game/shadowrun_dialogs.c` owns the catalog, the `debug.ini` parser, the
  Samurai setup and the dispatcher call.
- `game/shadowrun_spec.c` wires `shadowrun_dialogs_maybe_start()` to
  `GameSpec.call_periodic`.
- `segagenesisrecomp/runner/glue.c` calls `GameSpec.call_periodic` at a
  cycle-budget yield, on the game fiber. This is required because the dialog
  engine busy-waits for VBlank and cannot run inside the atomic VBlank handler.
  The change is recorded in `patches/0006-runner-game-periodic-hook.patch`.

## Testing

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-dialog.ps1 -DialogId 0
powershell -ExecutionPolicy Bypass -File scripts\validate-dialog-start.ps1 -DialogId 0
```

The validation script writes `build\debug.ini`, runs 400 frames, checks for the
`[dialog] id=0 ...` log line, the `[dialog] start node=$1113D2` line, a PNG in
`build\shots` and a clean exit, then restores the previous `debug.ini`.
