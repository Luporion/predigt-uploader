from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SPEAKER_HISTORY_SCHEMA_VERSION = 1
SPEAKER_HISTORY_FILENAME = "speakers.json"


def speaker_history_path(environ: dict[str, str] | None = None) -> Path:
    values = os.environ if environ is None else environ
    appdata = values.get("APPDATA")
    if not appdata:
        raise OSError("APPDATA ist nicht gesetzt; die Prediger-Historie kann nicht bestimmt werden.")
    return Path(appdata) / "PredigtUploader" / SPEAKER_HISTORY_FILENAME


def normalize_speaker_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


@dataclass
class SpeakerHistory:
    path: Path

    @classmethod
    def for_current_user(cls) -> SpeakerHistory:
        return cls(speaker_history_path())

    def list(self) -> tuple[str, ...]:
        if not self.path.exists():
            return ()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise OSError(f"Die Prediger-Historie konnte nicht gelesen werden: {self.path}") from exc
        names = data.get("speakers", ()) if isinstance(data, dict) else ()
        return _unique_names(names if isinstance(names, list) else ())

    def add(self, name: str) -> tuple[str, ...]:
        cleaned = normalize_speaker_name(name)
        if not cleaned:
            return self.list()
        names = list(self.list())
        if cleaned.casefold() not in {item.casefold() for item in names}:
            names.append(cleaned)
            names.sort(key=str.casefold)
            self._save(names)
        return tuple(names)

    def remove(self, name: str) -> tuple[str, ...]:
        key = normalize_speaker_name(name).casefold()
        names = [item for item in self.list() if item.casefold() != key]
        self._save(names)
        return tuple(names)

    def rename(self, old_name: str, new_name: str) -> tuple[str, ...]:
        old_key = normalize_speaker_name(old_name).casefold()
        cleaned = normalize_speaker_name(new_name)
        if not old_key:
            raise ValueError("Bitte zuerst einen gespeicherten Prediger auswählen.")
        if not cleaned:
            raise ValueError("Der neue Name darf nicht leer sein.")
        names = list(self.list())
        if not any(item.casefold() == old_key for item in names):
            raise ValueError("Der ausgewählte Prediger wurde nicht gefunden.")
        new_key = cleaned.casefold()
        if new_key != old_key and any(item.casefold() == new_key for item in names):
            raise ValueError("Dieser Prediger ist bereits gespeichert.")
        names = [cleaned if item.casefold() == old_key else item for item in names]
        names.sort(key=str.casefold)
        self._save(names)
        return tuple(names)

    def suggest(self, query: str, *, limit: int = 6) -> tuple[str, ...]:
        normalized = normalize_speaker_name(query).casefold()
        names = self.list()
        if not normalized:
            return names[:limit]
        starts = [name for name in names if name.casefold().startswith(normalized)]
        contains = [name for name in names if normalized in name.casefold() and name not in starts]
        return tuple((starts + contains)[:limit])

    def _save(self, names: Iterable[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        payload = {
            "schema_version": SPEAKER_HISTORY_SCHEMA_VERSION,
            "speakers": list(_unique_names(names)),
        }
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
        finally:
            if temporary.exists():
                temporary.unlink()


def _unique_names(names: Iterable[object]) -> tuple[str, ...]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in names:
        cleaned = normalize_speaker_name(str(value))
        key = cleaned.casefold()
        if cleaned and key not in seen:
            unique.append(cleaned)
            seen.add(key)
    return tuple(unique)
