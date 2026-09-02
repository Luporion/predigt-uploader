from pathlib import Path
import tomllib

import pytest

from predigt_uploader.config import (
    DEFAULT_VIMEO_TARGET_FOLDER_ID,
    DEFAULT_VIMEO_TARGET_FOLDER_NAME,
    DEFAULT_VIMEO_TEAM_OWNER_USER_ID,
    ConfigLoadError,
    default_config,
    load_config,
)
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
cut_mp4_folder = "D:\\\\Schnitt"

[workflow]
copy_instead_of_move = false
open_target_folder = false
raw_archive_mode = "copy"

[naming]
year_folder_template = "{year} Video+Audio"

[service_types]
additional = ["Andacht|true|true|false"]

[vimeo]
team_owner_user_id = "12345"
target_folder_id = "67890"
target_folder_name = "Predigten"
''',
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert str(config.vmix_storage) == "X:\\vmix"
    assert str(config.recordings_base) == "D:\\Aufnahmen"
    assert str(config.cut_mp4_folder) == "D:\\Schnitt"
    assert config.ffmpeg_path == "C:\\tools\\ffmpeg.exe"
    assert config.copy_instead_of_move is False
    assert config.open_target_folder is False
    assert config.raw_archive_mode == "copy"
    assert config.year_folder_template == "{year} Video+Audio"
    assert config.custom_service_types[0].name == "Andacht"
    assert config.custom_service_types[0].requires_title is True
    assert config.custom_service_types[0].requires_bible_reference is True
    assert config.custom_service_types[0].requires_speaker is False
    assert config.vimeo.team_owner_user_id == "12345"
    assert config.vimeo.target_folder_id == "67890"
    assert config.vimeo.target_folder_name == "Predigten"


def test_default_recordings_base_uses_current_user_desktop(monkeypatch, tmp_path: Path):
    home = tmp_path / "User"
    monkeypatch.setattr(Path, "home", lambda: home)

    config = default_config()

    assert config.recordings_base == home / "Desktop" / "Aufnahmen"
    assert config.vimeo.team_owner_user_id == DEFAULT_VIMEO_TEAM_OWNER_USER_ID
    assert config.vimeo.target_folder_id == DEFAULT_VIMEO_TARGET_FOLDER_ID
    assert config.vimeo.target_folder_name == DEFAULT_VIMEO_TARGET_FOLDER_NAME


def test_existing_config_without_vimeo_section_uses_safe_non_secret_defaults_without_rewrite(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    original = '[paths]\nrecordings_base = "D:\\\\Aufnahmen"\n'
    config_path.write_text(original, encoding="utf-8")

    config = load_config(config_path)

    assert config.recordings_base == Path(r"D:\Aufnahmen")
    assert config.vimeo.team_owner_user_id == "59930802"
    assert config.vimeo.target_folder_id == "1320477"
    assert config.vimeo.target_folder_name == "Predigten"
    assert config_path.read_text(encoding="utf-8") == original


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


def test_save_user_config_values_writes_custom_service_types(monkeypatch, tmp_path: Path):
    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))

    saved_path = save_user_config_values(service_types=["Andacht|true|true|false"])

    text = saved_path.read_text(encoding="utf-8")
    assert "[service_types]" in text
    assert 'additional = ["Andacht|true|true|false"]' in text


def test_save_user_config_values_writes_non_secret_vimeo_target(monkeypatch, tmp_path: Path):
    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))

    saved_path = save_user_config_values(
        vimeo={
            "team_owner_user_id": "12345",
            "target_folder_id": "67890",
            "target_folder_name": "Predigten",
        }
    )

    text = saved_path.read_text(encoding="utf-8")
    assert "[vimeo]" in text
    assert 'team_owner_user_id = "12345"' in text
    assert 'target_folder_id = "67890"' in text
    assert "token" not in text.casefold()


def test_describe_config_source_mentions_appdata(monkeypatch, tmp_path: Path):
    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))
    config_path = appdata / "PredigtUploader" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("[paths]\n", encoding="utf-8")

    assert "%APPDATA%" in describe_config_source()


def test_settings_round_trip_preserves_general_and_vimeo_values(monkeypatch, tmp_path: Path):
    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))
    saved = save_user_config_values(
        paths={
            "mp3_base": str(tmp_path / "Ziel"),
            "vmix_storage": str(tmp_path / "Roh"),
            "losslesscut_path": str(tmp_path / "LosslessCut.exe"),
        },
        naming={"year_folder_template": "{year} Video+Audio"},
        workflow={"raw_archive_mode": "copy"},
        vimeo={
            "team_owner_user_id": "59930802",
            "target_folder_id": "1320477",
            "target_folder_name": "Predigten",
        },
    )

    loaded = load_config(saved)

    assert loaded.mp3_base == tmp_path / "Ziel"
    assert loaded.vmix_storage == tmp_path / "Roh"
    assert loaded.losslesscut_path == str(tmp_path / "LosslessCut.exe")
    assert loaded.year_folder_template == "{year} Video+Audio"
    assert loaded.raw_archive_mode == "copy"
    assert loaded.vimeo.target_folder_id == "1320477"
    assert "token" not in saved.read_text(encoding="utf-8").casefold()


def test_save_does_not_overwrite_invalid_existing_config(monkeypatch, tmp_path: Path):
    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))
    path = appdata / "PredigtUploader" / "config.toml"
    path.parent.mkdir(parents=True)
    original = "[paths\nungueltig"
    path.write_text(original, encoding="utf-8")

    with pytest.raises(ConfigLoadError) as error:
        save_user_config_values(paths={"mp3_base": "X"})

    assert "nicht überschrieben" in error.value.user_message
    assert path.read_text(encoding="utf-8") == original


def test_save_preserves_unknown_toml_sections_and_keys(monkeypatch, tmp_path: Path):
    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))
    config_path = appdata / "PredigtUploader" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        '[paths]\nrecordings_base = "D:\\\\Alt"\ncustom_path_key = "bleibt"\n\n'
        '[future]\nenabled = true\ncount = 7\n\n[future.nested]\nlabel = "erhalten"\n',
        encoding="utf-8",
    )

    save_user_config_values(paths={"recordings_base": r"D:\Neu"})

    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    assert data["paths"]["recordings_base"] == r"D:\Neu"
    assert data["paths"]["custom_path_key"] == "bleibt"
    assert data["future"] == {"enabled": True, "count": 7, "nested": {"label": "erhalten"}}
