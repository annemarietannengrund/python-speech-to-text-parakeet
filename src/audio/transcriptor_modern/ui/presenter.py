"""Rich-based live presenter for the modern speech-to-text CLI.

Renders a single persistent status line that updates while the run
progresses. The live region is transient — once the presenter exits,
Rich erases the last frame so only the final summary + transcript
remain in the scrollback.
"""
from __future__ import annotations

import threading
from pathlib import Path
from types import TracebackType
from typing import Protocol

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from audio.transcriptor_modern.models.audio_info import AudioInfo
from audio.transcriptor_modern.models.ui_state import FinalSummary, Phase, UIState


_PHASE_LABEL: dict[Phase, str] = {
    Phase.IDLE: "Idle",
    Phase.RECORDING: "🎤 Recording",
    Phase.PAUSED: "⏸  Paused",
    Phase.LOADING_MODEL: "Loading model",
    Phase.MODEL_READY: "Model transcribing",
    Phase.TRANSCRIBING: "Transcribing",
    Phase.CLEANUP: "Cleaning up",
    Phase.DONE: "Done",
    Phase.ERROR: "Error",
}

_PHASE_STYLE: dict[Phase, str] = {
    Phase.IDLE: "dim",
    Phase.RECORDING: "bold red",
    Phase.PAUSED: "bold yellow",
    Phase.LOADING_MODEL: "cyan",
    Phase.MODEL_READY: "cyan",
    Phase.TRANSCRIBING: "cyan",
    Phase.CLEANUP: "dim",
    Phase.DONE: "bold green",
    Phase.ERROR: "bold red",
}

# Phases that explicitly suppress the leading spinner (steady icon instead).
_STATIC_PHASES: frozenset[Phase] = frozenset({Phase.PAUSED})

_PHASE_BADGE: dict[Phase, str] = {
    Phase.RECORDING: "✓",  # green check while actively capturing
    Phase.PAUSED: "✗",     # red cross while paused
}

_BADGE_STYLE: dict[Phase, str] = {
    Phase.RECORDING: "bold green",
    Phase.PAUSED: "bold red",
}

_LEVEL_BAR_WIDTH: int = 20
_HINT_RECORDING: str = "CTRL+SPACE pause · CTRL+ENTER stop"


class Renderer(Protocol):
    """Builds a Rich renderable from the current UI state."""

    def render(self, state: UIState) -> RenderableType: ...


class DefaultRenderer:
    """Default renderer: phase icon + label + elapsed + level bar + hint."""

    def render(self, state: UIState) -> RenderableType:
        label = _PHASE_LABEL[state.phase]
        style = _PHASE_STYLE[state.phase]
        elapsed = _format_duration(state.elapsed_seconds)

        text = Text()
        badge = _PHASE_BADGE.get(state.phase)
        if badge:
            text.append(f"{badge} ", style=_BADGE_STYLE[state.phase])
        text.append(label, style=style)
        if state.phase not in (Phase.ERROR,):
            text.append(f"  {elapsed}", style="dim")

        if state.phase in (Phase.RECORDING, Phase.PAUSED):
            text.append("  ")
            text.append(_render_level_bar(state.level), style="green")
            text.append(f"  {_HINT_RECORDING}", style="dim")

        if state.message:
            text.append(f"  · {state.message}", style="dim")

        if state.phase in _STATIC_PHASES:
            return Group(text)

        spinner_name = "dots12" if state.phase == Phase.RECORDING else "dots"
        return Group(Spinner(spinner_name, text=text, style=style))


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


_SIZE_UNITS: tuple[str, ...] = ("B", "KB", "MB", "GB", "TB")


def _format_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in _SIZE_UNITS:
        if value < 1024.0 or unit == _SIZE_UNITS[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024.0
    return f"{size_bytes} B"


def _render_level_bar(level: float) -> str:
    clamped = max(0.0, min(1.0, level))
    filled = int(clamped * _LEVEL_BAR_WIDTH)
    return "▕" + "█" * filled + "·" * (_LEVEL_BAR_WIDTH - filled) + "▏"


class LivePresenter:
    """Owns a Rich `Live` and re-renders on every `refresh()`.

    The live region is transient: when the context manager exits, the
    last frame is erased, so the caller can print a clean summary
    afterwards without leftover spinner artifacts.

    A render lock serialises updates so background ticker threads
    cannot overwrite a freshly transitioned phase between the caller's
    state mutation and `refresh()` call.
    """

    def __init__(
        self,
        state: UIState,
        console: Console | None = None,
        renderer: Renderer | None = None,
        refresh_per_second: int = 12,
    ) -> None:
        self.state = state
        self.console = console or Console()
        self.renderer = renderer or DefaultRenderer()
        self._lock = threading.Lock()
        self._stopped = False
        # `redirect_stdout/stderr=False` prevents Rich from pushing the
        # current live frame into the scrollback whenever an unrelated
        # write hits stdout/stderr during the run (e.g. a sounddevice
        # warning from the recorder thread). Without this guard a noisy
        # mic input could leave the "Recording …" line as an artifact
        # above the final summary.
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=refresh_per_second,
            transient=True,
            redirect_stdout=False,
            redirect_stderr=False,
        )

    def __enter__(self) -> "LivePresenter":
        with self._lock:
            self._stopped = False
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=self._live.refresh_per_second,
            transient=True,
            redirect_stdout=False,
            redirect_stderr=False,
        )
        self._live.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        with self._lock:
            self._stopped = True
        self._live.__exit__(exc_type, exc, tb)

    def refresh(self) -> None:
        with self._lock:
            if self._stopped:
                return
            self._live.update(self._render())

    def _render(self) -> RenderableType:
        return self.renderer.render(self.state)

    def print_file_info(self, info: AudioInfo) -> None:
        """Print a compact metadata block for an input audio file."""
        header = Text("── Input ──", style="bold cyan")
        self.console.print(header)
        self.console.print(Text(f"path     {info.path}", style="dim"))
        self.console.print(Text(f"size     {_format_size(info.size_bytes)}", style="dim"))
        self.console.print(Text(f"format   {info.format or 'unknown'}", style="dim"))
        if info.codec:
            self.console.print(Text(f"codec    {info.codec}", style="dim"))
        if info.duration_seconds is not None:
            self.console.print(Text(f"length   {_format_duration(info.duration_seconds)}", style="dim"))
        if info.sample_rate_hz is not None:
            self.console.print(Text(f"rate     {info.sample_rate_hz / 1000:.1f} kHz", style="dim"))
        if info.channels is not None:
            self.console.print(Text(f"channels {info.channels}", style="dim"))

    def print_summary(self, summary: FinalSummary, transcript: str) -> None:
        """Print the final compact summary line + transcript block."""
        line = Text()
        line.append("✓ ", style="bold green")
        line.append("done", style="bold green")
        line.append(
            f"  · recorded {_format_duration(summary.record_seconds)}"
            f"  · transcribed in {summary.transcribe_seconds:.1f}s",
            style="dim",
        )
        for extra in summary.extras:
            line.append(f"  · {extra}", style="dim")
        self.console.print(line)

        artifacts: list[tuple[str, Path]] = []
        if summary.recording_path is not None:
            artifacts.append(("audio", summary.recording_path))
        if summary.transcription_path is not None:
            artifacts.append((summary.transcription_path.suffix.lstrip(".") or "file", summary.transcription_path))
        if artifacts:
            header = Text("── Artifacts ──", style="bold cyan")
            self.console.print(header)
            for label, path in artifacts:
                self.console.print(Text(f"{label:<8} {path}", style="dim"))

        if transcript:
            header = Text("── Transcription ──", style="bold cyan")
            self.console.print(header)
            # Render as plain Text so Rich's repr highlighter does not
            # colourise numbers/paths inside the transcription.
            self.console.print(Text(transcript))


class NullPresenter:
    """No-op presenter for pipe mode — suppresses all UI output.

    Implements the same surface as :class:`LivePresenter` so the
    processor can drive it without conditionals. Used when the user
    passes ``--pipe`` so stdout stays reserved for the transcript only.
    """

    def __enter__(self) -> "NullPresenter":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def refresh(self) -> None:
        return None

    def print_file_info(self, info: AudioInfo) -> None:
        return None

    def print_summary(self, summary: FinalSummary, transcript: str) -> None:
        return None
