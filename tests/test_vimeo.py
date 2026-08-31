from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from predigt_uploader import cli
from predigt_uploader.models import SermonInfo, VimeoConfig
from predigt_uploader.publishing.vimeo import (
    RequestsVimeoTransport,
    VimeoApiError,
    VimeoConfigurationError,
    VimeoCredentialError,
    VimeoEmbedError,
    VimeoFolderError,
    VimeoPublishingService,
    VimeoStateConflictError,
    VimeoUploadError,
    load_vimeo_token,
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

    def get_json(self, path_or_url: str, *, params: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        self.calls.append(("GET", path_or_url))
        if path_or_url == "/me":
            return {"uri": "/users/5", "name": "Teammitglied"}
        if path_or_url == f"/users/{OWNER_ID}":
            options = ["GET", "POST"] if self.owner_can_upload else ["GET"]
            return {
                "uri": f"/users/{OWNER_ID}",
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
            return self._video()
        if path_or_url == f"/users/{OWNER_ID}/projects/{FOLDER_ID}/videos":
            data = [{"uri": f"/videos/{VIDEO_ID}"}] if self.member else []
            return {"data": data, "paging": {"next": None}}
        raise AssertionError(f"Unerwarteter GET: {path_or_url}")

    def post_json(self, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append(("POST_JSON", path))
        assert path == f"/users/{OWNER_ID}/videos"
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

    def head_upload(self, upload_url: str) -> tuple[int, int]:
        self.calls.append(("HEAD", upload_url))
        return self.offset, self.total

    def patch_upload(self, upload_url: str, *, offset: int, source, length: int, read_size: int) -> int:
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
        return {
            "uri": f"/videos/{VIDEO_ID}",
            "link": f"https://vimeo.com/{VIDEO_ID}/unlisted-hash",
            "upload": {"status": self.remote_upload_status},
            "player_embed_url": self.player_embed_url,
            "embed": {"html": self.embed_html},
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


def test_missing_token_is_rejected_without_echoing_a_secret():
    with pytest.raises(VimeoCredentialError) as error:
        load_vimeo_token({})

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


def test_preflight_requires_upload_and_folder_write_permissions():
    no_upload = FakeTransport()
    no_upload.owner_can_upload = False
    with pytest.raises(VimeoConfigurationError, match="keine Videos hochladen"):
        _service(no_upload).preflight()

    no_folder_write = FakeTransport()
    no_folder_write.folder_can_add = False
    with pytest.raises(VimeoFolderError, match="keine Videos hinzufügen"):
        _service(no_folder_write).preflight()


def test_preflight_rejects_wrong_owner_or_control_name():
    wrong_owner = FakeTransport()
    wrong_owner.folder_owner_uri = "/users/999"
    with pytest.raises(VimeoFolderError, match="Team-Owner"):
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

    assert ("POST_JSON", f"/users/{OWNER_ID}/videos") in transport.calls
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
    assert state.vimeo.folder_id == FOLDER_ID
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
        "fetching_embed",
        "complete",
    }
    assert progress[-1].percent == 100.0


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


def test_failed_folder_membership_verification_blocks_completion(tmp_path):
    path = _state_path(tmp_path)
    transport = FakeTransport()

    def do_not_assign(_path, _payload):
        transport.calls.append(("POST_EMPTY", _path))

    transport.post_empty = do_not_assign  # type: ignore[method-assign]

    with pytest.raises(VimeoFolderError, match="nicht im konfigurierten"):
        _service(transport).publish(path)

    assert load_workflow_state(path).vimeo.step.status == "failed"


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


def test_embed_can_be_refetched_later_and_saved(tmp_path):
    path = _state_path(
        tmp_path,
        vimeo=VimeoState(step=StepState("failed"), video_id=VIDEO_ID, video_uri=f"/videos/{VIDEO_ID}"),
    )

    embed = _service(FakeTransport()).refresh_embed(path)

    assert embed.embed_html
    assert load_workflow_state(path).vimeo.embed_html == embed.embed_html


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

    with source_path.open("rb") as source:
        offset = transport.patch_upload(
            UPLOAD_URL,
            offset=0,
            source=source,
            length=source_path.stat().st_size,
            read_size=64 * 1024,
        )

    assert offset == source_path.stat().st_size
    assert session.largest_read == 64 * 1024


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


def test_parser_exposes_vimeo_development_commands_without_changing_default():
    parser = cli.build_parser()

    assert parser.parse_args([]).command == "menu"
    assert parser.parse_args(["vimeo-diagnose"]).command == "vimeo-diagnose"
    upload = parser.parse_args(["vimeo-upload", "--state", "predigt-workflow.json", "--confirm-vimeo-upload"])
    assert upload.confirm_vimeo_upload is True
