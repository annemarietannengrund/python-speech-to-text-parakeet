# Speech to Text CLI

A command-line tool for transcribing audio files into text or markdown using NVIDIA Parakeet (NeMo). It supports
individual file transcription, recursive folder processing, and live recording transcription.

## Installation & Usage

The tool is managed by `uv`.

### 1. Run from outside the repository

```bash
uv run --project /path/to/python-speech-to-text-parakeet speech-to-text
```

### 2. Install as a global tool

```bash
uv tool install /path/to/python-speech-to-text-parakeet --editable --prerelease=allow
```

Now you can just run:

```bash
speech-to-text
```

### 3. Run from within the repository

```bash
uv run speech-to-text
```

## CLI Reference

### Basic Usage

```bash
# Transcribe a single file
speech-to-text my_audio.mp3

# Transcribe all audio files in a directory recursively
speech-to-text ./my_audio_folder --recursive

# Start a recording and transcribe it immediately
speech-to-text --record
```

### Arguments & Options

- `path`: (Optional) Path to an audio file or directory.
- `--recursive`: Walk through folders recursively and transcribe all supported audio files.
- `--record`: Use the integrated `record_audio` module to capture and then transcribe live audio.
- `--format`: Specify output extension (`txt` or `md`). Defaults to `txt`.
- `--model`: Transcription model id (default: `nvidia/parakeet-tdt-0.6b-v3`).
- `--provider`: Transcription provider (default: `parakeet`).
- `--no-skip`: Force transcription even if the output file already exists (default is to skip).
- `--list-providers`: List the transcription providers registered in this build and exit.

## Environment

| Variable                   | Default                               | Purpose                                                    |
|----------------------------|---------------------------------------|------------------------------------------------------------|
| `STT_PROVIDER`             | `parakeet`                            | Active provider (single choice today).                     |
| `STT_MODEL`                | `nvidia/parakeet-tdt-0.6b-v3`         | Hugging Face model id.                                     |
| `STT_DEVICE`               | auto (`mps` if available, else `cpu`) | Torch device override.                                     |
| `STT_PRECONVERSION_FORMAT` | `flac`                                | Target format used when FFmpeg pre-conversion is required. |

The Parakeet weights are fetched via Hugging Face Hub and cached under
`~/.cache/huggingface/hub/` (override with `HF_HOME`). The model is
`nvidia/parakeet-tdt-0.6b-v3`, released under **CC-BY-4.0**.

## Features

- **Smart Conversion**: Automatically handles conversion to Parakeet-supported formats (wav, flac, ogg, mp3) using the
  `audio_converter` module. Pre-conversion target defaults to FLAC.
- **Folder Processing**: Can walk through directories and create transcription files next to the source audio.
- **Flexible Output**: Supports both `.txt` and `.md` output formats.
- **Integrated Recording**: Leverages `record_audio` for a seamless voice-to-text workflow.

## Project Structure

- `src/speech_to_text/cli.py`: Entry point for the CLI.
- `src/speech_to_text/core.py`: Main transcription logic and folder walking.
- `src/speech_to_text/models/`: Data models for transcription settings.
