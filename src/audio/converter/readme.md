# Audio Converter CLI

A command-line tool for converting audio files between various formats (OGG, MP3, WAV, FLAC, MP4).

## wishes

- can convert audio files from one format to another
- takes a input file, produces an output file
- supported types (related to supported record_audio types)
    - ogg
    - mp3
    - wav
    - flac
    - mp4
- has some list option of mapped formats
- should be able to convert beteen all supported types (25 permutations)
- can be given a inputfolder, will convet its contents (requires --from and --to mapping)
- can be given a outputfolder (optional) that wil create the outputs there.
- can be given a recursive option, when folder is given.
- can map formats for bulk conversion (mandatory for folder input)
- supports "lazy" single file conversion by providing input file and --to format
- we have a cli entrypoint for this module in pytoml
- we have a designated cli python file for the module

## Usage (Intended)

### Single File Conversion

```bash
# Explicit input and output
audio-convert input.wav output.mp3

# Lazy conversion (target format specified, output name inferred)
audio-convert input.wav --to mp3
```

### Bulk Folder Conversion

Note: When processing a folder, `--from` and `--to` are mandatory.

```bash
# Convert all mp3 files in a folder to flac
audio-convert --input-folder ./raw_audio --output-folder ./converted --from mp3 --to flac

# Convert recursively
audio-convert --input-folder ./archive --recursive --from wav --to ogg
```

### CLI Reference

- `input`: Input file path.
- `output`: Output file path.
- `--input-folder`: Folder containing files to convert.
- `--output-folder`: Folder to store converted files.
- `--recursive`: Process subdirectories.
- `--from`: Source format for bulk conversion.
- `--to`: Target format for bulk conversion.
- `--list`: List all supported format mappings.