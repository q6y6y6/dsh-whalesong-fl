---
name: fl-melody
description: Use when the user asks to write a melody, hook, counter-line, or 8-bar idea into a specific FL Studio channel. Covers target readiness, key/tempo decisions, 8-bar pop piano phrasing, the three melody_* tools, append/replace, backup, and verification. Not for mixing, plugin loading, Playlist arrangement, rendering, or audio analysis.
---

# Write a melody into FL Studio

The MCP surface is only three tools:

- `melody_context(channel)` — readiness, target caption, pattern, tempo, current notes.
- `melody_write(channel, notes, mode="append", bars=8)` — backup, write, verify.
- `melody_restore(backup)` — restore one write.

FL writes to the **focused Piano Roll**. The user must open the target
channel's Piano Roll first. `melody_context` validates the focused editor
caption and refuses a mismatch; never guess or try to force focus.

## Workflow

1. Call `melody_context` with the channel name the user gave (for example
   `Piano`, `Keys`, `Synpluck Glass`).
2. If `ready` is false:
   - `No channel matching`: list the nearest channel names from the project and
     ask which one.
   - `ambiguous`: show the matches and ask for the exact name.
   - `Piano Roll is not focused` / caption mismatch: ask the user to open that
     channel's Piano Roll and stop. Do not write into whatever is focused.
3. Decide key, meter, tempo, and length:
   - Prefer values the user gave.
   - Otherwise use `context.tempo`, `context.beats_per_bar`, and
     `context.pattern_name` when available.
   - If the user names a reference song, use its key/meter/tempo as the default
     and say so. For JVKE "golden hour": E major, **6/8**, 63 dotted-quarter
     BPM (about 94.5 quarter-note BPM). Pass `beats_per_bar=3` to the tool.
   - Default to 8 bars. Ask at most one short question if key/meter is genuinely
     required and cannot be inferred.
4. Check `notes` in the context. If the Piano Roll already has notes, default to
   `mode="append"`; use `replace` only when the user asks to overwrite. A backup
   is created automatically either way.
5. Call `melody_write` with the complete note list in **one** call.
6. Report compactly: channel, pattern, bars, note count, pitch range, backup id.
   Do not solo, play, or render unless the user explicitly asks.

## Note format

```json
{"midi": 74, "start": 0.0, "duration": 0.75, "velocity": 0.62}
```

- `start` and `duration` are quarter-note beats, not seconds or ticks.
- `midi` 0–127; `velocity` 0.0–1.0.
- `bars` defaults to 8; `beats_per_bar` defaults to 4. For 6/8 pass
  `beats_per_bar=3`. The tool rejects notes past `bars * beats_per_bar`.
- Monophonic melody: avoid overlapping notes except deliberate legato.

## 8-bar pop piano melody rules

- Use a clear 2-bar motif, repeat it with variation in bars 3–4 and 7–8.
- Strong beats (1 and 3) land on chord tones; weak beats use passing/neighbor
  tones.
- Prefer stepwise motion; resolve larger leaps by step in the opposite direction.
- Keep a singable range, roughly one octave to an octave and a half (e.g.
  D4–A5, or C4–G5). Avoid continuous extremes.
- Mix note lengths: quarter/half anchors, eighth-note movement, occasional
  16th pickup. Leave rests so the phrase breathes.
- In 6/8, think two dotted-quarter pulses per bar. Put anchors on those pulses
  and use eighth-note pickups between them; avoid a square 4/4 pulse.
- Humanize velocity around 0.5–0.75; accent the phrase peak, soften pickups.
- End on a stable chord tone (root or fifth) with a longer note.

## Style card: JVKE "golden hour"

Verified against Hooktheory's TheoryTab (key E, meter 6, tempo 63, chorus
melody range C#4–B4, 1.23 beats/note, 83% chord tones, 99% diatonic):

- **Key**: E major. **Meter**: 6/8. **Tempo**: 63 dotted-quarter BPM
  (about 94.5 quarter-note BPM). In FL, pass `beats_per_bar=3`.
- **Harmony, verse/pre-chorus**: A9(add13) – G#m7(add11) – G+7(b9#11) –
  F#m7(add11) – E9. The signature is the chromatic descending line
  A–G#–G–F#–E; the G natural is not a mistake.
- **Harmony, chorus**: A9(add13) – Am9(add13) – E9 – V9/IV (A – Am – E – E/B).
  The borrowed Am (C natural) is the emotional turn.
- **Melody**: vocal, slow, and narrow. Mostly stepwise, 83% chord tones,
  loose syncopation, about 1.2 beats per note. Chorus range C#4–B4; lift to
  C#5/D#5 only at the peak. Long notes and rests, not a continuous arpeggio.
- **Piano**: 6/8 broken chords with wide voicing and pedal; the vocal line
  floats above. A melody-only write should imply this space through rhythm.
- **Do not**: use D-major 4/4 I–V–vi–IV, busy 8th/16th arpeggios, or wide
  D4–D6 leaps. Those produce a generic pop-piano sketch, not this song.

## Failure handling

- If `melody_write` returns `written: false`, do not retry blindly. Read the
  `error` / `warnings`:
  - target mismatch → ask the user to open the right Piano Roll;
  - script not consumed → ask the user to select `ComposeWithLLM` once;
  - note count mismatch → keep the backup, inspect the Piano Roll, then restore
    or retry once.
- If a write goes wrong, call `melody_restore` with the returned `backup_id`.

## Do not

- Do not mix, change plugins, arrange Playlist clips, render, or analyze audio.
- Do not call the archived full surface; it is not registered in this profile.
- Do not audition by default.
