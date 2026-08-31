from __future__ import annotations

import json

from predigt_uploader.speaker_history import SpeakerHistory, normalize_speaker_name


def test_speaker_history_normalizes_deduplicates_and_persists(tmp_path):
    path = tmp_path / "speakers.json"
    history = SpeakerHistory(path)

    history.add("  Max   Müller ")
    history.add("max müller")
    history.add("Anna Beispiel")

    assert history.list() == ("Anna Beispiel", "Max Müller")
    assert SpeakerHistory(path).list() == history.list()
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1


def test_speaker_history_suggests_without_autocorrecting(tmp_path):
    history = SpeakerHistory(tmp_path / "speakers.json")
    history.add("Max Müller")
    history.add("Maria Muster")
    history.add("Erika Max")

    assert history.suggest("ma") == ("Maria Muster", "Max Müller", "Erika Max")
    assert normalize_speaker_name("  Neuer   Name ") == "Neuer Name"


def test_speaker_history_removes_case_insensitively(tmp_path):
    history = SpeakerHistory(tmp_path / "speakers.json")
    history.add("Max Müller")

    assert history.remove("max müller") == ()
    assert history.list() == ()
