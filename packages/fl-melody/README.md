# DSH WhaleSong · fl-melody

The v0 minimal surface: three MCP tools for writing a melody into a channel's
focused Piano Roll.

```text
melody_context(channel)                              readiness + target check
melody_write(channel, notes, mode, bars, beats_per_bar)  backup, write, verify
melody_restore(backup)                                restore a previous write
```

It reuses the vendored karl bridge (`packages/fl-v0`) and `ComposeWithLLM`. It
does not expose the other tools, does not mix, load plugins, arrange, render, or
audition.

## Target rule

The user must open the target channel's Piano Roll. `melody_context` reads the
focused editor caption from the controller (`app.getContext`) and refuses a
write if the caption does not contain the requested channel name. It never
guesses or steals focus to fix the target.

The controller patch adds `app.getContext`; after deploying it, re-select
`FLStudioMCP` in FL's MIDI Settings once so FL loads the new script. Until then
the server uses a read-only OCR fallback for the caption.

## Run

```bash
uv pip install --python .venv/bin/python -e packages/fl-v0
uv pip install --python .venv/bin/python -e packages/fl-melody
.venv/bin/python -m fl_melody.server
```

The DSH bundle points `serverName: fl` at this module.

## Note format

`notes` is a list of `{midi, start, duration, velocity}`:

- `start` and `duration` are quarter notes (beats), not seconds or ticks.
- `midi` is 0–127; `velocity` is 0.0–1.0 (default 0.7).
- `bars` defaults to 8; `beats_per_bar` defaults to 4 and is 3 for 6/8.
  Notes beyond `bars * beats_per_bar` are rejected.

Backups are written to `backups/melody/` in the project root and returned as a
`backup_id` suitable for `melody_restore`.
