from __future__ import annotations

import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from ..models import AppConfig, SermonInfo
from ..mp3 import ffmpeg_available
from ..workflow_state import (
    StepState,
    WorkflowPaths,
    WorkflowState,
    load_workflow_state,
    save_workflow_state,
)
from .vimeo import (
    ProgressCallback,
    VimeoEmbedError,
    VimeoError,
    VimeoProgress,
    VimeoPublishingService,
)


SMOKE_TEST_DURATION_SECONDS = 4
SMOKE_TEST_WIDTH = 320
SMOKE_TEST_HEIGHT = 180
DEFAULT_PROCESSING_TIMEOUT_SECONDS = 120.0


class VimeoSmokeTestError(VimeoError):
    def __init__(
        self,
        user_message: str,
        admin_hint: str = "",
        *,
        stage: str,
        video_id: str | None = None,
        video_uri: str | None = None,
        video_url: str | None = None,
    ) -> None:
        super().__init__(user_message, admin_hint)
        self.stage = stage
        self.video_id = video_id
        self.video_uri = video_uri
        self.video_url = video_url


@dataclass(frozen=True)
class VimeoSmokeTestResult:
    authenticated_user_name: str
    team_owner_name: str
    target_folder_name: str
    target_folder_id: str
    clip_title: str
    clip_size: int
    clip_duration_seconds: int
    video_id: str
    video_uri: str
    video_url: str
    upload_status: str
    transcode_status: str
    processing_timed_out: bool
    remote_name: str
    privacy_view: str
    privacy_embed: str
    embed_domains: tuple[str, ...]
    embed_domains_note: str | None
    embed_html: str | None
    player_embed_url: str | None
    deleted: bool

    @property
    def embed_available(self) -> bool:
        return bool(self.embed_html)


ProcessRunner = Callable[..., Any]
FfmpegChecker = Callable[[AppConfig], bool]
Clock = Callable[[], float]


def create_smoke_test_clip(
    config: AppConfig,
    target: Path,
    *,
    duration_seconds: int = SMOKE_TEST_DURATION_SECONDS,
    ffmpeg_checker: FfmpegChecker = ffmpeg_available,
    process_runner: ProcessRunner = subprocess.run,
) -> None:
    """Create a tiny real MP4 without touching any production workflow file."""
    if not ffmpeg_checker(config):
        raise VimeoSmokeTestError(
            "FFmpeg wurde nicht gefunden. Der Vimeo-Smoke-Test wurde vor dem Upload abgebrochen.",
            f"ffmpeg_path: {config.ffmpeg_path!r}",
            stage="Testclip",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        config.ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={SMOKE_TEST_WIDTH}x{SMOKE_TEST_HEIGHT}:r=25:d={duration_seconds}",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t",
        str(duration_seconds),
        "-shortest",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        "-movflags",
        "+faststart",
        str(target),
    ]
    result = process_runner(command, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not target.is_file() or target.stat().st_size <= 0:
        stderr = str(getattr(result, "stderr", ""))[-1000:]
        raise VimeoSmokeTestError(
            "Der kleine Vimeo-Testclip konnte nicht erstellt werden. Es wurde kein Vimeo-Video angelegt.",
            f"FFmpeg Exit-Code {result.returncode}. {stderr}".strip(),
            stage="Testclip",
        )


def run_vimeo_smoke_test(
    service: VimeoPublishingService,
    config: AppConfig,
    *,
    delete_after_test: bool = False,
    progress: ProgressCallback | None = None,
    processing_timeout_seconds: float = DEFAULT_PROCESSING_TIMEOUT_SECONDS,
    ffmpeg_checker: FfmpegChecker = ffmpeg_available,
    process_runner: ProcessRunner = subprocess.run,
    sleep: Callable[[float], None] = time.sleep,
    clock: Clock = time.monotonic,
    now: Callable[[], datetime] = datetime.now,
) -> VimeoSmokeTestResult:
    """Run the explicit real-network Vimeo smoke test in an isolated temporary workflow."""
    current_phase = "Vorprüfung"
    state_path: Path | None = None
    known_video_id: str | None = None
    known_video_uri: str | None = None
    known_video_url: str | None = None

    def tracked_progress(item: VimeoProgress) -> None:
        nonlocal current_phase
        current_phase = item.phase
        if progress:
            progress(item)

    try:
        preflight = service.preflight()
        timestamp = now()
        title = f"PredigtUploader Vimeo Test {timestamp:%Y-%m-%d %H-%M-%S}"
        with tempfile.TemporaryDirectory(prefix="PredigtUploader-Vimeo-Smoke-") as temporary:
            temporary_path = Path(temporary)
            clip_path = temporary_path / f"{title}.mp4"
            current_phase = "Testclip"
            create_smoke_test_clip(
                config,
                clip_path,
                ffmpeg_checker=ffmpeg_checker,
                process_runner=process_runner,
            )
            state_path = temporary_path / "predigt-workflow.json"
            save_workflow_state(_isolated_smoke_state(timestamp, clip_path, temporary_path), state_path)

            embed_failed_during_publish = False
            try:
                service.publish(state_path, progress=tracked_progress)
            except VimeoEmbedError:
                # Upload and folder verification happen before the embed step. Keep testing the
                # already identified remote video; a delayed embed must not create a duplicate.
                embed_failed_during_publish = True
            except VimeoError as exc:
                failed_state = _load_optional_state(state_path)
                raise VimeoSmokeTestError(
                    exc.user_message,
                    exc.admin_hint,
                    stage=current_phase,
                    video_id=failed_state.vimeo.video_id if failed_state else None,
                    video_uri=failed_state.vimeo.video_uri if failed_state else None,
                    video_url=failed_state.vimeo.video_url if failed_state else None,
                ) from exc

            state = load_workflow_state(state_path)
            video_id = _required_state_text(state.vimeo.video_id, "Video-ID")
            video_uri = _required_state_text(state.vimeo.video_uri, "Video-URI")
            known_video_id = video_id
            known_video_uri = video_uri
            known_video_url = state.vimeo.video_url
            if not service.verify_folder_membership(video_uri, progress=tracked_progress):
                raise VimeoSmokeTestError(
                    "Das Testvideo ist nach dem Upload nicht im konfigurierten Vimeo-Zielordner auffindbar.",
                    f"Video {video_uri}, Folder {preflight.folder.uri}",
                    stage="Folder-Zuordnung",
                    video_id=video_id,
                    video_uri=video_uri,
                    video_url=state.vimeo.video_url,
                )

            current_phase = "Transkodierung"
            video, timed_out = _poll_video_processing(
                service,
                video_id,
                timeout_seconds=processing_timeout_seconds,
                sleep=sleep,
                clock=clock,
            )

            current_phase = "Embed-Code"
            embed_html = state.vimeo.embed_html
            player_embed_url = state.vimeo.player_embed_url
            if embed_failed_during_publish or not embed_html:
                try:
                    service.refresh_embed(state_path)
                except VimeoEmbedError:
                    pass
            else:
                # Exercise the same refresh path WordPress will use later.
                try:
                    service.refresh_embed(state_path)
                except VimeoEmbedError:
                    pass
            state = load_workflow_state(state_path)
            embed_html = state.vimeo.embed_html
            player_embed_url = state.vimeo.player_embed_url

            current_phase = "Video erneut abrufen"
            video = service.get_video(video_id)
            privacy = _mapping(video.get("privacy"))
            privacy_embed = _text(privacy.get("embed"), "unbekannt")
            domains: tuple[str, ...] = ()
            domains_note: str | None = None
            if privacy_embed == "whitelist":
                try:
                    domains = service.get_video_embed_domains(video_id)
                except VimeoError as exc:
                    domains_note = exc.user_message

            deleted = False
            if delete_after_test and embed_html and not timed_out:
                current_phase = "Testvideo löschen"
                # Never search by name or folder: only the ID persisted for this isolated run.
                service.delete_video(video_id)
                deleted = True

            transcode = _mapping(video.get("transcode"))
            upload = _mapping(video.get("upload"))
            return VimeoSmokeTestResult(
                authenticated_user_name=preflight.authenticated_user_name,
                team_owner_name=preflight.team_owner_name,
                target_folder_name=preflight.folder.name,
                target_folder_id=preflight.folder.folder_id,
                clip_title=title,
                clip_size=clip_path.stat().st_size,
                clip_duration_seconds=SMOKE_TEST_DURATION_SECONDS,
                video_id=video_id,
                video_uri=video_uri,
                video_url=_text(video.get("link"), state.vimeo.video_url or "(nicht gemeldet)"),
                upload_status=_text(upload.get("status"), state.vimeo.upload_status or "unbekannt"),
                transcode_status=_text(transcode.get("status"), "unbekannt"),
                processing_timed_out=timed_out,
                remote_name=_text(video.get("name"), "(nicht gemeldet)"),
                privacy_view=_text(privacy.get("view"), "unbekannt"),
                privacy_embed=privacy_embed,
                embed_domains=domains,
                embed_domains_note=domains_note,
                embed_html=embed_html,
                player_embed_url=player_embed_url,
                deleted=deleted,
            )
    except VimeoSmokeTestError:
        raise
    except VimeoError as exc:
        state = _load_optional_state(state_path)
        raise VimeoSmokeTestError(
            exc.user_message,
            exc.admin_hint,
            stage=current_phase,
            video_id=state.vimeo.video_id if state else known_video_id,
            video_uri=state.vimeo.video_uri if state else known_video_uri,
            video_url=state.vimeo.video_url if state else known_video_url,
        ) from exc
    except Exception as exc:
        state = _load_optional_state(state_path)
        raise VimeoSmokeTestError(
            "Der Vimeo-Smoke-Test konnte nicht abgeschlossen werden.",
            f"{type(exc).__name__}: {exc}",
            stage=current_phase,
            video_id=state.vimeo.video_id if state else known_video_id,
            video_uri=state.vimeo.video_uri if state else known_video_uri,
            video_url=state.vimeo.video_url if state else known_video_url,
        ) from exc


def _isolated_smoke_state(timestamp: datetime, clip_path: Path, temporary_path: Path) -> WorkflowState:
    return WorkflowState(
        sermon=SermonInfo(
            sermon_date=timestamp.date(),
            title="Vimeo Smoke-Test",
            bible_reference="",
            speaker="PredigtUploader",
            sermon_type="Diagnose",
        ),
        paths=WorkflowPaths(final_mp4=clip_path, target_folder=temporary_path),
        local_preparation=StepState("complete"),
    )


def _poll_video_processing(
    service: VimeoPublishingService,
    video_id: str,
    *,
    timeout_seconds: float,
    sleep: Callable[[float], None],
    clock: Clock,
) -> tuple[Mapping[str, Any], bool]:
    deadline = clock() + max(0.0, timeout_seconds)
    delay = 2.0
    while True:
        video = service.get_video(video_id)
        transcode = _mapping(video.get("transcode"))
        status = _text(transcode.get("status"), "")
        if status == "complete":
            return video, False
        if status == "error":
            raise VimeoSmokeTestError(
                "Vimeo meldet einen Fehler bei der Transkodierung des Testvideos.",
                "transcode.status=error",
                stage="Transkodierung",
                video_id=video_id,
                video_uri=_optional_text(video.get("uri")),
                video_url=_optional_text(video.get("link")),
            )
        remaining = deadline - clock()
        if remaining <= 0:
            return video, True
        sleep(min(delay, remaining))
        delay = min(delay * 1.5, 10.0)


def _load_optional_state(path: Path | None) -> WorkflowState | None:
    if path is None or not path.is_file():
        return None
    try:
        return load_workflow_state(path)
    except (OSError, ValueError):
        return None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object, default: str) -> str:
    text = _optional_text(value)
    return text if text is not None else default


def _optional_text(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _required_state_text(value: str | None, field: str) -> str:
    if value:
        return value
    raise VimeoSmokeTestError(
        f"Nach dem Vimeo-Upload fehlt die {field} im isolierten Teststatus.",
        stage="Workflow-State",
    )
