"""Filesystem/MIDI bridge for the minimal melody writer.

This reuses the vendored karl v0 connection and ComposeWithLLM file bridge. It
does not expose the rest of the v0 tool surface.
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fl_studio_mcp.utils.connection import get_connection
from fl_studio_mcp.utils.fl_trigger import get_trigger, trigger_fl_studio

ROOT = Path(__file__).resolve().parents[4]
PIANO_ROLL_DIR = (
    Path.home()
    / "Documents"
    / "Image-Line"
    / "FL Studio"
    / "Settings"
    / "Piano roll scripts"
)
REQUEST = PIANO_ROLL_DIR / "mcp_request.json"
RESPONSE = PIANO_ROLL_DIR / "mcp_response.json"
STATE = PIANO_ROLL_DIR / "piano_roll_state.json"
BACKUP_DIR = ROOT / "backups" / "melody"


def read_state() -> dict[str, Any]:
    return json.loads(STATE.read_text(encoding="utf-8"))


def summarize_notes(notes: list[dict[str, Any]]) -> dict[str, Any]:
    if not notes:
        return {
            "count": 0,
            "pitch_min": None,
            "pitch_max": None,
            "start": None,
            "end": None,
            "last": [],
        }
    times = [float(note.get("time", 0.0)) for note in notes]
    pitches = [int(note.get("midi", 0)) for note in notes]
    ends = [
        float(note.get("time", 0.0)) + float(note.get("duration", 0.0))
        for note in notes
    ]
    return {
        "count": len(notes),
        "pitch_min": min(pitches),
        "pitch_max": max(pitches),
        "start": min(times),
        "end": round(max(ends), 3),
        "last": [
            {
                "midi": int(note.get("midi", 0)),
                "time": round(float(note.get("time", 0.0)), 3),
            }
            for note in notes[-3:]
        ],
    }


def _ocr_context(attempts: int = 2) -> dict[str, Any]:
    """Read-only fallback for a controller that has not been reloaded yet.

    A single screenshot can miss the header while FL is repainting. Retry the
    read twice; this never writes and never focuses FL.
    """
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    last_error = "Piano Roll header not found via OCR"
    for attempt in range(attempts):
        try:
            import ui_vision

            image = Path("/tmp/fl-melody-context.png")
            ui_vision.capture(image)
            hit = ui_vision.find_text(ui_vision.ocr(image), "钢琴卷帘")
            if hit is not None:
                return {
                    "available": True,
                    "focused_caption": hit["text"],
                    "focused_form_id": None,
                    "piano_roll_focused": True,
                    "pattern_number": None,
                    "pattern_name": "",
                    "tempo": None,
                    "beats_per_bar": None,
                    "source": "ocr",
                }
        except Exception as exc:  # noqa: BLE001
            last_error = f"OCR fallback failed: {exc}"
        if attempt + 1 < attempts:
            time.sleep(0.3)
    return {"available": False, "error": last_error}


def get_app_context() -> dict[str, Any]:
    result = get_connection().send_command("app.getContext", timeout=3.0)
    if result.get("error"):
        fallback = _ocr_context()
        fallback["controller_error"] = str(result["error"])
        return fallback
    return {
        "available": True,
        "focused_caption": result.get("focused_caption") or "",
        "focused_form_id": result.get("focused_form_id"),
        "piano_roll_focused": bool(result.get("piano_roll_focused")),
        "pattern_number": result.get("pattern_number"),
        "pattern_name": result.get("pattern_name") or "",
        "tempo": result.get("tempo"),
        "beats_per_bar": result.get("beats_per_bar"),
        "source": "controller",
    }


def get_channels() -> list[dict[str, Any]]:
    result = get_connection().send_command("channels.getAll", timeout=3.0)
    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    return list(result.get("channels") or [])


def resolve_channel(name: str) -> list[dict[str, Any]]:
    query = name.strip().casefold()
    if not query:
        return []
    channels = get_channels()
    exact = [channel for channel in channels if str(channel.get("name", "")).casefold() == query]
    if exact:
        return exact
    return [
        channel
        for channel in channels
        if query in str(channel.get("name", "")).casefold()
    ]


def validate_target(channel_name: str, context: dict[str, Any]) -> str | None:
    if not context.get("available"):
        return f"Controller context unavailable: {context.get('error')}"
    if not context.get("piano_roll_focused"):
        return "Piano Roll is not focused. Open the target channel's Piano Roll."
    caption = str(context.get("focused_caption") or "")
    if not caption:
        return "Could not read the focused editor caption."
    if channel_name.casefold() not in caption.casefold():
        return (
            f"Focused editor is {caption!r}, not {channel_name!r}. "
            "Open the target channel's Piano Roll."
        )
    return None


def create_backup(channel: str, context: dict[str, Any]) -> dict[str, str]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    data = {
        "id": backup_id,
        "channel": channel,
        "pattern": context.get("pattern_name"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notes": read_state().get("notes", []),
    }
    path = BACKUP_DIR / f"{backup_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"backup_id": backup_id, "backup_path": str(path.relative_to(ROOT))}


def load_backup(backup_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9-]+", backup_id):
        raise ValueError("backup id must be a timestamp such as 20261021-163000-123456")
    path = (BACKUP_DIR / f"{backup_id}.json").resolve()
    if path.parent != BACKUP_DIR.resolve():
        raise ValueError("backup path escapes the backup directory")
    if not path.is_file():
        raise ValueError(f"backup not found: {backup_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _requests(notes: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    mapped = [
        {
            "midi": int(note["midi"]),
            "time": float(note["time"]),
            "duration": float(note["duration"]),
            "velocity": float(note["velocity"]),
        }
        for note in notes
    ]
    requests: list[dict[str, Any]] = []
    if mode == "replace":
        requests.append({"action": "clear"})
    requests.append({"action": "add_notes", "notes": mapped})
    return requests


def send_notes(notes: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    REQUEST.parent.mkdir(parents=True, exist_ok=True)
    REQUEST.write_text(
        json.dumps(_requests(notes, mode), ensure_ascii=False), encoding="utf-8"
    )

    trigger = get_trigger()
    trigger_sent = trigger_fl_studio()
    deadline = time.time() + 4.0
    while time.time() < deadline:
        text = REQUEST.read_text(encoding="utf-8").strip() if REQUEST.exists() else ""
        if text in ("", "[]"):
            break
        time.sleep(0.1)

    text = REQUEST.read_text(encoding="utf-8").strip() if REQUEST.exists() else ""
    consumed = text in ("", "[]")
    try:
        response = json.loads(RESPONSE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        response = {}
    return {
        "trigger_sent": bool(trigger_sent),
        "verified": bool(trigger.last_verified),
        "consumed": consumed,
        "response": response,
    }


def restore_notes(notes: list[dict[str, Any]]) -> dict[str, Any]:
    mapped = [
        {
            "midi": int(note["midi"]),
            "time": float(note["time"]),
            "duration": float(note["duration"]),
            "velocity": float(note.get("velocity", 0.7)),
        }
        for note in notes
    ]
    return send_notes(mapped, mode="replace")
