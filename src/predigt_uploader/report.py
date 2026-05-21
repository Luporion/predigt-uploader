from __future__ import annotations

from .models import ProcessingPlan


def build_summary_text(plan: ProcessingPlan) -> str:
    info = plan.info
    title = info.title or "-"
    bible_reference = info.bible_reference or "-"
    speaker = info.speaker or "-"
    return "\n".join(
        [
            "PredigtUploader Zusammenfassung",
            "=============================",
            "",
            f"Datum: {info.sermon_date.strftime('%d.%m.%Y')}",
            f"Dienstart: {info.sermon_type}",
            f"Titel/Bezeichnung: {title}",
            f"Bibelstelle: {bible_reference}",
            f"Redner/Leitung/Name: {speaker}",
            f"Besonderheit Ordner: {info.folder_note or '-'}",
            "",
            f"MP4-Dateiname: {plan.target_mp4.name}",
            f"MP3-Dateiname: {plan.target_mp3.name}",
            "",
            "WordPress-Hinweise:",
            "- Titel/Bezeichnung, Datum, Dienstart, Bibelstelle und Redner - soweit vorhanden - übertragen.",
            "- MP3 in WordPress hochladen.",
            "- Vimeo-Embed-Code später manuell einfügen, bis Vimeo-Automation eingebaut ist.",
        ]
    )


def write_summary_file(plan: ProcessingPlan) -> None:
    target_folder = plan.target_mp4.parent
    summary_path = target_folder / "predigt-zusammenfassung.txt"
    summary_path.write_text(build_summary_text(plan), encoding="utf-8")
