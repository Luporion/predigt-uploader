from __future__ import annotations

import json
from pathlib import Path

from .models import ProcessingPlan


def build_summary_text(plan: ProcessingPlan) -> str:
    info = plan.info
    return "\n".join(
        [
            "PredigtUploader Zusammenfassung",
            "=============================",
            "",
            f"Datum: {info.sermon_date.strftime('%d.%m.%Y')}",
            f"Typ: {info.sermon_type}",
            f"Titel: {info.title}",
            f"Hauptbibelstelle: {info.bible_reference}",
            f"Redner: {info.speaker}",
            f"Besonderheit Ordner: {info.folder_note or '-'}",
            "",
            f"MP4: {plan.target_mp4}",
            f"MP3: {plan.target_mp3}",
            "",
            "WordPress-Hinweis:",
            "- Titel, Prediger, Datum, Dienstart und Bibelstelle übertragen.",
            "- MP3 in WordPress hochladen.",
            "- Vimeo-Embed-Code später manuell einfügen, bis Vimeo-Automation eingebaut ist.",
        ]
    )


def write_summary_files(plan: ProcessingPlan) -> None:
    target_folder = plan.target_mp4.parent
    summary_path = target_folder / "predigt-zusammenfassung.txt"
    summary_path.write_text(build_summary_text(plan), encoding="utf-8")

    info_path = target_folder / "predigt-info.json"
    info_path.write_text(
        json.dumps(
            {
                "datum": plan.info.sermon_date.isoformat(),
                "typ": plan.info.sermon_type,
                "titel": plan.info.title,
                "hauptbibelstelle": plan.info.bible_reference,
                "redner": plan.info.speaker,
                "ordner_besonderheit": plan.info.folder_note,
                "source_mp4": str(plan.source_mp4),
                "target_mp4": str(plan.target_mp4),
                "target_mp3": str(plan.target_mp3),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
