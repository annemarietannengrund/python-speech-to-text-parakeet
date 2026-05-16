import unittest
from unittest.mock import patch

from audio.core.config import SpeechToTextSettings
from audio.transcriptor.models.provider import TranscriptionProvider
from audio.transcriptor.providers.registry import build_transcription_service


class TestRegistry(unittest.TestCase):
    def test_every_enum_value_resolves(self):
        for provider in TranscriptionProvider:
            settings = SpeechToTextSettings(provider=provider, model="nvidia/parakeet-tdt-0.6b-v3")
            with patch("audio.transcriptor.services.parakeet_service.ParakeetTranscriptionService") as mock_parakeet:
                mock_parakeet.return_value = "parakeet-instance"
                service = build_transcription_service(settings)
                mock_parakeet.assert_called_once_with(
                    model="nvidia/parakeet-tdt-0.6b-v3",
                    device=None,
                    chunk_threshold_seconds=settings.chunk_threshold_seconds,
                    chunk_max_seconds=settings.chunk_max_seconds,
                    chunk_silence_ms=settings.chunk_silence_ms,
                    chunk_silence_thresh_db=settings.chunk_silence_thresh_db,
                    chunk_keep_silence_ms=settings.chunk_keep_silence_ms,
                )
                self.assertEqual(service, "parakeet-instance")

    def test_parakeet_factory_returns_parakeet_service(self):
        settings = SpeechToTextSettings(provider=TranscriptionProvider.PARAKEET, model="nvidia/parakeet-tdt-0.6b-v3")
        with patch("audio.transcriptor.services.parakeet_service.ParakeetTranscriptionService") as mock_parakeet:
            build_transcription_service(settings)
            mock_parakeet.assert_called_once_with(
                model="nvidia/parakeet-tdt-0.6b-v3",
                device=None,
                chunk_threshold_seconds=settings.chunk_threshold_seconds,
                chunk_max_seconds=settings.chunk_max_seconds,
                chunk_silence_ms=settings.chunk_silence_ms,
                chunk_silence_thresh_db=settings.chunk_silence_thresh_db,
                chunk_keep_silence_ms=settings.chunk_keep_silence_ms,
            )

    def test_unknown_provider_raises(self):
        settings = SpeechToTextSettings.__new__(SpeechToTextSettings)
        object.__setattr__(settings, "provider", "bogus")
        object.__setattr__(settings, "model", "tiny")
        object.__setattr__(settings, "device", None)
        with self.assertRaises(ValueError):
            build_transcription_service(settings)

    def test_load_settings_rejects_unknown_provider(self):
        from audio.core.config import load_settings
        with patch.dict("os.environ", {"STT_PROVIDER": "bogus"}, clear=False):
            with self.assertRaises(ValueError):
                load_settings()


if __name__ == "__main__":
    unittest.main()
