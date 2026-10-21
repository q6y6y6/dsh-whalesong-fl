#!/usr/bin/env python3
"""End-to-end smoke test for the three-tool melody surface.

    .venv/bin/python scripts/melody_smoke.py --channel "Piano"

The target channel's Piano Roll must already be focused. The test appends two
high marker notes, verifies the note-count delta, then restores the pre-write
backup. It leaves the project unchanged on success.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from fastmcp import Client
from fl_melody.server import mcp


async def run(channel: str) -> tuple[int, dict]:
    async with Client(mcp) as client:
        context = json.loads(
            (await client.call_tool("melody_context", {"channel": channel})).content[0].text
        )
        if not context.get("ready"):
            return 2, {"stage": "context", "context": context}

        before = int(context["notes"]["count"])
        start = max(60.0, float(context["notes"].get("end") or 0.0) + 4.0)
        bars = min(64, max(16, int((start + 2.0) / 4.0) + 1))
        if start + 1.0 > bars * 4:
            return 2, {"stage": "layout", "error": "Piano Roll is too long for the marker"}
        notes = [
            {"midi": 108, "start": start, "duration": 0.25, "velocity": 0.2},
            {"midi": 110, "start": start + 0.5, "duration": 0.25, "velocity": 0.2},
        ]
        write = json.loads(
            (
                await client.call_tool(
                    "melody_write",
                    {
                        "channel": channel,
                        "notes": notes,
                        "mode": "append",
                        "bars": bars,
                    },
                )
            ).content[0].text
        )
        if not write.get("written"):
            return 1, {"stage": "write", "write": write}

        restore = json.loads(
            (
                await client.call_tool(
                    "melody_restore", {"backup": write["backup_id"]}
                )
            ).content[0].text
        )
        ok = bool(restore.get("restored")) and int(
            restore.get("note_count_after", -1)
        ) == before
        return (0 if ok else 1), {
            "stage": "done",
            "before": before,
            "after_write": write.get("note_count_after"),
            "after_restore": restore.get("note_count_after"),
            "write": write,
            "restore": restore,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default="Piano")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    code, result = asyncio.run(run(args.channel))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[{'PASS' if code == 0 else 'FAIL'}] melody smoke: {args.channel}")
        if result.get("stage") == "context":
            print(json.dumps(result["context"], ensure_ascii=False, indent=2))
        elif result.get("stage") == "done":
            print(
                f"  noteCount {result['before']} -> {result['after_write']} -> "
                f"{result['after_restore']}"
            )
            print(f"  backup: {result['write'].get('backup_id')}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
