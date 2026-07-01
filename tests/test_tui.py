import sys
from datetime import date, datetime
import os

from predigt_uploader import cli
from predigt_uploader.config import ConfigLoadError
from predigt_uploader.folders import resolve_folder, suggest_folder
from predigt_uploader.models import AppConfig, SermonInfo
from predigt_uploader.tui_app import (
    TUI_FILE_CHOICE_LIMIT,
    TUI_PROCESSING_DONE_LABEL,
    TUI_PROCESSING_EXECUTE_LABEL,
    TUI_PROCESSING_RUNNING_LABEL,
    apply_tui_overwrite_confirmation,
    build_tui_execute_button_state,
    build_tui_date_options,
    build_tui_date_options_for_sources,
    build_tui_export_detection_text,
    build_tui_file_choice_lines,
    build_tui_metadata_info,
    build_tui_file_candidates_lines,
    build_tui_mp4_file_rows,
    build_tui_mp4_selection_actions,
    build_tui_mp4_selection_config,
    build_tui_overwrite_confirmed_text,
    build_tui_preparation,
    build_tui_preparation_text,
    build_tui_processing_plan,
    build_tui_processing_ready_text,
    build_tui_processing_review_action_text,
    build_tui_processing_started_status,
    build_tui_processing_success_status,
    build_tui_target_conflict_text,
    build_tui_target_conflict_decision_text,
    build_tui_target_folder_review_text,
    build_tui_info_with_folder_note,
    build_tui_losslesscut_text,
    build_tui_field_labels,
    build_tui_preview_text,
    build_tui_settings_lines,
    build_tui_start_safety_text,
    build_tui_start_status_text,
    build_tui_validation_text,
    default_tui_service_type_for_sources,
    default_tui_service_type_name,
    detect_tui_export_candidates,
    detect_tui_recording_date_from_filename,
    detect_tui_target_conflicts,
    missing_tui_metadata_fields,
    newest_tui_mp4_candidates,
    newest_tui_mp4_candidate,
    load_tui_config,
    snapshot_tui_mp4_files,
    service_type_by_name,
    service_types_for_tui,
    score_tui_export_candidate,
    tui_cut_mp4_folder,
    tui_cut_mp4_folder_for_raw,
    tui_conflict_action_labels,
    tui_export_candidate_folders,
    tui_file_selection_next_screen,
    tui_mp4_action_text,
    tui_processing_finished_action_labels,
    tui_processing_review_back_target,
    tui_service_type_after_date_change,
    tui_source_choice_route,
    tui_start_safety_route,
    validate_tui_metadata,
)


def test_normal_cli_import_does_not_import_textual():
    sys.modules.pop("textual", None)

    assert "textual" not in sys.modules


def test_tui_command_reports_missing_textual(monkeypatch, capsys):
    def fail_import(*_args, **_kwargs):
        raise ImportError("Textual fehlt")

    monkeypatch.setattr("predigt_uploader.tui_app.run_tui", fail_import)

    result = cli.main(["tui"])

    assert result == 7
    assert "Die neue Oberfläche ist nicht installiert" in capsys.readouterr().out


def test_tui_command_reports_config_error(monkeypatch, capsys):
    def fail_config(*_args, **_kwargs):
        raise ConfigLoadError(
            "Die angegebene Konfigurationsdatei wurde nicht gefunden.",
            "Config-Datei existiert nicht: fehlt.toml",
        )

    monkeypatch.setattr("predigt_uploader.tui_app.run_tui", fail_config)

    result = cli.main(["tui"])

    assert result == 6
    output = capsys.readouterr().out
    assert "Die Konfiguration konnte nicht geladen werden." in output
    assert "Die angegebene Konfigurationsdatei wurde nicht gefunden." in output


def test_load_tui_config_uses_normal_config_search(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.toml").write_text(
        """
[paths]
recordings_base = "D:\\\\Aufnahmen"
vmix_storage = "D:\\\\vMixStorage"
""".strip(),
        encoding="utf-8",
    )

    config = load_tui_config()

    assert str(config.recordings_base) == "D:\\Aufnahmen"
    assert str(config.vmix_storage) == "D:\\vMixStorage"


def test_tui_preview_text_shows_mp4_mp3_and_target_folder(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )

    text = build_tui_preview_text(info, config)

    assert "MP4-Dateiname: Predigt (Lehre statt Leere_Johannes 3,16)_Max Muster.mp4" in text
    assert "MP3-Dateiname: Predigt (Lehre statt Leere_Johannes 3,16)_Max Muster.mp3" in text
    assert f"Zielordner: {tmp_path / 'Aufnahmen' / '2026' / '2026-05-24'}" in text


def test_tui_preview_text_uses_folder_note(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="Taufe",
    )

    text = build_tui_preview_text(info, config)

    assert f"Zielordner: {tmp_path / 'Aufnahmen' / '2026' / '2026-05-24 - Taufe'}" in text


def test_tui_preview_keeps_placeholders_for_missing_fields(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="",
        bible_reference="",
        speaker="",
    )

    text = build_tui_preview_text(info, config)

    assert "[Titel]" in text
    assert "[Bibelstelle]" in text
    assert "[Redner]" in text


def test_tui_start_status_shows_experiment_and_configured_folders(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )

    text = build_tui_start_status_text(config)

    assert "Experimentelle Oberfläche" in text
    assert "Produktiver Workflow: normaler Wizard" in text
    assert f"Ziel-Basisordner: {tmp_path / 'Aufnahmen'}" in text
    assert f"Rohaufnahme-Ordner: {tmp_path / 'vmix'}" in text


def test_tui_start_safety_text_warns_before_workflow():
    text = build_tui_start_safety_text()

    assert "Ist die Aufnahme in vMix beendet?" in text
    assert "Ist der Stream in vMix beendet?" in text
    assert "[ ]" not in text
    assert "==" not in text
    assert "Datenvolumen/Kosten" in text
    assert "[!]" in text


def test_tui_start_safety_routes_no_back_to_start():
    assert tui_start_safety_route("cancel") == "start"
    assert tui_start_safety_route(None) == "start"
    assert tui_start_safety_route("confirm") == "source"


def test_tui_file_candidates_show_cut_and_raw_mp4_files(tmp_path):
    cut_folder = tmp_path / "schnitt"
    raw_folder = tmp_path / "vmix"
    cut_folder.mkdir()
    raw_folder.mkdir()
    cut_file = cut_folder / "predigt_geschnitten.mp4"
    raw_file = raw_folder / "Gottesdienst - 10 Mai 2026.mp4"
    cut_file.write_bytes(b"cut")
    raw_file.write_bytes(b"raw")
    config = AppConfig(
        vmix_storage=raw_folder,
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        cut_mp4_folder=cut_folder,
    )

    lines = build_tui_file_candidates_lines(config)

    assert f"Schnitt-/Exportordner: {cut_folder}" in lines
    assert any("predigt_geschnitten.mp4" in line for line in lines)
    assert f"Rohaufnahme-Ordner: {raw_folder}" in lines
    assert any("Gottesdienst - 10 Mai 2026.mp4" in line for line in lines)


def test_tui_file_candidates_explain_missing_cut_folder(tmp_path):
    raw_folder = tmp_path / "vmix"
    raw_folder.mkdir()
    config = AppConfig(
        vmix_storage=raw_folder,
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )

    lines = build_tui_file_candidates_lines(config)

    assert "Schnitt-/Exportordner: noch nicht gemerkt" in lines


def test_tui_file_choice_filters_newest_mp4_files(tmp_path):
    folder = tmp_path / "vmix"
    folder.mkdir()
    older = folder / "Gottesdienst alt.mp4"
    newer = folder / "Gottesdienst neu.mp4"
    other = folder / "Seminar.mp4"
    older.write_bytes(b"older")
    newer.write_bytes(b"newer")
    other.write_bytes(b"other")
    import os

    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))
    os.utime(other, (3, 3))

    candidates = newest_tui_mp4_candidates(folder, search_text="Gottesdienst", limit=5)
    lines = build_tui_file_choice_lines(folder, search_text="Gottesdienst", limit=5)

    assert newer in candidates
    assert older in candidates
    assert other not in candidates
    assert newest_tui_mp4_candidate(folder) == other
    assert any("Gottesdienst neu.mp4" in line for line in lines)


def test_tui_file_choice_default_limit_is_not_ten(tmp_path):
    folder = tmp_path / "vmix"
    folder.mkdir()
    for index in range(15):
        video = folder / f"Gottesdienst {index:02d}.mp4"
        video.write_bytes(b"video")
        os.utime(video, (index + 1, index + 1))

    candidates = newest_tui_mp4_candidates(folder)
    rows = build_tui_mp4_file_rows(folder)

    assert TUI_FILE_CHOICE_LIMIT >= 500
    assert len(candidates) == 15
    assert len(rows) == 15


def test_tui_mp4_selection_config_supports_cut_and_raw_modes(tmp_path):
    cut_folder = tmp_path / "schnitt"
    raw_folder = tmp_path / "vmix"
    config = AppConfig(
        vmix_storage=raw_folder,
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        cut_mp4_folder=cut_folder,
    )

    cut = build_tui_mp4_selection_config(config, mode="cut")
    raw = build_tui_mp4_selection_config(config, mode="raw")

    assert cut.start_folder == cut_folder
    assert raw.start_folder == raw_folder
    assert cut.allow_search is True
    assert raw.allow_manual_input is True
    assert build_tui_mp4_selection_actions(raw) == ("newest", "recent", "search", "manual", "back", "cancel")


def test_tui_source_choice_routes_raw_to_losslesscut_first():
    assert tui_source_choice_route("cut") == "cut-selection"
    assert tui_source_choice_route("raw") == "raw-selection"
    assert tui_file_selection_next_screen(already_cut=True) == "metadata"
    assert tui_file_selection_next_screen(already_cut=False) == "losslesscut"


def test_tui_mp4_file_rows_show_filename_date_and_size(tmp_path):
    folder = tmp_path / "vmix"
    folder.mkdir()
    video = folder / "Gottesdienst neu.mp4"
    video.write_bytes(b"x" * 1024 * 1024)

    rows = build_tui_mp4_file_rows(folder)

    assert len(rows) == 1
    assert rows[0].path == video
    assert rows[0].filename == "Gottesdienst neu.mp4"
    assert rows[0].modified
    assert rows[0].size == "1.0 MB"


def test_tui_cut_folder_prefers_remembered_cut_folder(tmp_path):
    cut_folder = tmp_path / "schnitt"
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        cut_mp4_folder=cut_folder,
    )

    assert tui_cut_mp4_folder(config) == cut_folder


def test_tui_cut_selection_after_raw_prefers_cut_folder_then_raw_parent(tmp_path):
    cut_folder = tmp_path / "schnitt"
    raw_folder = tmp_path / "vmix"
    raw = raw_folder / "roh.mp4"
    config_with_cut = AppConfig(
        vmix_storage=raw_folder,
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        cut_mp4_folder=cut_folder,
    )
    config_without_cut = AppConfig(
        vmix_storage=raw_folder,
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )

    assert tui_cut_mp4_folder_for_raw(config_with_cut, raw) == cut_folder
    assert tui_cut_mp4_folder_for_raw(config_without_cut, raw) == raw_folder
    assert build_tui_mp4_selection_config(config_without_cut, mode="cut", raw_recording=raw).start_folder == raw_folder


def test_tui_losslesscut_text_explains_manual_cut_when_path_missing(tmp_path):
    raw = tmp_path / "vmix" / "roh.mp4"
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        losslesscut_path="",
    )

    text = build_tui_losslesscut_text(raw, config)

    assert "Jetzt wird LosslessCut geoeffnet." in text
    assert "Exportiere die geschnittene Predigt" in text
    assert "automatisch zu erkennen" in text
    assert "bestaetigen" in text
    assert "LosslessCut wurde nicht gefunden" in text
    assert str(raw) in text


def test_tui_export_detection_finds_new_mp4_after_snapshot(tmp_path):
    raw_folder = tmp_path / "vmix"
    raw_folder.mkdir()
    raw = raw_folder / "Gottesdienst roh.mp4"
    raw.write_bytes(b"raw")
    before = snapshot_tui_mp4_files((raw_folder,))
    started_at = datetime.fromtimestamp(1_700_000_100)
    exported = raw_folder / "Gottesdienst roh-00.01.00.000-00.20.00.000.mp4"
    exported.write_bytes(b"cut")
    os.utime(exported, (1_700_000_120, 1_700_000_120))
    after = snapshot_tui_mp4_files((raw_folder,))

    candidates = detect_tui_export_candidates(
        before,
        after,
        raw_recording=raw,
        started_at=started_at,
        preferred_folders=(raw_folder,),
    )

    assert [candidate.path for candidate in candidates] == [exported]
    assert "neu im beobachteten Ordner" in candidates[0].reason
    assert "nach LosslessCut-Start" in candidates[0].reason


def test_tui_export_detection_finds_changed_mp4_after_snapshot(tmp_path):
    folder = tmp_path / "schnitt"
    folder.mkdir()
    raw = folder / "roh.mp4"
    raw.write_bytes(b"raw")
    exported = folder / "roh_export.mp4"
    exported.write_bytes(b"old")
    os.utime(exported, (1_700_000_050, 1_700_000_050))
    before = snapshot_tui_mp4_files((folder,))
    exported.write_bytes(b"new-cut")
    os.utime(exported, (1_700_000_120, 1_700_000_120))

    candidates = detect_tui_export_candidates(
        before,
        snapshot_tui_mp4_files((folder,)),
        raw_recording=raw,
        started_at=datetime.fromtimestamp(1_700_000_100),
        preferred_folders=(folder,),
    )

    assert candidates[0].path == exported
    assert "seit Schnittschritt geaendert" in candidates[0].reason


def test_tui_export_detection_excludes_raw_recording(tmp_path):
    folder = tmp_path / "vmix"
    folder.mkdir()
    raw = folder / "roh.mp4"
    raw.write_bytes(b"raw")
    before: tuple = ()
    os.utime(raw, (1_700_000_120, 1_700_000_120))

    candidates = detect_tui_export_candidates(
        before,
        snapshot_tui_mp4_files((folder,)),
        raw_recording=raw,
        started_at=datetime.fromtimestamp(1_700_000_100),
        preferred_folders=(folder,),
    )

    assert candidates == ()


def test_tui_export_detection_sorts_newer_and_matching_candidates_higher(tmp_path):
    folder = tmp_path / "vmix"
    other_folder = tmp_path / "other"
    folder.mkdir()
    other_folder.mkdir()
    raw = folder / "Gottesdienst roh.mp4"
    raw.write_bytes(b"raw")
    older = other_folder / "fremd.mp4"
    matching = folder / "Gottesdienst roh export.mp4"
    older.write_bytes(b"old")
    matching.write_bytes(b"cut")
    os.utime(older, (1_700_000_080, 1_700_000_080))
    os.utime(matching, (1_700_000_120, 1_700_000_120))

    candidates = detect_tui_export_candidates(
        (),
        snapshot_tui_mp4_files((folder, other_folder)),
        raw_recording=raw,
        started_at=datetime.fromtimestamp(1_700_000_100),
        preferred_folders=(folder,),
    )

    assert candidates[0].path == matching
    assert candidates[0].score > candidates[1].score


def test_tui_export_detection_text_offers_manual_selection_when_empty():
    text = build_tui_export_detection_text(())

    assert "keine neue oder geaenderte MP4-Datei erkannt" in text
    assert "manuell" in text


def test_tui_field_labels_mark_unneeded_and_optional_fields(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )

    bibelstunde_labels = build_tui_field_labels(service_type_by_name(config, "Bibelstunde"))
    lobpreis_labels = build_tui_field_labels(service_type_by_name(config, "Lobpreis"))

    assert bibelstunde_labels["title"] == "Titel / Themenreihe (optional)"
    assert bibelstunde_labels["bible"] == "Hauptbibelstelle"
    assert bibelstunde_labels["speaker"] == "Redner / Leitung"
    assert lobpreis_labels["speaker"] == "Leitung (optional)"


def test_tui_field_labels_mark_missing_required_fields(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )

    labels = build_tui_field_labels(
        service_type_by_name(config, "Predigt"),
        missing_fields=("title", "bible", "speaker"),
    )

    assert labels["title"] == "Titel - FEHLT"
    assert labels["bible"] == "Hauptbibelstelle - FEHLT"
    assert labels["speaker"] == "Redner / Leitung - FEHLT"


def test_tui_service_type_defaults_follow_weekday(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )

    assert default_tui_service_type_name(config, date(2026, 5, 24)) == "Predigt"
    assert default_tui_service_type_name(config, date(2026, 5, 20)) == "Bibelstunde"
    assert default_tui_service_type_name(config, date(2026, 5, 22)) == "Gebetsstunde"
    assert default_tui_service_type_name(config, date(2026, 5, 21)) == "Predigt"


def test_tui_service_type_default_uses_source_filename_date_before_today(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    source = tmp_path / "Gottesdienst - 20 Mai 2026 - 19-30-00.mp4"

    assert (
        default_tui_service_type_for_sources(config, source, None, today=date(2026, 5, 22))
        == "Bibelstunde"
    )


def test_tui_service_type_default_uses_raw_filename_before_cut_source(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    raw = tmp_path / "vMix - 20 Mai 2026 - 19-30-00.mp4"
    source = tmp_path / "exportierte_predigt.mp4"

    assert (
        default_tui_service_type_for_sources(config, source, raw, today=date(2026, 5, 22))
        == "Bibelstunde"
    )


def test_tui_service_type_default_uses_raw_friday_and_sunday(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    friday_raw = tmp_path / "vMix - 22 Mai 2026 - 19-30-00.mp4"
    sunday_raw = tmp_path / "vMix - 24 Mai 2026 - 10-00-00.mp4"

    assert default_tui_service_type_for_sources(config, None, friday_raw, today=date(2026, 5, 20)) == "Gebetsstunde"
    assert default_tui_service_type_for_sources(config, None, sunday_raw, today=date(2026, 5, 22)) == "Predigt"


def test_tui_service_type_default_uses_today_when_no_file_date_is_available(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    source = tmp_path / "exportierte_predigt.mp4"

    options = build_tui_date_options_for_sources(source, None, today=date(2026, 5, 22))

    assert [option.kind for option in options] == ["today", "custom"]
    assert default_tui_service_type_for_sources(config, source, None, today=date(2026, 5, 22)) == "Gebetsstunde"


def test_tui_service_type_manual_change_is_not_overwritten_by_date_change(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )

    next_service = tui_service_type_after_date_change(
        config,
        date(2026, 5, 20),
        "Predigt",
        service_type_manually_changed=True,
    )

    assert next_service == "Predigt"


def test_tui_service_type_updates_after_date_change_until_manual_change(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )

    next_service = tui_service_type_after_date_change(
        config,
        date(2026, 5, 20),
        "Predigt",
        service_type_manually_changed=False,
    )

    assert next_service == "Bibelstunde"


def test_tui_service_types_include_configured_custom_types(tmp_path):
    from predigt_uploader.models import ServiceTypeConfig

    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        custom_service_types=(
            ServiceTypeConfig("Andacht", True, True, False, "Andacht ({title}_{bible_reference}){extension}"),
        ),
    )

    names = [service_type.name for service_type in service_types_for_tui(config)]

    assert "Predigt" in names
    assert "Andacht" in names
    assert service_type_by_name(config, "andacht").name == "Andacht"


def test_tui_metadata_info_builds_sermon_info_with_folder_note(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )

    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="Taufe",
    )

    assert info.sermon_date == date(2026, 5, 24)
    assert info.sermon_type == "Predigt"
    assert info.folder_note == "Taufe"


def test_tui_date_options_use_recording_date_from_filename(tmp_path):
    source = tmp_path / "Gottesdienst - 10 Mai 2026 - 09-55-08.mp4"
    source.write_bytes(b"video")

    options = build_tui_date_options(source, today=date(2026, 5, 26))

    assert detect_tui_recording_date_from_filename(source) == date(2026, 5, 10)
    assert [option.kind for option in options] == ["today", "filename", "custom"]
    assert options[1].value == date(2026, 5, 10)


def test_tui_target_folder_review_shows_missing_suggested_folder(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = SermonInfo(
        sermon_date=date(2026, 4, 29),
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )

    resolution = resolve_folder(config, info)
    text = build_tui_target_folder_review_text(resolution)

    assert resolution.status == "missing"
    assert resolution.suggested_folder == tmp_path / "Aufnahmen" / "2026" / "2026-04-29"
    assert "noch keinen Ordner" in text
    assert str(resolution.suggested_folder) in text


def test_tui_target_folder_review_detects_single_existing_folder(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    existing = tmp_path / "Aufnahmen" / "2026" / "2026-04-29"
    existing.mkdir(parents=True)
    info = SermonInfo(
        sermon_date=date(2026, 4, 29),
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )

    resolution = resolve_folder(config, info)
    text = build_tui_target_folder_review_text(resolution)

    assert resolution.status == "single_existing"
    assert resolution.candidates == (existing,)
    assert "bereits diesen Ordner" in text
    assert str(existing) in text


def test_tui_target_folder_review_detects_multiple_existing_folders(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    first = tmp_path / "Aufnahmen" / "2026" / "2026-04-29"
    second = tmp_path / "Aufnahmen" / "2026" / "2026-04-29 - Test"
    first.mkdir(parents=True)
    second.mkdir()
    info = SermonInfo(
        sermon_date=date(2026, 4, 29),
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )

    resolution = resolve_folder(config, info)
    text = build_tui_target_folder_review_text(resolution)

    assert resolution.status == "multiple_existing"
    assert resolution.candidates == (first, second)
    assert "mehrere Ordner" in text


def test_tui_folder_note_builds_new_target_folder_name(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = SermonInfo(
        sermon_date=date(2026, 4, 29),
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )

    changed = build_tui_info_with_folder_note(info, "Test")

    assert suggest_folder(config, changed) == tmp_path / "Aufnahmen" / "2026" / "2026-04-29 - Test"


def test_tui_preparation_uses_shared_filename_folder_and_summary_helpers(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="Taufe",
    )

    preparation = build_tui_preparation(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
    )
    text = build_tui_preparation_text(preparation)

    assert preparation.target_folder == tmp_path / "Aufnahmen" / "2026" / "2026-05-24 - Taufe"
    assert preparation.target_mp4.name == "Predigt (Lehre statt Leere_Johannes 3,16)_Max Muster.mp4"
    assert preparation.target_mp3.name == "Predigt (Lehre statt Leere_Johannes 3,16)_Max Muster.mp3"
    assert preparation.summary_path == preparation.target_folder / "predigt-zusammenfassung.txt"
    assert preparation.plan is not None
    assert "Zusammenfassung:" in text


def test_tui_processing_plan_builds_final_review_data(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )

    plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
    )

    assert plan.source_mp4 == source
    assert plan.target_mp4.name == "Predigt (Lehre statt Leere_Johannes 3,16)_Max Muster.mp4"
    assert plan.summary_path == plan.target_folder / "predigt-zusammenfassung.txt"
    assert plan.warnings == ()


def test_tui_processing_plan_uses_target_folder_override(tmp_path):
    source = tmp_path / "quelle.mp4"
    selected_folder = tmp_path / "Aufnahmen" / "2026" / "2026-05-24 - Test"
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )

    plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
        target_folder_override=selected_folder,
    )

    assert plan.target_folder == selected_folder
    assert plan.target_mp4.parent == selected_folder
    assert plan.target_mp3.parent == selected_folder
    assert plan.summary_path == selected_folder / "predigt-zusammenfassung.txt"


def test_tui_target_conflicts_detect_existing_mp4_mp3_and_summary(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
    )
    plan.target_folder.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"alte mp4")
    plan.target_mp3.write_bytes(b"alte mp3")
    plan.summary_path.write_text("alt", encoding="utf-8")

    conflicts = detect_tui_target_conflicts(plan)
    text = build_tui_target_conflict_text(conflicts)

    assert [(conflict.kind, conflict.severity) for conflict in conflicts] == [
        ("mp4", "danger"),
        ("mp3", "danger"),
        ("summary", "warning"),
    ]
    assert "Vorhandene Zieldateien:" in text
    assert "MP4:" in text
    assert "MP3:" in text
    assert "Zusammenfassung:" in text


def test_tui_target_conflict_decision_text_is_clear_for_users(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
    )
    plan.target_folder.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"alte mp4")

    text = build_tui_target_conflict_decision_text(detect_tui_target_conflicts(plan))

    assert "STOPP" in text
    assert "Es wird nichts ueberschrieben, bis du bewusst entscheidest." in text
    assert "Was moechtest du tun?" in text
    assert "Vorhandene Zieldateien:" in text
    assert "MP4:" in text
    assert "Waehle rechts 'Vorhandene Dateien ersetzen'" in text


def test_tui_execute_button_is_blocked_when_target_conflicts_exist(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
    )
    plan.target_folder.mkdir(parents=True)
    plan.target_mp3.write_bytes(b"alte mp3")

    label, disabled = build_tui_execute_button_state(plan, overwrite_confirmed=False)

    assert disabled is True
    assert label == "Erst entscheiden: ersetzen oder zurückgehen"


def test_tui_overwrite_confirmation_enables_execute_and_sets_plan_flags(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
    )
    plan.target_folder.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"alte mp4")

    confirmed_plan = apply_tui_overwrite_confirmation(plan)
    label, disabled = build_tui_execute_button_state(confirmed_plan, overwrite_confirmed=True)

    assert confirmed_plan.mp4_action == "overwrite"
    assert confirmed_plan.overwrite_existing_outputs is True
    assert disabled is False
    assert label == "Vorhandene Dateien ersetzen und finale Dateien erstellen"


def test_tui_overwrite_confirmed_text_replaces_stop_message():
    text = build_tui_overwrite_confirmed_text()

    assert "Ersetzen bestaetigt." in text
    assert "Beim naechsten Klick werden die vorhandenen Ziel-Dateien ersetzt." in text
    assert "STOPP" not in text


def test_tui_conflict_actions_are_visible_user_buttons():
    assert tui_conflict_action_labels() == (
        "Zurueck: anderen Zielordner waehlen",
        "Vorhandene Dateien ersetzen",
        "Abbrechen",
    )


def test_tui_execute_button_uses_normal_label_without_conflicts(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
    )

    label, disabled = build_tui_execute_button_state(plan, overwrite_confirmed=False)

    assert disabled is False
    assert label == TUI_PROCESSING_EXECUTE_LABEL


def test_tui_processing_ready_text_explains_next_click_without_conflicts(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
    )

    text = build_tui_processing_ready_text(plan)

    assert "Beim Klick werden die MP4/MP3/Zusammenfassung im Zielordner erstellt" in text
    assert "Rohaufnahme" in text


def test_tui_processing_review_back_returns_to_target_folder_review():
    assert tui_processing_review_back_target() == "target-folder-review"


def test_tui_raw_flow_processing_plan_keeps_cut_mp4_and_raw_recording_separate(tmp_path):
    raw = tmp_path / "vmix" / "roh.mp4"
    cut = tmp_path / "schnitt" / "predigt_geschnitten.mp4"
    raw.parent.mkdir()
    cut.parent.mkdir()
    raw.write_bytes(b"raw")
    cut.write_bytes(b"cut")
    config = AppConfig(
        vmix_storage=raw.parent,
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )

    plan = build_tui_processing_plan(
        config=config,
        source_mp4=cut,
        raw_recording=raw,
        already_cut=False,
        raw_action="copy",
        info=info,
    )
    preparation = build_tui_preparation(
        config=config,
        source_mp4=cut,
        raw_recording=raw,
        already_cut=False,
        info=info,
    )
    text = build_tui_preparation_text(preparation)

    assert plan.source_mp4 == cut
    assert plan.raw_recording == raw
    assert plan.raw_action == "copy"
    assert plan.processing_plan.source_mp4 == cut
    assert plan.source_mp4 != plan.raw_recording
    assert f"Quell-MP4 / geschnittene MP4: {cut}" in text
    assert f"Rohaufnahme: {raw}" in text


def test_tui_processing_review_action_text_warns_when_raw_action_moves(tmp_path):
    raw = tmp_path / "vmix" / "roh.mp4"
    cut = tmp_path / "schnitt" / "predigt_geschnitten.mp4"
    raw.parent.mkdir()
    cut.parent.mkdir()
    raw.write_bytes(b"raw")
    cut.write_bytes(b"cut")
    config = AppConfig(
        vmix_storage=raw.parent,
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        raw_archive_mode="move",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )

    plan = build_tui_processing_plan(
        config=config,
        source_mp4=cut,
        raw_recording=raw,
        already_cut=False,
        raw_action="move",
        info=info,
    )
    text = build_tui_processing_review_action_text(plan)

    assert plan.raw_action == "move"
    assert "Beim Klick passiert Folgendes:" in text
    assert "geschnittene MP4 wird in den Zielordner kopiert" in text
    assert "Rohaufnahme wird aus dem Quellordner entfernt" in text


def test_tui_mp4_action_text_matches_processing_plan_action(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )

    copy_plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
        mp4_action="copy",
    )
    move_plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
        mp4_action="move",
    )
    overwrite_plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
        mp4_action="overwrite",
    )
    keep_plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
        mp4_action="keep",
    )

    assert tui_mp4_action_text(copy_plan) == "geschnittene MP4 wird in den Zielordner kopiert"
    assert tui_mp4_action_text(move_plan) == "geschnittene MP4 wird in den Zielordner verschoben"
    assert tui_mp4_action_text(overwrite_plan) == "vorhandene Ziel-MP4 wird ersetzt"
    assert tui_mp4_action_text(keep_plan) == "vorhandene Ziel-MP4 wird verwendet"


def test_tui_processing_plan_warns_when_raw_and_source_are_identical(tmp_path):
    raw = tmp_path / "vmix" / "roh.mp4"
    raw.parent.mkdir()
    raw.write_bytes(b"raw")
    config = AppConfig(
        vmix_storage=raw.parent,
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )

    plan = build_tui_processing_plan(
        config=config,
        source_mp4=raw,
        raw_recording=raw,
        already_cut=False,
        info=info,
    )

    assert any("Rohaufnahme und finale MP4 sind identisch" in warning for warning in plan.warnings)


def test_tui_processing_button_feedback_status_is_visible(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
    )

    started = build_tui_processing_started_status()
    success = build_tui_processing_success_status(plan)

    assert started != "Noch nicht gestartet."
    assert "Verarbeitung gestartet" in started
    assert TUI_PROCESSING_RUNNING_LABEL == "Verarbeitung laeuft..."
    assert TUI_PROCESSING_DONE_LABEL == "Fertig vorbereitet"
    assert "Fertig. Die Dateien wurden vorbereitet." in success
    assert "Der Zielordner wurde geoeffnet." in success
    assert "Bitte jetzt kontrollieren:" in success
    assert "MP4 im Zielordner vorhanden?" in success
    assert "MP3 im Zielordner vorhanden?" in success
    assert "predigt-zusammenfassung.txt vorhanden?" in success
    assert "Danach manuell weiter:" in success
    assert "MP4 zu Vimeo hochladen" in success
    assert "MP3 in WordPress hochladen" in success
    assert "Angaben aus predigt-zusammenfassung.txt in WordPress uebernehmen" in success
    assert "Vimeo-Embed-Code spaeter in WordPress ergaenzen" in success
    assert "STOPP" not in success
    assert f"Zielordner: {plan.target_folder}" in success
    assert f"Finale MP4: {plan.target_mp4}" in success
    assert f"Finale MP3: {plan.target_mp3}" in success
    assert f"Zusammenfassung: {plan.summary_path}" in success
    assert "Rohaufnahme-Aktion: keine Rohaufnahme" in success


def test_tui_processing_success_status_mentions_replaced_files_after_overwrite(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    plan = apply_tui_overwrite_confirmation(
        build_tui_processing_plan(
            config=config,
            source_mp4=source,
            raw_recording=None,
            already_cut=True,
            info=info,
        )
    )

    success = build_tui_processing_success_status(plan)

    assert "Vorhandene Ziel-Dateien wurden ersetzt." in success
    assert "STOPP" not in success


def test_tui_processing_finished_actions_are_available_after_success():
    assert tui_processing_finished_action_labels() == (
        "Zielordner erneut oeffnen",
        "Neue Aufnahme vorbereiten",
        "Beenden",
    )


def test_tui_metadata_validation_requires_only_fields_for_service_type(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    predigt = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="",
        bible_reference="",
        speaker="",
        folder_note="",
    )
    bibelstunde = build_tui_metadata_info(
        config=config,
        date_text="2026-05-20",
        service_type_name="Bibelstunde",
        title="",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    gebetsstunde = build_tui_metadata_info(
        config=config,
        date_text="2026-05-22",
        service_type_name="Gebetsstunde",
        title="Gebet und Dank",
        bible_reference="",
        speaker="",
        folder_note="",
    )

    assert validate_tui_metadata(predigt, config, date_text="2026-05-24") == (
        "Titel fehlt.",
        "Hauptbibelstelle fehlt.",
        "Redner fehlt.",
    )
    assert missing_tui_metadata_fields(predigt, config, date_text="2026-05-24") == ("title", "bible", "speaker")
    assert validate_tui_metadata(bibelstunde, config, date_text="2026-05-20") == ()
    assert missing_tui_metadata_fields(bibelstunde, config, date_text="2026-05-20") == ()
    assert validate_tui_metadata(gebetsstunde, config, date_text="2026-05-22") == ()


def test_tui_metadata_validation_reports_invalid_date(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="24.05.2026",
        service_type_name="Bibelstunde",
        title="",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )

    messages = validate_tui_metadata(info, config, date_text="24.05.2026")

    assert messages == ("Datum bitte im Format YYYY-MM-DD eingeben.",)
    assert missing_tui_metadata_fields(info, config, date_text="24.05.2026") == ("date",)
    assert "Bitte ergaenzen:" in build_tui_validation_text(messages)


def test_tui_settings_lines_show_local_paths_and_workflow_defaults(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        losslesscut_path=str(tmp_path / "LosslessCut.exe"),
        year_folder_template="{year} Video+Audio",
        raw_archive_mode="copy",
    )

    lines = build_tui_settings_lines(config)

    assert f"Ziel-Basisordner: {tmp_path / 'Aufnahmen'}" in lines
    assert f"Rohaufnahme-Ordner: {tmp_path / 'vmix'}" in lines
    assert f"LosslessCut-Pfad: {tmp_path / 'LosslessCut.exe'}" in lines
    assert "Jahresordner-Format: {year} Video+Audio" in lines
    assert "Rohaufnahme-Aufräumen: copy" in lines
