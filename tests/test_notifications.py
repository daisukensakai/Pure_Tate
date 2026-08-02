import subprocess
import unittest
from unittest import mock

from pure_tate.notifications import send_desktop_notification, send_ntfy_notification


class DesktopNotificationTests(unittest.TestCase):
    def test_macos_notification_uses_jxa_with_separate_arguments(self):
        process = subprocess.CompletedProcess([], 0)
        with mock.patch("pure_tate.notifications.sys.platform", "darwin"), mock.patch(
            "pure_tate.notifications.subprocess.run", return_value=process
        ) as run:
            self.assertTrue(send_desktop_notification("Title", "Body"))
        argv = run.call_args.args[0]
        self.assertEqual(argv[:4], ["osascript", "-l", "JavaScript", "-e"])
        self.assertEqual(argv[-2:], ["Title", "Body"])

    def test_other_platforms_do_not_run_a_subprocess(self):
        with mock.patch("pure_tate.notifications.sys.platform", "linux"), mock.patch(
            "pure_tate.notifications.subprocess.run"
        ) as run:
            self.assertFalse(send_desktop_notification("Title", "Body"))
        run.assert_not_called()

    def test_ntfy_posts_title_priority_and_message(self):
        response = mock.MagicMock(status=200)
        response.__enter__.return_value = response
        with mock.patch(
            "pure_tate.notifications._ntfy_config",
            return_value={"server": "https://ntfy.sh", "topic": "private-topic"},
        ), mock.patch(
            "pure_tate.notifications.urlopen", return_value=response
        ) as post:
            self.assertTrue(send_ntfy_notification("Title", "Body", "high"))
        request = post.call_args.args[0]
        self.assertEqual(request.full_url, "https://ntfy.sh/private-topic")
        self.assertEqual(request.data, b"Body")
        self.assertEqual(request.headers["Title"], "Title")
        self.assertEqual(request.headers["Priority"], "high")
