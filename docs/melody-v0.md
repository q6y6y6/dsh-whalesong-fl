# WhaleSong v0 — melody-only

Scope: given a target channel and a musical idea, write an 8-bar melody into
the focused Piano Roll. Nothing else.

## Surface

| Tool | Read/write | Purpose |
|---|---|---|
| `melody_context(channel)` | read | target match, focused caption, pattern, tempo, current notes |
| `melody_write(channel, notes, mode, bars, beats_per_bar)` | write | backup, append/replace, verify |
| `melody_restore(backup)` | write | restore one write |

Measured: **3 tools, ~1.4 KB of schemas**. No other control surface is included.

## Target rule

The user opens the target channel's Piano Roll. `melody_context` reads the
focused editor caption:

- primary: controller `app.getContext` (caption, pattern, tempo, meter);
- fallback: OCR of the FL window when the controller has not been reloaded.

`melody_write` refuses when the caption does not contain the requested channel.
It never guesses or forces focus.

## Validation

- 8-bar 6/8 write: 24 notes over 24 beats, C#4–C#5.
- Append marker round-trip: note count increases and returns to the original.
- Target mismatch: refused by the caption check.
- Focus: DSH stayed frontmost; FL was not activated.
- Doctor: PASS for the three-tool surface.

Tests use a disposable project. Backups are written under `backups/melody/`
and are not part of the repository.

## Reference style

An early draft used D major, 4/4, and a busy arpeggio. The tested reference is a
slow 6/8 pop ballad:

- E major, 6/8, 63 dotted-quarter BPM (about 94.5 quarter-note BPM).
- Verse with a chromatic descending bass; chorus with a borrowed minor iv.
- Vocal-like melody: long notes, stepwise motion, narrow range, about 1.2
  beats per note.
- Piano: 6/8 broken chords with wide voicing; the melody floats above.

`melody_write` takes `beats_per_bar` (4 default, 3 for 6/8). If the FL project
stays in 4/4, the same 24 beats display as six 4/4 bars; set the project meter
to 6/8 to see the intended eight bars.

## Known limitation

If the controller command `app.getContext` is unavailable, `melody_context`
returns `source: ocr`, with `tempo`, `beats_per_bar`, and `pattern_name` empty.
Target validation and writes still work. After reloading the controller, the
same call returns the pattern, tempo, and meter.

## Usage

```bash
.venv/bin/python scripts/melody_smoke.py --channel "Piano"
```

Or in DSH:

> 我创建了一个 Piano 通道，请为我在其中写一个 8 小节的旋律，风格类似一首慢速 6/8 流行钢琴曲。

The model loads the `fl-melody` skill, calls `melody_context`, composes, calls
`melody_write` once, and reports the pattern, note count, pitch range, and
backup id. No audition, mixing, plugin loading, Playlist, or rendering.
