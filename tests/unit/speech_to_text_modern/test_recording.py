import numpy as np

from audio.transcriptor_modern.recording import _rms_to_unit
from tests.unit.test_helper import BaseTestCase


class TestRmsToUnit(BaseTestCase):
    def test_empty_returns_zero(self) -> None:
        self.assertEqual(_rms_to_unit(np.array([], dtype=np.float32)), 0.0)

    def test_silence_is_near_zero(self) -> None:
        samples = np.zeros(1024, dtype=np.float32)
        self.assertLess(_rms_to_unit(samples), 0.01)

    def test_loud_signal_clamps_to_one(self) -> None:
        samples = np.ones(1024, dtype=np.float32)
        self.assertEqual(_rms_to_unit(samples), 1.0)

    def test_mid_level_between_zero_and_one(self) -> None:
        samples = np.full(1024, 0.1, dtype=np.float32)
        level = _rms_to_unit(samples)
        self.assertGreater(level, 0.0)
        self.assertLess(level, 1.0)
