from typing import Protocol
from audio.converter.models.conversion_config import ConversionConfig


class AudioConverter(Protocol):
    def convert(self, config: ConversionConfig) -> None:
        """
        Convert audio file or directory based on the configuration.
        """
        ...

    def list_formats(self) -> list[str]:
        """
        List all supported audio formats.
        """
        ...
