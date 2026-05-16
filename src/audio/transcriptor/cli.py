import argparse
import logging
import sys
from pathlib import Path

from audio.converter.core import FFmpegAudioConverter
from audio.core.config import load_settings, SpeechToTextSettings
from audio.recorder.core import Recorder, Exporter
from audio.transcriptor.core import SpeechToTextProcessor
from audio.transcriptor.models.transcription_config import TranscriptionConfig
from audio.transcriptor.models.provider import TranscriptionProvider
from audio.transcriptor.providers.registry import build_transcription_service, available_providers
from audio.transcriptor.verbosity import configure_verbosity


def setup_logging(verbose: bool) -> logging.Logger:
    logger = logging.getLogger("speech_to_text")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
    return logger


class SpeechToTextCLI:
    def __init__(self, processor: SpeechToTextProcessor, logger: logging.Logger,
                 settings: SpeechToTextSettings) -> None:
        self.processor = processor
        self.logger = logger
        self.settings = settings

    def run(self) -> None:
        parser = argparse.ArgumentParser(description="Transcribe audio files to text.")
        parser.add_argument("path", nargs="?", help="Path to an audio file or directory.")
        parser.add_argument("--recursive", action="store_true", help="Walk through folders recursively.")
        parser.add_argument("--record", action="store_true", help="Record live audio and transcribe it.")
        parser.add_argument("--cleanup",
                            help="Comma-separated list of items to delete after processing ('audio', 'transcription').")
        parser.add_argument("--format", choices=["txt", "md"], default="md", help="Output format (default: md).")
        parser.add_argument("--output-dir",
                            help="Custom directory to store transcriptions (recreates source structure).")
        parser.add_argument("--model", help=f"Transcription model (default: {self.settings.model}).")
        parser.add_argument("--provider", choices=[p.value for p in TranscriptionProvider],
                            default=self.settings.provider.value,
                            help=f"Transcription provider (default: {self.settings.provider.value}).")
        parser.add_argument("--no-skip", action="store_true",
                            help="Force transcription even if output file already exists.")
        parser.add_argument("--list-providers", action="store_true",
                            help="List available transcription providers and exit.")
        parser.add_argument("-v", "--verbose", action="store_true",
                            help="Show verbose output from transcription backends.")

        args = parser.parse_args()
        configure_verbosity(args.verbose)
        self.logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)

        if args.list_providers:
            for provider in available_providers():
                print(provider.value)
            return

        if not args.record and not args.path:
            parser.print_help()
            return

        cleanup_items = [item.strip().lower() for item in (args.cleanup or "").split(",") if item.strip()]

        cleanup_audio = "audio" in cleanup_items or "all" in cleanup_items
        cleanup_transcription = "transcription" in cleanup_items or "all" in cleanup_items

        config = TranscriptionConfig(
            path=Path(args.path) if args.path else None,
            recursive=args.recursive,
            record=args.record,
            persist_recording=not cleanup_audio,
            output_format=args.format,
            no_skip=args.no_skip,
            cleanup_audio=cleanup_audio,
            cleanup_transcription=cleanup_transcription,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            model=args.model or self.settings.model,
            preconversion_format=self.settings.preconversion_format,
            recording_format=self.settings.preconversion_format,
        )

        try:
            self.processor.process(config)
        except Exception as e:
            self.logger.error("Error: %s", e)
            sys.exit(1)


def main() -> None:
    verbose = any(flag in sys.argv for flag in ("-v", "--verbose"))
    configure_verbosity(verbose)
    settings = load_settings()
    logger = setup_logging(verbose)

    converter = FFmpegAudioConverter()
    recorder = Recorder()
    exporter = Exporter()

    processor = SpeechToTextProcessor(
        transcription_service_factory=lambda: build_transcription_service(settings.stt),
        converter=converter,
        recorder=recorder,
        exporter=exporter,
        logger=logger
    )

    cli = SpeechToTextCLI(processor, logger, settings.stt)
    cli.run()


if __name__ == "__main__":
    main()
