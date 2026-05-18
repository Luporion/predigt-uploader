from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import ProcessingPlan


@dataclass
class WorkflowLog:
    path: Path
    enabled: bool = True

    @classmethod
    def start(cls, *, config_path: str | None, base_dir: Path | None = None) -> "WorkflowLog":
        now = datetime.now()
        log_dir = (base_dir or Path.cwd()) / "logs"
        log_path = log_dir / f"predigt-uploader-{now.strftime('%Y%m%d-%H%M%S')}.log"
        log = cls(log_path)
        log._write_lines(
            [
                "PredigtUploader Laufprotokoll",
                "=============================",
                f"Startzeit: {now.isoformat(timespec='seconds')}",
                f"Config: {config_path if config_path else 'Standardconfig'}",
                "",
            ]
        )
        return log

    def event(self, message: str) -> None:
        self._write_lines([f"[INFO] {message}"])

    def error(self, message: str, *, admin_hint: str | None = None) -> None:
        lines = [f"[FEHLER] {message}"]
        if admin_hint:
            lines.append(f"Admin-Hinweis: {admin_hint}")
        self._write_lines(lines)

    def plan(self, plan: ProcessingPlan) -> None:
        self._write_lines(
            [
                "[PLAN]",
                f"Quell-MP4: {plan.source_mp4}",
                f"Zielordner: {plan.target_mp4.parent}",
                f"Finaler MP4-Dateiname: {plan.target_mp4.name}",
                f"Finaler MP3-Dateiname: {plan.target_mp3.name}",
            ]
        )

    def finish(self, message: str) -> None:
        self._write_lines([f"[ENDE] {message}"])

    def _write_lines(self, lines: list[str]) -> None:
        if not self.enabled:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                for line in lines:
                    handle.write(f"{line}\n")
                handle.write("\n")
        except OSError:
            self.enabled = False
