import unittest
from unittest.mock import Mock

from audio.core import SpeechToTextSettings
from audio.transcriptor.cli import SpeechToTextCLI


class TestSpeechToTextCLI(unittest.TestCase):
    def setUp(self):
        self.mock_processor = Mock()
        self.mock_logger = Mock()
        self.settings = SpeechToTextSettings()
        self.cli = SpeechToTextCLI(self.mock_processor, self.mock_logger, self.settings)

    def test_cleanup_all_expands_to_both(self):
        import argparse
        from unittest.mock import patch

        # We need to mock parse_args to return our desired values
        with patch('argparse.ArgumentParser.parse_args') as mock_parse:
            mock_parse.return_value = argparse.Namespace(
                path="test.wav",
                recursive=False,
                record=False,
                cleanup="all",
                format="txt",
                output_dir=None,
                model=None,
                provider="parakeet",
                no_skip=False,
                list_providers=False,
                verbose=False
            )

            self.cli.run()

            # Verify that processor.process was called with a config that has both cleanup flags set
            self.mock_processor.process.assert_called_once()
            config = self.mock_processor.process.call_args[0][0]
            self.assertTrue(config.cleanup_audio)
            self.assertTrue(config.cleanup_transcription)
            self.assertFalse(config.persist_recording)

    def test_cleanup_audio_only(self):
        import argparse
        from unittest.mock import patch

        with patch('argparse.ArgumentParser.parse_args') as mock_parse:
            mock_parse.return_value = argparse.Namespace(
                path="test.wav",
                recursive=False,
                record=False,
                cleanup="audio",
                format="txt",
                output_dir=None,
                model=None,
                provider="parakeet",
                no_skip=False,
                list_providers=False,
                verbose=False
            )

            self.cli.run()

            config = self.mock_processor.process.call_args[0][0]
            self.assertTrue(config.cleanup_audio)
            self.assertFalse(config.cleanup_transcription)


if __name__ == "__main__":
    unittest.main()
