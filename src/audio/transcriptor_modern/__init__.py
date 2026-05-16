"""Modern speech-to-text CLI variant.

A sibling of :mod:`audio.transcriptor` that keeps the same core logic
(provider registry, transcription service, audio converter) but replaces
the procedural, line-based ASCII output with a `rich`-based live UI:

- single persistent status line with spinner + elapsed time + level meter
- compact final summary line after the run
- quiet logging by default (WARNING), `--verbose` switches to INFO

The classic CLI (``speech-to-text``) is untouched. This package is the
playground for richer terminal UX; further experiments live under
``speech-to-text-tui-<framework>`` once introduced.
"""
