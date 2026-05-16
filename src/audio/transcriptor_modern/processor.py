"""Modern speech-to-text processor.

Orchestrates the record → save → transcribe → cleanup pipeline while
feeding a shared :class:`UIState` that the presenter renders live.

Both the transcription service load **and** the actual transcription
run on background threads. The main thread drives the UI ticks while
waiting, so the spinner keeps animating even though the underlying
inference holds the GIL most of the time inside native code.
"""
from __future__ import annotations

import logging
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypeVar

import numpy as np

from audio.core import AudioFormat
from audio.converter.interfaces.converter_protocols import AudioConverter
from audio.converter.models.conversion_config import ConversionConfig
from audio.recorder.interfaces.audio_protocols import AudioExporter
from audio.recorder.models.audio_config import RecordingConfig
from audio.transcriptor.core import TranscriptionServiceFactory
from audio.transcriptor.interfaces.transcription_protocols import TranscriptionService
from audio.transcriptor.models.transcription_config import TranscriptionConfig
from audio.transcriptor_modern.models.ui_state import FinalSummary, Phase, UIState
from audio.transcriptor_modern.recording import ModernRecorder
from audio.transcriptor_modern.ui.presenter import LivePresenter, NullPresenter

logger = logging.getLogger(__name__)

_TICKER_INTERVAL: float = 0.1
_MODEL_READY_HOLD: float = 0.4  # seconds the "Model ready" badge stays visible
_TRANSCRIBING_MIN_VISIBLE: float = 0.6  # ensure the TRANSCRIBING phase is perceivable
                                        # even when inference finishes in < 1s

T = TypeVar("T")


@dataclass
class _Outcome:
    transcript: str
    summary: FinalSummary


class ElapsedTicker:
    """Background thread that updates `state.elapsed_seconds` until stopped."""

    def __init__(self, state: UIState, presenter: LivePresenter | NullPresenter, interval: float = _TICKER_INTERVAL) -> None:
        self._state = state
        self._presenter = presenter
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_time: float = 0.0

    def __enter__(self) -> "ElapsedTicker":
        self._start_time = time.monotonic()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._state.elapsed_seconds = time.monotonic() - self._start_time
            self._presenter.refresh()
            self._stop_event.wait(self._interval)


class BackgroundJob[T]:
    """Runs a callable on a daemon thread; exposes done/result/wait API.

    Used to keep blocking work (model load, model inference) off the
    main thread so the main thread can keep driving the live UI.
    """

    def __init__(self, work: Callable[[], T]) -> None:
        self._work = work
        self._value: T | None = None
        self._error: BaseException | None = None
        self._done = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> "BackgroundJob[T]":
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def is_done(self) -> bool:
        return self._done.is_set()

    def wait(self, timeout: float) -> bool:
        return self._done.wait(timeout)

    def result(self) -> T:
        self._done.wait()
        if self._error is not None:
            raise self._error
        return self._value  # type: ignore[return-value]

    def _run(self) -> None:
        try:
            self._value = self._work()
        except BaseException as exc:  # noqa: BLE001 — re-raised in result()
            self._error = exc
        finally:
            self._done.set()


class ModernSpeechToTextProcessor:
    """High-level orchestrator for the modern CLI."""

    def __init__(
        self,
        transcription_service_factory: TranscriptionServiceFactory,
        exporter: AudioExporter,
        presenter: LivePresenter | NullPresenter,
        state: UIState,
        converter: AudioConverter | None = None,
    ) -> None:
        self._service_factory = transcription_service_factory
        self._exporter = exporter
        self._presenter = presenter
        self._state = state
        self._converter = converter
        self._service: TranscriptionService | None = None

    def run_recording(self, config: TranscriptionConfig) -> _Outcome:
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
        recording_path = Path.cwd() / f"{timestamp}.{config.recording_format.value}"
        recording_config = RecordingConfig(
            filename=str(recording_path),
            format=config.recording_format,
            samplerate=44100,
            channels=1,
        )

        service_job = self._start_service_job()

        audio = self._record(recording_config)
        if audio.size == 0:
            self._state.phase = Phase.ERROR
            self._state.message = "no audio captured"
            self._presenter.refresh()
            return _Outcome("", FinalSummary())

        record_seconds = float(audio.shape[0]) / float(recording_config.samplerate)
        self._exporter.export(audio, recording_config)
        self._state.recording_path = recording_path

        service = self._await_service(service_job)

        self._state.phase = Phase.TRANSCRIBING
        self._state.elapsed_seconds = 0.0
        self._state.level = 0.0
        self._presenter.refresh()
        started = time.monotonic()
        transcribe_job: BackgroundJob[str] = BackgroundJob(
            lambda: service.transcribe(recording_path, model=config.model)
        ).start()
        self._drive_ui_until_done(transcribe_job, started)
        transcript = transcribe_job.result()
        transcribe_seconds = time.monotonic() - started
        # Guarantee the TRANSCRIBING phase stays on screen long enough
        # to be perceived even when inference is sub-second.
        remaining_visible = _TRANSCRIBING_MIN_VISIBLE - transcribe_seconds
        if remaining_visible > 0:
            time.sleep(remaining_visible)

        output_path = recording_path.with_suffix(f".{config.output_format}")
        if config.output_dir:
            config.output_dir.mkdir(parents=True, exist_ok=True)
            output_path = config.output_dir / output_path.name
        output_path.write_text(transcript, encoding="utf-8")
        self._state.transcription_path = output_path

        self._cleanup(config, recording_path, output_path)

        self._state.phase = Phase.DONE
        self._state.transcribe_seconds = transcribe_seconds
        self._state.record_seconds = record_seconds

        return _Outcome(
            transcript=transcript,
            summary=FinalSummary(
                record_seconds=record_seconds,
                transcribe_seconds=transcribe_seconds,
                recording_path=recording_path if not config.cleanup_audio else None,
                transcription_path=output_path if not config.cleanup_transcription else None,
            ),
        )

    def run_file(self, file_path: Path, config: TranscriptionConfig, base_path: Path) -> _Outcome | None:
        """Transcribe a single audio file with the rich live UI.

        Returns ``None`` when the file is skipped (output already exists
        and ``no_skip`` is false) or the format is unsupported.
        """
        output_path = self._resolve_output_path(file_path, config, base_path)
        if output_path.exists() and not config.no_skip:
            self._state.phase = Phase.IDLE
            self._state.message = f"skipping {file_path.name} (output exists)"
            self._presenter.refresh()
            return None

        file_format = self._safe_audio_format(file_path)
        if file_format is None:
            self._state.phase = Phase.ERROR
            self._state.message = f"unsupported format: {file_path.suffix}"
            self._presenter.refresh()
            return None

        service_job = self._start_service_job()
        service = self._await_service(service_job)

        transcribe_path, temp_file = self._prepare_for_transcription(file_path, file_format, service, config)
        try:
            self._state.phase = Phase.TRANSCRIBING
            self._state.elapsed_seconds = 0.0
            self._state.level = 0.0
            self._state.message = None
            self._presenter.refresh()
            started = time.monotonic()
            transcribe_job: BackgroundJob[str] = BackgroundJob(
                lambda: service.transcribe(transcribe_path, model=config.model)
            ).start()
            self._drive_ui_until_done(transcribe_job, started)
            transcript = transcribe_job.result()
            transcribe_seconds = time.monotonic() - started
            remaining_visible = _TRANSCRIBING_MIN_VISIBLE - transcribe_seconds
            if remaining_visible > 0:
                time.sleep(remaining_visible)
        finally:
            if temp_file is not None:
                temp_file.unlink(missing_ok=True)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(transcript, encoding="utf-8")
        self._state.transcription_path = output_path

        self._cleanup_file_outputs(config, file_path, output_path)

        self._state.phase = Phase.DONE
        self._state.transcribe_seconds = transcribe_seconds

        return _Outcome(
            transcript=transcript,
            summary=FinalSummary(
                transcribe_seconds=transcribe_seconds,
                recording_path=file_path if not config.cleanup_audio else None,
                transcription_path=output_path if not config.cleanup_transcription else None,
            ),
        )

    def _start_service_job(self) -> BackgroundJob[TranscriptionService]:
        if self._service is not None:
            cached = self._service

            def _return_cached() -> TranscriptionService:
                return cached

            return BackgroundJob(_return_cached).start()
        return BackgroundJob(self._service_factory).start()

    def _resolve_output_path(self, file_path: Path, config: TranscriptionConfig, base_path: Path) -> Path:
        output_path = file_path.with_suffix(f".{config.output_format}")
        if config.output_dir is None:
            return output_path
        relative = file_path.relative_to(base_path)
        return config.output_dir / relative.with_suffix(f".{config.output_format}")

    def _safe_audio_format(self, file_path: Path) -> AudioFormat | None:
        suffix = file_path.suffix.lower().lstrip(".")
        try:
            return AudioFormat(suffix)
        except ValueError:
            return None

    def _prepare_for_transcription(
        self,
        file_path: Path,
        file_format: AudioFormat,
        service: TranscriptionService,
        config: TranscriptionConfig,
    ) -> tuple[Path, Path | None]:
        if file_format in service.supported_input_formats:
            return file_path, None
        if self._converter is None:
            raise RuntimeError("Audio converter required to transcode unsupported formats.")
        target_format = config.preconversion_format
        self._state.message = f"converting to {target_format.value}"
        self._presenter.refresh()
        temp_file = Path(tempfile.mktemp(suffix=f".tmp.{target_format.value}"))
        self._converter.convert(ConversionConfig(
            input_path=file_path,
            output_path=temp_file,
            to_format=target_format,
            overwrite=True,
        ))
        self._state.message = None
        return temp_file, temp_file

    def _cleanup_file_outputs(self, config: TranscriptionConfig, source: Path, output_path: Path) -> None:
        if not (config.cleanup_audio or config.cleanup_transcription):
            return
        self._state.phase = Phase.CLEANUP
        self._presenter.refresh()
        if config.cleanup_audio:
            source.unlink(missing_ok=True)
        if config.cleanup_transcription:
            output_path.unlink(missing_ok=True)

    def _await_service(self, job: BackgroundJob[TranscriptionService]) -> TranscriptionService:
        if job.is_done():
            self._state.phase = Phase.MODEL_READY
            self._presenter.refresh()
            service = job.result()
            self._service = service
            time.sleep(_MODEL_READY_HOLD)
            return service

        self._state.phase = Phase.LOADING_MODEL
        self._state.level = 0.0
        self._state.message = None
        self._state.elapsed_seconds = 0.0
        self._presenter.refresh()
        started = time.monotonic()
        self._drive_ui_until_done(job, started)
        service = job.result()
        self._service = service
        self._state.phase = Phase.MODEL_READY
        self._presenter.refresh()
        time.sleep(_MODEL_READY_HOLD)
        return service

    def _drive_ui_until_done(self, job: BackgroundJob[object], start_time: float) -> None:
        """Pump UI refreshes from the main thread until `job` completes.

        Running this on the main thread (rather than a daemon ticker
        thread) ensures the spinner animates smoothly even when the
        worker's native code holds the GIL between releases.
        """
        while not job.wait(_TICKER_INTERVAL):
            self._state.elapsed_seconds = time.monotonic() - start_time
            self._presenter.refresh()
        self._state.elapsed_seconds = time.monotonic() - start_time
        self._presenter.refresh()

    def _record(self, recording_config: RecordingConfig) -> np.ndarray:
        def on_level(level: float) -> None:
            self._state.level = level

        def on_pause(paused: bool) -> None:
            self._state.phase = Phase.PAUSED if paused else Phase.RECORDING

        recorder = ModernRecorder(on_level=on_level, on_pause=on_pause)
        self._state.phase = Phase.RECORDING
        self._state.elapsed_seconds = 0.0
        self._presenter.refresh()
        with ElapsedTicker(self._state, self._presenter):
            return recorder.record(recording_config)

    def _cleanup(self, config: TranscriptionConfig, recording_path: Path, output_path: Path) -> None:
        if not (config.cleanup_audio or config.cleanup_transcription):
            return
        self._state.phase = Phase.CLEANUP
        self._presenter.refresh()
        if config.cleanup_audio:
            recording_path.unlink(missing_ok=True)
        if config.cleanup_transcription:
            output_path.unlink(missing_ok=True)
