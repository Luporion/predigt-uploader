from __future__ import annotations

import html
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Mapping, Protocol

from ..credentials import (
    VIMEO_TOKEN_ENV,
    CredentialNotConfiguredError,
    CredentialStoreError,
    VimeoCredentialManager,
)
from ..models import SermonInfo, VimeoConfig
from ..workflow_state import StepState, VimeoState, WorkflowState, load_workflow_state, save_workflow_state


VIMEO_API_BASE = "https://api.vimeo.com"
VIMEO_OEMBED_URL = "https://vimeo.com/api/oembed.json"
VIMEO_API_ACCEPT = "application/vnd.vimeo.*+json;version=3.4"
TUS_VERSION = "1.0.0"
DEFAULT_TUS_CHUNK_SIZE = 128 * 1024 * 1024
DEFAULT_STREAM_READ_SIZE = 1024 * 1024


class VimeoError(RuntimeError):
    def __init__(self, user_message: str, admin_hint: str = "") -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.admin_hint = admin_hint


class VimeoCredentialError(VimeoError):
    pass


class VimeoConfigurationError(VimeoError):
    pass


class VimeoUploadError(VimeoError):
    pass


class VimeoFolderError(VimeoError):
    pass


class VimeoStateConflictError(VimeoError):
    pass


class VimeoEmbedError(VimeoError):
    pass


class VimeoApiError(VimeoError):
    def __init__(self, user_message: str, admin_hint: str = "", *, status_code: int | None = None) -> None:
        super().__init__(user_message, admin_hint)
        self.status_code = status_code


@dataclass(frozen=True)
class VimeoProgress:
    phase: str
    uploaded_bytes: int = 0
    total_bytes: int = 0
    bytes_per_second: float | None = None
    eta_seconds: float | None = None

    @property
    def percent(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return max(0.0, min(100.0, self.uploaded_bytes * 100.0 / self.total_bytes))


ProgressCallback = Callable[[VimeoProgress], None]
UploadReadCallback = Callable[[int], None]


class _UploadProgressReporter:
    """Report byte-accurate session progress without persisting unconfirmed offsets."""

    def __init__(
        self,
        callback: ProgressCallback | None,
        *,
        initial_offset: int,
        total_bytes: int,
        clock: Callable[[], float],
    ) -> None:
        self.callback = callback
        self.initial_offset = initial_offset
        self.total_bytes = total_bytes
        self.clock = clock
        self.started_at = clock()

    def report(self, uploaded_bytes: int) -> None:
        uploaded_bytes = min(max(0, uploaded_bytes), self.total_bytes)
        elapsed = self.clock() - self.started_at
        session_bytes = max(0, uploaded_bytes - self.initial_offset)
        bytes_per_second = session_bytes / elapsed if elapsed > 0 and session_bytes > 0 else None
        eta_seconds = None
        if bytes_per_second:
            eta_seconds = max(0.0, (self.total_bytes - uploaded_bytes) / bytes_per_second)
        if self.callback is not None:
            self.callback(
                VimeoProgress(
                    "uploading",
                    uploaded_bytes,
                    self.total_bytes,
                    bytes_per_second,
                    eta_seconds,
                )
            )


@dataclass(frozen=True)
class VimeoFolder:
    folder_id: str
    uri: str
    name: str
    owner_uri: str | None = None
    parent_folder_uri: str | None = None
    item_options: tuple[str, ...] = ()


@dataclass(frozen=True)
class VimeoConnectionReport:
    authenticated_user_uri: str
    authenticated_user_name: str
    team_owner_user_id: str
    team_owner_name: str
    folders: tuple[VimeoFolder, ...]


@dataclass(frozen=True)
class VimeoPreflightResult:
    authenticated_user_uri: str
    authenticated_user_name: str
    team_owner_name: str
    folder: VimeoFolder
    permission_note: str


@dataclass(frozen=True)
class VimeoEmbedData:
    embed_html: str
    player_embed_url: str | None
    video_url: str


@dataclass(frozen=True)
class VimeoPublishResult:
    video_id: str
    video_uri: str
    video_url: str
    embed_html: str
    folder_uri: str
    transcode_status: str | None = None


@dataclass(frozen=True)
class VimeoUploadPreview:
    file_path: Path
    file_size: int
    title: str
    team_owner_name: str
    folder: VimeoFolder
    permission_note: str
    upload_approach: str = "tus"


class VimeoTransport(Protocol):
    def get_json(self, path_or_url: str, *, params: Mapping[str, Any] | None = None) -> Mapping[str, Any]: ...
    def post_json(self, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def post_empty(self, path: str, payload: Mapping[str, Any]) -> None: ...
    def delete(self, path: str) -> None: ...
    def head_upload(self, upload_url: str) -> tuple[int, int]: ...
    def patch_upload(
        self,
        upload_url: str,
        *,
        offset: int,
        source: BinaryIO,
        length: int,
        read_size: int,
        progress: UploadReadCallback | None = None,
    ) -> int: ...
    def get_oembed(self, video_url: str) -> Mapping[str, Any]: ...


class _BoundedReader:
    def __init__(
        self,
        source: BinaryIO,
        length: int,
        read_size: int,
        progress: UploadReadCallback | None = None,
    ) -> None:
        self.source = source
        self.length = length
        self.remaining = length
        self.read_size = read_size
        self.max_read_size = 0
        self.bytes_read = 0
        self.progress = progress

    def __len__(self) -> int:
        return self.length

    def read(self, size: int = -1) -> bytes:
        if self.remaining <= 0:
            return b""
        requested = self.read_size if size < 0 else min(size, self.read_size)
        requested = min(requested, self.remaining)
        self.max_read_size = max(self.max_read_size, requested)
        data = self.source.read(requested)
        self.remaining -= len(data)
        self.bytes_read += len(data)
        if data and self.progress is not None:
            self.progress(self.bytes_read)
        return data


class RequestsVimeoTransport:
    def __init__(
        self,
        token: str,
        *,
        session: Any | None = None,
        timeout: tuple[float, float] = (15.0, 600.0),
    ) -> None:
        token = require_vimeo_token(token)
        if session is None:
            try:
                import requests
            except ImportError as exc:
                raise VimeoConfigurationError(
                    "Die Vimeo-Unterstützung ist nicht vollständig installiert.",
                    "Python-Paket 'requests' fehlt. Bitte PredigtUploader erneut einrichten.",
                ) from exc
            session = requests.Session()
        self._token = token
        self._session = session
        self._timeout = timeout

    def get_json(self, path_or_url: str, *, params: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        response = self._request("GET", path_or_url, params=params)
        return self._json_object(response)

    def post_json(self, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        response = self._request("POST", path, json=dict(payload))
        return self._json_object(response)

    def post_empty(self, path: str, payload: Mapping[str, Any]) -> None:
        self._request("POST", path, json=dict(payload), expected=(200, 201, 204))

    def delete(self, path: str) -> None:
        self._request("DELETE", path, expected=(204,))

    def head_upload(self, upload_url: str) -> tuple[int, int]:
        response = self._request(
            "HEAD",
            upload_url,
            headers={"Tus-Resumable": TUS_VERSION},
            authenticated=False,
        )
        try:
            return int(response.headers["Upload-Offset"]), int(response.headers["Upload-Length"])
        except (KeyError, TypeError, ValueError) as exc:
            raise VimeoUploadError(
                "Vimeo hat keinen gültigen Upload-Fortschritt zurückgegeben.",
                "Tus-HEAD ohne gültige Upload-Offset-/Upload-Length-Header.",
            ) from exc

    def patch_upload(
        self,
        upload_url: str,
        *,
        offset: int,
        source: BinaryIO,
        length: int,
        read_size: int,
        progress: UploadReadCallback | None = None,
    ) -> int:
        reader = _BoundedReader(source, length, read_size, progress)
        response = self._request(
            "PATCH",
            upload_url,
            headers={
                "Tus-Resumable": TUS_VERSION,
                "Upload-Offset": str(offset),
                "Content-Type": "application/offset+octet-stream",
                "Content-Length": str(length),
            },
            data=reader,
            authenticated=False,
            expected=(204,),
        )
        try:
            return int(response.headers["Upload-Offset"])
        except (KeyError, TypeError, ValueError) as exc:
            raise VimeoUploadError(
                "Vimeo hat den neuen Upload-Fortschritt nicht bestätigt.",
                "Tus-PATCH ohne gültigen Upload-Offset-Header.",
            ) from exc

    def get_oembed(self, video_url: str) -> Mapping[str, Any]:
        response = self._request(
            "GET",
            VIMEO_OEMBED_URL,
            params={"url": video_url},
            authenticated=False,
        )
        return self._json_object(response)

    def _request(
        self,
        method: str,
        path_or_url: str,
        *,
        authenticated: bool = True,
        expected: tuple[int, ...] = (200, 201, 204),
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> Any:
        url = path_or_url if path_or_url.startswith("http") else VIMEO_API_BASE + path_or_url
        request_headers = {
            "Accept": VIMEO_API_ACCEPT,
            "User-Agent": "PredigtUploader/0.2",
        }
        if authenticated:
            request_headers["Authorization"] = f"bearer {self._token}"
        if headers:
            request_headers.update(headers)
        try:
            response = self._session.request(
                method,
                url,
                headers=request_headers,
                timeout=self._timeout,
                **kwargs,
            )
        except Exception as exc:
            detail = redact_secret(str(exc), self._token)
            raise VimeoApiError(
                "Vimeo ist momentan nicht erreichbar. Bitte Internetverbindung prüfen und später erneut versuchen.",
                f"{type(exc).__name__}: {detail}",
            ) from exc
        if response.status_code not in expected:
            detail = _safe_response_detail(response, self._token)
            raise VimeoApiError(
                _http_user_message(response.status_code),
                f"HTTP {response.status_code} bei {method} {_safe_endpoint(path_or_url)}. {detail}",
                status_code=response.status_code,
            )
        return response

    def _json_object(self, response: Any) -> Mapping[str, Any]:
        try:
            payload = response.json()
        except Exception as exc:
            raise VimeoApiError(
                "Vimeo hat eine unverständliche Antwort geliefert.",
                f"JSON konnte nicht gelesen werden: {type(exc).__name__}",
                status_code=getattr(response, "status_code", None),
            ) from exc
        if not isinstance(payload, Mapping):
            raise VimeoApiError("Vimeo hat eine unverständliche Antwort geliefert.", "JSON-Antwort ist kein Objekt.")
        return payload


class VimeoPublishingService:
    def __init__(
        self,
        config: VimeoConfig,
        token: str,
        transport: VimeoTransport,
        *,
        chunk_size: int = DEFAULT_TUS_CHUNK_SIZE,
        read_size: int = DEFAULT_STREAM_READ_SIZE,
        max_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        token = require_vimeo_token(token)
        self.config = config
        self.token = token
        self.transport = transport
        self.chunk_size = chunk_size
        self.read_size = read_size
        self.max_retries = max_retries
        self.sleep = sleep
        self.clock = clock

    def diagnose(self) -> VimeoConnectionReport:
        me = self.transport.get_json("/me", params={"fields": "uri,name"})
        if not self.config.team_owner_user_id:
            return VimeoConnectionReport(
                authenticated_user_uri=_required_text(me, "uri", VimeoCredentialError),
                authenticated_user_name=str(me.get("name") or "(ohne Namen)"),
                team_owner_user_id="",
                team_owner_name="(noch nicht konfiguriert)",
                folders=(),
            )
        owner = self._get_owner()
        return VimeoConnectionReport(
            authenticated_user_uri=_required_text(me, "uri", VimeoCredentialError),
            authenticated_user_name=str(me.get("name") or "(ohne Namen)"),
            team_owner_user_id=self.config.team_owner_user_id,
            team_owner_name=str(owner.get("name") or "(ohne Namen)"),
            folders=tuple(self.list_folders()),
        )

    def list_folders(self) -> list[VimeoFolder]:
        validate_vimeo_owner_config(self.config)
        path: str | None = f"/users/{self.config.team_owner_user_id}/folders"
        params: Mapping[str, Any] | None = {
            "per_page": 100,
            "fields": (
                "uri,name,user.uri,metadata.connections.parent_folder.uri,"
                "metadata.connections.items.options"
            ),
        }
        folders: list[VimeoFolder] = []
        while path:
            page = self.transport.get_json(path, params=params)
            data = page.get("data", [])
            if not isinstance(data, list):
                raise VimeoFolderError("Vimeo hat die Ordnerliste in einem unbekannten Format geliefert.")
            folders.extend(_folder_from_response(item) for item in data if isinstance(item, Mapping))
            paging = page.get("paging")
            path = str(paging.get("next")) if isinstance(paging, Mapping) and paging.get("next") else None
            params = None
        return folders

    def preflight(self) -> VimeoPreflightResult:
        validate_vimeo_config(self.config)
        me = self.transport.get_json("/me", params={"fields": "uri,name"})
        owner = self._get_owner()
        expected_owner_uri = f"/users/{self.config.team_owner_user_id}"
        actual_owner_uri = _required_text(owner, "uri", VimeoConfigurationError)
        if actual_owner_uri != expected_owner_uri:
            raise VimeoConfigurationError(
                "Vimeo hat nicht den konfigurierten Team-Owner zurückgegeben.",
                f"Erwartet {expected_owner_uri}, erhalten {actual_owner_uri}.",
            )
        folder = self._get_target_folder()
        return VimeoPreflightResult(
            authenticated_user_uri=_required_text(me, "uri", VimeoCredentialError),
            authenticated_user_name=str(me.get("name") or "(ohne Namen)"),
            team_owner_name=str(owner.get("name") or "(ohne Namen)"),
            folder=folder,
            permission_note="Die eigentliche Upload-Berechtigung wird beim Upload geprüft.",
        )

    def preview_upload(self, state_path: Path) -> VimeoUploadPreview:
        """Validate local and remote prerequisites without creating or uploading a video."""
        state = load_workflow_state(state_path)
        video_path = _validate_local_state(state)
        _guard_duplicate_state(state)
        known_video_id = _known_video_id(state.vimeo)
        if known_video_id:
            self.get_video(known_video_id)
            if state.vimeo.step.status == "complete":
                raise VimeoStateConflictError(
                    "Dieses Video wurde laut Workflow-State bereits zu Vimeo hochgeladen."
                )
        preflight = self.preflight()
        return VimeoUploadPreview(
            file_path=video_path,
            file_size=video_path.stat().st_size,
            title=build_vimeo_title(state.sermon, video_path),
            team_owner_name=preflight.team_owner_name,
            folder=preflight.folder,
            permission_note=preflight.permission_note,
        )

    def publish(self, state_path: Path, progress: ProgressCallback | None = None) -> VimeoPublishResult:
        preview = self.preview_upload(state_path)
        state = load_workflow_state(state_path)
        video_path = preview.file_path
        _emit(progress, "preparing", total=video_path.stat().st_size)
        preflight = VimeoPreflightResult("", "", preview.team_owner_name, preview.folder, preview.permission_note)
        total_size = video_path.stat().st_size
        state = replace(
            state,
            vimeo=replace(
                state.vimeo,
                step=StepState("in_progress"),
                target_folder_id=preflight.folder.folder_id,
                target_folder_uri=preflight.folder.uri,
                target_folder_name=preflight.folder.name,
                team_owner_user_id=self.config.team_owner_user_id,
                upload_status=state.vimeo.upload_status or "pending",
                upload_size=total_size,
            ),
        )
        save_workflow_state(state, state_path)
        try:
            remote = self._resolve_or_create_remote(state, state_path, video_path, progress)
            state = load_workflow_state(state_path)
            self._upload_if_needed(state, state_path, video_path, remote, progress)
            state = load_workflow_state(state_path)
            video = self._verify_remote_video(_known_video_id(state.vimeo), progress)
            state = self._persist_verified_upload(state_path, video)
            video_uri = _required_video_uri(state.vimeo)
            folder_membership_confirmed = self.verify_folder_membership(video_uri, progress=progress)
            if not folder_membership_confirmed:
                self._assign_folder(video_uri, progress)
                folder_membership_confirmed = self.verify_folder_membership(video_uri, progress=progress)
            if not folder_membership_confirmed:
                raise VimeoFolderError(
                    "Das Video wurde übertragen, ist aber nicht im konfigurierten Vimeo-Zielordner auffindbar.",
                    f"Video {_required_video_uri(state.vimeo)} fehlt in Folder {preflight.folder.uri}.",
                )
            current = load_workflow_state(state_path)
            save_workflow_state(
                replace(current, vimeo=replace(current.vimeo, folder_status="verified")),
                state_path,
            )
            _emit(progress, "processing_video")
            state = self._persist_remote_details(state_path, video)
            embed = self.get_video_embed(_required_video_id(state.vimeo), video=video, progress=progress)
            current = load_workflow_state(state_path)
            completed = replace(
                current,
                vimeo=replace(
                    current.vimeo,
                    step=StepState("complete"),
                    video_url=embed.video_url,
                    player_embed_url=embed.player_embed_url,
                    embed_html=embed.embed_html,
                    upload_status="complete",
                    upload_uri=None,
                    upload_offset=total_size,
                ),
            )
            save_workflow_state(completed, state_path)
            _emit(progress, "complete", total_size, total_size)
            return VimeoPublishResult(
                video_id=_required_video_id(completed.vimeo),
                video_uri=_required_video_uri(completed.vimeo),
                video_url=embed.video_url,
                embed_html=embed.embed_html,
                folder_uri=preflight.folder.uri,
                transcode_status=completed.vimeo.transcode_status,
            )
        except Exception as exc:
            self._persist_failure(state_path, exc)
            if isinstance(exc, VimeoError):
                raise
            raise VimeoUploadError(
                "Der Vimeo-Upload konnte nicht abgeschlossen werden.",
                redact_secret(f"{type(exc).__name__}: {exc}", self.token),
            ) from exc

    def refresh_embed(self, state_path: Path) -> VimeoEmbedData:
        state = load_workflow_state(state_path)
        video_id = _required_video_id(state.vimeo)
        video = self.get_video(video_id)
        embed = self.get_video_embed(video_id, video=video)
        transcode = video.get("transcode")
        updated = replace(
            state,
            vimeo=replace(
                state.vimeo,
                video_id=video_id,
                video_uri=state.vimeo.video_uri or f"/videos/{video_id}",
                video_url=embed.video_url,
                player_embed_url=embed.player_embed_url,
                embed_html=embed.embed_html,
                transcode_status=(
                    _optional_text(transcode.get("status"))
                    if isinstance(transcode, Mapping)
                    else state.vimeo.transcode_status
                ),
            ),
        )
        save_workflow_state(updated, state_path)
        return embed

    def get_video(self, video_id: str) -> Mapping[str, Any]:
        return self.transport.get_json(
            f"/videos/{video_id}",
            params={
                "fields": (
                    "uri,link,name,upload.status,transcode.status,status,is_playable,"
                    "player_embed_url,embed.html,privacy.view,privacy.embed,privacy.add,"
                    "privacy.download,parent_project.uri"
                )
            },
        )

    def get_video_embed_domains(self, video_id: str) -> tuple[str, ...]:
        """Return the explicit domain allowlist for a whitelist-protected video."""
        path: str | None = f"/videos/{video_id}/privacy/domains"
        params: Mapping[str, Any] | None = {"per_page": 100, "fields": "domain"}
        domains: list[str] = []
        while path:
            page = self.transport.get_json(path, params=params)
            data = page.get("data", [])
            if not isinstance(data, list):
                raise VimeoEmbedError("Vimeo hat die Liste der erlaubten Embed-Domains nicht lesbar geliefert.")
            for item in data:
                if isinstance(item, Mapping):
                    domain = _optional_text(item.get("domain"))
                    if domain:
                        domains.append(domain)
            paging = page.get("paging")
            path = str(paging.get("next")) if isinstance(paging, Mapping) and paging.get("next") else None
            params = None
        return tuple(domains)

    def delete_video(self, video_id: str) -> None:
        """Delete exactly one explicitly identified Vimeo video."""
        video_id = video_id.strip()
        if not video_id.isdigit():
            raise VimeoStateConflictError(
                "Das Vimeo-Testvideo kann ohne eindeutige numerische Video-ID nicht sicher gelöscht werden."
            )
        self.transport.delete(f"/videos/{video_id}")

    def get_video_embed(
        self,
        video_id: str,
        *,
        video: Mapping[str, Any] | None = None,
        progress: ProgressCallback | None = None,
    ) -> VimeoEmbedData:
        _emit(progress, "fetching_embed")
        video = video or self.get_video(video_id)
        video_url = _required_text(video, "link", VimeoEmbedError)
        player_url = _optional_text(video.get("player_embed_url"))
        embed = video.get("embed")
        embed_html = _optional_text(embed.get("html")) if isinstance(embed, Mapping) else None
        if not embed_html:
            try:
                oembed = self.transport.get_oembed(video_url)
                embed_html = _optional_text(oembed.get("html"))
            except VimeoApiError:
                embed_html = None
        if not embed_html and player_url:
            embed_html = (
                f'<iframe src="{html.escape(player_url, quote=True)}" '
                'width="640" height="360" frameborder="0" allow="autoplay; fullscreen; picture-in-picture" '
                'allowfullscreen></iframe>'
            )
        if not embed_html:
            raise VimeoEmbedError(
                "Für das Vimeo-Video konnte kein verwendbarer Einbettungscode abgerufen werden.",
                "Weder video.embed.html noch oEmbed.html noch player_embed_url vorhanden.",
            )
        return VimeoEmbedData(embed_html, player_url, video_url)

    def verify_folder_membership(self, video_uri: str, *, progress: ProgressCallback | None = None) -> bool:
        _emit(progress, "verifying_folder")
        path: str | None = (
            f"/users/{self.config.team_owner_user_id}/projects/{self.config.target_folder_id}/videos"
        )
        params: Mapping[str, Any] | None = {"per_page": 100, "fields": "uri"}
        while path:
            page = self.transport.get_json(path, params=params)
            data = page.get("data", [])
            if isinstance(data, list) and any(
                isinstance(item, Mapping) and item.get("uri") == video_uri for item in data
            ):
                return True
            paging = page.get("paging")
            path = str(paging.get("next")) if isinstance(paging, Mapping) and paging.get("next") else None
            params = None
        return False

    def _get_owner(self) -> Mapping[str, Any]:
        return self.transport.get_json(
            f"/users/{self.config.team_owner_user_id}",
            params={"fields": "uri,name"},
        )

    def _get_target_folder(self) -> VimeoFolder:
        try:
            payload = self.transport.get_json(
                f"/users/{self.config.team_owner_user_id}/folders/{self.config.target_folder_id}",
                params={
                    "fields": (
                        "uri,name,user.uri,metadata.connections.parent_folder.uri,"
                        "metadata.connections.items.options"
                    )
                },
            )
        except VimeoApiError as exc:
            raise VimeoFolderError(
                "Der konfigurierte Vimeo-Zielordner existiert nicht oder ist mit diesem Token nicht zugreifbar.",
                exc.admin_hint,
            ) from exc
        folder = _folder_from_response(payload)
        if folder.folder_id != self.config.target_folder_id:
            raise VimeoFolderError("Vimeo hat einen anderen Ordner als die konfigurierte Folder-ID zurückgegeben.")
        expected_owner = f"/users/{self.config.team_owner_user_id}"
        if folder.owner_uri != expected_owner:
            raise VimeoFolderError(
                "Die Team-Zugehörigkeit des konfigurierten Vimeo-Ordners konnte nicht bestätigt werden.",
                f"Erwartet {expected_owner}, erhalten {folder.owner_uri or '(keine Owner-URI)'}.",
            )
        if self.config.target_folder_name and folder.name != self.config.target_folder_name:
            raise VimeoFolderError(
                "Die Vimeo-Folder-ID gehört nicht zum erwarteten Ordnernamen.",
                f"Erwartet {self.config.target_folder_name!r}, erhalten {folder.name!r}.",
            )
        return folder

    def _resolve_or_create_remote(
        self,
        state: WorkflowState,
        state_path: Path,
        video_path: Path,
        progress: ProgressCallback | None,
    ) -> Mapping[str, Any]:
        known_video_id = _known_video_id(state.vimeo)
        if known_video_id:
            remote = self.get_video(known_video_id)
            current_uri = _optional_text(remote.get("uri")) or state.vimeo.video_uri or f"/videos/{known_video_id}"
            normalized = replace(
                state,
                vimeo=replace(state.vimeo, video_id=known_video_id, video_uri=current_uri),
            )
            save_workflow_state(normalized, state_path)
            return remote
        _emit(progress, "creating_remote_video", total=video_path.stat().st_size)
        payload = {
            "upload": {"approach": "tus", "size": video_path.stat().st_size},
            "name": build_vimeo_title(state.sermon, video_path),
        }
        remote = self.transport.post_json(
            "/me/videos",
            payload,
        )
        video_uri = _required_text(remote, "uri", VimeoUploadError)
        video_id = _video_id_from_uri(video_uri)
        upload = remote.get("upload")
        upload_uri = _optional_text(upload.get("upload_link")) if isinstance(upload, Mapping) else None
        updated = replace(
            state,
            vimeo=replace(
                state.vimeo,
                video_id=video_id,
                video_uri=video_uri,
                video_url=_optional_text(remote.get("link")),
                upload_status=(
                    _optional_text(upload.get("status")) if isinstance(upload, Mapping) else None
                ) or "in_progress",
                upload_uri=upload_uri,
                upload_offset=0,
                upload_size=video_path.stat().st_size,
            ),
        )
        save_workflow_state(updated, state_path)
        approach = str(upload.get("approach")) if isinstance(upload, Mapping) else ""
        if approach != "tus" or not upload_uri:
            raise VimeoUploadError(
                "Vimeo hat keinen gültigen resumierbaren tus-Upload bereitgestellt.",
                f"Video-ID {video_id} wurde gespeichert; approach={approach or '-'}, upload_link={'ja' if upload_uri else 'nein'}.",
            )
        return remote

    def _persist_verified_upload(self, state_path: Path, video: Mapping[str, Any]) -> WorkflowState:
        current = load_workflow_state(state_path)
        video_uri = _required_text(video, "uri", VimeoUploadError)
        video_id = _video_id_from_uri(video_uri)
        upload = video.get("upload")
        upload_status = _optional_text(upload.get("status")) if isinstance(upload, Mapping) else None
        transcode = video.get("transcode")
        transcode_status = _optional_text(transcode.get("status")) if isinstance(transcode, Mapping) else None
        if upload_status != "complete":
            raise VimeoUploadError(
                "Vimeo hat den Upload noch nicht als vollständig bestätigt.",
                f"upload.status={upload_status or '-'}",
            )
        verified = replace(
            current,
            vimeo=replace(
                current.vimeo,
                video_id=video_id,
                video_uri=video_uri,
                video_url=_optional_text(video.get("link")) or current.vimeo.video_url,
                upload_status="complete",
                transcode_status=transcode_status or current.vimeo.transcode_status,
                uploaded_at=current.vimeo.uploaded_at or _utc_now(),
                upload_uri=None,
                upload_offset=current.vimeo.upload_size,
            ),
        )
        save_workflow_state(verified, state_path)
        return load_workflow_state(state_path)

    def _persist_remote_details(self, state_path: Path, video: Mapping[str, Any]) -> WorkflowState:
        current = load_workflow_state(state_path)
        transcode = video.get("transcode")
        transcode_status = _optional_text(transcode.get("status")) if isinstance(transcode, Mapping) else None
        updated = replace(
            current,
            vimeo=replace(
                current.vimeo,
                video_url=_optional_text(video.get("link")) or current.vimeo.video_url,
                transcode_status=transcode_status or current.vimeo.transcode_status,
            ),
        )
        save_workflow_state(updated, state_path)
        return load_workflow_state(state_path)

    def _upload_if_needed(
        self,
        state: WorkflowState,
        state_path: Path,
        video_path: Path,
        remote: Mapping[str, Any],
        progress: ProgressCallback | None,
    ) -> None:
        total = video_path.stat().st_size
        upload = remote.get("upload")
        if isinstance(upload, Mapping) and upload.get("status") == "complete":
            return
        upload_uri = state.vimeo.upload_uri
        if not upload_uri:
            raise VimeoStateConflictError(
                "Der vorhandene Vimeo-Upload kann nicht sicher fortgesetzt werden, weil der tus-Upload-Link fehlt.",
                f"Video-ID: {state.vimeo.video_id or '-'}",
            )
        offset, remote_total = self.transport.head_upload(upload_uri)
        if remote_total != total:
            raise VimeoStateConflictError(
                "Die lokale MP4 passt nicht zur bereits begonnenen Vimeo-Übertragung.",
                f"Lokal {total} Bytes, Vimeo erwartet {remote_total} Bytes.",
            )
        upload_progress = _UploadProgressReporter(
            progress,
            initial_offset=offset,
            total_bytes=total,
            clock=self.clock,
        )
        upload_progress.report(offset)
        with video_path.open("rb") as source:
            while offset < total:
                source.seek(offset)
                length = min(self.chunk_size, total - offset)
                for attempt in range(self.max_retries + 1):
                    try:
                        new_offset = self.transport.patch_upload(
                            upload_uri,
                            offset=offset,
                            source=source,
                            length=length,
                            read_size=self.read_size,
                            progress=lambda sent, base_offset=offset: upload_progress.report(base_offset + sent),
                        )
                        if new_offset <= offset or new_offset > total:
                            raise VimeoUploadError("Vimeo hat einen unplausiblen Upload-Fortschritt gemeldet.")
                        offset = new_offset
                        break
                    except VimeoApiError:
                        if attempt >= self.max_retries:
                            raise
                        self.sleep(min(2**attempt, 8))
                        offset, remote_total = self.transport.head_upload(upload_uri)
                        if remote_total != total:
                            raise VimeoStateConflictError("Die Vimeo-Uploadgröße hat sich unerwartet geändert.")
                        source.seek(offset)
                        length = min(self.chunk_size, total - offset)
                        upload_progress.report(offset)
                current = load_workflow_state(state_path)
                save_workflow_state(
                    replace(current, vimeo=replace(current.vimeo, upload_offset=offset)),
                    state_path,
                )
                upload_progress.report(offset)
        _emit(progress, "verifying_upload", total, total)
        final_offset, final_total = self.transport.head_upload(upload_uri)
        if final_offset != total or final_total != total:
            raise VimeoUploadError(
                "Vimeo hat die MP4 noch nicht vollständig bestätigt.",
                f"Upload-Offset {final_offset} von {final_total} Bytes.",
            )

    def _verify_remote_video(
        self,
        video_id: str | None,
        progress: ProgressCallback | None,
    ) -> Mapping[str, Any]:
        video_id = video_id or ""
        if not video_id:
            raise VimeoUploadError("Nach dem Upload fehlt die Vimeo-Video-ID.")
        _emit(progress, "verifying_upload")
        last: Mapping[str, Any] = {}
        for attempt in range(6):
            last = self.get_video(video_id)
            upload = last.get("upload")
            status = str(upload.get("status")) if isinstance(upload, Mapping) else ""
            if status == "complete":
                return last
            if status in {"error", "canceled"}:
                raise VimeoUploadError("Vimeo meldet einen Fehler bei der Videoübertragung.", f"upload.status={status}")
            if attempt < 5:
                self.sleep(2)
        raise VimeoUploadError(
            "Vimeo hat die vollständige Übertragung noch nicht bestätigt. Bitte später erneut prüfen.",
            "upload.status blieb in_progress.",
        )

    def _assign_folder(self, video_uri: str, progress: ProgressCallback | None) -> None:
        _emit(progress, "assigning_folder")
        try:
            self.transport.post_empty(
                f"/users/{self.config.team_owner_user_id}/projects/{self.config.target_folder_id}/items",
                {"items": [{"uri": video_uri}]},
            )
        except VimeoApiError as exc:
            raise VimeoFolderError(
                "Das Video wurde hochgeladen, konnte aber nicht dem Vimeo-Zielordner zugeordnet werden.",
                exc.admin_hint,
            ) from exc

    def _persist_failure(self, state_path: Path, exc: Exception) -> None:
        try:
            current = load_workflow_state(state_path)
            message = exc.user_message if isinstance(exc, VimeoError) else "Der Vimeo-Vorgang ist fehlgeschlagen."
            message = redact_secret(message, self.token)
            upload_status = current.vimeo.upload_status
            if upload_status != "complete":
                upload_status = "failed"
            save_workflow_state(
                replace(
                    current,
                    vimeo=replace(
                        current.vimeo,
                        step=StepState("failed", message),
                        upload_status=upload_status,
                    ),
                ),
                state_path,
            )
        except OSError:
            return


def load_vimeo_token(
    environ: Mapping[str, str] | None = None,
    credential_manager: VimeoCredentialManager | None = None,
) -> str:
    manager = credential_manager or VimeoCredentialManager(environ=environ)
    try:
        return require_vimeo_token(manager.resolve().value)
    except CredentialNotConfiguredError as exc:
        raise VimeoCredentialError(
            "Vimeo ist noch nicht eingerichtet. Öffne Einstellungen > Vimeo und richte den Zugang ein.",
            f"Weder {VIMEO_TOKEN_ENV} noch ein sicher gespeicherter Vimeo-Token ist verfügbar.",
        ) from exc
    except CredentialStoreError as exc:
        raise VimeoCredentialError(
            "Der sichere Vimeo-Zugang konnte nicht gelesen werden. Bitte öffne Einstellungen > Vimeo.",
            str(exc),
        ) from exc


def require_vimeo_token(token: str) -> str:
    token = token.strip()
    if not token:
        raise VimeoCredentialError(
            "Der Vimeo-Zugangstoken fehlt.",
            f"Umgebungsvariable {VIMEO_TOKEN_ENV} ist nicht gesetzt.",
        )
    return token


def validate_vimeo_config(config: VimeoConfig) -> None:
    validate_vimeo_owner_config(config)
    if not config.target_folder_id:
        raise VimeoConfigurationError("In der Konfiguration fehlt die Vimeo-Zielordner-ID.")
    if not config.target_folder_id.isdigit():
        raise VimeoConfigurationError("Die konfigurierte Vimeo-Zielordner-ID muss eine numerische ID sein.")


def validate_vimeo_owner_config(config: VimeoConfig) -> None:
    if not config.team_owner_user_id:
        raise VimeoConfigurationError("In der Konfiguration fehlt die Vimeo-Team-Owner-User-ID.")
    if not config.team_owner_user_id.isdigit():
        raise VimeoConfigurationError("Die konfigurierte Vimeo-Team-Owner-User-ID muss eine numerische ID sein.")


def build_vimeo_title(info: SermonInfo, final_mp4: Path | None = None) -> str:
    if final_mp4 is not None and final_mp4.stem.strip():
        return final_mp4.stem.strip()
    details = [info.sermon_type, info.sermon_date.isoformat(), info.title, info.bible_reference, info.speaker]
    return " - ".join(part.strip() for part in details if part.strip())


def redact_secret(text: str, token: str) -> str:
    redacted = text
    if token:
        redacted = redacted.replace(token, "[GEHEIM]")
    return redacted


def _validate_local_state(state: WorkflowState) -> Path:
    if state.local_preparation.status != "complete":
        raise VimeoStateConflictError("Die lokale Vorbereitung ist noch nicht vollständig abgeschlossen.")
    path = state.paths.final_mp4
    if path is None or not path.is_file():
        raise VimeoStateConflictError("Die finale MP4 aus dem Workflow-State wurde nicht gefunden.")
    if path.stat().st_size <= 0:
        raise VimeoStateConflictError("Die finale MP4 ist leer und kann nicht hochgeladen werden.")
    return path


def _guard_duplicate_state(state: WorkflowState) -> None:
    vimeo = state.vimeo
    known_video_id = _known_video_id(vimeo)
    if vimeo.step.status == "complete" and not known_video_id:
        raise VimeoStateConflictError("Der Vimeo-State ist als vollständig markiert, enthält aber keine Video-ID.")
    if vimeo.step.status == "in_progress" and not known_video_id:
        raise VimeoStateConflictError(
            "Ein Vimeo-Upload ist als begonnen markiert, aber die Video-ID fehlt. Es wird kein zweiter Upload gestartet."
        )


def _folder_from_response(payload: Mapping[str, Any]) -> VimeoFolder:
    uri = _required_text(payload, "uri", VimeoFolderError)
    metadata = payload.get("metadata")
    connections = metadata.get("connections") if isinstance(metadata, Mapping) else None
    items = connections.get("items") if isinstance(connections, Mapping) else None
    parent = connections.get("parent_folder") if isinstance(connections, Mapping) else None
    user = payload.get("user")
    options = items.get("options", ()) if isinstance(items, Mapping) else ()
    return VimeoFolder(
        folder_id=_folder_id_from_uri(uri),
        uri=uri,
        name=str(payload.get("name") or ""),
        owner_uri=_optional_text(user.get("uri")) if isinstance(user, Mapping) else None,
        parent_folder_uri=_optional_text(parent.get("uri")) if isinstance(parent, Mapping) else None,
        item_options=tuple(str(option).upper() for option in options if isinstance(option, str)),
    )


def _required_text(payload: Mapping[str, Any], key: str, error_type: type[VimeoError]) -> str:
    value = _optional_text(payload.get(key))
    if value is None:
        raise error_type(f"Vimeo hat das erforderliche Feld '{key}' nicht zurückgegeben.")
    return value


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _video_id_from_uri(uri: str) -> str:
    if not uri.startswith("/videos/") or not uri.rsplit("/", 1)[-1]:
        raise VimeoUploadError("Vimeo hat eine ungültige Video-URI zurückgegeben.", uri)
    return uri.rsplit("/", 1)[-1]


def _folder_id_from_uri(uri: str) -> str:
    marker = "/projects/" if "/projects/" in uri else "/folders/" if "/folders/" in uri else ""
    if not marker:
        raise VimeoFolderError("Vimeo hat eine ungültige Folder-URI zurückgegeben.", uri)
    return uri.split(marker, 1)[1].split("/", 1)[0]


def _required_video_id(state: VimeoState) -> str:
    video_id = _known_video_id(state)
    if not video_id:
        raise VimeoStateConflictError("Im Workflow-State fehlt die Vimeo-Video-ID.")
    return video_id


def _required_video_uri(state: VimeoState) -> str:
    return state.video_uri or f"/videos/{_required_video_id(state)}"


def _known_video_id(state: VimeoState) -> str | None:
    if state.video_id:
        return state.video_id
    if not state.video_uri:
        return None
    try:
        return _video_id_from_uri(state.video_uri)
    except VimeoUploadError as exc:
        raise VimeoStateConflictError(
            "Die Vimeo-Video-URI im Workflow-State ist ungültig.",
            exc.admin_hint,
        ) from exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(
    callback: ProgressCallback | None,
    phase: str,
    uploaded: int = 0,
    total: int = 0,
    **kwargs: int,
) -> None:
    if "total" in kwargs:
        total = kwargs["total"]
    if callback is not None:
        callback(VimeoProgress(phase, uploaded, total))


def _safe_response_detail(response: Any, token: str) -> str:
    try:
        payload = response.json()
        if isinstance(payload, Mapping):
            detail = payload.get("developer_message") or payload.get("error") or payload.get("message") or ""
        else:
            detail = ""
    except Exception:
        detail = ""
    return redact_secret(str(detail), token)[:500]


def _http_user_message(status: int) -> str:
    if status in {401, 403}:
        return "Vimeo hat den Zugriff abgelehnt. Bitte Token, Scopes und Team-Berechtigungen prüfen."
    if status == 404:
        return "Die angeforderte Vimeo-Ressource wurde nicht gefunden oder ist nicht zugreifbar."
    if status == 429:
        return "Vimeo begrenzt gerade die Anzahl der Anfragen. Bitte später erneut versuchen."
    if status >= 500:
        return "Vimeo hat momentan ein Serverproblem. Bitte später erneut versuchen."
    return "Vimeo hat die Anfrage abgelehnt. Bitte Konfiguration und Eingaben prüfen."


def _safe_endpoint(path_or_url: str) -> str:
    return path_or_url.split("?", 1)[0]
