from pathlib import Path
from unittest.mock import Mock, patch

from audio.core import AudioFormat
from audio.transcriptor.models.transcription_config import TranscriptionConfig
from audio.transcriptor_modern.models.ui_state import Phase, UIState
from audio.transcriptor_modern.processor import ModernSpeechToTextProcessor
from tests.unit.test_helper import BaseTestCase


def _make_config(no_skip: bool = True) -> TranscriptionConfig:
    return TranscriptionConfig(
        path=Path("/tmp/sample.m4a"),
        record=False,
        no_skip=no_skip,
        output_format="md",
        recording_format=AudioFormat.FLAC,
        preconversion_format=AudioFormat.FLAC,
    )


class TestRunFile(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.state = UIState()
        self.presenter = Mock()
        self.exporter = Mock()
        self.converter = Mock()
        self.service = Mock()
        self.service.supported_input_formats = {AudioFormat.M4A}
        self.service.transcribe.return_value = "hello world"
        self.service_factory = Mock(return_value=self.service)
        self.processor = ModernSpeechToTextProcessor(
            transcription_service_factory=self.service_factory,
            exporter=self.exporter,
            presenter=self.presenter,
            state=self.state,
            converter=self.converter,
        )

    @patch("pathlib.Path.exists", return_value=False)
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.mkdir")
    def test_transcribes_and_writes_output(self, _mkdir: Mock, mock_write: Mock, _exists: Mock) -> None:
        outcome = self.processor.run_file(Path("/tmp/sample.m4a"), _make_config(), Path("/tmp"))
        self.assertIsNotNone(outcome)
        assert outcome is not None
        self.assertEqual("hello world", outcome.transcript)
        self.service.transcribe.assert_called_once_with(Path("/tmp/sample.m4a"), model=None)
        mock_write.assert_called_once_with("hello world", encoding="utf-8")
        self.assertEqual(Phase.DONE, self.state.phase)
        self.converter.convert.assert_not_called()

    @patch("pathlib.Path.exists", return_value=True)
    def test_skips_when_output_exists_and_no_skip_false(self, _exists: Mock) -> None:
        outcome = self.processor.run_file(
            Path("/tmp/sample.m4a"),
            _make_config(no_skip=False),
            Path("/tmp"),
        )
        self.assertIsNone(outcome)
        self.service.transcribe.assert_not_called()

    @patch("pathlib.Path.unlink")
    @patch("pathlib.Path.exists", return_value=False)
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.mkdir")
    def test_converts_when_format_unsupported(self, _mkdir: Mock, _write: Mock, _exists: Mock, _unlink: Mock) -> None:
        self.service.supported_input_formats = {AudioFormat.WAV}
        outcome = self.processor.run_file(Path("/tmp/sample.m4a"), _make_config(), Path("/tmp"))
        self.assertIsNotNone(outcome)
        self.converter.convert.assert_called_once()
        conv_call = self.converter.convert.call_args.args[0]
        self.assertEqual(Path("/tmp/sample.m4a"), conv_call.input_path)
        self.assertEqual(AudioFormat.FLAC, conv_call.to_format)
