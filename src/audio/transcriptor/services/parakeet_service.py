import logging
from pathlib import Path

import torch

from audio.core import AudioFormat
from audio.transcriptor.interfaces.transcription_protocols import TranscriptionService
from audio.transcriptor.verbosity import is_quiet, suppress_stdio

# NeMo prints OneLogger banner lines (and similar telemetry chatter) at import
# time via raw stdout/stderr writes that bypass Python logging. Suppress those
# file descriptors during the import so the user only sees them with --verbose.
with suppress_stdio(is_quiet()):
    import nemo.collections.asr as nemo_asr

_PARAKEET_NATIVE_FORMATS: frozenset[AudioFormat] = frozenset(
    {AudioFormat.WAV, AudioFormat.FLAC, AudioFormat.OGG, AudioFormat.MP3}
)


def resolve_device(override: str | None) -> str:
    """Return the explicit override, else `mps` if available, else `cpu`."""
    if override:
        return override
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class ParakeetTranscriptionService(TranscriptionService):
    def __init__(self, model: str, device: str | None = None) -> None:
        self.logger = logging.getLogger(f"{self.__module__}.{self.__class__.__name__}")
        self._model_id = model
        self._device = resolve_device(device)
        self._model = None

    @property
    def supported_input_formats(self) -> frozenset[AudioFormat]:
        return _PARAKEET_NATIVE_FORMATS

    def transcribe(self, audio_path: Path, model: str | None = None) -> str:
        self.logger.info("Transcribing %s", audio_path)
        active_model = self._load(model or self._model_id)
        with suppress_stdio(is_quiet()):
            hypotheses = active_model.transcribe([str(audio_path)])
        return hypotheses[0].text.strip()

    def _load(self, model_id: str):
        if self._model is None or model_id != self._model_id:
            self.logger.info("Loading Parakeet model %s on %s", model_id, self._device)
            with suppress_stdio(is_quiet()):
                loaded = nemo_asr.models.ASRModel.from_pretrained(model_id)
                self._model = loaded.to(self._device)
            self._model_id = model_id
        return self._model
