from audio.transcriptor_modern.cli import _cleanup_flags
from tests.unit.test_helper import BaseTestCase


class TestCleanupFlags(BaseTestCase):
    def test_none_yields_both_false(self) -> None:
        self.assertEqual(_cleanup_flags(None), (False, False))

    def test_empty_yields_both_false(self) -> None:
        self.assertEqual(_cleanup_flags(""), (False, False))

    def test_audio_only(self) -> None:
        self.assertEqual(_cleanup_flags("audio"), (True, False))

    def test_transcription_only(self) -> None:
        self.assertEqual(_cleanup_flags("transcription"), (False, True))

    def test_all_sets_both(self) -> None:
        self.assertEqual(_cleanup_flags("all"), (True, True))

    def test_combined_with_whitespace_and_case(self) -> None:
        self.assertEqual(_cleanup_flags(" Audio , Transcription "), (True, True))

    def test_unknown_token_is_ignored(self) -> None:
        self.assertEqual(_cleanup_flags("audio,bogus"), (True, False))
