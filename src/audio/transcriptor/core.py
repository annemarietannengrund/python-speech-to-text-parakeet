import logging
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Set
from audio.core import AudioFormat
from audio.converter import AudioConverter
from audio.converter.models.conversion_config import ConversionConfig
from audio.recorder.interfaces.audio_protocols import AudioRecorder, AudioExporter
from audio.recorder.models.audio_config import RecordingConfig
from audio.transcriptor.interfaces.transcription_protocols import TranscriptionService
from audio.transcriptor.models.transcription_config import TranscriptionConfig

TranscriptionServiceFactory = Callable[[], TranscriptionService]

class SpeechToTextProcessor:
    SUPPORTED_INPUT_FORMATS: Set[AudioFormat] = {
        AudioFormat.MP3,
        AudioFormat.MP4,
        AudioFormat.M4A,
        AudioFormat.WAV,
        AudioFormat.OGG,
        AudioFormat.FLAC
    }

    def __init__(
        self,
        transcription_service_factory: TranscriptionServiceFactory,
        converter: AudioConverter,
        recorder: AudioRecorder,
        exporter: AudioExporter,
        logger: logging.Logger
    ) -> None:
        self._transcription_service_factory = transcription_service_factory
        self._transcription_service: TranscriptionService | None = None
        self.converter = converter
        self.recorder = recorder
        self.exporter = exporter
        self.logger = logger

    @property
    def transcription_service(self) -> TranscriptionService:
        if self._transcription_service is None:
            self.logger.info("Initializing transcription service...")
            self._transcription_service = self._transcription_service_factory()
        return self._transcription_service

    def process(self, config: TranscriptionConfig) -> None:
        if config.record:
            self._handle_recording(config)
            return

        if not config.path:
            raise ValueError("Path is required when not recording.")

        if config.path.is_file():
            self._process_file(config.path, config, config.path.parent)
        elif config.path.is_dir():
            self._process_directory(config.path, config)
        else:
            raise FileNotFoundError(f"Path not found: {config.path}")

    def _handle_recording(self, config: TranscriptionConfig) -> None:
        recording_format = config.recording_format
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
        filename = f"{timestamp}.{recording_format.value}"
        recording_path = Path.cwd() / filename
        
        recording_config = RecordingConfig(
            filename=str(recording_path),
            format=recording_format,
            samplerate=44100,
            channels=1
        )
        
        try:
            self.logger.info("Starting recording...")
            data = self.recorder.record(recording_config)
            if data.size > 0:
                self.exporter.export(data, recording_config)
                self.logger.info("Recording saved to %s", recording_path)
                
                # Transcribe
                text = self.transcription_service.transcribe(
                    recording_path,
                    model=config.model
                )
                
                # Output
                output_path = recording_path.with_suffix(f".{config.output_format}")
                if config.output_dir:
                    config.output_dir.mkdir(parents=True, exist_ok=True)
                    output_path = config.output_dir / output_path.name

                output_path.write_text(text, encoding="utf-8")
                self.logger.info("Transcription saved to %s", output_path)
                print(f"\nTranscription:\n{text}")
                
                if config.cleanup_audio:
                    self.logger.info("Deleting recording %s", recording_path)
                    recording_path.unlink(missing_ok=True)
                
                if config.cleanup_transcription:
                    self.logger.info("Deleting transcription %s", output_path)
                    output_path.unlink(missing_ok=True)
            else:
                self.logger.warning("No audio data recorded.")
        except Exception as e:
            self.logger.error("Error during recording/transcription: %s", e)

    def _process_directory(self, directory: Path, config: TranscriptionConfig) -> None:
        files = []
        for ext in self.SUPPORTED_INPUT_FORMATS:
            pattern = f"*.{ext.value}"
            if config.recursive:
                files.extend(directory.rglob(pattern))
            else:
                files.extend(directory.glob(pattern))
        
        if not files:
            self.logger.warning("No supported audio files found in %s", directory)
            return

        for file_path in files:
            try:
                self._process_file(file_path, config, directory)
            except Exception as e:
                self.logger.error("Failed to process %s: %s", file_path, e)

    def _process_file(self, file_path: Path, config: TranscriptionConfig, base_path: Path) -> None:
        output_path = file_path.with_suffix(f".{config.output_format}")
        
        if config.output_dir:
            relative_path = file_path.relative_to(base_path)
            output_path = config.output_dir / relative_path.with_suffix(f".{config.output_format}")
            output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists() and not config.no_skip:
            self.logger.info("Skipping %s as output already exists.", file_path)
            return
        
        if output_path.exists() and config.no_skip:
            self.logger.warning("Overwriting existing transcription for %s", file_path)

        # Handle conversion if needed
        transcribe_path = file_path
        temp_file: Path | None = None
        
        file_ext_str = file_path.suffix.lower().lstrip('.')
        try:
            file_format = AudioFormat(file_ext_str)
        except ValueError:
            self.logger.warning("Unsupported file format: %s. Skipping %s", file_ext_str, file_path)
            return

        if file_format not in self.transcription_service.supported_input_formats:
            target_format = config.preconversion_format
            self.logger.info(
                "Converting %s to temporary %s for transcription",
                file_path,
                target_format.value,
            )
            temp_file = Path(tempfile.mktemp(suffix=f".tmp.{target_format.value}"))
            conv_config = ConversionConfig(
                input_path=file_path,
                output_path=temp_file,
                to_format=target_format,
                overwrite=True
            )
            self.converter.convert(conv_config)
            transcribe_path = temp_file

        try:
            text = self.transcription_service.transcribe(
                transcribe_path,
                model=config.model
            )
            output_path.write_text(text, encoding="utf-8")
            self.logger.info("Transcription saved to %s", output_path)
            print(f"\nTranscription ({file_path.name}):\n{text}")

            if config.cleanup_transcription:
                self.logger.info("Deleting transcription %s", output_path)
                output_path.unlink(missing_ok=True)
            
            if config.cleanup_audio:
                self.logger.info("Deleting audio file %s", file_path)
                file_path.unlink(missing_ok=True)
        finally:
            if temp_file:
                try:
                    temp_file.unlink(missing_ok=True)
                except Exception as e:
                    self.logger.warning("Failed to delete temporary file %s: %s", temp_file, e)
