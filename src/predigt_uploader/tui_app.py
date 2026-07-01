from __future__ import annotations

import subprocess
import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

from .config import default_service_types, load_config
from .filename import build_filename_preview, build_media_filename, service_type_config_for
from .folders import resolve_folder, suggest_folder
from .models import AppConfig, FolderResolution, ProcessingPlan, SermonInfo, ServiceTypeConfig
from .processing import (
    MP4_ACTION_COPY,
    MP4_ACTION_KEEP,
    MP4_ACTION_MOVE,
    MP4_ACTION_OVERWRITE,
    PreparedRecordingPlan,
    build_prepared_recording_plan,
    build_processing_plan_text,
    raw_action_label,
    execute_processing_plan,
)
from .report import summary_file_path

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


def load_tui_config(config_path: str | None = None) -> AppConfig:
    explicit_config = Path(config_path) if config_path else None
    return load_config(explicit_config)


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
    summary_path = summary_file_path(target_folder)
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
        summary_path=summary_file_path(target_folder),
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
        f"Jahresordner: {resolution.year_folder}",
        f"Datum: {resolution.date_prefix}",
        f"Vorgeschlagener Zielordner: {resolution.suggested_folder}",
        "",
    ]
    if resolution.status == "missing":
        lines.extend(
            [
                "Fuer dieses Datum gibt es noch keinen Ordner.",
                f"Dieser Ordner wird neu erstellt: {resolution.suggested_folder}",
            ]
        )
    elif resolution.status == "single_existing":
        lines.extend(
            [
                f"Fuer dieses Datum gibt es bereits diesen Ordner: {resolution.candidates[0]}",
                "Du kannst den vorhandenen Ordner verwenden oder einen neuen Ordner mit Besonderheit erstellen.",
            ]
        )
    else:
        lines.append("Fuer dieses Datum gibt es mehrere Ordner. Bitte waehle bewusst einen Zielordner.")
        lines.extend(f"- {candidate}" for candidate in resolution.candidates)
    return "\n".join(lines)


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
    return tuple(conflicts)


def build_tui_target_conflict_text(conflicts: tuple[TuiTargetConflict, ...]) -> str:
    if not conflicts:
        return "Keine bestehenden Zieldateien mit gleichem Namen gefunden."
    labels = {
        "mp4": "MP4",
        "mp3": "MP3",
        "summary": "Zusammenfassung",
    }
    lines = ["Vorhandene Zieldateien:"]
    lines.extend(f"- {labels.get(conflict.kind, conflict.kind)}: {conflict.path}" for conflict in conflicts)
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
        "Zielordner erneut oeffnen",
        "Neue Aufnahme vorbereiten",
        "Beenden",
    )


def apply_tui_overwrite_confirmation(plan: PreparedRecordingPlan) -> PreparedRecordingPlan:
    return replace(
        plan,
        mp4_action=MP4_ACTION_OVERWRITE,
        overwrite_existing_outputs=True,
    )


def build_tui_execute_button_state(
    plan: PreparedRecordingPlan,
    *,
    overwrite_confirmed: bool,
) -> tuple[str, bool]:
    conflicts = detect_tui_target_conflicts(plan)
    if conflicts and not overwrite_confirmed:
        return "Erst entscheiden: ersetzen oder zurückgehen", True
    if conflicts:
        return "Vorhandene Dateien ersetzen und finale Dateien erstellen", False
    return TUI_PROCESSING_EXECUTE_LABEL, False


def tui_processing_review_back_target() -> str:
    return "target-folder-review"


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
            "Experimentelle Oberfläche",
            "Produktiver Workflow: normaler Wizard",
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


def service_type_by_name(config: AppConfig, name: str) -> ServiceTypeConfig:
    normalized = name.casefold()
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


def build_tui_processing_started_status() -> str:
    return "Verarbeitung gestartet..."


def build_tui_processing_success_status(plan: PreparedRecordingPlan, *, opened_target_folder: bool = True) -> str:
    folder_status = (
        "Der Zielordner wurde geoeffnet."
        if opened_target_folder
        else "Der Zielordner konnte nicht automatisch geoeffnet werden. Bitte nutze den Button zum erneuten Oeffnen oder oeffne den Pfad manuell."
    )
    return "\n".join(
        [
            "Fertig. Die Dateien wurden vorbereitet.",
            folder_status,
            "Vorhandene Ziel-Dateien wurden ersetzt." if plan.overwrite_existing_outputs else "",
            "",
            f"Zielordner: {plan.target_folder}",
            f"Finale MP4: {plan.target_mp4}",
            f"Finale MP3: {plan.target_mp3}",
            f"Zusammenfassung: {plan.summary_path}",
            f"Rohaufnahme-Aktion: {raw_action_label(plan.raw_action, plan.raw_recording)}",
            "",
            "Bitte jetzt kontrollieren:",
            "- MP4 im Zielordner vorhanden?",
            "- MP3 im Zielordner vorhanden?",
            "- predigt-zusammenfassung.txt vorhanden?",
            "",
            "Danach manuell weiter:",
            "- MP4 zu Vimeo hochladen",
            "- MP3 in WordPress hochladen",
            "- Angaben aus predigt-zusammenfassung.txt in WordPress uebernehmen",
            "- Vimeo-Embed-Code spaeter in WordPress ergaenzen",
        ]
    ).replace("\n\n\n", "\n\n")


def build_tui_processing_ready_text(plan: PreparedRecordingPlan) -> str:
    return (
        "Beim Klick werden die MP4/MP3/Zusammenfassung im Zielordner erstellt. "
        "Falls eine Rohaufnahme ausgewaehlt wurde, wird sie gemaess Auswahl behandelt."
    )


def build_tui_processing_error_status(messages: tuple[str, ...], error: str) -> str:
    lines = list(messages)
    lines.extend(["", f"Fehler: {error}"])
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


def run_tui(config_path: str | None = None) -> int:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.screen import Screen
        from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Select, Static
    except ImportError as exc:
        raise ImportError("Textual ist nicht installiert.") from exc

    config = load_tui_config(config_path)

    class StartScreen(Screen[None]):
        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("PredigtUploader", id="title")
            with Horizontal():
                with Vertical(id="start_actions"):
                    yield Button("Neue Aufnahme vorbereiten", id="new", variant="primary")
                    yield Button("MP4-Dateien ansehen", id="files")
                    yield Button("Einstellungen", id="settings")
                    yield Button("Systemcheck-Hinweis", id="systemcheck")
                    yield Button("Beenden", id="quit")
                with Vertical(id="status_box"):
                    yield Static(build_tui_start_status_text(config), id="start_status")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "new":
                self.app.push_screen(StartSafetyScreen(config))
            elif event.button.id == "files":
                self.app.push_screen(FileCandidatesScreen(config))
            elif event.button.id == "settings":
                self.app.push_screen(SettingsScreen(config))
            elif event.button.id == "systemcheck":
                self.notify("Bitte PredigtUploader Systemcheck.cmd ausführen.")
            elif event.button.id == "quit":
                self.app.exit()

    class StartSafetyScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            with Vertical(id="safety_page"):
                yield Static(TUI_START_SAFETY_TITLE, id="safety_title")
                yield Static("\n".join(TUI_START_SAFETY_QUESTIONS), id="safety_questions")
                yield Static(TUI_START_SAFETY_WARNING, id="safety_warning")
                with Horizontal(id="safety_actions"):
                    yield Button(TUI_START_SAFETY_CANCEL_LABEL, id="cancel", variant="error")
                    yield Button(TUI_START_SAFETY_CONFIRM_LABEL, id="confirm", variant="primary")
            yield Footer()

        def on_mount(self) -> None:
            self.query_one("#cancel", Button).focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
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
            yield Static("Neue Aufnahme vorbereiten", id="screen_title")
            yield Static(
                "Textual sammelt Quelle und Metadaten. Die Verarbeitung laeuft weiterhin im normalen Wizard.",
                id="screen_note",
            )
            yield Button("Ja, fertig geschnittene MP4 auswaehlen", id="cut", variant="primary")
            yield Button("Nein, Rohaufnahme auswaehlen", id="raw")
            yield Button("Abbrechen", id="cancel")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            route = tui_source_choice_route(event.button.id)
            if route == "cut-selection":
                self.app.push_screen(FileSelectionScreen(self.app_config, already_cut=True))
            elif route == "raw-selection":
                self.app.push_screen(FileSelectionScreen(self.app_config, already_cut=False))
            elif route == "start":
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
            yield Static(self.selection.title, id="screen_title")
            yield Static(self.selection.note, id="screen_note")
            yield Static(f"Ordner: {self.source_folder}", id="source_folder")
            with Horizontal(id="file_actions"):
                if self.selection.suggest_newest:
                    newest_label = "Neueste geschnittene MP4 verwenden" if self.already_cut else "Neueste Aufnahme verwenden"
                    yield Button(newest_label, id="newest", variant="primary")
                yield Button("Ausgewaehlte Datei verwenden", id="select")
                yield Button("Zurueck", id="back")
                yield Button("Abbrechen", id="cancel")
            if self.selection.allow_search:
                yield Input(placeholder="Dateiname suchen oder filtern", id="file_search")
            yield Static("Neueste MP4-Dateien", id="file_table_heading")
            yield DataTable(id="file_table")
            if self.selection.allow_manual_input:
                yield Input(placeholder="Datei oder Ordner manuell eingeben", id="manual_path")
                yield Button("Manuellen Pfad verwenden", id="manual")
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
            yield Static("Rohaufnahme schneiden", id="screen_title")
            yield Static(build_tui_losslesscut_text(self.raw_recording, self.app_config), id="losslesscut_note")
            with Horizontal(id="losslesscut_actions"):
                yield Button("LosslessCut oeffnen", id="open", variant="primary")
                yield Button("Exportierte MP4 suchen", id="next")
                yield Button("Zurueck", id="back")
                yield Button("Abbrechen", id="cancel")
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
            title = "Vermutlich exportierte Schnittdatei gefunden" if self.candidates else "Exportierte MP4 manuell auswaehlen"
            yield Static(title, id="screen_title")
            yield Static(build_tui_export_detection_text(self.candidates), id="screen_note")
            if self.candidates:
                yield DataTable(id="export_candidate_table")
            with Horizontal(id="export_detection_actions"):
                if self.candidates:
                    action_label = "Diese Datei verwenden" if len(self.candidates) == 1 else "Ausgewaehlte Datei verwenden"
                    yield Button(action_label, id="use", variant="primary")
                    yield Button("Andere MP4 auswaehlen", id="manual")
                else:
                    yield Button("MP4 manuell auswaehlen", id="manual", variant="primary")
                yield Button("Zurueck", id="back")
                yield Button("Abbrechen", id="cancel")
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
            service_names = [(service.name, service.name) for service in service_types_for_tui(self.app_config)]
            default_service = default_tui_service_type_name(self.app_config, preferred_date.value)
            yield Static("Metadaten erfassen", id="screen_title")
            yield Static(
                "Textual bereitet einen Verarbeitungsplan vor. Der normale Wizard bleibt produktiver Standard.",
                id="screen_note",
            )
            with Horizontal():
                with Vertical(id="form"):
                    yield Label("Dienstart")
                    yield Select(service_names, value=default_service, id="service_type")
                    yield Label("Datum", id="date_label")
                    yield Select([(option.label, option.kind) for option in date_options], value=preferred_date.kind, id="date_choice")
                    yield Input(value=preferred_date.value.isoformat(), placeholder="YYYY-MM-DD", id="sermon_date")
                    yield Label("Titel", id="title_label")
                    yield Input(placeholder="Titel oder Thema", id="title_input")
                    yield Label("Hauptbibelstelle", id="bible_label")
                    yield Input(placeholder="Bibelstelle", id="bible_input")
                    yield Label("Redner / Leitung", id="speaker_label")
                    yield Input(placeholder="Redner oder Leitung", id="speaker_input")
                    yield Label("Besonderheit im Ordner")
                    yield Input(placeholder="optional, z. B. Taufe oder Gastredner", id="folder_note_input")
                    yield Static(
                        "Der vollständige Workflow läuft weiterhin im normalen Wizard.",
                        id="workflow_note",
                    )
                    yield Button("Zurueck", id="back")
                    yield Button("Abbrechen", id="cancel")
                    yield Button("Metadaten pruefen", id="next", variant="primary")
                with Vertical(id="preview_box"):
                    yield Label("Live-Vorschau", id="preview_heading")
                    yield Static("", id="filename_preview")
                    yield Static("", id="validation_status")
                    yield Static("", id="source_status")
            yield Footer()

        def on_mount(self) -> None:
            self._update_preview()

        def on_input_changed(self, _event: Input.Changed) -> None:
            if _event.input.id == "sermon_date":
                self._sync_service_type_for_date()
            self._update_preview()

        def on_select_changed(self, _event: Select.Changed) -> None:
            if _event.select.id == "service_type" and not self._syncing_service_type:
                self.service_type_manually_changed = True
            elif _event.select.id == "date_choice":
                self._sync_date_input_to_choice()
                self._sync_service_type_for_date()
            self._update_preview()

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
            source_widget.update(self._source_hint())
            self.query_one("#next", Button).disabled = bool(messages)

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

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("Zielordner pruefen", id="screen_title")
            yield Static(
                "Ordner und Zieldateien werden getrennt geprueft. Ein vorhandener Ordner ist erlaubt, vorhandene Dateien brauchen spaeter eine bewusste Entscheidung.",
                id="screen_note",
            )
            with Horizontal():
                with Vertical(id="processing_plan_box"):
                    yield Static(build_tui_target_folder_review_text(self.resolution), id="target_folder_review_text")
                    if self.resolution.status == "multiple_existing":
                        yield DataTable(id="target_folder_table")
                    if self.resolution.status != "missing":
                        yield Label("Besonderheit fuer neuen Ordner")
                        yield Input(value=self.info.folder_note, placeholder="z. B. Test oder Gastredner", id="folder_note_override")
                with Vertical(id="processing_status_box"):
                    yield Label("Was passiert?", id="processing_status_heading")
                    yield Static(self._action_hint(), id="target_folder_action_hint")
            with Horizontal(id="processing_actions"):
                yield Button("Vorhandenen Ordner verwenden / Dateien dort hinzufuegen", id="use_existing")
                yield Button("Neuen Ordner mit Besonderheit erstellen", id="create_with_note")
                yield Button("Weiter zur finalen Pruefung", id="continue", variant="primary")
                yield Button("Zurueck zu Metadaten", id="back")
                yield Button("Abbrechen", id="cancel")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one("#target_folder_table", DataTable) if self.resolution.status == "multiple_existing" else None
            if table is not None:
                table.add_columns("Ordner")
                for candidate in self.resolution.candidates:
                    table.add_row(str(candidate), key=str(candidate))
                table.cursor_type = "row"
            if self.resolution.status == "missing":
                self.query_one("#use_existing", Button).disabled = True
                self.query_one("#create_with_note", Button).disabled = True
            elif self.resolution.status == "single_existing":
                self.query_one("#continue", Button).disabled = True
            else:
                self.query_one("#continue", Button).disabled = True

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            self.selected_existing_folder = Path(str(event.row_key.value))
            self.query_one("#target_folder_action_hint", Static).update(
                f"Ausgewaehlter vorhandener Ordner:\n{self.selected_existing_folder}"
            )

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()
                return
            if event.button.id == "cancel":
                self._return_to_start()
                return
            if event.button.id == "continue":
                self._open_processing_review(self.resolution.suggested_folder, self.info)
                return
            if event.button.id == "use_existing":
                folder = self.selected_existing_folder or (self.resolution.candidates[0] if self.resolution.candidates else None)
                if folder is None:
                    self.notify("Bitte zuerst einen vorhandenen Ordner auswaehlen.")
                    return
                self._open_processing_review(folder, self.info)
                return
            if event.button.id == "create_with_note":
                note = self.query_one("#folder_note_override", Input).value.strip()
                if not note:
                    self.notify("Bitte eine Besonderheit fuer den neuen Ordner eingeben.")
                    return
                info = build_tui_info_with_folder_note(self.info, note)
                self._open_processing_review(suggest_folder(self.app_config, info), info)

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
                        target_folder_override=target_folder,
                    ),
                )
            )

        def _action_hint(self) -> str:
            if self.resolution.status == "missing":
                return "Der vorgeschlagene Zielordner wird neu erstellt."
            if self.resolution.status == "single_existing":
                return "Waehle bewusst, ob der vorhandene Tagesordner genutzt oder ein neuer Ordner mit Besonderheit erstellt wird."
            return "Waehle einen vorhandenen Ordner aus der Tabelle oder erstelle ueber eine Besonderheit einen neuen Ordner."

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

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("Vorbereitung pruefen", id="screen_title")
            yield Static(
                "Bitte pruefe Quelle, Zielordner und Dateinamen. Erst der Button unten schreibt Dateien.",
                id="screen_note",
            )
            with Horizontal():
                with Vertical(id="processing_plan_box"):
                    yield Static(build_tui_target_folder_status_text(self.plan), id="target_folder_status")
                    yield Static(build_processing_plan_text(self.plan, self.app_config), id="processing_plan_text")
                    yield Static(build_tui_target_conflict_text(detect_tui_target_conflicts(self.plan)), id="target_conflict_text")
                    if self.plan.raw_recording is not None:
                        yield Label("Was soll mit der urspruenglichen Rohaufnahme passieren?")
                        yield Select(
                            [
                                ("Rohaufnahme in Zielordner verschieben (empfohlen)", "move"),
                                ("Rohaufnahme in Zielordner kopieren", "copy"),
                                ("Rohaufnahme in vMixStorage liegen lassen", "none"),
                            ],
                            value=self.plan.raw_action,
                            id="raw_action",
                        )
                    yield Static(build_tui_processing_review_action_text(self.plan), id="processing_action_text")
                with Vertical(id="processing_status_box"):
                    yield Label("Status", id="processing_status_heading")
                    if detect_tui_target_conflicts(self.plan):
                        conflict_back_label, confirm_overwrite_label, conflict_cancel_label = tui_conflict_action_labels()
                        yield Static(
                            build_tui_target_conflict_decision_text(detect_tui_target_conflicts(self.plan)),
                            id="target_conflict_decision",
                        )
                        yield Button(
                            conflict_back_label,
                            id="conflict_back",
                        )
                        yield Button(
                            confirm_overwrite_label,
                            id="confirm_overwrite",
                            variant="warning",
                        )
                        yield Button(conflict_cancel_label, id="conflict_cancel")
                    else:
                        yield Static(build_tui_processing_ready_text(self.plan), id="processing_ready_text")
                    yield Static("Noch nicht gestartet.", id="processing_status")
            with Horizontal(id="processing_actions"):
                yield Button("Zurueck", id="back")
                yield Button("Abbrechen", id="cancel")
                yield Button(TUI_PROCESSING_EXECUTE_LABEL, id="execute", variant="primary")
            with Horizontal(id="processing_finished_actions"):
                open_label, new_label, quit_label = tui_processing_finished_action_labels()
                yield Button(open_label, id="open_target", disabled=True)
                yield Button(new_label, id="new_recording")
                yield Button(quit_label, id="quit")
            yield Footer()

        def on_mount(self) -> None:
            self._sync_execute_button()

        def on_select_changed(self, event: Select.Changed) -> None:
            if event.select.id == "raw_action":
                self.plan = replace(self.plan, raw_action=str(event.value))
                self.query_one("#processing_plan_text", Static).update(build_processing_plan_text(self.plan, self.app_config))
                self.query_one("#processing_action_text", Static).update(build_tui_processing_review_action_text(self.plan))
            elif event.select.id == "conflict_action":
                self.overwrite_confirmed = event.value == "overwrite"
                if self.overwrite_confirmed:
                    self.plan = apply_tui_overwrite_confirmation(self.plan)
                self.query_one("#processing_action_text", Static).update(build_tui_processing_review_action_text(self.plan))
            self._sync_execute_button()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id in {"back", "conflict_back"}:
                self.app.pop_screen()
                return
            if event.button.id in {"cancel", "conflict_cancel"}:
                self._return_to_start()
                return
            if event.button.id == "confirm_overwrite":
                self.overwrite_confirmed = True
                self.plan = apply_tui_overwrite_confirmation(self.plan)
                self.query_one("#processing_plan_text", Static).update(build_processing_plan_text(self.plan, self.app_config))
                self.query_one("#processing_action_text", Static).update(build_tui_processing_review_action_text(self.plan))
                self.query_one("#target_conflict_decision", Static).update(build_tui_overwrite_confirmed_text())
                self.query_one("#processing_status", Static).update("Bereit zum Ersetzen.")
                self._sync_execute_button()
                return
            if event.button.id == "execute":
                if detect_tui_target_conflicts(self.plan) and not self.overwrite_confirmed:
                    self.notify("Bitte zuerst bewusst entscheiden, ob vorhandene Dateien ersetzt werden sollen.")
                    return
                if self.overwrite_confirmed:
                    self.plan = apply_tui_overwrite_confirmation(self.plan)
                event.button.disabled = True
                event.button.label = TUI_PROCESSING_RUNNING_LABEL
                self.query_one("#processing_status", Static).update(build_tui_processing_started_status())
                self.set_timer(0.1, self._execute_plan)
                return
            if event.button.id == "open_target":
                self._open_target_folder_again()
                return
            if event.button.id == "new_recording":
                self._return_to_start()
                self.app.push_screen(SourceChoiceScreen(self.app_config))
                return
            if event.button.id == "quit":
                self.app.exit()

        def _sync_execute_button(self) -> None:
            button = self.query_one("#execute", Button)
            label, disabled = build_tui_execute_button_state(
                self.plan,
                overwrite_confirmed=self.overwrite_confirmed,
            )
            button.disabled = disabled
            button.label = label

        def _execute_plan(self) -> None:
            status_widget = self.query_one("#processing_status", Static)
            status_lines: list[str] = [build_tui_processing_started_status()]

            def append_status(message: str) -> None:
                status_lines.append(message)
                status_widget.update("\n".join(status_lines))

            try:
                result = execute_processing_plan(self.plan, self.app_config, progress=append_status)
            except Exception as exc:
                self.query_one("#execute", Button).disabled = False
                self.query_one("#execute", Button).label = TUI_PROCESSING_EXECUTE_LABEL
                status_widget.update(build_tui_processing_error_status(tuple(status_lines), f"{type(exc).__name__}: {exc}"))
                self.notify("Die Vorbereitung ist mit einem Fehler abgebrochen.", severity="error")
                return

            if result.success:
                self._hide_conflict_controls_after_success()
                status_widget.update(
                    build_tui_processing_success_status(self.plan, opened_target_folder=result.opened_target_folder)
                )
                self.query_one("#execute", Button).disabled = True
                self.query_one("#execute", Button).label = TUI_PROCESSING_DONE_LABEL
                self.query_one("#open_target", Button).disabled = False
                self.notify("Dateien wurden vorbereitet.")
                return

            self.query_one("#execute", Button).disabled = False
            self.query_one("#execute", Button).label = TUI_PROCESSING_EXECUTE_LABEL
            error = result.error or "Die Vorbereitung ist nicht vollstaendig abgeschlossen."
            status_widget.update(build_tui_processing_error_status(result.messages, error))
            self.notify(error, severity="error")

        def _hide_conflict_controls_after_success(self) -> None:
            for selector in ("#target_conflict_decision", "#conflict_back", "#confirm_overwrite", "#conflict_cancel"):
                try:
                    widget = self.query_one(selector)
                except Exception:
                    continue
                widget.display = False

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

    class SettingsScreen(Screen[None]):
        def __init__(self, app_config: AppConfig) -> None:
            super().__init__()
            self.app_config = app_config

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static("Einstellungen", id="screen_title")
            yield Static(
                "Nur Anzeige im Prototyp. Ändern bitte weiterhin über den normalen Wizard.",
                id="screen_note",
            )
            for line in build_tui_settings_lines(self.app_config):
                yield Static(line)
            yield Button("Zurück", id="back")
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()

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
            border: solid $accent;
            padding: 1;
        }
        #form {
            width: 1fr;
            padding-right: 2;
        }
        #preview_box {
            width: 1fr;
            border: solid $accent;
            padding: 1;
        }
        #preview_heading {
            text-style: bold;
            margin-bottom: 1;
        }
        #processing_plan_box {
            width: 1fr;
            border: solid $accent;
            padding: 1;
            margin-right: 1;
        }
        #processing_status_box {
            width: 1fr;
            border: solid $warning;
            padding: 1;
        }
        #processing_status_heading {
            text-style: bold;
            margin-bottom: 1;
        }
        #processing_actions {
            height: auto;
            margin-top: 1;
        }
        #processing_finished_actions {
            height: auto;
            margin-top: 1;
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

        def on_mount(self) -> None:
            self.push_screen(StartScreen())

    PredigtUploaderTui().run()
    return 0


def _parse_date(value: str) -> date:
    return parse_tui_date_or_today(value)
