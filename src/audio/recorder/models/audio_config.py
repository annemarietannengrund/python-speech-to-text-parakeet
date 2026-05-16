from dataclasses import dataclass
from audio.core import AudioFormat

@dataclass(frozen=True)
class RecordingConfig:
    filename: str
    format: AudioFormat
    samplerate: int = 44100
    channels: int = 1
