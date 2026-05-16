from unittest.mock import patch

from audio.transcriptor.models.provider import TranscriptionProvider
from audio.core.config import load_settings
from audio.core.models import AudioFormat
from tests.unit.test_helper import BaseTestCase


class LoadSettingsTest(BaseTestCase):
    def _load(self, env: dict[str, str]):
        with patch("audio.core.config.load_dotenv"), patch.dict("audio.core.config.environ", env, clear=True):
            return load_settings()

    def test_stt_defaults(self) -> None:
        settings = self._load({}).stt
        self.assertEqual(TranscriptionProvider.PARAKEET, settings.provider)
        self.assertEqual("nvidia/parakeet-tdt-0.6b-v3", settings.model)
        self.assertIsNone(settings.device)
        self.assertEqual(AudioFormat.FLAC, settings.preconversion_format)

    def test_stt_preconversion_format_override(self) -> None:
        settings = self._load({"STT_PRECONVERSION_FORMAT": "wav"}).stt
        self.assertEqual(AudioFormat.WAV, settings.preconversion_format)

    def test_stt_invalid_preconversion_format_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._load({"STT_PRECONVERSION_FORMAT": "bogus"})

    def test_record_defaults_use_flac(self) -> None:
        settings = self._load({}).record
        self.assertEqual(AudioFormat.FLAC, settings.default_format)

    def test_stt_full_env(self) -> None:
        settings = self._load({
            "STT_PROVIDER": "parakeet",
            "STT_MODEL": "nvidia/parakeet-tdt-0.6b-v3",
            "STT_DEVICE": "cpu",
            "STT_PRECONVERSION_FORMAT": "flac",
        }).stt
        self.assertEqual(TranscriptionProvider.PARAKEET, settings.provider)
        self.assertEqual("nvidia/parakeet-tdt-0.6b-v3", settings.model)
        self.assertEqual("cpu", settings.device)
        self.assertEqual(AudioFormat.FLAC, settings.preconversion_format)
