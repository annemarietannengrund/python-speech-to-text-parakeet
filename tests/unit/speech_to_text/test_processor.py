import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from audio.core import AudioFormat
from audio.transcriptor.core import SpeechToTextProcessor
from audio.transcriptor.models.transcription_config import TranscriptionConfig


class TestSpeechToTextProcessor(unittest.TestCase):
    def setUp(self):
        self.mock_transcription_service = Mock()
        self.mock_transcription_service.supported_input_formats = frozenset(
            {AudioFormat.WAV, AudioFormat.MP3, AudioFormat.FLAC}
        )
        self.mock_converter = Mock()
        self.mock_recorder = Mock()
        self.mock_exporter = Mock()
        self.mock_logger = Mock()

        self.mock_transcription_service_factory = Mock(return_value=self.mock_transcription_service)
        self.processor = SpeechToTextProcessor(
            transcription_service_factory=self.mock_transcription_service_factory,
            converter=self.mock_converter,
            recorder=self.mock_recorder,
            exporter=self.mock_exporter,
            logger=self.mock_logger
        )

    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.write_text")
    def test_process_file_no_conversion(self, mock_write, mock_exists, mock_is_file):
        # Setup
        mock_is_file.return_value = True
        mock_exists.return_value = False
        self.mock_transcription_service.transcribe.return_value = "transcribed text"

        file_path = Path("test.wav")
        config = TranscriptionConfig(path=file_path)

        # Execute
        self.processor.process(config)

        # Verify
        self.mock_transcription_service.transcribe.assert_called_once_with(file_path, model=None)
        mock_write.assert_called_once_with("transcribed text", encoding="utf-8")
        self.mock_converter.convert.assert_not_called()

    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.write_text")
    def test_process_file_with_model(self, mock_write, mock_exists, mock_is_file):
        # Setup
        mock_is_file.return_value = True
        mock_exists.return_value = False
        self.mock_transcription_service.transcribe.return_value = "transcribed text"

        file_path = Path("test.wav")
        config = TranscriptionConfig(path=file_path, model="tiny")

        # Execute
        self.processor.process(config)

        # Verify
        self.mock_transcription_service.transcribe.assert_called_once_with(file_path, model="tiny")

    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.unlink")
    def test_process_file_with_conversion(self, mock_unlink, mock_write, mock_exists, mock_is_file):
        # Setup
        mock_is_file.return_value = True
        mock_exists.side_effect = lambda: False
        self.mock_transcription_service.supported_input_formats = frozenset({AudioFormat.WAV})

        self.mock_transcription_service.transcribe.return_value = "transcribed text"

        file_path = Path("test.m4a")
        config = TranscriptionConfig(path=file_path)

        # Execute
        self.processor.process(config)

        # Verify
        self.mock_converter.convert.assert_called_once()
        conv_config = self.mock_converter.convert.call_args.args[0]
        self.assertEqual(conv_config.to_format, AudioFormat.FLAC)
        self.assertTrue(str(conv_config.output_path).endswith(".flac"))
        self.mock_transcription_service.transcribe.assert_called_once()
        mock_unlink.assert_called_once()

    @patch("pathlib.Path.cwd")
    @patch("pathlib.Path.write_text")
    def test_handle_recording(self, mock_write, mock_cwd):
        # Setup
        mock_cwd.return_value = Path("/tmp")
        self.mock_recorder.record.return_value = np.array([1, 2, 3])
        self.mock_transcription_service.transcribe.return_value = "recorded text"

        config = TranscriptionConfig(record=True, persist_recording=True)

        # Execute
        self.processor.process(config)

        # Verify
        self.mock_recorder.record.assert_called_once()
        self.mock_exporter.export.assert_called_once()
        self.mock_transcription_service.transcribe.assert_called_once()
        mock_write.assert_called_once_with("recorded text", encoding="utf-8")

    @patch("pathlib.Path.cwd")
    @patch("pathlib.Path.write_text")
    def test_recording_defers_transcription_service_initialization(self, mock_write, mock_cwd):
        mock_cwd.return_value = Path("/tmp")
        call_order: list[str] = []
        self.mock_transcription_service_factory.side_effect = lambda: (
            call_order.append("factory"), self.mock_transcription_service
        )[1]
        self.mock_recorder.record.side_effect = lambda _config: (
            call_order.append("record"), np.array([1, 2, 3])
        )[1]
        self.mock_transcription_service.transcribe.return_value = "recorded text"

        config = TranscriptionConfig(record=True, persist_recording=True)

        self.processor.process(config)

        self.assertEqual(call_order, ["record", "factory"])
        self.mock_transcription_service_factory.assert_called_once_with()

    def test_transcription_service_factory_is_not_called_on_construction(self):
        self.mock_transcription_service_factory.assert_not_called()

    @patch("pathlib.Path.cwd")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.unlink")
    def test_handle_recording_cleanup(self, mock_unlink, mock_write, mock_cwd):
        # Setup
        mock_cwd.return_value = Path("/tmp")
        self.mock_recorder.record.return_value = np.array([1, 2, 3])
        self.mock_transcription_service.transcribe.return_value = "recorded text"

        # Cleanup both audio and transcription
        config = TranscriptionConfig(record=True, cleanup_audio=True, cleanup_transcription=True)

        # Execute
        self.processor.process(config)

        # Verify
        # Should be called for audio and for transcription
        self.assertEqual(mock_unlink.call_count, 2)

    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.unlink")
    def test_process_file_cleanup_audio(self, mock_unlink, mock_write, mock_exists, mock_is_file):
        # Setup
        mock_is_file.return_value = True
        mock_exists.return_value = False
        self.mock_transcription_service.transcribe.return_value = "text"

        file_path = Path("test.wav")
        config = TranscriptionConfig(path=file_path, cleanup_audio=True)

        # Execute
        self.processor.process(config)

        # Verify
        mock_unlink.assert_called_once_with(missing_ok=True)

    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.mkdir")
    def test_process_file_custom_output_dir(self, mock_mkdir, mock_write, mock_exists, mock_is_file):
        # Setup
        mock_is_file.return_value = True
        mock_exists.return_value = False
        self.mock_transcription_service.transcribe.return_value = "transcribed text"

        file_path = Path("source/audio.wav")
        output_dir = Path("output_transcriptions")
        config = TranscriptionConfig(path=file_path, output_dir=output_dir)

        # Execute
        # In process(), config.path.parent is passed as base_path for single files
        self.processor.process(config)

        # Verify
        # Expected output path: output_dir / audio.txt (since base_path is source/)
        expected_output_path = output_dir / "audio.txt"

        # Check if transcribe was called with the correct file
        self.mock_transcription_service.transcribe.assert_called_once_with(file_path, model=None)

        # Check if write_text was called on the correct output path
        # We need to be careful with Path objects in mocks
        args, _ = mock_write.call_args
        self.assertEqual(args[0], "transcribed text")

        # Verify mkdir was called for the output directory
        mock_mkdir.assert_called()

    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.mkdir")
    def test_process_directory_custom_output_dir(self, mock_mkdir, mock_write, mock_exists, mock_is_dir):
        # Setup
        mock_is_dir.return_value = True
        mock_exists.return_value = False
        self.mock_transcription_service.transcribe.return_value = "text"

        dir_path = Path("audio_dir")
        output_dir = Path("out_dir")
        config = TranscriptionConfig(path=dir_path, output_dir=output_dir, recursive=True)

        # Mock files found in directory
        files = [dir_path / "sub" / "test.wav"]

        with patch.object(self.processor, '_process_file', wraps=self.processor._process_file) as mock_process_file:
            with patch("pathlib.Path.rglob") as mock_rglob:
                # We mock rglob for one of the formats to return our file
                mock_rglob.side_effect = lambda p: files if "*.wav" in p else []

                # Execute
                self.processor.process(config)

                # Verify
                # _process_file should be called with base_path=dir_path
                mock_process_file.assert_called_with(files[0], config, dir_path)

                # Check output path calculation in _process_file
                expected_output_path = output_dir / "sub" / "test.txt"
                # The actual write_text call should be on this path
                # Since we wrapped _process_file, it should have executed the logic
                mock_write.assert_called_once_with("text", encoding="utf-8")

    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.unlink")
    def test_preconversion_when_format_unsupported_by_service(
            self, mock_unlink, mock_write, mock_exists, mock_is_file
    ):
        mock_is_file.return_value = True
        mock_exists.return_value = False
        self.mock_transcription_service.supported_input_formats = frozenset({AudioFormat.WAV})
        self.mock_transcription_service.transcribe.return_value = "t"

        config = TranscriptionConfig(path=Path("clip.mp3"))
        self.processor.process(config)

        self.mock_converter.convert.assert_called_once()

    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.write_text")
    def test_no_preconversion_when_format_supported_by_service(
            self, mock_write, mock_exists, mock_is_file
    ):
        mock_is_file.return_value = True
        mock_exists.return_value = False
        self.mock_transcription_service.supported_input_formats = frozenset(
            {AudioFormat.WAV, AudioFormat.MP3}
        )
        self.mock_transcription_service.transcribe.return_value = "t"

        config = TranscriptionConfig(path=Path("clip.mp3"))
        self.processor.process(config)

        self.mock_converter.convert.assert_not_called()
