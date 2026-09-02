from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .companion_files import WORKFLOW_STATE_SUFFIX, recording_workflow_state_path
from .models import SermonInfo


WORKFLOW_STATE_FILENAME = "predigt-workflow.json"
WORKFLOW_STATE_SCHEMA_VERSION = 5
STEP_STATUSES = frozenset({"pending", "in_progress", "complete", "failed", "stopped"})


@dataclass(frozen=True)
class StepState:
    status: str = "pending"
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in STEP_STATUSES:
            allowed = ", ".join(sorted(STEP_STATUSES))
            raise ValueError(f"Unbekannter Workflow-Status {self.status!r}. Erlaubt: {allowed}")


@dataclass(frozen=True)
class VimeoState:
    step: StepState = field(default_factory=StepState)
    video_id: str | None = None
    video_uri: str | None = None
    video_url: str | None = None
    player_embed_url: str | None = None
    embed_html: str | None = None
    upload_status: str | None = None
    transcode_status: str | None = None
    uploaded_at: str | None = None
    target_folder_id: str | None = None
    target_folder_uri: str | None = None
    target_folder_name: str | None = None
    folder_status: str | None = None
    team_owner_user_id: str | None = None
    upload_uri: str | None = None
    upload_offset: int | None = None
    upload_size: int | None = None


@dataclass(frozen=True)
class WordPressAudioState:
    step: StepState = field(default_factory=StepState)
    media_id: int | None = None
    media_url: str | None = None


@dataclass(frozen=True)
class WordPressPostState:
    step: StepState = field(default_factory=StepState)
    post_id: int | None = None
    post_url: str | None = None


@dataclass(frozen=True)
class WorkflowPaths:
    raw_recording: Path | None = None
    archived_raw_recording: Path | None = None
    cut_mp4: Path | None = None
    final_mp4: Path | None = None
    final_mp3: Path | None = None
    summary: Path | None = None
    target_folder: Path | None = None


@dataclass(frozen=True)
class WorkflowState:
    sermon: SermonInfo
    paths: WorkflowPaths
    local_preparation: StepState = field(default_factory=StepState)
    vimeo: VimeoState = field(default_factory=VimeoState)
    wordpress_audio: WordPressAudioState = field(default_factory=WordPressAudioState)
    wordpress_post: WordPressPostState = field(default_factory=WordPressPostState)
    schema_version: int = WORKFLOW_STATE_SCHEMA_VERSION
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sermon"]["sermon_date"] = self.sermon.sermon_date.isoformat()
        data["paths"] = {
            key: str(value) if value is not None else None
            for key, value in data["paths"].items()
        }
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkflowState:
        sermon_data = _mapping(data.get("sermon"))
        paths_data = _mapping(data.get("paths"))
        return cls(
            schema_version=int(data.get("schema_version", WORKFLOW_STATE_SCHEMA_VERSION)),
            updated_at=str(data.get("updated_at") or datetime.now(timezone.utc).isoformat()),
            sermon=SermonInfo(
                sermon_date=date.fromisoformat(str(sermon_data["sermon_date"])),
                title=str(sermon_data.get("title", "")),
                bible_reference=str(sermon_data.get("bible_reference", "")),
                speaker=str(sermon_data.get("speaker", "")),
                sermon_type=str(sermon_data.get("sermon_type", "Predigt")),
                folder_note=str(sermon_data.get("folder_note", "")),
            ),
            paths=WorkflowPaths(**{
                name: _optional_path(paths_data.get(name))
                for name in WorkflowPaths.__dataclass_fields__
            }),
            local_preparation=_step_from(data.get("local_preparation"), default="pending"),
            vimeo=_vimeo_from(data.get("vimeo")),
            wordpress_audio=_wordpress_audio_from(data.get("wordpress_audio")),
            wordpress_post=_wordpress_post_from(data.get("wordpress_post")),
        )


def workflow_state_path(target_folder: Path) -> Path:
    """Return the legacy generic state path used before per-recording states."""
    return target_folder / WORKFLOW_STATE_FILENAME


def resolve_workflow_state_path(final_mp4: Path) -> Path | None:
    """Find the state belonging to one MP4 without claiming unrelated legacy state."""
    exact = recording_workflow_state_path(final_mp4)
    if exact.exists():
        _require_state_matches_mp4(exact, final_mp4)
        return exact

    legacy = workflow_state_path(final_mp4.parent)
    if legacy.exists() and _state_matches_mp4(legacy, final_mp4):
        return legacy

    for candidate in final_mp4.parent.glob(f"*{WORKFLOW_STATE_SUFFIX}"):
        if candidate != exact and _state_matches_mp4(candidate, final_mp4):
            return candidate
    return None


def save_workflow_state(state: WorkflowState, path: Path | None = None) -> Path:
    target = path or _default_workflow_state_path(state.paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and state.paths.final_mp4 is not None:
        _require_state_matches_mp4(target, state.paths.final_mp4)
    temporary = target.with_name(f".{target.name}.tmp")
    stored_state = replace(
        state,
        schema_version=WORKFLOW_STATE_SCHEMA_VERSION,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        temporary.write_text(
            json.dumps(stored_state.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def load_workflow_state(path: Path) -> WorkflowState:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Die Workflow-Statusdatei muss ein JSON-Objekt enthalten.")
    return WorkflowState.from_dict(data)


def completed_local_workflow_state(
    *,
    sermon: SermonInfo,
    target_folder: Path,
    final_mp4: Path,
    final_mp3: Path,
    summary: Path,
    cut_mp4: Path | None = None,
    raw_recording: Path | None = None,
    archived_raw_recording: Path | None = None,
) -> WorkflowState:
    return WorkflowState(
        sermon=sermon,
        paths=WorkflowPaths(
            raw_recording=raw_recording,
            archived_raw_recording=archived_raw_recording,
            cut_mp4=cut_mp4,
            final_mp4=final_mp4,
            final_mp3=final_mp3,
            summary=summary,
            target_folder=target_folder,
        ),
        local_preparation=StepState(status="complete"),
    )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_path(value: object) -> Path | None:
    return Path(str(value)) if value not in (None, "") else None


def _required_target_folder(paths: WorkflowPaths) -> Path:
    if paths.target_folder is None:
        raise ValueError("Zum Speichern fehlt der Zielordner im Workflow-Status.")
    return paths.target_folder


def _default_workflow_state_path(paths: WorkflowPaths) -> Path:
    if paths.final_mp4 is not None:
        return recording_workflow_state_path(paths.final_mp4)
    return workflow_state_path(_required_target_folder(paths))


def _state_matches_mp4(path: Path, final_mp4: Path) -> bool:
    try:
        state = load_workflow_state(path)
    except (OSError, ValueError, KeyError):
        return False
    stored = state.paths.final_mp4
    return stored is not None and _path_key(stored) == _path_key(final_mp4)


def _require_state_matches_mp4(path: Path, final_mp4: Path) -> None:
    if not _state_matches_mp4(path, final_mp4):
        raise FileExistsError(
            "Die Workflow-Statusdatei gehört zu einer anderen Aufnahme und wird nicht überschrieben: "
            f"{path}"
        )


def _path_key(path: Path) -> str:
    return str(path.absolute()).casefold()


def _step_from(value: object, *, default: str = "pending") -> StepState:
    data = _mapping(value)
    return StepState(status=str(data.get("status", default)), error=_optional_text(data.get("error")))


def _vimeo_from(value: object) -> VimeoState:
    data = _mapping(value)
    return VimeoState(
        step=_step_from(data.get("step")),
        video_id=_optional_text(data.get("video_id")),
        video_uri=_optional_text(data.get("video_uri")),
        video_url=_optional_text(data.get("video_url")),
        player_embed_url=_optional_text(data.get("player_embed_url")),
        embed_html=_optional_text(data.get("embed_html")),
        upload_status=_optional_text(data.get("upload_status")),
        transcode_status=_optional_text(data.get("transcode_status")),
        uploaded_at=_optional_text(data.get("uploaded_at")),
        target_folder_id=_optional_text(data.get("target_folder_id") or data.get("folder_id")),
        target_folder_uri=_optional_text(data.get("target_folder_uri") or data.get("folder_uri")),
        target_folder_name=_optional_text(data.get("target_folder_name") or data.get("folder_name")),
        folder_status=_optional_text(data.get("folder_status")),
        team_owner_user_id=_optional_text(data.get("team_owner_user_id")),
        upload_uri=_optional_text(data.get("upload_uri")),
        upload_offset=_optional_int(data.get("upload_offset")),
        upload_size=_optional_int(data.get("upload_size")),
    )


def _wordpress_audio_from(value: object) -> WordPressAudioState:
    data = _mapping(value)
    return WordPressAudioState(
        step=_step_from(data.get("step")),
        media_id=_optional_int(data.get("media_id")),
        media_url=_optional_text(data.get("media_url")),
    )


def _wordpress_post_from(value: object) -> WordPressPostState:
    data = _mapping(value)
    return WordPressPostState(
        step=_step_from(data.get("step")),
        post_id=_optional_int(data.get("post_id")),
        post_url=_optional_text(data.get("post_url")),
    )


def _optional_text(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _optional_int(value: object) -> int | None:
    return int(value) if value not in (None, "") else None
