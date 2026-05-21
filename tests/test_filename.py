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


def test_build_bibelstunde_filename_without_title(tmp_path: Path):
    info = SermonInfo(
        sermon_date=date(2026, 5, 20),
        title="",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        sermon_type="Bibelstunde",
    )

    assert build_media_filename(info, _config(tmp_path), ".mp4") == "Bibelstunde (Johannes 3,16)_Max Muster.mp4"


def test_build_vortrag_and_lobpreis_filenames(tmp_path: Path):
    vortrag = SermonInfo(date(2026, 5, 22), "Mission heute", "", "Max Muster", sermon_type="Vortrag")
    lobpreis = SermonInfo(date(2026, 5, 22), "Anbetungsabend", "", "Team", sermon_type="Lobpreis")

    assert build_media_filename(vortrag, _config(tmp_path), ".mp4") == "Vortrag (Mission heute)_Max Muster.mp4"
    assert build_media_filename(lobpreis, _config(tmp_path), ".mp4") == "Lobpreis (Anbetungsabend)_Team.mp4"


def test_build_sonstiges_filename_without_name(tmp_path: Path):
    info = SermonInfo(date(2026, 5, 22), "Gemeindeinfo", "", "", sermon_type="Sonstiges")

    assert build_media_filename(info, _config(tmp_path), ".mp3") == "Sonstiges (Gemeindeinfo).mp3"


def test_sanitize_windows_invalid_chars():
    assert sanitize_filename_part('Themenreihe: Gebet / Jüngerschaft?') == "Themenreihe- Gebet - Jüngerschaft"


def test_folder_suffix_is_sanitized():
    assert build_folder_suffix('Gastredner / Besuch: Jugend') == "Gastredner - Besuch- Jugend"
