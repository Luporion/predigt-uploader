from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from .models import AppConfig


class ConfigLoadError(RuntimeError):
    def __init__(self, user_message: str, admin_hint: str) -> None:
        super().__init__(admin_hint)
        self.user_message = user_message
        self.admin_hint = admin_hint


def default_config() -> AppConfig:
    return AppConfig(
        vmix_storage=Path(r"V:\vMixStorage"),
        recordings_base=Path.home() / "Desktop" / "Aufnahmen",
        mp3_base=Path(r"V:\Predigten\Predigten"),
    )


def user_config_path() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "PredigtUploader" / "config.toml"


def candidate_config_paths(explicit_path: Path | None = None) -> list[Path]:
    paths: list[Path] = []
    if explicit_path is not None:
        paths.append(explicit_path)
    paths.append(Path.cwd() / "config.toml")
    app_config = user_config_path()
    if app_config is not None:
        paths.append(app_config)
    return paths


def find_config_path(explicit_path: Path | None = None) -> Path | None:
    for path in candidate_config_paths(explicit_path):
        if path.exists():
            return path
    return None


def describe_config_source(explicit_path: Path | None = None) -> str:
    found = find_config_path(explicit_path)
    if explicit_path is not None:
        return str(explicit_path)
    if found is None:
        return "Standardconfig"
    app_config = user_config_path()
    if app_config is not None and found == app_config:
        return f"%APPDATA%\\PredigtUploader\\config.toml ({found})"
    if found == Path.cwd() / "config.toml":
        return f"Projekt-config.toml ({found})"
    return str(found)


def _get_nested(data: dict[str, Any], section: str, key: str, fallback: Any) -> Any:
    return data.get(section, {}).get(key, fallback)


def load_config(explicit_path: Path | None = None) -> AppConfig:
    base = default_config()
    loaded: dict[str, Any] = {}

    if explicit_path is not None and not explicit_path.exists():
        raise ConfigLoadError(
            "Die angegebene Konfigurationsdatei wurde nicht gefunden.",
            f"Config-Datei existiert nicht: {explicit_path}",
        )

    for path in candidate_config_paths(explicit_path):
        if path.exists():
            try:
                with path.open("rb") as handle:
                    loaded = tomllib.load(handle)
            except tomllib.TOMLDecodeError as exc:
                raise ConfigLoadError(
                    "Die Konfigurationsdatei ist ungültig.",
                    f"Ungültiges TOML in {path}: {exc}",
                ) from exc
            except OSError as exc:
                raise ConfigLoadError(
                    "Die Konfigurationsdatei konnte nicht gelesen werden.",
                    f"Config-Datei konnte nicht gelesen werden: {path}. Details: {exc}",
                ) from exc
            break

    return AppConfig(
        vmix_storage=Path(_get_nested(loaded, "paths", "vmix_storage", str(base.vmix_storage))),
        recordings_base=Path(_get_nested(loaded, "paths", "recordings_base", str(base.recordings_base))),
        mp3_base=Path(_get_nested(loaded, "paths", "mp3_base", str(base.mp3_base))),
        cut_mp4_folder=_optional_path(_get_nested(loaded, "paths", "cut_mp4_folder", "")),
        ffmpeg_path=str(_get_nested(loaded, "paths", "ffmpeg_path", base.ffmpeg_path)),
        losslesscut_path=str(_get_nested(loaded, "paths", "losslesscut_path", base.losslesscut_path)),
        predigt_template=str(_get_nested(loaded, "naming", "predigt_template", base.predigt_template)),
        bibelstunde_template=str(_get_nested(loaded, "naming", "bibelstunde_template", base.bibelstunde_template)),
        folder_suffix_separator=str(_get_nested(loaded, "naming", "folder_suffix_separator", base.folder_suffix_separator)),
        year_folder_template=str(_get_nested(loaded, "naming", "year_folder_template", base.year_folder_template)),
        copy_instead_of_move=bool(_get_nested(loaded, "workflow", "copy_instead_of_move", base.copy_instead_of_move)),
        open_target_folder=bool(_get_nested(loaded, "workflow", "open_target_folder", base.open_target_folder)),
        raw_archive_mode=str(_get_nested(loaded, "workflow", "raw_archive_mode", base.raw_archive_mode)),
    )


def _optional_path(value: Any) -> Path | None:
    text = str(value).strip()
    if not text:
        return None
    return Path(text)


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def save_user_config_values(
    *,
    paths: dict[str, str] | None = None,
    naming: dict[str, str] | None = None,
    workflow: dict[str, str | bool] | None = None,
) -> Path:
    path = user_config_path()
    if path is None:
        raise ConfigLoadError(
            "Die Einstellungen konnten nicht gespeichert werden.",
            "APPDATA ist nicht gesetzt; Benutzer-config.toml kann nicht bestimmt werden.",
        )

    data: dict[str, Any] = {}
    if path.exists():
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except (tomllib.TOMLDecodeError, OSError):
            data = {}

    if paths:
        data.setdefault("paths", {}).update(paths)
    if naming:
        data.setdefault("naming", {}).update(naming)
    if workflow:
        data.setdefault("workflow", {}).update(workflow)

    lines: list[str] = []
    for section in ("paths", "naming", "workflow"):
        values = data.get(section)
        if not isinstance(values, dict) or not values:
            continue
        lines.append(f"[{section}]")
        for key, value in values.items():
            if isinstance(value, bool):
                rendered = "true" if value else "false"
            else:
                rendered = _toml_string(str(value))
            lines.append(f"{key} = {rendered}")
        lines.append("")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
    except OSError as exc:
        raise ConfigLoadError(
            "Die Einstellungen konnten nicht gespeichert werden.",
            f"Benutzer-config.toml konnte nicht geschrieben werden: {path}. Details: {exc}",
        ) from exc
    return path
