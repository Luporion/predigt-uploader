from datetime import date
from pathlib import Path

from predigt_uploader.folders import resolve_folder, suggest_folder
from predigt_uploader.models import AppConfig, SermonInfo


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )


def test_suggest_folder_without_note(tmp_path: Path):
    info = SermonInfo(date(2026, 5, 24), "Titel", "Text", "Redner")
    assert suggest_folder(_config(tmp_path), info) == tmp_path / "Aufnahmen" / "2026" / "2026-05-24"


def test_suggest_folder_with_note(tmp_path: Path):
    info = SermonInfo(date(2026, 6, 7), "Titel", "Text", "Redner", folder_note="Pfingsten")
    assert suggest_folder(_config(tmp_path), info) == tmp_path / "Aufnahmen" / "2026" / "2026-06-07 - Pfingsten"


def test_suggest_folder_uses_year_folder_template(tmp_path: Path):
    info = SermonInfo(date(2026, 5, 17), "Titel", "Text", "Redner")
    config = _config(tmp_path)
    config = AppConfig(
        vmix_storage=config.vmix_storage,
        recordings_base=config.recordings_base,
        mp3_base=config.mp3_base,
        year_folder_template="{year} Video+Audio",
    )

    assert suggest_folder(config, info) == tmp_path / "Aufnahmen" / "2026 Video+Audio" / "2026-05-17"


def test_resolve_folder_missing(tmp_path: Path):
    info = SermonInfo(date(2026, 5, 24), "Titel", "Text", "Redner")
    result = resolve_folder(_config(tmp_path), info)
    assert result.status == "missing"
    assert result.candidates == ()


def test_resolve_folder_single_existing(tmp_path: Path):
    (tmp_path / "Aufnahmen" / "2026" / "2026-05-24").mkdir(parents=True)
    info = SermonInfo(date(2026, 5, 24), "Titel", "Text", "Redner")
    result = resolve_folder(_config(tmp_path), info)
    assert result.status == "single_existing"
    assert len(result.candidates) == 1


def test_resolve_folder_multiple_existing(tmp_path: Path):
    (tmp_path / "Aufnahmen" / "2026" / "2026-05-24").mkdir(parents=True)
    (tmp_path / "Aufnahmen" / "2026" / "2026-05-24 - Taufe").mkdir(parents=True)
    info = SermonInfo(date(2026, 5, 24), "Titel", "Text", "Redner")
    result = resolve_folder(_config(tmp_path), info)
    assert result.status == "multiple_existing"
    assert len(result.candidates) == 2
