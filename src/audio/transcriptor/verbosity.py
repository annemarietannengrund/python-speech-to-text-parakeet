"""Verbosity control for noisy third-party libraries (NeMo, PyTorch, etc.).

Silences library logging, Python warnings and low-level stdout/stderr
chatter unless the user explicitly opts in with ``--verbose``.
"""
from __future__ import annotations

import logging
import os
import sys
import warnings
from contextlib import contextmanager
from collections.abc import Iterator

_NOISY_LOGGERS: tuple[str, ...] = (
    "nemo_logger",
    "nemo",
    "pytorch_lightning",
    "lightning",
    "lightning.pytorch",
    "torch",
    "torch.distributed",
    "torch.distributed.elastic.multiprocessing.redirects",
    "transformers",
    "filelock",
    "fsspec",
    "huggingface_hub",
)

_QUIET_ENV: dict[str, str] = {
    "NEMO_TESTING": "1",
    "TRANSFORMERS_VERBOSITY": "error",
    "TOKENIZERS_PARALLELISM": "false",
    "PYTHONWARNINGS": "ignore",
    "HF_HUB_DISABLE_PROGRESS_BARS": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "ONE_LOGGER_ENABLED": "false",
}


_state: dict[str, bool] = {"verbose": True}


def is_quiet() -> bool:
    """Return True when third-party output should be suppressed."""
    return not _state["verbose"]


def configure_verbosity(verbose: bool) -> None:
    """Apply global verbosity settings.

    When ``verbose`` is False, third-party loggers and warnings are silenced.
    Must be called as early as possible, before importing NeMo/torch.
    """
    _state["verbose"] = verbose
    if verbose:
        return

    for key, value in _QUIET_ENV.items():
        os.environ.setdefault(key, value)

    warnings.filterwarnings("ignore")
    logging.captureWarnings(True)

    for name in _NOISY_LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(logging.ERROR)
        logger.propagate = False


@contextmanager
def suppress_stdio(enabled: bool) -> Iterator[None]:
    """Redirect file descriptors 1/2 to /dev/null while ``enabled`` is True.

    Catches output from C/C++ extensions (e.g. NeMo print statements,
    tqdm progress bars) that bypass Python's ``sys.stdout``.
    """
    if not enabled:
        yield
        return

    sys.stdout.flush()
    sys.stderr.flush()
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved_stdout = os.dup(1)
    saved_stderr = os.dup(2)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(saved_stdout, 1)
        os.dup2(saved_stderr, 2)
        os.close(devnull)
        os.close(saved_stdout)
        os.close(saved_stderr)
