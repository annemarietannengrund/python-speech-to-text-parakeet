import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from audio.converter.cli import AudioConverterCLI
from audio.core.config import AudioConverterSettings

@pytest.fixture
def mock_converter():
    return Mock()

@pytest.fixture
def cli(mock_converter):
    return AudioConverterCLI(mock_converter, Mock(), AudioConverterSettings())

def test_cli_list_formats(cli, mock_converter, capsys):
    mock_converter.list_formats.return_value = ["mp3", "wav"]
    
    with patch("argparse.ArgumentParser.parse_args", return_value=Mock(list=True)):
        cli.run()
    
    captured = capsys.readouterr()
    assert "Supported formats: mp3, wav" in captured.out

def test_cli_single_file_lazy(cli, mock_converter):
    args = Mock(
        input="test.wav",
        output=None,
        input_folder=None,
        output_folder=None,
        from_format=None,
        to_format="mp3",
        recursive=False,
        list=False,
        ask_overwrite=False
    )
    
    with patch("argparse.ArgumentParser.parse_args", return_value=args):
        cli.run()
    
    mock_converter.convert.assert_called_once()
    config = mock_converter.convert.call_args[0][0]
    assert config.input_path == Path("test.wav")
    assert config.output_path == Path("test.mp3")
    assert config.to_format.value == "mp3"

def test_cli_bulk_conversion(cli, mock_converter):
    args = Mock(
        input=None,
        output=None,
        input_folder="in",
        output_folder="out",
        from_format="wav",
        to_format="mp3",
        recursive=True,
        list=False,
        ask_overwrite=False
    )
    
    with patch("argparse.ArgumentParser.parse_args", return_value=args):
        cli.run()
    
    mock_converter.convert.assert_called_once()
    config = mock_converter.convert.call_args[0][0]
    assert config.input_path == Path("in")
    assert config.output_path == Path("out")
    assert config.from_format.value == "wav"
    assert config.to_format.value == "mp3"
    assert config.recursive is True
