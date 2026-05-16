import logging
import subprocess
from pathlib import Path
from audio.core.models import AudioFormat
from audio.converter.models.conversion_config import ConversionConfig

class FFmpegAudioConverter:
    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self._ask_on_overwrite = False

    @property
    def ask_on_overwrite(self) -> bool:
        return self._ask_on_overwrite

    @ask_on_overwrite.setter
    def ask_on_overwrite(self, value: bool) -> None:
        self._ask_on_overwrite = value

    def list_formats(self) -> list[str]:
        return [f.value for f in AudioFormat]

    def convert(self, config: ConversionConfig) -> None:
        if config.input_path.is_file():
            self._convert_single_file(config)
        elif config.input_path.is_dir():
            self._convert_directory(config)
        else:
            self.logger.error("Input path does not exist: %s", config.input_path)
            raise FileNotFoundError(f"Input path not found: {config.input_path}")

    def _convert_single_file(self, config: ConversionConfig) -> None:
        input_file = config.input_path
        output_file = config.output_path

        if not self._should_overwrite(output_file):
            self.logger.info("Skipping conversion of %s", input_file)
            return

        self._execute_ffmpeg(input_file, output_file)

    def _convert_directory(self, config: ConversionConfig) -> None:
        if not config.from_format or not config.to_format:
            self.logger.error("Bulk conversion requires --from and --to formats")
            raise ValueError("Bulk conversion requires --from and --to formats")

        input_dir = config.input_path
        output_dir = config.output_path
        pattern = f"*.{config.from_format.value}"
        
        files = list(input_dir.rglob(pattern) if config.recursive else input_dir.glob(pattern))
        
        if not files:
            self.logger.warning("No files with format %s found in %s", config.from_format, input_dir)
            return

        for input_file in files:
            relative_path = input_file.relative_to(input_dir)
            target_output_file = output_dir / relative_path.with_suffix(f".{config.to_format.value}")
            
            target_output_file.parent.mkdir(parents=True, exist_ok=True)
            
            if not self._should_overwrite(target_output_file):
                self.logger.info("Skipping conversion of %s", input_file)
                continue
                
            self._execute_ffmpeg(input_file, target_output_file)

    def _should_overwrite(self, file_path: Path) -> bool:
        if not file_path.exists():
            return True
        
        if not self._ask_on_overwrite:
            return True
            
        response = input(f"File {file_path} already exists. Overwrite? [y/N] ").lower()
        return response == 'y'

    def _execute_ffmpeg(self, input_path: Path, output_path: Path) -> None:
        # Determine target format from extension
        ext = output_path.suffix.lower().lstrip('.')
        try:
            target_format = AudioFormat(ext)
        except ValueError:
            self.logger.warning("Unknown output format %s, using defaults", ext)
            target_format = None

        cmd = ["ffmpeg", "-y", "-i", str(input_path)]
        
        if target_format == AudioFormat.MP3:
            cmd.extend(["-codec:a", "libmp3lame", "-q:a", "2"])
        elif target_format == AudioFormat.OGG:
            cmd.extend(["-codec:a", "libvorbis", "-q:a", "4"])
        elif target_format == AudioFormat.MP4:
            cmd.extend(["-codec:a", "aac", "-b:a", "192k"])
        elif target_format == AudioFormat.FLAC:
            cmd.extend(["-codec:a", "flac"])
        # WAV doesn't need special flags for basic conversion
        
        cmd.append(str(output_path))
        
        try:
            self.logger.info("Converting %s to %s", input_path, output_path)
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            self.logger.error("FFmpeg failed for %s: %s", input_path, e)
            raise
        except FileNotFoundError:
            self.logger.error("FFmpeg not found. Please install ffmpeg.")
            raise
