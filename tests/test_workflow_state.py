from __future__ import annotations

import json
from datetime import date

import pytest

from predigt_uploader.models import SermonInfo
from predigt_uploader.companion_files import recording_summary_path, recording_workflow_state_path
from predigt_uploader.workflow_state import (
    WORKFLOW_STATE_FILENAME,
    StepState,
    VimeoState,
    WorkflowState,
    completed_local_workflow_state,
    load_workflow_state,
    resolve_workflow_state_path,
    save_workflow_state,
)


def _completed_state(tmp_path) -> WorkflowState:
    target = tmp_path / "2026" / "2026-08-30"
    return completed_local_workflow_state(
        sermon=SermonInfo(
            sermon_date=date(2026, 8, 30),
            sermon_type="Bibelstunde",
            title="Gnade und Wahrheit",
            bible_reference="Johannes 1,14",
            speaker="Max Müller",
            folder_note="Abend",
        ),
        raw_recording=tmp_path / "vmix" / "aufnahme.mp4",
        cut_mp4=tmp_path / "schnitt" / "aufnahme_geschnitten.mp4",
        target_folder=target,
        final_mp4=target / "Predigt.mp4",
        final_mp3=target / "Predigt.mp3",
        summary=recording_summary_path(target / "Predigt.mp4"),
    )


def test_workflow_state_round_trip_preserves_metadata_paths_and_pending_publishing(tmp_path):
    state = _completed_state(tmp_path)

    path = save_workflow_state(state)
    loaded = load_workflow_state(path)

    assert path == recording_workflow_state_path(state.paths.final_mp4)
    assert loaded.sermon == state.sermon
    assert loaded.paths == state.paths
    assert loaded.local_preparation.status == "complete"
    assert loaded.vimeo.step.status == "pending"
    assert loaded.vimeo.video_id is None
    assert loaded.vimeo.video_url is None
    assert loaded.vimeo.embed_html is None
    assert loaded.vimeo.target_folder_id is None
    assert loaded.vimeo.upload_status is None
    assert loaded.vimeo.transcode_status is None
    assert loaded.vimeo.folder_status is None
    assert loaded.vimeo.uploaded_at is None
    assert loaded.vimeo.upload_uri is None
    assert loaded.wordpress_audio.step.status == "pending"
    assert loaded.wordpress_audio.media_id is None
    assert loaded.wordpress_post.step.status == "pending"
    assert loaded.wordpress_post.post_id is None


def test_workflow_state_json_is_utf8_machine_readable_and_contains_no_secrets(tmp_path):
    path = save_workflow_state(_completed_state(tmp_path))

    text = path.read_text(encoding="utf-8")
    data = json.loads(text)

    assert data["sermon"]["speaker"] == "Max Müller"
    assert data["paths"]["target_folder"] == str(path.parent)
    assert "token" not in text.casefold()
    assert "password" not in text.casefold()
    assert "secret" not in text.casefold()
    assert not path.with_name(f".{path.name}.tmp").exists()


def test_workflow_state_loads_minimal_older_state_with_safe_defaults(tmp_path):
    path = tmp_path / WORKFLOW_STATE_FILENAME
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sermon": {"sermon_date": "2026-08-30", "title": "Titel"},
                "paths": {"target_folder": str(tmp_path)},
                "local_preparation": {"status": "complete"},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_workflow_state(path)

    assert loaded.schema_version == 1
    assert loaded.sermon.sermon_type == "Predigt"
    assert loaded.sermon.bible_reference == ""
    assert loaded.paths.final_mp4 is None
    assert loaded.vimeo.step.status == "pending"
    assert loaded.vimeo.player_embed_url is None
    assert loaded.vimeo.team_owner_user_id is None
    assert loaded.vimeo.upload_offset is None
    assert loaded.wordpress_audio.step.status == "pending"
    assert loaded.wordpress_post.step.status == "pending"

    migrated_path = save_workflow_state(loaded, path)
    assert load_workflow_state(migrated_path).schema_version == 4


def test_workflow_state_migrates_legacy_vimeo_folder_names(tmp_path):
    path = tmp_path / WORKFLOW_STATE_FILENAME
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "sermon": {"sermon_date": "2026-08-30"},
                "paths": {"target_folder": str(tmp_path)},
                "vimeo": {
                    "folder_id": "77",
                    "folder_uri": "/projects/77",
                    "folder_name": "Predigten",
                },
            }
        ),
        encoding="utf-8",
    )

    loaded = load_workflow_state(path)

    assert loaded.vimeo.target_folder_id == "77"
    assert loaded.vimeo.target_folder_uri == "/projects/77"
    assert loaded.vimeo.target_folder_name == "Predigten"


def test_workflow_state_rejects_unknown_step_status():
    with pytest.raises(ValueError, match="Unbekannter Workflow-Status"):
        StepState(status="uploaded")


def test_workflow_state_round_trip_preserves_vimeo_resume_folder_and_embed_data(tmp_path):
    original = _completed_state(tmp_path)
    state = original.__class__(
        **{
            **original.__dict__,
            "vimeo": VimeoState(
                step=StepState("in_progress"),
                video_id="900",
                video_uri="/videos/900",
                video_url="https://vimeo.com/900/hash",
                player_embed_url="https://player.vimeo.com/video/900?h=hash",
                embed_html='<iframe src="https://player.vimeo.com/video/900?h=hash"></iframe>',
                upload_status="in_progress",
                transcode_status="in_progress",
                uploaded_at="2026-08-31T01:23:45+00:00",
                target_folder_id="77",
                target_folder_uri="/projects/77",
                target_folder_name="Predigten",
                folder_status="verified",
                team_owner_user_id="42",
                upload_uri="https://files.tus.vimeo.com/files/abc",
                upload_offset=1024,
                upload_size=4096,
            ),
        }
    )

    path = save_workflow_state(state)
    loaded = load_workflow_state(path)

    assert loaded.vimeo == state.vimeo
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["vimeo"]["upload_status"] == "in_progress"
    assert data["vimeo"]["transcode_status"] == "in_progress"
    assert data["vimeo"]["folder_status"] == "verified"
    assert data["vimeo"]["uploaded_at"] == "2026-08-31T01:23:45+00:00"
    assert data["vimeo"]["target_folder_id"] == "77"
    assert "folder_id" not in data["vimeo"]
    assert "token" not in path.read_text(encoding="utf-8").casefold()


def test_workflow_state_requires_target_folder_for_implicit_save(tmp_path):
    state = WorkflowState(
        sermon=SermonInfo(date(2026, 8, 30), "", "", ""),
        paths=_completed_state(tmp_path).paths.__class__(),
    )

    with pytest.raises(ValueError, match="Zielordner"):
        save_workflow_state(state)


def test_save_refreshes_updated_at_for_each_persisted_transition(tmp_path):
    original = _completed_state(tmp_path)
    old = original.__class__(**{**original.__dict__, "updated_at": "2020-01-01T00:00:00+00:00"})

    path = save_workflow_state(old)

    assert load_workflow_state(path).updated_at != old.updated_at


def test_two_recordings_in_same_folder_have_distinct_companion_files(tmp_path):
    first = _completed_state(tmp_path)
    second_mp4 = first.paths.final_mp4.with_name("Bibelstunde.mp4")
    second = completed_local_workflow_state(
        sermon=first.sermon,
        target_folder=second_mp4.parent,
        final_mp4=second_mp4,
        final_mp3=second_mp4.with_suffix(".mp3"),
        summary=recording_summary_path(second_mp4),
    )

    first_path = save_workflow_state(first)
    second_path = save_workflow_state(second)

    assert first_path != second_path
    assert load_workflow_state(first_path).paths.final_mp4 == first.paths.final_mp4
    assert load_workflow_state(second_path).paths.final_mp4 == second_mp4
    assert first.paths.summary != second.paths.summary


def test_resolver_reuses_matching_legacy_state_but_not_unrelated_one(tmp_path):
    state = _completed_state(tmp_path)
    legacy = state.paths.target_folder / WORKFLOW_STATE_FILENAME
    save_workflow_state(state, legacy)

    assert resolve_workflow_state_path(state.paths.final_mp4) == legacy
    assert resolve_workflow_state_path(state.paths.final_mp4.with_name("Andere.mp4")) is None
