"""Best-effort local notifications for long-running campaign batches."""

import json
import os
import subprocess
import sys
from email.header import Header
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .store import ROOT


_JAVASCRIPT_FOR_AUTOMATION = """function run(argv) {
var app = Application.currentApplication();
app.includeStandardAdditions = true;
app.displayNotification(argv[1], {withTitle: argv[0]});
}"""


def send_desktop_notification(title: str, message: str) -> bool:
    """Send a native macOS notification without letting alert failures stop work.

    Arguments are passed separately to JXA rather than interpolated into source,
    so task IDs and engine output cannot alter the notification command.
    """
    if sys.platform != "darwin":
        return False
    try:
        completed = subprocess.run(
            [
                "osascript",
                "-l",
                "JavaScript",
                "-e",
                _JAVASCRIPT_FOR_AUTOMATION,
                title,
                message,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _ntfy_config() -> Dict[str, str]:
    """Load an optional local ntfy destination without tracking its topic."""
    environment_topic = os.environ.get("PURE_TATE_NTFY_TOPIC", "").strip()
    if environment_topic:
        return {
            "server": os.environ.get("PURE_TATE_NTFY_SERVER", "https://ntfy.sh").strip(),
            "topic": environment_topic,
        }
    path = ROOT / "data" / "notifications.local.json"
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    ntfy = payload.get("ntfy", {}) if isinstance(payload, dict) else {}
    if not isinstance(ntfy, dict):
        return {}
    server = str(ntfy.get("server", "https://ntfy.sh")).rstrip("/")
    topic = str(ntfy.get("topic", "")).strip()
    return {"server": server, "topic": topic} if topic else {}


def ntfy_is_configured() -> bool:
    """Return whether this checkout has explicitly opted into phone alerts."""
    return bool(_ntfy_config())


def send_ntfy_notification(
    title: str, message: str, priority: str = "default"
) -> bool:
    """Publish a best-effort phone notification to an opt-in ntfy topic."""
    return bool(send_ntfy_notification_detailed(title, message, priority)["sent"])


def send_ntfy_notification_detailed(
    title: str, message: str, priority: str = "default"
) -> Dict[str, Any]:
    """Publish to ntfy and retain a redacted delivery diagnosis."""
    config = _ntfy_config()
    if not config:
        return {"enabled": False, "sent": False, "error": "ntfy is not configured"}
    server, topic = config["server"], config["topic"]
    if not server.startswith("https://"):
        return {
            "enabled": True,
            "sent": False,
            "error": "ntfy server must use https",
        }

    def header_value(value: str) -> str:
        try:
            value.encode("latin-1")
        except UnicodeEncodeError:
            return Header(value, "utf-8").encode()
        return value

    try:
        request = Request(
            "%s/%s" % (server, topic),
            data=message.encode("utf-8"),
            headers={
                "Title": header_value(title),
                "Priority": header_value(priority),
                "Tags": "computer",
            },
            method="POST",
        )
        with urlopen(request, timeout=10) as response:
            sent = 200 <= response.status < 300
            return {
                "enabled": True,
                "sent": sent,
                "status": int(response.status),
                "error": None if sent else "unexpected HTTP status",
            }
    except HTTPError as exc:
        return {
            "enabled": True,
            "sent": False,
            "status": int(exc.code),
            "error": "HTTP %d: %s" % (exc.code, str(exc.reason)[:200]),
        }
    except (OSError, URLError, ValueError) as exc:
        return {
            "enabled": True,
            "sent": False,
            "error": "%s: %s" % (type(exc).__name__, str(exc)[:300]),
        }


def notify_campaign_step(
    campaign_id: str,
    event: Dict[str, Any],
    requested_steps: int,
    *,
    desktop: bool = True,
    ntfy: bool = False,
) -> Dict[str, Any]:
    """Notify after a campaign step reaches a terminal state."""
    state = str(event.get("state", "completed")).replace("_", " ")
    step = event.get("step", "?")
    phase = str(event.get("phase", "task"))
    engine = str(event.get("engine", "unknown engine"))
    task_id = str(event.get("task_id", "unknown task"))
    title = "Pure Tate • step %s/%s" % (step, requested_steps)
    message = "%s • %s via %s\n%s (%s)" % (
        campaign_id,
        phase,
        engine,
        task_id,
        state,
    )
    desktop_sent = send_desktop_notification(title, message) if desktop else False
    ntfy_delivery = (
        send_ntfy_notification_detailed(title, message)
        if ntfy
        else {"enabled": False, "sent": False, "error": None}
    )
    return {
        "desktop": {"enabled": desktop, "sent": desktop_sent},
        "ntfy": ntfy_delivery,
    }


def notify_campaign_run(
    campaign_id: str,
    executed_steps: int,
    requested_steps: int,
    status: str,
    stop_reason: str,
    *,
    desktop: bool = True,
    ntfy: bool = False,
) -> Dict[str, Any]:
    """Notify once when a campaign batch exits."""
    title = "Pure Tate • run %s" % status
    message = "%s: %d/%d steps • %s" % (
        campaign_id,
        executed_steps,
        requested_steps,
        stop_reason,
    )
    desktop_sent = send_desktop_notification(title, message) if desktop else False
    ntfy_delivery = (
        send_ntfy_notification_detailed(title, message)
        if ntfy
        else {"enabled": False, "sent": False, "error": None}
    )
    return {
        "desktop": {"enabled": desktop, "sent": desktop_sent},
        "ntfy": ntfy_delivery,
    }
