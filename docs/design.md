# Design — WhaleSong v0

```text
DSH (desktop/web)
├── skill: fl-melody
├── DSH bundle: dsh-whalesong-fl
│   └── @deepseek-ai/dsh-mcp-client  →  stdio
└── fl-melody (3 tools)
    ├── melody_context  → target/readiness, pattern, tempo, note summary
    ├── melody_write    → backup, append/replace, verify
    └── melody_restore  → restore one write
          │
          └── fl-studio-bridge (packages/fl-v0)
              ├── MIDI command file + trigger note
              ├── device_FLStudioMCP.py inside FL
              └── ComposeWithLLM.pyscript in the focused Piano Roll
```

## Target validation

The user opens the target channel's Piano Roll. `melody_context` reads the
focused editor caption:

- primary: controller `app.getContext` (caption, pattern, tempo, meter);
- fallback: OCR of the FL window until the controller is reloaded.

`melody_write` refuses when the caption does not contain the requested channel.
It never guesses or steals focus.

## Write path

1. Create a backup under `backups/melody/`.
2. Write one JSON request: optional `clear`, then all notes.
3. Trigger `ComposeWithLLM` with Cmd+Opt+Y posted directly to FL's PID.
4. Wait for the request file to be consumed and read the new state.
5. Compare the note-count delta with the expected count.
6. Return a compact receipt with `written`, counts, pitch range, pattern, and
   `backup_id`.

If the postcondition fails, the write is reported as failed and the backup is
kept. No automatic retry.

## Why three tools

A general DAW control surface exposes dozens of tools and tens of kilobytes of
schemas. This workflow only needs context, write, and restore. Keeping the
surface at three tools:

- reduces resident schema to ~1.4 KB;
- keeps the model focused on one task;
- avoids exposing mixing, plugin, Playlist, and render operations that v0 does
  not support well.

## Boundary

v0 does not change tempo, project meter, patterns, mixer, plugins, Playlist, or
render. A 6/8 melody written into a 4/4 project displays as six 4/4 bars; set
the meter/tempo in FL for the intended feel.
