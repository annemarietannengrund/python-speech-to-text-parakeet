"""Entry point for ``speech-to-text-modern``.

A leaner, rich-styled variant of the classic ``speech-to-text`` CLI.
Currently focuses on the `--record` flow; file/folder transcription is
still served by the classic CLI to keep scope tight while we
experiment with terminal UX.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from audio.converter.core import FFmpegAudioConverter
from audio.core import AudioFormat
from audio.core.config import SpeechToTextSettings, load_settings
from audio.recorder.core import Exporter
from audio.transcriptor.models.provider import TranscriptionProvider
from audio.transcriptor.models.transcription_config import TranscriptionConfig
from audio.transcriptor.providers.registry import available_providers, build_transcription_service
from audio.transcriptor.verbosity import configure_verbosity
from audio.transcriptor_modern.audio_info import probe_audio
from audio.transcriptor_modern.models.ui_state import Phase, UIState
from audio.transcriptor_modern.post_actions import copy_to_clipboard, send_notification
from audio.transcriptor_modern.processor import ModernSpeechToTextProcessor
from audio.transcriptor_modern.ui.presenter import LivePresenter, NullPresenter

_SUPPORTED_INPUT_FORMATS: frozenset[AudioFormat] = frozenset({
    AudioFormat.MP3, AudioFormat.MP4, AudioFormat.M4A,
    AudioFormat.WAV, AudioFormat.OGG, AudioFormat.FLAC,
})

_CLEANUP_AUDIO_TOKENS: frozenset[str] = frozenset({"audio", "all"})
_CLEANUP_TRANSCRIPTION_TOKENS: frozenset[str] = frozenset({"transcription", "all"})
_ENV_COPY: str = "STT_COPY"
_ENV_NOTIFY: str = "STT_NOTIFY"
_TRUTHY: frozenset[str] = frozenset({"1", "true", "yes", "on"})
_NOTIFY_TITLE: str = "speech-to-text"
_NOTIFY_MESSAGE: str = "Transcription ready"


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def setup_logging(verbose: bool) -> logging.Logger:
    """Initialise the top-level `speech_to_text` logger.

    Default level is WARNING so that the rich UI stays the primary
    feedback channel; ``--verbose`` flips it to INFO/DEBUG.
    """
    logger = logging.getLogger("speech_to_text")
    logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)
    return logger


def _build_parser(settings: SpeechToTextSettings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name or "speech-to-text-modern",
        description="Record live audio and transcribe it with a rich live UI.",
    )
    parser.add_argument("path", nargs="?", help="Path to an audio file or directory.")
    parser.add_argument("--recursive", action="store_true", help="Walk through folders recursively.")
    parser.add_argument("--record", action="store_true", help="Record live audio and transcribe it.")
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Force transcription even if output file already exists.",
    )
    parser.add_argument(
        "--cleanup",
        help="Comma-separated items to delete after the run ('audio', 'transcription', 'all').",
    )
    parser.add_argument("--format", choices=["txt", "md"], default="md", help="Output format (default: md).")
    parser.add_argument("--output-dir", help="Custom directory to store transcriptions.")
    parser.add_argument("--model", help=f"Transcription model (default: {settings.model}).")
    parser.add_argument(
        "--provider",
        choices=[p.value for p in TranscriptionProvider],
        default=settings.provider.value,
        help=f"Transcription provider (default: {settings.provider.value}).",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List available transcription providers and exit.",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help=f"Copy the transcription to the system clipboard (env: {_ENV_COPY}=1).",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help=f"Show a system notification when transcription is ready (env: {_ENV_NOTIFY}=1).",
    )
    parser.add_argument(
        "--pipe",
        action="store_true",
        help="Suppress UI/logs and print only the transcription to stdout (pipe-friendly).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging.")
    return parser


def _cleanup_flags(raw: str | None) -> tuple[bool, bool]:
    tokens = {item.strip().lower() for item in (raw or "").split(",") if item.strip()}
    return (
        bool(tokens & _CLEANUP_AUDIO_TOKENS),
        bool(tokens & _CLEANUP_TRANSCRIPTION_TOKENS),
    )


def _build_config(args: argparse.Namespace, settings: SpeechToTextSettings) -> TranscriptionConfig:
    cleanup_audio, cleanup_transcription = _cleanup_flags(args.cleanup)
    return TranscriptionConfig(
        path=Path(args.path) if args.path else None,
        recursive=args.recursive,
        record=args.record,
        no_skip=args.no_skip,
        persist_recording=not cleanup_audio,
        output_format=args.format,
        cleanup_audio=cleanup_audio,
        cleanup_transcription=cleanup_transcription,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        model=args.model or settings.model,
        preconversion_format=settings.preconversion_format,
        recording_format=settings.preconversion_format,
    )


def main() -> None:
    verbose = any(flag in sys.argv for flag in ("-v", "--verbose"))
    configure_verbosity(verbose)
    settings = load_settings()
    logger = setup_logging(verbose)

    parser = _build_parser(settings.stt)
    args = parser.parse_args()
    logger.setLevel(logging.DEBUG if args.verbose else logging.WARNING)

    if args.list_providers:
        for provider in available_providers():
            print(provider.value)
        return

    if not args.record and not args.path:
        parser.print_help()
        return

    config = _build_config(args, settings.stt)

    if args.pipe:
        logger.setLevel(logging.CRITICAL)

    state = UIState()
    presenter: LivePresenter | NullPresenter = NullPresenter() if args.pipe else LivePresenter(state)
    processor = ModernSpeechToTextProcessor(
        transcription_service_factory=lambda: build_transcription_service(settings.stt),
        exporter=Exporter(),
        presenter=presenter,
        state=state,
        converter=FFmpegAudioConverter(),
    )

    if args.record:
        with presenter:
            outcome = processor.run_recording(config)
        if state.phase == Phase.ERROR:
            if not args.pipe:
                logger.error("No audio captured.")
            sys.exit(1)
        _apply_post_actions(args, outcome)
        if args.pipe:
            sys.stdout.write(outcome.transcript)
        else:
            presenter.print_summary(outcome.summary, outcome.transcript)
        return

    _run_file_mode(processor, presenter, config, args, logger)


def _collect_files(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"Path not found: {path}")
    matches: list[Path] = []
    for fmt in _SUPPORTED_INPUT_FORMATS:
        pattern = f"*.{fmt.value}"
        matches.extend(path.rglob(pattern) if recursive else path.glob(pattern))
    return sorted(matches)


def _run_file_mode(
    processor: ModernSpeechToTextProcessor,
    presenter: LivePresenter | NullPresenter,
    config: TranscriptionConfig,
    args: argparse.Namespace,
    logger: logging.Logger,
) -> None:
    if config.path is None:
        raise ValueError("Path is required when not recording.")
    files = _collect_files(config.path, config.recursive)
    if not files:
        logger.warning("No supported audio files found in %s", config.path)
        return
    base_path = config.path if config.path.is_dir() else config.path.parent

    for file_path in files:
        presenter.print_file_info(probe_audio(file_path))
        with presenter:
            outcome = processor.run_file(file_path, config, base_path)
        if outcome is None:
            logger.info("Skipped %s", file_path)
            continue
        _apply_post_actions(args, outcome)
        if args.pipe:
            sys.stdout.write(outcome.transcript)
            if not outcome.transcript.endswith("\n"):
                sys.stdout.write("\n")
        else:
            presenter.print_summary(outcome.summary, outcome.transcript)


def _apply_post_actions(args: argparse.Namespace, outcome) -> None:  # noqa: ANN001 — _Outcome is private
    copy_enabled = args.copy or _env_flag(_ENV_COPY)
    notify_enabled = args.notify or _env_flag(_ENV_NOTIFY)
    if copy_enabled:
        outcome.summary.extras.append(copy_to_clipboard(outcome.transcript).label)
    if notify_enabled:
        outcome.summary.extras.append(send_notification(_NOTIFY_TITLE, _NOTIFY_MESSAGE).label)


if __name__ == "__main__":
    main()
