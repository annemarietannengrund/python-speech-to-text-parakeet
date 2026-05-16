# speech-to-text-modern

A sibling CLI to `speech-to-text` that keeps the same backend
(recording, conversion, Parakeet transcription) but ships a richer
terminal experience.

## Naming convention for UX experiments

We expect to try several terminal UI frameworks in parallel before
settling on one. To keep variants cleanly separated, follow:

| Command                          | UI layer      | Notes                         |
|----------------------------------|---------------|-------------------------------|
| `speech-to-text`                 | plain ASCII   | classic, stays untouched      |
| `speech-to-text-modern`          | `rich` (Live) | this package; persistent line |
| `speech-to-text-tui-<framework>` | full TUI      | e.g. `-tui-textual`, future   |

Throwaway variants live in their own package mirror so we can delete
the loser without touching the others.

## Current choices (revisit later)

- **Live UI:** [`rich`](https://github.com/Textualize/rich) — chosen
  for low ceremony and great defaults. Alternatives still worth trying:
    - [`textual`](https://textual.textualize.io/) — full TUI, will get its
      own `speech-to-text-tui-textual` entry point.
    - [`prompt_toolkit`](https://python-prompt-toolkit.readthedocs.io/) —
      fine-grained control, more boilerplate.
    - [`urwid`](https://urwid.org/) — mature, slightly old-school.
- **Level meter:** simple RMS-to-unit mapping with a 20-cell bar. Could
  later be replaced with peak-hold or A-weighted dBFS.
- **Default verbosity:** logger at `WARNING`; user feedback flows
  through `rich`. `--verbose` flips to DEBUG.

## Flow

1. `Recording` phase: spinner, elapsed time, live RMS bar, key hints.
2. `Loading model` / `Transcribing` phases: spinner with elapsed time.
3. `Cleanup` phase (if `--cleanup` requested).
4. Final compact summary line + `── Transcription ──` block.
