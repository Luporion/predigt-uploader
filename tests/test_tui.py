import sys
from datetime import date

from predigt_uploader import cli
from predigt_uploader.config import ConfigLoadError
from predigt_uploader.models import AppConfig, SermonInfo
from predigt_uploader.tui_app import (
    build_tui_date_options,
    build_tui_file_choice_lines,
    build_tui_metadata_info,
    build_tui_file_candidates_lines,
    build_tui_mp4_file_rows,
    build_tui_mp4_selection_actions,
    build_tui_mp4_selection_config,
    build_tui_preparation,
    build_tui_preparation_text,
    build_tui_field_labels,
    build_tui_preview_text,
    build_tui_settings_lines,
    build_tui_start_status_text,
    build_tui_validation_text,
    default_tui_service_type_name,
    detect_tui_recording_date_from_filename,
    missing_tui_metadata_fields,
    newest_tui_mp4_candidates,
    newest_tui_mp4_candidate,
    load_tui_config,
    service_type_by_name,
    service_types_for_tui,
    tui_cut_mp4_folder,
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

    candidates = newest_tui_mp4_candidates(folder, search_text="Gottesdienst", limit=5)
    lines = build_tui_file_choice_lines(folder, search_text="Gottesdienst", limit=5)

    assert newer in candidates
    assert older in candidates
    assert other not in candidates
    assert newest_tui_mp4_candidate(folder) in {newer, other}
    assert any("Gottesdienst neu.mp4" in line for line in lines)


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


def test_tui_field_labels_mark_unneeded_and_optional_fields(tmp_path):
    config = AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )

    bibelstunde_labels = build_tui_field_labels(service_type_by_name(config, "Bibelstunde"))
    lobpreis_labels = build_tui_field_labels(service_type_by_name(config, "Lobpreis"))

    assert bibelstunde_labels["title"] == "Titel (nicht nötig)"
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
