from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class SermonInfo:
    sermon_date: date
    title: str
    bible_reference: str
    speaker: str
    sermon_type: str = "Predigt"
    folder_note: str = ""


@dataclass(frozen=True)
class AppConfig:
    vmix_storage: Path
    recordings_base: Path
    mp3_base: Path
    ffmpeg_path: str = "ffmpeg"
    losslesscut_path: str = ""
    predigt_template: str = "Predigt ({title}_{bible_reference})_{speaker}{extension}"
    bibelstunde_template: str = "Bibelstunde ({bible_reference})_{speaker}{extension}"
    folder_suffix_separator: str = " - "
    copy_instead_of_move: bool = True
    write_summary_file: bool = True


@dataclass(frozen=True)
class FolderResolution:
    year_folder: Path
    date_prefix: str
    candidates: tuple[Path, ...]
    suggested_folder: Path
    status: str


@dataclass(frozen=True)
class ProcessingPlan:
    source_mp4: Path
    target_mp4: Path
    target_mp3: Path
    info: SermonInfo
