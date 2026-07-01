from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .filename import build_media_filename
from .folders import ensure_folder, suggest_folder
from .models import AppConfig, ProcessingPlan, SermonInfo
from .mp3 import Mp3ConversionError, convert_mp4_to_mp3, ffmpeg_available
from .report import summary_file_path, write_summary_file

RAW_ACTION_MOVE = "move"
RAW_ACTION_COPY = "copy"
RAW_ACTION_KEEP = "keep"
RAW_ACTION_NONE = "none"

MP4_ACTION_COPY = "copy"
MP4_ACTION_MOVE = "move"
MP4_ACTION_KEEP = "keep"
MP4_ACTION_OVERWRITE = "overwrite"

ProgressCallback = Callable[[str], None]
FolderOpener = Callable[[Path], None]
Mp3Converter = Callable[[Path, Path, AppConfig], None]
FfmpegAvailable = Callable[[AppConfig], bool]


@dataclass(frozen=True)
class PreparedRecordingPlan:
    source_mp4: Path
    raw_recording: Path | None
    target_folder: Path
    target_mp4: Path
    target_mp3: Path
    summary_path: Path
    info: SermonInfo
    raw_action: str = RAW_ACTION_NONE
    mp4_action: str = MP4_ACTION_COPY
    overwrite_existing_outputs: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def service_type(self) -> str:
        return self.info.sermon_type

    @property
    def sermon_date(self):
        return self.info.sermon_date

    @property
    def title(self) -> str:
        return self.info.title

    @property
    def bible_reference(self) -> str:
        return self.info.bible_reference

    @property
    def speaker(self) -> str:
        return self.info.speaker

    @property
    def folder_note(self) -> str:
        return self.info.folder_note

    @property
    def processing_plan(self) -> ProcessingPlan:
        return ProcessingPlan(
            source_mp4=self.source_mp4,
            target_mp4=self.target_mp4,
            target_mp3=self.target_mp3,
            info=self.info,
        )


@dataclass(frozen=True)
class ProcessingExecutionResult:
    success: bool
    messages: tuple[str, ...]
    error: str | None = None
    summary_path: Path | None = None
    archived_raw_recording: Path | None = None
    opened_target_folder: bool = False


def build_prepared_recording_plan(
    *,
    config: AppConfig,
    source_mp4: Path,
    info: SermonInfo,
    raw_recording: Path | None = None,
    raw_action: str | None = None,
    mp4_action: str | None = None,
    target_folder_override: Path | None = None,
    overwrite_existing_outputs: bool = False,
    warnings: tuple[str, ...] = (),
) -> PreparedRecordingPlan:
    target_folder = target_folder_override or suggest_folder(config, info)
    target_mp4 = target_folder / build_media_filename(info, config, ".mp4")
    target_mp3 = target_folder / build_media_filename(info, config, ".mp3")
    normalized_raw_action = raw_action or (config.raw_archive_mode if raw_recording is not None else RAW_ACTION_NONE)
    normalized_mp4_action = mp4_action or (MP4_ACTION_COPY if config.copy_instead_of_move else MP4_ACTION_MOVE)
    return PreparedRecordingPlan(
        source_mp4=source_mp4,
        raw_recording=raw_recording,
        target_folder=target_folder,
        target_mp4=target_mp4,
        target_mp3=target_mp3,
        summary_path=summary_file_path(target_folder),
        info=info,
        raw_action=normalize_raw_action(normalized_raw_action),
        mp4_action=normalized_mp4_action,
        overwrite_existing_outputs=overwrite_existing_outputs,
        warnings=tuple(warnings),
    )


def normalize_raw_action(action: str) -> str:
    normalized = action.strip().casefold()
    if normalized in {RAW_ACTION_MOVE, RAW_ACTION_COPY, RAW_ACTION_KEEP, RAW_ACTION_NONE}:
        return normalized
    return RAW_ACTION_NONE


def raw_action_label(action: str, raw_recording: Path | None = None) -> str:
    if raw_recording is None:
        return "keine Rohaufnahme"
    labels = {
        RAW_ACTION_MOVE: "Rohaufnahme in Zielordner verschieben",
        RAW_ACTION_COPY: "Rohaufnahme in Zielordner kopieren",
        RAW_ACTION_KEEP: "Rohaufnahme liegen lassen",
        RAW_ACTION_NONE: "Rohaufnahme liegen lassen",
    }
    return labels.get(normalize_raw_action(action), labels[RAW_ACTION_NONE])


def build_processing_plan_warnings(plan: PreparedRecordingPlan, config: AppConfig) -> tuple[str, ...]:
    warnings = list(plan.warnings)
    if not ffmpeg_available(config):
        warnings.append("FFmpeg wurde nicht gefunden. Die MP3 kann dann nicht automatisch erstellt werden.")
    if plan.raw_recording is not None and plan.raw_action == RAW_ACTION_MOVE:
        warnings.append("Beim Verschieben wird die Rohaufnahme aus dem Quellordner entfernt.")
    return tuple(dict.fromkeys(warnings))


def build_processing_plan_text(plan: PreparedRecordingPlan, config: AppConfig | None = None) -> str:
    warnings = build_processing_plan_warnings(plan, config) if config is not None else plan.warnings
    raw_text = str(plan.raw_recording) if plan.raw_recording is not None else "-"
    lines = [
        f"Diese Datei wird als finale Predigt verwendet: {plan.source_mp4}",
        f"Diese Rohaufnahme wird danach verschoben/kopiert/liegen gelassen: {raw_text}",
        f"Zielordner: {plan.target_folder}",
        f"MP4-Dateiname: {plan.target_mp4.name}",
        f"MP3-Dateiname: {plan.target_mp3.name}",
        f"Zusammenfassung: {plan.summary_path}",
        f"Rohaufnahme-Aktion: {raw_action_label(plan.raw_action, plan.raw_recording)}",
    ]
    if warnings:
        lines.append("")
        lines.append("Warnungen:")
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines)


def execute_processing_plan(
    plan: PreparedRecordingPlan,
    config: AppConfig,
    *,
    progress: ProgressCallback | None = None,
    folder_opener: FolderOpener | None = None,
    mp3_converter: Mp3Converter = convert_mp4_to_mp3,
    ffmpeg_checker: FfmpegAvailable = ffmpeg_available,
) -> ProcessingExecutionResult:
    messages: list[str] = []

    def emit(message: str) -> None:
        messages.append(message)
        if progress is not None:
            progress(message)

    try:
        emit("Zielordner wird erstellt/geprueft.")
        ensure_folder(plan.target_folder)
        _ensure_outputs_can_be_written(plan)

        emit(_mp4_status_message(plan.mp4_action, config))
        _transfer_mp4(plan, config)

        if ffmpeg_checker(config):
            emit("MP3 wird erstellt.")
            mp3_converter(plan.target_mp4, plan.target_mp3, config)
        else:
            emit("MP3 wurde uebersprungen: FFmpeg wurde nicht gefunden.")

        emit("Zusammenfassung wird geschrieben.")
        write_summary_file(plan.processing_plan)

        archived_raw = _execute_raw_action(plan, emit)

        opened = False
        if config.open_target_folder:
            emit("Zielordner wird geoeffnet.")
            try:
                _open_target_folder(plan.target_folder, folder_opener)
                opened = True
            except OSError as exc:
                emit(f"Zielordner konnte nicht automatisch geoeffnet werden: {exc}")

        emit("Fertig.")
        success = plan.target_mp3.exists() if ffmpeg_checker(config) else False
        return ProcessingExecutionResult(
            success=success,
            messages=tuple(messages),
            summary_path=plan.summary_path,
            archived_raw_recording=archived_raw,
            opened_target_folder=opened,
        )
    except (OSError, Mp3ConversionError) as exc:
        error = _user_facing_processing_error(exc)
        emit(f"Fehler: {error}")
        return ProcessingExecutionResult(False, tuple(messages), error=error)


def _mp4_status_message(mp4_action: str, config: AppConfig) -> str:
    if mp4_action == MP4_ACTION_KEEP:
        return "Vorhandene MP4 wird verwendet."
    if mp4_action == MP4_ACTION_MOVE or (mp4_action == MP4_ACTION_COPY and not config.copy_instead_of_move):
        return "MP4 wird verschoben."
    return "MP4 wird kopiert."


def _transfer_mp4(plan: PreparedRecordingPlan, config: AppConfig) -> None:
    if plan.mp4_action == MP4_ACTION_KEEP:
        if not plan.target_mp4.exists():
            raise FileNotFoundError(f"Vorhandene Zieldatei fehlt: {plan.target_mp4}")
        return
    if not plan.source_mp4.exists() or not plan.source_mp4.is_file():
        raise FileNotFoundError(f"Quell-MP4 wurde nicht gefunden: {plan.source_mp4}")
    if plan.target_mp4.exists() and plan.mp4_action != MP4_ACTION_OVERWRITE:
        raise FileExistsError(f"Zieldatei existiert bereits: {plan.target_mp4}")
    if plan.target_mp4.exists() and plan.mp4_action == MP4_ACTION_OVERWRITE:
        plan.target_mp4.unlink()
    if plan.mp4_action == MP4_ACTION_MOVE or (plan.mp4_action == MP4_ACTION_COPY and not config.copy_instead_of_move):
        shutil.move(str(plan.source_mp4), str(plan.target_mp4))
    else:
        shutil.copy2(plan.source_mp4, plan.target_mp4)


def _ensure_outputs_can_be_written(plan: PreparedRecordingPlan) -> None:
    if plan.target_mp4.exists() and plan.mp4_action not in {MP4_ACTION_OVERWRITE, MP4_ACTION_KEEP}:
        raise FileExistsError(f"Zieldatei existiert bereits: {plan.target_mp4}")
    if not plan.overwrite_existing_outputs:
        if plan.target_mp3.exists():
            raise FileExistsError(f"Ziel-MP3 existiert bereits: {plan.target_mp3}")
        if plan.summary_path.exists():
            raise FileExistsError(f"Zusammenfassung existiert bereits: {plan.summary_path}")


def _execute_raw_action(plan: PreparedRecordingPlan, emit: ProgressCallback) -> Path | None:
    if plan.raw_recording is None:
        emit("Keine Rohaufnahme-Aktion noetig.")
        return None
    raw_action = normalize_raw_action(plan.raw_action)
    if raw_action in {RAW_ACTION_NONE, RAW_ACTION_KEEP}:
        emit("Rohaufnahme bleibt am bisherigen Ort.")
        return None
    if not plan.raw_recording.exists() or not plan.raw_recording.is_file():
        raise FileNotFoundError(f"Rohaufnahme wurde nicht gefunden: {plan.raw_recording}")
    if _same_path(plan.raw_recording.parent, plan.target_folder):
        emit("Rohaufnahme liegt bereits im Zielordner.")
        return None

    target = _raw_target_path(plan.raw_recording, plan.target_folder)
    if raw_action == RAW_ACTION_MOVE:
        emit("Rohaufnahme wird verschoben.")
        shutil.move(str(plan.raw_recording), str(target))
        return target
    if raw_action == RAW_ACTION_COPY:
        emit("Rohaufnahme wird kopiert.")
        shutil.copy2(plan.raw_recording, target)
        return target
    return None


def _raw_target_path(raw_recording: Path, target_folder: Path) -> Path:
    target = target_folder / raw_recording.name
    if not target.exists():
        return target
    for index in range(1, 100):
        candidate = target_folder / f"{raw_recording.stem} ({index}){raw_recording.suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Kein freier Dateiname fuer Rohaufnahme gefunden: {target}")


def _open_target_folder(target_folder: Path, folder_opener: FolderOpener | None) -> None:
    if folder_opener is not None:
        folder_opener(target_folder)
        return
    try:
        os.startfile(target_folder)  # type: ignore[attr-defined]
    except AttributeError as exc:
        raise OSError("Explorer kann auf diesem System nicht automatisch geoeffnet werden.") from exc


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left.absolute() == right.absolute()


def _user_facing_processing_error(exc: OSError | Mp3ConversionError) -> str:
    if isinstance(exc, Mp3ConversionError):
        return "Die MP3 konnte nicht erstellt werden. Bitte pruefe FFmpeg und ob die MP4 noch in einem anderen Programm geoeffnet ist."
    if isinstance(exc, PermissionError):
        return "Eine Datei oder ein Ordner konnte wegen fehlender Berechtigungen nicht geschrieben werden."
    if isinstance(exc, FileExistsError):
        return "Eine Zieldatei existiert bereits. Bitte pruefe den Zielordner oder waehle einen anderen Namen."
    if isinstance(exc, FileNotFoundError):
        return "Eine benoetigte Datei wurde nicht gefunden."
    return "Die Dateien konnten nicht vollstaendig vorbereitet werden."
