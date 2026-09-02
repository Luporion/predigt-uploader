from datetime import date
from dataclasses import replace
from pathlib import Path

import pytest

from predigt_uploader.models import AppConfig, SermonInfo
from predigt_uploader.processing import (
    MP4_ACTION_OVERWRITE,
    RAW_ACTION_COPY,
    RAW_ACTION_KEEP,
    build_prepared_recording_plan,
    build_processing_plan_text,
    execute_processing_plan,
    apply_output_filenames,
    next_available_numbered_path,
    planned_existing_output_renames,
    unique_output_name_suggestions,
    validate_windows_filename,
    raw_action_label,
)
from predigt_uploader.workflow_state import load_workflow_state
from predigt_uploader.companion_files import recording_summary_path, recording_workflow_state_path
from predigt_uploader.report import build_summary_text, write_summary_file


def _config(tmp_path: Path, *, open_target_folder: bool = False) -> AppConfig:
    return AppConfig(
        vmix_storage=tmp_path / "vmix",
        recordings_base=tmp_path / "Aufnahmen",
        mp3_base=tmp_path / "Predigten",
        open_target_folder=open_target_folder,
    )


def test_prepared_processing_plan_uses_shared_predigt_paths(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = _config(tmp_path)
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
        folder_note="Taufe",
    )

    plan = build_prepared_recording_plan(config=config, source_mp4=source, info=info)

    assert plan.target_folder == tmp_path / "Aufnahmen" / "2026" / "2026-05-24 - Taufe"
    assert plan.target_mp4.name == "Predigt (Lehre statt Leere_Johannes 3,16)_Max Muster.mp4"
    assert plan.target_mp3.name == "Predigt (Lehre statt Leere_Johannes 3,16)_Max Muster.mp3"
    assert plan.summary_path == recording_summary_path(plan.target_mp4)
    assert plan.processing_plan.target_mp4 == plan.target_mp4


def test_prepared_processing_plan_supports_target_folder_override(tmp_path):
    source = tmp_path / "quelle.mp4"
    target_folder = tmp_path / "Eigener Zielordner"
    source.write_bytes(b"video")
    config = _config(tmp_path)
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Lehre statt Leere",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )

    plan = build_prepared_recording_plan(
        config=config,
        source_mp4=source,
        info=info,
        target_folder_override=target_folder,
    )

    assert plan.target_folder == target_folder
    assert plan.target_mp4 == target_folder / "Predigt (Lehre statt Leere_Johannes 3,16)_Max Muster.mp4"
    assert plan.target_mp3 == target_folder / "Predigt (Lehre statt Leere_Johannes 3,16)_Max Muster.mp3"
    assert plan.summary_path == recording_summary_path(plan.target_mp4)


def test_prepared_processing_plan_supports_bibelstunde_with_and_without_title(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = _config(tmp_path)
    with_title = SermonInfo(
        sermon_date=date(2026, 5, 20),
        sermon_type="Bibelstunde",
        title="Gottes Treue",
        bible_reference="Psalm 23",
        speaker="Max Muster",
    )
    without_title = SermonInfo(
        sermon_date=date(2026, 5, 20),
        sermon_type="Bibelstunde",
        title="",
        bible_reference="Psalm 23",
        speaker="Max Muster",
    )

    title_plan = build_prepared_recording_plan(config=config, source_mp4=source, info=with_title)
    no_title_plan = build_prepared_recording_plan(config=config, source_mp4=source, info=without_title)

    assert title_plan.target_mp4.name == "Bibelstunde (Gottes Treue_Psalm 23)_Max Muster.mp4"
    assert no_title_plan.target_mp4.name == "Bibelstunde (Psalm 23)_Max Muster.mp4"


def test_prepared_processing_plan_supports_gebetsstunde_paths(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = _config(tmp_path)
    info = SermonInfo(
        sermon_date=date(2026, 5, 22),
        sermon_type="Gebetsstunde",
        title="Gebet und Dank",
        bible_reference="",
        speaker="",
    )

    plan = build_prepared_recording_plan(config=config, source_mp4=source, info=info)

    assert plan.target_folder == tmp_path / "Aufnahmen" / "2026" / "2026-05-22"
    assert plan.target_mp4.name == "Gebetsstunde (Gebet und Dank).mp4"
    assert plan.target_mp3.name == "Gebetsstunde (Gebet und Dank).mp3"


def test_processing_plan_text_shows_raw_action_and_warnings(tmp_path):
    source = tmp_path / "quelle.mp4"
    raw = tmp_path / "raw.mp4"
    source.write_bytes(b"video")
    raw.write_bytes(b"raw")
    config = _config(tmp_path)
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )

    plan = build_prepared_recording_plan(
        config=config,
        source_mp4=source,
        raw_recording=raw,
        raw_action=RAW_ACTION_KEEP,
        info=info,
        warnings=("Bitte pruefen.",),
    )
    text = build_processing_plan_text(plan)

    assert raw_action_label(plan.raw_action, plan.raw_recording) == "Rohaufnahme liegen lassen"
    assert f"Diese Datei wird als finale Predigt verwendet: {source}" in text
    assert f"Diese Rohaufnahme wird danach verschoben/kopiert/liegen gelassen: {raw}" in text
    assert "Rohaufnahme-Aktion: Rohaufnahme liegen lassen" in text
    assert "Bitte pruefen." in text


def test_execute_processing_plan_copies_mp4_creates_mp3_summary_and_opens_folder(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = _config(tmp_path, open_target_folder=True)
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )
    plan = build_prepared_recording_plan(config=config, source_mp4=source, info=info)
    opened: list[Path] = []

    def fake_convert(_source: Path, target: Path, _config: AppConfig) -> None:
        target.write_bytes(b"mp3")

    result = execute_processing_plan(
        plan,
        config,
        folder_opener=opened.append,
        mp3_converter=fake_convert,
        ffmpeg_checker=lambda _config: True,
    )

    assert result.success is True
    assert plan.target_mp4.read_bytes() == b"video"
    assert plan.target_mp3.read_bytes() == b"mp3"
    assert plan.summary_path.exists()
    assert opened == [plan.target_folder]
    assert "Zielordner wird erstellt/geprueft." in result.messages
    assert "MP4 wird kopiert." in result.messages
    assert "MP3 wird erstellt." in result.messages
    assert "Zusammenfassung wird geschrieben." in result.messages
    assert result.messages[-1] == "Fertig."
    assert result.workflow_state_path == recording_workflow_state_path(plan.target_mp4)
    state = load_workflow_state(result.workflow_state_path)
    assert state.local_preparation.status == "complete"
    assert state.paths.final_mp4 == plan.target_mp4
    assert state.paths.final_mp3 == plan.target_mp3
    assert state.paths.summary == plan.summary_path
    assert state.vimeo.step.status == "pending"


def test_execute_processing_plan_keeps_local_success_when_state_file_cannot_be_written(monkeypatch, tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = _config(tmp_path)
    info = SermonInfo(date(2026, 5, 24), "Lehre", "Johannes 3,16", "Max Muster")
    plan = build_prepared_recording_plan(config=config, source_mp4=source, info=info)

    def fail_state_write(_state):
        raise PermissionError("Statusdatei gesperrt")

    monkeypatch.setattr("predigt_uploader.processing.save_workflow_state", fail_state_write)

    result = execute_processing_plan(
        plan,
        config,
        mp3_converter=lambda _source, target, _config: target.write_bytes(b"mp3"),
        ffmpeg_checker=lambda _config: True,
    )

    assert result.success is True
    assert result.workflow_state_path is None
    assert plan.target_mp4.exists()
    assert plan.target_mp3.exists()
    assert plan.summary_path.exists()
    assert any("Mediendateien bleiben erhalten" in message for message in result.messages)


def test_summary_text_and_file_keep_utf8_umlauts(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = _config(tmp_path)
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Übertragung später einfügen",
        bible_reference="Johannes 3,16",
        speaker="Max Müller",
    )
    plan = build_prepared_recording_plan(config=config, source_mp4=source, info=info)
    plan.target_folder.mkdir(parents=True)

    text = build_summary_text(plan.processing_plan)
    write_summary_file(plan.processing_plan)
    written_text = plan.summary_path.read_text(encoding="utf-8-sig")

    assert "übertragen" in text
    assert "später" in text
    assert "einfügen" in text
    assert "Übertragung später einfügen" in written_text
    assert "Max Müller" in written_text
    assert plan.summary_path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_execute_processing_plan_can_copy_raw_recording(tmp_path):
    source = tmp_path / "quelle.mp4"
    raw = tmp_path / "raw.mp4"
    source.write_bytes(b"video")
    raw.write_bytes(b"raw")
    config = _config(tmp_path)
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )
    plan = build_prepared_recording_plan(
        config=config,
        source_mp4=source,
        raw_recording=raw,
        raw_action=RAW_ACTION_COPY,
        info=info,
    )

    result = execute_processing_plan(
        plan,
        config,
        mp3_converter=lambda _source, target, _config: target.write_bytes(b"mp3"),
        ffmpeg_checker=lambda _config: True,
    )

    assert result.success is True
    assert raw.exists()
    assert (plan.target_folder / "raw.mp4").read_bytes() == b"raw"
    assert result.archived_raw_recording == plan.target_folder / "raw.mp4"
    assert "Rohaufnahme wird kopiert." in result.messages


def test_execute_processing_plan_uses_cut_source_for_final_media_and_raw_separately(tmp_path):
    cut = tmp_path / "schnitt" / "predigt_geschnitten.mp4"
    raw = tmp_path / "vmix" / "rohaufnahme.mp4"
    cut.parent.mkdir()
    raw.parent.mkdir()
    cut.write_bytes(b"cut-video")
    raw.write_bytes(b"raw-video")
    config = _config(tmp_path)
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )
    plan = build_prepared_recording_plan(
        config=config,
        source_mp4=cut,
        raw_recording=raw,
        raw_action=RAW_ACTION_COPY,
        info=info,
    )
    converter_sources: list[Path] = []

    def fake_convert(source: Path, target: Path, _config: AppConfig) -> None:
        converter_sources.append(source)
        target.write_bytes(source.read_bytes() + b"-mp3")

    result = execute_processing_plan(
        plan,
        config,
        mp3_converter=fake_convert,
        ffmpeg_checker=lambda _config: True,
    )

    assert result.success is True
    assert plan.source_mp4 == cut
    assert plan.raw_recording == raw
    assert plan.target_mp4.read_bytes() == b"cut-video"
    assert plan.target_mp3.read_bytes() == b"cut-video-mp3"
    assert converter_sources == [plan.target_mp4]
    assert (plan.target_folder / raw.name).read_bytes() == b"raw-video"


def test_execute_processing_plan_does_not_overwrite_existing_mp3_without_permission(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = _config(tmp_path)
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )
    plan = build_prepared_recording_plan(config=config, source_mp4=source, info=info)
    plan.target_folder.mkdir(parents=True)
    plan.target_mp3.write_bytes(b"alte mp3")

    result = execute_processing_plan(
        plan,
        config,
        mp3_converter=lambda _source, target, _config: target.write_bytes(b"neue mp3"),
        ffmpeg_checker=lambda _config: True,
    )

    assert result.success is False
    assert plan.target_mp3.read_bytes() == b"alte mp3"
    assert result.error == "Eine Zieldatei existiert bereits. Bitte pruefe den Zielordner oder waehle einen anderen Namen."


def test_execute_processing_plan_can_overwrite_existing_outputs_after_confirmation(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = _config(tmp_path)
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )
    plan = build_prepared_recording_plan(
        config=config,
        source_mp4=source,
        info=info,
        mp4_action=MP4_ACTION_OVERWRITE,
        overwrite_existing_outputs=True,
    )
    plan.target_folder.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"alte mp4")
    plan.target_mp3.write_bytes(b"alte mp3")
    plan.summary_path.write_text("alte Zusammenfassung", encoding="utf-8")

    result = execute_processing_plan(
        plan,
        config,
        mp3_converter=lambda _source, target, _config: target.write_bytes(b"neue mp3"),
        ffmpeg_checker=lambda _config: True,
    )

    assert result.success is True
    assert plan.target_mp4.read_bytes() == b"video"
    assert plan.target_mp3.read_bytes() == b"neue mp3"
    assert plan.summary_path.read_text(encoding="utf-8-sig")


def test_execute_processing_plan_backs_up_existing_outputs_before_writing(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video-neu")
    config = _config(tmp_path)
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )
    plan = build_prepared_recording_plan(
        config=config,
        source_mp4=source,
        info=info,
        backup_existing_outputs=True,
    )
    plan.target_folder.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"video-alt")
    plan.target_mp3.write_bytes(b"mp3-alt")
    plan.summary_path.write_text("zusammenfassung-alt", encoding="utf-8")

    result = execute_processing_plan(
        plan,
        config,
        mp3_converter=lambda _source, target, _config: target.write_bytes(b"mp3-neu"),
        ffmpeg_checker=lambda _config: True,
    )

    assert result.success is True
    assert plan.target_mp4.read_bytes() == b"video-neu"
    assert plan.target_mp3.read_bytes() == b"mp3-neu"
    assert len(tuple(plan.target_folder.glob(f"{plan.target_mp4.stem}__alt-*.mp4"))) == 1
    assert len(tuple(plan.target_folder.glob(f"{plan.target_mp3.stem}__alt-*.mp3"))) == 1
    assert len(tuple(plan.target_folder.glob(f"{plan.summary_path.stem}__alt-*.txt"))) == 1
    assert "Vorhandene Ziel-Dateien werden gesichert." in result.messages


def test_execute_processing_plan_writes_custom_summary_path(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    config = _config(tmp_path)
    info = SermonInfo(
        sermon_date=date(2026, 5, 24),
        title="Lehre",
        bible_reference="Johannes 3,16",
        speaker="Max Muster",
    )
    plan = build_prepared_recording_plan(config=config, source_mp4=source, info=info)
    default_summary = plan.summary_path
    custom_summary = plan.target_folder / "predigt-zusammenfassung - Korrektur.txt"
    plan = replace(plan, summary_path=custom_summary)

    result = execute_processing_plan(
        plan,
        config,
        mp3_converter=lambda _source, target, _config: target.write_bytes(b"mp3"),
        ffmpeg_checker=lambda _config: True,
    )

    assert result.success is True
    assert custom_summary.exists()
    assert not default_summary.exists()


def test_two_recordings_in_same_day_folder_keep_separate_summaries_and_states(tmp_path):
    config = _config(tmp_path)
    target = tmp_path / "Aufnahmen" / "2026" / "2026-05-24"
    source_one = tmp_path / "quelle-1.mp4"
    source_two = tmp_path / "quelle-2.mp4"
    source_one.write_bytes(b"video-1")
    source_two.write_bytes(b"video-2")
    first = build_prepared_recording_plan(
        config=config,
        source_mp4=source_one,
        info=SermonInfo(date(2026, 5, 24), "Erste", "Johannes 1", "Max Muster"),
        target_folder_override=target,
    )
    second = build_prepared_recording_plan(
        config=config,
        source_mp4=source_two,
        info=SermonInfo(date(2026, 5, 24), "Zweite", "Johannes 2", "Anna Beispiel"),
        target_folder_override=target,
    )

    first_result = execute_processing_plan(
        first,
        config,
        mp3_converter=lambda _source, output, _config: output.write_bytes(b"mp3-1"),
        ffmpeg_checker=lambda _config: True,
    )
    second_result = execute_processing_plan(
        second,
        config,
        mp3_converter=lambda _source, output, _config: output.write_bytes(b"mp3-2"),
        ffmpeg_checker=lambda _config: True,
    )

    assert first_result.success and second_result.success
    assert first.summary_path != second.summary_path
    assert first_result.workflow_state_path != second_result.workflow_state_path
    assert first.summary_path.is_file() and second.summary_path.is_file()
    assert load_workflow_state(first_result.workflow_state_path).paths.final_mp4 == first.target_mp4
    assert load_workflow_state(second_result.workflow_state_path).paths.final_mp4 == second.target_mp4


def test_unique_output_names_use_numbered_windows_safe_suggestions(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    plan = build_prepared_recording_plan(
        config=_config(tmp_path),
        source_mp4=source,
        info=SermonInfo(date(2026, 5, 24), "Lehre", "Johannes 3,16", "Max Muster"),
    )
    plan.target_folder.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"alt")
    plan.target_mp4.with_name(f"{plan.target_mp4.stem} (2).mp4").write_bytes(b"auch alt")
    plan.target_mp3.write_bytes(b"alt")

    suggestions = unique_output_name_suggestions(plan)

    assert suggestions["mp4"].endswith(" (3).mp4")
    assert suggestions["mp3"].endswith(" (2).mp3")
    assert suggestions["summary"] == plan.summary_path.name


def test_apply_output_filenames_accepts_custom_unique_names_and_preserves_extensions(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    plan = build_prepared_recording_plan(
        config=_config(tmp_path),
        source_mp4=source,
        info=SermonInfo(date(2026, 5, 24), "Lehre", "Johannes 3,16", "Max Muster"),
    )

    renamed = apply_output_filenames(
        plan,
        mp4_filename="Predigt neu.mp4",
        mp3_filename="Predigt neu.mp3",
        summary_filename="Zusammenfassung neu.txt",
    )

    assert renamed.target_mp4.name == "Predigt neu.mp4"
    assert renamed.target_mp3.name == "Predigt neu.mp3"
    assert renamed.summary_path.name == "Zusammenfassung neu.txt"
    assert renamed.overwrite_existing_outputs is False


@pytest.mark.parametrize(
    ("filename", "extension"),
    [
        ("Predigt?.mp4", ".mp4"),
        ("CON.mp4", ".mp4"),
        ("Predigt.mp3", ".mp4"),
        ("Predigt. ", ".mp4"),
    ],
)
def test_validate_windows_filename_rejects_invalid_names(filename, extension):
    with pytest.raises(ValueError):
        validate_windows_filename(filename, expected_suffix=extension)


def test_apply_output_filenames_rechecks_custom_name_collision(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video")
    plan = build_prepared_recording_plan(
        config=_config(tmp_path),
        source_mp4=source,
        info=SermonInfo(date(2026, 5, 24), "Lehre", "Johannes 3,16", "Max Muster"),
    )
    plan.target_folder.mkdir(parents=True)
    (plan.target_folder / "Schon da.mp4").write_bytes(b"alt")

    with pytest.raises(FileExistsError, match="Schon da.mp4"):
        apply_output_filenames(
            plan,
            mp4_filename="Schon da.mp4",
            mp3_filename="Neu.mp3",
            summary_filename="Neu.txt",
        )


def test_planned_existing_renames_are_explicit_and_do_not_change_files_before_execution(tmp_path):
    source = tmp_path / "quelle.mp4"
    source.write_bytes(b"video-neu")
    config = _config(tmp_path)
    plan = build_prepared_recording_plan(
        config=config,
        source_mp4=source,
        info=SermonInfo(date(2026, 5, 24), "Lehre", "Johannes 3,16", "Max Muster"),
    )
    plan.target_folder.mkdir(parents=True)
    plan.target_mp4.write_bytes(b"video-alt")
    plan.target_mp3.write_bytes(b"mp3-alt")

    renames = planned_existing_output_renames(plan)

    assert [(old.name, new.name) for old, new in renames] == [
        (plan.target_mp4.name, f"{plan.target_mp4.stem}__alt.mp4"),
        (plan.target_mp3.name, f"{plan.target_mp3.stem}__alt.mp3"),
    ]
    assert plan.target_mp4.read_bytes() == b"video-alt"
    assert not renames[0][1].exists()

    confirmed = replace(plan, backup_existing_outputs=True, existing_output_renames=renames)
    result = execute_processing_plan(
        confirmed,
        config,
        mp3_converter=lambda _source, target, _config: target.write_bytes(b"mp3-neu"),
        ffmpeg_checker=lambda _config: True,
    )
    assert result.success
    assert renames[0][1].read_bytes() == b"video-alt"
    assert renames[1][1].read_bytes() == b"mp3-alt"
