"""Recorder variant that pushes RMS level updates to a callback.

Same input model (`RecordingConfig`) and output (`np.ndarray`) as the
classic recorder, but free of `print()` calls. The level callback lets
the live presenter draw a real-time RMS meter without coupling the
recorder to any UI framework.
"""
from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from typing import Any

import numpy as np
import sounddevice as sd
from pynput import keyboard

from audio.recorder.models.audio_config import RecordingConfig

logger = logging.getLogger(__name__)

LevelCallback = Callable[[float], None]
PauseCallback = Callable[[bool], None]
StopCallback = Callable[[], None]
ChunkCallback = Callable[[np.ndarray], None]

_LEVEL_FLOOR: float = 1e-6
_LEVEL_REFERENCE: float = 0.3  # RMS at which the bar is "full"
_CTRL_KEYS: frozenset[keyboard.Key] = frozenset({keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r})


class ModernRecorder:
    """Audio recorder with optional UI callbacks.

    Implements :class:`audio.recorder.interfaces.audio_protocols.AudioRecorder`
    structurally: same `record(config) -> np.ndarray` signature.
    """

    def __init__(
            self,
            on_level: LevelCallback | None = None,
            on_pause: PauseCallback | None = None,
            on_stop: StopCallback | None = None,
            on_chunk: ChunkCallback | None = None,
    ) -> None:
        self._on_level = on_level or (lambda _level: None)
        self._on_pause = on_pause or (lambda _paused: None)
        self._on_stop = on_stop or (lambda: None)
        self._on_chunk = on_chunk or (lambda _samples: None)
        self._is_recording: bool = False
        self._is_paused: bool = False
        self._audio_chunks: list[np.ndarray] = []
        self._ctrl_held: bool = False

    def record(self, config: RecordingConfig) -> np.ndarray:
        self._audio_chunks = []
        self._is_recording = True
        self._is_paused = False
        self._ctrl_held = False

        def audio_callback(
                indata: np.ndarray,
                frames: int,
                time: object,
                status: sd.CallbackFlags,
        ) -> None:
            if status:
                logger.warning("Sounddevice status: %s", status)
            if not self._is_recording or self._is_paused:
                self._on_level(0.0)
                return
            chunk = indata.copy()
            self._audio_chunks.append(chunk)
            self._on_level(_rms_to_unit(indata))
            self._on_chunk(chunk)

        def on_press(key: keyboard.Key | keyboard.KeyCode) -> None:
            if key in _CTRL_KEYS:
                self._ctrl_held = True
                return
            if not self._ctrl_held:
                return
            if key == keyboard.Key.space:
                self._is_paused = not self._is_paused
                self._on_pause(self._is_paused)
                return
            if key == keyboard.Key.enter:
                self._is_recording = False
                self._on_stop()

        def on_release(key: keyboard.Key | keyboard.KeyCode) -> bool | None:
            if key in _CTRL_KEYS:
                self._ctrl_held = False
                return None
            if key == keyboard.Key.enter and not self._is_recording:
                return False
            return None

        listener_kwargs: dict[str, Any] = {}
        if sys.platform == "darwin":
            listener_kwargs["darwin_intercept"] = _build_darwin_intercept()
        elif sys.platform == "win32":
            listener_kwargs["win32_event_filter"] = _build_win32_filter()

        with sd.InputStream(
                samplerate=config.samplerate,
                channels=config.channels,
                callback=audio_callback,
        ):
            with keyboard.Listener(on_press=on_press, on_release=on_release, **listener_kwargs) as listener:
                listener.join()

        if not self._audio_chunks:
            return np.array([], dtype=np.float32)
        return np.concatenate(self._audio_chunks, axis=0)


# macOS virtual key codes for keys we want to swallow while CTRL is held.
_DARWIN_VK_SPACE: int = 0x31
_DARWIN_VK_RETURN: int = 0x24
_DARWIN_VK_ENTER: int = 0x4C  # numeric keypad enter
_DARWIN_ENTER_VKS: frozenset[int] = frozenset({_DARWIN_VK_RETURN, _DARWIN_VK_ENTER})
_DARWIN_CONTROL_FLAG: int = 0x40000  # kCGEventFlagMaskControl

# Windows virtual key codes.
_WIN_VK_SPACE: int = 0x20
_WIN_VK_RETURN: int = 0x0D
_WIN_VK_CONTROL: int = 0x11


def _build_darwin_intercept() -> Callable[[Any, Any], Any]:
    """Return a darwin_intercept that drops ENTER (and CTRL+SPACE) events.

    While recording, ENTER must never reach the terminal: a stray newline
    scrolls Rich's transient Live region into the scrollback, leaving a
    duplicated "Recording" line per keypress, and any leaked CTRL+ENTER
    on exit produces trailing empty prompts. Suppressing ENTER outright
    (with or without CTRL) is safe here because the recorder owns the
    terminal foreground for the duration of the listener.
    """
    import Quartz  # type: ignore[import-not-found]

    def intercept(event_type: Any, event: Any) -> Any:
        vk = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
        if vk in _DARWIN_ENTER_VKS:
            return None
        if vk == _DARWIN_VK_SPACE:
            flags = Quartz.CGEventGetFlags(event)
            if flags & _DARWIN_CONTROL_FLAG:
                return None
        return event

    return intercept


def _build_win32_filter() -> Callable[[Any, Any], Any]:
    """Return a win32_event_filter that drops ENTER (and CTRL+SPACE) events."""
    import ctypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]

    def _ctrl_down() -> bool:
        return bool(user32.GetAsyncKeyState(_WIN_VK_CONTROL) & 0x8000)

    def filter_event(msg: Any, data: Any) -> bool:
        if data.vkCode == _WIN_VK_RETURN:
            return False
        if data.vkCode == _WIN_VK_SPACE and _ctrl_down():
            return False
        return True

    return filter_event


def _rms_to_unit(samples: np.ndarray) -> float:
    """Map an audio chunk to a 0..1 level using RMS, scaled & clipped."""
    if samples.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64)) + _LEVEL_FLOOR))
    return min(1.0, rms / _LEVEL_REFERENCE)
