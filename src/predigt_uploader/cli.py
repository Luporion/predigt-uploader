from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .config import ConfigLoadError, load_config
from .filename import build_media_filename, sanitize_filename_part
from .folders import ensure_folder, resolve_folder
from .models import AppConfig, ProcessingPlan, SermonInfo
from .mp3 import Mp3ConversionError, convert_mp4_to_mp3, ffmpeg_available
from .report import build_summary_text, write_summary_file
from .run_log import WorkflowLog
from .ui import MenuOption, UserAbortError, ask_yes_no, choose_from_options


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


def _ask_date() -> datetime.date:
    while True:
        raw = _ask("Datum der Predigt (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d"))
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            print("Bitte Datum im Format YYYY-MM-DD eingeben, z. B. 2026-05-24.")


def _normalize_user_path(raw_path: str) -> Path:
    return Path(raw_path.strip().strip('"')).expanduser()


def _ask_mp4_path() -> Path:
    while True:
        raw = _ask_required("Pfad zur geschnittenen MP4-Datei")
        source = _normalize_user_path(raw)
        if _is_valid_mp4_file(source):
            return source


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
    while True:
        raw = _ask_required(prompt)
        source = _normalize_user_path(raw)
        if _is_valid_mp4_file(source):
            return source


def _newest_mp4_in_folder(folder: Path) -> Path | None:
    if not folder.exists() or not folder.is_dir():
        return None
    candidates = [path for path in folder.glob("*.mp4") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _ask_raw_recording(config: AppConfig) -> Path:
    print()
    print("Rohaufnahme auswählen")
    print(f"Konfigurierter Quellordner: {config.vmix_storage}")
    suggestion = _newest_mp4_in_folder(config.vmix_storage)
    if suggestion is not None:
        print(f"Neueste MP4 im Quellordner: {suggestion}")
        if _ask_yes_no("Diese Rohaufnahme in LosslessCut öffnen?", True):
            return suggestion
    else:
        print("Im konfigurierten Quellordner wurde keine MP4 gefunden.")

    return _ask_mp4_path_with_prompt("Pfad zur vMix-Rohaufnahme")


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
        raw = _ask_required("Pfad zur LosslessCut.exe")
        path = _normalize_user_path(raw)
        if not path.exists():
            print("Diese Datei wurde nicht gefunden. Bitte den vollständigen Pfad zur LosslessCut.exe eingeben.")
            continue
        if not path.is_file():
            print("Das ist ein Ordner, keine Programmdatei. Bitte die Datei LosslessCut.exe auswählen.")
            continue
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


def _choose_exported_mp4(candidates: tuple[Path, ...]) -> Path:
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
    return _ask_mp4_path_with_prompt("Pfad zur exportierten Predigt-MP4")


def _select_exported_mp4(config: AppConfig, raw_recording: Path, assistant_start: datetime) -> Path:
    print()
    print("Exportierte Predigt-MP4 übernehmen")
    print("Wenn der Export in LosslessCut fertig ist, sucht der Wizard nach neuen MP4-Dateien.")
    _ask("Drücke Enter, sobald der Export fertig ist")
    folders = _export_search_folders(config, raw_recording)
    candidates = _find_new_mp4_exports(folders, assistant_start)
    return _choose_exported_mp4(candidates)


def _select_source_mp4(config: AppConfig, log: WorkflowLog) -> Path:
    if _ask_yes_no("Hast du bereits eine fertig geschnittene MP4-Datei?", True):
        return _ask_mp4_path()

    assistant_start = datetime.now()
    raw_recording = _ask_raw_recording(config)
    log.event(f"Rohaufnahme fuer LosslessCut ausgewaehlt: {raw_recording}")
    _try_start_losslesscut(raw_recording, config, log)

    _print_losslesscut_instructions()
    exported_mp4 = _select_exported_mp4(config, raw_recording, assistant_start)
    log.event(f"Exportierte MP4 ausgewaehlt: {exported_mp4}")
    return exported_mp4


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


def _print_mp4_action_preview(plan: ProcessingPlan, config: AppConfig) -> None:
    print()
    print("MP4-Datei übernehmen")
    print("--------------------")
    print(f"Quell-Datei: {plan.source_mp4}")
    print(f"Zielordner: {plan.target_mp4.parent}")
    print(f"Finaler MP4-Dateiname: {plan.target_mp4.name}")
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


def _handle_existing_target_mp4(plan: ProcessingPlan) -> tuple[ProcessingPlan, bool] | None:
    if not plan.target_mp4.exists():
        return plan, False

    print()
    print("Die Zieldatei existiert bereits.")
    print(f"Vorhandene Datei: {plan.target_mp4}")
    print("Sie wird nicht automatisch überschrieben.")
    print("Optionen:")
    print("  a = abbrechen")
    print("  b = vorhandene Datei behalten und ohne Kopieren/Verschieben weiterarbeiten")
    print("  n = neuen Dateinamen verwenden")
    choice = _ask_choice(
        "Was soll passieren?",
        {"a": "abbrechen", "b": "behalten", "n": "neu"},
        "a",
    )
    if choice == "a":
        return None
    if choice == "b":
        return plan, True

    target_mp4 = _ask_new_mp4_target(plan.target_mp4)
    target_mp3 = target_mp4.with_suffix(".mp3")
    return replace(plan, target_mp4=target_mp4, target_mp3=target_mp3), False


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


def _transfer_mp4_to_target(plan: ProcessingPlan, config: AppConfig, *, keep_existing: bool = False) -> None:
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

    if plan.target_mp4.exists():
        raise Mp4TransferError(
            "Die Zieldatei existiert bereits.",
            f"Zieldatei existiert vor der Dateiübernahme: {plan.target_mp4}",
        )

    try:
        if config.copy_instead_of_move:
            shutil.copy2(plan.source_mp4, plan.target_mp4)
            print(f"Die MP4 wurde kopiert: {plan.target_mp4}")
        else:
            shutil.move(str(plan.source_mp4), str(plan.target_mp4))
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

    source = _select_source_mp4(config, log)
    log.event(f"Quell-MP4 ausgewaehlt: {source}")

    sermon_date = _ask_date()
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
    plan, keep_existing_mp4 = existing_choice
    if keep_existing_mp4:
        log.event("Vorhandene MP4 wird behalten.")
    else:
        log.event("MP4-Uebernahme wird vorbereitet.")
    log.plan(plan)

    print()
    print(build_summary_text(plan))
    _print_mp4_action_preview(plan, config)
    if keep_existing_mp4:
        print("Hinweis: Die vorhandene MP4 wird behalten. Es wird nichts kopiert oder verschoben.")
    print()
    if not _ask_yes_no("MP4-Datei jetzt so übernehmen?", False):
        log.finish("Abbruch vor MP4-Uebernahme.")
        print("Abgebrochen.")
        return 1

    try:
        _transfer_mp4_to_target(plan, config, keep_existing=keep_existing_mp4)
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

    _print_local_workflow_success(plan, summary_path)
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
