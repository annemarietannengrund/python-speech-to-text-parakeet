"""Dataclasses describing the UI state rendered by the modern CLI."""
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Phase(StrEnum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    LOADING_MODEL = "loading_model"
    MODEL_READY = "model_ready"
    TRANSCRIBING = "transcribing"
    CLEANUP = "cleanup"
    DONE = "done"
    ERROR = "error"


@dataclass
class UIState:
    """Mutable state consumed by the presenter on each render tick."""
    phase: Phase = Phase.IDLE
    elapsed_seconds: float = 0.0
    level: float = 0.0  # RMS amplitude, 0.0 - 1.0
    message: str | None = None  # phase-specific detail (e.g. error text)
    recording_path: Path | None = None
    transcription_path: Path | None = None
    transcribe_seconds: float = 0.0
    record_seconds: float = 0.0
    transcript: str = ""


@dataclass
class FinalSummary:
    """Compact summary printed after the run completes."""
    record_seconds: float = 0.0
    transcribe_seconds: float = 0.0
    recording_path: Path | None = None
    transcription_path: Path | None = None
    extras: list[str] = field(default_factory=list)
