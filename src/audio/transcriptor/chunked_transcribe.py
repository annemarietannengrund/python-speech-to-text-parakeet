"""Silence-aware chunked transcription for long audio files.

When an audio file exceeds ``threshold_seconds``, it is split into
chunks at silence boundaries (never mid-word) and each chunk is
transcribed independently.  The results are joined with a single space.

Splitting uses pydub's ``split_on_silence`` which calls FFmpeg under
the hood — no extra system dependencies beyond what the project already
requires.

Configuration (all optional, with sensible defaults):

    threshold_seconds   – minimum audio duration that triggers chunking
                          (default 180 s / 3 min).  Set to 0 to always chunk.
    max_chunk_seconds   – hard upper bound per chunk (default 300 s / 5 min).
    silence_ms          – minimum silence length to split on (default 500 ms).
    silence_thresh_db   – dBFS level considered silence (default -40 dBFS).
    keep_silence_ms     – silence padding kept at each chunk edge so the
                          first/last word is never clipped (default 200 ms).
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# Defaults — can be overridden via SpeechToTextSettings / env vars.
DEFAULT_THRESHOLD_SECONDS: int = 60    # activate chunking above this (1 min)
DEFAULT_MAX_CHUNK_SECONDS: int = 180   # hard cap per chunk (3 min — safe for Parakeet)
DEFAULT_SILENCE_MS: int = 300          # min silence length to split on
DEFAULT_SILENCE_THRESH_DB: int = -40   # dBFS threshold for "silence"
DEFAULT_KEEP_SILENCE_MS: int = 200     # padding kept at chunk edges


TranscribeFn = Callable[[Path], str]


def needs_chunking(audio_path: Path, threshold_seconds: int) -> bool:
    """Return True when the file is long enough to warrant chunking."""
    if threshold_seconds <= 0:
        return True
    try:
        from pydub import AudioSegment  # type: ignore[import-untyped]
        audio = AudioSegment.from_file(str(audio_path))
        duration_s = len(audio) / 1000.0
        return duration_s > threshold_seconds
    except Exception:
        logger.debug("Could not probe duration of %s — skipping chunking", audio_path)
        return False


def chunked_transcribe(
    audio_path: Path,
    transcribe_fn: TranscribeFn,
    *,
    threshold_seconds: int = DEFAULT_THRESHOLD_SECONDS,
    max_chunk_seconds: int = DEFAULT_MAX_CHUNK_SECONDS,
    silence_ms: int = DEFAULT_SILENCE_MS,
    silence_thresh_db: int = DEFAULT_SILENCE_THRESH_DB,
    keep_silence_ms: int = DEFAULT_KEEP_SILENCE_MS,
) -> str:
    """Transcribe *audio_path*, splitting on silence for long files.

    Falls back to a direct ``transcribe_fn(audio_path)`` call when the
    file is shorter than *threshold_seconds*.
    """
    if not needs_chunking(audio_path, threshold_seconds):
        logger.debug("File shorter than threshold — transcribing whole file")
        return transcribe_fn(audio_path)

    logger.info(
        "File exceeds %ds threshold — splitting on silence (max chunk %ds)",
        threshold_seconds,
        max_chunk_seconds,
    )
    chunks = _split_audio(
        audio_path,
        max_chunk_seconds=max_chunk_seconds,
        silence_ms=silence_ms,
        silence_thresh_db=silence_thresh_db,
        keep_silence_ms=keep_silence_ms,
    )
    logger.info("Split into %d chunk(s)", len(chunks))

    suffix = audio_path.suffix  # preserve original format for each chunk
    parts: list[str] = []
    with tempfile.TemporaryDirectory(prefix="stt_chunks_") as tmp_dir:
        tmp = Path(tmp_dir)
        for i, chunk in enumerate(chunks):
            chunk_path = tmp / f"chunk_{i:04d}{suffix}"
            chunk.export(str(chunk_path), format=audio_path.suffix.lstrip("."))
            logger.debug("Transcribing chunk %d/%d (%ds)", i + 1, len(chunks), len(chunk) // 1000)
            text = transcribe_fn(chunk_path)
            if text:
                parts.append(text)

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _split_audio(
    audio_path: Path,
    *,
    max_chunk_seconds: int,
    silence_ms: int,
    silence_thresh_db: int,
    keep_silence_ms: int,
):
    """Return a list of pydub AudioSegment chunks.

    Strategy:
    1. Split on silence boundaries.
    2. If any resulting chunk still exceeds *max_chunk_seconds*, subdivide
       it further at the midpoint (hard split — last resort, avoids OOM).
    """
    from pydub import AudioSegment  # type: ignore[import-untyped]
    from pydub.silence import split_on_silence  # type: ignore[import-untyped]

    audio = AudioSegment.from_file(str(audio_path))
    raw_chunks = split_on_silence(
        audio,
        min_silence_len=silence_ms,
        silence_thresh=silence_thresh_db,
        keep_silence=keep_silence_ms,
    )

    if not raw_chunks:
        # No silence found — return the whole file as one chunk.
        logger.warning("No silence detected in %s — transcribing as single chunk", audio_path.name)
        return [audio]

    # Merge very short adjacent chunks and enforce the hard cap.
    return _enforce_max_length(raw_chunks, max_chunk_seconds * 1000)


def _enforce_max_length(chunks, max_ms: int):
    """Merge tiny chunks and hard-split oversized ones."""
    from pydub import AudioSegment  # type: ignore[import-untyped]

    result: list[AudioSegment] = []
    current: AudioSegment | None = None

    for chunk in chunks:
        if current is None:
            current = chunk
            continue
        merged = current + chunk
        if len(merged) <= max_ms:
            current = merged
        else:
            # Flush current, start fresh with this chunk.
            result.extend(_hard_split(current, max_ms))
            current = chunk

    if current is not None:
        result.extend(_hard_split(current, max_ms))

    return result


def _hard_split(segment, max_ms: int):
    """Split a segment into pieces of at most *max_ms* milliseconds."""
    if len(segment) <= max_ms:
        return [segment]
    parts = []
    offset = 0
    while offset < len(segment):
        parts.append(segment[offset: offset + max_ms])
        offset += max_ms
    return parts
