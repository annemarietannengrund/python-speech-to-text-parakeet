import logging
from pathlib import Path

import torch

from audio.core import AudioFormat
from audio.transcriptor.chunked_transcribe import chunked_transcribe, DEFAULT_THRESHOLD_SECONDS, DEFAULT_MAX_CHUNK_SECONDS, DEFAULT_SILENCE_MS, DEFAULT_SILENCE_THRESH_DB, DEFAULT_KEEP_SILENCE_MS
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
    def __init__(
        self,
        model: str,
        device: str | None = None,
        chunk_threshold_seconds: int = DEFAULT_THRESHOLD_SECONDS,
        chunk_max_seconds: int = DEFAULT_MAX_CHUNK_SECONDS,
        chunk_silence_ms: int = DEFAULT_SILENCE_MS,
        chunk_silence_thresh_db: int = DEFAULT_SILENCE_THRESH_DB,
        chunk_keep_silence_ms: int = DEFAULT_KEEP_SILENCE_MS,
    ) -> None:
        self.logger = logging.getLogger(f"{self.__module__}.{self.__class__.__name__}")
        self._model_id = model
        self._device = resolve_device(device)
        self._model = None
        self._chunk_threshold_seconds = chunk_threshold_seconds
        self._chunk_max_seconds = chunk_max_seconds
        self._chunk_silence_ms = chunk_silence_ms
        self._chunk_silence_thresh_db = chunk_silence_thresh_db
        self._chunk_keep_silence_ms = chunk_keep_silence_ms

    @property
    def supported_input_formats(self) -> frozenset[AudioFormat]:
        return _PARAKEET_NATIVE_FORMATS

    def transcribe(self, audio_path: Path, model: str | None = None) -> str:
        self.logger.info("Transcribing %s", audio_path)
        active_model = self._load(model or self._model_id)

        def _infer(path: Path) -> str:
            with suppress_stdio(is_quiet()):
                hypotheses = active_model.transcribe([str(path)])
            return hypotheses[0].text.strip()

        return chunked_transcribe(
            audio_path,
            _infer,
            threshold_seconds=self._chunk_threshold_seconds,
            max_chunk_seconds=self._chunk_max_seconds,
            silence_ms=self._chunk_silence_ms,
            silence_thresh_db=self._chunk_silence_thresh_db,
            keep_silence_ms=self._chunk_keep_silence_ms,
        )

    def _load(self, model_id: str):
        if self._model is None or model_id != self._model_id:
            self.logger.info("Loading Parakeet model %s on %s", model_id, self._device)
            with suppress_stdio(is_quiet()):
                loaded = nemo_asr.models.ASRModel.from_pretrained(model_id)
                self._model = loaded.to(self._device)
            self._model_id = model_id
        return self._model
