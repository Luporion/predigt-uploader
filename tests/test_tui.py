import sys
from datetime import date

from predigt_uploader import cli
from predigt_uploader.models import AppConfig, SermonInfo
from predigt_uploader.tui_app import build_tui_preview_text, build_tui_settings_lines


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

    assert "MP4: Predigt (Lehre statt Leere_Johannes 3,16)_Max Muster.mp4" in text
    assert "MP3: Predigt (Lehre statt Leere_Johannes 3,16)_Max Muster.mp3" in text
    assert f"Zielordner: {tmp_path / 'Aufnahmen' / '2026' / '2026-05-24'}" in text


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
