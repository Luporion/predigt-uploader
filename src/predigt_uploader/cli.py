from __future__ import annotations

import argparse
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .config import load_config
from .filename import build_media_filename
from .folders import ensure_folder, resolve_folder
from .models import AppConfig, ProcessingPlan, SermonInfo
from .mp3 import Mp3ConversionError, convert_mp4_to_mp3
from .report import build_summary_text, write_summary_files


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

    print()
    print(build_summary_text(plan))
    print()
    if not _ask_yes_no("Sollen diese Schritte jetzt ausgeführt werden?", False):
        print("Abgebrochen.")
        return 1

    ensure_folder(target_folder)
    if config.copy_instead_of_move:
        shutil.copy2(source, target_mp4)
        print(f"Die MP4 wurde kopiert: {target_mp4}")
    else:
        shutil.move(str(source), str(target_mp4))
        print(f"Die MP4 wurde verschoben: {target_mp4}")

    try:
        convert_mp4_to_mp3(target_mp4, target_mp3, config)
        print(f"Die MP3 wurde erstellt: {target_mp3}")
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
