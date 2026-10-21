# fl-studio-bridge

The FL-side bridge used by **DSH WhaleSong for FL Studio**, retained from
[karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp) (MIT).

It contains only what the melody writer needs:

- `fl_controller/device_FLStudioMCP.py` — MIDI command bridge inside FL Studio.
- `scripts/ComposeWithLLM.pyscript` — Piano Roll note request executor.
- `src/fl_studio_mcp/utils/` — MIDI connection, serialized command file, and
  the background/foreground Piano Roll trigger.

The original 57-tool MCP server, its tool modules, and its installers are in
`archive/fl-v0-full/` at the repository root. They are not part of the v0
melody surface.

Local changes to the upstream bridge are listed in `VENDORED.md`.
