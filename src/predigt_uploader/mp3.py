from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .models import AppConfig


class Mp3ConversionError(RuntimeError):
    pass


def ffmpeg_available(config: AppConfig) -> bool:
    if Path(config.ffmpeg_path).exists():
        return True
    return shutil.which(config.ffmpeg_path) is not None


def convert_mp4_to_mp3(source_mp4: Path, target_mp3: Path, config: AppConfig) -> None:
    """Create an MP3 from an MP4 using FFmpeg.

    This function intentionally keeps FFmpeg invisible to the end user.
    """
    if not source_mp4.exists():
        raise Mp3ConversionError(f"Quelldatei existiert nicht: {source_mp4}")
    if not ffmpeg_available(config):
        raise Mp3ConversionError(
            "FFmpeg wurde nicht gefunden. Bitte ffmpeg_path in der Konfiguration prüfen."
        )

    target_mp3.parent.mkdir(parents=True, exist_ok=True)
    command = [
        config.ffmpeg_path,
        "-y",
        "-i",
        str(source_mp4),
        "-vn",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(target_mp3),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise Mp3ConversionError(
            "FFmpeg konnte die MP3 nicht erstellen. "
            f"Exit-Code: {result.returncode}. Fehler: {result.stderr[-1000:]}"
        )
