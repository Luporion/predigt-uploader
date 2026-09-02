from __future__ import annotations

import subprocess
import re
import threading
import webbrowser
from dataclasses import dataclass, replace
from datetime import date, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable

from .companion_files import recording_summary_path, recording_workflow_state_path
from .config import (
    ConfigLoadError,
    default_service_types,
    describe_config_source,
    load_config,
    save_user_config_values,
)
from .credentials import (
    CredentialError,
    VimeoCredentialManager,
)
from .filename import build_filename_preview, build_media_filename, sanitize_filename_part, service_type_config_for
from .folders import resolve_folder, suggest_folder
from .models import AppConfig, FolderResolution, ProcessingPlan, SermonInfo, ServiceTypeConfig
from .processing import (
    MP4_ACTION_COPY,
    MP4_ACTION_KEEP,
    MP4_ACTION_MOVE,
    MP4_ACTION_OVERWRITE,
    PreparedRecordingPlan,
    apply_output_filenames,
    build_prepared_recording_plan,
    planned_existing_output_renames,
    raw_action_label,
    execute_processing_plan,
    unique_output_name_suggestions,
    validate_windows_filename,
)
from .publishing.vimeo import (
    VimeoError,
    VimeoFolder,
    VimeoFolderCatalog,
    VimeoFolderError,
    VimeoLibraryResult,
    VimeoLibraryVideo,
    VimeoProgress,
    VimeoPublishingService,
    VimeoUploadStoppedError,
    build_vimeo_title,
)
from .speaker_history import SpeakerHistory
from .workflow_state import (
    StepState,
    VimeoState,
    WorkflowPaths,
    WorkflowState,
    load_workflow_state,
    resolve_workflow_state_path,
    save_workflow_state,
)

TUI_MP4_PREVIEW_LIMIT = 5
TUI_FILE_CHOICE_LIMIT = 500
TUI_START_SAFETY_TITLE = "WICHTIGER CHECK VOR DEM START"
TUI_START_SAFETY_QUESTIONS = (
    "Ist die Aufnahme in vMix beendet?",
    "Ist der Stream in vMix beendet?",
)
TUI_START_SAFETY_WARNING = (
    "Wenn der Stream weiterlaeuft, verbraucht der Streaminganbieter weiter Datenvolumen/Kosten."
)
TUI_START_SAFETY_CANCEL_LABEL = "Nein, erst in vMix pruefen"
TUI_START_SAFETY_CONFIRM_LABEL = "Ja, Aufnahme und Stream sind beendet"
TUI_PROCESSING_EXECUTE_LABEL = "Finale Dateien jetzt erstellen"
TUI_PROCESSING_RUNNING_LABEL = "Verarbeitung laeuft..."
TUI_PROCESSING_DONE_LABEL = "Fertig vorbereitet"
TUI_TOTAL_WORKFLOW_STEPS = 8
TUI_BACK_LABEL = "Zurueck"
TUI_GOTTESDIENST_EXPLANATION = (
    "Gottesdienst bedeutet: normale Aufnahme eines Gottesdienstes. "
    "Die finale Predigtdatei wird trotzdem als Predigt benannt."
)
TUI_WORKFLOW_STEP_NAMES = ("Start", "Quelle", "Schnitt", "MP4", "Metadaten", "Ordner", "Dateien", "Vimeo")

TUI_VIMEO_STAGE_LABELS = (
    ("connection", "Vimeo-Verbindung geprüft"),
    ("remote_video", "Video auf Vimeo angelegt"),
    ("video_link", "Vimeo-Link erhalten"),
    ("embed", "Embed-Code erhalten"),
    ("upload", "Datei zu Vimeo übertragen"),
    ("verify_upload", "Vimeo bestätigt den Upload"),
    ("folder", "Ordner „Predigten“ wird zugeordnet"),
    ("processing", "Vimeo verarbeitet das Video"),
)


@dataclass(frozen=True)
class TuiDateOption:
    label: str
    value: date
    kind: str


@dataclass(frozen=True)
class TuiMp4SelectionConfig:
    mode: str
    start_folder: Path
    title: str
    note: str
    suggest_newest: bool = True
    allow_search: bool = True
    allow_manual_input: bool = True


@dataclass(frozen=True)
class TuiMp4FileRow:
    path: Path
    filename: str
    modified: str
    size: str


@dataclass(frozen=True)
class TuiMp4SnapshotEntry:
    path: Path
    size: int
    modified_at: float


@dataclass(frozen=True)
class TuiExportCandidate:
    path: Path
    score: int
    reason: str
    modified: str
    size: str


@dataclass(frozen=True)
class TuiTargetConflict:
    path: Path
    kind: str
    severity: str
    message: str


@dataclass(frozen=True)
class TuiPreparation:
    source_mp4: Path | None
    raw_recording: Path | None
    already_cut: bool
    info: SermonInfo
    target_folder: Path
    target_mp4: Path
    target_mp3: Path
    summary_path: Path

    @property
    def plan(self) -> ProcessingPlan | None:
        if self.source_mp4 is None:
            return None
        return ProcessingPlan(
            source_mp4=self.source_mp4,
            target_mp4=self.target_mp4,
            target_mp3=self.target_mp3,
            info=self.info,
        )


def build_tui_step_title(step: int, name: str) -> str:
    return f"Schritt {step}/{TUI_TOTAL_WORKFLOW_STEPS}: {name}"


def build_tui_progress_text(current_step: int, skipped_steps: set[int] | None = None) -> str:
    skipped = skipped_steps or set()
    parts: list[str] = []
    for step, name in enumerate(TUI_WORKFLOW_STEP_NAMES, start=1):
        if step in skipped:
            marker = "[-]"
        elif step < current_step:
            marker = "✓"
        elif step == current_step:
            marker = "▶"
        else:
            marker = "[ ]"
        parts.append(f"{marker}{step} {name}")
    return "Fortschritt: " + " | ".join(parts)


def build_tui_screen_help(instruction: str, _next_action: str) -> str:
    return instruction


def build_tui_back_footnote() -> str:
    return "Zurueck ist moeglich, solange noch keine finalen Dateien geschrieben wurden."


def load_tui_config(config_path: str | None = None) -> AppConfig:
    explicit_config = Path(config_path) if config_path else None
    return load_config(explicit_config)


def create_tui_vimeo_service(
    config: AppConfig,
    credential_manager: VimeoCredentialManager | None = None,
) -> VimeoPublishingService:
    """Build the shared Vimeo backend only after the user starts publishing."""
    from .publishing.vimeo import RequestsVimeoTransport, load_vimeo_token

    token = load_vimeo_token(credential_manager=credential_manager)
    return VimeoPublishingService(config.vimeo, token, RequestsVimeoTransport(token))


def validate_direct_vimeo_mp4(path: Path) -> Path:
    candidate = path.expanduser()
    if candidate.suffix.casefold() != ".mp4":
        raise ValueError("Bitte eine MP4-Datei auswählen.")
    if not candidate.is_file():
        raise ValueError("Die ausgewählte MP4-Datei wurde nicht gefunden.")
    try:
        if candidate.stat().st_size <= 0:
            raise ValueError("Die ausgewählte MP4-Datei ist leer.")
        with candidate.open("rb") as handle:
            handle.read(1)
    except OSError as exc:
        raise ValueError(f"Die ausgewählte MP4-Datei ist nicht lesbar: {exc}") from exc
    return candidate


def load_or_create_direct_vimeo_state(final_mp4: Path) -> tuple[Path, bool]:
    final_mp4 = validate_direct_vimeo_mp4(final_mp4)
    existing = resolve_workflow_state_path(final_mp4)
    if existing is not None:
        state = load_workflow_state(existing)
        if state.local_preparation.status != "complete":
            raise ValueError("Der gefundene Workflow-Status meldet die lokale Vorbereitung noch nicht als abgeschlossen.")
        return existing, False

    detected_date = detect_tui_recording_date_from_filename(final_mp4) or tui_file_modified_date(final_mp4) or date.today()
    summary = recording_summary_path(final_mp4)
    mp3 = final_mp4.with_suffix(".mp3")
    state = WorkflowState(
        sermon=SermonInfo(
            sermon_date=detected_date,
            title=final_mp4.stem,
            bible_reference="",
            speaker="",
            sermon_type="Direkt-Vimeo",
        ),
        paths=WorkflowPaths(
            final_mp4=final_mp4,
            final_mp3=mp3 if mp3.is_file() else None,
            summary=summary if summary.is_file() else None,
            target_folder=final_mp4.parent,
        ),
        local_preparation=StepState("complete"),
    )
    return save_workflow_state(state), True


def build_direct_vimeo_plan(final_mp4: Path, state: WorkflowState) -> PreparedRecordingPlan:
    return PreparedRecordingPlan(
        source_mp4=final_mp4,
        raw_recording=None,
        target_folder=final_mp4.parent,
        target_mp4=final_mp4,
        target_mp3=state.paths.final_mp3 or final_mp4.with_suffix(".mp3"),
        summary_path=state.paths.summary or recording_summary_path(final_mp4),
        info=state.sermon,
        raw_action="none",
        mp4_action=MP4_ACTION_KEEP,
    )


GERMAN_MONTHS = {
    "januar": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "maerz": 3,
    "mrz": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "oktober": 10,
    "okt": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
}


def build_tui_preview_text(info: SermonInfo, config: AppConfig) -> str:
    preview = build_filename_preview(info, config)
    target_folder = suggest_folder(config, info)
    summary_path = recording_summary_path(target_folder / preview.mp4)
    return "\n".join(
        [
            f"Zielordner: {target_folder}",
            f"MP4-Dateiname: {preview.mp4}",
            f"MP3-Dateiname: {preview.mp3}",
            f"Zusammenfassung: {summary_path}",
        ]
    )


def build_tui_preparation(
    *,
    config: AppConfig,
    source_mp4: Path | None,
    raw_recording: Path | None,
    already_cut: bool,
    info: SermonInfo,
) -> TuiPreparation:
    target_folder = suggest_folder(config, info)
    target_mp4 = target_folder / build_media_filename(info, config, ".mp4")
    target_mp3 = target_folder / build_media_filename(info, config, ".mp3")
    return TuiPreparation(
        source_mp4=source_mp4,
        raw_recording=raw_recording,
        already_cut=already_cut,
        info=info,
        target_folder=target_folder,
        target_mp4=target_mp4,
        target_mp3=target_mp3,
        summary_path=recording_summary_path(target_mp4),
    )


def build_tui_processing_plan(
    *,
    config: AppConfig,
    source_mp4: Path,
    raw_recording: Path | None,
    already_cut: bool,
    info: SermonInfo,
    raw_action: str | None = None,
    mp4_action: str | None = None,
    target_folder_override: Path | None = None,
    overwrite_existing_outputs: bool = False,
) -> PreparedRecordingPlan:
    warnings: list[str] = []
    if not already_cut and raw_recording is not None and _same_tui_path(source_mp4, raw_recording):
        warnings.append(
            "Achtung: Rohaufnahme und finale MP4 sind identisch. Das ist nur korrekt, wenn die Datei bereits fertig geschnitten ist."
        )
    return build_prepared_recording_plan(
        config=config,
        source_mp4=source_mp4,
        raw_recording=raw_recording,
        raw_action=raw_action,
        mp4_action=mp4_action,
        target_folder_override=target_folder_override,
        overwrite_existing_outputs=overwrite_existing_outputs,
        info=info,
        warnings=tuple(warnings),
    )


def build_tui_info_with_folder_note(info: SermonInfo, folder_note: str) -> SermonInfo:
    return replace(info, folder_note=folder_note)


def build_tui_target_folder_review_text(resolution: FolderResolution) -> str:
    lines = [
        f"Datum: {resolution.date_prefix}",
        f"Vorgeschlagener Zielordner: {resolution.suggested_folder}",
    ]
    if resolution.status == "missing":
        lines.append("Status: Kein vorhandener Ordner gefunden.")
    elif resolution.status == "single_existing":
        lines.append("Status: Vorhandener Tagesordner gefunden.")
        lines.append(f"Vorhandener Ordner: {resolution.candidates[0]}")
    else:
        lines.append("Status: Mehrere moegliche Ordner gefunden.")
    return "\n".join(lines)


def tui_target_folder_primary_action(resolution: FolderResolution) -> tuple[str, str]:
    if resolution.status == "missing":
        return "Neuen Zielordner verwenden", "use_suggested"
    if resolution.status == "single_existing":
        return "Vorhandenen Ordner verwenden / Dateien dort hinzufuegen", "use_existing"
    return "Ausgewaehlten Ordner verwenden", "use_existing"


def tui_target_folder_initial_focus_id(resolution: FolderResolution) -> str:
    return tui_target_folder_primary_action(resolution)[1]


def tui_target_folder_note_input_visible(create_with_note: bool) -> bool:
    return create_with_note


def tui_metadata_action_labels() -> tuple[str, str, str]:
    return (TUI_BACK_LABEL, "Abbrechen", "Zielordner pruefen")


def build_tui_target_folder_action_hint(
    resolution: FolderResolution,
    *,
    create_with_note: bool = False,
    selected_folder: Path | None = None,
) -> str:
    if create_with_note:
        return "Es wird ein neuer Ordner mit dem Zusatz erstellt. Vorhandene Ordner bleiben unveraendert."
    if resolution.status == "missing":
        return "Es wird ein neuer Zielordner erstellt."
    folder = selected_folder or resolution.candidates[0]
    return (
        f"Die neuen Dateien werden in diesen Ordner gelegt:\n{folder}\n"
        "Vorhandene Dateien werden in Schritt 7 separat geprueft."
    )


def tui_target_folder_status_message(resolution: FolderResolution) -> str:
    messages = {
        "missing": "Kein vorhandener Ordner gefunden",
        "single_existing": "Vorhandener Tagesordner gefunden",
        "multiple_existing": "Mehrere moegliche Ordner gefunden",
    }
    return messages[resolution.status]


def tui_target_folder_status_class(resolution: FolderResolution) -> str:
    classes = {
        "missing": "status-info",
        "single_existing": "status-ok",
        "multiple_existing": "status-warning",
    }
    return classes[resolution.status]


def build_tui_new_folder_decision_text(config: AppConfig, info: SermonInfo, note: str) -> str:
    cleaned_note = note.strip()
    if not cleaned_note:
        return "Neuer Ordner mit Zusatz\nBitte zuerst einen Zusatz eingeben."
    target_folder = suggest_folder(config, build_tui_info_with_folder_note(info, cleaned_note))
    folder_state = (
        "Dieser Zielordner existiert bereits. Er wird als vorhandener Ordner verwendet; "
        "Dateikonflikte werden weiterhin in Schritt 7 geprueft."
        if target_folder.exists()
        else "Der vorhandene Tagesordner bleibt unveraendert."
    )
    return f"Neuer Ordner mit Zusatz\nNeuer Zielordner: {target_folder}\n{folder_state}"


def tui_new_folder_decision_status_class(config: AppConfig, info: SermonInfo, note: str) -> str:
    cleaned_note = note.strip()
    if not cleaned_note:
        return "status-warning"
    target_folder = suggest_folder(config, build_tui_info_with_folder_note(info, cleaned_note))
    return "status-warning" if target_folder.exists() else "status-info"


def build_tui_target_folder_status_text(plan: PreparedRecordingPlan) -> str:
    if plan.target_folder.exists():
        return "Der Zielordner existiert bereits. Die neuen Dateien werden in diesen Ordner hinzugefuegt."
    return "Der Zielordner wird neu erstellt."


def detect_tui_target_conflicts(plan: PreparedRecordingPlan) -> tuple[TuiTargetConflict, ...]:
    conflicts: list[TuiTargetConflict] = []
    if plan.target_mp4.exists():
        conflicts.append(
            TuiTargetConflict(
                path=plan.target_mp4,
                kind="mp4",
                severity="danger",
                message=f"Finale MP4 existiert bereits: {plan.target_mp4}",
            )
        )
    if plan.target_mp3.exists():
        conflicts.append(
            TuiTargetConflict(
                path=plan.target_mp3,
                kind="mp3",
                severity="danger",
                message=f"Finale MP3 existiert bereits: {plan.target_mp3}",
            )
        )
    if plan.summary_path.exists():
        conflicts.append(
            TuiTargetConflict(
                path=plan.summary_path,
                kind="summary",
                severity="warning",
                message=f"Zusammenfassung existiert bereits: {plan.summary_path}",
            )
        )
    if plan.workflow_state_path.exists():
        conflicts.append(
            TuiTargetConflict(
                path=plan.workflow_state_path,
                kind="state",
                severity="warning",
                message=f"Workflow-Status existiert bereits: {plan.workflow_state_path}",
            )
        )
    return tuple(conflicts)


def build_tui_target_conflict_text(conflicts: tuple[TuiTargetConflict, ...]) -> str:
    if not conflicts:
        return "Keine bestehenden Zieldateien mit gleichem Namen gefunden."
    labels = {
        "mp4": "MP4",
        "mp3": "MP3",
        "summary": "Zusammenfassung",
        "state": "Workflow-Status",
    }
    lines = ["Vorhandene Zieldateien:"]
    lines.extend(f"- {labels.get(conflict.kind, conflict.kind)}: {conflict.path}" for conflict in conflicts)
    return "\n".join(lines)


def build_tui_target_file_plan_text(
    plan: PreparedRecordingPlan,
    conflicts: tuple[TuiTargetConflict, ...],
    *,
    proposed_names: dict[str, str] | None = None,
) -> str:
    conflict_kinds = {conflict.kind for conflict in conflicts}
    existing_renames = {source: target for source, target in plan.existing_output_renames}
    rows = (
        ("mp4", "MP4", plan.target_mp4),
        ("mp3", "MP3", plan.target_mp3),
        ("summary", "Zusammenfassung", plan.summary_path),
        ("state", "Workflow-Status", plan.workflow_state_path),
    )
    lines = ["Datei | Zustand | geplante Aktion"]
    for kind, label, path in rows:
        if kind in conflict_kinds:
            if proposed_names:
                action = (
                    f"Neue Datei: {proposed_names[kind]}"
                    if kind in proposed_names
                    else "wird aus dem neuen MP4-Namen abgeleitet"
                )
            elif path in existing_renames:
                action = f"Vorhandene Datei -> {existing_renames[path].name}; neue Datei -> {path.name}"
            elif plan.overwrite_existing_outputs:
                action = f"Vorhandene Datei ersetzen -> {path.name}"
            else:
                action = "Entscheidung erforderlich"
            lines.append(f"{label} | KONFLIKT: {path.name} | {action}")
        else:
            lines.append(f"{label} | frei | wird erstellt: {path.name}")
    return "\n".join(lines)


def build_tui_existing_output_rename_text(plan: PreparedRecordingPlan) -> str:
    if not plan.existing_output_renames:
        return ""
    lines = ["Vorhandene Dateien werden umbenannt:"]
    lines.extend(f"- {source.name} -> {target.name}" for source, target in plan.existing_output_renames)
    lines.append("Erst der finale Ausfuehren-Button fuehrt diese Umbenennungen aus.")
    return "\n".join(lines)


def build_tui_target_conflict_decision_text(conflicts: tuple[TuiTargetConflict, ...]) -> str:
    if not conflicts:
        return ""
    lines = [
        "STOPP: Es gibt bereits Dateien mit gleichem Namen.",
        "Es wird nichts ueberschrieben, bis du bewusst entscheidest.",
        "",
        build_tui_target_conflict_text(conflicts),
        "",
        "Was moechtest du tun?",
        "",
        "Waehle rechts 'Vorhandene Dateien ersetzen' oder gehe zurueck und waehle einen anderen Zielordner.",
    ]
    return "\n".join(lines)


def build_tui_overwrite_confirmed_text() -> str:
    return "Ersetzen bestaetigt.\nBeim naechsten Klick werden die vorhandenen Ziel-Dateien ersetzt."


def tui_conflict_action_labels() -> tuple[str, str, str]:
    return (
        "Zurueck: anderen Zielordner waehlen",
        "Vorhandene Dateien ersetzen",
        "Abbrechen",
    )


def tui_processing_finished_action_labels() -> tuple[str, str, str]:
    return (
        "Zielordner oeffnen",
        "Neue Aufnahme vorbereiten (zurueck zu Schritt 1)",
        "Beenden",
    )


def apply_tui_overwrite_confirmation(plan: PreparedRecordingPlan) -> PreparedRecordingPlan:
    return replace(
        plan,
        mp4_action=MP4_ACTION_OVERWRITE,
        overwrite_existing_outputs=True,
    )


def apply_tui_output_suffix(plan: PreparedRecordingPlan, suffix: str) -> PreparedRecordingPlan:
    cleaned = sanitize_filename_part(suffix)
    if not cleaned:
        raise ValueError("Bitte einen Zusatz fuer die neuen Dateien eingeben.")
    return apply_output_filenames(
        plan,
        mp4_filename=f"{plan.target_mp4.stem} - {cleaned}{plan.target_mp4.suffix}",
        mp3_filename=f"{plan.target_mp3.stem} - {cleaned}{plan.target_mp3.suffix}",
        summary_filename=f"{plan.summary_path.stem} - {cleaned}{plan.summary_path.suffix}",
    )


def apply_tui_backup_existing_confirmation(plan: PreparedRecordingPlan) -> PreparedRecordingPlan:
    mp4_action = plan.mp4_action
    if mp4_action in {MP4_ACTION_OVERWRITE, MP4_ACTION_KEEP}:
        mp4_action = MP4_ACTION_COPY
    return replace(
        plan,
        mp4_action=mp4_action,
        overwrite_existing_outputs=False,
        backup_existing_outputs=True,
        existing_output_renames=planned_existing_output_renames(plan),
    )


def build_tui_execute_button_state(
    plan: PreparedRecordingPlan,
    *,
    overwrite_confirmed: bool,
) -> tuple[str, bool]:
    conflicts = detect_tui_target_conflicts(plan)
    if conflicts and not overwrite_confirmed and not plan.backup_existing_outputs:
        return "Erst entscheiden: ersetzen oder zurückgehen", True
    if conflicts and plan.backup_existing_outputs:
        return "Gesicherte Dateien behalten und finale Dateien erstellen", False
    if conflicts:
        return "Vorhandene Dateien ersetzen und finale Dateien erstellen", False
    return TUI_PROCESSING_EXECUTE_LABEL, False


def tui_processing_warning_class(conflicts: tuple[TuiTargetConflict, ...]) -> str:
    severities = {conflict.severity for conflict in conflicts}
    if "danger" in severities:
        return "status-danger"
    if "warning" in severities:
        return "status-warning"
    return "status-ok"


def tui_processing_review_back_target() -> str:
    return "target-folder-review"


def tui_action_requires_confirmation(action: str) -> bool:
    return action in {"overwrite", "move_raw_recording", "detected_cut_export"}


def _same_tui_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left.absolute() == right.absolute()


def build_tui_preparation_text(preparation: TuiPreparation) -> str:
    source_text = str(preparation.source_mp4) if preparation.source_mp4 is not None else "noch nicht ausgewaehlt"
    raw_text = str(preparation.raw_recording) if preparation.raw_recording is not None else "-"
    return "\n".join(
        [
            f"Quell-MP4 / geschnittene MP4: {source_text}",
            f"Rohaufnahme: {raw_text}",
            f"Zielordner: {preparation.target_folder}",
            f"Finale MP4: {preparation.target_mp4.name}",
            f"Finale MP3: {preparation.target_mp3.name}",
            f"Zusammenfassung: {preparation.summary_path}",
        ]
    )


def build_tui_start_status_text(config: AppConfig) -> str:
    return "\n".join(
        [
            "Dieses Tool bereitet Gemeinde-Aufnahmen fuer WordPress/Vimeo vor: Rohaufnahme waehlen, bei Bedarf in LosslessCut schneiden, Metadaten erfassen, Zielordner pruefen und finale MP4/MP3/Zusammenfassung erstellen.",
            "Produktiver Standard bleibt der normale Wizard.",
            "MP4-Dateien ansehen: nur Anzeige/Info im Textual-Prototyp.",
            "Einstellungen: nur Anzeige/Info im Textual-Prototyp.",
            f"Ziel-Basisordner: {config.recordings_base}",
            f"Rohaufnahme-Ordner: {config.vmix_storage}",
        ]
    )


def build_tui_start_safety_text() -> str:
    return "\n".join(
        [
            *TUI_START_SAFETY_QUESTIONS,
            "",
            f"[!] {TUI_START_SAFETY_WARNING}",
        ]
    )


def tui_start_safety_route(action_id: str | None) -> str:
    if action_id == "confirm":
        return "source"
    return "start"


def build_tui_file_candidates_lines(config: AppConfig, *, limit: int = TUI_MP4_PREVIEW_LIMIT) -> tuple[str, ...]:
    lines: list[str] = ["MP4-Dateien zur Orientierung"]
    if config.cut_mp4_folder is None:
        lines.append("Schnitt-/Exportordner: noch nicht gemerkt")
    else:
        lines.extend(_build_tui_folder_file_lines("Schnitt-/Exportordner", config.cut_mp4_folder, limit=limit))
    lines.append("")
    lines.extend(_build_tui_folder_file_lines("Rohaufnahme-Ordner", config.vmix_storage, limit=limit))
    return tuple(lines)


def _build_tui_folder_file_lines(label: str, folder: Path, *, limit: int) -> tuple[str, ...]:
    lines = [f"{label}: {folder}"]
    if not folder.exists():
        return tuple(lines + ["Ordner wurde nicht gefunden."])
    if not folder.is_dir():
        return tuple(lines + ["Pfad ist kein Ordner."])

    files = _newest_mp4_files(folder, limit=limit)
    if not files:
        return tuple(lines + ["Keine MP4-Dateien gefunden."])
    lines.extend(_format_tui_file_line(path) for path in files)
    return tuple(lines)


def _newest_mp4_files(folder: Path, *, limit: int) -> tuple[Path, ...]:
    files = [path for path in folder.glob("*.mp4") if path.is_file()]
    return tuple(sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:limit])


def _format_tui_file_line(path: Path) -> str:
    try:
        stat = path.stat()
    except OSError:
        return f"- {path.name}"
    changed = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    size_mb = stat.st_size / (1024 * 1024)
    return f"- {path.name} | geaendert: {changed} | Groesse: {size_mb:.1f} MB"


def tui_cut_mp4_folder(config: AppConfig) -> Path:
    return config.cut_mp4_folder or config.vmix_storage


def tui_cut_mp4_folder_for_raw(config: AppConfig, raw_recording: Path | None) -> Path:
    if config.cut_mp4_folder is not None:
        return config.cut_mp4_folder
    if raw_recording is not None:
        return raw_recording.parent
    return config.vmix_storage


def build_tui_mp4_selection_config(
    config: AppConfig,
    *,
    mode: str,
    raw_recording: Path | None = None,
) -> TuiMp4SelectionConfig:
    if mode == "cut":
        return TuiMp4SelectionConfig(
            mode="cut",
            start_folder=tui_cut_mp4_folder_for_raw(config, raw_recording),
            title="Geschnittene MP4 auswaehlen",
            note="Waehle die bereits geschnittene MP4. Es wird noch nichts kopiert oder verschoben.",
            suggest_newest=True,
            allow_search=True,
            allow_manual_input=True,
        )
    if mode == "raw":
        return TuiMp4SelectionConfig(
            mode="raw",
            start_folder=config.vmix_storage,
            title="Rohaufnahme auswaehlen",
            note="Waehle die Rohaufnahme. Der Schnitt bleibt weiterhin ein bewusster Schritt mit LosslessCut.",
            suggest_newest=True,
            allow_search=True,
            allow_manual_input=True,
        )
    raise ValueError(f"Unbekannter MP4-Auswahlmodus: {mode}")


def tui_source_choice_route(action_id: str | None) -> str:
    if action_id == "cut":
        return "cut-selection"
    if action_id == "raw":
        return "raw-selection"
    return "start"


def tui_file_selection_next_screen(*, already_cut: bool) -> str:
    if already_cut:
        return "metadata"
    return "losslesscut"


def build_tui_mp4_selection_actions(selection: TuiMp4SelectionConfig) -> tuple[str, ...]:
    actions: list[str] = []
    if selection.suggest_newest:
        actions.append("newest")
    actions.append("recent")
    if selection.allow_search:
        actions.append("search")
    if selection.allow_manual_input:
        actions.append("manual")
    actions.extend(("back", "cancel"))
    return tuple(actions)


def newest_tui_mp4_candidates(
    folder: Path,
    *,
    search_text: str = "",
    limit: int = TUI_FILE_CHOICE_LIMIT,
) -> tuple[Path, ...]:
    if not folder.exists() or not folder.is_dir():
        return ()
    normalized = search_text.strip().casefold()
    files = [path for path in folder.glob("*.mp4") if path.is_file()]
    if normalized:
        files = [path for path in files if normalized in path.name.casefold()]
    return tuple(sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:limit])


def tui_export_candidate_folders(config: AppConfig, raw_recording: Path) -> tuple[Path, ...]:
    folders: list[Path] = []
    if config.cut_mp4_folder is not None:
        folders.append(config.cut_mp4_folder)
    folders.extend((raw_recording.parent, config.vmix_storage))
    if config.recordings_base.exists():
        folders.append(config.recordings_base)
    return _unique_paths(tuple(folders))


def _unique_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.absolute()).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return tuple(unique)


def snapshot_tui_mp4_files(folders: tuple[Path, ...]) -> tuple[TuiMp4SnapshotEntry, ...]:
    entries: list[TuiMp4SnapshotEntry] = []
    for folder in _unique_paths(folders):
        if not folder.exists() or not folder.is_dir():
            continue
        for path in folder.glob("*.mp4"):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append(TuiMp4SnapshotEntry(path=path, size=stat.st_size, modified_at=stat.st_mtime))
    return tuple(entries)


def detect_tui_export_candidates(
    before: tuple[TuiMp4SnapshotEntry, ...],
    after: tuple[TuiMp4SnapshotEntry, ...],
    *,
    raw_recording: Path,
    started_at: datetime,
    preferred_folders: tuple[Path, ...] = (),
) -> tuple[TuiExportCandidate, ...]:
    before_by_path = {_path_key(entry.path): entry for entry in before}
    started_timestamp = started_at.timestamp()
    candidates: list[TuiExportCandidate] = []
    for entry in after:
        if _same_tui_path(entry.path, raw_recording):
            continue
        old = before_by_path.get(_path_key(entry.path))
        is_new = old is None
        changed = old is not None and (old.size != entry.size or old.modified_at != entry.modified_at)
        modified_after_start = entry.modified_at >= started_timestamp
        if not (is_new or changed or modified_after_start):
            continue
        score, reason = score_tui_export_candidate(
            entry,
            previous=old,
            raw_recording=raw_recording,
            started_at=started_at,
            preferred_folders=preferred_folders,
        )
        candidates.append(
            TuiExportCandidate(
                path=entry.path,
                score=score,
                reason=reason,
                modified=_format_timestamp(entry.modified_at),
                size=_format_size(entry.size),
            )
        )
    return tuple(sorted(candidates, key=lambda candidate: candidate.score, reverse=True))


def score_tui_export_candidate(
    entry: TuiMp4SnapshotEntry,
    *,
    previous: TuiMp4SnapshotEntry | None,
    raw_recording: Path,
    started_at: datetime,
    preferred_folders: tuple[Path, ...] = (),
) -> tuple[int, str]:
    score = 0
    reasons: list[str] = []
    modified_after_start = entry.modified_at >= started_at.timestamp()
    if previous is None:
        score += 50
        reasons.append("neu im beobachteten Ordner")
    elif previous.size != entry.size or previous.modified_at != entry.modified_at:
        score += 35
        reasons.append("seit Schnittschritt geaendert")
    if modified_after_start:
        score += 40
        reasons.append("nach LosslessCut-Start")
    raw_stem = raw_recording.stem.casefold()
    if raw_stem and raw_stem in entry.path.stem.casefold():
        score += 20
        reasons.append("Name passt zur Rohaufnahme")
    if not _same_tui_path(entry.path, raw_recording):
        score += 10
    if any(_same_tui_path(entry.path.parent, folder) for folder in preferred_folders):
        score += 10
        reasons.append("passender Ordner")
    if not modified_after_start:
        score -= 20
        if previous is None:
            reasons.append("neu erkannt, Aenderungsdatum aelter als Schnittstart")
        else:
            reasons.append("Aenderungsdatum vor Schnittstart")
    return score, ", ".join(reasons) if reasons else "moeglicher Export"


def build_tui_export_detection_text(candidates: tuple[TuiExportCandidate, ...]) -> str:
    if not candidates:
        return "Es wurde keine neue oder geaenderte MP4-Datei erkannt. Bitte waehle die exportierte Schnittdatei manuell aus."
    if len(candidates) == 1:
        return "Diese Datei wurde nach dem Oeffnen von LosslessCut neu erstellt oder geaendert. Bitte kontrollieren und bestaetigen."
    return "Bitte kontrollieren. Das Programm schlaegt nur vor."


def _path_key(path: Path) -> str:
    return str(path.absolute()).casefold()


def _format_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _format_size(size: int) -> str:
    return f"{size / (1024 * 1024):.1f} MB"


def newest_tui_mp4_candidate(folder: Path) -> Path | None:
    candidates = newest_tui_mp4_candidates(folder, limit=1)
    if not candidates:
        return None
    return candidates[0]


def build_tui_mp4_file_rows(
    folder: Path,
    *,
    search_text: str = "",
    limit: int = TUI_FILE_CHOICE_LIMIT,
) -> tuple[TuiMp4FileRow, ...]:
    return tuple(_build_tui_mp4_file_row(path) for path in newest_tui_mp4_candidates(folder, search_text=search_text, limit=limit))


def _build_tui_mp4_file_row(path: Path) -> TuiMp4FileRow:
    try:
        stat = path.stat()
    except OSError:
        return TuiMp4FileRow(path=path, filename=path.name, modified="unbekannt", size="unbekannt")
    changed = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    size_mb = stat.st_size / (1024 * 1024)
    return TuiMp4FileRow(path=path, filename=path.name, modified=changed, size=f"{size_mb:.1f} MB")


def build_tui_file_choice_lines(
    folder: Path,
    *,
    search_text: str = "",
    limit: int = TUI_FILE_CHOICE_LIMIT,
) -> tuple[str, ...]:
    candidates = newest_tui_mp4_candidates(folder, search_text=search_text, limit=limit)
    if not folder.exists():
        return (f"Ordner wurde nicht gefunden: {folder}",)
    if not folder.is_dir():
        return (f"Pfad ist kein Ordner: {folder}",)
    if not candidates:
        return ("Keine passenden MP4-Dateien gefunden.",)
    return tuple(_format_tui_file_line(path) for path in candidates)


def detect_tui_recording_date_from_filename(path: Path) -> date | None:
    match = re.search(r"\b(\d{1,2})\s+([A-Za-zÄÖÜäöüß]+)\s+(\d{4})\b", path.stem)
    if match is None:
        return None
    day = int(match.group(1))
    month_name = match.group(2).casefold().replace("ä", "ae")
    month = GERMAN_MONTHS.get(month_name)
    if month is None:
        return None
    try:
        return date(int(match.group(3)), month, day)
    except ValueError:
        return None


def tui_file_modified_date(path: Path) -> date | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date()
    except OSError:
        return None


def build_tui_date_options(source_mp4: Path | None, today: date | None = None) -> tuple[TuiDateOption, ...]:
    return build_tui_date_options_for_sources(source_mp4=source_mp4, raw_recording=None, today=today)


def build_tui_date_options_for_sources(
    source_mp4: Path | None,
    raw_recording: Path | None,
    today: date | None = None,
) -> tuple[TuiDateOption, ...]:
    current = today or date.today()
    options = [TuiDateOption(f"Heutiges Datum: {current.isoformat()}", current, "today")]

    def add_filename_option(path: Path, kind: str, label: str) -> bool:
        filename_date = detect_tui_recording_date_from_filename(path)
        if filename_date is not None:
            options.append(TuiDateOption(f"{label}: {filename_date.isoformat()}", filename_date, kind))
            return True
        return False

    filename_found = False
    if raw_recording is not None:
        filename_found = add_filename_option(raw_recording, "raw_filename", "Aufnahmedatum aus Rohaufnahme-Dateiname")
    if source_mp4 is not None and not filename_found:
        source_kind = "filename" if raw_recording is None else "source_filename"
        filename_found = add_filename_option(source_mp4, source_kind, "Aufnahmedatum aus MP4-Dateiname")

    if not filename_found:
        filedate_path = raw_recording or source_mp4
        if filedate_path is not None:
            modified_date = tui_file_modified_date(filedate_path)
            if modified_date is not None:
                kind = "raw_filedate" if raw_recording is not None else "filedate"
                label = "Dateidatum der Rohaufnahme" if raw_recording is not None else "Dateidatum der MP4"
                options.append(TuiDateOption(f"{label}: {modified_date.isoformat()}", modified_date, kind))

    options.append(TuiDateOption("Benutzerdefiniertes Datum", current, "custom"))
    return tuple(options)


def preferred_tui_date_option(options: tuple[TuiDateOption, ...]) -> TuiDateOption:
    priorities = (
        "raw_filename",
        "filename",
        "source_filename",
        "raw_filedate",
        "filedate",
        "source_filedate",
        "today",
        "custom",
    )
    for priority in priorities:
        for option in options:
            if option.kind == priority:
                return option
    return options[0]


def date_from_tui_option(kind: str, options: tuple[TuiDateOption, ...], custom_text: str) -> date:
    if kind == "custom":
        return parse_tui_date_or_today(custom_text)
    for option in options:
        if option.kind == kind:
            return option.value
    return options[0].value


def build_tui_settings_lines(config: AppConfig) -> tuple[str, ...]:
    losslesscut = config.losslesscut_path or "PATH / Windows-App-Alias"
    return (
        f"Ziel-Basisordner: {config.recordings_base}",
        f"Rohaufnahme-Ordner: {config.vmix_storage}",
        f"LosslessCut-Pfad: {losslesscut}",
        f"Jahresordner-Format: {config.year_folder_template}",
        f"Rohaufnahme-Aufräumen: {config.raw_archive_mode}",
    )


def service_types_for_tui(config: AppConfig) -> tuple[ServiceTypeConfig, ...]:
    return default_service_types(config) + config.custom_service_types


def tui_service_type_display_name(internal_name: str) -> str:
    if internal_name.casefold() == "predigt":
        return "Gottesdienst"
    return internal_name


def normalize_tui_service_type_name(name: str) -> str:
    if name.strip().casefold() == "gottesdienst":
        return "Predigt"
    return name


def tui_service_type_options(config: AppConfig) -> tuple[tuple[str, str], ...]:
    return tuple((tui_service_type_display_name(service.name), service.name) for service in service_types_for_tui(config))


def service_type_by_name(config: AppConfig, name: str) -> ServiceTypeConfig:
    normalized = normalize_tui_service_type_name(name).casefold()
    for service_type in service_types_for_tui(config):
        if service_type.name.casefold() == normalized:
            return service_type
    return service_types_for_tui(config)[0]


def default_tui_service_type_name(config: AppConfig, sermon_date: date) -> str:
    weekday_defaults = {
        2: "Bibelstunde",
        4: "Gebetsstunde",
        6: "Predigt",
    }
    preferred = weekday_defaults.get(sermon_date.weekday(), "Predigt")
    for service_type in service_types_for_tui(config):
        if service_type.name.casefold() == preferred.casefold():
            return service_type.name
    return service_types_for_tui(config)[0].name


def default_tui_service_type_for_sources(
    config: AppConfig,
    source_mp4: Path | None,
    raw_recording: Path | None,
    today: date | None = None,
) -> str:
    options = build_tui_date_options_for_sources(source_mp4=source_mp4, raw_recording=raw_recording, today=today)
    return default_tui_service_type_name(config, preferred_tui_date_option(options).value)


def tui_service_type_after_date_change(
    config: AppConfig,
    selected_date: date,
    current_service_type: str,
    *,
    service_type_manually_changed: bool,
) -> str:
    if service_type_manually_changed:
        return current_service_type
    return default_tui_service_type_name(config, selected_date)


def parse_tui_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def parse_tui_date_or_today(value: str) -> date:
    parsed = parse_tui_date(value)
    if parsed is None:
        return date.today()
    return parsed


def build_tui_metadata_info(
    *,
    config: AppConfig,
    date_text: str,
    service_type_name: str,
    title: str,
    bible_reference: str,
    speaker: str,
    folder_note: str,
) -> SermonInfo:
    return SermonInfo(
        sermon_date=parse_tui_date_or_today(date_text),
        title=title,
        bible_reference=bible_reference,
        speaker=speaker,
        sermon_type=service_type_by_name(config, service_type_name).name,
        folder_note=folder_note,
    )


def validate_tui_metadata(info: SermonInfo, config: AppConfig, *, date_text: str | None = None) -> tuple[str, ...]:
    messages: list[str] = []
    if date_text is not None and parse_tui_date(date_text) is None:
        messages.append("Datum bitte im Format YYYY-MM-DD eingeben.")

    service_type = service_type_config_for(config, info.sermon_type)
    if service_type.requires_title and not info.title.strip():
        messages.append(f"{service_type.title_label} fehlt.")
    if service_type.requires_bible_reference and not info.bible_reference.strip():
        messages.append(f"{service_type.bible_reference_label} fehlt.")
    if service_type.requires_speaker and not info.speaker.strip():
        messages.append(f"{service_type.speaker_label} fehlt.")
    return tuple(messages)


def missing_tui_metadata_fields(info: SermonInfo, config: AppConfig, *, date_text: str | None = None) -> tuple[str, ...]:
    fields: list[str] = []
    if date_text is not None and parse_tui_date(date_text) is None:
        fields.append("date")

    service_type = service_type_config_for(config, info.sermon_type)
    if service_type.requires_title and not info.title.strip():
        fields.append("title")
    if service_type.requires_bible_reference and not info.bible_reference.strip():
        fields.append("bible")
    if service_type.requires_speaker and not info.speaker.strip():
        fields.append("speaker")
    return tuple(fields)


def build_tui_validation_text(messages: tuple[str, ...]) -> str:
    if not messages:
        return "Metadaten vollstaendig. Weiter geht es zur finalen Pruefung."
    return "Bitte ergaenzen:\n" + "\n".join(f"- {message}" for message in messages)


def build_tui_metadata_validation_text(messages: tuple[str, ...]) -> str:
    if not messages:
        return "Alle Pflichtfelder ausgefüllt."
    normalized_messages = tuple(_normalize_tui_metadata_message(message) for message in messages)
    return f"Noch auszufüllen: {', '.join(normalized_messages)}"


def _normalize_tui_metadata_message(message: str) -> str:
    cleaned = message.strip().rstrip(".")
    if cleaned.casefold().endswith(" fehlt"):
        cleaned = cleaned[:-6].rstrip()
    return cleaned


def build_tui_metadata_scroll_hint_text(
    missing_fields_above: tuple[str, ...],
    missing_fields_below: tuple[str, ...],
) -> str:
    if not missing_fields_above and not missing_fields_below:
        return ""
    if missing_fields_below:
        if len(missing_fields_below) == 1:
            return "↓ Pflichtfeld weiter unten"
        return f"↓ {len(missing_fields_below)} Pflichtfelder weiter unten"
    if len(missing_fields_above) == 1:
        return "↑ Pflichtfeld weiter oben"
    return f"↑ {len(missing_fields_above)} Pflichtfelder weiter oben"


def classify_tui_metadata_fields_by_position(
    field_regions: tuple[tuple[str, int, int], ...],
    *,
    viewport_top: int,
    viewport_bottom: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    above: list[str] = []
    below: list[str] = []
    for field_name, field_top, field_bottom in field_regions:
        if field_bottom <= viewport_top:
            above.append(field_name)
        elif field_top >= viewport_bottom:
            below.append(field_name)
    return tuple(above), tuple(below)


def build_tui_processing_started_status() -> str:
    return "\n".join(
        [
            "Verarbeitung gestartet...",
            "Bitte warten. Dateien werden erstellt/kopiert/verschoben.",
        ]
    )


def build_tui_vimeo_plan_text(plan: PreparedRecordingPlan, config: AppConfig) -> str:
    return "\n".join(
        [
            f"Lokale MP4: {plan.target_mp4}",
            f"Vimeo-Team / Konto: Team-Owner {config.vimeo.team_owner_user_id}",
            f"Zielordner: {config.vimeo.target_folder_name} (ID {config.vimeo.target_folder_id})",
            f"Vimeo-Titel: {build_vimeo_title(plan.info, plan.target_mp4)}",
        ]
    )


def build_tui_vimeo_initial_status(state: VimeoState | None) -> str:
    if state is None:
        return "Der lokale Workflow-Status fehlt. Vimeo kann noch nicht sicher gestartet werden."
    if state.step.status == "complete" and state.video_id:
        return "Vimeo-Upload abgeschlossen. Die vorhandene Video-ID wird weiterverwendet."
    if state.step.status == "stopped":
        return (
            "Der Vimeo-Upload wurde gestoppt. Die lokale Aufnahme ist unverändert; "
            "ein erneuter Versuch setzt den bestätigten tus-Stand fort."
        )
    if state.video_id:
        return (
            "Ein Vimeo-Video ist bereits bekannt. Beim Fortsetzen wird diese Video-ID wiederverwendet; "
            "es wird kein zweiter Platzhalter angelegt."
        )
    if state.step.status == "failed":
        return "Der letzte Vimeo-Versuch ist fehlgeschlagen. Die lokalen Dateien sind sicher fertig."
    return "Bereit. Erst der blaue Button startet die Vimeo-Veröffentlichung."


def build_tui_vimeo_available_actions_text(state: VimeoState | None, *, running: bool) -> str:
    if state is None:
        return ""
    lines: list[str] = []
    if state.video_url:
        lines.append("✓ Vimeo-Link verfügbar – das Video kann bereits auf Vimeo geöffnet werden.")
    if state.embed_html:
        lines.append("✓ Embed-Code verfügbar – kann bereits in WordPress eingefügt werden.")
    if running and state.video_url and state.embed_html:
        lines.append("Sie müssen für diese beiden Angaben nicht auf 100 % Upload warten.")
    return "\n".join(lines)


def build_tui_vimeo_progress_text(
    phase: str | None = None,
    *,
    percent: float = 0.0,
    transcode_status: str | None = None,
    failed_phase: str | None = None,
    video_url_available: bool = False,
    embed_available: bool = False,
) -> str:
    active_by_phase = {
        "checking_connection": "connection",
        "creating_remote_video": "remote_video",
        "fetching_early_embed": "embed",
        "uploading": "upload",
        "verifying_upload": "verify_upload",
        "assigning_folder": "folder",
        "verifying_folder": "folder",
        "processing_video": "processing",
        "fetching_embed": "embed",
    }
    completed_before = {
        "preparing": {"connection"},
        "creating_remote_video": {"connection"},
        "uploading": {"connection", "remote_video"},
        "verifying_upload": {"connection", "remote_video", "upload"},
        "assigning_folder": {"connection", "remote_video", "upload", "verify_upload"},
        "verifying_folder": {"connection", "remote_video", "upload", "verify_upload"},
        "processing_video": {"connection", "remote_video", "upload", "verify_upload", "folder"},
        "fetching_early_embed": {"connection", "remote_video"},
        "video_link_available": {"connection", "remote_video"},
        "early_embed_available": {"connection", "remote_video"},
        "fetching_embed": {"connection", "remote_video", "upload", "verify_upload", "folder"},
        "complete": {key for key, _label in TUI_VIMEO_STAGE_LABELS},
    }
    completed = set(completed_before.get(phase or "", set()))
    if video_url_available:
        completed.add("video_link")
    if embed_available:
        completed.add("embed")
    active = active_by_phase.get(phase or "")
    if active in completed:
        active = None
    normalized_transcode = (transcode_status or "").lower()
    if phase == "complete" and normalized_transcode not in {"complete", "completed"}:
        completed.discard("processing")
        active = "processing"
    failed = active_by_phase.get(failed_phase or "")
    lines: list[str] = []
    for key, label in TUI_VIMEO_STAGE_LABELS:
        if key == failed:
            marker = "✗"
        elif key in completed:
            marker = "✓"
        elif key == active:
            marker = "⟳"
        else:
            marker = "○"
        if key == "upload" and key == active:
            label = f"{label}: {percent:.1f} %"
        if key == "processing" and normalized_transcode:
            label = f"{label} …  Status: {normalized_transcode.upper()}"
        lines.append(f"{marker} {label}")
    return "\n".join(lines)


def format_tui_vimeo_upload_details(progress: VimeoProgress) -> str:
    transferred = _format_vimeo_bytes(progress.uploaded_bytes)
    total = _format_vimeo_bytes(progress.total_bytes)
    lines = [f"{transferred} / {total}"]
    if progress.bytes_per_second and progress.bytes_per_second > 0:
        speed = f"{_format_vimeo_bytes(progress.bytes_per_second)}/s"
        if progress.eta_seconds is not None:
            lines.append(f"{speed} · ca. {_format_vimeo_eta(progress.eta_seconds)} verbleibend")
        else:
            lines.append(speed)
    return "\n".join(lines)


def filter_tui_vimeo_library_videos(
    videos: tuple[VimeoLibraryVideo, ...],
    search_text: str,
) -> tuple[VimeoLibraryVideo, ...]:
    needle = search_text.strip().casefold()
    if not needle:
        return videos
    return tuple(video for video in videos if needle in video.title.casefold())


def sort_tui_vimeo_library_videos(
    videos: tuple[VimeoLibraryVideo, ...],
    order: str,
) -> tuple[VimeoLibraryVideo, ...]:
    if order == "oldest":
        return tuple(sorted(videos, key=lambda video: video.created_time or ""))
    if order == "title_az":
        return tuple(sorted(videos, key=lambda video: video.title.casefold()))
    if order == "title_za":
        return tuple(sorted(videos, key=lambda video: video.title.casefold(), reverse=True))
    return tuple(sorted(videos, key=lambda video: video.created_time or "", reverse=True))


def build_tui_vimeo_breadcrumbs(
    team_name: str,
    catalog: VimeoFolderCatalog | None,
    folder_id: str | None,
) -> str:
    names = [team_name]
    if catalog is not None:
        names.extend(folder.name for folder in catalog.breadcrumbs(folder_id))
    return " > ".join(names)


def _application_version() -> str:
    try:
        return version("predigt-uploader")
    except PackageNotFoundError:
        return "Entwicklungsstand"


def build_tui_vimeo_library_details(video: VimeoLibraryVideo, folder_name: str) -> str:
    processing = video.transcode_status or video.status or "unbekannt"
    lines = [
        f"Titel: {video.title}",
        f"Vimeo-ID: {video.video_id}",
        f"Vimeo-URL: {video.video_url or '(nicht geliefert)'}",
        f"Player-/Embed-URL: {video.player_embed_url or '(nicht geliefert)'}",
        f"Status: {processing.upper()}",
        f"Uploadstatus: {(video.upload_status or 'unbekannt').upper()}",
        f"Dauer: {_format_vimeo_duration(video.duration)}",
        f"Privacy: Ansicht {video.privacy_view or 'unbekannt'}, Embed {video.privacy_embed or 'unbekannt'}",
        f"Ordner: {folder_name}",
        f"Erstellt: {_format_vimeo_created_time(video.created_time)}",
        f"Embed-Code: {'verfügbar' if video.embed_html else 'nicht geliefert'}",
    ]
    if video.downloads:
        lines.append("Download-Dateien von Vimeo:")
        for item in video.downloads:
            resolution = f"{item.width}×{item.height}" if item.width and item.height else "Auflösung unbekannt"
            size = _format_vimeo_bytes(item.size) if item.size is not None else "Größe unbekannt"
            lines.append(f"- {item.quality} · {resolution} · {size} · {item.file_type or 'Typ unbekannt'}")
        lines.append("Es wurde kein Download gestartet.")
    else:
        lines.append(
            "Download: Vimeo hat für dieses Token/Video keine direkte Download-Datei geliefert."
        )
    return "\n".join(lines)


def _format_vimeo_duration(seconds: int | None) -> str:
    if seconds is None:
        return "unbekannt"
    minutes, secs = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _format_vimeo_created_time(value: str | None) -> str:
    if not value:
        return "unbekannt"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone().strftime("%d.%m.%Y %H:%M")


def _format_vimeo_bytes(value: float | int) -> str:
    amount = max(0.0, float(value))
    units = ("B", "KB", "MB", "GB", "TB")
    unit = units[0]
    for candidate in units:
        unit = candidate
        if amount < 1024 or candidate == units[-1]:
            break
        amount /= 1024
    if unit == "B":
        rendered = f"{amount:.0f}"
    elif amount >= 100:
        rendered = f"{amount:.0f}"
    elif amount >= 10:
        rendered = f"{amount:.1f}"
    else:
        rendered = f"{amount:.2f}"
    return f"{rendered.replace('.', ',')} {unit}"


def _format_vimeo_eta(seconds: float) -> str:
    remaining = max(0, int(round(seconds)))
    hours, remainder = divmod(remaining, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def build_tui_vimeo_success_text(plan: PreparedRecordingPlan, state: VimeoState) -> str:
    processing = (state.transcode_status or "").lower() not in {"complete", "completed"}
    return "\n".join(
        [
            (
                "Datei vollständig hochgeladen – Vimeo verarbeitet das Video"
                if processing
                else "Vimeo-Upload abgeschlossen"
            ),
            f"Vimeo-Titel: {build_vimeo_title(plan.info, plan.target_mp4)}",
            f"Zielordner: {state.target_folder_name or 'Predigten'}",
            f"Vimeo-URL: {state.video_url or '(noch nicht gemeldet)'}",
            f"Transkodierung: {(state.transcode_status or 'unbekannt').upper()}",
            f"Player-URL: {'vorhanden' if state.player_embed_url else 'noch nicht vorhanden'}",
            f"Embed-Code: {'abgerufen' if state.embed_html else 'noch nicht vorhanden'}",
        ]
    )


def build_tui_vimeo_error_text(error: Exception, state: VimeoState | None) -> str:
    if isinstance(error, VimeoError):
        message = error.user_message
        admin = f"\nAdmin-Hinweis: {error.admin_hint}" if error.admin_hint else ""
    else:
        message = "Die Vimeo-Veröffentlichung konnte nicht abgeschlossen werden."
        admin = f"\nAdmin-Hinweis: {type(error).__name__}: {error}"
    known = ""
    if state and state.video_id:
        known = f"\nBekannte Vimeo-Video-ID: {state.video_id}\nDiese ID wird beim nächsten Versuch wiederverwendet."
    return (
        "Vimeo-Veröffentlichung noch nicht abgeschlossen.\n"
        "Die lokale MP4, MP3 und Zusammenfassung sind sicher fertig.\n"
        f"Ursache: {message}{known}{admin}"
    )


def build_tui_processing_success_status(
    plan: PreparedRecordingPlan,
    *,
    opened_target_folder: bool = True,
    vimeo_state: VimeoState | None = None,
) -> str:
    folder_status = (
        "Der Zielordner wurde geoeffnet."
        if opened_target_folder
        else "Der Zielordner konnte nicht automatisch geoeffnet werden. Bitte nutze den Button zum erneuten Oeffnen oder oeffne den Pfad manuell."
    )
    vimeo_complete = bool(vimeo_state and vimeo_state.step.status == "complete" and vimeo_state.video_id)
    vimeo_lines = (
        [
            "✓ Video zu Vimeo hochgeladen.",
            f"✓ Ordner {vimeo_state.target_folder_name or 'Predigten'}.",
            f"✓ Embed-Code {'abgerufen' if vimeo_state.embed_html else 'noch nicht abgerufen'}.",
            f"Vimeo-URL: {vimeo_state.video_url or '(noch nicht gemeldet)'}",
        ]
        if vimeo_complete
        else ["○ Vimeo-Upload noch ausstehend."]
    )
    manual_steps = (
        [
            "1. Zielordner kontrollieren.",
            "2. MP3 in WordPress hochladen.",
            "3. Predigtinformationen in WordPress eintragen.",
            "4. Gespeicherten Vimeo-Embed-Code in WordPress ergaenzen.",
            "5. Danach kann der PredigtUploader geschlossen oder eine neue Aufnahme vorbereitet werden.",
        ]
        if vimeo_complete
        else [
            "1. Zielordner kontrollieren.",
            "2. Vimeo-Upload spaeter im PredigtUploader fortsetzen.",
            "3. MP3 in WordPress hochladen.",
            "4. Predigtinformationen in WordPress eintragen.",
            "5. Vimeo/Embed-Code in WordPress ergaenzen.",
            "6. Danach kann der PredigtUploader geschlossen oder eine neue Aufnahme vorbereitet werden.",
        ]
    )
    return "\n".join(
        [
            "Lokale Vorbereitung abgeschlossen.",
            "✓ Lokale Dateien erstellt.",
            folder_status,
            "Vorhandene Ziel-Dateien wurden ersetzt." if plan.overwrite_existing_outputs else "",
            "Vorhandene Ziel-Dateien wurden gesichert." if plan.backup_existing_outputs else "",
            "",
            f"Zielordner: {plan.target_folder}",
            f"Finale MP4: {plan.target_mp4}",
            f"Finale MP3: {plan.target_mp3}",
            f"Zusammenfassung: {plan.summary_path}",
            f"Workflow-Status: {recording_workflow_state_path(plan.target_mp4)}",
            f"Rohaufnahme-Aktion: {raw_action_label(plan.raw_action, plan.raw_recording)}",
            "",
            *vimeo_lines,
            "",
            "Naechste manuelle Schritte:",
            *manual_steps,
        ]
    ).replace("\n\n\n", "\n\n")


def build_tui_processing_success_banner(plan: PreparedRecordingPlan, *, opened_target_folder: bool = True) -> str:
    if opened_target_folder:
        return "Fertig vorbereitet\nDie Dateien wurden erstellt und der Zielordner wurde geoeffnet."
    return "Fertig vorbereitet\nDie Dateien wurden erstellt. Der Zielordner konnte nicht automatisch geoeffnet werden."


def build_tui_processing_ready_text(plan: PreparedRecordingPlan) -> str:
    return (
        "Beim Klick werden die MP4/MP3/Zusammenfassung im Zielordner erstellt. "
        "Falls eine Rohaufnahme ausgewaehlt wurde, wird sie gemaess Auswahl behandelt."
    )


def build_tui_processing_source_text(plan: PreparedRecordingPlan) -> str:
    raw = str(plan.raw_recording) if plan.raw_recording is not None else "keine Rohaufnahme"
    return "\n".join(
        [
            "Was wird verwendet?",
            f"Geschnittene MP4: {plan.source_mp4}",
            f"Rohaufnahme: {raw}",
            f"Zielordner: {plan.target_folder}",
        ]
    )


def build_tui_processing_files_text(plan: PreparedRecordingPlan) -> str:
    return "\n".join(
        [
            "Welche Dateien werden erstellt?",
            f"Finale MP4: {plan.target_mp4}",
            f"Finale MP3: {plan.target_mp3}",
            f"Zusammenfassung: {plan.summary_path}",
        ]
    )


def build_tui_processing_raw_action_text(plan: PreparedRecordingPlan) -> str:
    return "\n".join(
        [
            "Was passiert mit der Rohaufnahme?",
            raw_action_label(plan.raw_action, plan.raw_recording),
        ]
    )


def build_tui_processing_warning_text(
    plan: PreparedRecordingPlan,
    conflicts: tuple[TuiTargetConflict, ...],
) -> str:
    if not conflicts:
        return "Status / Warnungen\nKeine Konflikte gefunden."
    return "\n".join(
        [
            "Status / Warnungen",
            build_tui_target_conflict_decision_text(conflicts),
        ]
    )


def build_tui_processing_error_status(messages: tuple[str, ...], error: str, *, target_folder: Path | None = None) -> str:
    lines = list(messages)
    lines.extend(
        [
            "",
            "Die Verarbeitung wurde nicht vollstaendig abgeschlossen.",
            f"Fehler: {error}",
            "Es wurden keine Dateien still ueberschrieben.",
        ]
    )
    if target_folder is not None:
        lines.append(f"Zielordner: {target_folder}")
    lines.append("Logdateien liegen, falls vorhanden, im Ordner logs.")
    return "\n".join(lines)


def build_tui_processing_review_action_text(plan: PreparedRecordingPlan) -> str:
    lines = [
        "Beim Klick passiert Folgendes:",
        "- Zielordner wird erstellt/geprueft",
        f"- {tui_mp4_action_text(plan)}",
        "- MP3 wird aus der geschnittenen MP4 erstellt",
        "- Zusammenfassung wird geschrieben",
        "- Rohaufnahme wird gemaess Auswahl verschoben/kopiert/liegen gelassen",
        "- Zielordner wird geoeffnet",
    ]
    if plan.raw_recording is not None and plan.raw_action == "move":
        lines.extend(
            [
                "",
                "Hinweis: Die Rohaufnahme wird aus dem Quellordner entfernt und in den Zielordner verschoben.",
            ]
        )
    return "\n".join(lines)


def tui_mp4_action_text(plan: PreparedRecordingPlan) -> str:
    if plan.mp4_action == MP4_ACTION_OVERWRITE:
        return "vorhandene Ziel-MP4 wird ersetzt"
    if plan.mp4_action == MP4_ACTION_KEEP:
        return "vorhandene Ziel-MP4 wird verwendet"
    if plan.mp4_action == MP4_ACTION_MOVE:
        return "geschnittene MP4 wird in den Zielordner verschoben"
    return "geschnittene MP4 wird in den Zielordner kopiert"


def build_tui_losslesscut_text(raw_recording: Path, config: AppConfig) -> str:
    lines = [
        "Jetzt wird LosslessCut geoeffnet.",
        "Exportiere die geschnittene Predigt in LosslessCut als MP4.",
        "Danach versucht der PredigtUploader, die exportierte Datei automatisch zu erkennen.",
        "Du musst den Vorschlag danach bestaetigen.",
        "Wenn du fertig bist, schliesse LosslessCut oder klicke auf Exportierte MP4 suchen.",
        "",
        f"Rohaufnahme: {raw_recording}",
    ]
    if not config.losslesscut_path.strip():
        lines.extend(
            [
                "",
                "LosslessCut wurde nicht gefunden. Bitte Pfad in den Einstellungen setzen oder Schnitt manuell durchfuehren.",
            ]
        )
    return "\n".join(lines)


def open_tui_losslesscut(raw_recording: Path, config: AppConfig) -> subprocess.Popen[bytes]:
    command = config.losslesscut_path.strip()
    if not command:
        raise FileNotFoundError(
            "LosslessCut wurde nicht gefunden. Bitte Pfad in den Einstellungen setzen oder Schnitt manuell durchfuehren."
        )
    return subprocess.Popen(
        [command, str(raw_recording)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def build_tui_field_labels(service_type: ServiceTypeConfig, *, missing_fields: tuple[str, ...] = ()) -> dict[str, str]:
    if service_type.requires_title:
        title_suffix = ""
    elif service_type.optional_title:
        title_suffix = " (optional)"
    else:
        title_suffix = " (nicht nötig)"
    bible_suffix = "" if service_type.requires_bible_reference else " (optional)"
    speaker_suffix = "" if service_type.requires_speaker else " (optional)"
    if not service_type.optional_bible_reference and not service_type.requires_bible_reference:
        bible_suffix = " (nicht nötig)"
    speaker_label = service_type.speaker_label
    if speaker_label.casefold() == "redner":
        speaker_label = "Redner / Leitung"

    def mark_missing(key: str, label: str) -> str:
        if key in missing_fields:
            return f"{label} - FEHLT"
        return label

    return {
        "title": mark_missing("title", f"{service_type.title_label}{title_suffix}"),
        "bible": mark_missing("bible", f"{service_type.bible_reference_label}{bible_suffix}"),
        "speaker": mark_missing("speaker", f"{speaker_label}{speaker_suffix}"),
    }


TUI_METADATA_FIELD_ORDER = ("title", "bible", "speaker")


def tui_metadata_required_field_keys(service_type: ServiceTypeConfig) -> tuple[str, ...]:
    keys: list[str] = []
    for field_key in TUI_METADATA_FIELD_ORDER:
        if field_key == "title" and service_type.requires_title:
            keys.append(field_key)
        elif field_key == "bible" and service_type.requires_bible_reference:
            keys.append(field_key)
        elif field_key == "speaker" and service_type.requires_speaker:
            keys.append(field_key)
    return tuple(keys)


def tui_metadata_optional_field_keys(service_type: ServiceTypeConfig) -> tuple[str, ...]:
    keys: list[str] = []
    for field_key in TUI_METADATA_FIELD_ORDER:
        if field_key == "title" and not service_type.requires_title:
            keys.append(field_key)
        elif field_key == "bible" and not service_type.requires_bible_reference:
            keys.append(field_key)
        elif field_key == "speaker" and not service_type.requires_speaker:
            keys.append(field_key)
    keys.append("folder_note")
    return tuple(keys)


def tui_metadata_section_field_ids(field_key: str) -> tuple[str, ...]:
    ids = (f"{field_key}_label", f"{field_key}_input")
    if field_key == "speaker":
        return ids + ("speaker_suggestions",)
    return ids


def tui_metadata_widget_order(service_type: ServiceTypeConfig) -> tuple[str, ...]:
    order: list[str] = [
        "metadata_basic_heading",
        "service_type_label",
        "service_type",
        "service_type_help",
        "date_label",
        "date_choice",
        "sermon_date",
        "metadata_required_heading",
    ]
    for field_key in tui_metadata_required_field_keys(service_type):
        order.extend(tui_metadata_section_field_ids(field_key))
    order.append("metadata_optional_heading")
    for field_key in tui_metadata_optional_field_keys(service_type):
        order.extend(tui_metadata_section_field_ids(field_key))
    return tuple(order)


def build_tui_app(
    config_path: str | None = None,
    *,
    vimeo_service_factory: Callable[[AppConfig], VimeoPublishingService] | None = None,
    credential_manager: VimeoCredentialManager | None = None,
    speaker_store: SpeakerHistory | None = None,
):
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical, VerticalScroll
        from textual.dom import NoScreen
        from textual.screen import ModalScreen, Screen
        from textual.widgets import Button, DataTable, Footer, Header, Input, Label, OptionList, ProgressBar, Select, Static
    except ImportError as exc:
        raise ImportError("Textual ist nicht installiert.") from exc

    config = load_tui_config(config_path)
    credentials = credential_manager or VimeoCredentialManager()
    speakers = speaker_store or SpeakerHistory.for_current_user()
    make_vimeo_service = vimeo_service_factory or (
        lambda app_config: create_tui_vimeo_service(app_config, credentials)
    )

    class MetadataFormScroll(VerticalScroll):
        def watch_scroll_y(self, old_value: float, new_value: float) -> None:
            super().watch_scroll_y(old_value, new_value)
            if round(old_value) == round(new_value) or not self.is_mounted:
                return
            try:
                screen = self.screen
            except NoScreen:
                return
            update_hint = getattr(screen, "_update_metadata_scroll_hint", None)
            if update_hint is not None:
                self.call_after_refresh(update_hint)

    class StartScreen(Screen[None]):
        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("PredigtUploader", id="title")
            with Horizontal():
                with Vertical(id="start_actions"):
                    yield Button("Neue Aufnahme vorbereiten", id="new", variant="primary")
                    yield Button("Vimeo-Bibliothek", id="vimeo_library")
                    yield Button("Direkt zu Vimeo hochladen (Admin / Sonderfall)", id="direct_vimeo")
                    yield Static(
                        "Nur für bereits fertig geschnittene, korrekt benannte MP4-Dateien am endgültigen Speicherort. "
                        "Normalerweise 'Neue Aufnahme vorbereiten' verwenden.",
                        id="direct_vimeo_note",
                    )
                    yield Button("MP4-Dateien ansehen", id="files")
                    yield Button("Einstellungen", id="settings")
                    yield Button("Systemcheck-Hinweis", id="systemcheck")
                    yield Button("Beenden", id="quit")
                with Vertical(id="status_box"):
                    yield Static(build_tui_start_status_text(config), id="start_status", classes="panel-info")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "new":
                self.app.push_screen(StartSafetyScreen(self.app.app_config))
            elif event.button.id == "vimeo_library":
                self.app.push_screen(VimeoLibraryScreen(self.app.app_config))
            elif event.button.id == "direct_vimeo":
                self.app.push_screen(DirectVimeoSelectionScreen(self.app.app_config))
            elif event.button.id == "files":
                self.app.push_screen(FileCandidatesScreen(self.app.app_config))
            elif event.button.id == "settings":
                self.app.push_screen(SettingsScreen(self.app.app_config))
            elif event.button.id == "systemcheck":
                self.notify("Bitte PredigtUploader Systemcheck.cmd ausführen.")
            elif event.button.id == "quit":
                self.app.exit()

        def on_screen_resume(self) -> None:
            self.query_one("#start_status", Static).update(build_tui_start_status_text(self.app.app_config))

    class StartSafetyScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            with Vertical(id="safety_page"):
                yield Static(build_tui_step_title(1, "Startcheck"), id="screen_title")
                yield Static(build_tui_progress_text(1), classes="workflow_progress")
                yield Static(TUI_START_SAFETY_TITLE, id="safety_title")
                yield Static("\n".join(TUI_START_SAFETY_QUESTIONS), id="safety_questions")
                yield Static(TUI_START_SAFETY_WARNING, id="safety_warning", classes="status-warning")
                with Horizontal(id="safety_actions"):
                    yield Button(TUI_BACK_LABEL, id="back")
                    yield Button(TUI_START_SAFETY_CANCEL_LABEL, id="cancel")
                    yield Button(TUI_START_SAFETY_CONFIRM_LABEL, id="confirm", variant="primary")
            yield Footer()

        def on_mount(self) -> None:
            self.query_one("#back", Button).focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()
                return
            route = tui_start_safety_route(event.button.id)
            if route == "source":
                self.app.push_screen(SourceChoiceScreen(self.app_config))
            else:
                self.app.pop_screen()

    class SourceChoiceScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static(build_tui_step_title(2, "Aufnahmequelle auswaehlen"), id="screen_title")
            yield Static(build_tui_progress_text(2), classes="workflow_progress")
            yield Static(
                build_tui_screen_help("Standard: Rohaufnahme auswaehlen und danach in LosslessCut schneiden.", ""),
                id="screen_note",
            )
            yield Button("Rohaufnahme auswaehlen", id="raw", variant="primary")
            yield Static("Sonderfall: Die MP4 ist bereits fertig geschnitten.", id="cut_special_case")
            yield Button("Fertig geschnittene MP4 auswaehlen", id="cut")
            yield Button(TUI_BACK_LABEL, id="back")
            yield Footer()

        def on_mount(self) -> None:
            self.query_one("#raw", Button).focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            route = tui_source_choice_route(event.button.id)
            if route == "cut-selection":
                self.app.push_screen(FileSelectionScreen(self.app_config, already_cut=True))
            elif route == "raw-selection":
                self.app.push_screen(FileSelectionScreen(self.app_config, already_cut=False))
            elif event.button.id == "back" or route == "start":
                self.app.pop_screen()

    class FileSelectionScreen(Screen[None]):
        def __init__(
            self,
            app_config: AppConfig,
            *,
            already_cut: bool,
            raw_recording: Path | None = None,
        ) -> None:
            super().__init__()
            self.app_config = app_config
            self.already_cut = already_cut
            self.raw_recording = raw_recording
            mode = "cut" if already_cut else "raw"
            self.selection = build_tui_mp4_selection_config(app_config, mode=mode, raw_recording=raw_recording)
            self.current_folder = self.selection.start_folder
            self._visible_candidates: tuple[Path, ...] = ()

        @property
        def source_folder(self) -> Path:
            return self.current_folder

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            step = 4 if self.already_cut else 2
            step_name = "Geschnittene MP4 bestaetigen" if self.already_cut else "Rohaufnahme auswaehlen"
            instruction = self.selection.note
            if self.already_cut and self.raw_recording is None:
                instruction += " Der Schnittschritt 3 wird uebersprungen, weil die MP4 bereits fertig geschnitten ist."
            yield Static(build_tui_step_title(step, step_name), id="screen_title")
            skipped_steps = {3} if self.already_cut and self.raw_recording is None else set()
            yield Static(build_tui_progress_text(step, skipped_steps), classes="workflow_progress")
            yield Static(
                build_tui_screen_help(
                    instruction,
                    "Die ausgewaehlte Datei wird fuer den naechsten Schritt uebernommen; es werden noch keine Zieldateien geschrieben.",
                ),
                id="screen_note",
            )
            with VerticalScroll(id="file_selection_scroll"):
                yield Static(f"Ordner: {self.source_folder}", id="source_folder")
                if self.selection.allow_search:
                    yield Input(placeholder="Dateiname suchen oder filtern", id="file_search")
                yield Static("Neueste MP4-Dateien", id="file_table_heading")
                yield DataTable(id="file_table")
                if self.selection.allow_manual_input:
                    yield Input(placeholder="Datei oder Ordner manuell eingeben", id="manual_path")
                    yield Button("Manuellen Pfad verwenden", id="manual")
            with Horizontal(id="file_actions"):
                yield Button(TUI_BACK_LABEL, id="back")
                yield Button("Abbrechen", id="cancel")
                if self.selection.suggest_newest:
                    newest_label = "Neueste geschnittene MP4 verwenden" if self.already_cut else "Neueste Aufnahme verwenden"
                    yield Button(newest_label, id="newest")
                selected_label = (
                    "Ausgewaehlte geschnittene MP4 verwenden"
                    if self.already_cut
                    else "Ausgewaehlte Rohaufnahme verwenden"
                )
                yield Button(selected_label, id="select", variant="primary")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one("#file_table", DataTable)
            table.cursor_type = "row"
            table.zebra_stripes = True
            table.add_columns("Dateiname", "Geaendert", "Groesse")
            self._update_file_table()
            table.focus()

        def on_input_changed(self, _event: Input.Changed) -> None:
            self._update_file_table()

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            self._choose_file_by_row_key(event.row_key.value)

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()
                return
            if event.button.id == "cancel":
                self.app.pop_screen()
                self.app.pop_screen()
                return
            if event.button.id == "newest":
                selected = newest_tui_mp4_candidate(self.source_folder)
                if selected is None:
                    self.notify("Keine MP4-Datei im aktuellen Ordner gefunden.")
                    return
                self._open_metadata(selected)
                return
            if event.button.id == "select":
                table = self.query_one("#file_table", DataTable)
                if not self._visible_candidates or table.cursor_row >= len(self._visible_candidates):
                    self.notify("Bitte zuerst eine MP4-Datei in der Liste auswaehlen.")
                    return
                self._open_metadata(self._visible_candidates[table.cursor_row])
                return
            if event.button.id == "manual":
                self._use_manual_path()

        def _candidates(self) -> tuple[Path, ...]:
            return newest_tui_mp4_candidates(
                self.source_folder,
                search_text=self._search_text(),
                limit=TUI_FILE_CHOICE_LIMIT,
            )

        def _search_text(self) -> str:
            if not self.selection.allow_search:
                return ""
            return self.query_one("#file_search", Input).value

        def _update_file_table(self) -> None:
            table = self.query_one("#file_table", DataTable)
            rows = build_tui_mp4_file_rows(self.source_folder, search_text=self._search_text(), limit=TUI_FILE_CHOICE_LIMIT)
            self._visible_candidates = tuple(row.path for row in rows)
            table.clear()
            for index, row in enumerate(rows):
                table.add_row(row.filename, row.modified, row.size, key=str(index))
            self.query_one("#source_folder", Static).update(f"Ordner: {self.source_folder}")

        def _choose_file_by_row_key(self, row_key: object) -> None:
            try:
                index = int(str(row_key))
            except ValueError:
                return
            if index < len(self._visible_candidates):
                self._open_metadata(self._visible_candidates[index])

        def _use_manual_path(self) -> None:
            path_text = self.query_one("#manual_path", Input).value.strip()
            if not path_text:
                self.notify("Bitte eine MP4-Datei oder einen Ordner eingeben.")
                return
            path = Path(path_text).expanduser()
            if path.is_file() and path.suffix.casefold() == ".mp4":
                self._open_metadata(path)
                return
            if path.is_dir():
                self.current_folder = path
                self._update_file_table()
                self.notify("Ordner wurde fuer diese Auswahl uebernommen.")
                return
            self.notify("Der eingegebene Pfad ist keine MP4-Datei und kein vorhandener Ordner.")

        def _open_metadata(self, selected: Path) -> None:
            if tui_file_selection_next_screen(already_cut=self.already_cut) == "losslesscut":
                self.app.push_screen(LosslessCutScreen(self.app_config, raw_recording=selected))
                return
            self.app.push_screen(
                MetadataPreviewScreen(
                    self.app_config,
                    source_mp4=selected,
                    raw_recording=self.raw_recording,
                    already_cut=self.already_cut and self.raw_recording is None,
                )
            )

    class LosslessCutScreen(Screen[None]):
        def __init__(self, app_config: AppConfig, *, raw_recording: Path) -> None:
            super().__init__()
            self.app_config = app_config
            self.raw_recording = raw_recording
            self.losslesscut_process: subprocess.Popen[bytes] | None = None
            self.export_detection_started_at = datetime.now()
            self.export_candidate_folders = tui_export_candidate_folders(app_config, raw_recording)
            self.before_export_snapshot = snapshot_tui_mp4_files(self.export_candidate_folders)

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static(build_tui_step_title(3, "Rohaufnahme schneiden"), id="screen_title")
            yield Static(build_tui_progress_text(3), classes="workflow_progress")
            yield Static(
                build_tui_screen_help(
                    "Oeffne die Rohaufnahme in LosslessCut, schneide die Predigt und exportiere sie als MP4.",
                    "Der PredigtUploader sucht anschliessend nach der exportierten MP4; der Vorschlag muss bestaetigt werden.",
                ),
                id="screen_note",
            )
            yield Static(build_tui_losslesscut_text(self.raw_recording, self.app_config), id="losslesscut_note")
            with Horizontal(id="losslesscut_actions"):
                yield Button(TUI_BACK_LABEL, id="back")
                yield Button("Abbrechen", id="cancel")
                yield Button("LosslessCut oeffnen", id="open")
                yield Button("Exportierte MP4 suchen", id="next", variant="primary")
            yield Static("", id="losslesscut_status")
            yield Footer()

        def on_mount(self) -> None:
            if not self.app_config.losslesscut_path.strip():
                self.query_one("#losslesscut_status", Static).update(
                    "LosslessCut wurde nicht gefunden. Du kannst den Schnitt manuell durchfuehren und danach die geschnittene MP4 auswaehlen."
                )

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "open":
                self._open_losslesscut()
                return
            if event.button.id == "next":
                after_snapshot = snapshot_tui_mp4_files(self.export_candidate_folders)
                candidates = detect_tui_export_candidates(
                    self.before_export_snapshot,
                    after_snapshot,
                    raw_recording=self.raw_recording,
                    started_at=self.export_detection_started_at,
                    preferred_folders=self.export_candidate_folders,
                )
                self.app.push_screen(
                    CutMp4DetectionScreen(
                        self.app_config,
                        raw_recording=self.raw_recording,
                        candidates=candidates,
                    )
                )
                return
            if event.button.id == "back":
                self.app.pop_screen()
                return
            if event.button.id == "cancel":
                self._return_to_start()

        def _open_losslesscut(self) -> None:
            status = self.query_one("#losslesscut_status", Static)
            try:
                self.losslesscut_process = open_tui_losslesscut(self.raw_recording, self.app_config)
            except OSError as exc:
                status.update(
                    "LosslessCut wurde nicht gefunden. Bitte Pfad in den Einstellungen setzen oder Schnitt manuell durchfuehren.\n"
                    f"Admin-Hinweis: {exc}"
                )
                self.notify("LosslessCut konnte nicht gestartet werden.", severity="error")
                return
            status.update("LosslessCut wurde gestartet. Schneide und exportiere dort die Predigt als MP4.")
            self.notify("LosslessCut wurde gestartet.")

        def _return_to_start(self) -> None:
            for _ in range(3):
                try:
                    self.app.pop_screen()
                except Exception:
                    return

    class CutMp4DetectionScreen(Screen[None]):
        def __init__(
            self,
            app_config: AppConfig,
            *,
            raw_recording: Path,
            candidates: tuple[TuiExportCandidate, ...],
        ) -> None:
            super().__init__()
            self.app_config = app_config
            self.raw_recording = raw_recording
            self.candidates = candidates

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static(build_tui_step_title(4, "Geschnittene MP4 bestaetigen"), id="screen_title")
            yield Static(build_tui_progress_text(4), classes="workflow_progress")
            title = "Vermutlich exportierte Schnittdatei gefunden" if self.candidates else "Exportierte MP4 manuell auswaehlen"
            yield Static(title, id="export_detection_heading")
            yield Static(
                build_tui_screen_help(
                    build_tui_export_detection_text(self.candidates),
                    "Die bestaetigte Schnittdatei wird als Quelle fuer Metadaten und finale MP4/MP3 verwendet.",
                ),
                id="screen_note",
            )
            if self.candidates:
                yield DataTable(id="export_candidate_table")
            with Horizontal(id="export_detection_actions"):
                yield Button(TUI_BACK_LABEL, id="back")
                yield Button("Abbrechen", id="cancel")
                if self.candidates:
                    action_label = "Exportierte MP4 bestaetigen"
                    yield Button("Andere MP4 auswaehlen", id="manual")
                    yield Button(action_label, id="use", variant="primary")
                else:
                    yield Button("MP4 manuell auswaehlen", id="manual", variant="primary")
            yield Footer()

        def on_mount(self) -> None:
            if not self.candidates:
                return
            table = self.query_one("#export_candidate_table", DataTable)
            table.cursor_type = "row"
            table.zebra_stripes = True
            table.add_columns("Dateiname", "Geaendert", "Groesse", "Grund")
            for index, candidate in enumerate(self.candidates):
                table.add_row(candidate.path.name, candidate.modified, candidate.size, candidate.reason, key=str(index))
            table.focus()

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            self._use_candidate_key(event.row_key.value)

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "use":
                table = self.query_one("#export_candidate_table", DataTable)
                index = min(table.cursor_row, len(self.candidates) - 1)
                self._open_metadata(self.candidates[index].path)
                return
            if event.button.id == "manual":
                self.app.push_screen(FileSelectionScreen(self.app_config, already_cut=True, raw_recording=self.raw_recording))
                return
            if event.button.id == "back":
                self.app.pop_screen()
                return
            if event.button.id == "cancel":
                self._return_to_start()

        def _use_candidate_key(self, row_key: object) -> None:
            try:
                index = int(str(row_key))
            except ValueError:
                return
            if index < len(self.candidates):
                self._open_metadata(self.candidates[index].path)

        def _open_metadata(self, source_mp4: Path) -> None:
            self.app.push_screen(
                MetadataPreviewScreen(
                    self.app_config,
                    source_mp4=source_mp4,
                    raw_recording=self.raw_recording,
                    already_cut=False,
                )
            )

        def _return_to_start(self) -> None:
            for _ in range(4):
                try:
                    self.app.pop_screen()
                except Exception:
                    return

    class MetadataPreviewScreen(Screen[None]):
        def __init__(
            self,
            app_config: AppConfig,
            *,
            source_mp4: Path | None = None,
            raw_recording: Path | None = None,
            already_cut: bool = True,
        ) -> None:
            super().__init__()
            self.app_config = app_config
            self.source_mp4 = source_mp4
            self.raw_recording = raw_recording
            self.already_cut = already_cut
            self.service_type_manually_changed = False
            self._syncing_service_type = False

        def compose(self) -> ComposeResult:
            today = date.today()
            date_options = build_tui_date_options_for_sources(self.source_mp4, self.raw_recording, today)
            preferred_date = preferred_tui_date_option(date_options)
            service_names = list(tui_service_type_options(self.app_config))
            default_service = default_tui_service_type_name(self.app_config, preferred_date.value)
            yield Static(build_tui_step_title(5, "Metadaten erfassen"), id="screen_title")
            skipped_steps = {3} if self.already_cut and self.raw_recording is None else set()
            yield Static(build_tui_progress_text(5, skipped_steps), classes="workflow_progress")
            yield Static(
                build_tui_screen_help("Ergaenze die Angaben fuer Dateiname, MP3 und Zusammenfassung.", ""),
                id="screen_note",
            )
            yield Static("", id="metadata_validation", classes="status-info")
            with Vertical(id="metadata_content"):
                with Horizontal(id="metadata_body"):
                    with Vertical(id="metadata_form_pane"):
                        with MetadataFormScroll(id="metadata_form_scroll", classes="panel-neutral"):
                            with Vertical(id="metadata_field_stack"):
                                yield Static("Grunddaten", id="metadata_basic_heading", classes="metadata_section_heading")
                                yield Label("Art der Veranstaltung", id="service_type_label")
                                yield Select(service_names, value=default_service, id="service_type")
                                yield Static(TUI_GOTTESDIENST_EXPLANATION, id="service_type_help")
                                yield Label("Datum", id="date_label")
                                yield Select(
                                    [(option.label, option.kind) for option in date_options],
                                    value=preferred_date.kind,
                                    id="date_choice",
                                )
                                yield Input(value=preferred_date.value.isoformat(), placeholder="YYYY-MM-DD", id="sermon_date")
                                yield Static("Pflichtangaben", id="metadata_required_heading", classes="metadata_section_heading")
                                yield Label("Titel", id="title_label")
                                yield Input(placeholder="Titel oder Thema", id="title_input")
                                yield Label("Hauptbibelstelle", id="bible_label")
                                yield Input(placeholder="Bibelstelle", id="bible_input")
                                yield Label("Redner / Leitung", id="speaker_label")
                                yield Input(placeholder="Redner oder Leitung", id="speaker_input")
                                yield OptionList(id="speaker_suggestions")
                                yield Static("Optionale Angaben", id="metadata_optional_heading", classes="metadata_section_heading")
                                yield Label("Besonderheit im Ordner", id="folder_note_label")
                                yield Input(placeholder="optional, z. B. Taufe oder Gastredner", id="folder_note_input")
                        with Horizontal(id="metadata_scroll_hint_row"):
                            yield Static("", id="metadata_scroll_hint", classes="scroll-hint")
                    with VerticalScroll(id="metadata_preview_scroll", classes="panel-info"):
                        yield Label("Live-Vorschau", id="preview_heading")
                        yield Static("", id="filename_preview")
                        yield Static("", id="validation_status")
                        yield Static("", id="source_status")
                yield Static(build_tui_back_footnote(), classes="back_footnote")
                with Horizontal(id="metadata_actions"):
                    back_label, cancel_label, next_label = tui_metadata_action_labels()
                    yield Button(back_label, id="back")
                    yield Button(cancel_label, id="cancel")
                    yield Button(next_label, id="next", variant="primary")
            yield Footer()

        def on_mount(self) -> None:
            self.query_one("#speaker_suggestions", OptionList).display = False
            self._update_preview()

        def on_descendant_focus(self, event) -> None:
            for selector in ("#metadata_form_scroll", "#metadata_preview_scroll"):
                try:
                    scroll_container = self.query_one(selector, VerticalScroll)
                except Exception:
                    continue
                if not (
                    scroll_container.can_view_partial(event.widget)
                    or scroll_container.can_view_entire(event.widget)
                ):
                    scroll_container.scroll_to_widget(event.widget, top=False, immediate=True)
                    break
            self._update_metadata_scroll_hint()

        def on_input_changed(self, _event: Input.Changed) -> None:
            if _event.input.id == "sermon_date":
                self._sync_service_type_for_date()
            elif _event.input.id == "speaker_input":
                self._update_speaker_suggestions(_event.input.value)
            self._update_preview()

        def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
            if event.option_list.id != "speaker_suggestions":
                return
            suggestions = getattr(self, "_visible_speaker_suggestions", ())
            if event.option_index >= len(suggestions):
                return
            speaker_input = self.query_one("#speaker_input", Input)
            speaker_input.value = suggestions[event.option_index]
            event.option_list.display = False
            speaker_input.focus()

        def on_key(self, event) -> None:
            if event.key != "down" or self.app.focused is not self.query_one("#speaker_input", Input):
                return
            suggestions = self.query_one("#speaker_suggestions", OptionList)
            if suggestions.display and suggestions.option_count:
                suggestions.focus()
                event.prevent_default()

        def _update_speaker_suggestions(self, text: str) -> None:
            widget = self.query_one("#speaker_suggestions", OptionList)
            try:
                values = speakers.suggest(text) if text.strip() else ()
            except OSError:
                values = ()
            self._visible_speaker_suggestions = values
            widget.set_options(values)
            widget.display = bool(values)

        def on_select_changed(self, _event: Select.Changed) -> None:
            if _event.select.id == "service_type" and not self._syncing_service_type:
                self.service_type_manually_changed = True
            elif _event.select.id == "date_choice":
                self._sync_date_input_to_choice()
                self._sync_service_type_for_date()
            self._update_preview()

        def on_mouse_scroll_down(self, _event) -> None:
            self._update_metadata_scroll_hint()

        def on_mouse_scroll_up(self, _event) -> None:
            self._update_metadata_scroll_hint()

        def on_resize(self, _event) -> None:
            self._update_metadata_scroll_hint()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()
            elif event.button.id == "cancel":
                self._return_to_start()
            elif event.button.id == "next":
                messages = self._validation_messages()
                if messages:
                    self.notify("Bitte fehlende Pflichtfelder ergaenzen.")
                elif self.source_mp4 is None:
                    self.notify("Bitte zuerst eine MP4-Datei auswaehlen.")
                else:
                    self.app.push_screen(
                        TargetFolderReviewScreen(
                            self.app_config,
                            source_mp4=self.source_mp4,
                            raw_recording=self.raw_recording,
                            already_cut=self.already_cut,
                            info=self._current_info(),
                        )
                    )

        def _update_preview(self) -> None:
            preview_widget = self.query_one("#filename_preview", Static)
            validation_banner = self.query_one("#metadata_validation", Static)
            validation_widget = self.query_one("#validation_status", Static)
            source_widget = self.query_one("#source_status", Static)
            service_type = str(
                self.query_one("#service_type", Select).value
                or default_tui_service_type_for_sources(
                    self.app_config,
                    self.source_mp4,
                    self.raw_recording,
                )
            )
            service_config = service_type_by_name(self.app_config, service_type)
            self._update_metadata_widget_order(service_config)
            info = self._current_info()
            date_text = self._validation_date_text()
            messages = validate_tui_metadata(info, self.app_config, date_text=date_text)
            missing_fields = missing_tui_metadata_fields(info, self.app_config, date_text=date_text)
            self._update_field_state(service_config, missing_fields)
            preparation = build_tui_preparation(
                config=self.app_config,
                source_mp4=self.source_mp4,
                raw_recording=self.raw_recording,
                already_cut=self.already_cut,
                info=info,
            )
            preview_widget.update(build_tui_preparation_text(preparation))
            validation_widget.update(build_tui_validation_text(messages))
            validation_banner.update(build_tui_metadata_validation_text(messages))
            validation_banner.set_classes("status-ok" if not messages else "status-warning")
            source_widget.update(self._source_hint())
            self.query_one("#next", Button).disabled = bool(messages)
            self._update_metadata_scroll_hint(missing_fields)

        def _update_metadata_widget_order(self, service_type: ServiceTypeConfig) -> None:
            stack = self.query_one("#metadata_field_stack", Vertical)
            desired_order = tui_metadata_widget_order(service_type)
            previous_widget = None
            for widget_id in desired_order:
                widget = self.query_one(f"#{widget_id}")
                if previous_widget is None:
                    if stack.children and stack.children[0] is not widget:
                        stack.move_child(widget, before=stack.children[0])
                else:
                    stack.move_child(widget, after=previous_widget)
                previous_widget = widget

        def _update_metadata_scroll_hint(self, missing_fields: tuple[str, ...] | None = None) -> None:
            if missing_fields is None:
                date_text = self._validation_date_text()
                info = self._current_info()
                missing_fields = missing_tui_metadata_fields(info, self.app_config, date_text=date_text)
            missing_above, missing_below = self._metadata_missing_field_directions(missing_fields)
            hint_widget = self.query_one("#metadata_scroll_hint", Static)
            hint_text = build_tui_metadata_scroll_hint_text(missing_above, missing_below)
            hint_widget.update(hint_text)
            hint_widget.display = bool(hint_text)
            self.query_one("#metadata_scroll_hint_row", Horizontal).display = bool(hint_text)

        def _metadata_missing_field_directions(
            self, missing_fields: tuple[str, ...]
        ) -> tuple[tuple[str, ...], tuple[str, ...]]:
            field_widgets = {
                "date": "#sermon_date",
                "title": "#title_input",
                "bible": "#bible_input",
                "speaker": "#speaker_input",
                "folder_note": "#folder_note_input",
            }
            scroll_container = self.query_one("#metadata_form_scroll", VerticalScroll)
            field_regions: list[tuple[str, int, int]] = []
            for field_name in missing_fields:
                widget_id = field_widgets.get(field_name)
                if widget_id is None:
                    continue
                try:
                    widget = self.query_one(widget_id)
                except Exception:
                    continue
                field_regions.append((field_name, widget.region.y, widget.region.bottom))
            viewport = scroll_container.scrollable_content_region
            return classify_tui_metadata_fields_by_position(
                tuple(field_regions),
                viewport_top=viewport.y,
                viewport_bottom=viewport.bottom,
            )

        def _validation_messages(self, info: SermonInfo | None = None) -> tuple[str, ...]:
            date_text = self._validation_date_text()
            if info is None:
                info = self._current_info()
            return validate_tui_metadata(info, self.app_config, date_text=date_text)

        def _current_info(self) -> SermonInfo:
            service_type = str(
                self.query_one("#service_type", Select).value
                or default_tui_service_type_for_sources(
                    self.app_config,
                    self.source_mp4,
                    self.raw_recording,
                )
            )
            return build_tui_metadata_info(
                config=self.app_config,
                date_text=self._selected_date().isoformat(),
                service_type_name=service_type,
                title=self.query_one("#title_input", Input).value,
                bible_reference=self.query_one("#bible_input", Input).value,
                speaker=self.query_one("#speaker_input", Input).value,
                folder_note=self.query_one("#folder_note_input", Input).value,
            )

        def _selected_date(self) -> date:
            options = build_tui_date_options_for_sources(self.source_mp4, self.raw_recording)
            kind = str(self.query_one("#date_choice", Select).value or "today")
            return date_from_tui_option(kind, options, self.query_one("#sermon_date", Input).value)

        def _sync_date_input_to_choice(self) -> None:
            kind = str(self.query_one("#date_choice", Select).value or "today")
            if kind == "custom":
                return
            date_input = self.query_one("#sermon_date", Input)
            value = self._selected_date().isoformat()
            if date_input.value != value:
                date_input.value = value

        def _sync_service_type_for_date(self) -> None:
            if self.service_type_manually_changed:
                return
            service_select = self.query_one("#service_type", Select)
            next_service = default_tui_service_type_name(self.app_config, self._selected_date())
            if service_select.value == next_service:
                return
            self._syncing_service_type = True
            try:
                service_select.value = next_service
            finally:
                self._syncing_service_type = False

        def _validation_date_text(self) -> str:
            kind = str(self.query_one("#date_choice", Select).value or "today")
            if kind == "custom":
                return self.query_one("#sermon_date", Input).value
            return self._selected_date().isoformat()

        def _source_hint(self) -> str:
            if self.source_mp4 is None:
                return "Quelle: noch nicht ausgewaehlt"
            if self.already_cut:
                return f"Quelle: geschnittene MP4\n{self.source_mp4}"
            return "\n".join(
                [
                    f"Quell-MP4 / geschnittene MP4:\n{self.source_mp4}",
                    f"Rohaufnahme:\n{self.raw_recording or '-'}",
                ]
            )

        def _update_field_state(self, service_type: ServiceTypeConfig, missing_fields: tuple[str, ...]) -> None:
            labels = build_tui_field_labels(service_type, missing_fields=missing_fields)
            date_label = "Datum - FEHLT" if "date" in missing_fields else "Datum"
            self.query_one("#service_type_label", Label).update("Art der Veranstaltung")
            self.query_one("#date_label", Label).update(date_label)
            self.query_one("#title_label", Label).update(labels["title"])
            self.query_one("#bible_label", Label).update(labels["bible"])
            self.query_one("#speaker_label", Label).update(labels["speaker"])
            self.query_one("#title_input", Input).disabled = not service_type.requires_title and not service_type.optional_title
            self.query_one("#bible_input", Input).disabled = (
                not service_type.requires_bible_reference and not service_type.optional_bible_reference
            )
            self.query_one("#speaker_input", Input).disabled = (
                not service_type.requires_speaker and not service_type.optional_speaker
            )

        def _return_to_start(self) -> None:
            for _ in range(3):
                try:
                    self.app.pop_screen()
                except Exception:
                    return

    class TargetFolderReviewScreen(Screen[None]):
        def __init__(
            self,
            app_config: AppConfig,
            *,
            source_mp4: Path,
            raw_recording: Path | None,
            already_cut: bool,
            info: SermonInfo,
        ) -> None:
            super().__init__()
            self.app_config = app_config
            self.source_mp4 = source_mp4
            self.raw_recording = raw_recording
            self.already_cut = already_cut
            self.info = info
            self.resolution = resolve_folder(app_config, info)
            self.selected_existing_folder: Path | None = self.resolution.candidates[0] if self.resolution.candidates else None
            self.creating_with_note = False

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static(build_tui_step_title(6, "Zielordner pruefen"), id="screen_title")
            skipped_steps = {3} if self.already_cut and self.raw_recording is None else set()
            yield Static(build_tui_progress_text(6, skipped_steps), classes="workflow_progress")
            yield Static(
                build_tui_screen_help("Waehle den Zielordner fuer diese Aufnahme.", ""),
                id="screen_note",
            )
            with VerticalScroll(id="target_folder_scroll"):
                with Horizontal(id="target_folder_body"):
                    with Vertical(id="processing_plan_box", classes="panel-neutral"):
                        yield Label("Plan / Auswahl")
                        yield Static(build_tui_target_folder_review_text(self.resolution), id="target_folder_review_text")
                        if self.resolution.status == "multiple_existing":
                            yield DataTable(id="target_folder_table")
                        if self.resolution.status != "missing":
                            yield Button("Neuen Ordner mit Zusatz erstellen", id="create_with_note")
                            yield Label("Zusatz fuer neuen Ordner", id="folder_note_label")
                            yield Input(value=self.info.folder_note, placeholder="z. B. Taufe oder Gastredner", id="folder_note_override")
                    with Vertical(id="processing_status_box", classes="panel-info"):
                        yield Label("Status / Entscheidung", id="processing_status_heading")
                        yield Static(
                            tui_target_folder_status_message(self.resolution),
                            id="target_folder_status_banner",
                            classes=tui_target_folder_status_class(self.resolution),
                        )
                        yield Static(self._action_hint(), id="target_folder_action_hint")
            yield Static(build_tui_back_footnote(), classes="back_footnote")
            with Vertical(id="target_folder_actions"):
                primary_label, primary_id = tui_target_folder_primary_action(self.resolution)
                yield Button(primary_label, id="target_folder_primary", variant="primary")
                with Horizontal(classes="navigation_actions"):
                    yield Button(f"{TUI_BACK_LABEL} zu Metadaten", id="back")
                    yield Button("Abbrechen", id="cancel")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one("#target_folder_table", DataTable) if self.resolution.status == "multiple_existing" else None
            if table is not None:
                table.add_columns("Ordner")
                for candidate in self.resolution.candidates:
                    table.add_row(str(candidate), key=str(candidate))
                table.cursor_type = "row"
            if self.resolution.status != "missing":
                visible = tui_target_folder_note_input_visible(self.creating_with_note)
                self.query_one("#folder_note_label", Label).display = visible
                self.query_one("#folder_note_override", Input).display = visible
            self.query_one("#target_folder_primary", Button).focus()

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            self.selected_existing_folder = Path(str(event.row_key.value))
            self.query_one("#target_folder_action_hint", Static).update(
                build_tui_target_folder_action_hint(
                    self.resolution,
                    selected_folder=self.selected_existing_folder,
                )
            )

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()
                return
            if event.button.id == "cancel":
                self._return_to_start()
                return
            if event.button.id == "target_folder_primary":
                self._confirm_primary_decision()
                return
            if event.button.id == "create_with_note":
                if not self.creating_with_note:
                    self.creating_with_note = True
                    self.query_one("#folder_note_label", Label).display = True
                    note_input = self.query_one("#folder_note_override", Input)
                    note_input.display = True
                    note_input.focus()
                    event.button.label = "Doch vorhandenen Tagesordner verwenden"
                    self._refresh_folder_decision()
                    try:
                        self.call_after_refresh(self._scroll_to_folder_note)
                    except Exception:
                        pass
                    return
                self.creating_with_note = False
                self.query_one("#folder_note_label", Label).display = False
                self.query_one("#folder_note_override", Input).display = False
                event.button.label = "Neuen Ordner mit Zusatz erstellen"
                self._refresh_folder_decision()

        def on_input_changed(self, event: Input.Changed) -> None:
            if event.input.id == "folder_note_override" and self.creating_with_note:
                self._refresh_folder_decision()
                self.call_after_refresh(self._scroll_to_folder_note)

        def _confirm_primary_decision(self) -> None:
            if self.creating_with_note:
                note = self.query_one("#folder_note_override", Input).value.strip()
                if not note:
                    self.notify("Bitte eine Besonderheit fuer den neuen Ordner eingeben.")
                    return
                info = build_tui_info_with_folder_note(self.info, note)
                self._open_processing_review(suggest_folder(self.app_config, info), info)
                return
            if self.resolution.status == "missing":
                self._open_processing_review(self.resolution.suggested_folder, self.info)
                return
            folder = self.selected_existing_folder or (
                self.resolution.candidates[0] if self.resolution.candidates else None
            )
            if folder is None:
                self.notify("Bitte zuerst einen vorhandenen Ordner auswaehlen.")
                return
            self._open_processing_review(folder, self.info)

        def _scroll_to_folder_note(self) -> None:
            note_input = self.query_one("#folder_note_override", Input)
            self.query_one("#target_folder_scroll", VerticalScroll).scroll_to_widget(
                note_input,
                top=False,
                immediate=True,
            )

        def _refresh_folder_decision(self) -> None:
            primary = self.query_one("#target_folder_primary", Button)
            status = self.query_one("#target_folder_status_banner", Static)
            hint = self.query_one("#target_folder_action_hint", Static)
            if self.creating_with_note:
                note = self.query_one("#folder_note_override", Input).value
                primary.label = "Neuen Ordner mit Zusatz verwenden"
                primary.disabled = not note.strip()
                status.update(build_tui_new_folder_decision_text(self.app_config, self.info, note))
                status.set_classes(tui_new_folder_decision_status_class(self.app_config, self.info, note))
                hint.update(build_tui_target_folder_action_hint(self.resolution, create_with_note=True))
                return
            primary_label, _primary_id = tui_target_folder_primary_action(self.resolution)
            primary.label = primary_label
            primary.disabled = False
            status.update(tui_target_folder_status_message(self.resolution))
            status.set_classes(tui_target_folder_status_class(self.resolution))
            hint.update(self._action_hint())

        def _open_processing_review(self, target_folder: Path, info: SermonInfo) -> None:
            self.app.push_screen(
                ProcessingReviewScreen(
                    self.app_config,
                    build_tui_processing_plan(
                        config=self.app_config,
                        source_mp4=self.source_mp4,
                        raw_recording=self.raw_recording,
                        already_cut=self.already_cut,
                        info=info,
                        raw_action="keep" if self.raw_recording is not None else None,
                        target_folder_override=target_folder,
                    ),
                )
            )

        def _action_hint(self) -> str:
            if self.creating_with_note:
                note = self.query_one("#folder_note_override", Input).value.strip()
                if not note:
                    return build_tui_target_folder_action_hint(self.resolution, create_with_note=True) + "\nBitte zuerst einen Zusatz eingeben."
                return build_tui_target_folder_action_hint(self.resolution, create_with_note=True)
            return build_tui_target_folder_action_hint(
                self.resolution,
                selected_folder=self.selected_existing_folder,
            )

        def _return_to_start(self) -> None:
            for _ in range(4):
                try:
                    self.app.pop_screen()
                except Exception:
                    return

    class ProcessingReviewScreen(Screen[None]):
        def __init__(self, app_config: AppConfig, plan: PreparedRecordingPlan) -> None:
            super().__init__()
            self.app_config = app_config
            self.plan = plan
            self.overwrite_confirmed = plan.overwrite_existing_outputs
            self.editing_output_names = False

        def compose(self) -> ComposeResult:
            conflicts = detect_tui_target_conflicts(self.plan)
            yield Header(show_clock=False)
            yield Static(build_tui_step_title(7, "Lokale Dateien erstellen"), id="screen_title")
            skipped_steps = {3} if self.plan.raw_recording is None else set()
            yield Static(build_tui_progress_text(7, skipped_steps), classes="workflow_progress")
            yield Static(
                build_tui_screen_help("Pruefe den Plan. Erst der blaue Button erstellt oder ersetzt Dateien.", ""),
                id="screen_note",
            )
            suggestions = unique_output_name_suggestions(self.plan)
            with VerticalScroll(id="processing_review_scroll"):
                with Horizontal(id="processing_review_body"):
                    with Vertical(id="processing_plan_box", classes="panel-neutral"):
                        yield Label("Plan / Auswahl")
                        yield Static(build_tui_processing_source_text(self.plan), id="processing_source_text")
                        yield Static(build_tui_processing_files_text(self.plan), id="processing_files_text")
                        if self.plan.raw_recording is not None:
                            yield Label("Rohaufnahme-Aktion")
                            yield Select(
                                [
                                    ("Rohaufnahme in Zielordner verschieben", "move"),
                                    ("Rohaufnahme in Zielordner kopieren", "copy"),
                                    ("Rohaufnahme in vMixStorage liegen lassen (sicherer Standard)", "keep"),
                                ],
                                value=self.plan.raw_action,
                                id="raw_action",
                            )
                        yield Static(build_tui_processing_raw_action_text(self.plan), id="processing_raw_action_text")
                    with Vertical(id="processing_status_box", classes="panel-info"):
                        yield Label("Status / Entscheidung")
                        yield Static(
                            build_tui_processing_warning_text(self.plan, conflicts),
                            id="processing_warning_text",
                            classes=tui_processing_warning_class(conflicts),
                        )
                        yield Static(build_tui_processing_review_action_text(self.plan), id="processing_action_text")
                        yield Static(
                            build_tui_target_file_plan_text(self.plan, conflicts),
                            id="processing_file_state_text",
                        )
                        if conflicts:
                            with Vertical(id="output_rename_fields"):
                                yield Label("Neuer MP4-Dateiname")
                                yield Input(value=suggestions["mp4"], id="new_mp4_name")
                                yield Label("Neuer MP3-Dateiname")
                                yield Input(value=suggestions["mp3"], id="new_mp3_name")
                                yield Label("Neuer Name der Zusammenfassung")
                                yield Input(value=suggestions["summary"], id="new_summary_name")
                            yield Button("Neue Dateien umbenennen", id="use_output_suffix", variant="primary")
                            yield Button("Vorhandene Dateien umbenennen und neue Dateien erstellen", id="backup_existing")
                            yield Button("Vorhandene Dateien ersetzen", id="confirm_overwrite", variant="error")
                        yield Static("Noch nicht gestartet.", id="processing_status")
            yield Static(build_tui_back_footnote(), classes="back_footnote")
            with Vertical(id="processing_actions"):
                yield Button(TUI_PROCESSING_EXECUTE_LABEL, id="execute", variant="primary")
                with Horizontal(classes="navigation_actions"):
                    back_label = "Zurueck und anderen Ordner waehlen" if conflicts else TUI_BACK_LABEL
                    yield Button(back_label, id="back")
                    yield Button("Zielordner oeffnen", id="open_target", disabled=True)
                    yield Button("Abbrechen", id="cancel")
            yield Footer()

        def on_mount(self) -> None:
            if detect_tui_target_conflicts(self.plan):
                self.query_one("#output_rename_fields", Vertical).display = False
            self._sync_execute_button()

        def on_input_changed(self, event: Input.Changed) -> None:
            if event.input.id in {"new_mp4_name", "new_mp3_name", "new_summary_name"} and self.editing_output_names:
                self._update_output_name_preview()

        def on_select_changed(self, event: Select.Changed) -> None:
            if event.select.id == "raw_action":
                self.plan = replace(self.plan, raw_action=str(event.value))
                self.query_one("#processing_raw_action_text", Static).update(
                    build_tui_processing_raw_action_text(self.plan)
                )
                self.query_one("#processing_action_text", Static).update(build_tui_processing_review_action_text(self.plan))
            self._sync_execute_button()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()
                return
            if event.button.id == "cancel":
                self._return_to_start()
                return
            if event.button.id == "confirm_overwrite":
                self.overwrite_confirmed = True
                self.plan = apply_tui_overwrite_confirmation(self.plan)
                self._refresh_plan_widgets()
                warning = self.query_one("#processing_warning_text", Static)
                warning.update(build_tui_overwrite_confirmed_text())
                warning.set_classes("status-warning")
                self.query_one("#processing_status", Static).update("Bereit zum Ersetzen.")
                self._hide_conflict_strategy_buttons()
                self._sync_execute_button()
                return
            if event.button.id == "use_output_suffix":
                if not self.editing_output_names:
                    self.editing_output_names = True
                    self.query_one("#output_rename_fields", Vertical).display = True
                    event.button.label = "Neue Dateinamen verwenden"
                    self._update_output_name_preview()
                    self.call_after_refresh(self._focus_and_scroll_to_output_names)
                    return
                try:
                    self.plan = self._candidate_output_name_plan()
                except (ValueError, FileExistsError) as exc:
                    self.notify(str(exc), severity="error")
                    return
                self._refresh_plan_widgets()
                warning = self.query_one("#processing_warning_text", Static)
                warning.update("Status / Warnungen\nNeue eindeutige Dateinamen werden verwendet. Vorhandene Dateien bleiben unveraendert.")
                warning.set_classes("status-ok")
                self.query_one("#processing_status", Static).update("Bereit mit neuen Dateinamen.")
                self._hide_conflict_strategy_buttons()
                self._sync_execute_button()
                return
            if event.button.id == "backup_existing":
                self.plan = apply_tui_backup_existing_confirmation(self.plan)
                self._refresh_plan_widgets()
                warning = self.query_one("#processing_warning_text", Static)
                warning.update(
                    "Status / Warnungen\nUmbenennen bestaetigt.\n" + build_tui_existing_output_rename_text(self.plan)
                )
                warning.set_classes("status-warning")
                self.query_one("#processing_status", Static).update("Bereit zum Sichern und Erstellen.")
                self._hide_conflict_strategy_buttons()
                self._sync_execute_button()
                return
            if event.button.id == "execute":
                if (
                    detect_tui_target_conflicts(self.plan)
                    and not self.overwrite_confirmed
                    and not self.plan.backup_existing_outputs
                ):
                    self.notify("Bitte zuerst bewusst entscheiden, ob vorhandene Dateien ersetzt werden sollen.")
                    return
                if self.overwrite_confirmed:
                    self.plan = apply_tui_overwrite_confirmation(self.plan)
                event.button.disabled = True
                event.button.label = TUI_PROCESSING_RUNNING_LABEL
                self._set_processing_controls_disabled(True)
                self.query_one("#processing_status", Static).update(build_tui_processing_started_status())
                self.set_timer(0.1, self._execute_plan)
                return
            if event.button.id == "open_target":
                self._open_target_folder_again()
                return

        def _sync_execute_button(self) -> None:
            button = self.query_one("#execute", Button)
            label, disabled = build_tui_execute_button_state(
                self.plan,
                overwrite_confirmed=self.overwrite_confirmed,
            )
            button.disabled = disabled
            button.label = label

        def _refresh_plan_widgets(self) -> None:
            self.query_one("#processing_source_text", Static).update(build_tui_processing_source_text(self.plan))
            self.query_one("#processing_files_text", Static).update(build_tui_processing_files_text(self.plan))
            self.query_one("#processing_raw_action_text", Static).update(build_tui_processing_raw_action_text(self.plan))
            self.query_one("#processing_action_text", Static).update(build_tui_processing_review_action_text(self.plan))
            self.query_one("#processing_file_state_text", Static).update(
                build_tui_target_file_plan_text(self.plan, detect_tui_target_conflicts(self.plan))
            )

        def _candidate_output_name_plan(self) -> PreparedRecordingPlan:
            return apply_output_filenames(
                self.plan,
                mp4_filename=self.query_one("#new_mp4_name", Input).value,
                mp3_filename=self.query_one("#new_mp3_name", Input).value,
                summary_filename=self.query_one("#new_summary_name", Input).value,
            )

        def _update_output_name_preview(self) -> None:
            button = self.query_one("#use_output_suffix", Button)
            status = self.query_one("#processing_status", Static)
            proposed_names = {
                "mp4": self.query_one("#new_mp4_name", Input).value,
                "mp3": self.query_one("#new_mp3_name", Input).value,
                "summary": self.query_one("#new_summary_name", Input).value,
            }
            self.query_one("#processing_file_state_text", Static).update(
                build_tui_target_file_plan_text(
                    self.plan,
                    detect_tui_target_conflicts(self.plan),
                    proposed_names=proposed_names,
                )
            )
            try:
                self._candidate_output_name_plan()
            except (ValueError, FileExistsError) as exc:
                button.disabled = True
                status.update(f"Dateinamen noch nicht verwendbar: {exc}")
            else:
                button.disabled = False
                status.update("Die vorgeschlagenen Dateinamen sind frei und koennen verwendet werden.")

        def _focus_and_scroll_to_output_names(self) -> None:
            target = self.query_one("#new_mp4_name", Input)
            target.focus(scroll_visible=False)
            target.scroll_visible(
                animate=True,
                top=False,
                force=True,
            )

        def _hide_conflict_strategy_buttons(self) -> None:
            for selector in ("#use_output_suffix", "#backup_existing", "#confirm_overwrite"):
                try:
                    self.query_one(selector, Button).display = False
                except Exception:
                    continue
            for selector in ("#output_rename_fields",):
                try:
                    self.query_one(selector).display = False
                except Exception:
                    continue

        def _execute_plan(self) -> None:
            status_widget = self.query_one("#processing_status", Static)
            status_lines: list[str] = [build_tui_processing_started_status()]

            def append_status(message: str) -> None:
                status_lines.append(message)
                status_widget.update("\n".join(status_lines))

            try:
                result = execute_processing_plan(self.plan, self.app_config, progress=append_status)
            except Exception as exc:
                self._set_processing_controls_disabled(False)
                self.query_one("#execute", Button).disabled = False
                self.query_one("#execute", Button).label = TUI_PROCESSING_EXECUTE_LABEL
                self._enable_open_target_if_available()
                status_widget.update(
                    build_tui_processing_error_status(
                        tuple(status_lines),
                        f"{type(exc).__name__}: {exc}",
                        target_folder=self.plan.target_folder,
                    )
                )
                self.notify("Die Vorbereitung ist mit einem Fehler abgebrochen.", severity="error")
                return

            if result.success:
                if self.plan.info.speaker.strip():
                    try:
                        speakers.add(self.plan.info.speaker)
                    except OSError as exc:
                        self.notify(f"Prediger-Historie konnte nicht gespeichert werden: {exc}", severity="warning")
                self.app.open_vimeo_publishing(
                    self.plan,
                    state_path=result.workflow_state_path or recording_workflow_state_path(self.plan.target_mp4),
                    opened_target_folder=result.opened_target_folder,
                )
                self.notify("Dateien wurden vorbereitet.")
                return

            self.query_one("#execute", Button).disabled = False
            self.query_one("#execute", Button).label = TUI_PROCESSING_EXECUTE_LABEL
            self._set_processing_controls_disabled(False)
            self._enable_open_target_if_available()
            error = result.error or "Die Vorbereitung ist nicht vollstaendig abgeschlossen."
            status_widget.update(build_tui_processing_error_status(result.messages, error, target_folder=self.plan.target_folder))
            self.notify(error, severity="error")

        def _set_processing_controls_disabled(self, disabled: bool) -> None:
            for selector in ("#back", "#cancel", "#use_output_suffix", "#backup_existing", "#confirm_overwrite"):
                try:
                    self.query_one(selector, Button).disabled = disabled
                except Exception:
                    continue
            try:
                self.query_one("#raw_action", Select).disabled = disabled
            except Exception:
                pass

        def _enable_open_target_if_available(self) -> None:
            if self.plan.target_folder.exists():
                self.query_one("#open_target", Button).disabled = False

        def _open_target_folder_again(self) -> None:
            try:
                subprocess.Popen(["explorer", str(self.plan.target_folder)])
            except OSError as exc:
                self.query_one("#processing_status", Static).update(
                    f"Der Zielordner konnte nicht automatisch geoeffnet werden.\nPfad: {self.plan.target_folder}\nAdmin-Hinweis: {exc}"
                )

        def _return_to_start(self) -> None:
            for _ in range(4):
                try:
                    self.app.pop_screen()
                except Exception:
                    return

    class VimeoStopConfirmationScreen(ModalScreen[bool]):
        def compose(self) -> ComposeResult:
            with Vertical(id="vimeo_stop_dialog"):
                yield Static("Vimeo-Upload wirklich stoppen?", id="vimeo_stop_title")
                yield Static(
                    "Die lokale MP4 bleibt unverändert.\n"
                    "Bereits von Vimeo bestätigte Daten bleiben für einen späteren Resume erhalten.\n"
                    "Das Vimeo-Video wird nicht gelöscht.",
                    id="vimeo_stop_text",
                    classes="panel-info",
                )
                with Horizontal(id="vimeo_stop_dialog_actions"):
                    yield Button("Weiter hochladen", id="vimeo_stop_continue", variant="primary")
                    yield Button("Upload stoppen", id="vimeo_stop_confirm", variant="error")

        def on_mount(self) -> None:
            self.query_one("#vimeo_stop_continue", Button).focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            self.dismiss(event.button.id == "vimeo_stop_confirm")

    class VimeoPublishingScreen(Screen[None]):
        def __init__(
            self,
            app_config: AppConfig,
            plan: PreparedRecordingPlan,
            *,
            state_path: Path,
            opened_target_folder: bool,
            direct_mode: bool = False,
        ) -> None:
            super().__init__()
            self.app_config = app_config
            self.plan = plan
            self.state_path = state_path
            self.opened_target_folder = opened_target_folder
            self.direct_mode = direct_mode
            self.vimeo_state = self._load_vimeo_state()
            self.running = False
            self.last_progress: VimeoProgress | None = None
            self.cancel_event = threading.Event()
            self._link_announced = bool(self.vimeo_state and self.vimeo_state.video_url)
            self._embed_announced = bool(self.vimeo_state and self.vimeo_state.embed_html)

        def compose(self) -> ComposeResult:
            complete = bool(
                self.vimeo_state
                and self.vimeo_state.step.status == "complete"
                and self.vimeo_state.video_id
            )
            yield Header(show_clock=False)
            yield Static(build_tui_step_title(8, "Vimeo veröffentlichen"), id="screen_title")
            skipped_steps = {3} if self.plan.raw_recording is None else set()
            yield Static(build_tui_progress_text(8, skipped_steps), classes="workflow_progress")
            yield Static(
                "Die lokalen Dateien sind sicher fertig. Ein Vimeo-Upload startet erst nach Klick auf den blauen Button.",
                id="vimeo_local_safe",
                classes="status-ok",
            )
            with VerticalScroll(id="vimeo_scroll"):
                with Horizontal(id="vimeo_body"):
                    with Vertical(id="vimeo_plan_box", classes="panel-neutral"):
                        yield Label("Plan / Auswahl")
                        yield Static(build_tui_vimeo_plan_text(self.plan, self.app_config), id="vimeo_plan_text")
                    with Vertical(id="vimeo_status_box", classes="panel-info"):
                        yield Label("Status / Entscheidung", id="vimeo_status_heading")
                        yield Static(
                            build_tui_vimeo_initial_status(self.vimeo_state),
                            id="vimeo_status_banner",
                            classes="status-ok" if complete else "status-info",
                        )
                        yield Static(
                            build_tui_vimeo_progress_text(
                                "complete" if complete else None,
                                transcode_status=self.vimeo_state.transcode_status if self.vimeo_state else None,
                                video_url_available=bool(self.vimeo_state and self.vimeo_state.video_url),
                                embed_available=bool(self.vimeo_state and self.vimeo_state.embed_html),
                            ),
                            id="vimeo_progress",
                        )
                        yield Static(
                            build_tui_vimeo_available_actions_text(
                                self.vimeo_state,
                                running=False,
                            ),
                            id="vimeo_available_actions",
                            classes="status-ok",
                        )
                        yield ProgressBar(
                            total=100,
                            show_eta=False,
                            id="vimeo_upload_bar",
                        )
                        yield Static("", id="vimeo_upload_details")
            with Vertical(id="vimeo_actions"):
                yield Button(
                    "Video jetzt auf Vimeo hochladen",
                    id="vimeo_upload",
                    variant="primary",
                    disabled=self.vimeo_state is None or complete,
                )
                yield Button("Upload stoppen", id="vimeo_stop", disabled=True)
                with Horizontal(classes="navigation_actions"):
                    yield Button(
                        "Vimeo öffnen",
                        id="vimeo_open",
                        disabled=not bool(self.vimeo_state and self.vimeo_state.video_url),
                    )
                    yield Button(
                        "Embed-Code kopieren",
                        id="vimeo_copy_embed",
                        disabled=not bool(self.vimeo_state and self.vimeo_state.embed_html),
                    )
                    yield Button("Weiter zum Abschluss", id="vimeo_continue", variant="primary", disabled=not complete)
                    yield Button("Vimeo überspringen / später erledigen", id="vimeo_skip", disabled=complete)
            yield Footer()

        def on_mount(self) -> None:
            self.query_one("#vimeo_upload_bar", ProgressBar).display = False
            self.query_one("#vimeo_upload_details", Static).display = False
            if self.vimeo_state and self.vimeo_state.step.status == "complete" and self.vimeo_state.video_id:
                self._show_success(self.vimeo_state)
                self.query_one("#vimeo_continue", Button).focus()
            else:
                self._sync_vimeo_remote_actions()
                self.query_one("#vimeo_upload", Button).focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "vimeo_upload":
                self._start_publish()
                return
            if event.button.id == "vimeo_stop":
                self._request_stop_confirmation()
                return
            if event.button.id == "vimeo_skip":
                self._open_completion()
                return
            if event.button.id == "vimeo_continue":
                self._open_completion()
                return
            if event.button.id == "vimeo_open":
                self._open_vimeo()
                return
            if event.button.id == "vimeo_copy_embed":
                self._copy_embed()

        def _start_publish(self) -> None:
            if self.running:
                return
            self.cancel_event.clear()
            self.running = True
            self.query_one("#vimeo_stop", Button).label = "Upload stoppen"
            self._set_controls_running(True)
            self.query_one("#vimeo_status_banner", Static).update(
                "Vimeo-Veröffentlichung gestartet. Die lokalen Dateien bleiben unverändert."
            )
            self.query_one("#vimeo_status_banner", Static).set_classes("status-info")
            self.run_worker(
                self._publish_in_thread,
                thread=True,
                exclusive=True,
                group="vimeo-publish",
                exit_on_error=False,
            )

        def _publish_in_thread(self) -> None:
            try:
                service = make_vimeo_service(self.app_config)
                self.app.call_from_thread(
                    self._show_progress,
                    VimeoProgress("checking_connection"),
                )
                preview = service.preview_upload(self.state_path)
                self.app.call_from_thread(self._show_preview, preview)

                def report_progress(progress: VimeoProgress) -> None:
                    self.app.call_from_thread(self._show_progress, progress)

                service.publish(
                    self.state_path,
                    progress=report_progress,
                    should_cancel=self.cancel_event.is_set,
                )
                state = load_workflow_state(self.state_path).vimeo
                self.app.call_from_thread(self._show_success, state)
            except VimeoUploadStoppedError as exc:
                state = self._load_vimeo_state()
                self.app.call_from_thread(self._show_stopped, exc, state)
            except Exception as exc:
                state = self._load_vimeo_state()
                self.app.call_from_thread(self._show_error, exc, state)

        def _show_preview(self, preview) -> None:
            self.query_one("#vimeo_plan_text", Static).update(
                "\n".join(
                    [
                        f"Lokale MP4: {preview.file_path}",
                        f"Vimeo-Team / Konto: {preview.team_owner_name}",
                        f"Zielordner: {preview.folder.name} (ID {preview.folder.folder_id})",
                        f"Vimeo-Titel: {preview.title}",
                    ]
                )
            )
            self.query_one("#vimeo_progress", Static).update(build_tui_vimeo_progress_text("preparing"))
            if preview.remote_state_reset:
                banner = self.query_one("#vimeo_status_banner", Static)
                banner.update(
                    "Das zuvor gespeicherte Vimeo-Video existiert nicht mehr.\n"
                    "Die lokale Aufnahme bleibt unverändert. Ein neuer Vimeo-Upload wird vorbereitet."
                )
                banner.set_classes("status-info")

        def _show_progress(self, progress: VimeoProgress) -> None:
            self.last_progress = progress
            current = self._load_vimeo_state()
            self.vimeo_state = current
            self.query_one("#vimeo_progress", Static).update(
                build_tui_vimeo_progress_text(
                    progress.phase,
                    percent=progress.percent,
                    transcode_status=current.transcode_status if current else None,
                    video_url_available=bool(current and current.video_url),
                    embed_available=bool(current and current.embed_html),
                )
            )
            self._sync_vimeo_remote_actions()
            banner = self.query_one("#vimeo_status_banner", Static)
            if progress.phase == "remote_video_reset":
                banner.update(
                    "Das zuvor gespeicherte Vimeo-Video existiert nicht mehr.\n"
                    "Die lokale Aufnahme bleibt unverändert. Ein neuer Vimeo-Upload kann gestartet werden."
                )
                banner.set_classes("status-info")
            elif progress.phase == "verifying_upload":
                banner.update("Datei vollständig übertragen – Vimeo bestätigt den Upload.")
            elif progress.phase == "processing_video":
                banner.update("Datei vollständig hochgeladen – Vimeo verarbeitet das Video.")
            bar = self.query_one("#vimeo_upload_bar", ProgressBar)
            details = self.query_one("#vimeo_upload_details", Static)
            if progress.phase == "uploading":
                bar.display = True
                details.display = True
                bar.update(total=100, progress=progress.percent)
                details.update(format_tui_vimeo_upload_details(progress))
            elif progress.phase == "verifying_upload":
                bar.display = True
                details.display = True
                bar.update(total=100, progress=100)
                details.update(
                    format_tui_vimeo_upload_details(
                        VimeoProgress("uploading", progress.total_bytes, progress.total_bytes)
                    )
                )

        def _show_success(self, state: VimeoState) -> None:
            self.vimeo_state = state
            self.running = False
            banner = self.query_one("#vimeo_status_banner", Static)
            banner.update(build_tui_vimeo_success_text(self.plan, state))
            banner.set_classes("status-ok")
            self.query_one("#vimeo_progress", Static).update(
                build_tui_vimeo_progress_text(
                    "complete",
                    transcode_status=state.transcode_status,
                    video_url_available=bool(state.video_url),
                    embed_available=bool(state.embed_html),
                )
            )
            bar = self.query_one("#vimeo_upload_bar", ProgressBar)
            if self.last_progress and self.last_progress.total_bytes > 0:
                bar.display = True
                bar.update(total=100, progress=100)
            self._set_controls_running(False)
            processing = (state.transcode_status or "").lower() not in {"complete", "completed"}
            self.query_one("#vimeo_upload", Button).label = (
                "Datei hochgeladen – Vimeo verarbeitet noch"
                if processing
                else "Vimeo-Upload abgeschlossen"
            )
            self.query_one("#vimeo_upload", Button).disabled = True
            self.query_one("#vimeo_skip", Button).disabled = True
            self.query_one("#vimeo_open", Button).disabled = not bool(state.video_url)
            self.query_one("#vimeo_copy_embed", Button).disabled = not bool(state.embed_html)
            self.query_one("#vimeo_continue", Button).disabled = False
            self.query_one("#vimeo_continue", Button).focus()
            self.notify(
                "Datei hochgeladen; Vimeo verarbeitet das Video noch."
                if processing
                else "Vimeo-Upload abgeschlossen."
            )

        def _show_stopped(
            self,
            error: VimeoUploadStoppedError,
            state: VimeoState | None,
        ) -> None:
            self.vimeo_state = state
            self.running = False
            confirmed = state.upload_offset if state and state.upload_offset is not None else error.confirmed_bytes
            total = state.upload_size if state and state.upload_size is not None else error.total_bytes
            banner = self.query_one("#vimeo_status_banner", Static)
            banner.update(
                "Upload gestoppt.\n"
                f"{_format_vimeo_bytes(confirmed)} von {_format_vimeo_bytes(total)} wurden bestätigt übertragen.\n"
                "Ein erneuter Versuch kann den vorhandenen Upload fortsetzen."
            )
            banner.set_classes("status-info")
            self._set_controls_running(False)
            self.query_one("#vimeo_upload", Button).label = "Vimeo-Upload fortsetzen"
            self.query_one("#vimeo_upload", Button).disabled = state is None
            self.query_one("#vimeo_skip", Button).disabled = False
            self.query_one("#vimeo_stop", Button).disabled = True
            self.notify("Vimeo-Upload gestoppt. Der bestätigte Stand bleibt erhalten.")

        def _show_error(self, error: Exception, state: VimeoState | None) -> None:
            self.vimeo_state = state
            self.running = False
            banner = self.query_one("#vimeo_status_banner", Static)
            banner.update(build_tui_vimeo_error_text(error, state))
            banner.set_classes("status-danger")
            if self.last_progress is not None:
                self.query_one("#vimeo_progress", Static).update(
                    build_tui_vimeo_progress_text(
                        self.last_progress.phase,
                        percent=self.last_progress.percent,
                        transcode_status=state.transcode_status if state else None,
                        failed_phase=self.last_progress.phase,
                        video_url_available=bool(state and state.video_url),
                        embed_available=bool(state and state.embed_html),
                    )
                )
            self._set_controls_running(False)
            self.query_one("#vimeo_upload", Button).label = "Vimeo-Veröffentlichung erneut versuchen"
            self.query_one("#vimeo_upload", Button).disabled = state is None
            self.query_one("#vimeo_skip", Button).disabled = False
            self.query_one("#vimeo_open", Button).disabled = not bool(state and state.video_url)
            self.query_one("#vimeo_copy_embed", Button).disabled = not bool(state and state.embed_html)
            self.notify("Vimeo ist noch nicht abgeschlossen. Die lokalen Dateien sind sicher.", severity="error")

        def _set_controls_running(self, running: bool) -> None:
            self.query_one("#vimeo_upload", Button).disabled = running
            self.query_one("#vimeo_skip", Button).disabled = running
            self.query_one("#vimeo_stop", Button).disabled = not running
            if running:
                self.query_one("#vimeo_upload", Button).label = "Vimeo-Upload läuft..."
                self.query_one("#vimeo_continue", Button).disabled = True
            self._sync_vimeo_remote_actions()

        def _sync_vimeo_remote_actions(self) -> None:
            link_available = bool(self.vimeo_state and self.vimeo_state.video_url)
            embed_available = bool(self.vimeo_state and self.vimeo_state.embed_html)
            open_button = self.query_one("#vimeo_open", Button)
            embed_button = self.query_one("#vimeo_copy_embed", Button)
            open_button.disabled = not link_available
            embed_button.disabled = not embed_available
            open_button.set_class(link_available, "available-action")
            embed_button.set_class(embed_available, "available-action")
            self.query_one("#vimeo_available_actions", Static).update(
                build_tui_vimeo_available_actions_text(self.vimeo_state, running=self.running)
            )
            if link_available and not self._link_announced:
                self._link_announced = True
                self._highlight_new_vimeo_action(open_button)
                self.notify("Vimeo-Link ist jetzt verfügbar.")
            if embed_available and not self._embed_announced:
                self._embed_announced = True
                self._highlight_new_vimeo_action(embed_button)
                self.notify("Embed-Code ist jetzt verfügbar und kann bereits kopiert werden.")

        def _highlight_new_vimeo_action(self, button: Button) -> None:
            button.add_class("newly-available-action")
            self.set_timer(1.5, lambda: button.remove_class("newly-available-action"))

        def _request_stop_confirmation(self) -> None:
            if not self.running or self.cancel_event.is_set():
                return
            self.app.push_screen(VimeoStopConfirmationScreen(), self._handle_stop_confirmation)

        def _handle_stop_confirmation(self, stop_upload: bool | None) -> None:
            if not stop_upload or not self.running:
                return
            self.cancel_event.set()
            stop = self.query_one("#vimeo_stop", Button)
            stop.disabled = True
            stop.label = "Upload wird sicher gestoppt ..."
            banner = self.query_one("#vimeo_status_banner", Static)
            banner.update(
                "Upload wird nach der aktuellen Vimeo-Operation sicher gestoppt. "
                "Bitte kurz warten."
            )
            banner.set_classes("status-info")

        def _load_vimeo_state(self) -> VimeoState | None:
            try:
                return load_workflow_state(self.state_path).vimeo
            except (OSError, ValueError):
                return None

        def _open_vimeo(self) -> None:
            if not self.vimeo_state or not self.vimeo_state.video_url:
                self.notify("Vimeo hat noch keine verwendbare Video-URL geliefert.", severity="warning")
                return
            if not webbrowser.open(self.vimeo_state.video_url):
                self.notify("Vimeo konnte nicht automatisch geöffnet werden.", severity="warning")

        def _copy_embed(self) -> None:
            if not self.vimeo_state or not self.vimeo_state.embed_html:
                self.notify("Der Embed-Code ist noch nicht verfügbar.", severity="warning")
                return
            try:
                self.app.copy_to_clipboard(self.vimeo_state.embed_html)
            except Exception as exc:
                self.notify(f"Embed-Code konnte nicht kopiert werden: {exc}", severity="warning")
                return
            self.notify("Embed-Code wurde in die Zwischenablage kopiert.")

        def _open_completion(self) -> None:
            if self.direct_mode:
                self.app.pop_screen()
                self.app.pop_screen()
                return
            self.app.push_screen(
                CompletionScreen(
                    self.app_config,
                    self.plan,
                    opened_target_folder=self.opened_target_folder,
                    vimeo_state=self._load_vimeo_state(),
                )
            )

    class CompletionScreen(Screen[None]):
        def __init__(
            self,
            app_config: AppConfig,
            plan: PreparedRecordingPlan,
            *,
            opened_target_folder: bool,
            vimeo_state: VimeoState | None = None,
        ) -> None:
            super().__init__()
            self.app_config = app_config
            self.plan = plan
            self.opened_target_folder = opened_target_folder
            self.vimeo_state = vimeo_state

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("Fertig vorbereitet", id="screen_title")
            skipped_steps = {3} if self.plan.raw_recording is None else set()
            if not (self.vimeo_state and self.vimeo_state.step.status == "complete"):
                skipped_steps.add(8)
            yield Static(build_tui_progress_text(9, skipped_steps), classes="workflow_progress")
            yield Static(build_tui_processing_success_banner(self.plan, opened_target_folder=self.opened_target_folder), id="completion_banner", classes="status-ok")
            with VerticalScroll(id="completion_scroll"):
                yield Static(
                    build_tui_processing_success_status(
                        self.plan,
                        opened_target_folder=self.opened_target_folder,
                        vimeo_state=self.vimeo_state,
                    ),
                    id="completion_status",
                    classes="panel-info",
                )
            with Horizontal(id="completion_actions"):
                open_label, new_label, quit_label = tui_processing_finished_action_labels()
                yield Button(open_label, id="open_target", variant="primary")
                yield Button(new_label, id="new_recording")
                yield Button(quit_label, id="quit")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "open_target":
                try:
                    subprocess.Popen(["explorer", str(self.plan.target_folder)])
                except OSError as exc:
                    self.query_one("#completion_status", Static).update(
                        build_tui_processing_success_status(
                            self.plan,
                            opened_target_folder=False,
                            vimeo_state=self.vimeo_state,
                        )
                        + f"\n\nAdmin-Hinweis: {exc}"
                    )
                return
            if event.button.id == "new_recording":
                self._return_to_start()
                self.app.push_screen(StartSafetyScreen(self.app_config))
                return
            if event.button.id == "quit":
                self.app.exit()

        def _return_to_start(self) -> None:
            for _ in range(8):
                try:
                    self.app.pop_screen()
                except Exception:
                    return

    class FileCandidatesScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("MP4-Dateien", id="screen_title")
            yield Static(
                "Nur Anzeige im Prototyp. Die Auswahl und Verarbeitung laufen weiterhin im normalen Wizard.",
                id="screen_note",
            )
            for line in build_tui_file_candidates_lines(self.app_config):
                yield Static(line)
            yield Button("Zurück", id="back")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()

    class VimeoFolderCreateScreen(ModalScreen[str | None]):
        def __init__(self, destination: str) -> None:
            super().__init__()
            self.destination = destination

        def compose(self) -> ComposeResult:
            with Vertical(id="vimeo_folder_create_dialog"):
                yield Static("Neuen Vimeo-Ordner erstellen", classes="settings_heading")
                yield Static(f"Erstellen in: {self.destination}", classes="panel-info")
                yield Label("Name")
                yield Input(placeholder="Ordnername", id="vimeo_folder_create_name")
                yield Static("Erst 'Erstellen' verändert die Vimeo-Bibliothek.", classes="panel-neutral")
                with Horizontal(classes="navigation_actions"):
                    yield Button("Abbrechen", id="vimeo_folder_create_cancel")
                    yield Button("Erstellen", id="vimeo_folder_create_confirm", variant="primary")

        def on_mount(self) -> None:
            self.query_one("#vimeo_folder_create_name", Input).focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "vimeo_folder_create_cancel":
                self.dismiss(None)
            elif event.button.id == "vimeo_folder_create_confirm":
                value = " ".join(self.query_one("#vimeo_folder_create_name", Input).value.split())
                if not value:
                    self.notify("Bitte einen Ordnernamen eingeben.", severity="warning")
                    return
                self.dismiss(value)

    class VimeoFolderBrowserScreen(Screen[VimeoFolder | None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config
            self.catalog: VimeoFolderCatalog | None = None
            self.current_folder_id: str | None = None
            self.loading = False

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("Vimeo-Ordner auswählen", id="screen_title")
            yield Static("Team-Bibliothek wird geladen …", id="vimeo_folder_browser_status", classes="status-info")
            yield Static("", id="vimeo_folder_breadcrumbs", classes="panel-info")
            with VerticalScroll(id="vimeo_folder_browser_scroll"):
                yield DataTable(id="vimeo_folder_browser_table")
            with Horizontal(id="vimeo_folder_browser_actions", classes="navigation_actions"):
                yield Button("Abbrechen", id="vimeo_folder_browser_cancel")
                yield Button("Eine Ebene höher", id="vimeo_folder_browser_parent", disabled=True)
                yield Button("Zur Wurzel", id="vimeo_folder_browser_root", disabled=True)
                yield Button("Neuen Ordner erstellen", id="vimeo_folder_browser_create")
                yield Button(
                    "Diesen Ordner als Standard-Zielordner verwenden",
                    id="vimeo_folder_browser_select",
                    variant="primary",
                    disabled=True,
                )
                yield Button("Neu laden", id="vimeo_folder_browser_reload")
            yield Footer()

        @property
        def cache_key(self) -> str:
            return self.app_config.vimeo.team_owner_user_id

        def on_mount(self) -> None:
            table = self.query_one("#vimeo_folder_browser_table", DataTable)
            table.cursor_type = "row"
            table.add_columns("", "Ordner")
            cached = self.app.vimeo_folder_catalog_cache.get(self.cache_key)
            if cached is not None:
                self._show_catalog(cached)
            else:
                self._load_catalog()

        def on_unmount(self) -> None:
            self.workers.cancel_node(self)

        def _load_catalog(self, *, force: bool = False) -> None:
            if self.loading:
                return
            self.loading = True
            if force:
                self.app.vimeo_folder_catalog_cache.pop(self.cache_key, None)
            self.query_one("#vimeo_folder_browser_reload", Button).disabled = True
            self.query_one("#vimeo_folder_browser_status", Static).update("Vimeo-Ordner werden geladen …")

            def work() -> None:
                try:
                    catalog = make_vimeo_service(self.app_config).get_folder_catalog()
                    self.app.call_from_thread(self._show_catalog, catalog)
                except Exception as exc:
                    self.app.call_from_thread(self._show_catalog_error, exc)

            self.run_worker(work, thread=True, exclusive=True, group="vimeo-folder-catalog", exit_on_error=False)

        def _show_catalog(self, catalog: VimeoFolderCatalog) -> None:
            if not self.is_mounted:
                return
            self.catalog = catalog
            self.loading = False
            self.app.vimeo_folder_catalog_cache[self.cache_key] = catalog
            self.query_one("#vimeo_folder_browser_reload", Button).disabled = False
            configured = catalog.by_id(self.app_config.vimeo.target_folder_id)
            status = self.query_one("#vimeo_folder_browser_status", Static)
            if configured is None and self.app_config.vimeo.target_folder_id:
                status.update(
                    "Der konfigurierte Vimeo-Zielordner wurde nicht mehr gefunden.\n"
                    "Bitte einen neuen Zielordner auswählen."
                )
                status.set_classes("status-warning")
            else:
                status.update(f"Vimeo-Team: {catalog.team_owner_name}\n{len(catalog.folders)} Ordner geladen.")
                status.set_classes("status-ok")
            self._refresh_folder_table()

        def _show_catalog_error(self, error: Exception) -> None:
            if not self.is_mounted:
                return
            self.loading = False
            message = error.user_message if isinstance(error, VimeoError) else str(error)
            self.query_one("#vimeo_folder_browser_status", Static).update(message)
            self.query_one("#vimeo_folder_browser_status", Static).set_classes("status-danger")
            self.query_one("#vimeo_folder_browser_reload", Button).disabled = False

        def _refresh_folder_table(self) -> None:
            if self.catalog is None:
                return
            table = self.query_one("#vimeo_folder_browser_table", DataTable)
            table.clear(columns=False)
            for folder in self.catalog.children_of(self.current_folder_id):
                marker = "AKTUELL" if folder.folder_id == self.app_config.vimeo.target_folder_id else "ORDNER"
                table.add_row(marker, folder.name, key=folder.folder_id)
            breadcrumb = build_tui_vimeo_breadcrumbs(
                self.catalog.team_owner_name, self.catalog, self.current_folder_id
            )
            self.query_one("#vimeo_folder_breadcrumbs", Static).update(breadcrumb)
            current = self.catalog.by_id(self.current_folder_id or "")
            self.query_one("#vimeo_folder_browser_select", Button).disabled = current is None
            self.query_one("#vimeo_folder_browser_parent", Button).disabled = current is None
            self.query_one("#vimeo_folder_browser_root", Button).disabled = current is None

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            if event.data_table.id != "vimeo_folder_browser_table":
                return
            self.current_folder_id = str(event.row_key.value)
            self._refresh_folder_table()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            button_id = event.button.id
            if button_id == "vimeo_folder_browser_cancel":
                self.dismiss(None)
            elif button_id == "vimeo_folder_browser_reload":
                self._load_catalog(force=True)
            elif button_id == "vimeo_folder_browser_root":
                self.current_folder_id = None
                self._refresh_folder_table()
            elif button_id == "vimeo_folder_browser_parent" and self.catalog is not None:
                current = self.catalog.by_id(self.current_folder_id or "")
                self.current_folder_id = (
                    self._folder_id_from_uri(current.parent_folder_uri) if current else None
                )
                self._refresh_folder_table()
            elif button_id == "vimeo_folder_browser_select" and self.catalog is not None:
                folder = self.catalog.by_id(self.current_folder_id or "")
                if folder is not None:
                    self.dismiss(folder)
            elif button_id == "vimeo_folder_browser_create" and self.catalog is not None:
                destination = build_tui_vimeo_breadcrumbs(
                    self.catalog.team_owner_name, self.catalog, self.current_folder_id
                )
                self.app.push_screen(VimeoFolderCreateScreen(destination), self._create_folder)

        @staticmethod
        def _folder_id_from_uri(uri: str | None) -> str | None:
            if not uri:
                return None
            return uri.rstrip("/").rsplit("/", 1)[-1]

        def _create_folder(self, name: str | None) -> None:
            if not name:
                return
            self.query_one("#vimeo_folder_browser_status", Static).update("Vimeo-Ordner wird erstellt …")

            def work() -> None:
                try:
                    service = make_vimeo_service(self.app_config)
                    service.create_folder(name, parent_folder_id=self.current_folder_id)
                    catalog = service.get_folder_catalog()
                    self.app.call_from_thread(self._show_catalog, catalog)
                    self.app.call_from_thread(self.notify, "Der Vimeo-Ordner wurde erstellt.")
                except Exception as exc:
                    self.app.call_from_thread(self._show_catalog_error, exc)

            self.run_worker(work, thread=True, exclusive=True, group="vimeo-folder-create", exit_on_error=False)

    class VimeoLibraryScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config
            self.result: VimeoLibraryResult | None = None
            self.visible_videos: tuple[VimeoLibraryVideo, ...] = ()
            self.selected_video: VimeoLibraryVideo | None = None
            self.loading = False
            self.mode = "all"
            self.sort_order = "newest"
            self.catalog: VimeoFolderCatalog | None = None
            self.current_folder_id: str | None = None
            self.load_generation = 0

        @property
        def cache_key(self) -> tuple[str, str]:
            return (
                self.app_config.vimeo.team_owner_user_id,
                "__all__" if self.mode == "all" else (self.current_folder_id or "__root__"),
            )

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("Vimeo-Bibliothek", id="screen_title")
            yield Static(
                "Echte Vimeo-Daten werden nur gelesen. Es wird nichts hochgeladen, verschoben oder gelöscht.",
                id="vimeo_library_note",
                classes="panel-info",
            )
            with Horizontal(id="vimeo_library_view_switch", classes="navigation_actions"):
                yield Button("Alle Videos", id="vimeo_library_view_all", variant="primary")
                yield Button("Ordner", id="vimeo_library_view_folders")
            with VerticalScroll(id="vimeo_library_scroll"):
                yield Static("Vimeo-Bibliothek wird geladen …", id="vimeo_library_status", classes="status-info")
                yield Static("", id="vimeo_library_breadcrumbs", classes="panel-info")
                yield Input(placeholder="Titel in den geladenen Videos suchen", id="vimeo_library_search")
                yield Select(
                    (("Neueste zuerst", "newest"), ("Älteste zuerst", "oldest"), ("Titel A-Z", "title_az"), ("Titel Z-A", "title_za")),
                    value="newest",
                    id="vimeo_library_sort",
                )
                yield DataTable(id="vimeo_library_table")
                yield Static("Noch kein Video ausgewählt.", id="vimeo_library_details", classes="panel-neutral")
            with Vertical(id="vimeo_library_actions"):
                with Horizontal(classes="navigation_actions"):
                    yield Button("Zurück", id="vimeo_library_back")
                    yield Button("Eine Ebene höher", id="vimeo_library_parent", disabled=True)
                    yield Button("Zur Wurzel", id="vimeo_library_root", disabled=True)
                    yield Button("Neu laden", id="vimeo_library_reload")
                    yield Button("Vimeo öffnen", id="vimeo_library_open", disabled=True)
                    yield Button("Vimeo-Link kopieren", id="vimeo_library_copy_link", disabled=True)
                with Horizontal(classes="navigation_actions"):
                    yield Button("Embed-Code kopieren", id="vimeo_library_copy_embed", disabled=True)
                    yield Button("Details anzeigen", id="vimeo_library_show_details", disabled=True)
                    yield Button("Download nicht verfügbar", id="vimeo_library_downloads", disabled=True)
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one("#vimeo_library_table", DataTable)
            table.cursor_type = "row"
            table.add_columns("Typ", "Titel", "Erstellt", "Status", "Dauer")
            cached = self.app.vimeo_library_cache.get(self.cache_key)
            if cached is not None:
                self._show_library(cached)
                return
            self._start_library_load()

        def on_unmount(self) -> None:
            self.load_generation += 1
            self.workers.cancel_node(self)

        def _start_library_load(self, *, force: bool = False) -> None:
            if self.loading:
                return
            self.loading = True
            if force:
                self.app.vimeo_library_cache.pop(self.cache_key, None)
                if self.mode == "folders" and self.current_folder_id is None:
                    self.catalog = None
                    self.app.vimeo_folder_catalog_cache.pop(
                        self.app_config.vimeo.team_owner_user_id, None
                    )
                status = self.query_one("#vimeo_library_status", Static)
                status.update("Vimeo-Bibliothek wird neu geladen …")
                status.set_classes("status-info")
            self.query_one("#vimeo_library_reload", Button).disabled = True
            self.query_one("#vimeo_library_search", Input).disabled = False
            self.load_generation += 1
            generation = self.load_generation
            mode = self.mode
            folder_id = self.current_folder_id
            self.run_worker(
                lambda: self._load_library_in_thread(generation, mode, folder_id),
                thread=True,
                exclusive=True,
                group="vimeo-library",
                exit_on_error=False,
            )

        def _load_library_in_thread(
            self,
            generation: int,
            mode: str,
            folder_id: str | None,
        ) -> None:
            try:
                service = make_vimeo_service(self.app_config)
                if mode == "folders" and self.catalog is None:
                    catalog = service.get_folder_catalog()
                    self.app.call_from_thread(self._show_folder_catalog_if_current, catalog, generation)
                    return
                emitted = False

                def report_page(result: VimeoLibraryResult) -> None:
                    nonlocal emitted
                    emitted = True
                    self.app.call_from_thread(
                        self._show_library_if_current,
                        result,
                        generation,
                        mode,
                        folder_id,
                    )

                if mode == "all":
                    loader = getattr(service, "list_all_videos", service.list_target_folder_videos)
                    result = loader(progress=report_page)
                elif folder_id:
                    result = service.list_folder_videos(folder_id, progress=report_page)
                else:
                    self.app.call_from_thread(self._show_folder_root_if_current, generation)
                    return
                if not emitted:
                    self.app.call_from_thread(
                        self._show_library_if_current,
                        result,
                        generation,
                        mode,
                        folder_id,
                    )
            except Exception as exc:
                self.app.call_from_thread(self._show_library_error_if_current, exc, generation)

        def _show_library_if_current(
            self,
            result: VimeoLibraryResult,
            generation: int,
            mode: str,
            folder_id: str | None,
        ) -> None:
            if (
                not self.is_mounted
                or generation != self.load_generation
                or mode != self.mode
                or folder_id != self.current_folder_id
            ):
                return
            self._show_library(result)

        def _show_library_error_if_current(self, error: Exception, generation: int) -> None:
            if self.is_mounted and generation == self.load_generation:
                self._show_library_error(error)

        def _show_library(self, result: VimeoLibraryResult) -> None:
            self.result = result
            self.loading = not result.complete
            status = self.query_one("#vimeo_library_status", Static)
            if result.videos:
                count = len(result.videos)
                if result.complete:
                    count_text = f"{count} Videos geladen."
                elif result.total_count is not None:
                    count_text = f"{count} / {result.total_count} Videos geladen – weitere werden geladen …"
                else:
                    count_text = f"{count} Videos geladen – weitere werden geladen …"
                status.update(
                    f"Vimeo-Team: {result.team_owner_name}\n"
                    + (f"Ordner: {result.folder.name}\n" if self.mode == "folders" else "Ansicht: Alle Videos\n")
                    + f"{count_text}"
                    + (
                        "\nDie Titelsuche berücksichtigt vorerst nur die bereits geladenen Videos."
                        if not result.complete
                        else ""
                    )
                )
                status.set_classes("status-ok" if result.complete else "status-info")
            else:
                status.update(
                    f"Der Vimeo-Ordner {result.folder.name} ist leer oder enthält keine sichtbaren Videos."
                )
                status.set_classes("status-info")
            if result.complete:
                self.app.vimeo_library_cache[self.cache_key] = result
                self.query_one("#vimeo_library_reload", Button).disabled = False
            self._refresh_library_table()

        def _show_folder_catalog(self, catalog: VimeoFolderCatalog) -> None:
            self.catalog = catalog
            self.app.vimeo_folder_catalog_cache[self.app_config.vimeo.team_owner_user_id] = catalog
            self._show_folder_root()

        def _show_folder_catalog_if_current(
            self, catalog: VimeoFolderCatalog, generation: int
        ) -> None:
            if self.is_mounted and generation == self.load_generation and self.mode == "folders":
                self._show_folder_catalog(catalog)

        def _show_folder_root_if_current(self, generation: int) -> None:
            if self.is_mounted and generation == self.load_generation and self.mode == "folders":
                self._show_folder_root()

        def _show_folder_root(self) -> None:
            self.loading = False
            self.result = None
            self.selected_video = None
            self.query_one("#vimeo_library_reload", Button).disabled = False
            status = self.query_one("#vimeo_library_status", Static)
            status.update("Vimeo-Ordner sind geladen. Ordner mit Enter öffnen.")
            status.set_classes("status-ok")
            self._refresh_library_table()

        def _show_library_error(self, error: Exception) -> None:
            self.loading = False
            status = self.query_one("#vimeo_library_status", Static)
            if isinstance(error, VimeoError):
                details = f"\nAdmin-Hinweis: {error.admin_hint}" if error.admin_hint else ""
                message = error.user_message + details
            else:
                message = (
                    "Die Vimeo-Bibliothek konnte nicht geladen werden.\n"
                    f"Admin-Hinweis: {type(error).__name__}: {error}"
                )
            status.update(message)
            status.set_classes("status-danger")
            self.query_one("#vimeo_library_search", Input).disabled = self.result is None
            self.query_one("#vimeo_library_reload", Button).disabled = False

        def on_input_changed(self, event: Input.Changed) -> None:
            if event.input.id == "vimeo_library_search" and self.result is not None:
                self._refresh_library_table()

        def on_select_changed(self, event: Select.Changed) -> None:
            if event.select.id == "vimeo_library_sort" and event.value is not Select.BLANK:
                self.sort_order = str(event.value)
                self._refresh_library_table()

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            if event.data_table.id != "vimeo_library_table":
                return
            row_key = str(event.row_key.value)
            if row_key.startswith("folder:"):
                self.current_folder_id = row_key.split(":", 1)[1]
                self.result = None
                cached = self.app.vimeo_library_cache.get(self.cache_key)
                if cached is not None:
                    self._show_library(cached)
                else:
                    self._start_library_load()
                return
            video_id = row_key.split(":", 1)[-1]
            self.selected_video = next(
                (video for video in self.visible_videos if video.video_id == video_id),
                None,
            )
            self._sync_library_selection(show_details=False)

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "vimeo_library_back":
                self.app.pop_screen()
                return
            if event.button.id == "vimeo_library_view_all":
                self._switch_library_mode("all")
                return
            if event.button.id == "vimeo_library_view_folders":
                self._switch_library_mode("folders")
                return
            if event.button.id == "vimeo_library_root":
                self.current_folder_id = None
                self._show_folder_root()
                return
            if event.button.id == "vimeo_library_parent":
                if self.catalog is not None:
                    current = self.catalog.by_id(self.current_folder_id or "")
                    self.current_folder_id = VimeoFolderBrowserScreen._folder_id_from_uri(
                        current.parent_folder_uri if current else None
                    )
                    if self.current_folder_id:
                        cached = self.app.vimeo_library_cache.get(self.cache_key)
                        self._show_library(cached) if cached is not None else self._start_library_load()
                    else:
                        self._show_folder_root()
                return
            if event.button.id == "vimeo_library_reload":
                self._start_library_load(force=True)
                return
            if event.button.id == "vimeo_library_open":
                self._open_selected_video()
                return
            if event.button.id == "vimeo_library_copy_link":
                self._copy_library_value("Vimeo-Link", self.selected_video.video_url if self.selected_video else None)
                return
            if event.button.id == "vimeo_library_copy_embed":
                self._copy_library_value("Embed-Code", self.selected_video.embed_html if self.selected_video else None)
                return
            if event.button.id == "vimeo_library_downloads":
                self._open_selected_download()
                return
            if event.button.id == "vimeo_library_show_details":
                self._sync_library_selection(show_details=True)

        def _switch_library_mode(self, mode: str) -> None:
            if mode == self.mode:
                return
            self.mode = mode
            self.load_generation += 1
            self.loading = False
            self.result = None
            self.selected_video = None
            self.current_folder_id = None
            self.query_one("#vimeo_library_view_all", Button).variant = "primary" if mode == "all" else "default"
            self.query_one("#vimeo_library_view_folders", Button).variant = "primary" if mode == "folders" else "default"
            if mode == "folders":
                self.catalog = self.app.vimeo_folder_catalog_cache.get(
                    self.app_config.vimeo.team_owner_user_id
                )
                if self.catalog is not None:
                    self._show_folder_root()
                    return
            cached = self.app.vimeo_library_cache.get(self.cache_key)
            self._show_library(cached) if cached is not None else self._start_library_load()

        def _refresh_library_table(self) -> None:
            selected_id = self.selected_video.video_id if self.selected_video else None
            videos = self.result.videos if self.result is not None else ()
            search = self.query_one("#vimeo_library_search", Input).value
            self.visible_videos = sort_tui_vimeo_library_videos(
                filter_tui_vimeo_library_videos(videos, search), self.sort_order
            )
            self.selected_video = None
            table = self.query_one("#vimeo_library_table", DataTable)
            table.clear(columns=False)
            if self.mode == "folders" and self.catalog is not None:
                for folder in self.catalog.children_of(self.current_folder_id):
                    marker = "AKTUELL" if folder.folder_id == self.app_config.vimeo.target_folder_id else "ORDNER"
                    table.add_row(marker, folder.name, "", "", "", key=f"folder:{folder.folder_id}")
            for video in self.visible_videos:
                status = video.transcode_status or video.status or video.upload_status or "unbekannt"
                table.add_row(
                    "VIDEO",
                    video.title,
                    _format_vimeo_created_time(video.created_time),
                    status.upper(),
                    _format_vimeo_duration(video.duration),
                    key=f"video:{video.video_id}",
                )
            team_name = (
                self.catalog.team_owner_name
                if self.catalog is not None
                else (self.result.team_owner_name if self.result is not None else "Vimeo-Team")
            )
            self.query_one("#vimeo_library_breadcrumbs", Static).update(
                build_tui_vimeo_breadcrumbs(team_name, self.catalog, self.current_folder_id)
                if self.mode == "folders"
                else "Alle Videos"
            )
            self.query_one("#vimeo_library_parent", Button).disabled = not (
                self.mode == "folders" and self.current_folder_id
            )
            self.query_one("#vimeo_library_root", Button).disabled = not (
                self.mode == "folders" and self.current_folder_id
            )
            if selected_id:
                self.selected_video = next(
                    (video for video in self.visible_videos if video.video_id == selected_id),
                    None,
                )
            if not self.visible_videos and self.result and self.result.videos:
                self.query_one("#vimeo_library_details", Static).update(
                    "Keine geladenen Vimeo-Videos passen zur Titelsuche."
                )
            elif not self.visible_videos:
                self.query_one("#vimeo_library_details", Static).update("Keine Videos vorhanden.")
            else:
                self.query_one("#vimeo_library_details", Static).update(
                    "Video mit Pfeiltasten auswählen und Enter drücken."
                )
            self._sync_library_selection(show_details=False)

        def _sync_library_selection(self, *, show_details: bool) -> None:
            video = self.selected_video
            self.query_one("#vimeo_library_open", Button).disabled = not bool(video and video.video_url)
            self.query_one("#vimeo_library_copy_link", Button).disabled = not bool(video and video.video_url)
            self.query_one("#vimeo_library_copy_embed", Button).disabled = not bool(video and video.embed_html)
            self.query_one("#vimeo_library_show_details", Button).disabled = video is None
            downloads = self.query_one("#vimeo_library_downloads", Button)
            downloads.disabled = not bool(video and video.download_available)
            downloads.label = (
                f"Video herunterladen ({len(video.downloads)} Qualität(en))"
                if video and video.downloads
                else "Download nicht verfügbar"
            )
            if video is None:
                return
            folder_name = self.result.folder.name if self.result else self.app_config.vimeo.target_folder_name
            if show_details:
                text = build_tui_vimeo_library_details(video, folder_name)
            else:
                text = (
                    f"Ausgewählt: {video.title}\n"
                    f"Status: {(video.transcode_status or video.status or 'unbekannt').upper()}\n"
                    f"Embed-Code: {'verfügbar' if video.embed_html else 'nicht geliefert'}\n"
                    f"Download: {'Optionen verfügbar' if video.download_available else 'nicht von Vimeo geliefert'}"
                )
            self.query_one("#vimeo_library_details", Static).update(text)

        def _open_selected_download(self) -> None:
            video = self.selected_video
            if not video or not video.downloads:
                self.notify("Vimeo hat für dieses Video keinen erlaubten Download-Link geliefert.", severity="warning")
                return
            if not webbrowser.open(video.downloads[0].link):
                self.notify("Der Vimeo-Download konnte nicht im Browser geöffnet werden.", severity="warning")
                return
            self.notify("Der von Vimeo gelieferte Download-Link wurde im Browser geöffnet.")

        def _open_selected_video(self) -> None:
            if not self.selected_video or not self.selected_video.video_url:
                self.notify("Vimeo hat für dieses Video keinen Link geliefert.", severity="warning")
                return
            if not webbrowser.open(self.selected_video.video_url):
                self.notify("Vimeo konnte nicht automatisch geöffnet werden.", severity="warning")

        def _copy_library_value(self, label: str, value: str | None) -> None:
            if not value:
                self.notify(f"{label} ist für dieses Video nicht verfügbar.", severity="warning")
                return
            try:
                self.app.copy_to_clipboard(value)
            except Exception as exc:
                self.notify(f"{label} konnte nicht kopiert werden: {exc}", severity="warning")
                return
            self.notify(f"{label} wurde in die Zwischenablage kopiert.")

    class DirectVimeoSelectionScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config
            self.current_folder = app_config.recordings_base
            self._visible_candidates: tuple[Path, ...] = ()

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("Direkt zu Vimeo hochladen", id="screen_title")
            yield Static(
                "Admin / Sonderfall: Nur eine fertig geschnittene, korrekt benannte MP4 am endgültigen Speicherort wählen. "
                "Der Upload startet erst auf dem folgenden Vimeo-Screen.",
                id="direct_vimeo_warning",
                classes="status-warning",
            )
            with VerticalScroll(id="direct_vimeo_selection_scroll"):
                yield Static(f"Ordner: {self.current_folder}", id="direct_vimeo_folder")
                yield Input(placeholder="Dateiname filtern", id="direct_vimeo_search")
                yield DataTable(id="direct_vimeo_table")
                yield Input(placeholder="MP4-Datei oder Ordner manuell eingeben", id="direct_vimeo_path")
                yield Static("Noch keine Datei ausgewählt.", id="direct_vimeo_status", classes="panel-info")
            with Horizontal(id="direct_vimeo_actions", classes="navigation_actions"):
                yield Button("Zurück", id="direct_vimeo_back")
                yield Button("Pfad verwenden", id="direct_vimeo_manual")
                yield Button("Ausgewählte MP4 prüfen", id="direct_vimeo_select", variant="primary")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one("#direct_vimeo_table", DataTable)
            table.cursor_type = "row"
            table.zebra_stripes = True
            table.add_columns("Dateiname", "Geändert", "Größe")
            self._refresh_table()
            table.focus()

        def on_input_changed(self, event: Input.Changed) -> None:
            if event.input.id == "direct_vimeo_search":
                self._refresh_table()

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            try:
                selected = self._visible_candidates[int(str(event.row_key.value))]
            except (ValueError, IndexError):
                return
            self._prepare(selected)

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "direct_vimeo_back":
                self.app.pop_screen()
                return
            if event.button.id == "direct_vimeo_manual":
                text = self.query_one("#direct_vimeo_path", Input).value.strip()
                if not text:
                    self.notify("Bitte eine MP4-Datei oder einen Ordner eingeben.", severity="warning")
                    return
                path = Path(text).expanduser()
                if path.is_dir():
                    self.current_folder = path
                    self._refresh_table()
                    return
                self._prepare(path)
                return
            if event.button.id == "direct_vimeo_select":
                table = self.query_one("#direct_vimeo_table", DataTable)
                if not self._visible_candidates or table.cursor_row >= len(self._visible_candidates):
                    self.notify("Bitte zuerst eine MP4-Datei auswählen.", severity="warning")
                    return
                self._prepare(self._visible_candidates[table.cursor_row])

        def _refresh_table(self) -> None:
            rows = build_tui_mp4_file_rows(
                self.current_folder,
                search_text=self.query_one("#direct_vimeo_search", Input).value,
                limit=TUI_FILE_CHOICE_LIMIT,
            )
            self._visible_candidates = tuple(row.path for row in rows)
            table = self.query_one("#direct_vimeo_table", DataTable)
            table.clear()
            for index, row in enumerate(rows):
                table.add_row(row.filename, row.modified, row.size, key=str(index))
            self.query_one("#direct_vimeo_folder", Static).update(f"Ordner: {self.current_folder}")

        def _prepare(self, candidate: Path) -> None:
            status = self.query_one("#direct_vimeo_status", Static)
            try:
                final_mp4 = validate_direct_vimeo_mp4(candidate)
                state_path, created = load_or_create_direct_vimeo_state(final_mp4)
                state = load_workflow_state(state_path)
                plan = build_direct_vimeo_plan(final_mp4, state)
            except (OSError, ValueError, FileExistsError) as exc:
                status.update(str(exc))
                status.set_classes("status-danger")
                return
            status.update(
                "\n".join(
                    [
                        f"Lokale MP4: {final_mp4}",
                        f"Vimeo-Team-ID: {self.app_config.vimeo.team_owner_user_id}",
                        f"Zielordner: {self.app_config.vimeo.target_folder_name} (ID {self.app_config.vimeo.target_folder_id})",
                        f"Geplanter Titel: {build_vimeo_title(state.sermon, final_mp4)}",
                        "Workflow-Status: " + ("neu und isoliert angelegt" if created else "vorhanden und wiederverwendet"),
                        "Es wurde noch kein Upload gestartet.",
                    ]
                )
            )
            status.set_classes("status-ok")
            self.app.open_vimeo_publishing(
                plan,
                state_path=state_path,
                opened_target_folder=False,
                direct_mode=True,
            )

    class SettingsScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config
            self.selected_vimeo_folder_id = app_config.vimeo.target_folder_id
            self.selected_vimeo_folder_name = app_config.vimeo.target_folder_name

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("Einstellungen", id="screen_title")
            with VerticalScroll(id="settings_scroll"):
                yield Label("Allgemein", classes="settings_heading")
                yield Label("Ziel-Basisordner")
                yield Input(value=str(self.app_config.recordings_base), id="settings_recordings_base")
                yield Label("Rohaufnahme-Ordner")
                yield Input(value=str(self.app_config.vmix_storage), id="settings_vmix_storage")
                yield Label("Jahresordner-Format")
                yield Input(value=self.app_config.year_folder_template, id="settings_year_template")
                yield Label("Verarbeitung / Dateien", classes="settings_heading")
                yield Label("LosslessCut-Pfad")
                yield Input(value=self.app_config.losslesscut_path, id="settings_losslesscut")
                yield Label("Verhalten der Rohaufnahme")
                yield Select(
                    (("verschieben", "move"), ("kopieren", "copy"), ("liegen lassen", "keep")),
                    value=self.app_config.raw_archive_mode,
                    id="settings_raw_mode",
                )
                yield Button("Einstellungen speichern", id="settings_save_general", variant="primary")
                yield Label("Vimeo", classes="settings_heading")
                yield Static(f"Vimeo-Zugang: {credentials.status_text()}", id="settings_token_status", classes="panel-info")
                yield Static("Team: noch nicht geprüft", id="settings_vimeo_team", classes="panel-neutral")
                yield Label("Standard-Zielordner für Uploads")
                yield Static(
                    self.selected_vimeo_folder_name or "Nicht ausgewählt",
                    id="settings_vimeo_folder_display",
                    classes="panel-info",
                )
                yield Button(
                    "Zielordner auswählen / ändern",
                    id="settings_select_vimeo_folder",
                    variant="primary",
                )
                yield Input(placeholder="Vimeo-Token sicher speichern", password=True, id="settings_vimeo_token")
                with Horizontal(classes="settings_button_row"):
                    yield Button("Vimeo-Token einrichten / ersetzen", id="settings_save_token", variant="primary")
                    yield Button("Vimeo-Verbindung prüfen", id="settings_check_vimeo")
                    yield Button("Gespeicherten Token entfernen", id="settings_remove_token")
                yield Static("Noch keine Verbindungsprüfung ausgeführt.", id="settings_vimeo_result")
                yield Label("Prediger", classes="settings_heading")
                yield Static("Gespeicherte Prediger", classes="panel-info")
                yield DataTable(id="settings_speaker_table")
                yield Input(placeholder="Prediger hinzufügen oder neuen Namen eingeben", id="settings_speaker_name")
                with Horizontal(classes="settings_button_row"):
                    yield Button("Hinzufügen", id="settings_add_speaker")
                    yield Button("Ausgewählten umbenennen", id="settings_rename_speaker")
                    yield Button("Ausgewählten entfernen", id="settings_remove_speaker")
                yield Label("Erweitert / Admin", classes="settings_heading")
                yield Static(
                    "\n".join(
                        (
                            f"Config: {describe_config_source()}",
                            f"Team-Owner-ID: {self.app_config.vimeo.team_owner_user_id or '(nicht gesetzt)'}",
                            f"Zielordner-ID: {self.selected_vimeo_folder_id or '(nicht gesetzt)'}",
                            f"Anwendungsversion: {_application_version()}",
                            "Der Vimeo-Token wird hier niemals angezeigt.",
                        )
                    ),
                    id="settings_admin_info",
                    classes="panel-neutral",
                )
                yield Button("Vimeo-Diagnose / Verbindung prüfen", id="settings_admin_diagnose")
                yield Button("Vimeo-Cache leeren", id="settings_clear_vimeo_cache")
            with Horizontal(id="settings_actions", classes="navigation_actions"):
                yield Button("Zurück", id="back")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one("#settings_speaker_table", DataTable)
            table.cursor_type = "row"
            table.add_column("Name")
            self._refresh_speakers()

        def on_unmount(self) -> None:
            self.workers.cancel_node(self)

        def _refresh_speakers(self) -> None:
            table = self.query_one("#settings_speaker_table", DataTable)
            table.clear()
            try:
                values = speakers.list()
            except OSError as exc:
                self.query_one("#settings_vimeo_result", Static).update(str(exc))
                values = ()
            for index, name in enumerate(values):
                table.add_row(name, key=str(index))

        def _refresh_token_status(self) -> None:
            self.query_one("#settings_token_status", Static).update(f"Vimeo-Zugang: {credentials.status_text()}")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()
                return
            if event.button.id == "settings_save_general":
                self._save_general()
                return
            if event.button.id == "settings_save_token":
                try:
                    credentials.store(self.query_one("#settings_vimeo_token", Input).value)
                except CredentialError as exc:
                    self.notify(str(exc), severity="error")
                    return
                self.query_one("#settings_vimeo_token", Input).value = ""
                self._refresh_token_status()
                self.notify("Der Vimeo-Token wurde sicher gespeichert.")
                return
            if event.button.id == "settings_remove_token":
                try:
                    credentials.remove_stored()
                except CredentialError as exc:
                    self.notify(str(exc), severity="error")
                    return
                self._refresh_token_status()
                self.notify("Der lokal gespeicherte Vimeo-Token wurde entfernt.")
                return
            if event.button.id == "settings_check_vimeo":
                self._check_vimeo()
                return
            if event.button.id == "settings_admin_diagnose":
                self._check_vimeo()
                return
            if event.button.id == "settings_select_vimeo_folder":
                self.app.push_screen(VimeoFolderBrowserScreen(self.app_config), self._select_vimeo_folder)
                return
            if event.button.id == "settings_clear_vimeo_cache":
                self.app.vimeo_library_cache.clear()
                self.app.vimeo_folder_catalog_cache.clear()
                self.notify("Der Vimeo-Cache dieser Programmsitzung wurde geleert.")
                return
            if event.button.id == "settings_add_speaker":
                try:
                    speakers.add(self.query_one("#settings_speaker_name", Input).value)
                except OSError as exc:
                    self.notify(str(exc), severity="error")
                    return
                self.query_one("#settings_speaker_name", Input).value = ""
                self._refresh_speakers()
                return
            if event.button.id == "settings_remove_speaker":
                table = self.query_one("#settings_speaker_table", DataTable)
                values = speakers.list()
                if values and table.cursor_row < len(values):
                    speakers.remove(values[table.cursor_row])
                    self._refresh_speakers()
                return
            if event.button.id == "settings_rename_speaker":
                table = self.query_one("#settings_speaker_table", DataTable)
                values = speakers.list()
                if not values or table.cursor_row >= len(values):
                    self.notify("Bitte zuerst einen Prediger auswählen.", severity="warning")
                    return
                try:
                    speakers.rename(
                        values[table.cursor_row],
                        self.query_one("#settings_speaker_name", Input).value,
                    )
                except (OSError, ValueError) as exc:
                    self.notify(str(exc), severity="warning")
                    return
                self.query_one("#settings_speaker_name", Input).value = ""
                self._refresh_speakers()

        def _select_vimeo_folder(self, folder: VimeoFolder | None) -> None:
            if folder is None:
                return
            try:
                saved_path = save_user_config_values(
                    vimeo={
                        "team_owner_user_id": self.app_config.vimeo.team_owner_user_id,
                        "target_folder_id": folder.folder_id,
                        "target_folder_name": folder.name,
                    }
                )
                refreshed = load_config(saved_path)
            except ConfigLoadError as exc:
                self.notify(
                    f"{exc.user_message} Admin-Hinweis: {exc.admin_hint}",
                    severity="error",
                )
                return
            self.app.app_config = refreshed
            self.app_config = refreshed
            self.selected_vimeo_folder_id = refreshed.vimeo.target_folder_id
            self.selected_vimeo_folder_name = refreshed.vimeo.target_folder_name
            self.query_one("#settings_vimeo_folder_display", Static).update(folder.name)
            self._refresh_admin_info()
            self.notify("Der Vimeo-Zielordner wurde gespeichert.")

        def _refresh_admin_info(self) -> None:
            self.query_one("#settings_admin_info", Static).update(
                "\n".join(
                    (
                        f"Config: {describe_config_source()}",
                        f"Team-Owner-ID: {self.app_config.vimeo.team_owner_user_id or '(nicht gesetzt)'}",
                        f"Zielordner-ID: {self.selected_vimeo_folder_id or '(nicht gesetzt)'}",
                        f"Anwendungsversion: {_application_version()}",
                        "Der Vimeo-Token wird hier niemals angezeigt.",
                    )
                )
            )

        def _save_general(self) -> None:
            raw_mode = self.query_one("#settings_raw_mode", Select).value
            recordings_base = self.query_one("#settings_recordings_base", Input).value.strip()
            vmix_storage = self.query_one("#settings_vmix_storage", Input).value.strip()
            year_template = self.query_one("#settings_year_template", Input).value.strip()
            if not recordings_base or not vmix_storage:
                self.notify("Ziel-Basisordner und Rohaufnahme-Ordner dürfen nicht leer sein.", severity="warning")
                return
            try:
                rendered_year = year_template.format(year=2026)
            except (KeyError, ValueError) as exc:
                self.notify(f"Das Jahresordner-Format ist ungültig: {exc}", severity="warning")
                return
            if "{year}" not in year_template or not rendered_year.strip():
                self.notify("Das Jahresordner-Format muss {year} enthalten.", severity="warning")
                return
            try:
                saved_path = save_user_config_values(
                    paths={
                        "recordings_base": recordings_base,
                        "vmix_storage": vmix_storage,
                        "losslesscut_path": self.query_one("#settings_losslesscut", Input).value.strip(),
                    },
                    naming={"year_folder_template": year_template},
                    workflow={"raw_archive_mode": str(raw_mode)},
                    vimeo={
                        "team_owner_user_id": self.app_config.vimeo.team_owner_user_id,
                        "target_folder_id": self.selected_vimeo_folder_id,
                        "target_folder_name": self.selected_vimeo_folder_name,
                    },
                )
                refreshed = load_config(saved_path)
            except ConfigLoadError as exc:
                self.notify(f"{exc.user_message} Admin-Hinweis: {exc.admin_hint}", severity="error")
                return
            self.app.app_config = refreshed
            self.app_config = refreshed
            self.notify("Die Einstellungen wurden gespeichert.")

        def _check_vimeo(self) -> None:
            result = self.query_one("#settings_vimeo_result", Static)
            result.update("Vimeo-Verbindung wird geprüft …")
            self.query_one("#settings_check_vimeo", Button).disabled = True

            def work() -> None:
                try:
                    service = make_vimeo_service(self.app_config)
                    preflight = service.preflight()
                    message = (
                        f"Vimeo-Verbindung: OK\nTeam: {preflight.team_owner_name}\n"
                        f"Zielordner: {preflight.folder.name}"
                    )
                    self.app.call_from_thread(self._finish_vimeo_check, message, False, preflight.team_owner_name)
                except Exception as exc:
                    if isinstance(exc, VimeoError):
                        message = exc.user_message
                        if exc.admin_hint and exc.admin_hint != exc.user_message:
                            message += f"\nAdmin-Hinweis: {exc.admin_hint}"
                    else:
                        message = str(exc)
                    self.app.call_from_thread(self._finish_vimeo_check, message, True, None)

            self.run_worker(work, thread=True, exclusive=True, group="settings-vimeo-check", exit_on_error=False)

        def _finish_vimeo_check(self, message: str, failed: bool, team_name: str | None = None) -> None:
            if not self.is_mounted:
                return
            result = self.query_one("#settings_vimeo_result", Static)
            result.update(message)
            result.set_classes("status-danger" if failed else "status-ok")
            if team_name:
                self.query_one("#settings_vimeo_team", Static).update(f"Team: {team_name}")
            self.query_one("#settings_check_vimeo", Button).disabled = False

    class PredigtUploaderTui(App[None]):
        CSS = """
        Screen {
            padding: 1 2;
        }
        #title {
            text-style: bold;
            margin-bottom: 1;
        }
        #screen_title {
            text-style: bold;
            margin-bottom: 1;
        }
        #screen_note {
            margin-bottom: 1;
        }
        #start_actions {
            width: 1fr;
            padding-right: 2;
        }
        #status_box {
            width: 1fr;
        }
        #form {
            width: 1fr;
            padding-right: 2;
        }
        #metadata_content {
            height: 1fr;
            min-height: 0;
        }
        #metadata_body {
            height: 1fr;
            min-height: 0;
        }
        #metadata_field_stack {
            height: auto;
            min-height: 0;
        }
        #metadata_form_pane {
            width: 1fr;
            min-height: 0;
            margin-right: 1;
        }
        #metadata_form_scroll, #metadata_preview_scroll {
            width: 1fr;
            height: 1fr;
            min-height: 0;
            overflow-y: auto;
        }
        #metadata_preview_scroll {
            padding: 1;
        }
        #speaker_suggestions {
            height: auto;
            max-height: 6;
            margin-bottom: 1;
        }
        #metadata_validation {
            margin-bottom: 1;
        }
        .metadata_section_heading {
            margin-top: 1;
            margin-bottom: 0;
            text-style: bold;
        }
        #metadata_basic_heading {
            margin-top: 0;
        }
        #metadata_scroll_hint_row {
            height: auto;
            min-height: 0;
            margin-top: 0;
            margin-bottom: 1;
            align: right middle;
        }
        .scroll-hint {
            color: $warning;
            text-style: bold;
            padding: 0 1;
            border: round $warning;
        }
        #preview_heading {
            text-style: bold;
            margin-bottom: 1;
        }
        #processing_plan_box {
            width: 1fr;
            margin-right: 1;
        }
        #processing_status_box {
            width: 1fr;
        }
        #processing_status_heading {
            text-style: bold;
            margin-bottom: 1;
        }
        #processing_actions {
            height: auto;
            margin-top: 1;
        }
        #target_folder_scroll, #processing_review_scroll, #vimeo_scroll, #completion_scroll {
            height: 1fr;
            min-height: 0;
        }
        #settings_scroll, #direct_vimeo_selection_scroll, #vimeo_library_scroll,
        #vimeo_folder_browser_scroll {
            height: 1fr;
            min-height: 0;
        }
        #settings_actions, #direct_vimeo_actions, #vimeo_library_actions,
        #vimeo_folder_browser_actions {
            height: auto;
            margin-top: 1;
        }
        #vimeo_library_table {
            height: 12;
            margin-bottom: 1;
        }
        #vimeo_folder_browser_table {
            height: 1fr;
            min-height: 6;
        }
        #vimeo_folder_create_dialog {
            width: 72;
            max-width: 94%;
            height: auto;
            border: heavy $accent;
            background: $surface;
            padding: 1 2;
        }
        #vimeo_library_details {
            height: auto;
        }
        #vimeo_available_actions {
            height: auto;
            margin-top: 1;
        }
        Button.available-action {
            border: heavy $success;
        }
        Button.newly-available-action {
            background: $success;
            color: $text;
            text-style: bold;
        }
        VimeoStopConfirmationScreen {
            align: center middle;
            background: $background 70%;
        }
        VimeoFolderCreateScreen {
            align: center middle;
            background: $background 70%;
        }
        #vimeo_stop_dialog {
            width: 76;
            max-width: 94%;
            height: auto;
            border: heavy $warning;
            background: $surface;
            padding: 1 2;
        }
        #vimeo_stop_title {
            text-style: bold;
            text-align: center;
            margin-bottom: 1;
        }
        #vimeo_stop_dialog_actions {
            height: auto;
            align-horizontal: center;
        }
        #direct_vimeo_table {
            height: 10;
        }
        #settings_speaker_table {
            height: 8;
        }
        .settings_heading {
            text-style: bold;
            margin-top: 1;
            margin-bottom: 1;
        }
        .settings_button_row {
            height: auto;
        }
        .settings_button_row > Button {
            width: 1fr;
            margin-right: 1;
        }
        #settings_select_vimeo_folder {
            width: 100%;
        }
        #target_folder_body {
            height: auto;
            min-height: 0;
        }
        #target_folder_body > Vertical {
            height: auto;
        }
        #processing_review_body {
            height: auto;
            min-height: 0;
        }
        #processing_review_body > Vertical, #output_rename_fields {
            height: auto;
        }
        #vimeo_body {
            height: auto;
            min-height: 0;
        }
        #vimeo_body > Vertical {
            width: 1fr;
            height: auto;
        }
        #vimeo_plan_box {
            margin-right: 1;
        }
        #vimeo_status_heading {
            text-style: bold;
            margin-bottom: 1;
        }
        #vimeo_progress {
            padding: 1;
        }
        #vimeo_upload_bar {
            height: auto;
            margin: 0 1;
        }
        #vimeo_upload_details {
            height: auto;
            color: $text-muted;
            margin: 0 1 1 1;
        }
        #vimeo_actions {
            height: auto;
            margin-top: 1;
        }
        #vimeo_actions > #vimeo_upload {
            width: 100%;
        }
        #metadata_actions, #target_folder_actions, #completion_actions {
            height: auto;
            margin-top: 1;
        }
        #target_folder_actions > Button, #processing_actions > Button {
            width: 100%;
        }
        .navigation_actions {
            height: auto;
        }
        .navigation_actions Button, #metadata_actions Button, #completion_actions Button {
            width: 1fr;
            margin-right: 1;
        }
        #file_actions Button, #losslesscut_actions Button, #export_detection_actions Button,
        #safety_actions Button {
            margin-right: 1;
        }
        .back_footnote {
            color: $text-muted;
            height: auto;
        }
        .workflow_progress {
            height: auto;
            color: $text-muted;
            margin-bottom: 1;
        }
        .panel-neutral, .panel-info, .panel-warning, .panel-danger {
            padding: 1;
            margin-bottom: 1;
        }
        .panel-neutral {
            border: solid #7f7f7f;
        }
        .panel-info {
            border: solid $accent;
        }
        .panel-warning {
            border: heavy $warning;
        }
        .panel-danger {
            border: heavy $error;
        }
        .status-ok, .status-info, .status-warning, .status-danger {
            padding: 1;
            margin-bottom: 1;
            text-style: bold;
        }
        .status-ok {
            border: solid $success;
        }
        .status-info {
            border: solid $accent;
        }
        .status-warning {
            border: heavy $warning;
        }
        .status-danger {
            border: heavy $error;
        }
        #completion_banner {
            margin-bottom: 1;
        }
        #target_folder_table {
            height: 8;
        }
        #processing_source_text, #processing_files_text, #processing_raw_action_text {
            margin-bottom: 1;
        }
        #target_conflict_decision {
            border: heavy $error;
            padding: 1;
            margin-bottom: 1;
            text-style: bold;
        }
        #conflict_back, #confirm_overwrite, #conflict_cancel {
            width: 100%;
            min-width: 42;
            margin-bottom: 1;
        }
        #confirm_overwrite {
            color: black;
            background: yellow;
            text-style: bold;
        }
        #workflow_note {
            border: solid $accent;
            padding: 1;
            margin-bottom: 1;
        }
        #safety_page {
            align: center middle;
            height: 1fr;
        }
        #safety_title {
            text-style: bold;
            text-align: center;
            width: 100%;
            border: heavy $error;
            padding: 1 2;
            margin-bottom: 1;
        }
        #safety_questions {
            text-style: bold;
            text-align: center;
            width: 100%;
            border: solid $warning;
            padding: 1 2;
            margin-bottom: 1;
        }
        #safety_warning {
            text-align: center;
            width: 64;
            border: heavy $warning;
            padding: 1 2;
            margin-bottom: 2;
        }
        #safety_actions {
            align-horizontal: center;
            height: auto;
        }
        #safety_actions Button {
            width: 34;
            margin: 0 1 1 1;
        }
        #file_actions {
            height: auto;
            margin-bottom: 1;
        }
        #file_table {
            height: 12;
            margin-bottom: 1;
        }
        Input, Select, Button {
            margin-bottom: 1;
        }
        """

        def __init__(self) -> None:
            super().__init__()
            self.app_config = config
            self.vimeo_library_cache: dict[tuple[str, str], VimeoLibraryResult] = {}
            self.vimeo_folder_catalog_cache: dict[str, VimeoFolderCatalog] = {}

        def on_mount(self) -> None:
            self.push_screen(StartScreen())

        def open_vimeo_publishing(
            self,
            plan: PreparedRecordingPlan,
            *,
            state_path: Path,
            opened_target_folder: bool,
            direct_mode: bool = False,
        ) -> None:
            self.push_screen(
                VimeoPublishingScreen(
                    self.app_config,
                    plan,
                    state_path=state_path,
                    opened_target_folder=opened_target_folder,
                    direct_mode=direct_mode,
                )
            )

    return PredigtUploaderTui()


def run_tui(config_path: str | None = None) -> int:
    build_tui_app(config_path).run()
    return 0


def _parse_date(value: str) -> date:
    return parse_tui_date_or_today(value)
