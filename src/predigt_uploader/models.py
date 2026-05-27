from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class ServiceTypeConfig:
    name: str
    requires_title: bool
    requires_bible_reference: bool
    requires_speaker: bool
    template: str
    title_label: str = "Titel"
    bible_reference_label: str = "Hauptbibelstelle"
    speaker_label: str = "Redner"
    optional_title: bool = False
    optional_bible_reference: bool = False
    optional_speaker: bool = False


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
    cut_mp4_folder: Path | None = None
    ffmpeg_path: str = "ffmpeg"
    losslesscut_path: str = ""
    predigt_template: str = "Predigt ({title}_{bible_reference})_{speaker}{extension}"
    bibelstunde_template: str = "Bibelstunde ({title_bible_reference})_{speaker}{extension}"
    vortrag_template: str = "Vortrag ({title})_{speaker}{extension}"
    lobpreis_template: str = "Lobpreis ({title}){speaker_suffix}{extension}"
    sonstiges_template: str = "{service_type} ({title}){speaker_suffix}{extension}"
    custom_service_types: tuple[ServiceTypeConfig, ...] = ()
    folder_suffix_separator: str = " - "
    year_folder_template: str = "{year}"
    copy_instead_of_move: bool = True
    open_target_folder: bool = True
    raw_archive_mode: str = "move"


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
