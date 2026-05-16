import logging
import os
import subprocess
import tempfile
import numpy as np
import sounddevice as sd
import soundfile as sf
from pynput import keyboard
from audio.core import AudioFormat
from audio.recorder.models.audio_config import RecordingConfig

logger = logging.getLogger(__name__)

_CTRL_KEYS: frozenset[keyboard.Key] = frozenset({keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r})


class Recorder:
    def __init__(self) -> None:
        self._is_recording = False
        self._is_paused = False
        self._audio_chunks: list[np.ndarray] = []
        self._ctrl_held: bool = False

    def record(self, config: RecordingConfig) -> np.ndarray:
        self._audio_chunks = []
        self._is_recording = True
        self._is_paused = False
        self._ctrl_held = False

        print("\n--- Recording started ---")
        print("Press CTRL+SPACE to pause/resume")
        print("Press CTRL+ENTER to stop")

        def callback(indata: np.ndarray, frames: int, time: any, status: sd.CallbackFlags) -> None:
            if status:
                logger.warning("Sounddevice status: %s", status)
            if self._is_recording and not self._is_paused:
                self._audio_chunks.append(indata.copy())

        def on_press(key: keyboard.Key | keyboard.KeyCode) -> bool | None:
            if key in _CTRL_KEYS:
                self._ctrl_held = True
                return None
            if not self._ctrl_held:
                return None
            if key == keyboard.Key.space:
                self._is_paused = not self._is_paused
                status = "PAUSED" if self._is_paused else "RESUMED"
                print(f"\nRecording {status}")
                return None
            if key == keyboard.Key.enter:
                self._is_recording = False
                return False  # Stop listener
            return None

        def on_release(key: keyboard.Key | keyboard.KeyCode) -> None:
            if key in _CTRL_KEYS:
                self._ctrl_held = False

        with sd.InputStream(samplerate=config.samplerate, channels=config.channels, callback=callback):
            with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
                listener.join()

        print("\nRecording stopped.")
        if not self._audio_chunks:
            return np.array([], dtype=np.float32)
        
        return np.concatenate(self._audio_chunks, axis=0)

class Exporter:
    def export(self, data: np.ndarray, config: RecordingConfig) -> None:
        if data.size == 0:
            logger.error("No audio data to export")
            return

        if config.format == AudioFormat.WAV:
            sf.write(config.filename, data, config.samplerate)
            logger.info("Saved to %s", config.filename)
        elif config.format == AudioFormat.FLAC:
            sf.write(config.filename, data, config.samplerate, format='FLAC')
            logger.info("Saved to %s", config.filename)
        elif config.format in [AudioFormat.MP3, AudioFormat.OGG, AudioFormat.MP4]:
            self._export_with_ffmpeg(data, config)
        else:
            raise ValueError(f"Unsupported format: {config.format}")

    def _export_with_ffmpeg(self, data: np.ndarray, config: RecordingConfig) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_wav_name = tmp_wav.name
        
        try:
            sf.write(tmp_wav_name, data, config.samplerate)
            
            cmd = ["ffmpeg", "-y", "-i", tmp_wav_name]
            
            if config.format == AudioFormat.MP3:
                cmd.extend(["-codec:a", "libmp3lame", "-q:a", "2"])
            elif config.format == AudioFormat.OGG:
                cmd.extend(["-codec:a", "libvorbis", "-q:a", "4"])
            elif config.format == AudioFormat.MP4:
                cmd.extend(["-codec:a", "aac", "-b:a", "192k"])
            
            cmd.append(config.filename)
            
            logger.info("Running ffmpeg: %s", " ".join(cmd))
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("Successfully exported to %s", config.filename)
        except subprocess.CalledProcessError as e:
            logger.error("FFmpeg failed: %s", e)
            raise
        except FileNotFoundError:
            logger.error("FFmpeg not found. Please install ffmpeg.")
            raise
        finally:
            if os.path.exists(tmp_wav_name):
                os.remove(tmp_wav_name)
