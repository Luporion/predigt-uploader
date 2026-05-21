from datetime import date
from pathlib import Path

from predigt_uploader.filename import build_filename_preview, build_folder_suffix, build_media_filename, sanitize_filename_part
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


def test_filename_preview_shows_placeholders_for_empty_fields(tmp_path: Path):
    info = SermonInfo(date(2026, 5, 24), "", "", "", sermon_type="Predigt")

    preview = build_filename_preview(info, _config(tmp_path))

    assert preview.mp4 == "Predigt ([Titel]_[Bibelstelle])_[Redner].mp4"
    assert preview.mp3 == "Predigt ([Titel]_[Bibelstelle])_[Redner].mp3"


def test_filename_preview_updates_with_partial_fields(tmp_path: Path):
    info = SermonInfo(date(2026, 5, 24), "Lehre statt Leere", "", "", sermon_type="Predigt")

    preview = build_filename_preview(info, _config(tmp_path))

    assert preview.mp4 == "Predigt (Lehre statt Leere_[Bibelstelle])_[Redner].mp4"


def test_filename_preview_matches_final_filename_when_complete(tmp_path: Path):
    info = SermonInfo(date(2026, 5, 24), "Heiligkeit", "Jesaja 6,1-3", "Eduard Wiebe")

    preview = build_filename_preview(info, _config(tmp_path))

    assert preview.mp4 == build_media_filename(info, _config(tmp_path), ".mp4")
    assert preview.mp3 == build_media_filename(info, _config(tmp_path), ".mp3")


def test_filename_preview_uses_consistent_sanitizing(tmp_path: Path):
    info = SermonInfo(date(2026, 5, 24), "Gebet / Jüngerschaft?", "Jesaja 6:1-3", "Max <Muster>")

    preview = build_filename_preview(info, _config(tmp_path))

    assert preview.mp4 == "Predigt (Gebet - Jüngerschaft_Jesaja 6-1-3)_Max -Muster.mp4"


def test_filename_preview_covers_standard_service_types(tmp_path: Path):
    service_types = ("Predigt", "Bibelstunde", "Vortrag", "Lobpreis", "Gebetsstunde", "Zeugnis", "Seminar", "Sonstiges")

    previews = [
        build_filename_preview(SermonInfo(date(2026, 5, 22), "", "", "", sermon_type=service_type), _config(tmp_path)).mp4
        for service_type in service_types
    ]

    assert len(previews) == len(service_types)
    assert all(preview.endswith(".mp4") for preview in previews)


def test_sanitize_windows_invalid_chars():
    assert sanitize_filename_part('Themenreihe: Gebet / Jüngerschaft?') == "Themenreihe- Gebet - Jüngerschaft"


def test_folder_suffix_is_sanitized():
    assert build_folder_suffix('Gastredner / Besuch: Jugend') == "Gastredner - Besuch- Jugend"
