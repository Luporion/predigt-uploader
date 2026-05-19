from pathlib import Path

import pytest

from predigt_uploader.config import ConfigLoadError, default_config, load_config
from predigt_uploader.config import describe_config_source, save_user_config_values


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
open_target_folder = false
raw_archive_mode = "copy"

[naming]
year_folder_template = "{year} Video+Audio"
''',
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert str(config.vmix_storage) == "X:\\vmix"
    assert str(config.recordings_base) == "D:\\Aufnahmen"
    assert config.ffmpeg_path == "C:\\tools\\ffmpeg.exe"
    assert config.copy_instead_of_move is False
    assert config.open_target_folder is False
    assert config.raw_archive_mode == "copy"
    assert config.year_folder_template == "{year} Video+Audio"


def test_default_recordings_base_uses_current_user_desktop(monkeypatch, tmp_path: Path):
    home = tmp_path / "User"
    monkeypatch.setattr(Path, "home", lambda: home)

    config = default_config()

    assert config.recordings_base == home / "Desktop" / "Aufnahmen"


def test_load_config_ignores_removed_write_summary_file_option(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '''
[workflow]
write_summary_file = false
''',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert not hasattr(config, "write_summary_file")


def test_load_config_raises_for_missing_explicit_path(tmp_path: Path):
    missing_path = tmp_path / "fehlt.toml"

    with pytest.raises(ConfigLoadError) as error:
        load_config(missing_path)

    assert "nicht gefunden" in error.value.user_message
    assert str(missing_path) in error.value.admin_hint


def test_load_config_raises_for_invalid_toml(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[paths\nrecordings_base = 'x'", encoding="utf-8")

    with pytest.raises(ConfigLoadError) as error:
        load_config(config_path)

    assert "ungültig" in error.value.user_message
    assert str(config_path) in error.value.admin_hint


def test_load_config_raises_for_unreadable_file(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[paths]\n", encoding="utf-8")

    def fail_open(*_args, **_kwargs):
        raise PermissionError("kein Zugriff")

    monkeypatch.setattr(Path, "open", fail_open)

    with pytest.raises(ConfigLoadError) as error:
        load_config(config_path)

    assert "konnte nicht gelesen werden" in error.value.user_message
    assert "kein Zugriff" in error.value.admin_hint


def test_save_user_config_values_writes_appdata_config(monkeypatch, tmp_path: Path):
    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))

    saved_path = save_user_config_values(paths={"recordings_base": str(tmp_path / "Aufnahmen")})

    assert saved_path == appdata / "PredigtUploader" / "config.toml"
    text = saved_path.read_text(encoding="utf-8")
    assert "[paths]" in text
    assert "recordings_base" in text
    assert "Aufnahmen" in text


def test_save_user_config_values_writes_naming_and_workflow(monkeypatch, tmp_path: Path):
    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))

    saved_path = save_user_config_values(
        naming={"year_folder_template": "{year} Video+Audio"},
        workflow={"raw_archive_mode": "move"},
    )

    text = saved_path.read_text(encoding="utf-8")
    assert 'year_folder_template = "{year} Video+Audio"' in text
    assert 'raw_archive_mode = "move"' in text


def test_describe_config_source_mentions_appdata(monkeypatch, tmp_path: Path):
    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))
    config_path = appdata / "PredigtUploader" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("[paths]\n", encoding="utf-8")

    assert "%APPDATA%" in describe_config_source()
