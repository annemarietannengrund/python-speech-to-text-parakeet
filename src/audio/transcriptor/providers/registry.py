from collections.abc import Callable

from audio.core.config import SpeechToTextSettings
from audio.transcriptor.interfaces.transcription_protocols import TranscriptionService
from audio.transcriptor.models.provider import TranscriptionProvider

ServiceFactory = Callable[[SpeechToTextSettings], TranscriptionService]


def _build_parakeet(settings: SpeechToTextSettings) -> TranscriptionService:
    # Imported here intentionally: importing parakeet_service eagerly loads the
    # `nemo` stack (multi-second side effects + log spam). Constructing the
    # service must remain deferrable so `speech-to-text --record` can start
    # recording before the transcription backend is initialized.
    from audio.transcriptor.services.parakeet_service import ParakeetTranscriptionService
    return ParakeetTranscriptionService(
        model=settings.model,
        device=settings.device,
        chunk_threshold_seconds=settings.chunk_threshold_seconds,
        chunk_max_seconds=settings.chunk_max_seconds,
        chunk_silence_ms=settings.chunk_silence_ms,
        chunk_silence_thresh_db=settings.chunk_silence_thresh_db,
        chunk_keep_silence_ms=settings.chunk_keep_silence_ms,
    )


_FACTORIES: dict[TranscriptionProvider, ServiceFactory] = {
    TranscriptionProvider.PARAKEET: _build_parakeet,
}


def build_transcription_service(settings: SpeechToTextSettings) -> TranscriptionService:
    factory = _FACTORIES.get(settings.provider)
    if factory is None:
        raise ValueError(f"Unknown transcription provider: {settings.provider}")
    return factory(settings)


def available_providers() -> tuple[TranscriptionProvider, ...]:
    """Return the providers currently registered in the registry."""
    return tuple(_FACTORIES.keys())
