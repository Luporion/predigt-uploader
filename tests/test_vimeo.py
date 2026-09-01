from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from predigt_uploader import cli
from predigt_uploader.models import AppConfig, SermonInfo, VimeoConfig
from predigt_uploader.publishing.vimeo import (
    RequestsVimeoTransport,
    VimeoApiError,
    VimeoConfigurationError,
    VimeoCredentialError,
    VimeoEmbedError,
    VimeoFolderError,
    VimeoProgress,
    VimeoPublishingService,
    VimeoStateConflictError,
    VimeoUploadError,
    load_vimeo_token,
)
from predigt_uploader.credentials import CredentialNotConfiguredError
from predigt_uploader.publishing.vimeo_smoke import (
    VimeoSmokeTestError,
    create_smoke_test_clip,
    run_vimeo_smoke_test,
)
from predigt_uploader.workflow_state import (
    StepState,
    VimeoState,
    WorkflowPaths,
    WorkflowState,
    load_workflow_state,
    save_workflow_state,
)


TOKEN = "streng-geheimer-test-token"
OWNER_ID = "42"
FOLDER_ID = "77"
VIDEO_ID = "900"
UPLOAD_URL = "https://files.tus.vimeo.com/files/abc"


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.offset = 0
        self.total = 0
        self.member = False
        self.owner_can_upload = True
        self.owner_response_uri = f"/users/{OWNER_ID}"
        self.folder_can_add = True
        self.folder_exists = True
        self.folder_name = "Predigten"
        self.folder_owner_uri = f"/users/{OWNER_ID}"
        self.assign_fails = False
        self.patch_failures = 0
        self.remote_upload_status = "complete"
        self.embed_html: str | None = '<iframe src="https://player.vimeo.com/video/900"></iframe>'
        self.player_embed_url: str | None = "https://player.vimeo.com/video/900"
        self.oembed_html: str | None = None
        self.max_source_read = 0
        self.create_payload: Mapping[str, Any] | None = None
        self.transcode_statuses = ["complete"]
        self.video_get_count = 0
        self.remote_name = "PredigtUploader Vimeo Test"
        self.privacy_view = "unlisted"
        self.privacy_embed = "whitelist"
        self.embed_domains = ["gemeinde.example"]
        self.deleted_paths: list[str] = []

    def get_json(self, path_or_url: str, *, params: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        self.calls.append(("GET", path_or_url))
        if path_or_url == "/me":
            return {"uri": "/users/5", "name": "Teammitglied"}
        if path_or_url == f"/users/{OWNER_ID}":
            options = ["GET", "POST"] if self.owner_can_upload else ["GET"]
            return {
                "uri": self.owner_response_uri,
                "name": "Gemeinde-Team",
                "metadata": {"connections": {"videos": {"options": options}}},
            }
        if path_or_url == f"/users/{OWNER_ID}/folders":
            return {"data": [self._folder()], "paging": {"next": None}}
        if path_or_url == f"/users/{OWNER_ID}/folders/{FOLDER_ID}":
            if not self.folder_exists:
                raise VimeoApiError("nicht gefunden", "HTTP 404", status_code=404)
            return self._folder()
        if path_or_url == f"/videos/{VIDEO_ID}":
            self.video_get_count += 1
            return self._video()
        if path_or_url == f"/videos/{VIDEO_ID}/privacy/domains":
            return {
                "data": [{"domain": domain} for domain in self.embed_domains],
                "paging": {"next": None},
            }
        if path_or_url == f"/users/{OWNER_ID}/projects/{FOLDER_ID}/videos":
            data = [{"uri": f"/videos/{VIDEO_ID}"}] if self.member else []
            return {"data": data, "paging": {"next": None}}
        raise AssertionError(f"Unerwarteter GET: {path_or_url}")

    def post_json(self, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append(("POST_JSON", path))
        assert path == "/me/videos"
        assert payload["upload"]["approach"] == "tus"
        self.create_payload = payload
        self.total = int(payload["upload"]["size"])
        return {
            "uri": f"/videos/{VIDEO_ID}",
            "link": f"https://vimeo.com/{VIDEO_ID}/unlisted-hash",
            "upload": {"approach": "tus", "upload_link": UPLOAD_URL},
        }

    def post_empty(self, path: str, payload: Mapping[str, Any]) -> None:
        self.calls.append(("POST_EMPTY", path))
        assert path == f"/users/{OWNER_ID}/projects/{FOLDER_ID}/items"
        assert payload == {"items": [{"uri": f"/videos/{VIDEO_ID}"}]}
        if self.assign_fails:
            raise VimeoApiError("abgelehnt", "HTTP 403", status_code=403)
        self.member = True

    def delete(self, path: str) -> None:
        self.calls.append(("DELETE", path))
        self.deleted_paths.append(path)

    def head_upload(self, upload_url: str) -> tuple[int, int]:
        self.calls.append(("HEAD", upload_url))
        return self.offset, self.total

    def patch_upload(
        self,
        upload_url: str,
        *,
        offset: int,
        source,
        length: int,
        read_size: int,
        progress=None,
    ) -> int:
        self.calls.append(("PATCH", upload_url))
        if self.patch_failures:
            self.patch_failures -= 1
            raise VimeoApiError("Netzwerkfehler", "temporär")
        read_total = 0
        while read_total < length:
            data = source.read(min(read_size, length - read_total))
            self.max_source_read = max(self.max_source_read, len(data))
            if not data:
                break
            read_total += len(data)
            if progress:
                progress(read_total)
        self.offset = offset + read_total
        return self.offset

    def get_oembed(self, video_url: str) -> Mapping[str, Any]:
        self.calls.append(("OEMBED", video_url))
        return {"html": self.oembed_html} if self.oembed_html else {}

    def _folder(self) -> Mapping[str, Any]:
        options = ["GET", "POST"] if self.folder_can_add else ["GET"]
        return {
            "uri": f"/projects/{FOLDER_ID}",
            "name": self.folder_name,
            "user": {"uri": self.folder_owner_uri},
            "metadata": {
                "connections": {
                    "parent_folder": {"uri": "/folders/12"},
                    "items": {"options": options},
                }
            },
        }

    def _video(self) -> Mapping[str, Any]:
        transcode_index = min(max(self.video_get_count - 1, 0), len(self.transcode_statuses) - 1)
        return {
            "uri": f"/videos/{VIDEO_ID}",
            "link": f"https://vimeo.com/{VIDEO_ID}/unlisted-hash",
            "name": self.remote_name,
            "upload": {"status": self.remote_upload_status},
            "transcode": {"status": self.transcode_statuses[transcode_index]},
            "player_embed_url": self.player_embed_url,
            "embed": {"html": self.embed_html},
            "privacy": {"view": self.privacy_view, "embed": self.privacy_embed},
            "parent_project": {"uri": f"/projects/{FOLDER_ID}"} if self.member else None,
        }


def _config(**changes: str) -> VimeoConfig:
    values = {
        "team_owner_user_id": OWNER_ID,
        "target_folder_id": FOLDER_ID,
        "target_folder_name": "Predigten",
    }
    values.update(changes)
    return VimeoConfig(**values)


def _state_path(tmp_path: Path, *, local_status: str = "complete", vimeo: VimeoState | None = None) -> Path:
    video = tmp_path / "Predigt (Gnade_Johannes 1,14)_Max Müller.mp4"
    video.write_bytes(b"0123456789abcdef")
    state_path = tmp_path / "predigt-workflow.json"
    state = WorkflowState(
        sermon=SermonInfo(date(2026, 8, 30), "Gnade", "Johannes 1,14", "Max Müller"),
        paths=WorkflowPaths(final_mp4=video, target_folder=tmp_path),
        local_preparation=StepState(local_status),
        vimeo=vimeo or VimeoState(),
    )
    save_workflow_state(state, state_path)
    return state_path


def _service(transport: FakeTransport, config: VimeoConfig | None = None, **kwargs) -> VimeoPublishingService:
    return VimeoPublishingService(
        config or _config(),
        TOKEN,
        transport,
        chunk_size=5,
        read_size=2,
        sleep=lambda _seconds: None,
        **kwargs,
    )


def _app_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        vmix_storage=tmp_path,
        recordings_base=tmp_path,
        mp3_base=tmp_path,
        ffmpeg_path="ffmpeg",
        vimeo=_config(),
    )


def _fake_ffmpeg(targets: list[Path] | None = None):
    def run(command, **_kwargs):
        target = Path(command[-1])
        target.write_bytes(b"kleiner-gueltiger-testclip")
        if targets is not None:
            targets.append(target)
        return SimpleNamespace(returncode=0, stderr="")

    return run


class _FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def test_missing_token_is_rejected_without_echoing_a_secret():
    manager = SimpleNamespace(
        resolve=lambda: (_ for _ in ()).throw(CredentialNotConfiguredError("nicht eingerichtet"))
    )
    with pytest.raises(VimeoCredentialError) as error:
        load_vimeo_token(credential_manager=manager)

    assert "PREDIGT_UPLOADER_VIMEO_TOKEN" in error.value.admin_hint
    assert TOKEN not in str(error.value)


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (_config(team_owner_user_id=""), "Team-Owner"),
        (_config(target_folder_id=""), "Zielordner-ID"),
        (_config(team_owner_user_id="kein-name"), "numerische ID"),
        (_config(target_folder_id="Predigten"), "numerische ID"),
    ],
)
def test_preflight_requires_explicit_owner_and_folder_ids(config, message):
    with pytest.raises(VimeoConfigurationError, match=message):
        _service(FakeTransport(), config).preflight()


def test_diagnose_can_show_authenticated_identity_before_owner_is_known():
    report = _service(FakeTransport(), _config(team_owner_user_id="", target_folder_id="")).diagnose()

    assert report.authenticated_user_uri == "/users/5"
    assert report.team_owner_user_id == ""
    assert report.folders == ()


def test_diagnose_lists_team_folders_with_ids_uris_and_parent():
    report = _service(FakeTransport()).diagnose()

    assert report.team_owner_user_id == OWNER_ID
    assert report.folders[0].folder_id == FOLDER_ID
    assert report.folders[0].uri == f"/projects/{FOLDER_ID}"
    assert report.folders[0].parent_folder_uri == "/folders/12"


def test_target_folder_must_exist_and_be_accessible():
    transport = FakeTransport()
    transport.folder_exists = False

    with pytest.raises(VimeoFolderError, match="existiert nicht|zugreifbar"):
        _service(transport).preflight()


def test_failed_target_preflight_does_not_mark_upload_in_progress(tmp_path):
    path = _state_path(tmp_path)
    transport = FakeTransport()
    transport.folder_exists = False

    with pytest.raises(VimeoFolderError):
        _service(transport).publish(path)

    assert load_workflow_state(path).vimeo.step.status == "pending"
    assert not any(method == "POST_JSON" for method, _ in transport.calls)


def test_preflight_does_not_treat_connection_options_as_hard_capabilities():
    no_upload = FakeTransport()
    no_upload.owner_can_upload = False
    no_upload.folder_can_add = False

    result = _service(no_upload).preflight()

    assert result.permission_note == "Die eigentliche Upload-Berechtigung wird beim Upload geprüft."


def test_preflight_rejects_wrong_owner_or_control_name():
    wrong_owner_response = FakeTransport()
    wrong_owner_response.owner_response_uri = "/users/999"
    with pytest.raises(VimeoConfigurationError, match="Team-Owner"):
        _service(wrong_owner_response).preflight()

    wrong_owner = FakeTransport()
    wrong_owner.folder_owner_uri = "/users/999"
    with pytest.raises(VimeoFolderError, match="Team-Zugehörigkeit"):
        _service(wrong_owner).preflight()

    wrong_name = FakeTransport()
    wrong_name.folder_name = "Privat"
    with pytest.raises(VimeoFolderError, match="Ordnernamen"):
        _service(wrong_name).preflight()


def test_publish_requires_completed_local_preparation(tmp_path):
    path = _state_path(tmp_path, local_status="pending")

    with pytest.raises(VimeoStateConflictError, match="noch nicht vollständig"):
        _service(FakeTransport()).publish(path)


def test_publish_requires_existing_nonempty_final_mp4(tmp_path):
    path = _state_path(tmp_path)
    load = load_workflow_state(path)
    load.paths.final_mp4.unlink()

    with pytest.raises(VimeoStateConflictError, match="nicht gefunden"):
        _service(FakeTransport()).publish(path)


def test_complete_state_checks_remote_and_never_creates_duplicate(tmp_path):
    path = _state_path(tmp_path, vimeo=VimeoState(step=StepState("complete"), video_id=VIDEO_ID))
    transport = FakeTransport()

    with pytest.raises(VimeoStateConflictError, match="bereits zu Vimeo"):
        _service(transport).publish(path)

    assert ("GET", f"/videos/{VIDEO_ID}") in transport.calls
    assert not any(method == "POST_JSON" for method, _ in transport.calls)


def test_in_progress_without_video_id_never_starts_second_upload(tmp_path):
    path = _state_path(tmp_path, vimeo=VimeoState(step=StepState("in_progress")))
    transport = FakeTransport()

    with pytest.raises(VimeoStateConflictError, match="Video-ID fehlt"):
        _service(transport).publish(path)

    assert not any(method == "POST_JSON" for method, _ in transport.calls)


def test_in_progress_with_video_id_reuses_remote_video(tmp_path):
    path = _state_path(
        tmp_path,
        vimeo=VimeoState(step=StepState("in_progress"), video_id=VIDEO_ID, video_uri=f"/videos/{VIDEO_ID}"),
    )
    transport = FakeTransport()

    result = _service(transport).publish(path)

    assert result.video_id == VIDEO_ID
    assert not any(method == "POST_JSON" for method, _ in transport.calls)
    assert load_workflow_state(path).vimeo.step.status == "complete"


def test_failed_state_can_retry_in_a_controlled_way(tmp_path):
    path = _state_path(tmp_path, vimeo=VimeoState(step=StepState("failed", "Netzwerk")))
    transport = FakeTransport()

    _service(transport).publish(path)

    assert ("POST_JSON", "/me/videos") in transport.calls
    assert load_workflow_state(path).vimeo.step.status == "complete"


def test_successful_publish_streams_with_progress_assigns_and_verifies_folder(tmp_path):
    path = _state_path(tmp_path)
    transport = FakeTransport()
    progress = []

    result = _service(transport).publish(path, progress.append)
    state = load_workflow_state(path)

    assert result.video_url.endswith("/unlisted-hash")
    assert state.vimeo.step.status == "complete"
    assert state.vimeo.video_id == VIDEO_ID
    assert state.vimeo.target_folder_id == FOLDER_ID
    assert state.vimeo.target_folder_name == "Predigten"
    assert state.vimeo.upload_status == "complete"
    assert state.vimeo.transcode_status == "complete"
    assert state.vimeo.folder_status == "verified"
    assert state.vimeo.uploaded_at is not None
    assert state.vimeo.embed_html == transport.embed_html
    assert state.vimeo.player_embed_url == transport.player_embed_url
    assert state.vimeo.upload_uri is None
    assert transport.create_payload["name"] == "Predigt (Gnade_Johannes 1,14)_Max Müller"
    assert transport.max_source_read <= 2
    assert {item.phase for item in progress} >= {
        "creating_remote_video",
        "uploading",
        "assigning_folder",
        "verifying_folder",
        "processing_video",
        "fetching_embed",
        "complete",
    }
    assert progress[-1].percent == 100.0
    upload_updates = [item for item in progress if item.phase == "uploading"]
    assert len(upload_updates) > 3
    assert [item.uploaded_bytes for item in upload_updates] == sorted(
        item.uploaded_bytes for item in upload_updates
    )


@pytest.mark.parametrize(
    ("uploaded", "total", "expected"),
    [
        (0, 0, 0.0),
        (0, 1, 0.0),
        (1, 2, 50.0),
        (1, 1, 100.0),
        (2, 1, 100.0),
        (-1, 1, 0.0),
    ],
)
def test_vimeo_progress_percent_is_bounded(uploaded, total, expected):
    assert VimeoProgress("uploading", uploaded, total).percent == expected


def test_upload_progress_reports_session_speed_and_eta(tmp_path):
    path = _state_path(tmp_path)
    transport = FakeTransport()
    ticks = iter(range(100))
    progress: list[VimeoProgress] = []

    _service(transport, clock=lambda: float(next(ticks))).publish(path, progress.append)

    measured = [item for item in progress if item.phase == "uploading" and item.bytes_per_second]
    assert measured
    assert measured[-1].uploaded_bytes == 16
    assert measured[-1].eta_seconds == 0


def test_in_progress_state_is_saved_after_preflight_before_remote_video_creation(tmp_path):
    path = _state_path(tmp_path)

    class InspectingTransport(FakeTransport):
        status_seen_during_create: str | None = None

        def post_json(self, api_path, payload):
            self.status_seen_during_create = load_workflow_state(path).vimeo.step.status
            return super().post_json(api_path, payload)

    transport = InspectingTransport()

    _service(transport).publish(path)

    assert transport.status_seen_during_create == "in_progress"


def test_temporary_network_error_resumes_from_confirmed_tus_offset(tmp_path):
    path = _state_path(tmp_path)
    transport = FakeTransport()
    transport.patch_failures = 1

    _service(transport).publish(path)

    assert len([call for call in transport.calls if call[0] == "HEAD"]) >= 3
    assert load_workflow_state(path).vimeo.upload_offset == 16


def test_network_failure_marks_failed_without_losing_known_video_id(tmp_path):
    path = _state_path(tmp_path)
    transport = FakeTransport()
    transport.patch_failures = 2

    with pytest.raises(VimeoApiError):
        _service(transport, max_retries=0).publish(path)

    state = load_workflow_state(path)
    assert state.vimeo.step.status == "failed"
    assert state.vimeo.video_id == VIDEO_ID
    assert state.vimeo.upload_uri == UPLOAD_URL
    assert state.vimeo.upload_status == "failed"


def test_video_id_is_saved_even_if_vimeo_returns_invalid_tus_information(tmp_path):
    path = _state_path(tmp_path)

    class InvalidTusTransport(FakeTransport):
        def post_json(self, path, payload):
            self.calls.append(("POST_JSON", path))
            return {"uri": f"/videos/{VIDEO_ID}", "upload": {"approach": "streaming"}}

    with pytest.raises(VimeoUploadError, match="keinen gültigen"):
        _service(InvalidTusTransport()).publish(path)

    state = load_workflow_state(path)
    assert state.vimeo.step.status == "failed"
    assert state.vimeo.video_id == VIDEO_ID
    assert state.vimeo.upload_status == "failed"
    assert state.vimeo.uploaded_at is None
    assert state.vimeo.video_uri == f"/videos/{VIDEO_ID}"


def test_folder_assignment_failure_is_not_reported_complete_and_keeps_video_id(tmp_path):
    path = _state_path(tmp_path)
    transport = FakeTransport()
    transport.assign_fails = True

    with pytest.raises(VimeoFolderError, match="konnte aber nicht"):
        _service(transport).publish(path)

    state = load_workflow_state(path)
    assert state.vimeo.step.status == "failed"
    assert state.vimeo.video_id == VIDEO_ID
    assert state.vimeo.upload_status == "complete"
    assert state.vimeo.uploaded_at is not None
    assert state.vimeo.upload_uri is None


def test_video_uri_without_separate_id_is_remote_checked_and_never_duplicated(tmp_path):
    path = _state_path(
        tmp_path,
        vimeo=VimeoState(step=StepState("complete"), video_uri=f"/videos/{VIDEO_ID}"),
    )
    transport = FakeTransport()

    with pytest.raises(VimeoStateConflictError, match="bereits zu Vimeo"):
        _service(transport).publish(path)

    assert ("GET", f"/videos/{VIDEO_ID}") in transport.calls
    assert not any(method == "POST_JSON" for method, _ in transport.calls)


def test_retry_skips_folder_assignment_when_membership_already_exists(tmp_path):
    path = _state_path(
        tmp_path,
        vimeo=VimeoState(
            step=StepState("failed", "Embed fehlte"),
            video_id=VIDEO_ID,
            video_uri=f"/videos/{VIDEO_ID}",
            upload_status="complete",
        ),
    )
    transport = FakeTransport()
    transport.member = True

    result = _service(transport).publish(path)

    assert result.video_id == VIDEO_ID
    assert not any(method == "POST_EMPTY" for method, _ in transport.calls)


def test_failed_folder_membership_verification_blocks_completion(tmp_path):
    path = _state_path(tmp_path)
    transport = FakeTransport()

    def do_not_assign(_path, _payload):
        transport.calls.append(("POST_EMPTY", _path))

    transport.post_empty = do_not_assign  # type: ignore[method-assign]

    with pytest.raises(VimeoFolderError, match="nicht im konfigurierten"):
        _service(transport).publish(path)

    assert load_workflow_state(path).vimeo.step.status == "failed"


def test_upload_verification_tolerates_in_progress_with_exponential_backoff(tmp_path):
    """After TUS completes, Vimeo may briefly report in_progress before complete."""
    path = _state_path(tmp_path)
    transport = FakeTransport()
    # Simulate: first 3 checks show in_progress, then complete
    transport.transcode_statuses = ["complete"]  # transcode is unrelated
    upload_statuses = ["in_progress", "in_progress", "in_progress", "complete"]
    status_index = [0]

    original_get_video = transport.get_json

    def get_video_with_varying_upload(path_or_url, **kwargs):
        result = original_get_video(path_or_url, **kwargs)
        if path_or_url == f"/videos/{VIDEO_ID}":
            upload_status = upload_statuses[min(status_index[0], len(upload_statuses) - 1)]
            status_index[0] += 1
            result = dict(result)
            result["upload"] = {"status": upload_status}
        return result

    transport.get_json = get_video_with_varying_upload  # type: ignore[method-assign]
    clock = _FakeClock()

    service = VimeoPublishingService(
        _config(),
        TOKEN,
        transport,
        chunk_size=5,
        read_size=2,
        sleep=clock.sleep,
        clock=clock,
    )
    result = service.publish(path)

    assert result.video_id == VIDEO_ID
    assert load_workflow_state(path).vimeo.upload_status == "complete"
    # Should have slept multiple times (backoff: 1, 2, 4, ...)
    assert clock.value > 0


def test_upload_verification_timeout_is_recoverable_with_same_video_id(tmp_path):
    """If Vimeo stays in_progress too long, error is recoverable and ID is saved."""
    path = _state_path(tmp_path)
    transport = FakeTransport()
    # Always report in_progress to trigger timeout
    transport.remote_upload_status = "in_progress"
    clock = _FakeClock()

    service = VimeoPublishingService(
        _config(),
        TOKEN,
        transport,
        chunk_size=5,
        read_size=2,
        sleep=clock.sleep,
        clock=clock,
    )
    with pytest.raises(VimeoUploadError, match="Vimeo-Veröffentlichung noch nicht abgeschlossen"):
        service.publish(path)

    state = load_workflow_state(path)
    assert state.vimeo.video_id == VIDEO_ID  # ID is preserved
    assert state.vimeo.video_uri == f"/videos/{VIDEO_ID}"  # URI is preserved
    assert state.vimeo.step.status == "failed"
    assert state.vimeo.step.error is not None
    assert "Bekannte Vimeo-Video-ID" in state.vimeo.step.error


def test_upload_verification_preserves_total_bytes_in_progress_display(tmp_path):
    """After upload completes, progress should show full bytes, not 0 B / 0 B."""
    path = _state_path(tmp_path)
    transport = FakeTransport()
    progress = []

    result = _service(transport).publish(path, progress.append)

    # Find verifying_upload phase in progress
    verify_updates = [p for p in progress if p.phase == "verifying_upload"]
    assert len(verify_updates) > 0

    # All verification updates should have the same bytes (full upload)
    for p in verify_updates:
        assert p.uploaded_bytes == p.total_bytes
        assert p.total_bytes == 16  # our test file size
        assert p.percent == 100.0


def test_retry_with_known_upload_status_skips_remote_video_creation(tmp_path):
    """After upload verification fails with timeout, retry uses existing video ID."""
    path = _state_path(
        tmp_path,
        vimeo=VimeoState(
            step=StepState("failed", "Timeout"),
            video_id=VIDEO_ID,
            video_uri=f"/videos/{VIDEO_ID}",
            upload_status="in_progress",
            upload_uri=UPLOAD_URL,
            upload_size=16,
        ),
    )
    transport = FakeTransport()
    transport.remote_upload_status = "in_progress"
    transport.total = 16  # Match test file size
    transport.offset = 16  # Already uploaded
    clock = _FakeClock()

    service = VimeoPublishingService(
        _config(),
        TOKEN,
        transport,
        chunk_size=5,
        read_size=2,
        sleep=clock.sleep,
        clock=clock,
    )
    with pytest.raises(VimeoUploadError):
        service.publish(path)

    # Should not have created a new video
    create_calls = [call for call in transport.calls if call == ("POST_JSON", "/me/videos")]
    assert len(create_calls) == 0  # Retry should not create new video, just verify existing


def test_upload_and_transcode_status_are_independent(tmp_path):
    """upload.status=complete with transcode.status=in_progress is not an error."""
    path = _state_path(tmp_path)
    transport = FakeTransport()
    transport.remote_upload_status = "complete"
    transport.transcode_statuses = ["in_progress"]  # still processing

    result = _service(transport).publish(path)

    assert result.video_id == VIDEO_ID
    state = load_workflow_state(path)
    assert state.vimeo.upload_status == "complete"
    assert state.vimeo.transcode_status == "in_progress"
    assert state.vimeo.step.status == "complete"  # Publishing can complete


def test_embed_uses_oembed_then_player_url_fallback():
    transport = FakeTransport()
    transport.embed_html = None
    transport.oembed_html = "<iframe>oEmbed</iframe>"
    embed = _service(transport).get_video_embed(VIDEO_ID)
    assert embed.embed_html == "<iframe>oEmbed</iframe>"

    transport.oembed_html = None
    embed = _service(transport).get_video_embed(VIDEO_ID)
    assert transport.player_embed_url in embed.embed_html


def test_missing_embed_marks_failed_but_preserves_remote_id(tmp_path):
    path = _state_path(tmp_path)
    transport = FakeTransport()
    transport.embed_html = None
    transport.player_embed_url = None

    with pytest.raises(VimeoEmbedError):
        _service(transport).publish(path)

    state = load_workflow_state(path)
    assert state.vimeo.step.status == "failed"
    assert state.vimeo.video_id == VIDEO_ID
    assert state.vimeo.embed_html is None
    assert state.vimeo.upload_status == "complete"


def test_embed_can_be_refetched_later_and_saved(tmp_path):
    path = _state_path(
        tmp_path,
        vimeo=VimeoState(step=StepState("failed"), video_id=VIDEO_ID, video_uri=f"/videos/{VIDEO_ID}"),
    )

    embed = _service(FakeTransport()).refresh_embed(path)

    assert embed.embed_html
    assert load_workflow_state(path).vimeo.embed_html == embed.embed_html


def test_embed_refresh_normalizes_video_id_from_known_uri(tmp_path):
    path = _state_path(
        tmp_path,
        vimeo=VimeoState(step=StepState("failed"), video_uri=f"/videos/{VIDEO_ID}"),
    )

    _service(FakeTransport()).refresh_embed(path)

    state = load_workflow_state(path)
    assert state.vimeo.video_id == VIDEO_ID
    assert state.vimeo.video_uri == f"/videos/{VIDEO_ID}"
    assert state.vimeo.video_url.endswith("/unlisted-hash")


class _Response:
    status_code = 500
    headers: dict[str, str] = {}

    def json(self):
        return {"developer_message": f"Server sah {TOKEN}"}


class _FailingSession:
    def request(self, *_args, **_kwargs):
        return _Response()


def test_http_error_redacts_token_from_user_admin_and_logs(caplog):
    transport = RequestsVimeoTransport(TOKEN, session=_FailingSession())

    with pytest.raises(VimeoApiError) as error:
        transport.get_json("/me")

    combined = f"{error.value} {error.value.user_message} {error.value.admin_hint}"
    assert TOKEN not in combined
    assert TOKEN not in caplog.text
    assert "[GEHEIM]" in error.value.admin_hint


class _TusResponse:
    status_code = 204

    def __init__(self, offset: int):
        self.headers = {"Upload-Offset": str(offset)}

    def json(self):
        return {}


class _StreamingSession:
    def __init__(self) -> None:
        self.largest_read = 0

    def request(self, method, _url, **kwargs):
        assert method == "PATCH"
        reader = kwargs["data"]
        total = 0
        while True:
            block = reader.read()
            if not block:
                break
            self.largest_read = max(self.largest_read, len(block))
            total += len(block)
        return _TusResponse(total)


def test_requests_transport_never_reads_a_tus_chunk_fully_into_ram(tmp_path):
    source_path = tmp_path / "gross.mp4"
    source_path.write_bytes(b"x" * (2 * 1024 * 1024))
    session = _StreamingSession()
    transport = RequestsVimeoTransport(TOKEN, session=session)

    reported: list[int] = []
    with source_path.open("rb") as source:
        offset = transport.patch_upload(
            UPLOAD_URL,
            offset=0,
            source=source,
            length=source_path.stat().st_size,
            read_size=64 * 1024,
            progress=reported.append,
        )

    assert offset == source_path.stat().st_size
    assert session.largest_read == 64 * 1024
    assert len(reported) > 1
    assert reported[-1] == source_path.stat().st_size
    assert reported == sorted(reported)


def test_state_file_never_contains_token_during_failed_publish(tmp_path):
    path = _state_path(tmp_path)
    transport = FakeTransport()
    transport.patch_failures = 1

    with pytest.raises(VimeoApiError):
        _service(transport, max_retries=0).publish(path)

    assert TOKEN not in path.read_text(encoding="utf-8")
    assert not path.with_name(f".{path.name}.tmp").exists()


def test_manual_upload_command_needs_explicit_confirmation(monkeypatch, tmp_path, capsys):
    published = False
    preview = SimpleNamespace(
        team_owner_name="Gemeinde-Team",
        folder=SimpleNamespace(name="Predigten", folder_id=FOLDER_ID),
        file_path=tmp_path / "Predigt.mp4",
        file_size=123,
        title="Predigt",
        upload_approach="tus",
        permission_note="Die eigentliche Upload-Berechtigung wird beim Upload geprüft.",
    )

    class StubService:
        def preview_upload(self, _path):
            return preview

        def publish(self, *_args, **_kwargs):
            nonlocal published
            published = True

    monkeypatch.setattr(cli, "_create_vimeo_service", lambda _args: StubService())
    args = SimpleNamespace(state=str(tmp_path / "predigt-workflow.json"), confirm_vimeo_upload=False)

    result = cli.run_vimeo_upload(args)

    assert result == 2
    assert published is False
    assert "Kein Upload gestartet" in capsys.readouterr().out


def test_vimeo_check_prints_non_destructive_permission_diagnostic(monkeypatch, tmp_path, capsys):
    preview = SimpleNamespace(
        team_owner_name="Gemeinde-Team",
        folder=SimpleNamespace(name="Predigten", folder_id=FOLDER_ID),
        file_path=tmp_path / "Predigt.mp4",
        file_size=123,
        title="Predigt",
        upload_approach="tus",
        permission_note="Die eigentliche Upload-Berechtigung wird beim Upload geprüft.",
    )

    class StubService:
        def preview_upload(self, _path):
            return preview

    monkeypatch.setattr(cli, "_create_vimeo_service", lambda _args: StubService())
    args = SimpleNamespace(state=str(tmp_path / "predigt-workflow.json"))

    result = cli.run_vimeo_check(args)

    output = capsys.readouterr().out
    assert result == 0
    assert "Die eigentliche Upload-Berechtigung wird beim Upload geprüft." in output
    assert "Es wurde kein Upload gestartet." in output


def test_parser_exposes_vimeo_development_commands_without_changing_default():
    parser = cli.build_parser()

    assert parser.parse_args([]).command == "menu"
    assert parser.parse_args(["vimeo-diagnose"]).command == "vimeo-diagnose"
    upload = parser.parse_args(["vimeo-upload", "--state", "predigt-workflow.json", "--confirm-vimeo-upload"])
    assert upload.confirm_vimeo_upload is True
    smoke = parser.parse_args(["vimeo-smoke-test", "--confirm-vimeo-upload", "--delete-after-test"])
    assert smoke.command == "vimeo-smoke-test"
    assert smoke.delete_after_test is True


def test_smoke_command_without_confirmation_does_not_load_config_create_clip_or_request_vimeo(monkeypatch, capsys):
    def must_not_run(_args):
        raise AssertionError("Ohne Bestätigung darf der Vimeo-Unterbau nicht gestartet werden")

    monkeypatch.setattr(cli, "_create_vimeo_runtime", must_not_run)
    args = SimpleNamespace(confirm_vimeo_upload=False, delete_after_test=False)

    result = cli.run_vimeo_smoke_test_command(args)

    assert result == 2
    output = capsys.readouterr().out
    assert "weder ein Testclip noch ein Vimeo-Video erzeugt" in output
    assert "--confirm-vimeo-upload" in output


def test_smoke_clip_uses_ffmpeg_and_creates_small_mp4(tmp_path):
    target = tmp_path / "test.mp4"
    commands = []

    def runner(command, **_kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"mp4")
        return SimpleNamespace(returncode=0, stderr="")

    create_smoke_test_clip(
        _app_config(tmp_path),
        target,
        ffmpeg_checker=lambda _config: True,
        process_runner=runner,
    )

    assert target.read_bytes() == b"mp4"
    assert "color=c=black:s=320x180:r=25:d=4" in commands[0]
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in commands[0]
    assert commands[0][-1] == str(target)


def test_smoke_test_missing_ffmpeg_stops_before_remote_video_creation(tmp_path):
    transport = FakeTransport()

    with pytest.raises(VimeoSmokeTestError, match="FFmpeg wurde nicht gefunden"):
        run_vimeo_smoke_test(
            _service(transport),
            _app_config(tmp_path),
            ffmpeg_checker=lambda _config: False,
        )

    assert not any(method == "POST_JSON" for method, _path in transport.calls)


def test_successful_smoke_test_uploads_assigns_folder_fetches_embed_and_cleans_temp_files(tmp_path):
    transport = FakeTransport()
    generated_targets: list[Path] = []

    result = run_vimeo_smoke_test(
        _service(transport),
        _app_config(tmp_path),
        ffmpeg_checker=lambda _config: True,
        process_runner=_fake_ffmpeg(generated_targets),
        now=lambda: datetime(2026, 8, 31, 12, 34, 56),
    )

    assert result.video_id == VIDEO_ID
    assert result.video_uri == f"/videos/{VIDEO_ID}"
    assert result.upload_status == "complete"
    assert result.transcode_status == "complete"
    assert result.target_folder_name == "Predigten"
    assert result.embed_html == transport.embed_html
    assert result.player_embed_url == transport.player_embed_url
    assert result.privacy_view == "unlisted"
    assert result.privacy_embed == "whitelist"
    assert result.embed_domains == ("gemeinde.example",)
    assert transport.member is True
    assert transport.create_payload["name"] == "PredigtUploader Vimeo Test 2026-08-31 12-34-56"
    assert generated_targets and not generated_targets[0].parent.exists()


def test_smoke_upload_failure_reports_known_remote_id_and_removes_temporary_files(tmp_path):
    transport = FakeTransport()
    transport.patch_failures = 1
    generated_targets: list[Path] = []

    with pytest.raises(VimeoSmokeTestError) as error:
        run_vimeo_smoke_test(
            _service(transport, max_retries=0),
            _app_config(tmp_path),
            ffmpeg_checker=lambda _config: True,
            process_runner=_fake_ffmpeg(generated_targets),
        )

    assert error.value.video_id == VIDEO_ID
    assert error.value.video_uri == f"/videos/{VIDEO_ID}"
    assert generated_targets and not generated_targets[0].parent.exists()


def test_smoke_folder_assignment_failure_keeps_remote_identity(tmp_path):
    transport = FakeTransport()
    transport.assign_fails = True

    with pytest.raises(VimeoSmokeTestError) as error:
        run_vimeo_smoke_test(
            _service(transport),
            _app_config(tmp_path),
            ffmpeg_checker=lambda _config: True,
            process_runner=_fake_ffmpeg(),
        )

    assert error.value.stage == "assigning_folder"
    assert error.value.video_id == VIDEO_ID
    assert transport.member is False


def test_smoke_embed_not_yet_available_is_reported_without_duplicate_upload(tmp_path):
    transport = FakeTransport()
    transport.embed_html = None
    transport.player_embed_url = None

    result = run_vimeo_smoke_test(
        _service(transport),
        _app_config(tmp_path),
        ffmpeg_checker=lambda _config: True,
        process_runner=_fake_ffmpeg(),
    )

    assert result.embed_available is False
    assert result.video_id == VIDEO_ID
    assert len([call for call in transport.calls if call == ("POST_JSON", "/me/videos")]) == 1


def test_smoke_waits_for_processing_with_bounded_polling(tmp_path):
    transport = FakeTransport()
    transport.transcode_statuses = ["in_progress", "in_progress", "complete"]
    clock = _FakeClock()

    result = run_vimeo_smoke_test(
        _service(transport),
        _app_config(tmp_path),
        ffmpeg_checker=lambda _config: True,
        process_runner=_fake_ffmpeg(),
        processing_timeout_seconds=30,
        sleep=clock.sleep,
        clock=clock,
    )

    assert result.processing_timed_out is False
    assert result.transcode_status == "complete"
    assert clock.value > 0


def test_smoke_processing_timeout_is_a_visible_non_destructive_result(tmp_path):
    transport = FakeTransport()
    transport.transcode_statuses = ["in_progress"]
    clock = _FakeClock()

    result = run_vimeo_smoke_test(
        _service(transport),
        _app_config(tmp_path),
        delete_after_test=True,
        ffmpeg_checker=lambda _config: True,
        process_runner=_fake_ffmpeg(),
        processing_timeout_seconds=3,
        sleep=clock.sleep,
        clock=clock,
    )

    assert result.processing_timed_out is True
    assert result.transcode_status == "in_progress"
    assert transport.deleted_paths == []


def test_delete_after_smoke_deletes_only_the_persisted_test_video_id(tmp_path):
    transport = FakeTransport()

    result = run_vimeo_smoke_test(
        _service(transport),
        _app_config(tmp_path),
        delete_after_test=True,
        ffmpeg_checker=lambda _config: True,
        process_runner=_fake_ffmpeg(),
    )

    assert result.deleted is True
    assert transport.deleted_paths == [f"/videos/{VIDEO_ID}"]


def test_smoke_test_does_not_change_a_productive_workflow_state(tmp_path):
    productive_folder = tmp_path / "produktiv"
    productive_folder.mkdir()
    productive_state = _state_path(productive_folder)
    before = productive_state.read_bytes()

    run_vimeo_smoke_test(
        _service(FakeTransport()),
        _app_config(tmp_path),
        ffmpeg_checker=lambda _config: True,
        process_runner=_fake_ffmpeg(),
    )

    assert productive_state.read_bytes() == before
