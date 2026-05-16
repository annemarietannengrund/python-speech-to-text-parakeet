from unittest.mock import patch, MagicMock

import numpy as np

from audio.recorder.core import Exporter
from audio.recorder.models.audio_config import RecordingConfig, AudioFormat
from tests.unit.test_helper import BaseTestCase


class TestExporter(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.exporter = Exporter()
        self.mock_data = np.zeros(44100, dtype=np.float32)
        self.config = RecordingConfig(filename="test.wav", format=AudioFormat.WAV)

    @patch("soundfile.write")
    def test_export_wav(self, mock_sf_write: MagicMock) -> None:
        self.exporter.export(self.mock_data, self.config)
        mock_sf_write.assert_called_once_with("test.wav", self.mock_data, 44100)

    @patch("soundfile.write")
    def test_export_flac(self, mock_sf_write: MagicMock) -> None:
        config = RecordingConfig(filename="test.flac", format=AudioFormat.FLAC)
        self.exporter.export(self.mock_data, config)
        mock_sf_write.assert_called_once_with("test.flac", self.mock_data, 44100, format='FLAC')

    @patch("subprocess.run")
    @patch("soundfile.write")
    @patch("os.remove")
    def test_export_mp3_calls_ffmpeg(self, mock_remove: MagicMock, mock_sf_write: MagicMock,
                                     mock_run: MagicMock) -> None:
        config = RecordingConfig(filename="test.mp3", format=AudioFormat.MP3)
        self.exporter.export(self.mock_data, config)

        # Check if soundfile.write was called for temp file
        self.assertTrue(mock_sf_write.called)
        # Check if subprocess.run was called for ffmpeg
        self.assertTrue(mock_run.called)
        args, _ = mock_run.call_args
        cmd = args[0]
        self.assertIn("ffmpeg", cmd)
        self.assertIn("libmp3lame", cmd)
        self.assertIn("test.mp3", cmd)

    def test_export_empty_data(self) -> None:
        empty_data = np.array([], dtype=np.float32)
        with self.assertLogs("audio.recorder.core", level="ERROR") as cm:
            self.exporter.export(empty_data, self.config)
        self.assertIn("No audio data to export", cm.output[0])
