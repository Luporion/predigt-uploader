from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from .models import AppConfig, ServiceTypeConfig


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


def default_service_types(config: AppConfig) -> tuple[ServiceTypeConfig, ...]:
    return (
        ServiceTypeConfig("Predigt", True, True, True, config.predigt_template),
        ServiceTypeConfig("Bibelstunde", False, True, True, config.bibelstunde_template, title_label="Titel / Themenreihe", optional_title=True),
        ServiceTypeConfig("Vortrag", True, False, True, config.vortrag_template, optional_bible_reference=True),
        ServiceTypeConfig("Lobpreis", True, False, False, config.lobpreis_template, title_label="Titel oder Thema", speaker_label="Leitung", optional_speaker=True),
        ServiceTypeConfig("Gebetsstunde", True, False, False, config.sonstiges_template, title_label="Titel oder Thema", optional_speaker=True),
        ServiceTypeConfig("Zeugnis", True, False, False, config.sonstiges_template, optional_speaker=True),
        ServiceTypeConfig("Seminar", True, False, True, config.sonstiges_template),
        ServiceTypeConfig("Sonstiges", True, False, False, config.sonstiges_template, title_label="Titel oder Bezeichnung", speaker_label="Name", optional_speaker=True),
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

    config = AppConfig(
        vmix_storage=Path(_get_nested(loaded, "paths", "vmix_storage", str(base.vmix_storage))),
        recordings_base=Path(_get_nested(loaded, "paths", "recordings_base", str(base.recordings_base))),
        mp3_base=Path(_get_nested(loaded, "paths", "mp3_base", str(base.mp3_base))),
        cut_mp4_folder=_optional_path(_get_nested(loaded, "paths", "cut_mp4_folder", "")),
        ffmpeg_path=str(_get_nested(loaded, "paths", "ffmpeg_path", base.ffmpeg_path)),
        losslesscut_path=str(_get_nested(loaded, "paths", "losslesscut_path", base.losslesscut_path)),
        predigt_template=str(_get_nested(loaded, "naming", "predigt_template", base.predigt_template)),
        bibelstunde_template=str(_get_nested(loaded, "naming", "bibelstunde_template", base.bibelstunde_template)),
        vortrag_template=str(_get_nested(loaded, "naming", "vortrag_template", base.vortrag_template)),
        lobpreis_template=str(_get_nested(loaded, "naming", "lobpreis_template", base.lobpreis_template)),
        sonstiges_template=str(_get_nested(loaded, "naming", "sonstiges_template", base.sonstiges_template)),
        folder_suffix_separator=str(_get_nested(loaded, "naming", "folder_suffix_separator", base.folder_suffix_separator)),
        year_folder_template=str(_get_nested(loaded, "naming", "year_folder_template", base.year_folder_template)),
        copy_instead_of_move=bool(_get_nested(loaded, "workflow", "copy_instead_of_move", base.copy_instead_of_move)),
        open_target_folder=bool(_get_nested(loaded, "workflow", "open_target_folder", base.open_target_folder)),
        raw_archive_mode=str(_get_nested(loaded, "workflow", "raw_archive_mode", base.raw_archive_mode)),
    )
    custom_service_types = _parse_custom_service_types(_get_nested(loaded, "service_types", "additional", ()), config)
    return AppConfig(
        **{**config.__dict__, "custom_service_types": custom_service_types}
    )


def _optional_path(value: Any) -> Path | None:
    text = str(value).strip()
    if not text:
        return None
    return Path(text)


def _parse_custom_service_types(value: Any, config: AppConfig) -> tuple[ServiceTypeConfig, ...]:
    if isinstance(value, str):
        entries = [part for part in value.split(";") if part.strip()]
    elif isinstance(value, list):
        entries = [str(part) for part in value]
    else:
        return ()

    service_types: list[ServiceTypeConfig] = []
    for entry in entries:
        parts = [part.strip() for part in entry.split("|")]
        if len(parts) != 4 or not parts[0]:
            continue
        name = parts[0]
        requires_title = _parse_bool(parts[1])
        requires_bible = _parse_bool(parts[2])
        requires_speaker = _parse_bool(parts[3])
        service_types.append(
            ServiceTypeConfig(
                name=name,
                requires_title=requires_title,
                requires_bible_reference=requires_bible,
                requires_speaker=requires_speaker,
                template=_automatic_service_template(name, requires_title, requires_bible, requires_speaker, config),
            )
        )
    return tuple(service_types)


def _parse_bool(value: str) -> bool:
    return value.strip().casefold() in {"1", "true", "ja", "yes", "j"}


def _automatic_service_template(
    service_name: str,
    requires_title: bool,
    requires_bible_reference: bool,
    requires_speaker: bool,
    config: AppConfig,
) -> str:
    if requires_title and requires_bible_reference:
        base = f"{service_name} " + "({title}_{bible_reference})"
    elif requires_title:
        base = f"{service_name} " + "({title})"
    elif requires_bible_reference:
        base = f"{service_name} " + "({bible_reference})"
    else:
        base = service_name
    if requires_speaker:
        return base + "_{speaker}{extension}"
    return base + "{extension}"


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def save_user_config_values(
    *,
    paths: dict[str, str] | None = None,
    naming: dict[str, str] | None = None,
    workflow: dict[str, str | bool] | None = None,
    service_types: list[str] | None = None,
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
    if service_types is not None:
        data.setdefault("service_types", {})["additional"] = service_types

    lines: list[str] = []
    for section in ("paths", "naming", "workflow", "service_types"):
        values = data.get(section)
        if not isinstance(values, dict) or not values:
            continue
        lines.append(f"[{section}]")
        for key, value in values.items():
            if isinstance(value, bool):
                rendered = "true" if value else "false"
            elif isinstance(value, list):
                rendered = "[" + ", ".join(_toml_string(str(item)) for item in value) + "]"
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
