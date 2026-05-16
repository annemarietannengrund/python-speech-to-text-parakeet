from dataclasses import dataclass
from pathlib import Path

from audio.core import AudioFormat


@dataclass(frozen=True)
class TranscriptionConfig:
    path: Path | None = None
    recursive: bool = False
    record: bool = False
    persist_recording: bool = True
    output_format: str = "txt"
    no_skip: bool = False
    cleanup_audio: bool = False
    cleanup_transcription: bool = False
    output_dir: Path | None = None
    model: str | None = None
    preconversion_format: AudioFormat = AudioFormat.FLAC
    recording_format: AudioFormat = AudioFormat.FLAC
    # Chunking settings (silence-aware splitting for long audio)
    chunk_threshold_seconds: int = 60
    chunk_max_seconds: int = 180
    chunk_silence_ms: int = 300
    chunk_silence_thresh_db: int = -40
    chunk_keep_silence_ms: int = 200
