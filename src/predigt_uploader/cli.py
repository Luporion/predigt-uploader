from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from .config import ConfigLoadError, default_service_types, describe_config_source, load_config, save_user_config_values, user_config_path
from .filename import build_filename_preview, build_media_filename, sanitize_filename_part, service_type_config_for
from .folders import ensure_folder, resolve_folder
from .models import AppConfig, ProcessingPlan, SermonInfo, ServiceTypeConfig
from .mp3 import Mp3ConversionError, convert_mp4_to_mp3, ffmpeg_available
from .report import build_summary_text, write_summary_file
from .run_log import WorkflowLog
from .ui import BACK, MenuOption, UserAbortError, ask_file_path, ask_yes_no, choose_from_options, search_from_options


class Mp4TransferError(RuntimeError):
    def __init__(self, user_message: str, admin_hint: str) -> None:
        super().__init__(admin_hint)
        self.user_message = user_message
        self.admin_hint = admin_hint


class Mp3ResultError(RuntimeError):
    def __init__(self, user_message: str, admin_hint: str) -> None:
        super().__init__(admin_hint)
        self.user_message = user_message
        self.admin_hint = admin_hint


class SummaryWriteError(RuntimeError):
    def __init__(self, admin_hint: str) -> None:
        super().__init__(admin_hint)
        self.admin_hint = admin_hint


class LosslessCutStartError(RuntimeError):
    def __init__(self, user_message: str, admin_hint: str) -> None:
        super().__init__(admin_hint)
        self.user_message = user_message
        self.admin_hint = admin_hint


class TargetFolderOpenError(RuntimeError):
    def __init__(self, admin_hint: str) -> None:
        super().__init__(admin_hint)
        self.admin_hint = admin_hint


class RawRecordingArchiveError(RuntimeError):
    def __init__(self, user_message: str, admin_hint: str) -> None:
        super().__init__(admin_hint)
        self.user_message = user_message
        self.admin_hint = admin_hint


MP4_TRANSFER_COPY = "copy"
MP4_TRANSFER_KEEP = "keep"
MP4_TRANSFER_OVERWRITE = "overwrite"
Mp4TransferMode = str
RAW_ARCHIVE_NONE = "none"
RAW_ARCHIVE_MOVE = "move"
RAW_ARCHIVE_COPY = "copy"
RawArchiveMode = str
RECENT_MP4_LIMIT = 15
SEARCH_RESULT_LIMIT = 15


@dataclass(frozen=True)
class Mp4FileSnapshot:
    path: Path
    size: int
    modified_at: float
    created_at: float


def _ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or (default or "")


def _ask_required(prompt: str) -> str:
    while True:
        value = _ask(prompt)
        if value:
            return value
        print("Bitte etwas eingeben. Dieses Feld darf nicht leer bleiben.")


def _ask_yes_no(prompt: str, default: bool = False) -> bool:
    return ask_yes_no(prompt, default)


def _remember_path_setting(section_key: str, path: Path, prompt: str, log: WorkflowLog | None = None) -> None:
    if not _ask_yes_no(prompt, False):
        return
    try:
        saved_path = save_user_config_values(paths={section_key: str(path)})
    except ConfigLoadError as exc:
        print("Die Einstellung konnte nicht gespeichert werden.")
        print(f"Admin-Hinweis: {exc.admin_hint}")
        if log is not None:
            log.error("Einstellung konnte nicht gespeichert werden.", admin_hint=exc.admin_hint)
        return
    print(f"Einstellung gespeichert: {saved_path}")
    if log is not None:
        log.event(f"Einstellung gespeichert: {section_key}={path}")


def _path_has_windows_invalid_chars(path: Path) -> bool:
    invalid_chars = set('<>"|?*')
    parts_to_check = [part for part in path.parts if part not in {path.drive, path.root, path.anchor}]
    for part in parts_to_check:
        if ":" in part or any(char in invalid_chars for char in part):
            return True
    return False


def _normalize_folder_path(raw_path: str) -> Path:
    cleaned = raw_path.strip().strip('"')
    if not cleaned:
        raise ValueError("leer")
    path = Path(cleaned).expanduser()
    if _path_has_windows_invalid_chars(path):
        raise ValueError("ungueltige Windows-Zeichen")
    return path


def _prepare_recordings_base(path: Path) -> bool:
    try:
        if path.exists() and not path.is_dir():
            raise Mp4TransferError(
                "Der Ziel-Basisordner ist kein Ordner, sondern eine Datei.",
                f"Ziel-Basisordner ist Datei statt Ordner: {path}",
            )

        if not path.exists():
            print("Dieser Ordner existiert noch nicht:")
            print(path)
            if not _ask_yes_no("Ordner erstellen?", True):
                print("Okay, dann bitte einen anderen Ziel-Basisordner angeben.")
                return False
            ensure_folder(path)

        _check_target_folder_writable(path)
        return True
    except PermissionError as exc:
        raise Mp4TransferError(
            "Der Ziel-Basisordner konnte wegen fehlender Berechtigungen nicht verwendet werden.",
            f"Keine Berechtigung fuer Ziel-Basisordner: {path}. Details: {exc}",
        ) from exc
    except Mp4TransferError:
        raise
    except OSError as exc:
        raise Mp4TransferError(
            "Der Ziel-Basisordner konnte nicht erstellt oder beschrieben werden.",
            f"Ziel-Basisordner konnte nicht vorbereitet werden: {path}. Details: {exc}",
        ) from exc


def _ask_recordings_base_path() -> Path:
    while True:
        raw = _ask_required("Anderer Ziel-Basisordner")
        try:
            return _normalize_folder_path(raw)
        except ValueError:
            print("Dieser Pfad ist nicht gültig. Bitte einen vollständigen Ordnerpfad ohne Sonderzeichen wie < > : \" | ? * eingeben.")


def _ask_initial_recordings_base_path(suggested_path: Path) -> Path:
    while True:
        raw = _ask("Drücke Enter, um diesen Ordner zu verwenden, oder gib einen anderen Ordner ein")
        if not raw:
            return suggested_path
        try:
            return _normalize_folder_path(raw)
        except ValueError:
            print("Dieser Pfad ist nicht gültig. Bitte einen vollständigen Ordnerpfad ohne Sonderzeichen wie < > : \" | ? * eingeben.")


def _select_recordings_base(config: AppConfig) -> AppConfig:
    print()
    print("Ziel-Basisordner")
    print("In diesem Ordner legt der Wizard später Jahres- und Datumsordner an.")
    print(f"Vorschlag: {config.recordings_base}")

    suggested_path = config.recordings_base
    current_path = _ask_initial_recordings_base_path(suggested_path)

    while True:
        try:
            if _prepare_recordings_base(current_path):
                print(f"Ziel-Basisordner ist bereit: {current_path}")
                if current_path != suggested_path:
                    _remember_path_setting("recordings_base", current_path, "Diesen Ziel-Basisordner künftig merken?")
                return replace(config, recordings_base=current_path)
            current_path = _ask_recordings_base_path()
        except Mp4TransferError as exc:
            print(exc.user_message)
            print("Bitte einen anderen Ziel-Basisordner wählen, auf den du Schreibzugriff hast.")
            print(f"Admin-Hinweis: {exc.admin_hint}")
            current_path = _ask_recordings_base_path()


def _ask_choice(prompt: str, choices: dict[str, str], default: str | None = None) -> str:
    choices_text = "/".join(choices)
    while True:
        raw = _ask(f"{prompt} ({choices_text})", default).casefold()
        for key, label in choices.items():
            if raw in {key, label.casefold()}:
                return key
        print("Bitte eine der angezeigten Optionen eingeben.")


def _show_wait_status(message: str) -> None:
    print(f"{message} Bitte warten ...")


GERMAN_MONTHS = {
    "januar": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "märz": 3,
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


def _format_german_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _detect_recording_date_from_filename(path: Path) -> date | None:
    name = path.stem
    match = re.search(r"\b(\d{1,2})\s+([A-Za-zÄÖÜäöüß]+)\s+(\d{4})\b", name)
    if match is None:
        return None

    day = int(match.group(1))
    month_name = match.group(2).casefold().replace("ä", "ae")
    year = int(match.group(3))
    month = GERMAN_MONTHS.get(month_name)
    if month is None:
        return None

    try:
        return date(year, month, day)
    except ValueError:
        return None


def _file_modified_date(path: Path) -> date | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date()
    except OSError:
        return None


def _ask_date() -> date:
    while True:
        raw = _ask("Datum der Aufnahme (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d"))
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            print("Bitte Datum im Format YYYY-MM-DD eingeben, z. B. 2026-05-24.")


def _ask_sermon_date(source_mp4: Path) -> date:
    recording_date = _detect_recording_date_from_filename(source_mp4)
    file_date = None if recording_date is not None else _file_modified_date(source_mp4)
    today = datetime.now().date()

    options: list[MenuOption[str]] = []
    if recording_date is not None:
        options.append(
            MenuOption(
                f"Aufnahmedatum aus Dateiname: {_format_german_date(recording_date)}",
                "recording",
            )
        )
    elif file_date is not None:
        options.append(
            MenuOption(
                f"Dateidatum der MP4: {_format_german_date(file_date)}",
                "filedate",
            )
        )
    options.append(MenuOption(f"Heutiges Datum: {_format_german_date(today)}", "today"))
    options.append(MenuOption("Anderes Datum manuell eingeben", "manual"))

    print()
    print("Datum der Aufnahme auswählen")
    print("Wenn das vorgeschlagene Datum nicht stimmt, wähle bitte ein anderes Datum.")
    selected = choose_from_options("Welches Datum soll verwendet werden?", options)
    if selected == "recording" and recording_date is not None:
        return recording_date
    if selected == "filedate" and file_date is not None:
        return file_date
    if selected == "today":
        return today
    return _ask_date()


def _normalize_user_path(raw_path: str) -> Path:
    return Path(raw_path.strip().strip('"')).expanduser()


def _ask_mp4_path() -> Path:
    return ask_file_path(
        "Pfad zur geschnittenen MP4-Datei",
        extensions=(".mp4",),
        file_description="MP4-Dateien",
    )


def _is_valid_mp4_file(path: Path) -> bool:
    if not path.exists():
        print("Diese Datei wurde nicht gefunden. Bitte den vollständigen Pfad zur MP4 einfügen.")
        return False
    if not path.is_file():
        print("Das ist ein Ordner, keine Datei. Bitte eine MP4-Datei auswählen.")
        return False
    if path.suffix.casefold() != ".mp4":
        print("Diese Datei ist keine MP4-Datei. Bitte eine Datei mit der Endung .mp4 auswählen.")
        return False
    return True


def _ask_mp4_path_with_prompt(prompt: str) -> Path:
    return ask_file_path(
        prompt,
        extensions=(".mp4",),
        file_description="MP4-Dateien",
    )


def _newest_mp4_in_folder(folder: Path) -> Path | None:
    if not folder.exists() or not folder.is_dir():
        return None
    candidates = list(_mp4_files_sorted(folder))
    if not candidates:
        return None
    return candidates[0]


def _looks_like_cut_or_final_mp4(path: Path) -> bool:
    name = path.name.casefold().replace(" ", "")
    stem = path.stem.casefold()
    return (
        "_geschnitten" in stem
        or "geschnitten" in stem
        or "predigt(" in name
        or name.startswith("predigt_")
        or name.startswith("predigt-")
    )


def _looks_like_final_sermon_mp4(path: Path) -> bool:
    name = path.name.casefold()
    compact = name.replace(" ", "")
    return (
        path.suffix.casefold() == ".mp4"
        and (
            re.match(r"^predigt\s*\(.+\)_.+\.mp4$", name) is not None
            or re.match(r"^bibelstunde\s*\(.+\)_.+\.mp4$", name) is not None
            or compact.startswith("predigt(")
        )
    )


def _cut_mp4_sort_key(path: Path) -> tuple[int, float]:
    stem = path.stem.casefold()
    if "_geschnitten" in stem:
        priority = 0
    elif "geschnitten" in stem:
        priority = 1
    elif _looks_like_final_sermon_mp4(path):
        priority = 2
    else:
        priority = 3
    return priority, -path.stat().st_mtime


def _cut_mp4_candidates_sorted(folder: Path) -> tuple[Path, ...]:
    return tuple(sorted(_mp4_files_sorted(folder), key=_cut_mp4_sort_key))


def _looks_like_vmix_raw_recording(path: Path) -> bool:
    stem = path.stem.casefold()
    return bool(re.search(r"\b\d{1,2}\s+[a-zäöüß]+\s+\d{4}\b", stem)) and "gottesdienst" in stem


def _raw_recording_sort_key(path: Path) -> tuple[int, float]:
    if _looks_like_cut_or_final_mp4(path):
        priority = 2
    elif _looks_like_vmix_raw_recording(path):
        priority = 0
    else:
        priority = 1
    return priority, -path.stat().st_mtime


def _raw_recording_candidates_sorted(folder: Path) -> tuple[Path, ...]:
    return tuple(sorted(_mp4_files_sorted(folder), key=_raw_recording_sort_key))


def _newest_raw_recording_candidate(folder: Path) -> Path | None:
    candidates = _raw_recording_candidates_sorted(folder)
    if not candidates:
        return None
    return candidates[0]


def _format_file_choice(path: Path) -> str:
    try:
        stat = path.stat()
        changed = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        size_mb = stat.st_size / (1024 * 1024)
        return f"{path.name} | geändert: {changed} | Größe: {size_mb:.1f} MB"
    except OSError:
        return path.name


def _mp4_files_sorted(folder: Path) -> tuple[Path, ...]:
    if not folder.exists() or not folder.is_dir():
        return ()
    files = [path for path in folder.glob("*.mp4") if path.is_file()]
    return tuple(sorted(files, key=lambda path: path.stat().st_mtime, reverse=True))


def _limit_file_list(files: tuple[Path, ...], limit: int) -> tuple[Path, ...]:
    return files[:limit]


def _search_mp4_files(folder: Path, search_text: str, *, limit: int = SEARCH_RESULT_LIMIT) -> tuple[Path, ...]:
    normalized = search_text.strip().casefold()
    if not normalized:
        return _limit_file_list(_mp4_files_sorted(folder), limit)
    matches = tuple(path for path in _mp4_files_sorted(folder) if normalized in path.name.casefold())
    return _limit_file_list(matches, limit)


def _choose_mp4_from_list(prompt: str, files: tuple[Path, ...], *, overflow_count: int = 0, live_search: bool = False) -> Path | None:
    if not files:
        print("Es wurden keine passenden MP4-Dateien gefunden.")
        return None
    if overflow_count > 0:
        print(f"Hinweis: Es gibt {overflow_count} weitere Treffer. Bitte Suchtext genauer eingeben, wenn die Datei nicht dabei ist.")
    options = [MenuOption(_format_file_choice(path), path) for path in files] + [MenuOption("Zurück", BACK, ("z", "zurueck", "zurück"))]
    if live_search:
        selected = search_from_options(prompt, options)
    else:
        selected = choose_from_options(prompt, options)
    if selected is BACK:
        return None
    return selected


def _ask_mp4_path_or_limited_folder(prompt: str, *, folder_prompt: str = "MP4-Dateien auswählen") -> Path:
    while True:
        raw = _ask_required(prompt)
        path = _normalize_user_path(raw)
        if not path.exists():
            print("Dieser Pfad wurde nicht gefunden. Bitte den vollständigen Pfad eingeben.")
            continue
        if path.is_file():
            if path.suffix.casefold() == ".mp4":
                if _confirm_raw_recording_if_suspicious(path):
                    return path
                continue
            print("Diese Datei ist keine MP4-Datei. Bitte eine Datei mit der Endung .mp4 auswählen.")
            continue
        if not path.is_dir():
            print("Dieser Pfad ist keine Datei und kein Ordner. Bitte erneut eingeben.")
            continue

        files = _mp4_files_sorted(path)
        shown = _limit_file_list(files, RECENT_MP4_LIMIT)
        print("Das ist ein Ordner. Ich zeige nur die neuesten MP4-Dateien, damit die Liste übersichtlich bleibt.")
        selected = _choose_mp4_from_list(folder_prompt, shown, overflow_count=max(0, len(files) - len(shown)))
        if selected is not None:
            return selected


def _ask_search_mp4_in_folder(folder: Path) -> Path | None:
    if not folder.exists() or not folder.is_dir():
        print("Der konfigurierte Rohaufnahme-Ordner wurde nicht gefunden.")
        print(f"Ordner: {folder}")
        return None
    files = _mp4_files_sorted(folder)
    if not files:
        print("In diesem Ordner wurden keine MP4-Dateien gefunden.")
        return None
    return _choose_mp4_from_list(
        "MP4-Datei suchen und auswählen",
        files,
        overflow_count=0,
        live_search=True,
    )


def _ask_manual_raw_recording_path(config: AppConfig | None = None, log: WorkflowLog | None = None) -> Path:
    while True:
        raw = _ask_required("Pfad zur vMix-Rohaufnahme oder zu einem Ordner")
        path = _normalize_user_path(raw)
        if not path.exists():
            print("Dieser Pfad wurde nicht gefunden. Bitte den vollständigen Pfad eingeben.")
            continue
        if path.is_file():
            if path.suffix.casefold() == ".mp4":
                return path
            print("Diese Datei ist keine MP4-Datei. Bitte eine Datei mit der Endung .mp4 auswählen.")
            continue
        if path.is_dir():
            print("Dieser Ordner wird für diesen Wizard-Lauf als Rohaufnahme-Quellordner verwendet.")
            print(f"Temporärer Quellordner: {path}")
            if config is not None and path != config.vmix_storage:
                _remember_path_setting("vmix_storage", path, "Diesen Rohaufnahme-Ordner künftig merken?", log)
            return _ask_raw_recording_from_folder(path, "Temporärer Rohaufnahme-Quellordner", config=config, log=log)
        print("Dieser Pfad ist keine Datei und kein Ordner. Bitte erneut eingeben.")


def _confirm_raw_recording_if_suspicious(path: Path) -> bool:
    if not _looks_like_cut_or_final_mp4(path):
        return True
    print()
    print("Diese Datei wirkt bereits geschnitten. Ist das wirklich die Rohaufnahme?")
    print(f"Datei: {path}")
    return _ask_yes_no("Diese Datei trotzdem als Rohaufnahme verwenden?", False)


def _ask_raw_recording_from_folder(
    folder: Path,
    folder_label: str = "Konfigurierter Quellordner",
    *,
    config: AppConfig | None = None,
    log: WorkflowLog | None = None,
) -> Path:
    print(f"{folder_label}: {folder}")
    files = _raw_recording_candidates_sorted(folder)
    if not files:
        print("In diesem Rohaufnahme-Ordner wurde keine MP4 gefunden.")
        return _ask_manual_raw_recording_path(config, log)

    newest = _newest_raw_recording_candidate(folder)
    if newest is None:
        return _ask_manual_raw_recording_path(config, log)
    print(f"Vorschlag: {_format_file_choice(newest)}")
    while True:
        choice = choose_from_options(
            "Was möchtest du tun?",
            [
                MenuOption("Neueste Aufnahme verwenden", "newest", ("1", "neueste")),
                MenuOption(f"In den neuesten {min(RECENT_MP4_LIMIT, len(files))} Aufnahmen auswählen", "recent", ("2", "liste")),
                MenuOption("Suchen/filtern", "search", ("3", "suchen")),
                MenuOption("Datei/Ordner manuell eingeben", "manual", ("4", "manuell")),
                MenuOption("Abbrechen", "abort", ("5", "abbrechen")),
            ],
        )
        if choice == "newest":
            if _confirm_raw_recording_if_suspicious(newest):
                return newest
        if choice == "recent":
            shown = _limit_file_list(files, RECENT_MP4_LIMIT)
            selected = _choose_mp4_from_list(
                "Rohaufnahme auswählen",
                shown,
                overflow_count=max(0, len(files) - len(shown)),
            )
            if selected is not None and _confirm_raw_recording_if_suspicious(selected):
                return selected
        elif choice == "search":
            selected = _ask_search_mp4_in_folder(folder)
            if selected is not None and _confirm_raw_recording_if_suspicious(selected):
                return selected
        elif choice == "manual":
            selected = _ask_manual_raw_recording_path(config, log)
            return selected
        else:
            raise UserAbortError("Abbruch durch Nutzer.")


def _ask_raw_recording(config: AppConfig, log: WorkflowLog | None = None) -> Path:
    print()
    print("Rohaufnahme auswählen")
    if not config.vmix_storage.exists() or not config.vmix_storage.is_dir():
        print(f"Konfigurierter Quellordner: {config.vmix_storage}")
        print("Der konfigurierte Rohaufnahme-Ordner wurde nicht gefunden.")
        print("Du kannst jetzt einen anderen Rohaufnahme-Ordner oder direkt eine MP4-Datei eingeben.")
        print(f"Admin-Hinweis: vmix_storage existiert nicht oder ist kein Ordner: {config.vmix_storage}")
        return _ask_manual_raw_recording_path(config, log)

    return _ask_raw_recording_from_folder(config.vmix_storage, config=config, log=log)


def _default_cut_mp4_folder(config: AppConfig) -> Path:
    if config.cut_mp4_folder is not None:
        return config.cut_mp4_folder
    for folder in (config.vmix_storage, config.recordings_base):
        if folder.exists() and folder.is_dir():
            return folder
    return config.vmix_storage


def _newest_cut_mp4_candidate(folder: Path) -> Path | None:
    candidates = _cut_mp4_candidates_sorted(folder)
    if not candidates:
        return None
    return candidates[0]


def _warn_if_no_clear_cut_mp4(candidates: tuple[Path, ...]) -> None:
    if any(_cut_mp4_sort_key(path)[0] < 3 for path in candidates):
        return
    print("Ich habe keine eindeutig geschnittene Datei gefunden. Bitte bewusst die richtige MP4-Datei auswählen.")


def _choose_cut_mp4_from_folder(prompt: str, folder: Path, *, live_search: bool = False) -> Path | None:
    candidates = _cut_mp4_candidates_sorted(folder)
    if not candidates:
        print("In diesem Ordner wurden keine MP4-Dateien gefunden.")
        return None
    _warn_if_no_clear_cut_mp4(candidates)
    return _choose_mp4_from_list(prompt, candidates, live_search=live_search)


def _ask_manual_cut_mp4_path(config: AppConfig, log: WorkflowLog | None = None) -> Path:
    while True:
        raw = _ask_required("Anderen Ordner oder vollständigen MP4-Dateipfad eingeben")
        path = _normalize_user_path(raw)
        if not path.exists():
            print("Dieser Pfad wurde nicht gefunden. Bitte den vollständigen Pfad eingeben.")
            continue
        if path.is_file():
            if _is_valid_mp4_file(path):
                return path
            continue
        if not path.is_dir():
            print("Dieser Pfad ist keine Datei und kein Ordner. Bitte erneut eingeben.")
            continue

        print("Dieser Ordner wird für die Auswahl der geschnittenen MP4-Datei verwendet.")
        print(f"Ordner: {path}")
        if path != config.cut_mp4_folder:
            _remember_path_setting("cut_mp4_folder", path, "Diesen Ordner künftig für geschnittene MP4-Dateien merken?", log)
        selected = _choose_cut_mp4_from_folder("Geschnittene MP4-Datei auswählen", path)
        if selected is not None:
            return selected


def _select_existing_cut_mp4(config: AppConfig, log: WorkflowLog | None = None) -> Path | None:
    print()
    print("Fertig geschnittene MP4 auswählen")
    folder = _default_cut_mp4_folder(config)
    print(f"Vorgeschlagener Ordner: {folder}")
    if not folder.exists() or not folder.is_dir():
        print("Dieser vorgeschlagene Ordner wurde nicht gefunden.")
        print("Bitte gib jetzt einen anderen Ordner oder direkt die fertige MP4-Datei ein.")
        print(f"Admin-Hinweis: vorgeschlagener Ordner existiert nicht oder ist kein Ordner: {folder}")
        return _ask_manual_cut_mp4_path(config, log)

    newest = _newest_cut_mp4_candidate(folder)
    if newest is not None:
        print(f"Vorschlag: {_format_file_choice(newest)}")
    else:
        print("In diesem Ordner wurden keine MP4-Dateien gefunden.")

    while True:
        choice = choose_from_options(
            "Was möchtest du tun?",
            [
                MenuOption("In diesem Ordner suchen/auswählen", "search", ("1", "suchen", "auswaehlen", "auswählen")),
                MenuOption("Neueste geschnittene MP4 verwenden", "newest", ("2", "neueste")),
                MenuOption(f"In den neuesten {RECENT_MP4_LIMIT} MP4-Dateien auswählen", "recent", ("3", "liste")),
                MenuOption("Anderen Ordner oder Datei eingeben", "manual", ("4", "manuell")),
                MenuOption("Zurück", "back", ("5", "zurueck", "zurück", "z")),
            ],
        )
        if choice == "back":
            return None
        if choice == "search":
            selected = _choose_cut_mp4_from_folder("MP4-Datei suchen und auswählen", folder, live_search=True)
            if selected is not None:
                return selected
        elif choice == "newest":
            if newest is None:
                print("In diesem Ordner wurde keine MP4-Datei gefunden. Bitte einen anderen Ordner oder eine Datei eingeben.")
                continue
            if _cut_mp4_sort_key(newest)[0] >= 3:
                print("Ich habe keine eindeutig geschnittene Datei gefunden. Bitte bewusst die richtige MP4-Datei auswählen.")
                if not _ask_yes_no("Diese MP4 trotzdem als fertige Aufnahmedatei verwenden?", False):
                    continue
            return newest
        elif choice == "recent":
            candidates = _cut_mp4_candidates_sorted(folder)
            shown = _limit_file_list(candidates, RECENT_MP4_LIMIT)
            _warn_if_no_clear_cut_mp4(shown)
            selected = _choose_mp4_from_list(
                "MP4-Datei auswählen",
                shown,
                overflow_count=max(0, len(candidates) - len(shown)),
            )
            if selected is not None:
                return selected
        else:
            return _ask_manual_cut_mp4_path(config, log)


def _losslesscut_command(config: AppConfig) -> str:
    configured = config.losslesscut_path.strip()
    return configured or "LosslessCut"


def _losslesscut_source_label(config: AppConfig) -> str:
    return "config.toml" if config.losslesscut_path.strip() else "PATH/App-Alias"


def _open_losslesscut(raw_recording: Path, config: AppConfig) -> subprocess.Popen[bytes]:
    command = _losslesscut_command(config)
    try:
        return subprocess.Popen(
            [command, str(raw_recording)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise LosslessCutStartError(
            "LosslessCut konnte nicht gestartet werden.",
            f"Programm nicht gefunden: {command!r}. Details: {exc}",
        ) from exc
    except OSError as exc:
        raise LosslessCutStartError(
            "LosslessCut konnte nicht gestartet werden.",
            f"Start von LosslessCut fehlgeschlagen mit {command!r} und Datei {raw_recording}. Details: {exc}",
        ) from exc


def _is_plausible_losslesscut_exe(path: Path) -> bool:
    name = path.name.casefold()
    return path.suffix.casefold() == ".exe" or "losslesscut" in name


def _ask_losslesscut_exe_path() -> Path:
    while True:
        path = ask_file_path(
            "Pfad zur LosslessCut.exe",
            extensions=(".exe",),
            file_description="EXE-Dateien",
        )
        if not _is_plausible_losslesscut_exe(path):
            print("Diese Datei sieht nicht nach LosslessCut aus. Bitte eine .exe-Datei oder LosslessCut.exe auswählen.")
            continue
        return path


def _try_start_losslesscut(raw_recording: Path, config: AppConfig, log: WorkflowLog) -> subprocess.Popen[bytes] | None:
    log.event(f"LosslessCut-Startversuch ueber {_losslesscut_source_label(config)}: {_losslesscut_command(config)!r}")
    try:
        process = _open_losslesscut(raw_recording, config)
        log.event("LosslessCut wurde gestartet.")
        return process
    except LosslessCutStartError as exc:
        log.error("LosslessCut konnte automatisch nicht gestartet werden.", admin_hint=exc.admin_hint)
        print()
        print("LosslessCut wurde nicht gefunden oder konnte nicht gestartet werden.")
        print("Du kannst jetzt den Pfad zur LosslessCut.exe eingeben oder den Schnitt manuell durchführen.")
        print(f"Admin-Hinweis: {exc.admin_hint}")

    if _ask_yes_no("Pfad zur LosslessCut.exe jetzt eingeben?", True):
        manual_path = _ask_losslesscut_exe_path()
        log.event(f"Manueller LosslessCut-Pfad eingegeben: {manual_path}")
        manual_config = replace(config, losslesscut_path=str(manual_path))
        _remember_path_setting("losslesscut_path", manual_path, "LosslessCut-Pfad künftig merken?", log)
        try:
            process = _open_losslesscut(raw_recording, manual_config)
            log.event("LosslessCut wurde mit manuellem Pfad gestartet.")
            return process
        except LosslessCutStartError as exc:
            log.error("LosslessCut konnte auch mit manuellem Pfad nicht gestartet werden.", admin_hint=exc.admin_hint)
            print()
            print("LosslessCut konnte auch mit diesem Pfad nicht gestartet werden.")
            print("Bitte öffne LosslessCut manuell und lade dort die Rohaufnahme.")
            print(f"Admin-Hinweis: {exc.admin_hint}")
    else:
        log.event("Nutzer ueberspringt manuellen LosslessCut-Pfad.")

    print(f"Rohaufnahme: {raw_recording}")
    return None


def _print_losslesscut_instructions() -> None:
    print()
    print("Bitte jetzt in LosslessCut schneiden")
    print("-----------------------------------")
    print("- Markiere nur den gewünschten Aufnahmebereich.")
    print("- Exportiere nur diesen Abschnitt als MP4.")
    print("- Chorlieder, Beiträge oder Ansagen nicht versehentlich auswählen, wenn sie nicht zur Aufnahme gehören.")
    print("- Exportiere den Abschnitt in LosslessCut.")
    print("- Danach kannst du LosslessCut schließen oder hier Enter drücken.")


def _process_finished(process: subprocess.Popen[bytes] | None) -> bool:
    return process is not None and process.poll() is not None


def _wait_for_losslesscut_or_enter(process: subprocess.Popen[bytes] | None) -> None:
    print()
    print("Warten auf LosslessCut-Export")
    print("Exportiere den gewünschten Abschnitt in LosslessCut. Danach kannst du LosslessCut schließen oder hier Enter drücken.")
    if process is None:
        _ask("Drücke Enter, sobald der Export fertig ist")
        return
    if _process_finished(process):
        print("LosslessCut wurde geschlossen. Ich suche jetzt nach der exportierten MP4.")
        return
    if os.name == "nt" and sys.stdin.isatty():
        try:
            import msvcrt
        except ImportError:
            _ask("Drücke Enter, sobald der Export fertig ist")
            return
        print("Drücke Enter, sobald der Export fertig ist. Wenn LosslessCut geschlossen wird, geht es automatisch weiter.")
        while not _process_finished(process):
            if msvcrt.kbhit():
                key = msvcrt.getwch()
                if key in {"\r", "\n"}:
                    print()
                    return
            time.sleep(0.5)
        print("LosslessCut wurde geschlossen. Ich suche jetzt nach der exportierten MP4.")
        return
    _ask("Drücke Enter, sobald der Export fertig ist")


def _export_search_folders(config: AppConfig, raw_recording: Path) -> tuple[Path, ...]:
    folders = [
        raw_recording.parent,
        config.vmix_storage,
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        config.recordings_base,
    ]
    unique: list[Path] = []
    for folder in folders:
        if folder not in unique:
            unique.append(folder)
    return tuple(unique)


def _find_new_mp4_exports(folders: tuple[Path, ...], since: datetime) -> tuple[Path, ...]:
    since_timestamp = since.timestamp()
    found: list[Path] = []
    for folder in folders:
        if not folder.exists() or not folder.is_dir():
            continue
        for path in folder.glob("*.mp4"):
            if path.is_file() and path.stat().st_mtime >= since_timestamp and path not in found:
                found.append(path)
    return tuple(sorted(found, key=lambda path: path.stat().st_mtime, reverse=True))


def _is_cut_export(path: Path) -> bool:
    name = path.stem.casefold()
    return "_geschnitten" in name or "geschnitten" in name


def _looks_like_losslesscut_export(path: Path) -> bool:
    stem = path.stem.casefold()
    return _is_cut_export(path) or bool(re.search(r"\d{2}\.\d{2}\.\d{3}\s*-\s*\d{2}\.\d{2}\.\d{3}", stem))


def _looks_like_raw_named_export(path: Path, raw_recording: Path | None) -> bool:
    if raw_recording is None:
        return False
    stem = path.stem.casefold()
    raw_stem = raw_recording.stem.casefold()
    return (
        stem.startswith(f"_geschnitten_{raw_stem}")
        or stem.startswith(f"geschnitten_{raw_stem}")
        or (raw_stem in stem and _looks_like_losslesscut_export(path))
    )


def _prioritize_export_candidates(candidates: tuple[Path, ...], raw_recording: Path | None = None) -> tuple[Path, ...]:
    return tuple(
        sorted(
            candidates,
            key=lambda path: (
                0 if _looks_like_raw_named_export(path, raw_recording) else 1,
                0 if _looks_like_losslesscut_export(path) else 1,
                -path.stat().st_mtime,
            ),
        )
    )


def _snapshot_mp4_files(folders: tuple[Path, ...]) -> dict[Path, Mp4FileSnapshot]:
    snapshots: dict[Path, Mp4FileSnapshot] = {}
    for folder in folders:
        if not folder.exists() or not folder.is_dir():
            continue
        for path in folder.glob("*.mp4"):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            snapshots[path] = Mp4FileSnapshot(
                path=path,
                size=stat.st_size,
                modified_at=stat.st_mtime,
                created_at=stat.st_ctime,
            )
    return snapshots


def _find_mp4_exports_after_snapshot(
    folders: tuple[Path, ...],
    before: dict[Path, Mp4FileSnapshot],
    assistant_start: datetime,
    raw_recording: Path | None = None,
) -> tuple[Path, ...]:
    start_timestamp = assistant_start.timestamp()
    broad_user_folders = {Path.home() / "Downloads", Path.home() / "Desktop"}
    found: list[Path] = []
    for folder in folders:
        if not folder.exists() or not folder.is_dir():
            continue
        for path in folder.glob("*.mp4"):
            if not path.is_file() or path in found:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            old = before.get(path)
            is_new_path = old is None
            changed_file = old is not None and (old.size != stat.st_size or old.modified_at != stat.st_mtime or old.created_at != stat.st_ctime)
            created_after_start = stat.st_ctime >= start_timestamp
            modified_after_start = stat.st_mtime >= start_timestamp
            is_in_broad_user_folder = path.parent in broad_user_folders
            plausible_name = _looks_like_losslesscut_export(path)
            raw_named_export = _looks_like_raw_named_export(path, raw_recording)
            if (
                is_new_path
                and (created_after_start or modified_after_start or not is_in_broad_user_folder)
            ) or raw_named_export or (changed_file and plausible_name):
                found.append(path)
    return _prioritize_export_candidates(tuple(found), raw_recording)


def _manual_export_candidates(folder: Path, assistant_start: datetime) -> tuple[Path, ...]:
    files = _mp4_files_sorted(folder)
    new_files = tuple(path for path in files if path.stat().st_mtime >= assistant_start.timestamp())
    if new_files:
        print("In diesem Ordner wurden neue MP4-Dateien seit Start des Assistenten gefunden.")
        return new_files
    print("Keine neuen MP4-Dateien seit Start des Assistenten gefunden.")
    print("Ich zeige bevorzugt neue und geschnittene Dateien, nicht die ganze alte Liste.")
    return _prioritize_export_candidates(files)


def _choose_exported_mp4(candidates: tuple[Path, ...], raw_recording: Path | None = None) -> Path:
    candidates = _prioritize_export_candidates(candidates, raw_recording)
    if len(candidates) == 1:
        candidate = candidates[0]
        print(f"Gefundene neue MP4: {candidate}")
        if _ask_yes_no("Diese exportierte MP4-Datei verwenden?", True):
            return candidate

    if len(candidates) > 1:
        print("Es wurden mehrere neue MP4-Dateien gefunden.")
        print("Bitte wähle bewusst die Datei aus, die den gewünschten Abschnitt enthält.")
        return choose_from_options(
            "Richtige MP4-Datei auswählen",
            [MenuOption(str(candidate), candidate) for candidate in candidates],
        )

    print("Es wurde keine passende neue MP4 automatisch ausgewählt.")
    return _ask_mp4_path_or_limited_folder("Pfad zur exportierten MP4 oder zu einem Ordner", folder_prompt="Exportierte MP4 auswählen")


def _ask_exported_mp4_manually(assistant_start: datetime) -> Path:
    while True:
        raw = _ask_required("Pfad zur exportierten MP4 oder zu einem Ordner")
        path = _normalize_user_path(raw)
        if not path.exists():
            print("Dieser Pfad wurde nicht gefunden. Bitte den vollständigen Pfad eingeben.")
            continue
        if path.is_file():
            if path.suffix.casefold() == ".mp4":
                return path
            print("Diese Datei ist keine MP4-Datei. Bitte eine Datei mit der Endung .mp4 auswählen.")
            continue
        if not path.is_dir():
            print("Dieser Pfad ist keine Datei und kein Ordner. Bitte erneut eingeben.")
            continue

        candidates = _manual_export_candidates(path, assistant_start)
        shown = _limit_file_list(candidates, RECENT_MP4_LIMIT)
        selected = _choose_mp4_from_list(
            "Exportierte MP4 auswählen",
            shown,
            overflow_count=max(0, len(candidates) - len(shown)),
        )
        if selected is not None:
            return selected
        continue


def _select_exported_mp4(
    config: AppConfig,
    raw_recording: Path,
    assistant_start: datetime,
    before_export: dict[Path, Mp4FileSnapshot] | None = None,
    losslesscut_process: subprocess.Popen[bytes] | None = None,
) -> Path:
    print()
    print("Exportierte MP4 übernehmen")
    print("Wenn der Export in LosslessCut fertig ist, sucht der Wizard nach neuen MP4-Dateien.")
    _wait_for_losslesscut_or_enter(losslesscut_process)
    folders = _export_search_folders(config, raw_recording)
    if before_export is None:
        before_export = _snapshot_mp4_files(folders)
    try:
        candidates = _find_mp4_exports_after_snapshot(folders, before_export, assistant_start, raw_recording)
    except TypeError:
        candidates = _find_mp4_exports_after_snapshot(folders, before_export, assistant_start)
    if candidates:
        return _choose_exported_mp4(candidates, raw_recording)
    print("Es wurde keine passende neue MP4 automatisch ausgewählt.")
    return _ask_exported_mp4_manually(assistant_start)


def _select_source_mp4_for_workflow(config: AppConfig, log: WorkflowLog) -> tuple[Path, Path | None]:
    while True:
        if _ask_yes_no("Hast du bereits eine fertig geschnittene MP4-Datei?", True):
            selected = _select_existing_cut_mp4(config, log)
            if selected is not None:
                return selected, None
            continue
        break

    assistant_start = datetime.now()
    raw_recording = _ask_raw_recording(config, log)
    log.event(f"Rohaufnahme fuer LosslessCut ausgewaehlt: {raw_recording}")
    export_folders = _export_search_folders(config, raw_recording)
    before_export = _snapshot_mp4_files(export_folders)
    log.event(f"MP4-Snapshot vor LosslessCut-Export erstellt: {len(before_export)} Dateien.")
    losslesscut_process = _try_start_losslesscut(raw_recording, config, log)

    _print_losslesscut_instructions()
    exported_mp4 = _select_exported_mp4(config, raw_recording, assistant_start, before_export, losslesscut_process)
    log.event(f"Exportierte MP4 ausgewaehlt: {exported_mp4}")
    return exported_mp4, raw_recording


def _select_source_mp4(config: AppConfig, log: WorkflowLog) -> Path:
    source, _raw_recording = _select_source_mp4_for_workflow(config, log)
    return source


def _ask_optional_folder_note() -> str:
    print()
    print("Ordner-Besonderheit")
    print("Beispiele: Feiertag, Themenreihe, Gastredner, Besuch, Taufe, Gemeindefreizeit")
    if not _ask_yes_no("Soll etwas Besonderes im Ordnernamen stehen?", False):
        return ""
    return _ask_required("Besonderheit für den Ordnernamen")


METADATA_HELP_TEXT = (
    "Diese Informationen findest du z. B. im Broadcast/Ablaufplan, bei der Beamertechnik bzw. "
    "in der Präsentation, in ChurchTools oder beim Prediger. Wenn etwas fehlt, bitte kurz Kontakt aufnehmen."
)


def _print_metadata_help() -> None:
    print()
    print("Hinweis zu den Angaben")
    print(METADATA_HELP_TEXT)


def _ask_optional_text(prompt: str) -> str:
    return _ask(prompt).strip()


def _service_types_for(config: AppConfig) -> tuple[ServiceTypeConfig, ...]:
    return default_service_types(config) + config.custom_service_types


def _service_type_default_index(service_types: tuple[ServiceTypeConfig, ...], sermon_date: date) -> int:
    weekday_defaults = {
        2: "Bibelstunde",
        4: "Gebetsstunde",
        6: "Predigt",
    }
    preferred = weekday_defaults.get(sermon_date.weekday(), "Predigt")
    for index, service_type in enumerate(service_types):
        if service_type.name.casefold() == preferred.casefold():
            return index
    return 0


def _ask_service_type(config: AppConfig, sermon_date: date) -> ServiceTypeConfig:
    service_types = _service_types_for(config)
    options = [MenuOption(service_type.name, service_type) for service_type in service_types]
    return choose_from_options(
        "Welche Art von Aufnahme ist das?",
        options,
        default_index=_service_type_default_index(service_types, sermon_date),
    )


def _print_filename_preview(config: AppConfig, sermon_date: date, service_type: ServiceTypeConfig, title: str, bible_reference: str, speaker: str) -> None:
    preview = build_filename_preview(
        SermonInfo(
            sermon_date=sermon_date,
            title=title,
            bible_reference=bible_reference,
            speaker=speaker,
            sermon_type=service_type.name,
        ),
        config,
    )
    print(f"Aktueller Dateiname: {preview.mp4}")


def _ask_sermon_metadata(config: AppConfig, sermon_date: date) -> SermonInfo:
    service_type = _ask_service_type(config, sermon_date)
    _print_filename_preview(config, sermon_date, service_type, "", "", "")
    _print_metadata_help()

    title = ""
    bible_reference = ""
    speaker = ""

    if service_type.requires_title:
        title = _ask_required(service_type.title_label)
        _print_filename_preview(config, sermon_date, service_type, title, bible_reference, speaker)
    else:
        print("Für diese Dienstart ist kein Titel nötig.")
    if service_type.requires_bible_reference:
        bible_reference = _ask_required(service_type.bible_reference_label)
        _print_filename_preview(config, sermon_date, service_type, title, bible_reference, speaker)
    elif service_type.optional_bible_reference and _ask_yes_no("Gibt es eine Bibelstelle, die in die Zusammenfassung soll?", False):
        bible_reference = _ask_optional_text(service_type.bible_reference_label)
        _print_filename_preview(config, sermon_date, service_type, title, bible_reference, speaker)
    if service_type.requires_speaker:
        speaker = _ask_required(service_type.speaker_label)
        _print_filename_preview(config, sermon_date, service_type, title, bible_reference, speaker)
    elif service_type.optional_speaker and _ask_yes_no(f"{service_type.speaker_label} angeben?", False):
        speaker = _ask_optional_text(service_type.speaker_label)
        _print_filename_preview(config, sermon_date, service_type, title, bible_reference, speaker)

    folder_note = _ask_optional_folder_note()
    return SermonInfo(
        sermon_date=sermon_date,
        title=title,
        bible_reference=bible_reference,
        speaker=speaker,
        sermon_type=service_type.name,
        folder_note=folder_note,
    )


def _choose_from_existing_folders(candidates: tuple[Path, ...]) -> Path:
    while True:
        raw_choice = _ask_required("Nummer des Zielordners")
        try:
            choice = int(raw_choice)
        except ValueError:
            print("Bitte eine Nummer aus der Liste eingeben.")
            continue
        if 1 <= choice <= len(candidates):
            return candidates[choice - 1]
        print(f"Bitte eine Nummer zwischen 1 und {len(candidates)} eingeben.")


def _show_new_folder_note(info: SermonInfo, config: AppConfig) -> None:
    if info.folder_note:
        print(f"Aus der Besonderheit wird dieser Ordnername: {resolve_folder(config, info).suggested_folder.name}")


def _select_target_folder(config: AppConfig, info: SermonInfo) -> tuple[Path, SermonInfo] | None:
    resolution = resolve_folder(config, info)
    print()
    print("Zielordner prüfen")
    print(f"Jahresordner: {resolution.year_folder}")
    print(f"Datum: {resolution.date_prefix}")
    _show_new_folder_note(info, config)

    if resolution.status == "multiple_existing":
        print("Für dieses Datum gibt es mehrere Ordner:")
        for index, candidate in enumerate(resolution.candidates, start=1):
            print(f"  {index}. {candidate.name}")
        print("Bitte wähle bewusst den Ordner aus, in dem die Aufnahme gespeichert werden soll.")
        return _choose_from_existing_folders(resolution.candidates), info

    if resolution.status == "single_existing":
        existing = resolution.candidates[0]
        print(f"Es gibt bereits diesen Ordner: {existing}")
        if _ask_yes_no("Diesen vorhandenen Ordner verwenden?", True):
            return existing, info

        if existing == resolution.suggested_folder:
            print("Damit ein neuer Ordner entstehen kann, braucht er eine Besonderheit im Namen.")
            new_note = _ask_required("Besonderheit für den neuen Ordner")
            info = replace(info, folder_note=new_note)
            resolution = resolve_folder(config, info)
            _show_new_folder_note(info, config)

        print(f"Stattdessen wird dieser neue Ordner erstellt: {resolution.suggested_folder}")
        return resolution.suggested_folder, info

    print("Für dieses Datum gibt es noch keinen Ordner.")
    print(f"Dieser Ordner wird erstellt: {resolution.suggested_folder}")
    return resolution.suggested_folder, info


def _mp4_action_name(config: AppConfig) -> str:
    return "kopiert" if config.copy_instead_of_move else "verschoben"


def _print_mp4_action_preview(plan: ProcessingPlan, config: AppConfig, transfer_mode: Mp4TransferMode = MP4_TRANSFER_COPY) -> None:
    print()
    print("MP4-Datei übernehmen")
    print("--------------------")
    print(f"Quell-Datei: {plan.source_mp4}")
    print(f"Zielordner: {plan.target_mp4.parent}")
    print(f"Finaler MP4-Dateiname: {plan.target_mp4.name}")
    if transfer_mode == MP4_TRANSFER_KEEP:
        print("Aktion: Die vorhandene MP4 bleibt erhalten. Es wird nichts kopiert oder verschoben.")
    elif transfer_mode == MP4_TRANSFER_OVERWRITE:
        print(f"Aktion: Die vorhandene MP4 wird ersetzt. Die neue MP4 wird {_mp4_action_name(config)}.")
    else:
        print(f"Aktion: Die MP4 wird {_mp4_action_name(config)}.")


def _ask_new_mp4_target(current_target: Path) -> Path:
    while True:
        raw_name = _ask_required("Neuer MP4-Dateiname")
        if not raw_name.casefold().endswith(".mp4"):
            raw_name = f"{raw_name}.mp4"
        safe_name = sanitize_filename_part(raw_name)
        if not safe_name.casefold().endswith(".mp4"):
            print("Bitte einen Dateinamen mit der Endung .mp4 verwenden.")
            continue
        target = current_target.with_name(safe_name)
        if target.exists():
            print("Auch diese Datei gibt es bereits. Bitte einen anderen Namen eingeben.")
            continue
        return target


def _handle_existing_target_mp4(plan: ProcessingPlan) -> tuple[ProcessingPlan, Mp4TransferMode] | None:
    if not plan.target_mp4.exists():
        return plan, MP4_TRANSFER_COPY

    print()
    print("Die Zieldatei existiert bereits.")
    print(f"Vorhandene Datei: {plan.target_mp4}")
    print("Sie wird nicht automatisch überschrieben.")
    print("Wichtig: Überschreiben ersetzt die vorhandene Datei.")
    choice = choose_from_options(
        "Was soll passieren?",
        [
            MenuOption(
                "Vorhandene Datei behalten und ohne Kopieren/Verschieben weiterarbeiten",
                "keep",
                ("b", "behalten"),
            ),
            MenuOption("Neuen Dateinamen verwenden", "new", ("n", "neu")),
            MenuOption("Abbrechen", "abort", ("a", "abbrechen")),
            MenuOption(
                "Überschreiben: vorhandene Datei ersetzen",
                "overwrite",
                ("o", "overwrite", "überschreiben", "ueberschreiben", "ü"),
            ),
        ],
    )
    if choice == "abort":
        return None
    if choice == "keep":
        return plan, MP4_TRANSFER_KEEP
    if choice == "overwrite":
        print()
        print("Sicherheitsfrage: Die vorhandene MP4 wird wirklich ersetzt.")
        print(f"Betroffene Datei: {plan.target_mp4}")
        if not _ask_yes_no("Vorhandene MP4 wirklich überschreiben?", False):
            print("Die vorhandene Datei bleibt unverändert.")
            return None
        return plan, MP4_TRANSFER_OVERWRITE

    target_mp4 = _ask_new_mp4_target(plan.target_mp4)
    target_mp3 = target_mp4.with_suffix(".mp3")
    return replace(plan, target_mp4=target_mp4, target_mp3=target_mp3), MP4_TRANSFER_COPY


def _check_target_folder_writable(target_folder: Path) -> None:
    test_file = target_folder / f".predigt-uploader-schreibtest-{uuid4().hex}.tmp"
    try:
        with test_file.open("x", encoding="utf-8") as handle:
            handle.write("test")
    except PermissionError as exc:
        raise Mp4TransferError(
            "Der Zielordner ist nicht beschreibbar.",
            f"Keine Berechtigung zum Schreiben in den Zielordner: {target_folder}. Details: {exc}",
        ) from exc
    except OSError as exc:
        raise Mp4TransferError(
            "Der Zielordner ist nicht beschreibbar.",
            f"Schreibtest im Zielordner fehlgeschlagen: {target_folder}. Details: {exc}",
        ) from exc
    finally:
        try:
            test_file.unlink(missing_ok=True)
        except OSError:
            pass


def _transfer_mp4_to_target(
    plan: ProcessingPlan,
    config: AppConfig,
    *,
    keep_existing: bool = False,
    overwrite_existing: bool = False,
) -> None:
    if keep_existing:
        if not plan.target_mp4.exists():
            raise Mp4TransferError(
                "Die vorhandene MP4 wurde nicht gefunden.",
                f"Vorhandene Zieldatei fehlt: {plan.target_mp4}",
            )
        print(f"Die vorhandene MP4 bleibt erhalten: {plan.target_mp4}")
        return

    if not plan.source_mp4.exists():
        raise Mp4TransferError(
            "Die Quell-MP4 wurde nicht mehr gefunden.",
            f"Quelldatei fehlt vor der Dateiübernahme: {plan.source_mp4}",
        )
    if not plan.source_mp4.is_file():
        raise Mp4TransferError(
            "Die angegebene Quelle ist keine Datei.",
            f"Quelle ist keine Datei: {plan.source_mp4}",
        )

    try:
        ensure_folder(plan.target_mp4.parent)
    except PermissionError as exc:
        raise Mp4TransferError(
            "Der Zielordner konnte nicht erstellt oder geöffnet werden.",
            f"Keine Berechtigung für Zielordner: {plan.target_mp4.parent}. Details: {exc}",
        ) from exc
    except OSError as exc:
        raise Mp4TransferError(
            "Der Zielordner konnte nicht erstellt oder geöffnet werden.",
            f"Zielordner konnte nicht vorbereitet werden: {plan.target_mp4.parent}. Details: {exc}",
        ) from exc

    _check_target_folder_writable(plan.target_mp4.parent)

    if plan.target_mp4.exists() and not overwrite_existing:
        raise Mp4TransferError(
            "Die Zieldatei existiert bereits.",
            f"Zieldatei existiert vor der Dateiübernahme: {plan.target_mp4}",
        )

    try:
        if config.copy_instead_of_move:
            _show_wait_status("MP4 wird kopiert.")
            shutil.copy2(plan.source_mp4, plan.target_mp4)
            if overwrite_existing:
                print(f"Die vorhandene MP4 wurde überschrieben: {plan.target_mp4}")
            else:
                print(f"Die MP4 wurde kopiert: {plan.target_mp4}")
        else:
            if overwrite_existing and plan.target_mp4.exists():
                plan.target_mp4.unlink()
            _show_wait_status("MP4 wird verschoben.")
            shutil.move(str(plan.source_mp4), str(plan.target_mp4))
            if overwrite_existing:
                print(f"Die vorhandene MP4 wurde überschrieben: {plan.target_mp4}")
            else:
                print(f"Die MP4 wurde verschoben: {plan.target_mp4}")
    except PermissionError as exc:
        raise Mp4TransferError(
            "Die MP4 konnte wegen fehlender Berechtigungen nicht übernommen werden.",
            f"Berechtigungsfehler bei Quelle '{plan.source_mp4}' oder Ziel '{plan.target_mp4}'. Details: {exc}",
        ) from exc
    except FileExistsError as exc:
        raise Mp4TransferError(
            "Die Zieldatei existiert bereits.",
            f"Zieldatei wurde während der Dateiübernahme angelegt: {plan.target_mp4}. Details: {exc}",
        ) from exc
    except OSError as exc:
        raise Mp4TransferError(
            "Die MP4 konnte nicht in den Zielordner übernommen werden.",
            f"Dateiübernahme fehlgeschlagen von '{plan.source_mp4}' nach '{plan.target_mp4}'. Details: {exc}",
        ) from exc


def _print_mp4_transfer_error(exc: Mp4TransferError) -> None:
    print()
    print(exc.user_message)
    print("Bitte prüfe die Datei und den Zielordner und starte den Vorgang danach erneut.")
    print(f"Admin-Hinweis: {exc.admin_hint}")


def _print_missing_ffmpeg_message(plan: ProcessingPlan, config: AppConfig) -> None:
    print()
    print("Die MP3 kann noch nicht erstellt werden.")
    print("Es fehlt FFmpeg. Das ist ein Hilfsprogramm, mit dem aus der MP4 eine MP3-Tondatei erstellt wird.")
    print(f"Die MP4 wurde trotzdem vorbereitet und liegt hier: {plan.target_mp4}")
    print()
    print("So kannst du manuell weitermachen:")
    print("- Erstelle aus der vorbereiteten MP4 eine MP3 mit File Converter, Shutter Encoder oder einem ähnlichen Programm.")
    print(f"- Speichere die MP3 mit diesem Namen: {plan.target_mp3.name}")
    print(f"- Lege die MP3 in diesen Ordner: {plan.target_mp3.parent}")
    print()
    print(
        "Admin-Hinweis: FFmpeg wurde nicht gefunden. "
        f"Eingestellter ffmpeg_path: {config.ffmpeg_path!r}. "
        "Erwartet wird eine ausführbare FFmpeg-Datei oder ein Eintrag im PATH."
    )


def _print_mp3_manual_steps(plan: ProcessingPlan) -> None:
    print("So kannst du manuell weitermachen:")
    print("- Erstelle aus der vorbereiteten MP4 eine MP3 mit File Converter, Shutter Encoder oder einem ähnlichen Programm.")
    print(f"- Speichere die MP3 mit diesem Namen: {plan.target_mp3.name}")
    print(f"- Lege die MP3 in diesen Ordner: {plan.target_mp3.parent}")


def _validate_non_empty_file(path: Path, label: str) -> None:
    if not path.exists():
        raise Mp3ResultError(
            f"Die {label} wurde nicht gefunden.",
            f"Erwartete Datei fehlt: {path}",
        )
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise Mp3ResultError(
            f"Die {label} konnte nicht geprüft werden.",
            f"Dateigröße konnte nicht gelesen werden: {path}. Details: {exc}",
        ) from exc
    if size <= 0:
        raise Mp3ResultError(
            f"Die {label} ist leer.",
            f"Datei hat 0 Bytes: {path}",
        )


def _validate_created_mp3(target_mp3: Path) -> None:
    try:
        _validate_non_empty_file(target_mp3, "MP3")
    except Mp3ResultError as exc:
        user_message = exc.user_message
        if "nicht gefunden" in user_message:
            user_message = "Die MP3 wurde nach der Konvertierung nicht gefunden."
        elif "leer" in user_message:
            user_message = "Die MP3 wurde erstellt, ist aber leer."
        elif "konnte nicht geprüft" in user_message:
            user_message = "Die MP3 konnte nach der Konvertierung nicht geprüft werden."
        raise Mp3ResultError(user_message, exc.admin_hint) from exc


def _print_mp3_creation_error(plan: ProcessingPlan, user_message: str, admin_hint: str) -> None:
    print()
    print(user_message)
    print(f"Die vorbereitete MP4 liegt hier: {plan.target_mp4}")
    print()
    _print_mp3_manual_steps(plan)
    print()
    print(f"Admin-Hinweis: {admin_hint}")


def _write_summary_file_safely(plan: ProcessingPlan) -> Path:
    try:
        write_summary_file(plan)
    except PermissionError as exc:
        raise SummaryWriteError(
            f"Keine Berechtigung beim Schreiben der Zusammenfassung in {plan.target_mp4.parent}. Details: {exc}"
        ) from exc
    except OSError as exc:
        raise SummaryWriteError(
            f"Zusammenfassung konnte nicht in {plan.target_mp4.parent} geschrieben werden. Details: {exc}"
        ) from exc
    return plan.target_mp4.parent / "predigt-zusammenfassung.txt"


def _print_summary_write_error(plan: ProcessingPlan, exc: SummaryWriteError) -> None:
    print()
    print("Die Mediendateien wurden vorbereitet, aber die Zusammenfassung konnte nicht geschrieben werden.")
    print(f"Zielordner: {plan.target_mp4.parent}")
    print("Bitte prüfe, ob der Ordner geöffnet, schreibgeschützt oder nicht erreichbar ist.")
    print(f"Admin-Hinweis: {exc.admin_hint}")


def _validate_local_workflow_result(plan: ProcessingPlan) -> None:
    try:
        _validate_non_empty_file(plan.target_mp4, "MP4")
        _validate_non_empty_file(plan.target_mp3, "MP3")
    except Mp3ResultError as exc:
        raise Mp3ResultError(
            "Der lokale Workflow konnte nicht erfolgreich abgeschlossen werden.",
            exc.admin_hint,
        ) from exc


def _print_local_workflow_success(plan: ProcessingPlan, summary_path: Path | None) -> None:
    print()
    print("Lokaler Workflow erfolgreich abgeschlossen.")
    print(f"Zielordner: {plan.target_mp4.parent}")
    print(f"Finale MP4: {plan.target_mp4}")
    print(f"Finale MP3: {plan.target_mp3}")
    if summary_path is not None:
        print(f"Zusammenfassung: {summary_path}")


def _open_target_folder(target_folder: Path) -> None:
    try:
        os.startfile(target_folder)  # type: ignore[attr-defined]
    except AttributeError as exc:
        raise TargetFolderOpenError("os.startfile ist auf diesem System nicht verfügbar.") from exc
    except OSError as exc:
        raise TargetFolderOpenError(f"Explorer konnte den Zielordner nicht öffnen: {target_folder}. Details: {exc}") from exc


def _open_target_folder_safely(config: AppConfig, target_folder: Path, log: WorkflowLog) -> None:
    if not config.open_target_folder:
        log.event("Automatisches Oeffnen des Zielordners ist deaktiviert.")
        return
    try:
        _open_target_folder(target_folder)
        log.event(f"Zielordner im Explorer geoeffnet: {target_folder}")
    except TargetFolderOpenError as exc:
        log.error("Zielordner konnte nicht automatisch geoeffnet werden.", admin_hint=exc.admin_hint)
        print()
        print("Der Zielordner konnte nicht automatisch geöffnet werden.")
        print(f"Bitte öffne ihn bei Bedarf manuell: {target_folder}")
        print(f"Admin-Hinweis: {exc.admin_hint}")


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left.absolute() == right.absolute()


def _archive_target_for_raw_recording(raw_recording: Path, target_folder: Path) -> Path | None:
    target = target_folder / raw_recording.name
    if not target.exists():
        return target

    stem = raw_recording.stem
    suffix = raw_recording.suffix
    for index in range(1, 100):
        candidate = target_folder / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            print()
            print("Im Zielordner gibt es bereits eine Datei mit diesem Namen.")
            print(f"Vorgeschlagener neuer Name: {candidate.name}")
            if _ask_yes_no("Diesen neuen Namen verwenden?", True):
                return candidate
            return None
    return None


def _raw_archive_default_index(options: list[MenuOption[RawArchiveMode]], default_mode: RawArchiveMode) -> int:
    for index, option in enumerate(options):
        if option.value == default_mode:
            return index
    return 0


def _ask_raw_archive_mode(raw_recording: Path, target_folder: Path, default_mode: RawArchiveMode = RAW_ARCHIVE_MOVE) -> RawArchiveMode:
    if _same_file(raw_recording.parent, target_folder):
        return RAW_ARCHIVE_NONE
    print()
    print("Rohaufnahme aufräumen")
    print(f"Rohaufnahme: {raw_recording}")
    print(f"Zielordner: {target_folder}")
    if _looks_like_cut_or_final_mp4(raw_recording):
        print("Diese Datei sieht bereits geschnitten aus. Bitte nicht als Rohaufnahme archivieren, wenn sie nicht der vollständige Gottesdienst ist.")
        default_mode = RAW_ARCHIVE_NONE
    options = [
        MenuOption("Ja, Rohaufnahme in Zielordner verschieben", RAW_ARCHIVE_MOVE, ("v", "verschieben", "j", "ja")),
        MenuOption("Nein, Rohaufnahme liegen lassen", RAW_ARCHIVE_NONE, ("n", "nein")),
        MenuOption("Rohaufnahme kopieren statt verschieben", RAW_ARCHIVE_COPY, ("k", "kopieren")),
    ]
    return choose_from_options(
        "Rohaufnahme in den Zielordner verschieben, damit vMixStorage frei bleibt?",
        options,
        default_index=_raw_archive_default_index(options, default_mode),
    )


def _archive_raw_recording(raw_recording: Path, target_folder: Path, mode: RawArchiveMode) -> Path | None:
    if mode == RAW_ARCHIVE_NONE:
        return None
    if not raw_recording.exists() or not raw_recording.is_file():
        raise RawRecordingArchiveError(
            "Die Rohaufnahme wurde nicht mehr gefunden.",
            f"Rohaufnahme fehlt oder ist keine Datei: {raw_recording}",
        )
    if _same_file(raw_recording.parent, target_folder):
        return None

    target = _archive_target_for_raw_recording(raw_recording, target_folder)
    if target is None:
        return None

    try:
        ensure_folder(target_folder)
        if mode == RAW_ARCHIVE_MOVE:
            print("Wichtig: Beim Verschieben wird die Rohaufnahme aus dem Quellordner entfernt.")
            if not _ask_yes_no("Rohaufnahme wirklich verschieben?", False):
                return None
            _show_wait_status("Rohaufnahme wird verschoben.")
            shutil.move(str(raw_recording), str(target))
        elif mode == RAW_ARCHIVE_COPY:
            _show_wait_status("Rohaufnahme wird kopiert.")
            shutil.copy2(raw_recording, target)
        else:
            return None
    except PermissionError as exc:
        raise RawRecordingArchiveError(
            "Die Rohaufnahme konnte wegen fehlender Berechtigungen nicht übernommen werden.",
            f"Berechtigungsfehler bei Rohaufnahme '{raw_recording}' oder Ziel '{target}'. Details: {exc}",
        ) from exc
    except OSError as exc:
        raise RawRecordingArchiveError(
            "Die Rohaufnahme konnte nicht in den Zielordner übernommen werden.",
            f"Archivierung fehlgeschlagen von '{raw_recording}' nach '{target}'. Details: {exc}",
        ) from exc
    return target


def _maybe_archive_raw_recording(raw_recording: Path | None, plan: ProcessingPlan, config: AppConfig, log: WorkflowLog) -> None:
    if raw_recording is None:
        return
    if _same_file(raw_recording, plan.source_mp4):
        return
    if _same_file(raw_recording.parent, plan.target_mp4.parent):
        log.event("Rohaufnahme liegt bereits im Zielordner.")
        return

    mode = _ask_raw_archive_mode(raw_recording, plan.target_mp4.parent, config.raw_archive_mode)
    if mode == RAW_ARCHIVE_NONE:
        log.event("Rohaufnahme bleibt im Quellordner.")
        return
    try:
        archived_path = _archive_raw_recording(raw_recording, plan.target_mp4.parent, mode)
    except RawRecordingArchiveError as exc:
        log.error("Rohaufnahme konnte nicht archiviert werden.", admin_hint=exc.admin_hint)
        print()
        print(exc.user_message)
        print("Der lokale Workflow bleibt erfolgreich. Bitte räume die Rohaufnahme bei Bedarf später manuell auf.")
        print(f"Admin-Hinweis: {exc.admin_hint}")
        return

    if archived_path is None:
        log.event("Rohaufnahme wurde nicht archiviert.")
        print("Die Rohaufnahme bleibt am bisherigen Ort.")
        return
    action = "verschoben" if mode == RAW_ARCHIVE_MOVE else "kopiert"
    log.event(f"Rohaufnahme wurde {action}: {archived_path}")
    print(f"Die Rohaufnahme wurde {action}: {archived_path}")


def _print_config_load_error(exc: ConfigLoadError) -> None:
    print("Die Konfiguration konnte nicht geladen werden.")
    print(exc.user_message)
    print("Bitte prüfe den Pfad oder die Datei und starte den Wizard danach erneut.")
    print(f"Admin-Hinweis: {exc.admin_hint}")


def _save_user_settings(
    *,
    paths: dict[str, str] | None = None,
    naming: dict[str, str] | None = None,
    workflow: dict[str, str | bool] | None = None,
    service_types: list[str] | None = None,
) -> Path | None:
    try:
        saved_path = save_user_config_values(paths=paths, naming=naming, workflow=workflow, service_types=service_types)
    except ConfigLoadError as exc:
        print("Die Einstellung konnte nicht gespeichert werden.")
        print(f"Admin-Hinweis: {exc.admin_hint}")
        return None
    print(f"Einstellung gespeichert: {saved_path}")
    return saved_path


def _ask_folder_setting(prompt: str) -> Path:
    while True:
        raw = _ask_required(prompt)
        path = _normalize_user_path(raw)
        if _path_has_windows_invalid_chars(path):
            print("Dieser Pfad ist nicht gültig. Bitte keine Zeichen wie < > \" | ? * verwenden.")
            continue
        return path


def _year_folder_template_label(template: str) -> str:
    if template == "{year} Video+Audio":
        return "Jahresordner mit Zusatz, z. B. 2026 Video+Audio"
    return "Nur Jahr, z. B. 2026"


def _ask_year_folder_template(current_template: str) -> str:
    options = [
        MenuOption("Nur Jahr, z. B. 2026", "{year}", ("1", "jahr")),
        MenuOption("Jahresordner mit Zusatz, z. B. 2026 Video+Audio", "{year} Video+Audio", ("2", "video", "audio")),
    ]
    default_index = 1 if current_template == "{year} Video+Audio" else 0
    return choose_from_options("Wie soll der Jahresordner heißen?", options, default_index=default_index)


def _raw_archive_mode_label(mode: str) -> str:
    labels = {
        RAW_ARCHIVE_MOVE: "Rohaufnahme in Zielordner verschieben",
        RAW_ARCHIVE_NONE: "Rohaufnahme liegen lassen",
        RAW_ARCHIVE_COPY: "Rohaufnahme kopieren statt verschieben",
    }
    return labels.get(mode, labels[RAW_ARCHIVE_MOVE])


def _ask_raw_archive_setting(current_mode: str) -> RawArchiveMode:
    options = [
        MenuOption("Rohaufnahme in Zielordner verschieben", RAW_ARCHIVE_MOVE, ("v", "verschieben", "j", "ja")),
        MenuOption("Rohaufnahme liegen lassen", RAW_ARCHIVE_NONE, ("n", "nein", "liegen")),
        MenuOption("Rohaufnahme kopieren statt verschieben", RAW_ARCHIVE_COPY, ("k", "kopieren")),
    ]
    return choose_from_options(
        "Was soll nach erfolgreichem Lauf mit der Rohaufnahme vorgeschlagen werden?",
        options,
        default_index=_raw_archive_default_index(options, current_mode),
    )


def _encode_custom_service_type(service_type: ServiceTypeConfig) -> str:
    return "|".join(
        [
            service_type.name,
            "true" if service_type.requires_title else "false",
            "true" if service_type.requires_bible_reference else "false",
            "true" if service_type.requires_speaker else "false",
        ]
    )


def _ask_custom_service_type() -> ServiceTypeConfig:
    print()
    print("Neue Dienstart hinzufügen")
    print("Standard-Dienstarten bleiben immer erhalten.")
    name = _ask_required("Name der Dienstart")
    requires_title = _ask_yes_no("Braucht diese Dienstart einen Titel oder ein Thema?", True)
    requires_bible = _ask_yes_no("Braucht diese Dienstart eine Bibelstelle?", False)
    requires_speaker = _ask_yes_no("Braucht diese Dienstart einen Redner, Leiter oder Namen?", True)
    template = _automatic_custom_service_template(name, requires_title, requires_bible, requires_speaker)
    print(f"Dateinamen-Vorlage wird automatisch verwendet: {template}")
    return ServiceTypeConfig(name, requires_title, requires_bible, requires_speaker, template)


def _automatic_custom_service_template(name: str, requires_title: bool, requires_bible: bool, requires_speaker: bool) -> str:
    safe_name = sanitize_filename_part(name) or "Sonstiges"
    if requires_title and requires_bible:
        base = f"{safe_name} " + "({title}_{bible_reference})"
    elif requires_title:
        base = f"{safe_name} " + "({title})"
    elif requires_bible:
        base = f"{safe_name} " + "({bible_reference})"
    else:
        base = safe_name
    if requires_speaker:
        return base + "_{speaker}{extension}"
    return base + "{extension}"


def _run_service_types_settings(config: AppConfig) -> AppConfig:
    while True:
        print()
        print("Dienstarten verwalten")
        print("---------------------")
        print("Standard-Dienstarten:")
        for service_type in default_service_types(config):
            print(f"- {service_type.name}")
        if config.custom_service_types:
            print("Zusätzliche Dienstarten:")
            for service_type in config.custom_service_types:
                print(f"- {service_type.name}")
        else:
            print("Zusätzliche Dienstarten: keine")

        choice = choose_from_options(
            "Was möchtest du tun?",
            [
                MenuOption("Dienstart hinzufügen", "add", ("h", "hinzufuegen", "hinzufügen")),
                MenuOption("Zurück zu den Einstellungen", "back", ("z", "zurueck", "zurück")),
            ],
        )
        if choice == "back":
            return config
        new_service_type = _ask_custom_service_type()
        custom = config.custom_service_types + (new_service_type,)
        _save_user_settings(service_types=[_encode_custom_service_type(service_type) for service_type in custom])
        config = replace(config, custom_service_types=custom)


def _run_settings_menu(args: argparse.Namespace) -> int:
    explicit_config = Path(args.config) if args.config else None
    try:
        config = load_config(explicit_config)
    except ConfigLoadError as exc:
        _print_config_load_error(exc)
        return 6

    print()
    print("Einstellungen ändern")
    print("--------------------")
    print("Gespeichert wird in der Benutzer-Config:")
    path = user_config_path()
    print(path if path is not None else "%APPDATA% konnte nicht bestimmt werden.")
    print()
    print(f"Aktuell: Ziel-Basisordner: {config.recordings_base}")
    print(f"Aktuell: Rohaufnahme-Ordner: {config.vmix_storage}")
    print(f"Aktuell: LosslessCut-Pfad: {config.losslesscut_path or 'PATH/App-Alias'}")
    print(f"Aktuell: Jahresordner: {_year_folder_template_label(config.year_folder_template)}")
    print(f"Aktuell: Rohaufnahme nach Erfolg: {_raw_archive_mode_label(config.raw_archive_mode)}")
    print(f"Aktuell: zusätzliche Dienstarten: {len(config.custom_service_types)}")

    while True:
        choice = choose_from_options(
            "Welche Einstellung möchtest du ändern?",
            [
                MenuOption("Ziel-Basisordner", "recordings_base", ("ziel", "z")),
                MenuOption("Rohaufnahme-Ordner / vMixStorage", "vmix_storage", ("roh", "vmix", "v")),
                MenuOption("LosslessCut-Pfad", "losslesscut_path", ("losslesscut", "l")),
                MenuOption("Jahresordner-Format", "year_folder_template", ("jahr", "j")),
                MenuOption("Rohaufnahme nach Erfolg", "raw_archive_mode", ("aufraeumen", "a")),
                MenuOption("Dienstarten verwalten", "service_types", ("dienstart", "d")),
                MenuOption("Zurück zum Hauptmenü", "back", ("zurueck", "zurück", "b")),
            ],
        )
        if choice == "back":
            return 0
        if choice == "recordings_base":
            folder = _ask_folder_setting("Neuer Ziel-Basisordner")
            _save_user_settings(paths={"recordings_base": str(folder)})
            config = replace(config, recordings_base=folder)
        elif choice == "vmix_storage":
            folder = _ask_folder_setting("Neuer Rohaufnahme-Ordner / vMixStorage")
            _save_user_settings(paths={"vmix_storage": str(folder)})
            config = replace(config, vmix_storage=folder)
        elif choice == "losslesscut_path":
            path_value = _ask_losslesscut_exe_path()
            _save_user_settings(paths={"losslesscut_path": str(path_value)})
            config = replace(config, losslesscut_path=str(path_value))
        elif choice == "year_folder_template":
            template = _ask_year_folder_template(config.year_folder_template)
            _save_user_settings(naming={"year_folder_template": template})
            config = replace(config, year_folder_template=template)
        elif choice == "raw_archive_mode":
            mode = _ask_raw_archive_setting(config.raw_archive_mode)
            _save_user_settings(workflow={"raw_archive_mode": mode})
            config = replace(config, raw_archive_mode=mode)
        elif choice == "service_types":
            config = _run_service_types_settings(config)


def _latest_log_file(log_dir: Path) -> Path | None:
    if not log_dir.exists() or not log_dir.is_dir():
        return None
    logs = tuple(path for path in log_dir.glob("predigt-uploader-*.log") if path.is_file())
    if not logs:
        return None
    return max(logs, key=lambda path: path.stat().st_mtime)


def _open_path_safely(path: Path, description: str) -> None:
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except AttributeError:
        print(f"{description} kann auf diesem System nicht automatisch geöffnet werden: {path}")
    except OSError as exc:
        print(f"{description} konnte nicht automatisch geöffnet werden: {path}")
        print(f"Admin-Hinweis: {exc}")


def _open_latest_log_or_log_folder() -> None:
    log_dir = Path.cwd() / "logs"
    latest = _latest_log_file(log_dir)
    if latest is None:
        print("Es wurde noch keine Logdatei gefunden.")
        if _ask_yes_no("Logordner trotzdem öffnen?", True):
            log_dir.mkdir(parents=True, exist_ok=True)
            _open_path_safely(log_dir, "Logordner")
        return
    choice = choose_from_options(
        "Was möchtest du öffnen?",
        [
            MenuOption(f"Letzte Logdatei öffnen: {latest.name}", "file", ("datei", "log")),
            MenuOption("Logordner öffnen", "folder", ("ordner", "o")),
            MenuOption("Zurück", "back", ("zurueck", "zurück", "z")),
        ],
    )
    if choice == "file":
        _open_path_safely(latest, "Logdatei")
    elif choice == "folder":
        _open_path_safely(log_dir, "Logordner")


def _print_systemcheck_hint() -> None:
    print()
    print("Systemcheck")
    print("-----------")
    print("Für eine schnelle Prüfung doppelklicke im Projektordner:")
    print("PredigtUploader Systemcheck.cmd")
    print()
    print("Der Systemcheck prüft Python, die virtuelle Umgebung, den Wizard, FFmpeg und optional LosslessCut.")


def _print_app_header() -> None:
    print("PredigtUploader")
    print("================")
    print("Bereitet Predigtvideo, MP3 und Website-Dateien vor.")
    print("Es wird nichts zu Vimeo oder WordPress hochgeladen.")
    print("Strg+C bricht den Vorgang ab. Zum Zurückgehen bitte die Option 'Zurück' verwenden.")
    print()


def run_wizard(args: argparse.Namespace) -> int:
    explicit_config = Path(args.config) if args.config else None
    log = WorkflowLog.start(config_path=describe_config_source(explicit_config))
    log.event("Wizard gestartet.")
    try:
        config = load_config(explicit_config)
    except ConfigLoadError as exc:
        log.error("Konfiguration konnte nicht geladen werden.", admin_hint=exc.admin_hint)
        log.finish("Abbruch wegen Config-Fehler.")
        _print_config_load_error(exc)
        return 6
    log.event("Konfiguration geladen.")

    _print_app_header()

    config = _select_recordings_base(config)
    log.event(f"Ziel-Basisordner vorbereitet: {config.recordings_base}")

    source, raw_recording = _select_source_mp4_for_workflow(config, log)
    log.event(f"Quell-MP4 ausgewaehlt: {source}")

    sermon_date = _ask_sermon_date(source)
    info = _ask_sermon_metadata(config, sermon_date)
    log.event(f"Dienstart ausgewaehlt: {info.sermon_type}")

    selected = _select_target_folder(config, info)
    if selected is None:
        log.finish("Abbruch bei Zielordner-Auswahl.")
        print("Abgebrochen.")
        return 1
    target_folder, info = selected
    log.event(f"Zielordner ausgewaehlt: {target_folder}")

    target_mp4 = target_folder / build_media_filename(info, config, ".mp4")
    target_mp3 = target_folder / build_media_filename(info, config, ".mp3")
    plan = ProcessingPlan(source_mp4=source, target_mp4=target_mp4, target_mp3=target_mp3, info=info)
    log.plan(plan)

    existing_choice = _handle_existing_target_mp4(plan)
    if existing_choice is None:
        log.finish("Abbruch wegen vorhandener Zieldatei.")
        print("Abgebrochen.")
        return 1
    plan, mp4_transfer_mode = existing_choice
    if mp4_transfer_mode == MP4_TRANSFER_KEEP:
        log.event("Vorhandene MP4 wird behalten.")
    elif mp4_transfer_mode == MP4_TRANSFER_OVERWRITE:
        log.event("Vorhandene MP4 wird nach doppelter Bestaetigung ueberschrieben.")
    else:
        log.event("MP4-Uebernahme wird vorbereitet.")
    log.plan(plan)

    print()
    print(build_summary_text(plan))
    _print_mp4_action_preview(plan, config, mp4_transfer_mode)
    if mp4_transfer_mode == MP4_TRANSFER_KEEP:
        print("Hinweis: Die vorhandene MP4 wird behalten. Es wird nichts kopiert oder verschoben.")
    elif mp4_transfer_mode == MP4_TRANSFER_OVERWRITE:
        print("Hinweis: Die vorhandene MP4 wird beim nächsten Schritt ersetzt.")
    print()
    if not _ask_yes_no("MP4-Datei jetzt so übernehmen?", False):
        log.finish("Abbruch vor MP4-Uebernahme.")
        print("Abgebrochen.")
        return 1

    try:
        _transfer_mp4_to_target(
            plan,
            config,
            keep_existing=mp4_transfer_mode == MP4_TRANSFER_KEEP,
            overwrite_existing=mp4_transfer_mode == MP4_TRANSFER_OVERWRITE,
        )
    except Mp4TransferError as exc:
        log.error("MP4 konnte nicht uebernommen werden.", admin_hint=exc.admin_hint)
        log.finish("Abbruch bei MP4-Uebernahme.")
        _print_mp4_transfer_error(exc)
        return 2
    log.event("MP4-Uebernahme abgeschlossen.")

    if not ffmpeg_available(config):
        log.error(
            "FFmpeg ist nicht verfuegbar.",
            admin_hint=f"ffmpeg_path: {config.ffmpeg_path!r}",
        )
        log.finish("Abbruch vor MP3-Erzeugung.")
        _print_missing_ffmpeg_message(plan, config)
        return 3
    log.event("FFmpeg ist verfuegbar.")

    try:
        _show_wait_status("MP3 wird erstellt.")
        convert_mp4_to_mp3(plan.target_mp4, plan.target_mp3, config)
        _validate_created_mp3(plan.target_mp3)
        print(f"Die MP3 wurde erstellt: {plan.target_mp3}")
        log.event("MP3-Erzeugung abgeschlossen und geprueft.")
    except Mp3ConversionError as exc:
        log.error("MP3 konnte nicht erstellt werden.", admin_hint=str(exc))
        log.finish("Abbruch bei MP3-Erzeugung.")
        _print_mp3_creation_error(
            plan,
            "Die MP3 konnte nicht erstellt werden.",
            str(exc),
        )
        return 3
    except Mp3ResultError as exc:
        log.error("MP3-Ergebnis ist ungueltig.", admin_hint=exc.admin_hint)
        log.finish("Abbruch bei MP3-Pruefung.")
        _print_mp3_creation_error(
            plan,
            exc.user_message,
            exc.admin_hint,
        )
        return 3

    try:
        summary_path = _write_summary_file_safely(plan)
        print("Die Zusammenfassung wurde geschrieben: predigt-zusammenfassung.txt")
        log.event(f"Zusammenfassung geschrieben: {summary_path}")
    except SummaryWriteError as exc:
        log.error("Zusammenfassung konnte nicht geschrieben werden.", admin_hint=exc.admin_hint)
        log.finish("Abbruch beim Schreiben der Zusammenfassung.")
        _print_summary_write_error(plan, exc)
        return 4

    try:
        _validate_local_workflow_result(plan)
    except Mp3ResultError as exc:
        log.error("Lokaler Workflow-Endzustand ist ungueltig.", admin_hint=exc.admin_hint)
        log.finish("Abbruch bei Workflow-Endpruefung.")
        print()
        print(exc.user_message)
        print("Bitte prüfe die Dateien im Zielordner, bevor du weitermachst.")
        print(f"Admin-Hinweis: {exc.admin_hint}")
        return 5
    log.event("Lokaler Workflow-Endzustand geprueft.")

    _maybe_archive_raw_recording(raw_recording, plan, config, log)
    _print_local_workflow_success(plan, summary_path)
    _open_target_folder_safely(config, plan.target_mp4.parent, log)
    if log.enabled:
        print(f"Logdatei: {log.path}")
    log.finish("Workflow erfolgreich abgeschlossen.")
    return 0


def run_start_menu(args: argparse.Namespace) -> int:
    _print_app_header()
    while True:
        choice = choose_from_options(
            "Was möchtest du tun?",
            [
                MenuOption("Neue Aufnahme vorbereiten", "wizard", ("aufnahme", "predigt", "neu", "n")),
                MenuOption("Einstellungen ändern", "settings", ("einstellungen", "e")),
                MenuOption("Systemcheck-Hinweis anzeigen", "systemcheck", ("systemcheck", "s")),
                MenuOption("Letzte Logdatei öffnen oder Logordner öffnen", "logs", ("logs", "l")),
                MenuOption("Beenden", "exit", ("beenden", "b", "q")),
            ],
        )
        if choice == "wizard":
            return run_wizard(args)
        if choice == "settings":
            result = _run_settings_menu(args)
            if result != 0:
                return result
            print()
            continue
        if choice == "systemcheck":
            _print_systemcheck_hint()
            print()
            continue
        if choice == "logs":
            _open_latest_log_or_log_folder()
            print()
            continue
        print("Beendet.")
        return 0


def run_tui_command(args: argparse.Namespace) -> int:
    try:
        from .tui_app import run_tui
        return run_tui(config_path=args.config)
    except ConfigLoadError as exc:
        _print_config_load_error(exc)
        return 6
    except ImportError:
        print("Die neue Oberfläche ist nicht installiert. Bitte setup ausführen oder den normalen Wizard verwenden.")
        return 7


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="predigt-uploader")
    parser.add_argument("command", nargs="?", default="menu", choices=["menu", "wizard", "tui", "textual"])
    parser.add_argument("--config", help="Pfad zu config.toml")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "menu":
            return run_start_menu(args)
        if args.command == "wizard":
            return run_wizard(args)
        if args.command in {"tui", "textual"}:
            return run_tui_command(args)
        parser.print_help()
        return 1
    except (KeyboardInterrupt, UserAbortError):
        print()
        print("Abgebrochen.")
        return 130
