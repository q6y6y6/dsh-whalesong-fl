"""Minimal FL Studio melody-writer MCP server.

Three tools only: context/readiness, write, restore. The controller and
ComposeWithLLM bridge are the vendored karl v0 implementation.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from .bridge import (
    create_backup,
    get_app_context,
    get_trigger,
    load_backup,
    read_state,
    resolve_channel,
    restore_notes,
    send_notes,
    summarize_notes,
    validate_target,
)

mcp = FastMCP(
    name="fl-melody",
    instructions="""
FL Studio melody writer. Call melody_context first and use its target/pattern
information. melody_write refuses to run unless the focused Piano Roll belongs
to the requested channel. Notes use quarter-note beats. Do not audition, mix,
load plugins, arrange, or render.
""",
)


def _resolve_target(channel: str) -> tuple[dict[str, Any] | None, dict[str, Any], str | None]:
    matches = resolve_channel(channel)
    context = get_app_context()
    if not matches:
        return None, context, f"No channel matching {channel!r}."
    if len(matches) > 1:
        names = [match["name"] for match in matches]
        return None, context, f"Channel name is ambiguous: {names}."
    target = matches[0]
    error = validate_target(str(target["name"]), context)
    return target, context, error


def _normalise_notes(
    notes: list[dict[str, Any]], bars: int, beats_per_bar: float
) -> tuple[list[dict[str, Any]], list[str]]:
    if not notes:
        raise ValueError("notes must not be empty")
    if not 1 <= bars <= 64:
        raise ValueError("bars must be between 1 and 64")
    if not 1.0 <= beats_per_bar <= 12.0:
        raise ValueError("beats_per_bar must be between 1 and 12")
    mapped: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, note in enumerate(notes):
        try:
            midi = int(note["midi"])
            start = float(note.get("start", note.get("time", 0.0)))
            duration = float(note["duration"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"note {index} needs midi, start, and duration") from exc
        if not 0 <= midi <= 127:
            raise ValueError(f"note {index} midi must be 0..127")
        if start < 0 or duration <= 0:
            raise ValueError(f"note {index} needs start >= 0 and duration > 0")
        if start + duration > bars * beats_per_bar + 1e-6:
            raise ValueError(
                f"note {index} ends at beat {start + duration:.2f}, beyond "
                f"{bars} bars of {beats_per_bar:g} beats"
            )
        velocity = float(note.get("velocity", 0.7))
        if not 0.0 <= velocity <= 1.0:
            raise ValueError(f"note {index} velocity must be 0.0..1.0")
        mapped.append(
            {
                "midi": midi,
                "time": start,
                "duration": duration,
                "velocity": velocity,
            }
        )

    ordered = sorted(mapped, key=lambda item: item["time"])
    for previous, current in zip(ordered, ordered[1:]):
        if (
            current["time"] < previous["time"] + previous["duration"] - 0.011
            and abs(current["time"] - previous["time"]) > 0.001
        ):
            warnings.append("notes overlap; confirm this is legato rather than a chord")
            break
    return mapped, warnings


@mcp.tool()
def melody_context(channel: str) -> dict[str, Any]:
    """Read readiness, target channel, pattern, tempo, and current note summary.

    A write is allowed only when the focused Piano Roll caption contains the
    requested channel name. This tool never focuses or activates FL.
    """
    matches = resolve_channel(channel)
    context = get_app_context()
    state = read_state()
    result: dict[str, Any] = {
        "ready": False,
        "channel_query": channel,
        "matches": [match["name"] for match in matches],
        "context": context,
        "notes": summarize_notes(state.get("notes", [])),
        "trigger_supported": get_trigger().is_supported,
    }
    if not matches:
        result["error"] = f"No channel matching {channel!r}."
        return result
    if len(matches) > 1:
        result["error"] = "Channel name is ambiguous."
        return result
    target = matches[0]
    error = validate_target(str(target["name"]), context)
    result["target"] = target
    result["error"] = error
    result["ready"] = error is None
    return result


@mcp.tool()
def melody_write(
    channel: str,
    notes: list[dict[str, Any]],
    mode: str = "append",
    bars: int = 8,
    beats_per_bar: float = 4.0,
) -> dict[str, Any]:
    """Write one melody into the focused Piano Roll of `channel`.

    `notes` are `{midi, start, duration, velocity}` in quarter-note beats.
    `mode` is append or replace. `beats_per_bar` is 4 for 4/4 and 3 for 6/8.
    The existing notes are backed up first, and the receipt reports whether the
    script consumed the request and the note count changed as expected.
    """
    if mode not in ("append", "replace"):
        return {"written": False, "error": "mode must be append or replace"}
    try:
        target, context, error = _resolve_target(channel)
        if error:
            return {"written": False, "error": error}
        assert target is not None
        mapped, warnings = _normalise_notes(notes, bars, beats_per_bar)
    except Exception as exc:  # noqa: BLE001 - surface a typed failure to the model
        return {"written": False, "error": str(exc)}

    before = summarize_notes(read_state().get("notes", []))
    backup = create_backup(str(target["name"]), context)
    result = send_notes(mapped, mode)
    after = summarize_notes(read_state().get("notes", []))
    expected = len(mapped) if mode == "replace" else before["count"] + len(mapped)
    written = bool(result["consumed"] and after["count"] == expected)
    if not result["verified"]:
        warnings.append("trigger was sent but no bridge file changed")
    if not written:
        warnings.append(
            "note count did not match; keep the backup and check the target Piano Roll"
        )
    return {
        "written": written,
        "channel": target["name"],
        "pattern": context.get("pattern_name"),
        "pattern_number": context.get("pattern_number"),
        "mode": mode,
        "bars": bars,
        "beats_per_bar": beats_per_bar,
        "notes_written": len(mapped),
        "note_count_before": before["count"],
        "note_count_after": after["count"],
        "pitch_range": [after["pitch_min"], after["pitch_max"]],
        "backup_id": backup["backup_id"],
        "backup_path": backup["backup_path"],
        "warnings": warnings,
    }


@mcp.tool()
def melody_restore(backup: str) -> dict[str, Any]:
    """Restore a previous melody_write backup into its original channel."""
    try:
        data = load_backup(backup)
        target, context, error = _resolve_target(str(data.get("channel", "")))
        if error:
            return {"restored": False, "error": error}
        assert target is not None
        notes = list(data.get("notes") or [])
        result = restore_notes(notes)
        after = summarize_notes(read_state().get("notes", []))
        restored = bool(result["consumed"] and after["count"] == len(notes))
        return {
            "restored": restored,
            "channel": target["name"],
            "pattern": context.get("pattern_name"),
            "notes_restored": len(notes),
            "note_count_after": after["count"],
            "warnings": [] if restored else ["restore was not confirmed"],
        }
    except Exception as exc:  # noqa: BLE001
        return {"restored": False, "error": str(exc)}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
