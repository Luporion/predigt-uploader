from __future__ import annotations

import argparse
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .config import load_config
from .filename import build_media_filename, sanitize_filename_part
from .folders import ensure_folder, resolve_folder
from .models import AppConfig, ProcessingPlan, SermonInfo
from .mp3 import Mp3ConversionError, convert_mp4_to_mp3
from .report import build_summary_text, write_summary_files


class Mp4TransferError(RuntimeError):
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
    default_text = "j" if default else "n"
    while True:
        value = _ask(prompt, default_text).casefold()
        if value in {"j", "ja"}:
            return True
        if value in {"n", "nein"}:
            return False
        print("Bitte mit j für Ja oder n für Nein antworten.")


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
        if not source.exists():
            print("Diese Datei wurde nicht gefunden. Bitte den vollständigen Pfad zur MP4 einfügen.")
            continue
        if not source.is_file():
            print("Das ist ein Ordner, keine Datei. Bitte die geschnittene MP4-Datei auswählen.")
            continue
        if source.suffix.casefold() != ".mp4":
            print("Diese Datei ist keine MP4-Datei. Bitte eine Datei mit der Endung .mp4 auswählen.")
            continue
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


def run_wizard(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config) if args.config else None)

    print("PredigtUploader – lokaler Version-1-Prototyp")
    print("============================================")
    print("Dieses Programm bereitet die Dateien nur lokal vor. Es lädt nichts zu Vimeo oder WordPress hoch.")
    print()

    source = _ask_mp4_path()

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
        print("Abgebrochen.")
        return 1
    target_folder, info = selected

    target_mp4 = target_folder / build_media_filename(info, config, ".mp4")
    target_mp3 = target_folder / build_media_filename(info, config, ".mp3")
    plan = ProcessingPlan(source_mp4=source, target_mp4=target_mp4, target_mp3=target_mp3, info=info)

    existing_choice = _handle_existing_target_mp4(plan)
    if existing_choice is None:
        print("Abgebrochen.")
        return 1
    plan, keep_existing_mp4 = existing_choice

    print()
    print(build_summary_text(plan))
    _print_mp4_action_preview(plan, config)
    if keep_existing_mp4:
        print("Hinweis: Die vorhandene MP4 wird behalten. Es wird nichts kopiert oder verschoben.")
    print()
    if not _ask_yes_no("MP4-Datei jetzt so übernehmen?", False):
        print("Abgebrochen.")
        return 1

    try:
        _transfer_mp4_to_target(plan, config, keep_existing=keep_existing_mp4)
    except Mp4TransferError as exc:
        _print_mp4_transfer_error(exc)
        return 2

    try:
        convert_mp4_to_mp3(plan.target_mp4, plan.target_mp3, config)
        print(f"Die MP3 wurde erstellt: {plan.target_mp3}")
    except Mp3ConversionError as exc:
        print()
        print("Die MP3 konnte nicht erstellt werden.")
        print("Bitte erstelle die MP3 notfalls manuell mit File Converter oder Shutter Encoder.")
        print(f"Admin-Hinweis: {exc}")
        return 3

    if config.write_summary_file:
        write_summary_files(plan)
        print("Die Zusammenfassung wurde geschrieben: predigt-zusammenfassung.txt und predigt-info.json")

    print("Fertig.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="predigt-uploader")
    parser.add_argument("command", nargs="?", default="wizard", choices=["wizard"])
    parser.add_argument("--config", help="Pfad zu config.toml")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "wizard":
        return run_wizard(args)
    parser.print_help()
    return 1
