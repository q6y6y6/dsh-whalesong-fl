#!/usr/bin/env python3
"""Diagnose the v0 melody bridge.

    .venv/bin/python scripts/doctor.py
    .venv/bin/python scripts/doctor.py --live --json

The doctor is read-only by default. ``--live`` sends one real MIDI handshake.
"""

from __future__ import annotations

import argparse
import json
import platform
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FL_USER_DATA = Path.home() / "Documents" / "Image-Line" / "FL Studio"
HARDWARE_DIR = FL_USER_DATA / "Settings" / "Hardware" / "FLStudioMCP"
PIANO_ROLL_DIR = FL_USER_DATA / "Settings" / "Piano roll scripts"
TEST_PROJECT = FL_USER_DATA / "Projects" / "test project" / "test project.flp"
PROFILE_PATCH = Path.home() / ".dsh" / "profiles" / "desktop" / "cordis.patch.yml"


class Report:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def add(self, name: str, status: str, detail: str, hint: str | None = None) -> None:
        self.checks.append(
            {"name": name, "status": status, "detail": detail, "hint": hint}
        )

    def ok(self, name: str, detail: str = "") -> None:
        self.add(name, "ok", detail)

    def warn(self, name: str, detail: str, hint: str | None = None) -> None:
        self.add(name, "warn", detail, hint)

    def fail(self, name: str, detail: str, hint: str | None = None) -> None:
        self.add(name, "fail", detail, hint)

    @property
    def failed(self) -> bool:
        return any(check["status"] == "fail" for check in self.checks)


def _run(argv: list[str], timeout: float = 5.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            argv, check=False, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def check_python(rep: Report) -> None:
    version = platform.python_version()
    if sys.version_info >= (3, 10):
        rep.ok("python", f"{version} ({sys.executable})")
    else:
        rep.fail("python", f"{version} is too old", "Use Python 3.10+ (3.12 recommended).")


def check_mido(rep: Report) -> None:
    try:
        import mido
    except Exception as exc:  # noqa: BLE001
        rep.fail("mido", f"import failed: {exc}", "Run scripts/setup.py.")
        return
    try:
        outputs = list(mido.get_output_names())
        inputs = list(mido.get_input_names())
    except Exception as exc:  # noqa: BLE001
        rep.fail("midi", f"enumerating ports failed: {exc}", "Check Audio MIDI Setup.")
        return
    rep.ok("mido", f"{len(outputs)} output, {len(inputs)} input port(s)")
    iac = [name for name in outputs if "IAC" in name]
    if iac:
        rep.ok("iac", f"found {len(iac)} IAC output(s): {', '.join(iac)}")
    else:
        rep.fail(
            "iac",
            "no IAC MIDI output found",
            "Enable the IAC Driver in Audio MIDI Setup.",
        )
    if iac and not [name for name in iac if name in inputs]:
        rep.warn(
            "iac-pair",
            "IAC output is visible but the matching input was not",
            "Enable the same IAC bus as an input in FL Studio MIDI Settings.",
        )


def _fl_version(app: Path) -> str | None:
    try:
        with (app / "Contents" / "Info.plist").open("rb") as stream:
            data = plistlib.load(stream)
        return str(data.get("CFBundleShortVersionString") or data.get("CFBundleVersion"))
    except Exception:  # noqa: BLE001
        return None


def check_fl_install(rep: Report) -> None:
    candidates = sorted(Path("/Applications").glob("FL Studio*.app"))
    if not candidates:
        rep.fail("fl-studio", "no /Applications/FL Studio*.app found")
        return
    app = candidates[-1]
    rep.ok("fl-studio", f"{app.name} {_fl_version(app) or 'unknown version'}")
    proc = _run(["pgrep", "-fl", "OsxFL"])
    if proc and proc.stdout.strip():
        rep.ok("fl-running", proc.stdout.strip().splitlines()[0])
    else:
        rep.warn("fl-running", "FL Studio is not running", "Open FL Studio before live tests.")


def check_scripts(rep: Report) -> None:
    device = HARDWARE_DIR / "device_FLStudioMCP.py"
    if device.is_file():
        rep.ok("controller", str(device))
    else:
        rep.fail(
            "controller",
            f"missing {device}",
            "Run scripts/deploy_controller.py.",
        )
    pyscript = PIANO_ROLL_DIR / "ComposeWithLLM.pyscript"
    if pyscript.is_file():
        rep.ok("piano-roll-script", str(pyscript))
    else:
        rep.fail(
            "piano-roll-script",
            f"missing {pyscript}",
            "Run scripts/deploy_controller.py.",
        )


def check_write(rep: Report) -> None:
    probe = HARDWARE_DIR / ".doctor-write-test"
    try:
        HARDWARE_DIR.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        rep.ok("fl-user-data-write", "writable")
    except Exception as exc:  # noqa: BLE001
        rep.warn(
            "fl-user-data-write",
            f"not writable from this process: {exc}",
            "If this is the DSH bash sandbox, run the doctor with Full access. "
            "The MCP server itself runs outside that sandbox.",
        )


def check_test_project(rep: Report) -> None:
    if TEST_PROJECT.is_file():
        rep.ok("test-project", f"{TEST_PROJECT} ({TEST_PROJECT.stat().st_size} bytes)")
    else:
        rep.fail(
            "test-project",
            f"missing {TEST_PROJECT}",
            "Create a disposable project named test project.",
        )


def check_melody_surface(rep: Report) -> None:
    code = """
import asyncio, json
from fl_melody.server import mcp

async def main():
    tools = await mcp.list_tools()
    schema = lambda t: getattr(t, "parameters", None) or {}
    size = sum(
        len(json.dumps({"name": t.name, "description": t.description, "inputSchema": schema(t)}))
        for t in tools
    )
    print(len(tools), size)

asyncio.run(main())
"""
    proc = _run([sys.executable, "-c", code], timeout=20)
    if not proc or proc.returncode != 0:
        detail = (proc.stderr if proc else "process failed").strip().splitlines()
        rep.fail(
            "melody-surface",
            detail[-1] if detail else "import failed",
            "Run scripts/setup.py.",
        )
        return
    parts = proc.stdout.strip().split()
    if len(parts) != 2:
        rep.warn("melody-surface", proc.stdout.strip())
        return
    count, size = parts
    if count == "3":
        rep.ok("melody-surface", f"3 tools, {size} schema bytes")
    else:
        rep.warn("melody-surface", f"{count} tools (expected 3), {size} schema bytes")


def check_profile(rep: Report) -> None:
    if not PROFILE_PATCH.is_file():
        rep.warn("dsh-profile", f"missing {PROFILE_PATCH}", "Install the dsh-whalesong-fl bundle.")
        return
    text = PROFILE_PATCH.read_text(encoding="utf-8")
    if "fl-studio-mcp" in text and "dsh-mcp-client" in text:
        rep.ok("dsh-profile", "fl-studio-mcp entry present")
    else:
        rep.warn(
            "dsh-profile",
            "no fl-studio-mcp entry",
            "Install packages/dsh-bundle or apply its patch.",
        )
    if "fl_melody.server" in text:
        rep.ok("dsh-profile-surface", "melody-only (fl_melody.server)")
    elif "fl_studio_mcp.server" in text:
        rep.warn(
            "dsh-profile-surface",
            "profile points at the legacy full-control server",
            "Use fl_melody.server for the v0 surface.",
        )
    else:
        rep.warn("dsh-profile-surface", "no recognized FL server module")
    if str(ROOT) not in text:
        rep.warn(
            "dsh-profile-paths",
            "profile does not point at this checkout",
            "Re-run scripts/setup.py after moving the project.",
        )


def check_live(rep: Report) -> None:
    code = (
        "import json;"
        "from fl_studio_mcp.utils.connection import get_connection;"
        "c=get_connection();"
        "print(json.dumps(c.ping(timeout=2.0), ensure_ascii=False))"
    )
    proc = _run([sys.executable, "-c", code], timeout=15)
    if not proc or proc.returncode:
        detail = (proc.stderr if proc else "process failed").strip().splitlines()
        rep.fail("live-handshake", detail[-1] if detail else "failed")
        return
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        rep.fail("live-handshake", proc.stdout.strip()[:300])
        return
    if payload.get("success"):
        rep.ok("live-handshake", f"FL answered; loop={payload.get('loop_mode')}")
    else:
        rep.fail(
            "live-handshake",
            str(payload.get("error") or payload)[:300],
            "Check FL MIDI Settings: IAC input enabled, Controller type = FLStudioMCP.",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    rep = Report()
    check_python(rep)
    check_mido(rep)
    check_fl_install(rep)
    check_scripts(rep)
    check_write(rep)
    check_test_project(rep)
    check_melody_surface(rep)
    check_profile(rep)
    if args.live:
        check_live(rep)

    if args.json:
        print(json.dumps({"root": str(ROOT), "checks": rep.checks}, ensure_ascii=False, indent=2))
    else:
        icons = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}
        print(f"DSH WhaleSong doctor — {ROOT}")
        for check in rep.checks:
            print(f"[{icons[check['status']]}] {check['name']}: {check['detail']}")
            if check["hint"] and check["status"] != "ok":
                print(f"       -> {check['hint']}")
        print()
        print("RESULT:", "FAIL" if rep.failed else "PASS (warnings may need attention)")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
