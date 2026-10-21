"""FL Studio trigger utility for Piano Roll script execution.

This module handles sending keystrokes to FL Studio to trigger the
ComposeWithLLM Piano Roll script, which processes JSON note requests.
"""

from __future__ import annotations

import platform
import subprocess
import time
from pathlib import Path
from typing import Callable

# Delay after triggering to allow FL Studio to process
TRIGGER_DELAY = 2.0


class FLStudioTrigger:
    """Handles triggering FL Studio's Piano Roll script via keystrokes.

    The trigger sends Cmd+Opt+Y (macOS) or Ctrl+Alt+Y (Windows) to FL Studio,
    which executes the ComposeWithLLM.pyscript to process pending JSON requests.
    """

    def __init__(self) -> None:
        self._system = platform.system()
        self._trigger_func: Callable[[], bool] | None = None
        # None = not attempted/unknown, True = the request/state changed,
        # False = the keystroke was sent but nothing consumed it.
        self.last_verified: bool | None = None
        self._setup_trigger()

    def _setup_trigger(self) -> None:
        """Set up the appropriate trigger method for the current platform."""
        if self._system == "Darwin":
            self._trigger_func = self._trigger_macos
        elif self._system == "Windows":
            self._trigger_func = self._trigger_windows
        else:
            self._trigger_func = None

    def _piano_roll_signature(self) -> tuple:
        """Cheap postcondition fingerprint for the Piano Roll bridge files."""
        base = (
            Path.home()
            / "Documents"
            / "Image-Line"
            / "FL Studio"
            / "Settings"
            / "Piano roll scripts"
        )
        signature = []
        for name in ("mcp_request.json", "mcp_response.json", "piano_roll_state.json"):
            path = base / name
            try:
                stat = path.stat()
                signature.append((name, stat.st_mtime_ns, stat.st_size))
            except OSError:
                signature.append((name, None, None))
        return tuple(signature)

    def _post_key_background_macos(self) -> bool:
        """Send Cmd+Opt+Y to FL's PID without activating it.

        FL keeps the Piano Roll's internal focus while the app is in the
        background. Posting the key directly to the PID avoids stealing focus
        from DSH; if the bridge files do not change, the caller falls back to
        the foreground path.
        """
        try:
            import Quartz

            pid = int(
                subprocess.check_output(["pgrep", "-x", "OsxFL"], text=True)
                .split()[0]
            )
            for down in (True, False):
                event = Quartz.CGEventCreateKeyboardEvent(None, 16, down)
                Quartz.CGEventSetFlags(
                    event,
                    Quartz.kCGEventFlagMaskCommand
                    | Quartz.kCGEventFlagMaskAlternate,
                )
                Quartz.CGEventPostToPid(pid, event)
                time.sleep(0.05)
            return True
        except Exception:
            return False

    def _focus_piano_roll_macos(self) -> bool:
        """Click the Piano Roll header so the run-last-script key reaches it.

        FL's Piano Roll is custom-drawn and has no AX node. The header is a wide
        target whose center is stable relative to the FL window. This is a
        deliberate last-resort fallback: if it misses, it clicks the Playlist
        header, which is harmless. The melody write's note-count postcondition
        owns the actual verification.
        """
        try:
            import Quartz

            windows = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly
                | Quartz.kCGWindowListExcludeDesktopElements,
                Quartz.kCGNullWindowID,
            )
            candidates = [
                window
                for window in windows
                if window.get("kCGWindowOwnerName") == "FL Studio"
                and window.get("kCGWindowLayer", 0) == 0
            ]
            if not candidates:
                return False
            bounds = max(
                candidates,
                key=lambda item: item.get("kCGWindowBounds", {}).get("Width", 0)
                * item.get("kCGWindowBounds", {}).get("Height", 0),
            )["kCGWindowBounds"]
            point = Quartz.CGPointMake(
                bounds["X"] + bounds["Width"] * 0.5,
                bounds["Y"] + bounds["Height"] * 0.135,
            )
            for event in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
                Quartz.CGEventPost(
                    Quartz.kCGHIDEventTap,
                    Quartz.CGEventCreateMouseEvent(
                        None, event, point, Quartz.kCGMouseButtonLeft
                    ),
                )
                time.sleep(0.05)
            return True
        except Exception:
            return False

    def _trigger_macos(self) -> bool:
        """Trigger FL Studio without stealing focus when possible.

        First post Cmd+Opt+Y directly to FL's PID. If the bridge files do not
        change, fall back to activating FL, focusing the Piano Roll header, and
        sending the key through System Events. The fallback is the only path
        that should move the user's focus.
        """
        before = self._piano_roll_signature()
        if self._post_key_background_macos():
            time.sleep(0.8)
            if self._piano_roll_signature() != before:
                self.last_verified = True
                return True
        try:
            activate = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application id "com.image-line.flstudio" to activate',
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if activate.returncode != 0:
                self.last_verified = False
                return False
            time.sleep(0.5)
            self._focus_piano_roll_macos()
            time.sleep(0.2)
            keystroke = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to keystroke "y" '
                    'using {command down, option down}',
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if keystroke.returncode != 0:
                self.last_verified = False
                return False
            time.sleep(0.8)
            self.last_verified = self._piano_roll_signature() != before
            return True
        except subprocess.TimeoutExpired:
            self.last_verified = False
            return False
        except Exception:
            # Fallback to pynput
            self.last_verified = None
            return self._trigger_macos_pynput()

    def _trigger_macos_pynput(self) -> bool:
        """Trigger FL Studio on macOS using pynput."""
        try:
            from pynput.keyboard import Controller, Key

            keyboard = Controller()

            # Focus FL Studio first
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application id "com.image-line.flstudio" to activate',
                ],
                capture_output=True,
                timeout=5,
            )
            time.sleep(0.3)

            # Send Cmd+Opt+Y
            keyboard.press(Key.cmd)
            keyboard.press(Key.alt)
            keyboard.press("y")
            keyboard.release("y")
            keyboard.release(Key.alt)
            keyboard.release(Key.cmd)

            return True
        except Exception:
            return False

    def _focus_fl_studio_windows(self) -> bool:
        """Bring the FL Studio window to the foreground on Windows.

        The keystroke that triggers the ComposeWithLLM script is delivered to
        whichever window has focus, so FL Studio must be foregrounded first
        (mirroring the ``activate`` step used on macOS). Uses only ctypes/user32
        so no extra dependency is required.

        Returns:
            True if an FL Studio window was found and foregrounded, else False.
        """
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            found = {"hwnd": None}

            EnumWindowsProc = ctypes.WINFUNCTYPE(
                ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
            )

            def _enum(hwnd, _lparam):
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length == 0:
                    return True
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                # FL Studio's main window title contains "FL Studio"
                if "FL Studio" in buffer.value:
                    found["hwnd"] = hwnd
                    return False  # stop enumerating
                return True

            user32.EnumWindows(EnumWindowsProc(_enum), 0)

            hwnd = found["hwnd"]
            if not hwnd:
                return False

            # Restore if minimized, then foreground it.
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)

            # Windows normally forbids a background process from stealing focus.
            # Tapping ALT unlocks SetForegroundWindow for this call.
            VK_MENU = 0x12
            KEYEVENTF_KEYUP = 0x0002
            user32.keybd_event(VK_MENU, 0, 0, 0)
            user32.SetForegroundWindow(hwnd)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

            return True
        except Exception:
            return False

    def _trigger_windows(self) -> bool:
        """Trigger FL Studio on Windows using pynput.

        Foregrounds FL Studio first so the Ctrl+Alt+Y hotkey actually reaches
        it; returns False (so the caller reports a manual-trigger warning) if the
        FL Studio window can't be found.
        """
        try:
            from pynput.keyboard import Controller, Key

            if not self._focus_fl_studio_windows():
                return False

            # Give FL Studio a moment to accept focus before the keystroke.
            time.sleep(0.3)

            keyboard = Controller()

            # Send Ctrl+Alt+Y
            keyboard.press(Key.ctrl)
            keyboard.press(Key.alt)
            keyboard.press("y")
            keyboard.release("y")
            keyboard.release(Key.alt)
            keyboard.release(Key.ctrl)

            return True
        except Exception:
            return False

    def trigger(self, delay: float = TRIGGER_DELAY) -> bool:
        """Trigger FL Studio to execute the Piano Roll script.

        Args:
            delay: Seconds to wait after triggering for FL Studio to process.

        Returns:
            True if the trigger was sent successfully, False otherwise.
        """
        if self._trigger_func is None:
            return False

        self.last_verified = None
        success = self._trigger_func()
        if success and delay > 0:
            time.sleep(delay)

        return success

    @property
    def is_supported(self) -> bool:
        """Check if triggering is supported on this platform."""
        return self._trigger_func is not None

    @property
    def platform(self) -> str:
        """Get the current platform name."""
        return self._system

    @property
    def keystroke(self) -> str:
        """Get the keystroke used for this platform."""
        if self._system == "Darwin":
            return "Cmd+Opt+Y"
        elif self._system == "Windows":
            return "Ctrl+Alt+Y"
        return "Unknown"


# Global trigger instance
_trigger: FLStudioTrigger | None = None


def get_trigger() -> FLStudioTrigger:
    """Get the global FL Studio trigger instance."""
    global _trigger
    if _trigger is None:
        _trigger = FLStudioTrigger()
    return _trigger


def trigger_fl_studio(delay: float = TRIGGER_DELAY) -> bool:
    """Convenience function to trigger FL Studio.

    Args:
        delay: Seconds to wait after triggering.

    Returns:
        True if successful, False otherwise.
    """
    return get_trigger().trigger(delay)
