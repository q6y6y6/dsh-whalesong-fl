# WhaleSong v0 — melody-only

Scope: given a target channel and a musical idea, write an 8-bar melody into
the focused Piano Roll. Nothing else.

## Surface

| Tool | Read/write | Purpose |
|---|---|---|
| `melody_context(channel)` | read | target match, focused caption, pattern, tempo, current notes |
| `melody_write(channel, notes, mode, bars, beats_per_bar)` | write | backup, append/replace, verify |
| `melody_restore(backup)` | write | restore one write |

Measured: **3 tools, ~1.4 KB of schemas**. The 57-tool debug server is archived
under `archive/fl-v0-full/` and is not part of this version.

## Target rule

The user opens the target channel's Piano Roll. `melody_context` reads the
focused editor caption:

- primary: controller `app.getContext` (caption, pattern, tempo);
- fallback: OCR of the FL window until the controller is reloaded.

`melody_write` refuses when the caption does not contain the requested channel
name. It never guesses or forces focus.

## Evidence (2026-10-21)

| Check | Result |
|---|---|
| Default profile module | `fl_melody.server` |
| Tool count | 3 |
| 8-bar 6/8 E-major write (Piano Wide) | noteCount 50 → 24, 24 beats, C#4–C#5 |
| Older 8-bar 4/4 draft | kept in backup `20261021-084352-107334` |
| Append marker round-trip | 93 → 95 → 93 |
| Target mismatch | refused by caption check |
| Focus during write | DSH stayed frontmost; FL not activated |
| Doctor | PASS (melody surface) |

The 8-bar test and restore used the disposable `test project` at
`~/Documents/Image-Line/FL Studio/Projects/test project/test project.flp`.
Backups are under `backups/melody/`.

## Style accuracy

The first draft used D major, 4/4, and a busy arpeggio. That was wrong for JVKE
"golden hour". Hooktheory's TheoryTab (key E, meter 6, tempo 63, chorus melody
C#4–B4, 1.23 beats/note, 83% chord tones) shows the actual shape:

- E major, 6/8, 63 dotted-quarter BPM (about 94.5 quarter-note BPM).
- Verse descent A9(add13) – G#m7(add11) – G+7(b9#11) – F#m7(add11) – E9.
- Chorus A9(add13) – Am9(add13) – E9 – V9/IV; the borrowed C natural matters.
- Vocal-like melody: long notes, stepwise, narrow range, not an arpeggio.

`melody_write` now takes `beats_per_bar` (4 default, 3 for 6/8). The replacement
draft for Piano Wide is 24 notes over 24 beats (8 bars of 6/8), C#4–C#5, and
keeps the previous 50-note draft in backup `20261021-084352-107334`.

If the FL project stays in 4/4, the same 24 beats display as six 4/4 bars; set
the project meter to 6/8 to see the intended eight bars.

## Known limitation

The controller command `app.getContext` is deployed but FL has not reloaded the
script yet. Until the user re-selects `FLStudioMCP` in FL's MIDI Settings,
`melody_context` returns `source: ocr`, with `tempo`, `beats_per_bar`, and
`pattern_name` empty. Target validation and writes still work.

After reload, the same call returns `source: controller` plus the current
pattern, tempo, and meter.

## Usage

```bash
.venv/bin/python scripts/melody_smoke.py --channel "Piano Wide"
```

Or in DSH:

> 我创建了一个 Piano Wide 通道，请为我在其中写一个 8 小节的旋律，风格类似 JVKE 的《golden hour》。

The model loads the `fl-melody` skill, calls `melody_context`, composes, calls
`melody_write` once, and reports the pattern, note count, pitch range, and
backup id. No audition, mixing, plugin loading, Playlist, or rendering.
