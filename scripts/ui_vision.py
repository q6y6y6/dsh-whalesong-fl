#!/usr/bin/env python3
"""Small macOS UI-vision helpers for FL Studio.

This is the read-only visual fallback: capture one window, OCR it with Vision,
then click the center of a recognized text box. Coordinates are derived from
the recognized text, not guessed. Keep coordinate fallbacks explicit and last.

Requires the workspace virtualenv (pyobjc-framework-Quartz) and the macOS
Command Line Tools (swiftc) for the one-time OCR binary build.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import Quartz

ROOT = Path(__file__).resolve().parents[1]
OCR_SOURCE = ROOT / "scripts" / "visual_ocr.swift"
OCR_BINARY = ROOT / ".cache" / "visual_ocr"
FL_OWNER = "FL Studio"


def fl_window() -> dict[str, Any]:
    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly
        | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    candidates = [
        window
        for window in windows
        if window.get("kCGWindowOwnerName") == FL_OWNER
        and window.get("kCGWindowLayer", 0) == 0
    ]
    if not candidates:
        raise RuntimeError("FL Studio window not found; is FL running?")
    # Prefer the largest window (the main project window).
    window = max(
        candidates,
        key=lambda item: item.get("kCGWindowBounds", {}).get("Width", 0)
        * item.get("kCGWindowBounds", {}).get("Height", 0),
    )
    bounds = window["kCGWindowBounds"]
    return {
        "id": int(window["kCGWindowNumber"]),
        "x": float(bounds["X"]),
        "y": float(bounds["Y"]),
        "w": float(bounds["Width"]),
        "h": float(bounds["Height"]),
    }


def capture(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    info = fl_window()
    completed = subprocess.run(
        ["screencapture", "-x", "-l", str(info["id"]), str(path)],
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or "screencapture failed")[:300])
    return path


def _ensure_ocr() -> Path:
    if OCR_BINARY.is_file():
        return OCR_BINARY
    OCR_BINARY.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["swiftc", "-O", str(OCR_SOURCE), "-o", str(OCR_BINARY)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode:
        raise RuntimeError(
            "could not build OCR helper (run with Full access so Swift can write "
            f"its module cache): {(completed.stderr or '').strip()[:400]}"
        )
    return OCR_BINARY


def ocr(image: Path) -> list[dict[str, Any]]:
    binary = _ensure_ocr()
    completed = subprocess.run(
        [str(binary), str(image)], capture_output=True, text=True, timeout=60
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or "OCR failed").strip()[:300])
    return json.loads(completed.stdout)


def find_text(rows: list[dict[str, Any]], needle: str) -> dict[str, Any] | None:
    needle = needle.casefold()
    matches = [
        row
        for row in rows
        if needle in str(row.get("text", "")).casefold()
        and float(row.get("confidence", 0)) >= 0.25
    ]
    if not matches:
        return None
    # Prefer the highest-confidence match.
    return max(matches, key=lambda row: float(row.get("confidence", 0)))


def click_normalized(
    box: dict[str, Any], window: dict[str, Any] | None = None
) -> tuple[float, float]:
    """Click the center of a normalized OCR box in screen coordinates."""
    info = window or fl_window()
    x = info["x"] + (float(box["x"]) + float(box["w"]) / 2.0) * info["w"]
    y = info["y"] + (float(box["y"]) + float(box["h"]) / 2.0) * info["h"]
    click(x, y)
    return x, y


def click(x: float, y: float) -> None:
    point = Quartz.CGPointMake(x, y)
    for event in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        Quartz.CGEventPost(
            Quartz.kCGHIDEventTap,
            Quartz.CGEventCreateMouseEvent(
                None, event, point, Quartz.kCGMouseButtonLeft
            ),
        )
        time.sleep(0.05)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: ui_vision.py <text-to-find> [--capture PATH]", file=sys.stderr)
        return 2
    needle = sys.argv[1]
    image = Path("/tmp/fl-ui-vision.png")
    if "--capture" in sys.argv:
        image = Path(sys.argv[sys.argv.index("--capture") + 1])
    capture(image)
    rows = ocr(image)
    hit = find_text(rows, needle)
    if hit is None:
        print(json.dumps({"found": False, "needle": needle, "rows": rows}, ensure_ascii=False, indent=2))
        return 1
    point = click_normalized(hit)
    print(json.dumps({"found": True, "needle": needle, "text": hit["text"], "clicked": point}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
