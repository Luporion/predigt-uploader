from __future__ import annotations

import re

from .config import default_service_types
from .models import AppConfig, SermonInfo, ServiceTypeConfig

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
    service_type = sanitize_filename_part(info.sermon_type)
    speaker_suffix = f"_{speaker}" if speaker else ""

    service_config = service_type_config_for(config, info.sermon_type)
    template = service_config.template

    filename = template.format(
        title=title,
        bible_reference=bible_reference,
        speaker=speaker,
        speaker_suffix=speaker_suffix,
        service_type=service_type,
        extension=extension,
    )
    return sanitize_filename_part(filename)


def service_type_config_for(config: AppConfig, name: str) -> ServiceTypeConfig:
    normalized = name.strip().casefold()
    for service_type in default_service_types(config) + config.custom_service_types:
        if service_type.name.casefold() == normalized:
            return service_type
    return ServiceTypeConfig(
        name=name or "Sonstiges",
        requires_title=True,
        requires_bible_reference=False,
        requires_speaker=False,
        template=config.sonstiges_template,
        optional_speaker=True,
    )


def build_folder_suffix(note: str) -> str:
    """Sanitize optional folder note."""
    return sanitize_filename_part(note)
