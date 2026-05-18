from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from .models import AppConfig


def default_config() -> AppConfig:
    return AppConfig(
        vmix_storage=Path(r"V:\vMixStorage"),
        recordings_base=Path(r"C:\Users\micro\Desktop\Aufnahmen"),
        mp3_base=Path(r"V:\Predigten\Predigten"),
    )


def candidate_config_paths(explicit_path: Path | None = None) -> list[Path]:
    paths: list[Path] = []
    if explicit_path is not None:
        paths.append(explicit_path)
    paths.append(Path.cwd() / "config.toml")
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(Path(appdata) / "PredigtUploader" / "config.toml")
    return paths


def _get_nested(data: dict[str, Any], section: str, key: str, fallback: Any) -> Any:
    return data.get(section, {}).get(key, fallback)


def load_config(explicit_path: Path | None = None) -> AppConfig:
    base = default_config()
    loaded: dict[str, Any] = {}

    for path in candidate_config_paths(explicit_path):
        if path.exists():
            with path.open("rb") as handle:
                loaded = tomllib.load(handle)
            break

    return AppConfig(
        vmix_storage=Path(_get_nested(loaded, "paths", "vmix_storage", str(base.vmix_storage))),
        recordings_base=Path(_get_nested(loaded, "paths", "recordings_base", str(base.recordings_base))),
        mp3_base=Path(_get_nested(loaded, "paths", "mp3_base", str(base.mp3_base))),
        ffmpeg_path=str(_get_nested(loaded, "paths", "ffmpeg_path", base.ffmpeg_path)),
        losslesscut_path=str(_get_nested(loaded, "paths", "losslesscut_path", base.losslesscut_path)),
        predigt_template=str(_get_nested(loaded, "naming", "predigt_template", base.predigt_template)),
        bibelstunde_template=str(_get_nested(loaded, "naming", "bibelstunde_template", base.bibelstunde_template)),
        folder_suffix_separator=str(_get_nested(loaded, "naming", "folder_suffix_separator", base.folder_suffix_separator)),
        copy_instead_of_move=bool(_get_nested(loaded, "workflow", "copy_instead_of_move", base.copy_instead_of_move)),
        write_summary_file=bool(_get_nested(loaded, "workflow", "write_summary_file", base.write_summary_file)),
    )
