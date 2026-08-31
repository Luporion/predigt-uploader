import asyncio
import sys
import threading
from dataclasses import replace
from datetime import date, datetime
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from predigt_uploader import cli
from predigt_uploader.companion_files import recording_summary_path
import predigt_uploader.tui_app as tui_module
from predigt_uploader.config import ConfigLoadError
from predigt_uploader.folders import resolve_folder, suggest_folder
from predigt_uploader.models import AppConfig, SermonInfo, VimeoConfig
from predigt_uploader.processing import ProcessingExecutionResult, execute_processing_plan
from predigt_uploader.credentials import VimeoCredentialManager
from predigt_uploader.speaker_history import SpeakerHistory
from predigt_uploader.publishing.vimeo import VimeoProgress, VimeoUploadError
from predigt_uploader.tui_app import (
    TUI_FILE_CHOICE_LIMIT,
    TUI_PROCESSING_DONE_LABEL,
    TUI_PROCESSING_EXECUTE_LABEL,
    TUI_PROCESSING_RUNNING_LABEL,
    TUI_BACK_LABEL,
    TUI_GOTTESDIENST_EXPLANATION,
    TUI_TOTAL_WORKFLOW_STEPS,
    apply_tui_backup_existing_confirmation,
    apply_tui_output_suffix,
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
    build_tui_processing_files_text,
    build_tui_processing_raw_action_text,
    build_tui_processing_ready_text,
    build_tui_processing_source_text,
    build_tui_processing_warning_text,
    build_tui_progress_text,
    build_tui_processing_error_status,
    build_tui_processing_review_action_text,
    build_tui_processing_started_status,
    build_tui_processing_success_status,
    build_tui_processing_success_banner,
    build_tui_vimeo_error_text,
    build_tui_vimeo_progress_text,
    build_tui_vimeo_success_text,
    format_tui_vimeo_upload_details,
    tui_processing_warning_class,
    build_tui_target_conflict_text,
    build_tui_target_conflict_decision_text,
    build_tui_target_file_plan_text,
    build_tui_existing_output_rename_text,
    build_tui_target_folder_review_text,
    build_tui_target_folder_action_hint,
    build_tui_new_folder_decision_text,
    build_tui_back_footnote,
    build_tui_info_with_folder_note,
    build_tui_losslesscut_text,
    build_tui_field_labels,
    build_tui_preview_text,
    build_tui_settings_lines,
    build_tui_screen_help,
    build_tui_step_title,
    build_tui_metadata_validation_text,
    build_tui_metadata_scroll_hint_text,
    build_tui_app,
    classify_tui_metadata_fields_by_position,
    tui_metadata_optional_field_keys,
    tui_metadata_required_field_keys,
    tui_metadata_widget_order,
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
    load_or_create_direct_vimeo_state,
    validate_direct_vimeo_mp4,
    snapshot_tui_mp4_files,
    service_type_by_name,
    service_types_for_tui,
    score_tui_export_candidate,
    tui_cut_mp4_folder,
    tui_cut_mp4_folder_for_raw,
    tui_action_requires_confirmation,
    tui_conflict_action_labels,
    tui_export_candidate_folders,
    tui_file_selection_next_screen,
    tui_mp4_action_text,
    tui_metadata_action_labels,
    tui_processing_finished_action_labels,
    tui_processing_review_back_target,
    tui_processing_warning_class,
    tui_target_folder_initial_focus_id,
    tui_target_folder_note_input_visible,
    tui_target_folder_primary_action,
    tui_target_folder_status_class,
    tui_target_folder_status_message,
    tui_new_folder_decision_status_class,
    tui_service_type_display_name,
    tui_service_type_options,
    tui_service_type_after_date_change,
    tui_source_choice_route,
    tui_start_safety_route,
    TuiTargetConflict,
    validate_tui_metadata,
)
from predigt_uploader.workflow_state import (
    StepState,
    VimeoState,
    completed_local_workflow_state,
    load_workflow_state,
    save_workflow_state,
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

    assert "Dieses Tool bereitet Gemeinde-Aufnahmen fuer WordPress/Vimeo vor" in text
    assert "Produktiver Standard bleibt der normale Wizard." in text
    assert "MP4-Dateien ansehen: nur Anzeige/Info im Textual-Prototyp." in text
    assert "Einstellungen: nur Anzeige/Info im Textual-Prototyp." in text
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


def test_tui_start_safety_screen_has_back_button_and_returns_to_main_menu():
    source = (Path(__file__).resolve().parents[1] / "src" / "predigt_uploader" / "tui_app.py").read_text(
        encoding="utf-8"
    )

    assert 'Button(TUI_BACK_LABEL, id="back")' in source
    assert 'if event.button.id == "back":' in source
    assert 'self.app.pop_screen()' in source


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


def test_tui_shows_gottesdienst_but_keeps_predigt_internal(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )

    options = tui_service_type_options(config)
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Gottesdienst",
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )

    assert ("Gottesdienst", "Predigt") in options
    assert ("Predigt", "Predigt") not in options
    assert tui_service_type_display_name("Predigt") == "Gottesdienst"
    assert service_type_by_name(config, "Gottesdienst").name == "Predigt"
    assert service_type_by_name(config, "Predigt").name == "Predigt"
    assert info.sermon_type == "Predigt"
    assert TUI_GOTTESDIENST_EXPLANATION.startswith("Gottesdienst bedeutet:")


def test_tui_workflow_step_titles_and_back_help_are_consistent():
    expected = (
        (1, "Startcheck"),
        (2, "Rohaufnahme auswaehlen"),
        (3, "Rohaufnahme schneiden"),
        (4, "Geschnittene MP4 bestaetigen"),
        (5, "Metadaten erfassen"),
        (6, "Zielordner pruefen"),
        (7, "Lokale Dateien erstellen"),
        (8, "Vimeo veröffentlichen"),
    )

    titles = tuple(build_tui_step_title(step, name) for step, name in expected)
    help_text = build_tui_screen_help("Auswahl treffen.", "Naechster Schritt wird geoeffnet.")

    assert TUI_TOTAL_WORKFLOW_STEPS == 8
    assert titles[0] == "Schritt 1/8: Startcheck"
    assert titles[-1] == "Schritt 8/8: Vimeo veröffentlichen"
    assert all(f"Schritt {step}/8:" in title for (step, _), title in zip(expected, titles))
    assert TUI_BACK_LABEL == "Zurueck"
    assert help_text == "Auswahl treffen."
    assert "Was muss ich hier tun?" not in help_text
    assert "Was passiert beim naechsten Klick?" not in help_text
    assert build_tui_back_footnote() == (
        "Zurueck ist moeglich, solange noch keine finalen Dateien geschrieben wurden."
    )
    assert tui_metadata_action_labels() == ("Zurueck", "Abbrechen", "Zielordner pruefen")


def test_tui_progress_marks_current_completed_and_skipped_steps():
    first = build_tui_progress_text(1)
    metadata = build_tui_progress_text(5)
    already_cut = build_tui_progress_text(5, {3})

    assert first.startswith("Fortschritt:")
    assert "▶1 Start" in first
    assert "[ ]2 Quelle" in first
    assert "✓1 Start" in metadata
    assert "✓4 MP4" in metadata
    assert "▶5 Metadaten" in metadata
    assert "[-]3 Schnitt" in already_cut


def test_tui_only_risky_actions_require_confirmation():
    assert tui_action_requires_confirmation("overwrite") is True
    assert tui_action_requires_confirmation("move_raw_recording") is True
    assert tui_action_requires_confirmation("detected_cut_export") is True
    assert tui_action_requires_confirmation("select_source") is False
    assert tui_action_requires_confirmation("edit_metadata") is False


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
    assert "Status: Kein vorhandener Ordner gefunden." in text
    assert str(resolution.suggested_folder) in text
    assert tui_target_folder_primary_action(resolution) == ("Neuen Zielordner verwenden", "use_suggested")
    assert tui_target_folder_initial_focus_id(resolution) == "use_suggested"
    assert build_tui_target_folder_action_hint(resolution) == "Es wird ein neuer Zielordner erstellt."
    assert tui_target_folder_status_message(resolution) == "Kein vorhandener Ordner gefunden"
    assert tui_target_folder_status_class(resolution) == "status-info"


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
    assert "Status: Vorhandener Tagesordner gefunden." in text
    assert str(existing) in text
    assert tui_target_folder_primary_action(resolution) == (
        "Vorhandenen Ordner verwenden / Dateien dort hinzufuegen",
        "use_existing",
    )
    assert tui_target_folder_initial_focus_id(resolution) == "use_existing"
    assert tui_target_folder_note_input_visible(False) is False
    assert tui_target_folder_note_input_visible(True) is True
    assert tui_target_folder_status_message(resolution) == "Vorhandener Tagesordner gefunden"
    assert tui_target_folder_status_class(resolution) == "status-ok"
    assert "Vorhandene Dateien werden in Schritt 7 separat geprueft." in build_tui_target_folder_action_hint(
        resolution
    )


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
    assert "Status: Mehrere moegliche Ordner gefunden." in text
    assert tui_target_folder_primary_action(resolution) == ("Ausgewaehlten Ordner verwenden", "use_existing")
    assert tui_target_folder_initial_focus_id(resolution) == "use_existing"
    assert tui_target_folder_status_message(resolution) == "Mehrere moegliche Ordner gefunden"
    assert tui_target_folder_status_class(resolution) == "status-warning"
    assert "neuer Ordner mit dem Zusatz" in build_tui_target_folder_action_hint(
        resolution,
        create_with_note=True,
    )


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


def test_tui_new_folder_decision_shows_live_target_and_existing_collision(tmp_path):
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
    target = tmp_path / "Aufnahmen" / "2026" / "2026-04-29 - Test"

    text = build_tui_new_folder_decision_text(config, info, " Test ")

    assert "Neuer Ordner mit Zusatz" in text
    assert f"Neuer Zielordner: {target}" in text
    assert "Der vorhandene Tagesordner bleibt unveraendert." in text
    assert tui_new_folder_decision_status_class(config, info, "Test") == "status-info"

    target.mkdir(parents=True)
    collision_text = build_tui_new_folder_decision_text(config, info, "Test")
    assert "Dieser Zielordner existiert bereits." in collision_text
    assert "Dateikonflikte werden weiterhin in Schritt 7 geprueft." in collision_text
    assert tui_new_folder_decision_status_class(config, info, "Test") == "status-warning"


def test_tui_new_folder_decision_requires_non_empty_note(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = SermonInfo(sermon_date=date(2026, 4, 29), title="", bible_reference="", speaker="")

    assert "Bitte zuerst einen Zusatz eingeben." in build_tui_new_folder_decision_text(config, info, "   ")
    assert tui_new_folder_decision_status_class(config, info, "   ") == "status-warning"


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
    assert preparation.summary_path == recording_summary_path(preparation.target_mp4)
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
    assert plan.summary_path == recording_summary_path(plan.target_mp4)
    assert plan.warnings == ()


def test_tui_processing_review_uses_clear_checklist_sections(tmp_path):
    source = tmp_path / "schnitt.mp4"
    raw = tmp_path / "roh.mp4"
    source.write_bytes(b"video")
    raw.write_bytes(b"raw")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Gottesdienst",
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=raw,
        already_cut=False,
        raw_action="keep",
        info=info,
    )

    source_text = build_tui_processing_source_text(plan)
    files_text = build_tui_processing_files_text(plan)
    raw_text = build_tui_processing_raw_action_text(plan)
    warning_text = build_tui_processing_warning_text(plan, ())

    assert "Was wird verwendet?" in source_text
    assert f"Geschnittene MP4: {source}" in source_text
    assert f"Rohaufnahme: {raw}" in source_text
    assert f"Zielordner: {plan.target_folder}" in source_text
    assert "Welche Dateien werden erstellt?" in files_text
    assert f"Finale MP4: {plan.target_mp4}" in files_text
    assert f"Finale MP3: {plan.target_mp3}" in files_text
    assert f"Zusammenfassung: {plan.summary_path}" in files_text
    assert "Was passiert mit der Rohaufnahme?" in raw_text
    assert "Rohaufnahme liegen lassen" in raw_text
    assert warning_text == "Status / Warnungen\nKeine Konflikte gefunden."


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
    assert plan.summary_path == recording_summary_path(plan.target_mp4)


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
    warning_text = build_tui_processing_warning_text(plan, conflicts)

    assert [(conflict.kind, conflict.severity) for conflict in conflicts] == [
        ("mp4", "danger"),
        ("mp3", "danger"),
        ("summary", "warning"),
    ]
    assert "Vorhandene Zieldateien:" in text
    assert "MP4:" in text
    assert "MP3:" in text
    assert "Zusammenfassung:" in text
    assert "Status / Warnungen" in warning_text
    assert "STOPP" in warning_text
    assert "bewusst entscheidest" in warning_text
    assert tui_processing_warning_class(conflicts) == "status-danger"
    assert tui_processing_warning_class(()) == "status-ok"


@pytest.mark.parametrize(
    ("kind", "attribute"),
    (("mp4", "target_mp4"), ("mp3", "target_mp3"), ("summary", "summary_path")),
)
def test_tui_detects_each_output_conflict_separately(tmp_path, kind, attribute):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(tmp_path / "vmix", tmp_path / "Aufnahmen", tmp_path / "Predigten")
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    plan = build_tui_processing_plan(config=config, source_mp4=source, raw_recording=None, already_cut=True, info=info)
    plan.target_folder.mkdir(parents=True)
    path = getattr(plan, attribute)
    path.write_bytes(b"alt")

    assert [conflict.kind for conflict in detect_tui_target_conflicts(plan)] == [kind]


def test_tui_file_plan_distinguishes_free_and_conflicting_outputs(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = AppConfig(tmp_path / "vmix", tmp_path / "Aufnahmen", tmp_path / "Predigten")
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Predigt",
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    plan = build_tui_processing_plan(config=config, source_mp4=source, raw_recording=None, already_cut=True, info=info)
    plan.target_folder.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"alt")

    text = build_tui_target_file_plan_text(
        plan,
        detect_tui_target_conflicts(plan),
        proposed_names={"mp4": "Predigt (2).mp4", "mp3": plan.target_mp3.name, "summary": plan.summary_path.name},
    )

    assert f"MP4 | KONFLIKT: {plan.target_mp4.name} | Neue Datei: Predigt (2).mp4" in text
    assert f"MP3 | frei | wird erstellt: {plan.target_mp3.name}" in text
    assert f"Zusammenfassung | frei | wird erstellt: {plan.summary_path.name}" in text


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


def test_tui_warning_status_uses_warning_or_danger_class_by_severity(tmp_path):
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
    plan.summary_path.write_text("alt", encoding="utf-8")

    warning_text = build_tui_processing_warning_text(plan, detect_tui_target_conflicts(plan))

    assert warning_text.startswith("Status / Warnungen")
    assert tui_processing_warning_class(()) == "status-ok"
    assert tui_processing_warning_class((TuiTargetConflict(path=plan.summary_path, kind="summary", severity="warning", message="x"),)) == "status-warning"
    assert tui_processing_warning_class((TuiTargetConflict(path=plan.target_mp4, kind="mp4", severity="danger", message="x"),)) == "status-danger"


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


def test_tui_output_suffix_keeps_existing_files_unchanged(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video-neu")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )
    info = build_tui_metadata_info(
        config=config,
        date_text="2026-05-24",
        service_type_name="Gottesdienst",
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    original_plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
    )
    original_plan.target_folder.mkdir(parents=True)
    original_plan.target_mp4.write_bytes(b"video-alt")
    original_plan.target_mp3.write_bytes(b"mp3-alt")
    original_plan.summary_path.write_text("summary-alt", encoding="utf-8")

    suffixed_plan = apply_tui_output_suffix(original_plan, "Korrektur")
    result = execute_processing_plan(
        suffixed_plan,
        config,
        mp3_converter=lambda _source, target, _config: target.write_bytes(b"mp3-neu"),
        ffmpeg_checker=lambda _config: True,
    )

    assert result.success is True
    assert original_plan.target_mp4.read_bytes() == b"video-alt"
    assert original_plan.target_mp3.read_bytes() == b"mp3-alt"
    assert original_plan.summary_path.read_text(encoding="utf-8") == "summary-alt"
    assert suffixed_plan.target_mp4.name.endswith(" - Korrektur.mp4")
    assert suffixed_plan.target_mp3.name.endswith(" - Korrektur.mp3")
    assert suffixed_plan.summary_path.name.endswith(" - Zusammenfassung - Korrektur.txt")
    assert suffixed_plan.target_mp4.exists()
    assert suffixed_plan.target_mp3.exists()
    assert suffixed_plan.summary_path.exists()


def test_tui_backup_strategy_requires_selection_then_enables_execute(tmp_path):
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
        service_type_name="Gottesdienst",
        title="Lehre",
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
    plan.target_mp4.write_bytes(b"alt")

    blocked_label, blocked = build_tui_execute_button_state(plan, overwrite_confirmed=False)
    backup_plan = apply_tui_backup_existing_confirmation(plan)
    enabled_label, enabled = build_tui_execute_button_state(backup_plan, overwrite_confirmed=False)

    assert blocked is True
    assert "Erst entscheiden" in blocked_label
    assert backup_plan.backup_existing_outputs is True
    assert backup_plan.overwrite_existing_outputs is False
    assert backup_plan.existing_output_renames
    assert plan.target_mp4.exists()
    assert "->" in build_tui_existing_output_rename_text(backup_plan)
    backup_matrix = build_tui_target_file_plan_text(backup_plan, detect_tui_target_conflicts(backup_plan))
    assert f"Vorhandene Datei -> {plan.target_mp4.stem}__alt.mp4" in backup_matrix
    assert f"neue Datei -> {plan.target_mp4.name}" in backup_matrix
    assert enabled is False
    assert enabled_label == "Gesicherte Dateien behalten und finale Dateien erstellen"


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


def test_tui_safe_raw_recording_standard_can_be_selected_without_extra_confirmation(tmp_path):
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
        service_type_name="Gottesdienst",
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )

    plan = build_tui_processing_plan(
        config=config,
        source_mp4=cut,
        raw_recording=raw,
        already_cut=False,
        raw_action="keep",
        info=info,
    )

    assert plan.raw_action == "keep"
    assert tui_action_requires_confirmation("keep") is False


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
    assert "Bitte warten. Dateien werden erstellt/kopiert/verschoben." in started
    assert TUI_PROCESSING_RUNNING_LABEL == "Verarbeitung laeuft..."
    assert TUI_PROCESSING_DONE_LABEL == "Fertig vorbereitet"
    assert "Lokale Vorbereitung abgeschlossen." in success
    assert "Workflow-Status:" in success
    assert "Der Zielordner wurde geoeffnet." in success
    assert "Naechste manuelle Schritte:" in success
    assert "○ Vimeo-Upload noch ausstehend." in success
    assert "1. Zielordner kontrollieren." in success
    assert "2. Vimeo-Upload spaeter im PredigtUploader fortsetzen." in success
    assert "3. MP3 in WordPress hochladen." in success
    assert "4. Predigtinformationen in WordPress eintragen." in success
    assert "5. Vimeo/Embed-Code in WordPress ergaenzen." in success
    assert "6. Danach kann der PredigtUploader geschlossen oder eine neue Aufnahme vorbereitet werden." in success
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


def test_tui_processing_error_status_is_understandable(tmp_path):
    target = tmp_path / "Aufnahmen" / "2026" / "2026-05-24"

    text = build_tui_processing_error_status(
        ("Verarbeitung gestartet...", "MP3 wird erstellt."),
        "Die MP3 konnte nicht erstellt werden.",
        target_folder=target,
    )

    assert "Die Verarbeitung wurde nicht vollstaendig abgeschlossen." in text
    assert "Fehler: Die MP3 konnte nicht erstellt werden." in text
    assert "Es wurden keine Dateien still ueberschrieben." in text
    assert f"Zielordner: {target}" in text
    assert "Logdateien liegen" in text


def test_tui_processing_finished_actions_are_available_after_success():
    assert tui_processing_finished_action_labels() == (
        "Zielordner oeffnen",
        "Neue Aufnahme vorbereiten (zurueck zu Schritt 1)",
        "Beenden",
    )


def test_tui_metadata_validation_text_reports_missing_or_complete_fields():
    assert build_tui_metadata_validation_text(()) == "Alle Pflichtfelder ausgefüllt."
    assert build_tui_metadata_validation_text(("Hauptbibelstelle fehlt.", "Redner / Leitung fehlt.")) == (
        "Noch auszufüllen: Hauptbibelstelle, Redner / Leitung"
    )


def test_tui_metadata_scroll_hint_text_shows_only_hidden_missing_fields():
    assert build_tui_metadata_scroll_hint_text((), ("bible", "speaker")) == "↓ 2 Pflichtfelder weiter unten"
    assert build_tui_metadata_scroll_hint_text((), ("bible",)) == "↓ Pflichtfeld weiter unten"
    assert build_tui_metadata_scroll_hint_text(("bible",), ()) == "↑ Pflichtfeld weiter oben"
    assert build_tui_metadata_scroll_hint_text(("bible", "speaker"), ()) == "↑ 2 Pflichtfelder weiter oben"
    assert build_tui_metadata_scroll_hint_text((), ()) == ""


def test_tui_metadata_field_positions_distinguish_above_visible_and_below():
    above, below = classify_tui_metadata_fields_by_position(
        (("title", 3, 4), ("bible", 8, 10), ("speaker", 14, 16)),
        viewport_top=5,
        viewport_bottom=12,
    )

    assert above == ("title",)
    assert below == ("speaker",)


def test_tui_metadata_field_order_groups_required_before_optional_fields(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )

    predigt = service_type_by_name(config, "Predigt")
    bibelstunde = service_type_by_name(config, "Bibelstunde")

    assert tui_metadata_required_field_keys(predigt) == ("title", "bible", "speaker")
    assert tui_metadata_optional_field_keys(predigt) == ("folder_note",)
    assert tui_metadata_widget_order(predigt)[0:8] == (
        "metadata_basic_heading",
        "service_type_label",
        "service_type",
        "service_type_help",
        "date_label",
        "date_choice",
        "sermon_date",
        "metadata_required_heading",
    )
    assert tui_metadata_widget_order(predigt).index("title_label") < tui_metadata_widget_order(predigt).index(
        "metadata_optional_heading"
    )
    assert tui_metadata_required_field_keys(bibelstunde) == ("bible", "speaker")
    assert tui_metadata_optional_field_keys(bibelstunde)[0] == "title"
    assert tui_metadata_widget_order(bibelstunde).index("bible_label") < tui_metadata_widget_order(
        bibelstunde
    ).index("title_label")
    assert tui_metadata_widget_order(bibelstunde).index("speaker_label") < tui_metadata_widget_order(
        bibelstunde
    ).index("metadata_optional_heading")


def test_tui_metadata_screen_scrolls_at_small_height_and_keeps_actions_visible(tmp_path, monkeypatch):
    cut_folder = tmp_path / "Schnitt"
    cut_folder.mkdir()
    (cut_folder / "aufnahme.mp4").write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        cut_mp4_folder=cut_folder,
    )
    monkeypatch.setattr(tui_module, "load_tui_config", lambda _path=None: config)

    async def exercise() -> None:
        from textual.containers import VerticalScroll
        from textual.widgets import Button, Input, Static

        app = build_tui_app()
        async with app.run_test(size=(100, 32)) as pilot:
            for selector in ("#new", "#confirm", "#cut", "#newest"):
                app.screen.query_one(selector, Button).press()
                await pilot.pause(0.05)
            await pilot.pause(0.2)

            form_scroll = app.screen.query_one("#metadata_form_scroll", VerticalScroll)
            preview_scroll = app.screen.query_one("#metadata_preview_scroll", VerticalScroll)
            actions = app.screen.query_one("#metadata_actions")
            next_button = app.screen.query_one("#next", Button)
            hint = app.screen.query_one("#metadata_scroll_hint", Static)

            assert form_scroll.max_scroll_y > 0
            assert form_scroll.show_vertical_scrollbar, (
                form_scroll.max_scroll_y,
                form_scroll.scrollable_size,
                form_scroll.scrollable_content_region,
                form_scroll.styles.overflow_y,
                form_scroll.scrollbars_enabled,
            )
            assert preview_scroll is not form_scroll
            assert actions.region.bottom <= app.screen.region.bottom
            assert next_button.disabled
            assert "weiter unten" in str(hint.render())

            form_scroll.scroll_end(animate=False)
            await pilot.pause()
            assert "weiter oben" in str(hint.render())
            app.screen.query_one("#service_type").focus()
            await pilot.press("tab", "tab", "tab", "tab", "tab")
            await pilot.pause()
            assert app.focused.id == "speaker_input"
            assert form_scroll.can_view_partial(app.screen.query_one("#speaker_input", Input))

            app.screen.query_one("#title_input", Input).value = "Lehre statt Leere"
            app.screen.query_one("#bible_input", Input).value = "Johannes 3,16"
            app.screen.query_one("#speaker_input", Input).value = "Max Muster"
            await pilot.pause()
            assert not hint.display
            assert not next_button.disabled

    asyncio.run(exercise())


def test_tui_metadata_screen_fields_are_reachable_at_large_height(tmp_path, monkeypatch):
    cut_folder = tmp_path / "Schnitt"
    cut_folder.mkdir()
    (cut_folder / "aufnahme.mp4").write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        cut_mp4_folder=cut_folder,
    )
    monkeypatch.setattr(tui_module, "load_tui_config", lambda _path=None: config)

    async def exercise() -> None:
        from textual.widgets import Button

        app = build_tui_app()
        async with app.run_test(size=(120, 50)) as pilot:
            for selector in ("#new", "#confirm", "#cut", "#newest"):
                app.screen.query_one(selector, Button).press()
                await pilot.pause(0.05)
            await pilot.pause(0.2)

            required_heading = app.screen.query_one("#metadata_required_heading")
            optional_heading = app.screen.query_one("#metadata_optional_heading")
            actions = app.screen.query_one("#metadata_actions")
            assert required_heading.region.y < optional_heading.region.y
            assert actions.region.bottom <= app.screen.region.bottom

            app.screen.query_one("#service_type").focus()
            await pilot.press("tab", "tab", "tab")
            assert app.focused.id == "title_input"

    asyncio.run(exercise())


def test_tui_target_folder_decision_switches_modes_at_small_height(tmp_path, monkeypatch):
    cut_folder = tmp_path / "Schnitt"
    cut_folder.mkdir()
    (cut_folder / "aufnahme.mp4").write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        cut_mp4_folder=cut_folder,
    )
    existing = suggest_folder(
        config,
        SermonInfo(sermon_date=date.today(), title="", bible_reference="", speaker=""),
    )
    existing.mkdir(parents=True)
    monkeypatch.setattr(tui_module, "load_tui_config", lambda _path=None: config)

    async def exercise() -> None:
        from textual.containers import VerticalScroll
        from textual.widgets import Button, Input, Static

        app = build_tui_app()
        async with app.run_test(size=(100, 32)) as pilot:
            for selector in ("#new", "#confirm", "#cut", "#newest"):
                app.screen.query_one(selector, Button).press()
                await pilot.pause(0.05)
            app.screen.query_one("#title_input", Input).value = "Lehre"
            app.screen.query_one("#bible_input", Input).value = "Johannes 3,16"
            app.screen.query_one("#speaker_input", Input).value = "Max Muster"
            await pilot.pause()
            app.screen.query_one("#next", Button).press()
            await pilot.pause(0.2)

            primary = app.screen.query_one("#target_folder_primary", Button)
            secondary = app.screen.query_one("#create_with_note", Button)
            status = app.screen.query_one("#target_folder_status_banner", Static)
            actions = app.screen.query_one("#target_folder_actions")
            scroll = app.screen.query_one("#target_folder_scroll", VerticalScroll)
            assert "Vorhandenen Ordner verwenden" in str(primary.label)
            assert "Vorhandener Tagesordner gefunden" in str(status.render())
            assert actions.region.bottom <= app.screen.region.bottom

            secondary.press()
            await pilot.pause()
            note_input = app.screen.query_one("#folder_note_override", Input)
            assert note_input.display
            assert app.focused is note_input
            assert primary.disabled
            assert str(primary.label) == "Neuen Ordner mit Zusatz verwenden"
            assert str(secondary.label) == "Doch vorhandenen Tagesordner verwenden"
            assert "Vorhandener Tagesordner gefunden" not in str(status.render())

            note_input.value = "test"
            await pilot.pause()
            await pilot.wait_for_animation()
            expected = existing.with_name(f"{existing.name} - test")
            assert not primary.disabled
            assert f"Neuer Zielordner: {expected}" in str(status.render())
            assert scroll.can_view_partial(note_input), (
                scroll.region,
                scroll.scrollable_content_region,
                scroll.scroll_y,
                scroll.max_scroll_y,
                note_input.region,
            )
            assert actions.region.bottom <= app.screen.region.bottom

            expected.mkdir()
            note_input.value = "test "
            await pilot.pause()
            assert "Dieser Zielordner existiert bereits." in str(status.render())
            assert status.has_class("status-warning")

            secondary.press()
            await pilot.pause()
            assert not note_input.display
            assert "Vorhandenen Ordner verwenden" in str(primary.label)
            assert "Vorhandener Tagesordner gefunden" in str(status.render())
            assert not primary.disabled
            primary.press()
            await pilot.pause(0.2)
            assert app.screen.plan.target_folder == existing
            app.pop_screen()
            await pilot.pause(0.2)
            app.screen.query_one("#create_with_note", Button).press()
            await pilot.pause()
            app.screen.query_one("#folder_note_override", Input).value = "neu"
            await pilot.pause()
            app.screen.query_one("#target_folder_primary", Button).press()
            await pilot.pause(0.2)
            assert app.screen.plan.target_folder == existing.with_name(f"{existing.name} - neu")

    asyncio.run(exercise())


def test_tui_processing_conflicts_are_responsive_and_validate_new_names(tmp_path, monkeypatch):
    cut_folder = tmp_path / "Schnitt"
    cut_folder.mkdir()
    source = cut_folder / "aufnahme.mp4"
    source.write_bytes(b"video-neu")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        cut_mp4_folder=cut_folder,
    )
    service_name = default_tui_service_type_name(config, date.today())
    info = build_tui_metadata_info(
        config=config,
        date_text=date.today().isoformat(),
        service_type_name=service_name,
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="",
    )
    expected_plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
    )
    expected_plan.target_folder.mkdir(parents=True)
    expected_plan.target_mp4.write_bytes(b"mp4-alt")
    expected_plan.target_mp3.write_bytes(b"mp3-alt")
    expected_plan.summary_path.write_text("summary-alt", encoding="utf-8")
    monkeypatch.setattr(tui_module, "load_tui_config", lambda _path=None: config)

    async def exercise() -> None:
        from textual.containers import VerticalScroll
        from textual.widgets import Button, Input, Static

        app = build_tui_app()
        async with app.run_test(size=(100, 32)) as pilot:
            for selector in ("#new", "#confirm", "#cut", "#newest"):
                app.screen.query_one(selector, Button).press()
                await pilot.pause(0.05)
            app.screen.query_one("#title_input", Input).value = "Lehre"
            app.screen.query_one("#bible_input", Input).value = "Johannes 3,16"
            app.screen.query_one("#speaker_input", Input).value = "Max Muster"
            await pilot.pause()
            app.screen.query_one("#next", Button).press()
            await pilot.pause(0.2)
            app.screen.query_one("#target_folder_primary", Button).press()
            await pilot.pause(0.2)

            scroll = app.screen.query_one("#processing_review_scroll", VerticalScroll)
            actions = app.screen.query_one("#processing_actions")
            warning = app.screen.query_one("#processing_warning_text", Static)
            file_state = app.screen.query_one("#processing_file_state_text", Static)
            back = app.screen.query_one("#back", Button)
            rename = app.screen.query_one("#use_output_suffix", Button)
            assert "STOPP" in str(warning.render())
            assert warning.has_class("status-danger")
            assert "MP4 | KONFLIKT" in str(file_state.render())
            assert "MP3 | KONFLIKT" in str(file_state.render())
            assert str(back.label) == "Zurueck und anderen Ordner waehlen"
            assert actions.region.bottom <= app.screen.region.bottom
            assert scroll.max_scroll_y > 0

            rename.press()
            await pilot.pause()
            await pilot.wait_for_animation()
            mp4_name = app.screen.query_one("#new_mp4_name", Input)
            assert mp4_name.value.endswith(" (2).mp4")
            assert scroll.can_view_partial(mp4_name), (
                scroll.region,
                scroll.scroll_y,
                scroll.max_scroll_y,
                mp4_name.region,
            )

            mp4_name.value = "ungueltig?.mp4"
            await pilot.pause()
            assert rename.disabled
            mp4_name.value = expected_plan.target_mp4.name
            await pilot.pause()
            assert rename.disabled
            mp4_name.value = "Eigener neuer Predigtname.mp4"
            await pilot.pause()
            assert not rename.disabled
            assert expected_plan.target_mp4.read_bytes() == b"mp4-alt"
            assert expected_plan.target_mp3.read_bytes() == b"mp3-alt"
            assert expected_plan.summary_path.read_text(encoding="utf-8") == "summary-alt"

            back.press()
            await pilot.pause(0.2)
            assert app.screen.query_one("#target_folder_primary", Button)

    asyncio.run(exercise())


def test_tui_processing_success_banner_is_green_and_clear(tmp_path):
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

    banner = build_tui_processing_success_banner(plan, opened_target_folder=True)

    assert banner.startswith("Fertig vorbereitet")
    assert "Die Dateien wurden erstellt und der Zielordner wurde geoeffnet." in banner


def test_tui_steps_five_to_seven_keep_scroll_areas_and_completion_screen():
    source = (Path(__file__).resolve().parents[1] / "src" / "predigt_uploader" / "tui_app.py").read_text(
        encoding="utf-8"
    )

    assert 'yield Static("", id="metadata_validation", classes="status-info")' in source
    assert 'with Vertical(id="metadata_form_pane")' in source
    assert 'with Vertical(id="metadata_field_stack")' in source
    assert 'MetadataFormScroll(id="metadata_form_scroll", classes="panel-neutral")' in source
    assert 'VerticalScroll(id="metadata_preview_scroll", classes="panel-info")' in source
    assert 'with Vertical(id="metadata_content")' in source
    assert 'with Horizontal(id="metadata_body")' in source
    assert 'with Horizontal(id="metadata_scroll_hint_row")' in source
    assert 'yield Static("", id="metadata_scroll_hint", classes="scroll-hint")' in source
    assert 'yield Static("Grunddaten", id="metadata_basic_heading", classes="metadata_section_heading")' in source
    assert 'yield Static("Pflichtangaben", id="metadata_required_heading", classes="metadata_section_heading")' in source
    assert 'yield Static("Optionale Angaben", id="metadata_optional_heading", classes="metadata_section_heading")' in source
    assert 'Horizontal(id="metadata_actions")' in source
    assert 'VerticalScroll(id="target_folder_scroll")' in source
    assert 'with Vertical(id="processing_plan_box", classes="panel-neutral")' in source
    assert 'with Vertical(id="processing_status_box", classes="panel-info")' in source
    assert 'Vertical(id="target_folder_actions")' in source
    assert 'VerticalScroll(id="processing_review_scroll")' in source
    assert 'with Vertical(id="processing_plan_box", classes="panel-neutral")' in source
    assert 'with Vertical(id="processing_status_box", classes="panel-info")' in source
    assert 'Vertical(id="processing_actions")' in source
    assert "class VimeoPublishingScreen" in source
    assert "self.app.open_vimeo_publishing(" in source
    assert 'VerticalScroll(id="vimeo_scroll")' in source
    assert '"Video jetzt auf Vimeo hochladen",' in source
    assert 'Button("Vimeo überspringen / später erledigen"' in source
    assert "class CompletionScreen" in source
    assert "self.app.push_screen(\n                CompletionScreen(" in source
    assert 'VerticalScroll(id="completion_scroll")' in source
    assert 'Horizontal(id="completion_actions")' in source
    assert 'classes="panel-info"' in source
    assert source.index('Button("Rohaufnahme auswaehlen", id="raw", variant="primary")') < source.index(
        'Button("Fertig geschnittene MP4 auswaehlen", id="cut")'
    )
    assert 'id="target_folder_status_banner"' in source
    assert 'classes=tui_target_folder_status_class(self.resolution)' in source
    assert 'id="processing_warning_text"' in source
    assert 'classes=tui_processing_warning_class(conflicts)' in source
    assert 'Button("Neue Dateien umbenennen", id="use_output_suffix", variant="primary")' in source
    assert 'Button("Vorhandene Dateien umbenennen und neue Dateien erstellen", id="backup_existing")' in source
    assert 'Button("Vorhandene Dateien ersetzen", id="confirm_overwrite", variant="error")' in source
    assert '"Zurueck und anderen Ordner waehlen" if conflicts else TUI_BACK_LABEL' in source
    assert ".navigation_actions Button" in source
    assert "margin-right: 1;" in source
    assert 'yield Static(build_tui_processing_success_banner(self.plan, opened_target_folder=self.opened_target_folder), id="completion_banner", classes="status-ok")' in source
    assert '#metadata_form_pane {' in source
    assert '#metadata_field_stack {' in source
    assert 'height: auto;' in source
    assert '#metadata_form_scroll, #metadata_preview_scroll {' in source
    assert 'overflow-y: auto;' in source
    assert '#metadata_scroll_hint_row {' in source
    assert '.scroll-hint {' in source
    assert '.metadata_section_heading {' in source
    assert '#completion_banner {' in source


def _tui_vimeo_plan_and_state(tmp_path, *, vimeo: VimeoState | None = None):
    source = tmp_path / "Schnitt" / "aufnahme.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        cut_mp4_folder=source.parent,
        vimeo=VimeoConfig("59930802", "1320477", "Predigten"),
    )
    info = SermonInfo(date(2026, 8, 31), "Lehre", "Johannes 3,16", "Max Muster")
    plan = build_tui_processing_plan(
        config=config,
        source_mp4=source,
        raw_recording=None,
        already_cut=True,
        info=info,
    )
    plan.target_folder.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"final-video")
    plan.target_mp3.write_bytes(b"final-audio")
    plan.summary_path.write_text("Zusammenfassung", encoding="utf-8")
    state = completed_local_workflow_state(
        sermon=info,
        target_folder=plan.target_folder,
        cut_mp4=source,
        final_mp4=plan.target_mp4,
        final_mp3=plan.target_mp3,
        summary=plan.summary_path,
    )
    if vimeo is not None:
        state = replace(state, vimeo=vimeo)
    state_path = save_workflow_state(state)
    return config, plan, state_path


def test_tui_local_processing_success_opens_vimeo_screen_without_upload(tmp_path, monkeypatch):
    cut_folder = tmp_path / "Schnitt"
    cut_folder.mkdir()
    (cut_folder / "aufnahme.mp4").write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        cut_mp4_folder=cut_folder,
        vimeo=VimeoConfig("59930802", "1320477", "Predigten"),
    )
    monkeypatch.setattr(tui_module, "load_tui_config", lambda _path=None: config)
    factory_calls = 0

    def factory(_config):
        nonlocal factory_calls
        factory_calls += 1
        return _TuiFakeVimeoService()

    def fake_execute(plan, _config, progress=None):
        plan.target_folder.mkdir(parents=True)
        plan.target_mp4.write_bytes(b"final-video")
        plan.target_mp3.write_bytes(b"final-audio")
        plan.summary_path.write_text("Zusammenfassung", encoding="utf-8")
        state = completed_local_workflow_state(
            sermon=plan.info,
            target_folder=plan.target_folder,
            cut_mp4=plan.source_mp4,
            final_mp4=plan.target_mp4,
            final_mp3=plan.target_mp3,
            summary=plan.summary_path,
        )
        state_path = save_workflow_state(state)
        return ProcessingExecutionResult(
            success=True,
            messages=("Lokale Dateien erstellt.",),
            summary_path=plan.summary_path,
            workflow_state_path=state_path,
        )

    monkeypatch.setattr(tui_module, "execute_processing_plan", fake_execute)

    async def exercise() -> None:
        from textual.widgets import Button, Input, Static

        app = build_tui_app(vimeo_service_factory=factory)
        async with app.run_test(size=(100, 32)) as pilot:
            for selector in ("#new", "#confirm", "#cut", "#newest"):
                app.screen.query_one(selector, Button).press()
                await pilot.pause(0.05)
            app.screen.query_one("#title_input", Input).value = "Lehre"
            app.screen.query_one("#bible_input", Input).value = "Johannes 3,16"
            app.screen.query_one("#speaker_input", Input).value = "Max Muster"
            await pilot.pause()
            app.screen.query_one("#next", Button).press()
            await pilot.pause(0.1)
            app.screen.query_one("#target_folder_primary", Button).press()
            await pilot.pause(0.1)
            app.screen.query_one("#execute", Button).press()

            await _wait_for_tui_condition(
                pilot,
                lambda: bool(app.screen.query("#vimeo_upload")),
            )
            await pilot.pause(0.2)
            assert "Schritt 8/8" in str(app.screen.query_one("#screen_title", Static).render())
            assert factory_calls == 0
            plan_state_path = app.screen.state_path
            assert load_workflow_state(plan_state_path).vimeo.step.status == "pending"
            assert plan_state_path.is_file()

    asyncio.run(exercise())


class _TuiFakeVimeoService:
    def __init__(self, *, gate: threading.Event | None = None, error: Exception | None = None) -> None:
        self.gate = gate
        self.error = error
        self.started = threading.Event()
        self.preview_calls = 0
        self.publish_calls = 0
        self.known_video_id: str | None = None

    def preflight(self):
        return SimpleNamespace(
            team_owner_name="Immanuelgemeinde Wolfsburg",
            folder=SimpleNamespace(name="Predigten", folder_id="1320477"),
        )

    def preview_upload(self, state_path):
        self.preview_calls += 1
        state = load_workflow_state(state_path)
        return SimpleNamespace(
            file_path=state.paths.final_mp4,
            file_size=state.paths.final_mp4.stat().st_size,
            title=state.paths.final_mp4.stem,
            team_owner_name="Immanuelgemeinde Wolfsburg",
            folder=SimpleNamespace(name="Predigten", folder_id="1320477"),
            permission_note="Uploadrecht wird beim Upload geprüft.",
            upload_approach="tus",
        )

    def publish(self, state_path, progress=None):
        self.publish_calls += 1
        state = load_workflow_state(state_path)
        self.known_video_id = state.vimeo.video_id
        if progress:
            progress(VimeoProgress("creating_remote_video", 0, 100))
            progress(VimeoProgress("uploading", 10, 100))
            progress(VimeoProgress("uploading", 63, 100, 18.4 * 1024 * 1024, 71))
        self.started.set()
        if self.gate is not None:
            self.gate.wait(timeout=5)
        if self.error is not None:
            raise self.error
        if progress:
            progress(VimeoProgress("verifying_upload", 100, 100))
            progress(VimeoProgress("assigning_folder"))
            progress(VimeoProgress("processing_video"))
            progress(VimeoProgress("fetching_embed"))
        completed = replace(
            state,
            vimeo=replace(
                state.vimeo,
                step=StepState("complete"),
                video_id=state.vimeo.video_id or "900",
                video_uri=state.vimeo.video_uri or "/videos/900",
                video_url="https://vimeo.com/900/hash",
                upload_status="complete",
                transcode_status="complete",
                target_folder_id="1320477",
                target_folder_uri="/projects/1320477",
                target_folder_name="Predigten",
                folder_status="verified",
                team_owner_user_id="59930802",
                player_embed_url="https://player.vimeo.com/video/900?h=hash",
                embed_html='<iframe src="https://player.vimeo.com/video/900?h=hash"></iframe>',
            ),
        )
        save_workflow_state(completed, state_path)
        if progress:
            progress(VimeoProgress("complete", 100, 100))
        return SimpleNamespace(video_id="900")


async def _wait_for_tui_condition(pilot, condition, *, attempts: int = 80) -> None:
    for _ in range(attempts):
        if condition():
            return
        await pilot.pause(0.05)
    raise AssertionError("Textual-Zustand wurde nicht rechtzeitig erreicht")


def test_tui_vimeo_progress_and_success_text_are_clear(tmp_path):
    config, plan, _state_path = _tui_vimeo_plan_and_state(tmp_path)
    state = VimeoState(
        step=StepState("complete"),
        video_id="900",
        video_url="https://vimeo.com/900/hash",
        target_folder_name="Predigten",
        transcode_status="complete",
        player_embed_url="https://player.vimeo.com/video/900",
        embed_html="<iframe></iframe>",
    )

    uploading = build_tui_vimeo_progress_text("uploading", percent=63)
    success = build_tui_vimeo_success_text(plan, state)
    completion = build_tui_processing_success_status(plan, vimeo_state=state)
    error = build_tui_vimeo_error_text(VimeoUploadError("Netzwerk unterbrochen"), replace(state, step=StepState("failed")))

    assert "⟳ Video wird hochgeladen: 63.0 %" in uploading
    assert "○ Upload wird geprüft" in uploading
    assert "Vimeo-Upload abgeschlossen" in success
    assert "Embed-Code: abgerufen" in success
    assert "✓ Video zu Vimeo hochgeladen." in completion
    assert "✓ Ordner Predigten." in completion
    assert "○ Vimeo-Upload noch ausstehend." not in completion
    assert "lokale MP4, MP3 und Zusammenfassung sind sicher fertig" in error
    assert "Bekannte Vimeo-Video-ID: 900" in error
    assert config.vimeo.target_folder_id == "1320477"


def test_tui_vimeo_upload_details_are_human_readable_and_transcoding_has_no_fake_percent():
    details = format_tui_vimeo_upload_details(
        VimeoProgress(
            "uploading",
            int(1.45 * 1024**3),
            int(2.73 * 1024**3),
            18.4 * 1024**2,
            71,
        )
    )
    processing = build_tui_vimeo_progress_text(
        "complete",
        transcode_status="in_progress",
    )
    complete = build_tui_vimeo_progress_text(
        "complete",
        transcode_status="complete",
    )

    assert "1,45 GB / 2,73 GB" in details
    assert "18,4 MB/s · ca. 1:11 verbleibend" in details
    assert "⟳ Vimeo verarbeitet das Video …  Status: IN_PROGRESS" in processing
    assert "%" not in processing
    assert "✓ Vimeo verarbeitet das Video …  Status: COMPLETE" in complete


def test_tui_vimeo_screen_does_not_upload_on_entry_and_skip_shows_pending_completion(tmp_path, monkeypatch):
    config, plan, state_path = _tui_vimeo_plan_and_state(tmp_path)
    monkeypatch.setattr(tui_module, "load_tui_config", lambda _path=None: config)
    factory_calls = 0

    def factory(_config):
        nonlocal factory_calls
        factory_calls += 1
        return _TuiFakeVimeoService()

    async def exercise() -> None:
        from textual.containers import VerticalScroll
        from textual.widgets import Button, ProgressBar, Static

        app = build_tui_app(vimeo_service_factory=factory)
        async with app.run_test(size=(100, 32)) as pilot:
            app.open_vimeo_publishing(plan, state_path=state_path, opened_target_folder=True)
            await pilot.pause(0.2)

            assert factory_calls == 0
            assert load_workflow_state(state_path).vimeo.step.status == "pending"
            assert "erst nach Klick auf den blauen Button" in str(
                app.screen.query_one("#vimeo_local_safe", Static).render()
            )
            assert app.screen.query_one("#vimeo_scroll", VerticalScroll)
            assert app.screen.query_one("#vimeo_actions").region.bottom <= app.screen.region.bottom

            app.screen.query_one("#vimeo_skip", Button).press()
            await pilot.pause(0.2)
            completion = str(app.screen.query_one("#completion_status", Static).render())
            assert "○ Vimeo-Upload noch ausstehend." in completion
            assert "✓ Lokale Dateien erstellt." in completion
            assert factory_calls == 0

    asyncio.run(exercise())


def test_tui_vimeo_upload_runs_in_worker_updates_progress_and_completes(tmp_path, monkeypatch):
    config, plan, state_path = _tui_vimeo_plan_and_state(tmp_path)
    monkeypatch.setattr(tui_module, "load_tui_config", lambda _path=None: config)
    release = threading.Event()
    service = _TuiFakeVimeoService(gate=release)

    async def exercise() -> None:
        from textual.widgets import Button, ProgressBar, Static

        app = build_tui_app(vimeo_service_factory=lambda _config: service)
        async with app.run_test(size=(100, 32)) as pilot:
            app.open_vimeo_publishing(plan, state_path=state_path, opened_target_folder=True)
            await pilot.pause()
            app.screen.query_one("#vimeo_upload", Button).press()
            await _wait_for_tui_condition(pilot, service.started.is_set)

            assert "63.0 %" in str(app.screen.query_one("#vimeo_progress", Static).render())
            assert app.screen.query_one("#vimeo_upload_bar", ProgressBar).progress == 63
            details = str(app.screen.query_one("#vimeo_upload_details", Static).render())
            assert "63 B / 100 B" in details
            assert "18,4 MB/s" in details
            assert app.screen.query_one("#vimeo_skip", Button).disabled
            assert app.screen.query_one("#vimeo_upload", Button).disabled
            app.screen.query_one("#vimeo_upload", Button).press()
            await pilot.pause(0.1)
            assert service.publish_calls == 1
            assert app.screen.query_one("#vimeo_actions").region.bottom <= app.screen.region.bottom

            release.set()
            await _wait_for_tui_condition(
                pilot,
                lambda: not app.screen.query_one("#vimeo_continue", Button).disabled,
            )
            state = load_workflow_state(state_path).vimeo
            assert service.publish_calls == 1
            assert state.step.status == "complete"
            assert state.folder_status == "verified"
            assert state.transcode_status == "complete"
            assert "Vimeo-Upload abgeschlossen" in str(
                app.screen.query_one("#vimeo_status_banner", Static).render()
            )
            assert str(app.screen.query_one("#vimeo_upload", Button).label) == "Vimeo-Upload abgeschlossen"

            app.screen.query_one("#vimeo_continue", Button).press()
            await pilot.pause(0.2)
            completion = str(app.screen.query_one("#completion_status", Static).render())
            assert "✓ Video zu Vimeo hochgeladen." in completion
            assert "✓ Embed-Code abgerufen." in completion

    try:
        asyncio.run(exercise())
    finally:
        release.set()


def test_tui_vimeo_error_keeps_local_files_and_allows_later_completion(tmp_path, monkeypatch):
    config, plan, state_path = _tui_vimeo_plan_and_state(tmp_path)
    monkeypatch.setattr(tui_module, "load_tui_config", lambda _path=None: config)
    service = _TuiFakeVimeoService(error=VimeoUploadError("Keine Internetverbindung"))
    original_mp4 = plan.target_mp4.read_bytes()

    async def exercise() -> None:
        from textual.widgets import Button, Static

        app = build_tui_app(vimeo_service_factory=lambda _config: service)
        async with app.run_test(size=(100, 32)) as pilot:
            app.open_vimeo_publishing(plan, state_path=state_path, opened_target_folder=False)
            await pilot.pause()
            app.screen.query_one("#vimeo_upload", Button).press()
            await _wait_for_tui_condition(
                pilot,
                lambda: "erneut versuchen" in str(app.screen.query_one("#vimeo_upload", Button).label),
            )

            banner = str(app.screen.query_one("#vimeo_status_banner", Static).render())
            assert "lokale MP4, MP3 und Zusammenfassung sind sicher fertig" in banner
            assert "Keine Internetverbindung" in banner
            assert plan.target_mp4.read_bytes() == original_mp4
            assert not app.screen.query_one("#vimeo_skip", Button).disabled
            stages = str(app.screen.query_one("#vimeo_progress", Static).render())
            assert "✓ Vimeo-Verbindung geprüft" in stages
            assert "✓ Video auf Vimeo angelegt" in stages
            assert "✗ Video wird hochgeladen" in stages
            assert "63 B / 100 B" in str(
                app.screen.query_one("#vimeo_upload_details", Static).render()
            )

    asyncio.run(exercise())


def test_tui_vimeo_retry_reuses_existing_video_id(tmp_path, monkeypatch):
    existing = VimeoState(
        step=StepState("failed", "Netzwerk"),
        video_id="900",
        video_uri="/videos/900",
        upload_status="failed",
    )
    config, plan, state_path = _tui_vimeo_plan_and_state(tmp_path, vimeo=existing)
    monkeypatch.setattr(tui_module, "load_tui_config", lambda _path=None: config)
    service = _TuiFakeVimeoService()

    async def exercise() -> None:
        from textual.widgets import Button

        app = build_tui_app(vimeo_service_factory=lambda _config: service)
        async with app.run_test() as pilot:
            app.open_vimeo_publishing(plan, state_path=state_path, opened_target_folder=False)
            await pilot.pause()
            app.screen.query_one("#vimeo_upload", Button).press()
            await _wait_for_tui_condition(
                pilot,
                lambda: not app.screen.query_one("#vimeo_continue", Button).disabled,
            )

            assert service.known_video_id == "900"
            assert load_workflow_state(state_path).vimeo.video_id == "900"
            assert service.publish_calls == 1

    asyncio.run(exercise())


class _TuiMemoryCredentials:
    def __init__(self, password: str | None = None) -> None:
        self.password = password

    def get_password(self, _service, _username):
        return self.password

    def set_password(self, _service, _username, password):
        self.password = password

    def delete_password(self, _service, _username):
        self.password = None


def test_direct_vimeo_state_reuses_existing_and_creates_isolated_minimal_state(tmp_path):
    first = tmp_path / "Fertige Predigt.mp4"
    second = tmp_path / "Zweite Aufnahme.mp4"
    first.write_bytes(b"video")
    second.write_bytes(b"video-2")

    first_path, first_created = load_or_create_direct_vimeo_state(first)
    reused_path, reused_created = load_or_create_direct_vimeo_state(first)
    second_path, second_created = load_or_create_direct_vimeo_state(second)

    assert validate_direct_vimeo_mp4(first) == first
    assert first_created is True
    assert reused_created is False
    assert reused_path == first_path
    assert second_created is True
    assert second_path != first_path
    assert load_workflow_state(first_path).paths.final_mp4 == first
    assert load_workflow_state(second_path).paths.final_mp4 == second


def test_tui_direct_vimeo_entry_uses_the_shared_progress_screen(tmp_path, monkeypatch):
    target = tmp_path / "Predigten"
    target.mkdir()
    mp4 = target / "Fertige Predigt.mp4"
    mp4.write_bytes(b"video")
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=target,
        mp3_base=target,
        vimeo=VimeoConfig("59930802", "1320477", "Predigten"),
    )
    monkeypatch.setattr(tui_module, "load_tui_config", lambda _path=None: config)
    calls = 0

    def factory(_config):
        nonlocal calls
        calls += 1
        return _TuiFakeVimeoService()

    async def exercise() -> None:
        from textual.widgets import Button, ProgressBar

        app = build_tui_app(
            vimeo_service_factory=factory,
            speaker_store=SpeakerHistory(tmp_path / "speakers.json"),
        )
        async with app.run_test(size=(100, 32)) as pilot:
            app.screen.query_one("#direct_vimeo", Button).press()
            await pilot.pause(0.2)
            assert calls == 0
            assert app.screen.query_one("#direct_vimeo_actions").region.bottom <= app.screen.region.bottom

            app.screen.query_one("#direct_vimeo_select", Button).press()
            await pilot.pause(0.2)
            assert calls == 0
            assert app.screen.query_one("#vimeo_upload", Button)
            assert load_workflow_state(app.screen.state_path).paths.final_mp4 == mp4

            app.screen.query_one("#vimeo_upload", Button).press()
            await _wait_for_tui_condition(
                pilot,
                lambda: not app.screen.query_one("#vimeo_continue", Button).disabled,
            )
            assert app.screen.direct_mode is True
            assert app.screen.query_one("#vimeo_upload_bar", ProgressBar).progress == 100
            assert calls == 1

    asyncio.run(exercise())


def test_tui_settings_store_masked_token_speakers_and_general_values(tmp_path, monkeypatch):
    appdata = tmp_path / "AppData"
    monkeypatch.setenv("APPDATA", str(appdata))
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        vimeo=VimeoConfig("59930802", "1320477", "Predigten"),
    )
    monkeypatch.setattr(tui_module, "load_tui_config", lambda _path=None: config)
    backend = _TuiMemoryCredentials()
    manager = VimeoCredentialManager(backend, {})
    history = SpeakerHistory(appdata / "PredigtUploader" / "speakers.json")
    service = _TuiFakeVimeoService()

    async def exercise() -> None:
        from textual.widgets import Button, Input

        app = build_tui_app(
            credential_manager=manager,
            speaker_store=history,
            vimeo_service_factory=lambda _config: service,
        )
        async with app.run_test(size=(100, 32)) as pilot:
            app.screen.query_one("#settings", Button).press()
            await pilot.pause(0.2)
            token = app.screen.query_one("#settings_vimeo_token", Input)
            assert token.password is True
            token.value = "safe-token-value"
            app.screen.query_one("#settings_save_token", Button).press()
            await pilot.pause()
            assert backend.password == "safe-token-value"
            assert token.value == ""
            app.screen.query_one("#settings_check_vimeo", Button).press()
            await _wait_for_tui_condition(
                pilot,
                lambda: "Vimeo-Verbindung: OK" in str(app.screen.query_one("#settings_vimeo_result").render()),
            )

            app.screen.query_one("#settings_speaker_name", Input).value = "  Max   Müller "
            app.screen.query_one("#settings_add_speaker", Button).press()
            app.screen.query_one("#settings_year_template", Input).value = "{year} Video+Audio"
            app.screen.query_one("#settings_save_general", Button).press()
            await pilot.pause(0.2)

            assert history.list() == ("Max Müller",)
            saved = appdata / "PredigtUploader" / "config.toml"
            text = saved.read_text(encoding="utf-8")
            assert 'year_folder_template = "{year} Video+Audio"' in text
            assert "safe-token-value" not in text
            assert app.screen.query_one("#settings_actions").region.bottom <= app.screen.region.bottom

    asyncio.run(exercise())


def test_tui_speaker_suggestions_are_keyboard_reachable(tmp_path, monkeypatch):
    cut_folder = tmp_path / "Schnitt"
    cut_folder.mkdir()
    (cut_folder / "aufnahme.mp4").write_bytes(b"video")
    config = AppConfig(tmp_path / "vmix", tmp_path / "Aufnahmen", tmp_path / "Predigten", cut_mp4_folder=cut_folder)
    monkeypatch.setattr(tui_module, "load_tui_config", lambda _path=None: config)
    history = SpeakerHistory(tmp_path / "speakers.json")
    history.add("Max Müller")

    async def exercise() -> None:
        from textual.widgets import Button, Input, OptionList

        app = build_tui_app(speaker_store=history)
        async with app.run_test(size=(100, 32)) as pilot:
            for selector in ("#new", "#confirm", "#cut", "#newest"):
                app.screen.query_one(selector, Button).press()
                await pilot.pause(0.05)
            field = app.screen.query_one("#speaker_input", Input)
            field.value = "max"
            await pilot.pause()
            suggestions = app.screen.query_one("#speaker_suggestions", OptionList)
            assert suggestions.display
            field.focus()
            await pilot.press("down", "enter")
            assert field.value == "Max Müller"

    asyncio.run(exercise())


def test_tui_metadata_step_validation_banner_and_folder_note_button_are_visible():
    source = (Path(__file__).resolve().parents[1] / "src" / "predigt_uploader" / "tui_app.py").read_text(
        encoding="utf-8"
    )

    assert 'yield Static("", id="metadata_validation", classes="status-info")' in source
    assert 'validation_banner = self.query_one("#metadata_validation", Static)' in source
    assert 'validation_banner.update(build_tui_metadata_validation_text(messages))' in source
    assert 'validation_banner.set_classes("status-ok" if not messages else "status-warning")' in source
    assert 'yield Button("Neuen Ordner mit Zusatz erstellen", id="create_with_note")' in source
    assert 'note_input.focus()' in source
    assert 'event.button.label = "Doch vorhandenen Tagesordner verwenden"' in source
    assert 'primary.label = "Neuen Ordner mit Zusatz verwenden"' in source
    assert 'primary.disabled = not note.strip()' in source
    assert 'Bitte zuerst einen Zusatz eingeben.' in source


def test_tui_metadata_step_contains_all_required_fields_and_fixed_actions():
    source = (Path(__file__).resolve().parents[1] / "src" / "predigt_uploader" / "tui_app.py").read_text(
        encoding="utf-8"
    )

    assert 'yield Static(build_tui_step_title(5, "Metadaten erfassen"), id="screen_title")' in source
    assert 'yield Static(build_tui_progress_text(5, skipped_steps), classes="workflow_progress")' in source
    assert 'with MetadataFormScroll(id="metadata_form_scroll", classes="panel-neutral")' in source
    assert 'stack.move_child(widget, after=previous_widget)' in source
    assert 'with VerticalScroll(id="metadata_preview_scroll", classes="panel-info")' in source
    assert 'yield Static("Grunddaten", id="metadata_basic_heading", classes="metadata_section_heading")' in source
    assert 'yield Label("Art der Veranstaltung", id="service_type_label")' in source
    assert 'yield Select(service_names, value=default_service, id="service_type")' in source
    assert 'id="date_choice"' in source
    assert 'yield Input(value=preferred_date.value.isoformat(), placeholder="YYYY-MM-DD", id="sermon_date")' in source
    assert 'yield Static("Pflichtangaben", id="metadata_required_heading", classes="metadata_section_heading")' in source
    assert 'yield Label("Titel", id="title_label")' in source
    assert 'yield Label("Hauptbibelstelle", id="bible_label")' in source
    assert 'yield Label("Redner / Leitung", id="speaker_label")' in source
    assert 'yield Static("Optionale Angaben", id="metadata_optional_heading", classes="metadata_section_heading")' in source
    assert 'yield Label("Besonderheit im Ordner", id="folder_note_label")' in source
    assert 'yield Button(back_label, id="back")' in source
    assert 'yield Button(cancel_label, id="cancel")' in source
    assert 'yield Button(next_label, id="next", variant="primary")' in source
    assert 'yield Static(build_tui_back_footnote(), classes="back_footnote")' in source


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
