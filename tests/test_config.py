from pathlib import Path

from predigt_uploader.config import load_config


def test_load_config_from_explicit_path(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '''
[paths]
vmix_storage = "X:\\\\vmix"
recordings_base = "D:\\\\Aufnahmen"
mp3_base = "Y:\\\\Predigten"
ffmpeg_path = "C:\\\\tools\\\\ffmpeg.exe"

[workflow]
copy_instead_of_move = false
''',
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert str(config.vmix_storage) == "X:\\vmix"
    assert str(config.recordings_base) == "D:\\Aufnahmen"
    assert config.ffmpeg_path == "C:\\tools\\ffmpeg.exe"
    assert config.copy_instead_of_move is False
