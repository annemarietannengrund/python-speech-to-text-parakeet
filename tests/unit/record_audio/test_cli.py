from unittest.mock import MagicMock, patch
from tests.unit.test_helper import BaseTestCase
from audio.recorder.cli import RecordAudioCLI
from audio.recorder.models.audio_config import AudioFormat
from audio.core.config import RecordAudioSettings


class TestCLI(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mock_recorder = MagicMock()
        self.mock_exporter = MagicMock()
        self.mock_logger = MagicMock()
        self.cli = RecordAudioCLI(self.mock_recorder, self.mock_exporter, self.mock_logger, RecordAudioSettings())

    def test_determine_format_from_extension(self) -> None:
        self.assertEqual(self.cli._determine_format("test.mp3", None), AudioFormat.MP3)
        self.assertEqual(self.cli._determine_format("test.WAV", None), AudioFormat.WAV)

    def test_determine_format_from_arg(self) -> None:
        self.assertEqual(self.cli._determine_format("test.txt", "flac"), AudioFormat.FLAC)

    def test_determine_format_default(self) -> None:
        self.assertEqual(self.cli._determine_format("test.unknown", None), AudioFormat.FLAC)
        self.assertEqual(self.cli._determine_format(None, None), AudioFormat.FLAC)

    def test_generate_default_filename(self) -> None:
        filename = self.cli._generate_default_filename(AudioFormat.MP3)
        self.assertTrue(filename.endswith(".mp3"))
        # Format is YYYY-mm-dd-hh-mm
        self.assertEqual(len(filename), 16 + 4) # 16 for timestamp, 4 for .mp3

    @patch("argparse.ArgumentParser.parse_args")
    def test_run_success_with_filename(self, mock_parse_args: MagicMock) -> None:
        mock_parse_args.return_value = MagicMock(
            filename="test.wav",
            format=None,
            samplerate=44100,
            channels=1
        )
        self.mock_recorder.record.return_value = MagicMock(size=100)
        
        self.cli.run()
        
        self.mock_recorder.record.assert_called_once()
        self.mock_exporter.export.assert_called_once()

    @patch("argparse.ArgumentParser.parse_args")
    def test_run_success_no_filename(self, mock_parse_args: MagicMock) -> None:
        mock_parse_args.return_value = MagicMock(
            filename=None,
            format="mp3",
            samplerate=44100,
            channels=1
        )
        self.mock_recorder.record.return_value = MagicMock(size=100)
        
        self.cli.run()
        
        # Check that it recorded and exported
        self.mock_recorder.record.assert_called_once()
        self.mock_exporter.export.assert_called_once()
        
        # Check that the filename in the config passed to export ends with .mp3
        config = self.mock_exporter.export.call_args[0][1]
        self.assertTrue(config.filename.endswith(".mp3"))
