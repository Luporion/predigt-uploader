from __future__ import annotations

import re

from .models import AppConfig, SermonInfo

WINDOWS_INVALID_CHARS = r'<>:"/\\|?*'
_TRANSLATION = str.maketrans({char: "-" for char in WINDOWS_INVALID_CHARS})


def sanitize_filename_part(value: str) -> str:
    """Return a Windows-safe but readable filename/folder part."""
    cleaned = value.strip().translate(_TRANSLATION)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned)
    cleaned = cleaned.strip(" .-")
    return cleaned


def build_media_filename(info: SermonInfo, config: AppConfig, extension: str) -> str:
    """Build the target media filename for a sermon."""
    if not extension.startswith("."):
        extension = f".{extension}"

    title = sanitize_filename_part(info.title)
    bible_reference = sanitize_filename_part(info.bible_reference)
    speaker = sanitize_filename_part(info.speaker)

    template = config.predigt_template
    if info.sermon_type.casefold() == "bibelstunde":
        template = config.bibelstunde_template

    filename = template.format(
        title=title,
        bible_reference=bible_reference,
        speaker=speaker,
        extension=extension,
    )
    return sanitize_filename_part(filename)


def build_folder_suffix(note: str) -> str:
    """Sanitize optional folder note."""
    return sanitize_filename_part(note)
