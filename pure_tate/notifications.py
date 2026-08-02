"""Best-effort local notifications for long-running campaign batches."""

import subprocess
import sys
from typing import Any, Dict


_APPLE_SCRIPT = """on run argv
display notification (item 2 of argv) with title (item 1 of argv)
end run"""


def send_desktop_notification(title: str, message: str) -> bool:
    """Send a native macOS notification without letting alert failures stop work.

    Arguments are passed separately to AppleScript rather than interpolated into
    source, so task IDs and engine output cannot alter the notification command.
    """
    if sys.platform != "darwin":
        return False
    try:
        completed = subprocess.run(
            ["osascript", "-e", _APPLE_SCRIPT, title, message],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def notify_campaign_step(
    campaign_id: str, event: Dict[str, Any], requested_steps: int
) -> bool:
    """Notify after a campaign step reaches a terminal state."""
    state = str(event.get("state", "completed")).replace("_", " ")
    step = event.get("step", "?")
    phase = str(event.get("phase", "task"))
    engine = str(event.get("engine", "unknown engine"))
    task_id = str(event.get("task_id", "unknown task"))
    return send_desktop_notification(
        "Pure Tate • step %s/%s" % (step, requested_steps),
        "%s • %s via %s\n%s (%s)"
        % (campaign_id, phase, engine, task_id, state),
    )


def notify_campaign_run(
    campaign_id: str,
    executed_steps: int,
    requested_steps: int,
    status: str,
    stop_reason: str,
) -> bool:
    """Notify once when a campaign batch exits."""
    return send_desktop_notification(
        "Pure Tate • run %s" % status,
        "%s: %d/%d steps • %s"
        % (campaign_id, executed_steps, requested_steps, stop_reason),
    )
