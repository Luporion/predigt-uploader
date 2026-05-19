from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from .config import ConfigLoadError, load_config
from .filename import build_media_filename, sanitize_filename_part
from .folders import ensure_folder, resolve_folder
from .models import AppConfig, ProcessingPlan, SermonInfo
from .mp3 import Mp3ConversionError, convert_mp4_to_mp3, ffmpeg_available
from .report import build_summary_text, write_summary_file
from .run_log import WorkflowLog
from .ui import MenuOption, UserAbortError, ask_file_path, ask_yes_no, choose_from_options


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

    current_path = _ask_initial_recordings_base_path(config.recordings_base)

    while True:
        try:
            if _prepare_recordings_base(current_path):
                print(f"Ziel-Basisordner ist bereit: {current_path}")
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
        raw = _ask("Datum der Predigt (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d"))
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
    print("Datum der Predigt auswählen")
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
        return ()
    matches = tuple(path for path in _mp4_files_sorted(folder) if normalized in path.name.casefold())
    return _limit_file_list(matches, limit)


def _choose_mp4_from_list(prompt: str, files: tuple[Path, ...], *, overflow_count: int = 0) -> Path | None:
    if not files:
        print("Es wurden keine passenden MP4-Dateien gefunden.")
        return None
    if overflow_count > 0:
        print(f"Hinweis: Es gibt {overflow_count} weitere Treffer. Bitte Suchtext genauer eingeben, wenn die Datei nicht dabei ist.")
    selected = choose_from_options(
        prompt,
        [MenuOption(_format_file_choice(path), path) for path in files]
        + [MenuOption("Zurück", None, ("z", "zurueck", "zurück"))],
    )
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
                return path
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
    while True:
        search_text = _ask_required("Suchtext im Dateinamen")
        all_matches = tuple(path for path in _mp4_files_sorted(folder) if search_text.casefold() in path.name.casefold())
        matches = _limit_file_list(all_matches, SEARCH_RESULT_LIMIT)
        selected = _choose_mp4_from_list(
            "Passende MP4-Datei auswählen",
            matches,
            overflow_count=max(0, len(all_matches) - len(matches)),
        )
        if selected is not None:
            return selected
        if not _ask_yes_no("Noch einmal suchen?", True):
            return None


def _ask_raw_recording(config: AppConfig) -> Path:
    print()
    print("Rohaufnahme auswählen")
    print(f"Konfigurierter Quellordner: {config.vmix_storage}")
    if not config.vmix_storage.exists() or not config.vmix_storage.is_dir():
        print("Der konfigurierte Rohaufnahme-Ordner wurde nicht gefunden.")
        print("Du kannst die Rohaufnahme trotzdem manuell auswählen.")
        print(f"Admin-Hinweis: vmix_storage existiert nicht oder ist kein Ordner: {config.vmix_storage}")
        return _ask_mp4_path_or_limited_folder("Pfad zur vMix-Rohaufnahme oder zu einem Ordner")

    files = _mp4_files_sorted(config.vmix_storage)
    if not files:
        print("Im konfigurierten Rohaufnahme-Ordner wurde keine MP4 gefunden.")
        return _ask_mp4_path_or_limited_folder("Pfad zur vMix-Rohaufnahme oder zu einem Ordner")

    newest = files[0]
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
            return newest
        if choice == "recent":
            shown = _limit_file_list(files, RECENT_MP4_LIMIT)
            selected = _choose_mp4_from_list(
                "Rohaufnahme auswählen",
                shown,
                overflow_count=max(0, len(files) - len(shown)),
            )
            if selected is not None:
                return selected
        elif choice == "search":
            selected = _ask_search_mp4_in_folder(config.vmix_storage)
            if selected is not None:
                return selected
        elif choice == "manual":
            return _ask_mp4_path_or_limited_folder("Pfad zur vMix-Rohaufnahme oder zu einem Ordner")
        else:
            raise UserAbortError("Abbruch durch Nutzer.")


def _losslesscut_command(config: AppConfig) -> str:
    configured = config.losslesscut_path.strip()
    return configured or "LosslessCut"


def _losslesscut_source_label(config: AppConfig) -> str:
    return "config.toml" if config.losslesscut_path.strip() else "PATH/App-Alias"


def _open_losslesscut(raw_recording: Path, config: AppConfig) -> None:
    command = _losslesscut_command(config)
    try:
        subprocess.Popen([command, str(raw_recording)])
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


def _try_start_losslesscut(raw_recording: Path, config: AppConfig, log: WorkflowLog) -> None:
    log.event(f"LosslessCut-Startversuch ueber {_losslesscut_source_label(config)}: {_losslesscut_command(config)!r}")
    try:
        _open_losslesscut(raw_recording, config)
        log.event("LosslessCut wurde gestartet.")
        return
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
        try:
            _open_losslesscut(raw_recording, manual_config)
            log.event("LosslessCut wurde mit manuellem Pfad gestartet.")
            return
        except LosslessCutStartError as exc:
            log.error("LosslessCut konnte auch mit manuellem Pfad nicht gestartet werden.", admin_hint=exc.admin_hint)
            print()
            print("LosslessCut konnte auch mit diesem Pfad nicht gestartet werden.")
            print("Bitte öffne LosslessCut manuell und lade dort die Rohaufnahme.")
            print(f"Admin-Hinweis: {exc.admin_hint}")
    else:
        log.event("Nutzer ueberspringt manuellen LosslessCut-Pfad.")

    print(f"Rohaufnahme: {raw_recording}")


def _print_losslesscut_instructions() -> None:
    print()
    print("Bitte jetzt in LosslessCut schneiden")
    print("-----------------------------------")
    print("- Markiere nur den Predigtbereich.")
    print("- Exportiere nur die Predigt als MP4.")
    print("- Chorlieder, Beiträge oder Ansagen nicht als Predigtdatei verwenden.")
    print("- Komm danach zu diesem Wizard zurück.")


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


def _prioritize_export_candidates(candidates: tuple[Path, ...]) -> tuple[Path, ...]:
    return tuple(
        sorted(
            candidates,
            key=lambda path: (0 if _is_cut_export(path) else 1, -path.stat().st_mtime),
        )
    )


def _manual_export_candidates(folder: Path, assistant_start: datetime) -> tuple[Path, ...]:
    files = _mp4_files_sorted(folder)
    new_files = tuple(path for path in files if path.stat().st_mtime >= assistant_start.timestamp())
    if new_files:
        print("In diesem Ordner wurden neue MP4-Dateien seit Start des Assistenten gefunden.")
        return new_files
    print("Keine neuen MP4-Dateien seit Start des Assistenten gefunden.")
    print("Ich zeige bevorzugt neue und geschnittene Dateien, nicht die ganze alte Liste.")
    return _prioritize_export_candidates(files)


def _choose_exported_mp4(candidates: tuple[Path, ...]) -> Path:
    candidates = _prioritize_export_candidates(candidates)
    if len(candidates) == 1:
        candidate = candidates[0]
        print(f"Gefundene neue MP4: {candidate}")
        if _ask_yes_no("Diese exportierte Predigtdatei verwenden?", True):
            return candidate

    if len(candidates) > 1:
        print("Es wurden mehrere neue MP4-Dateien gefunden.")
        print("Bitte wähle bewusst die Datei aus, die nur die Predigt enthält.")
        return choose_from_options(
            "Richtige Predigtdatei auswählen",
            [MenuOption(str(candidate), candidate) for candidate in candidates],
        )

    print("Es wurde keine passende neue MP4 automatisch ausgewählt.")
    return _ask_mp4_path_or_limited_folder("Pfad zur exportierten Predigt-MP4 oder zu einem Ordner", folder_prompt="Exportierte Predigt-MP4 auswählen")


def _ask_exported_mp4_manually(assistant_start: datetime) -> Path:
    while True:
        raw = _ask_required("Pfad zur exportierten Predigt-MP4 oder zu einem Ordner")
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
            "Exportierte Predigt-MP4 auswählen",
            shown,
            overflow_count=max(0, len(candidates) - len(shown)),
        )
        if selected is not None:
            return selected
        if _ask_yes_no("In diesem Ordner suchen/filtern?", True):
            searched = _ask_search_mp4_in_folder(path)
            if searched is not None:
                return searched


def _select_exported_mp4(config: AppConfig, raw_recording: Path, assistant_start: datetime) -> Path:
    print()
    print("Exportierte Predigt-MP4 übernehmen")
    print("Wenn der Export in LosslessCut fertig ist, sucht der Wizard nach neuen MP4-Dateien.")
    _ask("Drücke Enter, sobald der Export fertig ist")
    folders = _export_search_folders(config, raw_recording)
    candidates = _find_new_mp4_exports(folders, assistant_start)
    if candidates:
        return _choose_exported_mp4(candidates)
    print("Es wurde keine passende neue MP4 automatisch ausgewählt.")
    return _ask_exported_mp4_manually(assistant_start)


def _select_source_mp4_for_workflow(config: AppConfig, log: WorkflowLog) -> tuple[Path, Path | None]:
    if _ask_yes_no("Hast du bereits eine fertig geschnittene MP4-Datei?", True):
        return _ask_mp4_path(), None

    assistant_start = datetime.now()
    raw_recording = _ask_raw_recording(config)
    log.event(f"Rohaufnahme fuer LosslessCut ausgewaehlt: {raw_recording}")
    _try_start_losslesscut(raw_recording, config, log)

    _print_losslesscut_instructions()
    exported_mp4 = _select_exported_mp4(config, raw_recording, assistant_start)
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
        print("Bitte wähle bewusst den Ordner aus, in dem die Predigt gespeichert werden soll.")
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
            shutil.copy2(plan.source_mp4, plan.target_mp4)
            if overwrite_existing:
                print(f"Die vorhandene MP4 wurde überschrieben: {plan.target_mp4}")
            else:
                print(f"Die MP4 wurde kopiert: {plan.target_mp4}")
        else:
            if overwrite_existing and plan.target_mp4.exists():
                plan.target_mp4.unlink()
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


def _ask_raw_archive_mode(raw_recording: Path, target_folder: Path) -> RawArchiveMode:
    if _same_file(raw_recording.parent, target_folder):
        return RAW_ARCHIVE_NONE
    print()
    print("Rohaufnahme aufräumen")
    print(f"Rohaufnahme: {raw_recording}")
    print(f"Zielordner: {target_folder}")
    return choose_from_options(
        "Rohaufnahme in den Zielordner verschieben, damit vMixStorage frei bleibt?",
        [
            MenuOption("Nein, Rohaufnahme liegen lassen", RAW_ARCHIVE_NONE, ("n", "nein")),
            MenuOption("Ja, Rohaufnahme in Zielordner verschieben", RAW_ARCHIVE_MOVE, ("v", "verschieben")),
            MenuOption("Rohaufnahme kopieren statt verschieben", RAW_ARCHIVE_COPY, ("k", "kopieren")),
        ],
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
            shutil.move(str(raw_recording), str(target))
        elif mode == RAW_ARCHIVE_COPY:
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


def _maybe_archive_raw_recording(raw_recording: Path | None, plan: ProcessingPlan, log: WorkflowLog) -> None:
    if raw_recording is None:
        return
    if _same_file(raw_recording, plan.source_mp4):
        return
    if _same_file(raw_recording.parent, plan.target_mp4.parent):
        log.event("Rohaufnahme liegt bereits im Zielordner.")
        return

    mode = _ask_raw_archive_mode(raw_recording, plan.target_mp4.parent)
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


def run_wizard(args: argparse.Namespace) -> int:
    log = WorkflowLog.start(config_path=args.config)
    log.event("Wizard gestartet.")
    try:
        config = load_config(Path(args.config) if args.config else None)
    except ConfigLoadError as exc:
        log.error("Konfiguration konnte nicht geladen werden.", admin_hint=exc.admin_hint)
        log.finish("Abbruch wegen Config-Fehler.")
        _print_config_load_error(exc)
        return 6
    log.event("Konfiguration geladen.")

    print("PredigtUploader – lokaler Version-1-Prototyp")
    print("============================================")
    print("Dieses Programm bereitet die Dateien nur lokal vor. Es lädt nichts zu Vimeo oder WordPress hoch.")
    print()

    config = _select_recordings_base(config)
    log.event(f"Ziel-Basisordner vorbereitet: {config.recordings_base}")

    source, raw_recording = _select_source_mp4_for_workflow(config, log)
    log.event(f"Quell-MP4 ausgewaehlt: {source}")

    sermon_date = _ask_sermon_date(source)
    title = _ask_required("Predigttitel")
    bible_reference = _ask_required("Hauptbibelstelle")
    speaker = _ask_required("Redner Vorname Nachname")
    folder_note = _ask_optional_folder_note()

    info = SermonInfo(
        sermon_date=sermon_date,
        title=title,
        bible_reference=bible_reference,
        speaker=speaker,
        folder_note=folder_note,
    )

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

    _maybe_archive_raw_recording(raw_recording, plan, log)
    _print_local_workflow_success(plan, summary_path)
    _open_target_folder_safely(config, plan.target_mp4.parent, log)
    if log.enabled:
        print(f"Logdatei: {log.path}")
    log.finish("Workflow erfolgreich abgeschlossen.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="predigt-uploader")
    parser.add_argument("command", nargs="?", default="wizard", choices=["wizard"])
    parser.add_argument("--config", help="Pfad zu config.toml")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "wizard":
            return run_wizard(args)
        parser.print_help()
        return 1
    except (KeyboardInterrupt, UserAbortError):
        print()
        print("Abgebrochen.")
        return 130
