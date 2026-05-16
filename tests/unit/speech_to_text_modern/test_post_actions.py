from unittest.mock import Mock, patch

from audio.transcriptor_modern.post_actions import (
    copy_to_clipboard,
    send_notification,
)
from tests.unit.test_helper import BaseTestCase


class TestCopyToClipboard(BaseTestCase):
    def test_empty_text_skips_subprocess(self) -> None:
        with patch("audio.transcriptor_modern.post_actions.subprocess.run") as mock_run:
            result = copy_to_clipboard("")
        self.assertFalse(result.success)
        self.assertEqual(result.label, "copy: empty")
        mock_run.assert_not_called()

    @patch("audio.transcriptor_modern.post_actions.sys.platform", "darwin")
    @patch("audio.transcriptor_modern.post_actions.shutil.which")
    @patch("audio.transcriptor_modern.post_actions.subprocess.run")
    def test_macos_uses_pbcopy(self, mock_run: Mock, mock_which: Mock) -> None:
        mock_which.side_effect = lambda name: "/usr/bin/pbcopy" if name == "pbcopy" else None

        result = copy_to_clipboard("hello")

        self.assertTrue(result.success)
        self.assertEqual(result.label, "copied")
        mock_run.assert_called_once_with(["pbcopy"], input="hello", text=True, check=True)

    @patch("audio.transcriptor_modern.post_actions.sys.platform", "linux")
    @patch("audio.transcriptor_modern.post_actions.shutil.which", return_value=None)
    @patch("audio.transcriptor_modern.post_actions.subprocess.run")
    def test_no_tool_returns_failure_without_subprocess(
        self, mock_run: Mock, _which: Mock
    ) -> None:
        result = copy_to_clipboard("hello")
        self.assertFalse(result.success)
        self.assertEqual(result.label, "copy: no tool")
        mock_run.assert_not_called()


class TestSendNotification(BaseTestCase):
    @patch("audio.transcriptor_modern.post_actions.sys.platform", "darwin")
    @patch("audio.transcriptor_modern.post_actions.shutil.which")
    @patch("audio.transcriptor_modern.post_actions.subprocess.run")
    def test_macos_invokes_osascript(self, mock_run: Mock, mock_which: Mock) -> None:
        mock_which.side_effect = lambda name: "/usr/bin/osascript" if name == "osascript" else None

        result = send_notification("title", "msg")

        self.assertTrue(result.success)
        self.assertEqual(result.label, "notified")
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0][0], "osascript")
        self.assertIn('display notification "msg"', args[0][2])
        self.assertIn('with title "title"', args[0][2])
        self.assertTrue(kwargs["check"])

    @patch("audio.transcriptor_modern.post_actions.sys.platform", "darwin")
    @patch("audio.transcriptor_modern.post_actions.shutil.which")
    @patch("audio.transcriptor_modern.post_actions.subprocess.run")
    def test_macos_prefers_terminal_notifier(self, mock_run: Mock, mock_which: Mock) -> None:
        mock_which.side_effect = lambda name: f"/usr/local/bin/{name}" if name in {"terminal-notifier", "osascript"} else None

        result = send_notification("title", "msg")

        self.assertTrue(result.success)
        self.assertEqual(result.label, "notified")
        args, _ = mock_run.call_args
        self.assertEqual(args[0][0], "terminal-notifier")
        self.assertIn("-title", args[0])
        self.assertIn("title", args[0])
        self.assertIn("-message", args[0])
        self.assertIn("msg", args[0])

    @patch("audio.transcriptor_modern.post_actions.sys.platform", "linux")
    @patch("audio.transcriptor_modern.post_actions.shutil.which", return_value=None)
    @patch("audio.transcriptor_modern.post_actions.subprocess.run")
    def test_no_tool_returns_failure(self, mock_run: Mock, _which: Mock) -> None:
        result = send_notification("t", "m")
        self.assertFalse(result.success)
        self.assertEqual(result.label, "notify: no tool")
        mock_run.assert_not_called()
