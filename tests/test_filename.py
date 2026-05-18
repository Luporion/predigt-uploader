from datetime import date
from pathlib import Path

from predigt_uploader.filename import build_folder_suffix, build_media_filename, sanitize_filename_part
from predigt_uploader.models import AppConfig, SermonInfo


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
    )


def test_build_predigt_filename(tmp_path: Path):
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Heiligkeit",
        bible_reference="Jesaja 6,1-3",
        speaker="Eduard Wiebe",
    )
    assert (
        build_media_filename(info, _config(tmp_path), ".mp4")
        == "Predigt (Heiligkeit_Jesaja 6,1-3)_Eduard Wiebe.mp4"
    )


def test_sanitize_windows_invalid_chars():
    assert sanitize_filename_part('Themenreihe: Gebet / Jüngerschaft?') == "Themenreihe- Gebet - Jüngerschaft"


def test_folder_suffix_is_sanitized():
    assert build_folder_suffix('Gastredner / Besuch: Jugend') == "Gastredner - Besuch- Jugend"
