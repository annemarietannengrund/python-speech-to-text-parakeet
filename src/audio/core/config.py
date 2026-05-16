from dataclasses import dataclass, field
from os import environ
from dotenv import load_dotenv
from audio.core.models import AudioFormat
from audio.transcriptor.models.provider import TranscriptionProvider


@dataclass(frozen=True)
class RecordAudioSettings:
    default_format: AudioFormat = AudioFormat.FLAC
    default_samplerate: int = 44100
    default_channels: int = 1
    date_format: str = "%Y-%m-%d-%H-%M"


@dataclass(frozen=True)
class AudioConverterSettings:
    ask_on_overwrite: bool = False


@dataclass(frozen=True)
class SpeechToTextSettings:
    provider: TranscriptionProvider = TranscriptionProvider.PARAKEET
    model: str = "nvidia/parakeet-tdt-0.6b-v3"
    device: str | None = None
    preconversion_format: AudioFormat = AudioFormat.FLAC
    # Chunking — activate when audio exceeds threshold_seconds (0 = always chunk)
    chunk_threshold_seconds: int = 60
    chunk_max_seconds: int = 180
    chunk_silence_ms: int = 300
    chunk_silence_thresh_db: int = -40
    chunk_keep_silence_ms: int = 200


@dataclass(frozen=True)
class Settings:
    record: RecordAudioSettings = field(default_factory=RecordAudioSettings)
    converter: AudioConverterSettings = field(default_factory=AudioConverterSettings)
    stt: SpeechToTextSettings = field(default_factory=SpeechToTextSettings)


def load_settings() -> Settings:
    load_dotenv()

    return Settings(
        record=RecordAudioSettings(
            default_format=AudioFormat(environ.get("RECORD_AUDIO_DEFAULT_FORMAT", AudioFormat.FLAC.value)),
            default_samplerate=int(environ.get("RECORD_AUDIO_DEFAULT_SAMPLERATE", "44100")),
            default_channels=int(environ.get("RECORD_AUDIO_DEFAULT_CHANNELS", "1")),
            date_format=environ.get("RECORD_AUDIO_DATE_FORMAT", "%Y-%m-%d-%H-%M"),
        ),
        converter=AudioConverterSettings(
            ask_on_overwrite=environ.get("AUDIO_CONVERTER_ASK_ON_OVERWRITE", "false").lower() == "true",
        ),
        stt=SpeechToTextSettings(
            provider=TranscriptionProvider(environ.get("STT_PROVIDER", TranscriptionProvider.PARAKEET.value)),
            model=environ.get("STT_MODEL", "nvidia/parakeet-tdt-0.6b-v3"),
            device=environ.get("STT_DEVICE"),
            preconversion_format=AudioFormat(environ.get("STT_PRECONVERSION_FORMAT", AudioFormat.FLAC.value)),
            chunk_threshold_seconds=int(environ.get("STT_CHUNK_THRESHOLD_SECONDS", "60")),
            chunk_max_seconds=int(environ.get("STT_CHUNK_MAX_SECONDS", "180")),
            chunk_silence_ms=int(environ.get("STT_CHUNK_SILENCE_MS", "300")),
            chunk_silence_thresh_db=int(environ.get("STT_CHUNK_SILENCE_THRESH_DB", "-40")),
            chunk_keep_silence_ms=int(environ.get("STT_CHUNK_KEEP_SILENCE_MS", "200")),
        )
    )
