"""Post-transcription side effects: clipboard copy + system notification.

Both helpers degrade gracefully: if the underlying OS tool is missing
the action is skipped and a short human-readable reason is returned.
Pure stdlib — no extra Python dependency required (uses macOS `pbcopy`
and `osascript`, plus Linux `xclip`/`wl-copy` and `notify-send` when
present).
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActionResult:
    """Outcome of a single post action."""
    success: bool
    label: str  # short status fragment for the summary line, e.g. "copied" or "copy: pbcopy missing"


def copy_to_clipboard(text: str) -> ActionResult:
    """Copy `text` to the system clipboard using a platform-native tool."""
    if not text:
        return ActionResult(False, "copy: empty")
    command = _clipboard_command()
    if command is None:
        return ActionResult(False, "copy: no tool")
    try:
        subprocess.run(command, input=text, text=True, check=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning("Clipboard copy failed: %s", exc)
        return ActionResult(False, "copy: failed")
    return ActionResult(True, "copied")


def send_notification(title: str, message: str) -> ActionResult:
    """Show a system notification via the platform's native facility."""
    command = _notification_command(title, message)
    if command is None:
        return ActionResult(False, "notify: no tool")
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning("Notification failed: %s", exc)
        return ActionResult(False, "notify: failed")
    return ActionResult(True, "notified")


def _clipboard_command() -> Sequence[str] | None:
    if sys.platform == "darwin" and shutil.which("pbcopy"):
        return ["pbcopy"]
    if shutil.which("wl-copy"):
        return ["wl-copy"]
    if shutil.which("xclip"):
        return ["xclip", "-selection", "clipboard"]
    if shutil.which("xsel"):
        return ["xsel", "--clipboard", "--input"]
    return None


def _notification_command(title: str, message: str) -> Sequence[str] | None:
    if sys.platform == "darwin":
        if shutil.which("terminal-notifier"):
            return ["terminal-notifier", "-title", title, "-message", message, "-sound", "Glass"]
        if shutil.which("osascript"):
            escaped_title = title.replace('"', '\\"')
            escaped_message = message.replace('"', '\\"')
            script = f'display notification "{escaped_message}" with title "{escaped_title}" sound name "Glass"'
            return ["osascript", "-e", script]
    if shutil.which("notify-send"):
        return ["notify-send", title, message]
    return None
