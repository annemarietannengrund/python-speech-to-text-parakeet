import json
from pathlib import Path
from unittest.mock import Mock, patch

from audio.transcriptor_modern.audio_info import probe_audio
from tests.unit.test_helper import BaseTestCase


class TestProbeAudio(BaseTestCase):
    @patch("audio.transcriptor_modern.audio_info.shutil.which", return_value=None)
    @patch("audio.transcriptor_modern.audio_info.Path.stat")
    def test_returns_filesystem_only_when_ffprobe_missing(self, mock_stat: Mock, _which: Mock) -> None:
        mock_stat.return_value.st_size = 4096
        with patch("audio.transcriptor_modern.audio_info.Path.exists", return_value=True):
            info = probe_audio(Path("/tmp/sample.m4a"))
        self.assertEqual(4096, info.size_bytes)
        self.assertEqual("m4a", info.format)
        self.assertIsNone(info.duration_seconds)
        self.assertIsNone(info.sample_rate_hz)

    @patch("audio.transcriptor_modern.audio_info.subprocess.run")
    @patch("audio.transcriptor_modern.audio_info.shutil.which", return_value="/usr/bin/ffprobe")
    @patch("audio.transcriptor_modern.audio_info.Path.stat")
    def test_parses_ffprobe_payload(self, mock_stat: Mock, _which: Mock, mock_run: Mock) -> None:
        mock_stat.return_value.st_size = 1024
        payload = {
            "streams": [{
                "duration": "12.34",
                "sample_rate": "44100",
                "channels": 2,
                "codec_name": "aac",
            }],
            "format": {"duration": "12.34"},
        }
        mock_run.return_value = Mock(stdout=json.dumps(payload))
        with patch("audio.transcriptor_modern.audio_info.Path.exists", return_value=True):
            info = probe_audio(Path("/tmp/sample.m4a"))
        self.assertAlmostEqual(12.34, info.duration_seconds or 0.0)
        self.assertEqual(44100, info.sample_rate_hz)
        self.assertEqual(2, info.channels)
        self.assertEqual("aac", info.codec)
        mock_run.assert_called_once()
        command = mock_run.call_args.args[0]
        self.assertEqual("ffprobe", command[0])
        self.assertIn(str(Path("/tmp/sample.m4a")), command)
