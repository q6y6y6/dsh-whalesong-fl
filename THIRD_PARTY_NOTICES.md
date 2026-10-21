# Third-party notices

This project builds on and/or vendors the following open-source projects.
Their licenses apply to the corresponding files; this project's own code is
licensed under `LICENSE`.

## karl-andres/fl-studio-mcp

- Source: https://github.com/karl-andres/fl-studio-mcp
- License: MIT
- V0 vendors only the bridge subset at `packages/fl-v0/` (connection,
  trigger, controller, and pyscript); see `packages/fl-v0/LICENSE`.
- The original 57-tool server and installers are archived under
  `archive/fl-v0-full/` and are not part of the v0 commit.
- Local modifications are listed in `packages/fl-v0/VENDORED.md`.

## synopsys0/postfader-fl-studio-mcp

- Source: https://github.com/synopsys0/postfader-fl-studio-mcp
- License: Apache-2.0
- Archived under `archive/fl-core/`; not part of v0. The Apache-2.0 `LICENSE`
  and `NOTICE` files are preserved in that archive.

## Boyan253/fl-studio-2025-ai-bridge

- Source: https://github.com/Boyan253/fl-studio-2025-ai-bridge
- License: MIT
- Not vendored; its Playlist `globalTransport` notes are a design reference
  kept in the archived research docs.

## DSH / DeepSeek Harness

- Source: https://github.com/deepseek-ai/deepseek-harness
- License: MIT (per upstream repository)
- Used as the host, not vendored.
