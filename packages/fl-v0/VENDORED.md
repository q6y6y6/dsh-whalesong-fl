# Vendored: karl-andres/fl-studio-mcp

- Upstream: https://github.com/karl-andres/fl-studio-mcp
- Commit: `202b7a2` (tarball snapshot, 2026-10-20)
- License: MIT (see `LICENSE`)
- Purpose: the bridge subset used by `fl-melody` — MIDI connection, serialized
  command/response files, the FL controller, and the Piano Roll pyscript.

## Local changes

1. `src/fl_studio_mcp/utils/midi_connection.py`
   - Added an `RLock` around `send_command`. FL uses one command file and one
     response file, so overlapping calls could otherwise overwrite each other.
   - Added `ping()`, which sends `transport.getStatus` and waits for a real FL
     response.
   - Raised the default command timeout from 2 s to 5 s.
2. `src/fl_studio_mcp/utils/connection.py`
   - Added `FLConnection.ping()` and the same 5 s default.
3. `fl_controller/device_FLStudioMCP.py`
   - Added `app.getContext` (focused caption, pattern, tempo, meter) so the
     melody writer can refuse a wrong target.
   - The original tool handlers remain in this file.
4. `src/fl_studio_mcp/utils/fl_trigger.py`
   - Activate FL by bundle id (`com.image-line.flstudio`) instead of the
     hardcoded name `FL Studio`; current installs are `FL Studio 2026`.
   - Post Cmd+Opt+Y directly to FL's PID with `CGEventPostToPid`, then verify a
     bridge-file change. This avoids stealing focus from DSH.
   - Fall back to activating FL and clicking the Piano Roll header only when the
     background key changes nothing.
   - Return False when the AppleScript exits non-zero instead of always
     claiming success.
5. `pyproject.toml`
   - Removed the unused MCP server entry point and `fastmcp` dependency.
   - Added `pyobjc-framework-Quartz` on macOS for the focus/background key.

Feature work belongs in `packages/fl-melody`, not in this vendored bridge
subset.
