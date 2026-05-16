import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from audio.core import AudioFormat
from audio.transcriptor.services.parakeet_service import (
    _PARAKEET_NATIVE_FORMATS,
    ParakeetTranscriptionService,
    resolve_device,
)

_MODEL_ID = "nvidia/parakeet-tdt-0.6b-v3"


class TestParakeetTranscriptionService(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch(
            "audio.transcriptor.services.parakeet_service.nemo_asr.models.ASRModel.from_pretrained"
        )
        self.from_pretrained = patcher.start()
        self.addCleanup(patcher.stop)

        self.loaded_model = MagicMock()
        self.loaded_model.to.return_value = self.loaded_model
        hypothesis = MagicMock()
        hypothesis.text = "  hello world  "
        self.loaded_model.transcribe.return_value = [hypothesis]
        self.from_pretrained.return_value = self.loaded_model

    def test_supported_input_formats_matches_native_constant(self):
        service = ParakeetTranscriptionService(model=_MODEL_ID, device="cpu")
        self.assertEqual(service.supported_input_formats, _PARAKEET_NATIVE_FORMATS)
        self.assertIn(AudioFormat.MP3, service.supported_input_formats)

    def test_transcribe_loads_with_configured_model_id(self):
        service = ParakeetTranscriptionService(model=_MODEL_ID, device="cpu")
        service.transcribe(Path("/tmp/sample.wav"))
        self.from_pretrained.assert_called_once_with(_MODEL_ID)

    def test_transcribe_calls_underlying_with_stringified_path(self):
        service = ParakeetTranscriptionService(model=_MODEL_ID, device="cpu")
        audio_path = Path("/tmp/sample.wav")
        service.transcribe(audio_path)
        self.loaded_model.transcribe.assert_called_once_with([str(audio_path)])

    def test_transcribe_strips_returned_text(self):
        service = ParakeetTranscriptionService(model=_MODEL_ID, device="cpu")
        result = service.transcribe(Path("/tmp/sample.wav"))
        self.assertEqual(result, "hello world")

    def test_model_moved_to_resolved_device(self):
        service = ParakeetTranscriptionService(model=_MODEL_ID, device="cpu")
        service.transcribe(Path("/tmp/sample.wav"))
        self.loaded_model.to.assert_called_once_with("cpu")


class TestResolveDevice(unittest.TestCase):
    def test_override_wins(self):
        with patch(
                "audio.transcriptor.services.parakeet_service.torch.backends.mps.is_available",
                return_value=True,
        ):
            self.assertEqual(resolve_device("cuda"), "cuda")

    def test_mps_when_available(self):
        with patch(
                "audio.transcriptor.services.parakeet_service.torch.backends.mps.is_available",
                return_value=True,
        ):
            self.assertEqual(resolve_device(None), "mps")

    def test_cpu_fallback(self):
        with patch(
                "audio.transcriptor.services.parakeet_service.torch.backends.mps.is_available",
                return_value=False,
        ):
            self.assertEqual(resolve_device(None), "cpu")


if __name__ == "__main__":
    unittest.main()
