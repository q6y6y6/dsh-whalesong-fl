#!/usr/bin/env python3
"""Deploy the v0 FL Studio controller and Piano Roll script.

    .venv/bin/python scripts/deploy_controller.py --dry-run
    .venv/bin/python scripts/deploy_controller.py

Existing files are backed up next to the originals with a timestamp suffix.
After deploying, re-select `FLStudioMCP` in FL's MIDI Settings (Controller
type) so the Python module is re-read, and re-select `ComposeWithLLM` in the
Piano Roll Scripts menu.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FL_USER_DATA = Path.home() / "Documents" / "Image-Line" / "FL Studio"
HARDWARE_DIR = FL_USER_DATA / "Settings" / "Hardware" / "FLStudioMCP"
PIANO_ROLL_DIR = FL_USER_DATA / "Settings" / "Piano roll scripts"

FILES = [
    (ROOT / "packages" / "fl-v0" / "fl_controller" / "device_FLStudioMCP.py", HARDWARE_DIR / "device_FLStudioMCP.py"),
    (ROOT / "packages" / "fl-v0" / "scripts" / "ComposeWithLLM.pyscript", PIANO_ROLL_DIR / "ComposeWithLLM.pyscript"),
]


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    target = path.with_name(f"{path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(path, target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for source, target in FILES:
        if not source.is_file():
            print(f"FAIL missing source: {source}")
            return 1
        print(f"{source} -> {target}")
        if args.dry_run:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        saved = backup(target)
        shutil.copy2(source, target)
        if saved:
            print(f"  backed up: {saved}")
    if args.dry_run:
        print("Dry run only; nothing written.")
        return 0
    print()
    print("Deployed. In FL Studio:")
    print("  1. Options > MIDI Settings > Input > re-select Controller type = FLStudioMCP.")
    print("  2. Open a Piano Roll > Scripts > re-select ComposeWithLLM.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
