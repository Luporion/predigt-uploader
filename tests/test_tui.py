import sys
from datetime import date

from predigt_uploader import cli
from predigt_uploader.config import ConfigLoadError
from predigt_uploader.models import AppConfig, SermonInfo
from predigt_uploader.tui_app import (
    build_tui_file_candidates_lines,
    build_tui_field_labels,
    build_tui_preview_text,
    build_tui_settings_lines,
    build_tui_start_status_text,
    load_tui_config,
    service_type_by_name,
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
