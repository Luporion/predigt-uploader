from __future__ import annotations

import json
from datetime import date

import pytest

from predigt_uploader.models import SermonInfo
from predigt_uploader.workflow_state import (
    WORKFLOW_STATE_FILENAME,
    StepState,
    VimeoState,
    WorkflowState,
    completed_local_workflow_state,
    load_workflow_state,
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
        summary=target / "predigt-zusammenfassung.txt",
    )


def test_workflow_state_round_trip_preserves_metadata_paths_and_pending_publishing(tmp_path):
    state = _completed_state(tmp_path)

    path = save_workflow_state(state)
    loaded = load_workflow_state(path)

    assert path.name == WORKFLOW_STATE_FILENAME
    assert loaded.sermon == state.sermon
    assert loaded.paths == state.paths
    assert loaded.local_preparation.status == "complete"
    assert loaded.vimeo.step.status == "pending"
    assert loaded.vimeo.video_id is None
    assert loaded.vimeo.video_url is None
    assert loaded.vimeo.embed_html is None
    assert loaded.vimeo.folder_id is None
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
    assert load_workflow_state(migrated_path).schema_version == 2


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
                folder_id="77",
                folder_uri="/projects/77",
                folder_name="Predigten",
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
