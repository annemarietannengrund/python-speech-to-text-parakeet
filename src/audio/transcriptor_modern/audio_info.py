"""Probe an audio file for display metadata via `ffprobe`.

Graceful degradation: when `ffprobe` is unavailable or the file is
unreadable, returns an :class:`AudioInfo` with only filesystem-level
data (path, size, format).
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from audio.transcriptor_modern.models.audio_info import AudioInfo

logger = logging.getLogger(__name__)

_FFPROBE: str = "ffprobe"
_TIMEOUT_SECONDS: float = 5.0


def probe_audio(path: Path) -> AudioInfo:
    """Return :class:`AudioInfo` for `path`, probing with ffprobe when present."""
    size_bytes = path.stat().st_size if path.exists() else 0
    audio_format = path.suffix.lstrip(".").lower()
    base = AudioInfo(path=path, size_bytes=size_bytes, format=audio_format)

    if shutil.which(_FFPROBE) is None:
        return base

    command = [
        _FFPROBE,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        "-select_streams", "a:0",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("ffprobe failed for %s: %s", path, exc)
        return base

    payload = json.loads(completed.stdout or "{}")
    streams = payload.get("streams") or []
    stream = streams[0] if streams else {}
    container = payload.get("format") or {}

    duration_raw = stream.get("duration") or container.get("duration")
    sample_rate_raw = stream.get("sample_rate")
    channels = stream.get("channels")
    codec = stream.get("codec_name")

    return AudioInfo(
        path=path,
        size_bytes=size_bytes,
        format=audio_format,
        duration_seconds=float(duration_raw) if duration_raw is not None else None,
        sample_rate_hz=int(sample_rate_raw) if sample_rate_raw is not None else None,
        channels=int(channels) if channels is not None else None,
        codec=codec,
    )
