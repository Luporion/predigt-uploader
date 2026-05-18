from __future__ import annotations

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
            f"MP4-Dateiname: {plan.target_mp4.name}",
            f"MP3-Dateiname: {plan.target_mp3.name}",
            "",
            "WordPress-Hinweise:",
            "- Titel, Prediger, Datum, Dienstart und Bibelstelle übertragen.",
            "- MP3 in WordPress hochladen.",
            "- Vimeo-Embed-Code später manuell einfügen, bis Vimeo-Automation eingebaut ist.",
        ]
    )


def write_summary_file(plan: ProcessingPlan) -> None:
    target_folder = plan.target_mp4.parent
    summary_path = target_folder / "predigt-zusammenfassung.txt"
    summary_path.write_text(build_summary_text(plan), encoding="utf-8")
