from typing import Protocol
from pathlib import Path
from audio.core import AudioFormat


class TranscriptionService(Protocol):
    @property
    def supported_input_formats(self) -> frozenset[AudioFormat]:
        """Audio formats this service can transcribe natively without pre-conversion."""
        ...

    def transcribe(self, audio_path: Path, model: str | None = None) -> str:
        """
        Transcribe the given audio file.
        """
        ...
