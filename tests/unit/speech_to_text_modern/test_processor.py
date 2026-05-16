from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from audio.core import AudioFormat
from audio.transcriptor.models.transcription_config import TranscriptionConfig
from audio.transcriptor_modern.models.ui_state import Phase, UIState
from audio.transcriptor_modern.processor import ModernSpeechToTextProcessor
from tests.unit.test_helper import BaseTestCase


class TestModernSpeechToTextProcessor(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.state = UIState()
        self.presenter = Mock()
        self.exporter = Mock()
        self.service = Mock()
        self.service.transcribe.return_value = "hello"
        self.service_factory = Mock(return_value=self.service)
        self.processor = ModernSpeechToTextProcessor(
            transcription_service_factory=self.service_factory,
            exporter=self.exporter,
            presenter=self.presenter,
            state=self.state,
        )

    def _patch_recorder(self, audio: np.ndarray) -> Mock:
        recorder = Mock()
        recorder.record.return_value = audio
        return recorder

    def _make_config(self, cleanup_audio: bool = False, cleanup_transcription: bool = False) -> TranscriptionConfig:
        return TranscriptionConfig(
            record=True,
            output_format="md",
            cleanup_audio=cleanup_audio,
            cleanup_transcription=cleanup_transcription,
            recording_format=AudioFormat.FLAC,
        )

    @patch("audio.transcriptor_modern.processor.ModernRecorder")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.unlink")
    def test_full_run_writes_transcription_and_reaches_done(
        self,
        mock_unlink: Mock,
        mock_write: Mock,
        mock_recorder_cls: Mock,
    ) -> None:
        audio = np.ones(44100, dtype=np.float32)  # 1 second
        mock_recorder_cls.return_value = self._patch_recorder(audio)

        outcome = self.processor.run_recording(self._make_config())

        self.assertEqual(outcome.transcript, "hello")
        self.assertEqual(self.state.phase, Phase.DONE)
        self.service_factory.assert_called_once()
        self.service.transcribe.assert_called_once()
        self.exporter.export.assert_called_once()
        mock_write.assert_called_once()
        mock_unlink.assert_not_called()
        self.assertAlmostEqual(outcome.summary.record_seconds, 1.0, places=2)

    @patch("audio.transcriptor_modern.processor.ModernRecorder")
    def test_empty_recording_sets_error_phase(self, mock_recorder_cls: Mock) -> None:
        mock_recorder_cls.return_value = self._patch_recorder(np.array([], dtype=np.float32))

        outcome = self.processor.run_recording(self._make_config())

        self.assertEqual(self.state.phase, Phase.ERROR)
        self.assertEqual(outcome.transcript, "")
        # Factory is invoked eagerly on a background thread for parallel preload;
        # transcribe must not be called because there is no audio to process.
        self.service_factory.assert_called_once()
        self.service.transcribe.assert_not_called()
        self.exporter.export.assert_not_called()

    @patch("audio.transcriptor_modern.processor.ModernRecorder")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.unlink")
    def test_cleanup_all_deletes_both_files(
        self,
        mock_unlink: Mock,
        mock_write: Mock,
        mock_recorder_cls: Mock,
    ) -> None:
        audio = np.ones(4410, dtype=np.float32)
        mock_recorder_cls.return_value = self._patch_recorder(audio)

        self.processor.run_recording(
            self._make_config(cleanup_audio=True, cleanup_transcription=True)
        )

        self.assertEqual(mock_unlink.call_count, 2)
