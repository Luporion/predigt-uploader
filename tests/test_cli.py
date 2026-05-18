from datetime import date
from pathlib import Path

import pytest

from predigt_uploader.cli import (
    Mp3ResultError,
    Mp4TransferError,
    _ask_mp4_path,
    _ask_required,
    _handle_existing_target_mp4,
    _print_missing_ffmpeg_message,
    _print_mp4_action_preview,
    _select_target_folder,
    _transfer_mp4_to_target,
    _validate_created_mp3,
    run_wizard,
)
from predigt_uploader.mp3 import Mp3ConversionError
from predigt_uploader.models import AppConfig, ProcessingPlan, SermonInfo


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )


def _inputs(monkeypatch, values: list[str]) -> None:
    iterator = iter(values)

    def fake_input(prompt: str) -> str:
        print(prompt, end="")
        return next(iterator)

    monkeypatch.setattr("builtins.input", fake_input)


def test_ask_required_repeats_until_value(monkeypatch, capsys):
    _inputs(monkeypatch, ["", "  ", "Heiligkeit"])

    assert _ask_required("Predigttitel") == "Heiligkeit"

    output = capsys.readouterr().out
    assert "Dieses Feld darf nicht leer bleiben" in output


def test_ask_mp4_path_rejects_empty_missing_folder_and_wrong_extension(monkeypatch, tmp_path, capsys):
    folder = tmp_path / "Export"
    folder.mkdir()
    text_file = tmp_path / "notizen.txt"
    text_file.write_text("keine mp4", encoding="utf-8")
    mp4_file = tmp_path / "predigt.mp4"
    mp4_file.write_bytes(b"mp4")

    _inputs(
        monkeypatch,
        [
            "",
            str(tmp_path / "fehlt.mp4"),
            str(folder),
            str(text_file),
            f'"{mp4_file}"',
        ],
    )

    assert _ask_mp4_path() == mp4_file

    output = capsys.readouterr().out
    assert "Datei wurde nicht gefunden" in output
    assert "Das ist ein Ordner" in output
    assert "keine MP4-Datei" in output


def test_select_target_folder_asks_before_using_existing_folder(monkeypatch, tmp_path, capsys):
    existing = tmp_path / "Aufnahmen" / "2026" / "2026-05-24"
    existing.mkdir(parents=True)
    info = SermonInfo(date(2026, 5, 24), "Titel", "Text", "Redner")
    _inputs(monkeypatch, ["j"])

    selected, selected_info = _select_target_folder(_config(tmp_path), info)

    assert selected == existing
    assert selected_info == info
    assert "Diesen vorhandenen Ordner verwenden" in capsys.readouterr().out


def test_select_target_folder_can_create_new_folder_when_existing_is_rejected(monkeypatch, tmp_path, capsys):
    existing = tmp_path / "Aufnahmen" / "2026" / "2026-05-24"
    existing.mkdir(parents=True)
    info = SermonInfo(date(2026, 5, 24), "Titel", "Text", "Redner")
    _inputs(monkeypatch, ["n", "Taufe"])

    selected, selected_info = _select_target_folder(_config(tmp_path), info)

    assert selected == tmp_path / "Aufnahmen" / "2026" / "2026-05-24 - Taufe"
    assert selected_info.folder_note == "Taufe"
    output = capsys.readouterr().out
    assert "neuer Ordner" in output
    assert "2026-05-24 - Taufe" in output


def test_select_target_folder_shows_new_note_folder_name(tmp_path, capsys):
    info = SermonInfo(date(2026, 6, 7), "Titel", "Text", "Redner", folder_note="Pfingsten")

    selected, selected_info = _select_target_folder(_config(tmp_path), info)

    assert selected == tmp_path / "Aufnahmen" / "2026" / "2026-06-07 - Pfingsten"
    assert selected_info == info
    assert "2026-06-07 - Pfingsten" in capsys.readouterr().out


def _plan(tmp_path: Path) -> ProcessingPlan:
    info = SermonInfo(date(2026, 5, 24), "Heiligkeit", "Jesaja 6,1-3", "Eduard Wiebe")
    return ProcessingPlan(
        source_mp4=tmp_path / "quelle.mp4",
        target_mp4=tmp_path / "Aufnahmen" / "2026" / "2026-05-24" / "Predigt.mp4",
        target_mp3=tmp_path / "Aufnahmen" / "2026" / "2026-05-24" / "Predigt.mp3",
        info=info,
    )


def test_print_mp4_action_preview_shows_source_target_name_and_copy_mode(tmp_path, capsys):
    plan = _plan(tmp_path)

    _print_mp4_action_preview(plan, _config(tmp_path))

    output = capsys.readouterr().out
    assert str(plan.source_mp4) in output
    assert str(plan.target_mp4.parent) in output
    assert plan.target_mp4.name in output
    assert "kopiert" in output


def test_handle_existing_target_mp4_can_abort(monkeypatch, tmp_path):
    plan = _plan(tmp_path)
    plan.target_mp4.parent.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"vorhanden")
    _inputs(monkeypatch, ["a"])

    assert _handle_existing_target_mp4(plan) is None


def test_handle_existing_target_mp4_can_keep_existing(monkeypatch, tmp_path):
    plan = _plan(tmp_path)
    plan.target_mp4.parent.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"vorhanden")
    _inputs(monkeypatch, ["b"])

    selected_plan, keep_existing = _handle_existing_target_mp4(plan)

    assert selected_plan == plan
    assert keep_existing is True


def test_handle_existing_target_mp4_can_use_new_name(monkeypatch, tmp_path):
    plan = _plan(tmp_path)
    plan.target_mp4.parent.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"vorhanden")
    _inputs(monkeypatch, ["n", "Predigt anderer Name"])

    selected_plan, keep_existing = _handle_existing_target_mp4(plan)

    assert selected_plan.target_mp4 == plan.target_mp4.with_name("Predigt anderer Name.mp4")
    assert selected_plan.target_mp3 == plan.target_mp4.with_name("Predigt anderer Name.mp3")
    assert keep_existing is False


def test_transfer_mp4_copies_by_default(tmp_path):
    plan = _plan(tmp_path)
    plan.source_mp4.write_bytes(b"video")

    _transfer_mp4_to_target(plan, _config(tmp_path))

    assert plan.source_mp4.exists()
    assert plan.target_mp4.read_bytes() == b"video"


def test_transfer_mp4_does_not_overwrite_existing_target(tmp_path):
    plan = _plan(tmp_path)
    plan.source_mp4.write_bytes(b"neu")
    plan.target_mp4.parent.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"alt")

    with pytest.raises(Mp4TransferError) as error:
        _transfer_mp4_to_target(plan, _config(tmp_path))

    assert "existiert bereits" in error.value.user_message
    assert plan.target_mp4.read_bytes() == b"alt"


def test_transfer_mp4_reports_missing_source(tmp_path):
    plan = _plan(tmp_path)

    with pytest.raises(Mp4TransferError) as error:
        _transfer_mp4_to_target(plan, _config(tmp_path))

    assert "Quell-MP4" in error.value.user_message
    assert str(plan.source_mp4) in error.value.admin_hint


def test_transfer_mp4_reports_unwritable_target_folder(monkeypatch, tmp_path):
    plan = _plan(tmp_path)
    plan.source_mp4.write_bytes(b"video")

    def fail_write_test(_target_folder: Path) -> None:
        raise Mp4TransferError("Der Zielordner ist nicht beschreibbar.", "Schreibtest fehlgeschlagen")

    monkeypatch.setattr("predigt_uploader.cli._check_target_folder_writable", fail_write_test)

    with pytest.raises(Mp4TransferError) as error:
        _transfer_mp4_to_target(plan, _config(tmp_path))

    assert "nicht beschreibbar" in error.value.user_message


def test_transfer_mp4_reports_permission_error(monkeypatch, tmp_path):
    plan = _plan(tmp_path)
    plan.source_mp4.write_bytes(b"video")

    def fail_copy(_source: Path, _target: Path) -> None:
        raise PermissionError("kein Zugriff")

    monkeypatch.setattr("shutil.copy2", fail_copy)

    with pytest.raises(Mp4TransferError) as error:
        _transfer_mp4_to_target(plan, _config(tmp_path))

    assert "fehlender Berechtigungen" in error.value.user_message
    assert "kein Zugriff" in error.value.admin_hint


def test_print_missing_ffmpeg_message_explains_manual_next_steps(tmp_path, capsys):
    plan = _plan(tmp_path)
    config = _config(tmp_path)

    _print_missing_ffmpeg_message(plan, config)

    output = capsys.readouterr().out
    assert "Die MP3 kann noch nicht erstellt werden" in output
    assert "Es fehlt FFmpeg" in output
    assert "Die MP4 wurde trotzdem vorbereitet" in output
    assert str(plan.target_mp4) in output
    assert "File Converter" in output
    assert plan.target_mp3.name in output
    assert "Admin-Hinweis" in output
    assert config.ffmpeg_path in output


def test_run_wizard_stops_before_mp3_conversion_when_ffmpeg_is_missing(monkeypatch, tmp_path, capsys):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config_path = tmp_path / "config.toml"
    recordings_base = tmp_path / "Aufnahmen"

    def toml_path(path: Path) -> str:
        return str(path).replace("\\", "/")

    config_path.write_text(
        "\n".join(
            [
                "[paths]",
                f'vmix_storage = "{toml_path(tmp_path / "vmix")}"',
                f'recordings_base = "{toml_path(recordings_base)}"',
                f'mp3_base = "{toml_path(tmp_path / "Predigten")}"',
                'ffmpeg_path = "ffmpeg-fehlt-fuer-test"',
            ]
        ),
        encoding="utf-8",
    )
    _inputs(
        monkeypatch,
        [
            str(source),
            "2026-05-24",
            "Heiligkeit",
            "Jesaja 6,1-3",
            "Eduard Wiebe",
            "n",
            "j",
        ],
    )
    monkeypatch.setattr("predigt_uploader.cli.ffmpeg_available", lambda _config: False)

    def fail_conversion(*_args, **_kwargs) -> None:
        raise AssertionError("convert_mp4_to_mp3 darf ohne FFmpeg nicht aufgerufen werden")

    monkeypatch.setattr("predigt_uploader.cli.convert_mp4_to_mp3", fail_conversion)

    result = run_wizard(type("Args", (), {"config": str(config_path)})())

    target_mp4 = (
        recordings_base
        / "2026"
        / "2026-05-24"
        / "Predigt (Heiligkeit_Jesaja 6,1-3)_Eduard Wiebe.mp4"
    )
    assert result == 3
    assert source.exists()
    assert target_mp4.exists()
    output = capsys.readouterr().out
    assert "Die MP4 wurde trotzdem vorbereitet" in output
    assert "Admin-Hinweis" in output
    assert "Traceback" not in output


def test_validate_created_mp3_accepts_non_empty_file(tmp_path):
    mp3 = tmp_path / "predigt.mp3"
    mp3.write_bytes(b"audio")

    _validate_created_mp3(mp3)


def test_validate_created_mp3_reports_missing_file(tmp_path):
    mp3 = tmp_path / "fehlt.mp3"

    with pytest.raises(Mp3ResultError) as error:
        _validate_created_mp3(mp3)

    assert "nicht gefunden" in error.value.user_message
    assert str(mp3) in error.value.admin_hint


def test_validate_created_mp3_reports_empty_file(tmp_path):
    mp3 = tmp_path / "leer.mp3"
    mp3.write_bytes(b"")

    with pytest.raises(Mp3ResultError) as error:
        _validate_created_mp3(mp3)

    assert "leer" in error.value.user_message
    assert "0 Bytes" in error.value.admin_hint


def test_run_wizard_reports_conversion_failure_without_traceback(monkeypatch, tmp_path, capsys):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config_path = tmp_path / "config.toml"
    recordings_base = tmp_path / "Aufnahmen"

    def toml_path(path: Path) -> str:
        return str(path).replace("\\", "/")

    config_path.write_text(
        "\n".join(
            [
                "[paths]",
                f'vmix_storage = "{toml_path(tmp_path / "vmix")}"',
                f'recordings_base = "{toml_path(recordings_base)}"',
                f'mp3_base = "{toml_path(tmp_path / "Predigten")}"',
                'ffmpeg_path = "ffmpeg-test"',
            ]
        ),
        encoding="utf-8",
    )
    _inputs(
        monkeypatch,
        [
            str(source),
            "2026-05-24",
            "Heiligkeit",
            "Jesaja 6,1-3",
            "Eduard Wiebe",
            "n",
            "j",
        ],
    )
    monkeypatch.setattr("predigt_uploader.cli.ffmpeg_available", lambda _config: True)

    def fail_conversion(*_args, **_kwargs) -> None:
        raise Mp3ConversionError("FFmpeg Exit-Code: 1. stderr: Datei ist gesperrt.")

    monkeypatch.setattr("predigt_uploader.cli.convert_mp4_to_mp3", fail_conversion)

    result = run_wizard(type("Args", (), {"config": str(config_path)})())

    target_mp4 = (
        recordings_base
        / "2026"
        / "2026-05-24"
        / "Predigt (Heiligkeit_Jesaja 6,1-3)_Eduard Wiebe.mp4"
    )
    assert result == 3
    assert target_mp4.exists()
    output = capsys.readouterr().out
    assert "Die MP3 konnte nicht erstellt werden" in output
    assert str(target_mp4) in output
    assert "File Converter" in output
    assert "Admin-Hinweis" in output
    assert "Exit-Code: 1" in output
    assert "Traceback" not in output


def test_run_wizard_reports_empty_mp3_after_conversion(monkeypatch, tmp_path, capsys):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config_path = tmp_path / "config.toml"
    recordings_base = tmp_path / "Aufnahmen"

    def toml_path(path: Path) -> str:
        return str(path).replace("\\", "/")

    config_path.write_text(
        "\n".join(
            [
                "[paths]",
                f'vmix_storage = "{toml_path(tmp_path / "vmix")}"',
                f'recordings_base = "{toml_path(recordings_base)}"',
                f'mp3_base = "{toml_path(tmp_path / "Predigten")}"',
                'ffmpeg_path = "ffmpeg-test"',
            ]
        ),
        encoding="utf-8",
    )
    _inputs(
        monkeypatch,
        [
            str(source),
            "2026-05-24",
            "Heiligkeit",
            "Jesaja 6,1-3",
            "Eduard Wiebe",
            "n",
            "j",
        ],
    )
    monkeypatch.setattr("predigt_uploader.cli.ffmpeg_available", lambda _config: True)

    def create_empty_mp3(_source_mp4: Path, target_mp3: Path, _config) -> None:
        target_mp3.write_bytes(b"")

    monkeypatch.setattr("predigt_uploader.cli.convert_mp4_to_mp3", create_empty_mp3)

    result = run_wizard(type("Args", (), {"config": str(config_path)})())

    assert result == 3
    output = capsys.readouterr().out
    assert "Die MP3 wurde erstellt, ist aber leer" in output
    assert "0 Bytes" in output
    assert "Traceback" not in output
