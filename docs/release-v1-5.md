# Release-ZIP: lokale Version 1.5

Diese Anleitung beschreibt die einfache ZIP-Auslieferung für den Gemeinderechner. Die ZIP enthält nur die lokale Phase 1.5 und keine Vimeo- oder WordPress-Automatisierung.

## ZIP erstellen

Im Projektordner:

```powershell
.\scripts\make-release-zip.ps1
```

Das Skript erstellt:

```text
dist\predigt-uploader-v0.1.5-local.zip
```

## Diese Dateien und Ordner gehören in die ZIP

- `src/`
- `scripts/`
- `docs/install-v1-5.md`
- `docs/manual-test-v1-5.md`
- `README.md`
- `pyproject.toml`
- `config.example.toml`
- `PredigtUploader starten.cmd`
- `PredigtUploader einrichten.cmd`
- `PredigtUploader Systemcheck.cmd`

## Diese Dateien und Ordner gehören nicht in die ZIP

- `.git/`
- `.venv/`
- `logs/`
- `dist/`
- `build/`
- `*.egg-info/`, zum Beispiel `src/predigt_uploader.egg-info/`
- `*.pyc`
- `__pycache__/`
- `.pytest_cache/`
- echte `config.toml`
- Test-Ausgabedateien oder lokale Aufnahme-/Exportdateien

## Auf dem Gemeinderechner entpacken

1. ZIP auf den Gemeinderechner kopieren.
2. ZIP in einen festen Ordner entpacken, zum Beispiel unter `Dokumente` oder auf ein gemeinsames Technik-Laufwerk.
3. Den entpackten Ordner öffnen.
4. Bei Bedarf `config.example.toml` nach `config.toml` kopieren und lokale Pfade anpassen.

Keine Zugangsdaten, Tokens oder Passwörter in `config.toml` eintragen.

## Danach per Doppelklick nutzen

Für normale Nutzer sind diese Dateien im entpackten Ordner wichtig:

- `PredigtUploader einrichten.cmd`: richtet `.venv` und Abhängigkeiten ein.
- `PredigtUploader Systemcheck.cmd`: prüft Python, Wizard, FFmpeg und optional LosslessCut.
- `PredigtUploader starten.cmd`: startet den lokalen Wizard.

Empfohlene Reihenfolge beim ersten Mal:

1. `PredigtUploader einrichten.cmd`
2. `PredigtUploader Systemcheck.cmd`
3. `PredigtUploader starten.cmd`

Später kann eine Desktop-Verknüpfung auf `PredigtUploader starten.cmd` erstellt werden. Die Datei selbst sollte im entpackten Projektordner bleiben.
