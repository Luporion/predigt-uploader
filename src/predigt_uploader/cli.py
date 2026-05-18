from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from .config import load_config
from .filename import build_media_filename
from .folders import ensure_folder, resolve_folder
from .models import ProcessingPlan, SermonInfo
from .mp3 import Mp3ConversionError, convert_mp4_to_mp3
from .report import build_summary_text, write_summary_files


def _ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or (default or "")


def _ask_date() -> datetime.date:
    while True:
        raw = _ask("Datum der Predigt (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d"))
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            print("Bitte Datum im Format YYYY-MM-DD eingeben, z. B. 2026-05-24.")


def run_wizard(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config) if args.config else None)

    print("PredigtUploader – lokaler Version-1-Prototyp")
    print("============================================")
    print()

    source = Path(_ask("Pfad zur geschnittenen MP4-Datei"))
    if not source.exists() or source.suffix.lower() != ".mp4":
        print("Die angegebene Datei existiert nicht oder ist keine MP4-Datei.")
        return 2

    sermon_date = _ask_date()
    title = _ask("Predigttitel")
    bible_reference = _ask("Hauptbibelstelle")
    speaker = _ask("Redner Vorname Nachname")
    has_note = _ask("Besonderheit im Ordnernamen? (j/n)", "n").casefold().startswith("j")
    folder_note = _ask("Besonderheit, z. B. Pfingsten/Gastredner/Themenreihe") if has_note else ""

    info = SermonInfo(
        sermon_date=sermon_date,
        title=title,
        bible_reference=bible_reference,
        speaker=speaker,
        folder_note=folder_note,
    )

    resolution = resolve_folder(config, info)
    print()
    print(f"Ziel-Jahresordner: {resolution.year_folder}")

    if resolution.status == "multiple_existing":
        print("Mehrere Ordner für dieses Datum gefunden:")
        for index, candidate in enumerate(resolution.candidates, start=1):
            print(f"  {index}. {candidate}")
        print("Bitte den passenden Ordner auswählen oder Vorgang abbrechen.")
        choice = int(_ask("Nummer des Zielordners"))
        target_folder = resolution.candidates[choice - 1]
    elif resolution.status == "single_existing" and not folder_note:
        target_folder = resolution.candidates[0]
        print(f"Vorhandener Ordner wird verwendet: {target_folder}")
    else:
        target_folder = resolution.suggested_folder
        print(f"Zielordner: {target_folder}")

    target_mp4 = target_folder / build_media_filename(info, config, ".mp4")
    target_mp3 = target_folder / build_media_filename(info, config, ".mp3")
    plan = ProcessingPlan(source_mp4=source, target_mp4=target_mp4, target_mp3=target_mp3, info=info)

    print()
    print(build_summary_text(plan))
    print()
    if not _ask("So ausführen? (j/n)", "n").casefold().startswith("j"):
        print("Abgebrochen.")
        return 1

    ensure_folder(target_folder)
    if config.copy_instead_of_move:
        shutil.copy2(source, target_mp4)
        print(f"MP4 kopiert nach: {target_mp4}")
    else:
        shutil.move(str(source), str(target_mp4))
        print(f"MP4 verschoben nach: {target_mp4}")

    try:
        convert_mp4_to_mp3(target_mp4, target_mp3, config)
        print(f"MP3 erstellt: {target_mp3}")
    except Mp3ConversionError as exc:
        print()
        print("Die MP3 konnte nicht erstellt werden.")
        print("Bitte erstelle die MP3 notfalls manuell mit File Converter oder Shutter Encoder.")
        print(f"Admin-Hinweis: {exc}")
        return 3

    if config.write_summary_file:
        write_summary_files(plan)
        print("Zusammenfassung geschrieben: predigt-zusammenfassung.txt und predigt-info.json")

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
