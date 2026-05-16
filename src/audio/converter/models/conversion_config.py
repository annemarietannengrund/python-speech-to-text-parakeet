from dataclasses import dataclass
from pathlib import Path
from audio.core.models import AudioFormat


@dataclass(frozen=True)
class ConversionConfig:
    input_path: Path
    output_path: Path
    from_format: AudioFormat | None = None
    to_format: AudioFormat | None = None
    recursive: bool = False
    overwrite: bool = True
