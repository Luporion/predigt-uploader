from datetime import date
from pathlib import Path

from predigt_uploader.cli import _ask_mp4_path, _ask_required, _select_target_folder
from predigt_uploader.models import AppConfig, SermonInfo


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
