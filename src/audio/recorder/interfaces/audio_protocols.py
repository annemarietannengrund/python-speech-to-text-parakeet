from typing import Protocol, runtime_checkable
import numpy as np
from audio.recorder.models.audio_config import RecordingConfig


@runtime_checkable
class AudioRecorder(Protocol):
    def record(self, config: RecordingConfig) -> np.ndarray:
        ...


@runtime_checkable
class AudioExporter(Protocol):
    def export(self, data: np.ndarray, config: RecordingConfig) -> None:
        ...
