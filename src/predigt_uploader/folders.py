from __future__ import annotations

from pathlib import Path

from .filename import build_folder_suffix
from .models import AppConfig, FolderResolution, SermonInfo


def date_prefix(info: SermonInfo) -> str:
    return info.sermon_date.strftime("%Y-%m-%d")


def find_date_folders(year_folder: Path, prefix: str) -> tuple[Path, ...]:
    if not year_folder.exists():
        return ()
    return tuple(sorted(path for path in year_folder.iterdir() if path.is_dir() and path.name.startswith(prefix)))


def year_folder_name(config: AppConfig, info: SermonInfo) -> str:
    return config.year_folder_template.format(year=info.sermon_date.year)


def suggest_folder(config: AppConfig, info: SermonInfo) -> Path:
    year_folder = config.recordings_base / year_folder_name(config, info)
    prefix = date_prefix(info)
    note = build_folder_suffix(info.folder_note)
    folder_name = prefix
    if note:
        folder_name = f"{prefix}{config.folder_suffix_separator}{note}"
    return year_folder / folder_name


def resolve_folder(config: AppConfig, info: SermonInfo) -> FolderResolution:
    year_folder = config.recordings_base / year_folder_name(config, info)
    prefix = date_prefix(info)
    candidates = find_date_folders(year_folder, prefix)
    suggested = suggest_folder(config, info)

    if not candidates:
        status = "missing"
    elif len(candidates) == 1:
        status = "single_existing"
    else:
        status = "multiple_existing"

    return FolderResolution(
        year_folder=year_folder,
        date_prefix=prefix,
        candidates=candidates,
        suggested_folder=suggested,
        status=status,
    )


def ensure_folder(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
