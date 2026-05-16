"""Dataclass describing a probed audio file for the modern CLI."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioInfo:
    """Lightweight metadata for an input audio file."""
    path: Path
    size_bytes: int
    format: str
    duration_seconds: float | None = None
    sample_rate_hz: int | None = None
    channels: int | None = None
    codec: str | None = None
