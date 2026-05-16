from unittest.mock import patch

import pytest

from audio.converter import FFmpegAudioConverter
from audio.converter.models.conversion_config import ConversionConfig
from audio.core import AudioFormat


@pytest.fixture
def converter():
    return FFmpegAudioConverter()


def test_list_formats(converter):
    formats = converter.list_formats()
    assert "mp3" in formats
    assert "wav" in formats
    assert "ogg" in formats
    assert "flac" in formats
    assert "mp4" in formats


@patch("subprocess.run")
def test_convert_single_file(mock_run, converter, tmp_path):
    input_file = tmp_path / "test.wav"
    input_file.touch()
    output_file = tmp_path / "test.mp3"

    config = ConversionConfig(
        input_path=input_file,
        output_path=output_file,
        to_format=AudioFormat.MP3
    )

    converter.convert(config)

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "ffmpeg"
    assert "-i" in cmd
    assert str(input_file) in cmd
    assert str(output_file) in cmd
    assert "libmp3lame" in cmd


@patch("subprocess.run")
def test_convert_directory_recursive(mock_run, converter, tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    sub_dir = input_dir / "sub"
    sub_dir.mkdir()

    file1 = input_dir / "file1.wav"
    file1.touch()
    file2 = sub_dir / "file2.wav"
    file2.touch()

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    config = ConversionConfig(
        input_path=input_dir,
        output_path=output_dir,
        from_format=AudioFormat.WAV,
        to_format=AudioFormat.MP3,
        recursive=True
    )

    converter.convert(config)

    assert mock_run.call_count == 2
    # Verify structure in output_dir
    assert (output_dir / "file1.mp3").parent == output_dir
    assert (output_dir / "sub" / "file2.mp3").parent == output_dir / "sub"


@patch("subprocess.run")
def test_should_not_overwrite_if_asked_and_declined(mock_run, converter, tmp_path):
    input_file = tmp_path / "test.wav"
    input_file.touch()
    output_file = tmp_path / "test.mp3"
    output_file.touch()

    converter.ask_on_overwrite = True

    config = ConversionConfig(
        input_path=input_file,
        output_path=output_file,
        to_format=AudioFormat.MP3
    )

    with patch("builtins.input", return_value="n"):
        converter.convert(config)

    mock_run.assert_not_called()


@patch("subprocess.run")
def test_should_overwrite_if_asked_and_accepted(mock_run, converter, tmp_path):
    input_file = tmp_path / "test.wav"
    input_file.touch()
    output_file = tmp_path / "test.mp3"
    output_file.touch()

    converter.ask_on_overwrite = True

    config = ConversionConfig(
        input_path=input_file,
        output_path=output_file,
        to_format=AudioFormat.MP3
    )

    with patch("builtins.input", return_value="y"):
        converter.convert(config)

    mock_run.assert_called_once()
