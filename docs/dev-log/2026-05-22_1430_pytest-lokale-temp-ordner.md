# Entwicklungsbericht: pytest-lokale-temp-ordner

## Ziel

Pytest auf Windows-Rechnern unabhaengiger von globalen Temp- und Cache-Berechtigungen machen, ohne feste Testpfade in `pyproject.toml` zu verankern.

## Geänderte Dateien

- `.gitignore`
- `STATUS.md`
- `pyproject.toml`
- `scripts/test.ps1`
- `Tests ausführen.cmd`
- `scripts/make-release-zip.ps1`
- `tests/test_manual_test_assets.py`
- `docs/dev-log/2026-05-22_1430_pytest-lokale-temp-ordner.md`

## Was wurde umgesetzt?

- Feste Pytest-Temp- und Cache-Pfade wurden aus `pyproject.toml` entfernt.
- `scripts/test.ps1` waehlt einen beschreibbaren Testordner: zuerst `%LOCALAPPDATA%\PredigtUploader\pytest`, danach `%TEMP%\PredigtUploader-pytest`.
- Das Script erstellt `run` und `cache` vor dem Test neu und bricht mit verstaendlicher Meldung ab, wenn kein Kandidat beschreibbar ist.
- `Tests ausführen.cmd` startet das Testscript per Doppelklick.
- `.pytest-tmp/`, `.pytest_cache/`, `Windows PowerShell.txt` und weitere lokale Test-/Build-Artefakte sind in `.gitignore` eingetragen.
- Das Release-ZIP-Script schliesst Test-/Cache-/Dev-Artefakte wie `.pytest-tmp`, `.pytest_cache`, `test-extract` und `Windows PowerShell.txt` explizit aus.
- Der Release-Script-Test prueft den aktuellen Namensaufbau mit `textual-preview`, ohne an eine feste Versionsnummer gebunden zu sein.
- `STATUS.md` wurde kurz aktualisiert.

## Tests

- `.\scripts\test.ps1`
- Ergebnis: `189 passed`

## Offene Punkte / Risiken

- `python -m pytest` nutzt weiterhin die normale, portable Projektkonfiguration. Fuer problematische Windows-Rechner ist `scripts/test.ps1` der robuste Startweg.

## Nächster sinnvoller Schritt

Auf dem Gemeinderechner `.\scripts\test.ps1` ausfuehren und pruefen, ob der bevorzugte LOCALAPPDATA-Ordner oder der TEMP-Fallback sauber verwendet wird.
