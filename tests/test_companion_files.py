from __future__ import annotations

from predigt_uploader.companion_files import recording_summary_path, recording_workflow_state_path


def test_companion_names_follow_final_mp4_stem(tmp_path):
    mp4 = tmp_path / "Predigt (Gnade_Johannes 1)_Max Müller.mp4"

    assert recording_summary_path(mp4).name == "Predigt (Gnade_Johannes 1)_Max Müller - Zusammenfassung.txt"
    assert recording_workflow_state_path(mp4).name == "Predigt (Gnade_Johannes 1)_Max Müller.predigt-workflow.json"


def test_long_companion_names_are_windows_safe_and_remain_unique(tmp_path):
    first = tmp_path / (("Sehr lange Predigt " * 20) + "A.mp4")
    second = tmp_path / (("Sehr lange Predigt " * 20) + "B.mp4")

    first_state = recording_workflow_state_path(first)
    second_state = recording_workflow_state_path(second)

    assert len(first_state.name) <= 255
    assert len(recording_summary_path(first).name) <= 255
    assert first_state != second_state
