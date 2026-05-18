from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from predigt_uploader.cli import (
    MP4_TRANSFER_COPY,
    MP4_TRANSFER_KEEP,
    MP4_TRANSFER_OVERWRITE,
    Mp3ResultError,
    LosslessCutStartError,
    Mp4TransferError,
    SummaryWriteError,
    _ask_sermon_date,
    _choose_exported_mp4,
    _detect_recording_date_from_filename,
    _find_new_mp4_exports,
    _ask_yes_no,
    _ask_mp4_path,
    _ask_required,
    _losslesscut_command,
    _ask_losslesscut_exe_path,
    _newest_mp4_in_folder,
    _open_losslesscut,
    _try_start_losslesscut,
    _handle_existing_target_mp4,
    _print_local_workflow_success,
    _print_missing_ffmpeg_message,
    _print_mp4_action_preview,
    _select_source_mp4,
    _select_recordings_base,
    _select_target_folder,
    _transfer_mp4_to_target,
    _validate_created_mp3,
    _validate_local_workflow_result,
    run_wizard,
)
from predigt_uploader.mp3 import Mp3ConversionError
from predigt_uploader.models import AppConfig, ProcessingPlan, SermonInfo
from predigt_uploader.report import build_summary_text
from predigt_uploader.run_log import WorkflowLog


@pytest.fixture(autouse=True)
def _isolate_working_directory(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)


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
    assert "Pfad wurde nicht gefunden" in output
    assert "Das ist ein Ordner" in output
    assert "Erwartet wird: .mp4" in output


def test_newest_mp4_in_folder_returns_latest_mp4(tmp_path):
    older = tmp_path / "alt.mp4"
    newer = tmp_path / "neu.mp4"
    note = tmp_path / "notiz.txt"
    older.write_bytes(b"alt")
    newer.write_bytes(b"neu")
    note.write_text("x", encoding="utf-8")
    old_time = datetime.now().timestamp() - 100
    new_time = datetime.now().timestamp()
    older.touch()
    newer.touch()
    import os

    os.utime(older, (old_time, old_time))
    os.utime(newer, (new_time, new_time))

    assert _newest_mp4_in_folder(tmp_path) == newer


def test_losslesscut_command_uses_path_or_app_alias(tmp_path):
    config = _config(tmp_path)

    assert _losslesscut_command(config) == "LosslessCut"
    assert _losslesscut_command(AppConfig(tmp_path / "vmix", tmp_path / "out", tmp_path / "mp3", losslesscut_path="C:/Tools/LosslessCut.exe")) == "C:/Tools/LosslessCut.exe"


def test_ask_losslesscut_exe_path_validates_file(monkeypatch, tmp_path, capsys):
    folder = tmp_path / "LosslessCut"
    folder.mkdir()
    wrong = tmp_path / "notiz.txt"
    wrong.write_text("x", encoding="utf-8")
    exe = tmp_path / "LosslessCut.exe"
    exe.write_bytes(b"exe")
    _inputs(monkeypatch, [str(tmp_path / "fehlt.exe"), str(folder), str(wrong), f'"{exe}"'])

    assert _ask_losslesscut_exe_path() == exe

    output = capsys.readouterr().out
    assert "nicht gefunden" in output
    assert "Das ist ein Ordner" in output
    assert "Erwartet wird: .exe" in output


def test_open_losslesscut_starts_external_program(monkeypatch, tmp_path):
    raw = tmp_path / "roh.mp4"
    raw.write_bytes(b"video")
    calls = []

    def fake_popen(args):
        calls.append(args)

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    _open_losslesscut(raw, _config(tmp_path))

    assert calls == [["LosslessCut", str(raw)]]


def test_open_losslesscut_reports_start_error(monkeypatch, tmp_path):
    raw = tmp_path / "roh.mp4"
    raw.write_bytes(b"video")

    def fail_popen(_args):
        raise FileNotFoundError("fehlt")

    monkeypatch.setattr("subprocess.Popen", fail_popen)

    with pytest.raises(LosslessCutStartError) as error:
        _open_losslesscut(raw, _config(tmp_path))

    assert "konnte nicht gestartet" in error.value.user_message
    assert "LosslessCut" in error.value.admin_hint


def test_find_new_mp4_exports_only_returns_files_since_start(tmp_path):
    before = tmp_path / "vorher.mp4"
    after = tmp_path / "nachher.mp4"
    before.write_bytes(b"alt")
    after.write_bytes(b"neu")
    import os

    start = datetime.now()
    before_time = (start - timedelta(seconds=10)).timestamp()
    after_time = (start + timedelta(seconds=10)).timestamp()
    os.utime(before, (before_time, before_time))
    os.utime(after, (after_time, after_time))

    assert _find_new_mp4_exports((tmp_path,), start) == (after,)


def test_choose_exported_mp4_requires_choice_when_multiple_candidates(monkeypatch, tmp_path):
    first = tmp_path / "chor.mp4"
    second = tmp_path / "predigt.mp4"
    first.write_bytes(b"chor")
    second.write_bytes(b"predigt")
    _inputs(monkeypatch, ["2"])

    assert _choose_exported_mp4((first, second)) == second


def test_select_source_mp4_can_keep_existing_cut_file(monkeypatch, tmp_path):
    source = tmp_path / "schnitt.mp4"
    source.write_bytes(b"video")
    _inputs(monkeypatch, ["", str(source)])
    log = WorkflowLog.start(config_path=None, base_dir=tmp_path)

    assert _select_source_mp4(_config(tmp_path), log) == source


def test_select_source_mp4_opens_losslesscut_and_uses_export(monkeypatch, tmp_path, capsys):
    raw = tmp_path / "vmix" / "roh.mp4"
    raw.parent.mkdir()
    raw.write_bytes(b"raw")
    exported = tmp_path / "vmix" / "export-predigt.mp4"
    exported.write_bytes(b"export")
    log = WorkflowLog.start(config_path=None, base_dir=tmp_path)
    config = _config(tmp_path)
    calls = []

    monkeypatch.setattr("predigt_uploader.cli._newest_mp4_in_folder", lambda _folder: raw)
    monkeypatch.setattr("predigt_uploader.cli._open_losslesscut", lambda source, _config: calls.append(source))
    monkeypatch.setattr("predigt_uploader.cli._find_new_mp4_exports", lambda _folders, _since: (exported,))
    _inputs(monkeypatch, ["nein", "", "", ""])

    selected = _select_source_mp4(config, log)

    assert selected == exported
    assert calls == [raw]
    output = capsys.readouterr().out
    assert "Bitte jetzt in LosslessCut schneiden" in output
    assert "Chorlieder" in output


def test_try_start_losslesscut_accepts_manual_path_after_auto_failure(monkeypatch, tmp_path, capsys):
    raw = tmp_path / "roh.mp4"
    raw.write_bytes(b"raw")
    manual_exe = tmp_path / "LosslessCut.exe"
    manual_exe.write_bytes(b"exe")
    log = WorkflowLog.start(config_path=None, base_dir=tmp_path)
    calls = []

    def fake_open(source: Path, config: AppConfig) -> None:
        calls.append(config.losslesscut_path or "auto")
        if not config.losslesscut_path:
            raise LosslessCutStartError("LosslessCut konnte nicht gestartet werden.", "nicht gefunden")

    monkeypatch.setattr("predigt_uploader.cli._open_losslesscut", fake_open)
    _inputs(monkeypatch, ["", str(manual_exe)])

    _try_start_losslesscut(raw, _config(tmp_path), log)

    assert calls == ["auto", str(manual_exe)]
    output = capsys.readouterr().out
    assert "Pfad zur LosslessCut.exe" in output
    log_text = log.path.read_text(encoding="utf-8")
    assert "Manueller LosslessCut-Pfad" in log_text
    assert "manuellem Pfad gestartet" in log_text


@pytest.mark.parametrize("answer", ["j", "ja", "J", "JA", "y", "yes", "YES"])
def test_ask_yes_no_accepts_clear_yes_words(monkeypatch, answer):
    _inputs(monkeypatch, [answer])

    assert _ask_yes_no("Fortfahren?", False) is True


@pytest.mark.parametrize("answer", ["n", "nein", "N", "NEIN", "no", "NO"])
def test_ask_yes_no_accepts_clear_no_words(monkeypatch, answer):
    _inputs(monkeypatch, [answer])

    assert _ask_yes_no("Fortfahren?", True) is False


def test_ask_yes_no_uses_documented_default_for_enter(monkeypatch, capsys):
    _inputs(monkeypatch, [""])

    assert _ask_yes_no("Fortfahren?", False) is False

    output = capsys.readouterr().out
    assert "Antwort: j/ja/y/yes = Ja, n/nein/no = Nein, Enter = Nein" in output


def test_ask_yes_no_repeats_after_unclear_input(monkeypatch, capsys):
    _inputs(monkeypatch, ["vielleicht", "yes"])

    assert _ask_yes_no("Fortfahren?", False) is True

    output = capsys.readouterr().out
    assert "Bitte j, ja, y oder yes" in output


def test_select_recordings_base_can_use_suggested_folder(monkeypatch, tmp_path, capsys):
    config = _config(tmp_path)
    _inputs(monkeypatch, ["", ""])

    selected = _select_recordings_base(config)

    assert selected.recordings_base == config.recordings_base
    assert selected.recordings_base.exists()
    output = capsys.readouterr().out
    assert "Ziel-Basisordner" in output
    assert "Drücke Enter" in output
    assert str(config.recordings_base) in output


def test_select_recordings_base_can_use_alternative_folder(monkeypatch, tmp_path):
    alternative = tmp_path / "AndereAufnahmen"
    _inputs(monkeypatch, [str(alternative), ""])

    selected = _select_recordings_base(_config(tmp_path))

    assert selected.recordings_base == alternative
    assert alternative.exists()


def test_select_recordings_base_rejects_invalid_path_before_accepting_alternative(monkeypatch, tmp_path, capsys):
    alternative = tmp_path / "AndereAufnahmen"
    _inputs(monkeypatch, ["ungueltig:name", str(alternative), ""])

    selected = _select_recordings_base(_config(tmp_path))

    assert selected.recordings_base == alternative
    output = capsys.readouterr().out
    assert "Pfad ist nicht gültig" in output


def test_select_recordings_base_retries_after_unwritable_folder(monkeypatch, tmp_path, capsys):
    config = _config(tmp_path)
    alternative = tmp_path / "AndereAufnahmen"

    def fail_once(path: Path) -> bool:
        if path == config.recordings_base:
            raise Mp4TransferError(
                "Der Ziel-Basisordner konnte nicht erstellt oder beschrieben werden.",
                "Schreibtest fehlgeschlagen",
            )
        path.mkdir(parents=True, exist_ok=True)
        return True

    monkeypatch.setattr("predigt_uploader.cli._prepare_recordings_base", fail_once)
    _inputs(monkeypatch, ["", str(alternative)])

    selected = _select_recordings_base(config)

    assert selected.recordings_base == alternative
    output = capsys.readouterr().out
    assert "anderen Ziel-Basisordner" in output
    assert "Admin-Hinweis" in output


def test_select_recordings_base_can_decline_creation_and_choose_other_folder(monkeypatch, tmp_path, capsys):
    config = _config(tmp_path)
    alternative = tmp_path / "AndereAufnahmen"
    _inputs(monkeypatch, ["", "nein", str(alternative), ""])

    selected = _select_recordings_base(config)

    assert selected.recordings_base == alternative
    assert not config.recordings_base.exists()
    assert alternative.exists()
    output = capsys.readouterr().out
    assert "Dieser Ordner existiert noch nicht" in output
    assert "Ordner erstellen?" in output


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


def test_detect_recording_date_from_vmix_filename():
    path = Path("Gottesdienst - 10 Mai 2026 - 09-55-08.mp4")

    assert _detect_recording_date_from_filename(path) == date(2026, 5, 10)


def test_ask_sermon_date_can_use_detected_recording_date(monkeypatch):
    monkeypatch.setattr("predigt_uploader.cli.choose_from_options", lambda _prompt, _options: "recording")

    selected = _ask_sermon_date(Path("Gottesdienst - 10 Mai 2026 - 09-55-08.mp4"))

    assert selected == date(2026, 5, 10)


def test_ask_sermon_date_can_use_today(monkeypatch):
    monkeypatch.setattr("predigt_uploader.cli.choose_from_options", lambda _prompt, _options: "today")

    selected = _ask_sermon_date(Path("Predigt.mp4"))

    assert selected == datetime.now().date()


def test_ask_sermon_date_can_use_manual_date(monkeypatch):
    monkeypatch.setattr("predigt_uploader.cli.choose_from_options", lambda _prompt, _options: "manual")
    _inputs(monkeypatch, ["2026-05-24"])

    selected = _ask_sermon_date(Path("Predigt.mp4"))

    assert selected == date(2026, 5, 24)


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

    selected_plan, transfer_mode = _handle_existing_target_mp4(plan)

    assert selected_plan == plan
    assert transfer_mode == MP4_TRANSFER_KEEP


def test_handle_existing_target_mp4_can_use_new_name(monkeypatch, tmp_path):
    plan = _plan(tmp_path)
    plan.target_mp4.parent.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"vorhanden")
    _inputs(monkeypatch, ["n", "Predigt anderer Name"])

    selected_plan, transfer_mode = _handle_existing_target_mp4(plan)

    assert selected_plan.target_mp4 == plan.target_mp4.with_name("Predigt anderer Name.mp4")
    assert selected_plan.target_mp3 == plan.target_mp4.with_name("Predigt anderer Name.mp3")
    assert transfer_mode == MP4_TRANSFER_COPY


def test_handle_existing_target_mp4_can_overwrite_after_second_confirmation(monkeypatch, tmp_path):
    plan = _plan(tmp_path)
    plan.target_mp4.parent.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"vorhanden")
    _inputs(monkeypatch, ["o", "ja"])

    selected_plan, transfer_mode = _handle_existing_target_mp4(plan)

    assert selected_plan == plan
    assert transfer_mode == MP4_TRANSFER_OVERWRITE


def test_handle_existing_target_mp4_overwrite_can_be_cancelled(monkeypatch, tmp_path):
    plan = _plan(tmp_path)
    plan.target_mp4.parent.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"vorhanden")
    _inputs(monkeypatch, ["o", "nein"])

    assert _handle_existing_target_mp4(plan) is None
    assert plan.target_mp4.read_bytes() == b"vorhanden"


@pytest.mark.parametrize("answer", ["o", "overwrite", "überschreiben", "ueberschreiben"])
def test_handle_existing_target_mp4_accepts_overwrite_text_fallback(monkeypatch, tmp_path, answer):
    plan = _plan(tmp_path)
    plan.target_mp4.parent.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"vorhanden")
    _inputs(monkeypatch, [answer, "ja"])

    selected_plan, transfer_mode = _handle_existing_target_mp4(plan)

    assert selected_plan == plan
    assert transfer_mode == MP4_TRANSFER_OVERWRITE


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


def test_transfer_mp4_can_overwrite_after_confirmation(tmp_path):
    plan = _plan(tmp_path)
    plan.source_mp4.write_bytes(b"neu")
    plan.target_mp4.parent.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"alt")

    _transfer_mp4_to_target(plan, _config(tmp_path), overwrite_existing=True)

    assert plan.target_mp4.read_bytes() == b"neu"


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
            "",
            "",
            "",
            str(source),
            "3",
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
            "",
            "",
            "",
            str(source),
            "3",
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
            "",
            "",
            "",
            str(source),
            "3",
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


def test_build_summary_text_contains_required_fields_and_filenames(tmp_path):
    plan = _plan(tmp_path)

    text = build_summary_text(plan)

    assert "Datum: 24.05.2026" in text
    assert "Typ: Predigt" in text
    assert "Titel: Heiligkeit" in text
    assert "Hauptbibelstelle: Jesaja 6,1-3" in text
    assert "Redner: Eduard Wiebe" in text
    assert "Besonderheit Ordner: -" in text
    assert f"MP4-Dateiname: {plan.target_mp4.name}" in text
    assert f"MP3-Dateiname: {plan.target_mp3.name}" in text
    assert "WordPress-Hinweise" in text


def test_validate_local_workflow_result_requires_non_empty_mp4_and_mp3(tmp_path):
    plan = _plan(tmp_path)
    plan.target_mp4.parent.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"video")
    plan.target_mp3.write_bytes(b"audio")

    _validate_local_workflow_result(plan)


def test_validate_local_workflow_result_reports_empty_mp4(tmp_path):
    plan = _plan(tmp_path)
    plan.target_mp4.parent.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"")
    plan.target_mp3.write_bytes(b"audio")

    with pytest.raises(Mp3ResultError) as error:
        _validate_local_workflow_result(plan)

    assert "lokale Workflow" in error.value.user_message
    assert "0 Bytes" in error.value.admin_hint


def test_print_local_workflow_success_shows_final_paths(tmp_path, capsys):
    plan = _plan(tmp_path)
    summary_path = plan.target_mp4.parent / "predigt-zusammenfassung.txt"

    _print_local_workflow_success(plan, summary_path)

    output = capsys.readouterr().out
    assert "Lokaler Workflow erfolgreich abgeschlossen" in output
    assert str(plan.target_mp4.parent) in output
    assert str(plan.target_mp4) in output
    assert str(plan.target_mp3) in output
    assert str(summary_path) in output


def test_run_wizard_success_writes_summary_and_prints_final_state(monkeypatch, tmp_path, capsys):
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
            "",
            "",
            "",
            str(source),
            "3",
            "2026-05-24",
            "Heiligkeit",
            "Jesaja 6,1-3",
            "Eduard Wiebe",
            "n",
            "j",
        ],
    )
    monkeypatch.setattr("predigt_uploader.cli.ffmpeg_available", lambda _config: True)

    def create_mp3(_source_mp4: Path, target_mp3: Path, _config) -> None:
        target_mp3.write_bytes(b"audio")

    monkeypatch.setattr("predigt_uploader.cli.convert_mp4_to_mp3", create_mp3)

    result = run_wizard(type("Args", (), {"config": str(config_path)})())

    target_folder = recordings_base / "2026" / "2026-05-24"
    target_mp4 = target_folder / "Predigt (Heiligkeit_Jesaja 6,1-3)_Eduard Wiebe.mp4"
    target_mp3 = target_folder / "Predigt (Heiligkeit_Jesaja 6,1-3)_Eduard Wiebe.mp3"
    summary_path = target_folder / "predigt-zusammenfassung.txt"
    info_json_path = target_folder / "predigt-info.json"
    assert result == 0
    assert target_mp4.stat().st_size > 0
    assert target_mp3.stat().st_size > 0
    assert summary_path.exists()
    assert not info_json_path.exists()
    summary = summary_path.read_text(encoding="utf-8")
    assert "MP4-Dateiname: Predigt (Heiligkeit_Jesaja 6,1-3)_Eduard Wiebe.mp4" in summary
    assert "MP3-Dateiname: Predigt (Heiligkeit_Jesaja 6,1-3)_Eduard Wiebe.mp3" in summary
    output = capsys.readouterr().out
    assert "Lokaler Workflow erfolgreich abgeschlossen" in output
    assert str(target_folder) in output
    assert str(target_mp4) in output
    assert str(target_mp3) in output
    assert "Logdatei:" in output
    log_files = list((tmp_path / "logs").glob("predigt-uploader-*.log"))
    assert len(log_files) == 1
    log_text = log_files[0].read_text(encoding="utf-8")
    assert "Startzeit:" in log_text
    assert f"Config: {config_path}" in log_text
    assert f"Quell-MP4: {source}" in log_text
    assert f"Zielordner: {target_folder}" in log_text
    assert f"Finaler MP4-Dateiname: {target_mp4.name}" in log_text
    assert f"Finaler MP3-Dateiname: {target_mp3.name}" in log_text
    assert "Workflow erfolgreich abgeschlossen" in log_text


def test_run_wizard_reports_summary_write_error(monkeypatch, tmp_path, capsys):
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
            "",
            "",
            "",
            str(source),
            "3",
            "2026-05-24",
            "Heiligkeit",
            "Jesaja 6,1-3",
            "Eduard Wiebe",
            "n",
            "j",
        ],
    )
    monkeypatch.setattr("predigt_uploader.cli.ffmpeg_available", lambda _config: True)

    def create_mp3(_source_mp4: Path, target_mp3: Path, _config) -> None:
        target_mp3.write_bytes(b"audio")

    def fail_summary(_plan: ProcessingPlan) -> Path:
        raise SummaryWriteError("Schreibfehler Test")

    monkeypatch.setattr("predigt_uploader.cli.convert_mp4_to_mp3", create_mp3)
    monkeypatch.setattr("predigt_uploader.cli._write_summary_file_safely", fail_summary)

    result = run_wizard(type("Args", (), {"config": str(config_path)})())

    assert result == 4
    output = capsys.readouterr().out
    assert "Zusammenfassung konnte nicht geschrieben werden" in output
    assert "Admin-Hinweis" in output
    assert "Schreibfehler Test" in output
    assert "Lokaler Workflow erfolgreich abgeschlossen" not in output


def test_run_wizard_reports_missing_config_without_traceback(tmp_path, capsys):
    config_path = tmp_path / "fehlt.toml"

    result = run_wizard(type("Args", (), {"config": str(config_path)})())

    assert result == 6
    output = capsys.readouterr().out
    assert "Konfiguration konnte nicht geladen werden" in output
    assert "nicht gefunden" in output
    assert "Admin-Hinweis" in output
    assert str(config_path) in output
    assert "Traceback" not in output
    log_files = list((tmp_path / "logs").glob("predigt-uploader-*.log"))
    assert len(log_files) == 1
    log_text = log_files[0].read_text(encoding="utf-8")
    assert f"Config: {config_path}" in log_text
    assert "Konfiguration konnte nicht geladen werden" in log_text


def test_run_wizard_reports_invalid_config_without_traceback(tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[paths\nrecordings_base = 'x'", encoding="utf-8")

    result = run_wizard(type("Args", (), {"config": str(config_path)})())

    assert result == 6
    output = capsys.readouterr().out
    assert "Konfiguration konnte nicht geladen werden" in output
    assert "ungültig" in output
    assert "Admin-Hinweis" in output
    assert "Traceback" not in output


def test_workflow_log_uses_standardconfig_label(tmp_path):
    log = WorkflowLog.start(config_path=None, base_dir=tmp_path)
    log.finish("Test abgeschlossen.")

    text = log.path.read_text(encoding="utf-8")
    assert "Config: Standardconfig" in text
    assert "Test abgeschlossen" in text


def test_workflow_log_disables_itself_when_writing_fails(monkeypatch, tmp_path):
    log = WorkflowLog(tmp_path / "logs" / "test.log")

    def fail_open(*_args, **_kwargs):
        raise PermissionError("kein Zugriff")

    monkeypatch.setattr(Path, "open", fail_open)

    log.event("Das wird nicht geschrieben.")

    assert log.enabled is False
