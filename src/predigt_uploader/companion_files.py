from __future__ import annotations

import hashlib
from pathlib import Path


WINDOWS_MAX_FILENAME_LENGTH = 255
SUMMARY_SUFFIX = " - Zusammenfassung.txt"
WORKFLOW_STATE_SUFFIX = ".predigt-workflow.json"


def recording_summary_path(final_mp4: Path) -> Path:
    return _companion_path(final_mp4, SUMMARY_SUFFIX)


def recording_workflow_state_path(final_mp4: Path) -> Path:
    return _companion_path(final_mp4, WORKFLOW_STATE_SUFFIX)


def _companion_path(final_mp4: Path, suffix: str) -> Path:
    """Build a Windows-safe companion name tied uniquely to one final MP4."""
    stem = final_mp4.stem
    filename = f"{stem}{suffix}"
    if len(filename) <= WINDOWS_MAX_FILENAME_LENGTH:
        return final_mp4.with_name(filename)

    digest = hashlib.sha256(stem.encode("utf-8")).hexdigest()[:10]
    marker = f"~{digest}"
    available = WINDOWS_MAX_FILENAME_LENGTH - len(marker) - len(suffix)
    shortened = stem[: max(1, available)].rstrip(" .") or "aufnahme"
    return final_mp4.with_name(f"{shortened}{marker}{suffix}")
