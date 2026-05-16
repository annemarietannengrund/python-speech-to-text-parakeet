import argparse
import logging
import sys
from datetime import datetime
from audio.recorder.core import Recorder, Exporter
from audio.core import AudioFormat
from audio.core import RecordAudioSettings, load_settings
from audio.recorder.models.audio_config import RecordingConfig
from audio.recorder.interfaces.audio_protocols import AudioRecorder, AudioExporter


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("record_audio")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


class RecordAudioCLI:
    DEFAULT_DATE_FORMAT = "%Y-%m-%d-%H-%M"

    def __init__(
            self,
            recorder: AudioRecorder,
            exporter: AudioExporter,
            logger: logging.Logger,
            settings: RecordAudioSettings
    ) -> None:
        self.recorder = recorder
        self.exporter = exporter
        self.logger = logger
        self.settings = settings

    def run(self) -> None:
        parser = argparse.ArgumentParser(description="Record audio to various formats.")
        parser.add_argument("filename", nargs="?", help="Output filename (optional)")
        parser.add_argument("--format", choices=[f.value for f in AudioFormat],
                            help=f"Output format (default: {self.settings.default_format.value})")
        parser.add_argument("--samplerate", type=int, default=self.settings.default_samplerate,
                            help=f"Samplerate (default: {self.settings.default_samplerate})")
        parser.add_argument("--channels", type=int, default=self.settings.default_channels,
                            help=f"Number of channels (default: {self.settings.default_channels})")

        args = parser.parse_args()

        audio_format = self._determine_format(args.filename, args.format)
        filename = args.filename or self._generate_default_filename(audio_format)

        config = RecordingConfig(
            filename=filename,
            format=audio_format,
            samplerate=args.samplerate,
            channels=args.channels
        )

        try:
            self.logger.info("Recording to: %s", config.filename)
            data = self.recorder.record(config)
            if data.size > 0:
                self.exporter.export(data, config)
            else:
                self.logger.warning("No audio data recorded, skipping export.")
        except Exception as e:
            self.logger.error("An error occurred: %s", e)
            sys.exit(1)

    def _determine_format(self, filename: str | None, format_arg: str | None) -> AudioFormat:
        if format_arg:
            return AudioFormat(format_arg)

        if filename:
            extension = filename.split(".")[-1].lower()
            try:
                return AudioFormat(extension)
            except ValueError:
                self.logger.info("Could not determine format from extension, defaulting to %s",
                                 self.settings.default_format.value)

        return self.settings.default_format

    def _generate_default_filename(self, audio_format: AudioFormat) -> str:
        timestamp = datetime.now().strftime(self.settings.date_format)
        return f"{timestamp}.{audio_format.value}"


def main() -> None:
    settings = load_settings()
    logger = setup_logging()
    recorder = Recorder()
    exporter = Exporter()
    cli = RecordAudioCLI(recorder, exporter, logger, settings.record)
    cli.run()


if __name__ == "__main__":
    main()
