import argparse
import logging
import sys
from pathlib import Path
from audio.core.models import AudioFormat
from audio.core.config import AudioConverterSettings, load_settings
from audio.converter.models.conversion_config import ConversionConfig
from audio.converter.core import FFmpegAudioConverter
from audio.converter.interfaces.converter_protocols import AudioConverter


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("audio_converter")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


class AudioConverterCLI:
    def __init__(self, converter: AudioConverter, logger: logging.Logger, settings: AudioConverterSettings) -> None:
        self.converter = converter
        self.logger = logger
        self.settings = settings

    def run(self) -> None:
        parser = argparse.ArgumentParser(description="Convert audio files between formats.")

        # Single file arguments
        parser.add_argument("input", nargs="?", help="Input file path")
        parser.add_argument("output", nargs="?", help="Output file path")

        # Bulk arguments
        parser.add_argument("--input-folder", help="Folder containing files to convert")
        parser.add_argument("--output-folder", help="Folder to store converted files")
        parser.add_argument("--recursive", action="store_true", help="Process subdirectories")

        # Format mapping
        parser.add_argument("--from", dest="from_format", choices=[f.value for f in AudioFormat],
                            help="Source format for bulk conversion")
        parser.add_argument("--to", dest="to_format", choices=[f.value for f in AudioFormat], help="Target format")

        # Options
        parser.add_argument("--list", action="store_true", help="List all supported format mappings")
        parser.add_argument("--ask-overwrite", action="store_true", default=self.settings.ask_on_overwrite,
                            help=f"Ask before overwriting existing files (default: {self.settings.ask_on_overwrite})")

        args = parser.parse_args()

        if args.list:
            formats = self.converter.list_formats()
            print("Supported formats:", ", ".join(formats))
            return

        if args.ask_overwrite and hasattr(self.converter, 'ask_on_overwrite'):
            self.converter.ask_on_overwrite = True

        try:
            config = self._build_config(args)
            self.converter.convert(config)
        except Exception as e:
            self.logger.error("Error: %s", e)
            sys.exit(1)

    def _build_config(self, args: argparse.Namespace) -> ConversionConfig:
        if args.input_folder:
            return self._build_bulk_config(args)

        if args.input:
            return self._build_single_config(args)

        raise ValueError("Either an input file or --input-folder must be specified")

    def _build_single_config(self, args: argparse.Namespace) -> ConversionConfig:
        input_path = Path(args.input)

        if args.to_format:
            to_format = AudioFormat(args.to_format)
            output_path = Path(args.output) if args.output else input_path.with_suffix(f".{to_format.value}")
        elif args.output:
            output_path = Path(args.output)
            to_format = self._determine_format_from_path(output_path)
        else:
            raise ValueError("Target format (--to) or output file must be specified for single file conversion")

        return ConversionConfig(
            input_path=input_path,
            output_path=output_path,
            to_format=to_format,
            overwrite=not args.ask_overwrite
        )

    def _build_bulk_config(self, args: argparse.Namespace) -> ConversionConfig:
        if not args.from_format or not args.to_format:
            raise ValueError("--from and --to formats are mandatory for bulk conversion")

        input_folder = Path(args.input_folder)
        output_folder = Path(args.output_folder) if args.output_folder else input_folder

        return ConversionConfig(
            input_path=input_folder,
            output_path=output_folder,
            from_format=AudioFormat(args.from_format),
            to_format=AudioFormat(args.to_format),
            recursive=args.recursive,
            overwrite=not args.ask_overwrite
        )

    def _determine_format_from_path(self, path: Path) -> AudioFormat:
        ext = path.suffix.lower().lstrip('.')
        try:
            return AudioFormat(ext)
        except ValueError:
            raise ValueError(f"Unsupported output format: {ext}")


def main() -> None:
    settings = load_settings()
    logger = setup_logging()
    converter = FFmpegAudioConverter()
    cli = AudioConverterCLI(converter, logger, settings.converter)
    cli.run()


if __name__ == "__main__":
    main()
