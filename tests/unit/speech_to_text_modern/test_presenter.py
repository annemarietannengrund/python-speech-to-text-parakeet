from rich.console import Console

from audio.transcriptor_modern.models.ui_state import FinalSummary, Phase, UIState
from audio.transcriptor_modern.ui.presenter import DefaultRenderer, LivePresenter
from tests.unit.test_helper import BaseTestCase


class TestDefaultRenderer(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.renderer = DefaultRenderer()
        self.console = Console(record=True, force_terminal=False, width=120)

    def _capture(self, state: UIState) -> str:
        self.console.print(self.renderer.render(state))
        return self.console.export_text()

    def test_recording_shows_level_bar_and_hint(self) -> None:
        state = UIState(phase=Phase.RECORDING, elapsed_seconds=12.0, level=0.5)
        output = self._capture(state)
        self.assertIn("Recording", output)
        self.assertIn("00:12", output)
        self.assertIn("SPACE pause", output)
        self.assertIn("█", output)

    def test_transcribing_omits_recording_hint(self) -> None:
        state = UIState(phase=Phase.TRANSCRIBING, elapsed_seconds=3.0)
        output = self._capture(state)
        self.assertIn("Transcribing", output)
        self.assertNotIn("SPACE pause", output)

    def test_message_is_rendered(self) -> None:
        state = UIState(phase=Phase.ERROR, message="boom")
        output = self._capture(state)
        self.assertIn("Error", output)
        self.assertIn("boom", output)


class TestLivePresenterSummary(BaseTestCase):
    def test_summary_prints_compact_line_and_transcript(self) -> None:
        console = Console(record=True, force_terminal=False, width=120)
        presenter = LivePresenter(UIState(), console=console)
        summary = FinalSummary(record_seconds=42.0, transcribe_seconds=3.14)
        presenter.print_summary(summary, "hello world")
        output = console.export_text()
        self.assertIn("done", output)
        self.assertIn("00:42", output)
        self.assertIn("3.1s", output)
        self.assertIn("── Transcription ──", output)
        self.assertIn("hello world", output)

    def test_summary_without_transcript_skips_header(self) -> None:
        console = Console(record=True, force_terminal=False, width=120)
        presenter = LivePresenter(UIState(), console=console)
        presenter.print_summary(FinalSummary(), "")
        output = console.export_text()
        self.assertNotIn("Transcription", output)
